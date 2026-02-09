CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fuzzy matching

-- Check existing indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'places';

-- Trigram index for fuzzy name matching (O(log n) lookups)
CREATE INDEX IF NOT EXISTS idx_places_name_trgm 
ON places USING gin(name gin_trgm_ops);

-- GIN index for word_similarity (better for partial matches)
CREATE INDEX IF NOT EXISTS idx_places_name_gist
ON places USING gist(name gist_trgm_ops);

-- Spatial index for polygon operations (O(log n) for ST_Contains, ST_Intersects)
CREATE INDEX IF NOT EXISTS idx_places_polygon 
ON places USING gist(polygon);

-- B-tree index for hierarchy level filtering
CREATE INDEX IF NOT EXISTS idx_places_hierarchy 
ON places(hierarchy_level);

-- CRITICAL: B-tree index for parent_id lookups (hierarchical aggregation)
-- This massively speeds up get_children and hierarchical queries
CREATE INDEX IF NOT EXISTS idx_places_parent_id 
ON places(parent_id);

-- CRITICAL: B-tree index for id lookups (batch .in_() queries)
-- PostgreSQL uses this for efficient multi-ID lookups
CREATE INDEX IF NOT EXISTS idx_places_id 
ON places(id);

-- Composite index for common parent + hierarchy queries
-- Speeds up queries like: WHERE parent_id = X AND hierarchy_level = Y
CREATE INDEX IF NOT EXISTS idx_places_parent_hierarchy 
ON places(parent_id, hierarchy_level);

-- Note: No composite GIST index for (polygon, hierarchy_level) needed
-- PostgreSQL will use idx_places_polygon for spatial queries and can combine
-- it with idx_places_hierarchy using bitmap index scans when needed

-- Function 1: Fuzzy name search with trigram similarity
-- ADMINISTRATIVE WEIGHTED MATCHING: Aggressive fuzzy threshold (0.30) with hierarchy priority
-- Prioritizes provinces/districts over villages for better relevance
CREATE OR REPLACE FUNCTION search_places_fuzzy(
    search_name TEXT,
    similarity_threshold REAL DEFAULT 0.30  -- AGGRESSIVE: 0.30 for true fuzzy matching (hierarchy sorts trash to bottom)
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    hierarchy_level INT,
    similarity_score REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id,
        p.name,
        p.hierarchy_level,
        -- Use word_similarity for better partial matching on long names (AJK, etc)
        GREATEST(
            similarity(p.name, search_name),
            word_similarity(search_name, p.name)
        )::REAL as similarity_score
    FROM places p
    WHERE (
        p.name % search_name  -- Use the % operator which leverages the trigram index
        OR similarity(p.name, search_name) > 0.3
        OR word_similarity(search_name, p.name) > 0.4  -- More aggressive for long names
    )
    ORDER BY 
        -- HIERARCHY PRIORITY: 1) Lower hierarchy first (L1>L2>L3), 2) similarity score, 3) exact match
        -- A 30% match on a Province/District is more relevant than 90% on a remote village
        hierarchy_level ASC,
        similarity_score DESC, 
        CASE WHEN p.name = search_name THEN 0 ELSE 1 END
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;

-- Function 2: Find place containing a point
CREATE OR REPLACE FUNCTION find_place_by_point(
    lon FLOAT,
    lat FLOAT
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    hierarchy_level INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT p.id, p.name, p.hierarchy_level
    FROM places p
    WHERE ST_Contains(p.polygon, ST_SetSRID(ST_MakePoint(lon, lat), 4326))
    ORDER BY hierarchy_level DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Drop old grid-based function (if it exists from previous versions)
DROP FUNCTION IF EXISTS get_directional_grid_cell(geometry, text);

-- NEW: Radial Sector-based Directional Query with Accuracy Enhancements
-- Uses centroid azimuth (polar coordinates) instead of BBox grid
-- Eliminates latitudinal leakage and provides true geographic directionality
-- 
-- Improvements:
-- 1. Aspect-ratio aware central envelope (handles tall vs wide provinces)
-- 2. Province-size aware sector widths (narrower for large provinces)
-- 3. Strict administrative containment (ST_Covers instead of ST_Intersects)
-- 4. Directional bbox secondary filter (prevents diagonal leakage)
CREATE OR REPLACE FUNCTION find_places_in_direction(
    base_place_ids UUID[],
    direction TEXT
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    hierarchy_level INT,
    parent_id UUID
) AS $$
DECLARE
    combined_geom GEOMETRY;
    base_centroid GEOMETRY;
    dir_lower TEXT;
    -- Bounding box variables
    bbox_xmin FLOAT;
    bbox_xmax FLOAT;
    bbox_ymin FLOAT;
    bbox_ymax FLOAT;
    bbox_width FLOAT;
    bbox_height FLOAT;
    bbox_area FLOAT;
    aspect_ratio FLOAT;
    -- Central envelope variables
    horizontal_margin FLOAT;
    vertical_margin FLOAT;
    central_envelope GEOMETRY;
    -- Directional sector variables
    -- INCLUSIVE OVERLAPPING SECTORS: Wider beams eliminate geographic holes
    cardinal_half_width FLOAT := 67.5;  -- Default 135° wide beam (±67.5° from center) - OVERLAPPING
    ordinal_half_width FLOAT := 33.75;  -- Default 67.5° ordinal wedge (±33.75°) - OVERLAPPING
    directional_bbox GEOMETRY;
BEGIN
    -- Step 1: Get the combined polygon of all base regions
    SELECT ST_Union(p.polygon) INTO combined_geom
    FROM places p
    WHERE p.id = ANY(base_place_ids);
    
    -- Early exit if no base geometry found
    IF combined_geom IS NULL THEN
        RAISE NOTICE 'No base geometry found for provided place IDs';
        RETURN;
    END IF;
    
    -- Validate geometry before processing
    IF NOT ST_IsValid(combined_geom) THEN
        RAISE WARNING 'Invalid geometry detected, attempting repair';
        combined_geom := ST_MakeValid(combined_geom);
    END IF;
    
    -- Step 2: Calculate geometry metadata
    base_centroid := ST_PointOnSurface(combined_geom);
    bbox_xmin := ST_XMin(combined_geom);
    bbox_xmax := ST_XMax(combined_geom);
    bbox_ymin := ST_YMin(combined_geom);
    bbox_ymax := ST_YMax(combined_geom);
    bbox_width := bbox_xmax - bbox_xmin;
    bbox_height := bbox_ymax - bbox_ymin;
    bbox_area := ST_Area(combined_geom::geography);
    aspect_ratio := bbox_height / NULLIF(bbox_width, 0);
    
    aspect_ratio := bbox_height / NULLIF(bbox_width, 0);
    
    -- Normalize direction
    dir_lower := LOWER(TRIM(direction));
    
    -- Step 3: Adjust sector widths based on province size
    -- INCLUSIVE OVERLAPPING: All provinces use wide beams to eliminate holes
    -- Large provinces (Punjab, Sindh, Balochistan): 120° beams for smooth coverage
    -- Small provinces (GB, AJK, KP): 135° beams for maximum inclusivity
    IF bbox_area > 150000000000 THEN  -- ~150,000 km² threshold (catches Sindh, Punjab, Balochistan)
        cardinal_half_width := 60.0;   -- 120° total width (OVERLAPPING)
        ordinal_half_width := 30.0;    -- 60° total width (OVERLAPPING)
        RAISE NOTICE 'Large province detected (area: % km²), using overlapping sectors (120°)', bbox_area / 1000000;
    ELSE  -- Small provinces
        cardinal_half_width := 67.5;   -- 135° total width (WIDE OVERLAPPING)
        ordinal_half_width := 33.75;   -- 67.5° total width (WIDE OVERLAPPING)
        RAISE NOTICE 'Small province detected (area: % km²), using wide overlapping sectors (135°)', bbox_area / 1000000;
    END IF;
    
    -- Step 4: CENTRAL LOGIC - Aspect-ratio aware rectangular envelope
    -- WIDER CENTRAL: Reduced margins (20-25%) for more inclusive interior coverage
    -- Captures larger central portions of provinces
    IF dir_lower IN ('central', 'middle') THEN
        -- Determine margins based on aspect ratio
        IF aspect_ratio > 1.2 THEN
            -- Tall province (height > 1.2 × width)
            horizontal_margin := 0.25;  -- 25% margin (WIDER for better coverage)
            vertical_margin := 0.25;    -- 25% margin (WIDER for better coverage)
            RAISE NOTICE 'Tall province (aspect: %, WxH: %x%), margins H:25%% V:25%%', 
                         ROUND(aspect_ratio::numeric, 2), ROUND(bbox_width::numeric, 2), ROUND(bbox_height::numeric, 2);
        ELSIF aspect_ratio < 0.83 THEN
            -- Wide province (width > 1.2 × height, or aspect < 0.83)
            horizontal_margin := 0.20;  -- 20% margin (MUCH WIDER)
            vertical_margin := 0.25;    -- 25% margin (WIDER)
            RAISE NOTICE 'Wide province (aspect: %, WxH: %x%), margins H:20%% V:25%%', 
                         ROUND(aspect_ratio::numeric, 2), ROUND(bbox_width::numeric, 2), ROUND(bbox_height::numeric, 2);
        ELSE
            -- Balanced province (0.83 <= aspect <= 1.2)
            horizontal_margin := 0.22;  -- 22% margin (WIDER for inclusivity)
            vertical_margin := 0.22;    -- 22% margin (EQUAL and WIDER)
            RAISE NOTICE 'Balanced province (aspect: %, WxH: %x%), margins H:22%% V:22%%', 
                         ROUND(aspect_ratio::numeric, 2), ROUND(bbox_width::numeric, 2), ROUND(bbox_height::numeric, 2);
        END IF;
        
        -- Create central envelope
        central_envelope := ST_MakeEnvelope(
            bbox_xmin + (bbox_width * horizontal_margin),   -- Left edge
            bbox_ymin + (bbox_height * vertical_margin),    -- Bottom edge
            bbox_xmax - (bbox_width * horizontal_margin),   -- Right edge
            bbox_ymax - (bbox_height * vertical_margin),    -- Top edge
            4326  -- EPSG:4326 (WGS84)
        );
        
        RETURN QUERY
        SELECT 
            p.id,
            p.name,
            p.hierarchy_level,
            p.parent_id
        FROM places p
        WHERE p.polygon IS NOT NULL
            -- Must be within base region - use ST_Covers on centroid to prevent cross-province leakage
            AND ST_Covers(combined_geom, ST_PointOnSurface(p.polygon))
            -- STRICT: Place's centroid must be within central envelope
            AND ST_Covers(central_envelope, ST_PointOnSurface(p.polygon))
            -- Exclude base places themselves
            AND NOT (p.id = ANY(base_place_ids))
        ORDER BY p.hierarchy_level DESC;
        
        RETURN;
    END IF;
    
    -- Step 5: Create directional bounding box filter (secondary constraint)
    -- SOFTENED BOXES: Relaxed from 60% to 75% (25% exclusion) for inclusive coverage
    -- This allows South Sindh to capture Karachi, North Punjab to reach mid-latitude districts
    IF dir_lower IN ('north', 'northern') THEN
        -- Northern bbox: top 75% of province (SOFTENED)
        directional_bbox := ST_MakeEnvelope(
            bbox_xmin, 
            bbox_ymin + (bbox_height * 0.25),  -- Start 25% from bottom (was 40%)
            bbox_xmax, 
            bbox_ymax, 
            4326
        );
    ELSIF dir_lower IN ('south', 'southern') THEN
        -- Southern bbox: bottom 75% of province (SOFTENED)
        directional_bbox := ST_MakeEnvelope(
            bbox_xmin, 
            bbox_ymin, 
            bbox_xmax, 
            bbox_ymax - (bbox_height * 0.25),  -- End 25% from top (was 40%)
            4326
        );
    ELSIF dir_lower IN ('east', 'eastern') THEN
        -- Eastern bbox: right 75% of province (SOFTENED)
        directional_bbox := ST_MakeEnvelope(
            bbox_xmin + (bbox_width * 0.25),  -- Start 25% from left (was 40%)
            bbox_ymin, 
            bbox_xmax, 
            bbox_ymax, 
            4326
        );
    ELSIF dir_lower IN ('west', 'western') THEN
        -- Western bbox: left 75% of province (SOFTENED)
        directional_bbox := ST_MakeEnvelope(
            bbox_xmin, 
            bbox_ymin, 
            bbox_xmax - (bbox_width * 0.25),  -- End 25% from right (was 40%)
            bbox_ymax, 
            4326
        );
    -- Ordinal directions: Use combined bbox filters to prevent diagonal leakage
    -- INCLUSIVE ORDINALS: 75% coverage (25% exclusion) for better diagonal reach
    ELSIF dir_lower LIKE '%north%east%' OR dir_lower LIKE '%northeast%' THEN
        -- North-East bbox: top 75% AND right 75% (SOFTENED)
        directional_bbox := ST_MakeEnvelope(
            bbox_xmin + (bbox_width * 0.25),   -- Right 75% (was 70%)
            bbox_ymin + (bbox_height * 0.25),  -- Top 75% (was 70%)
            bbox_xmax, 
            bbox_ymax, 
            4326
        );
    ELSIF dir_lower LIKE '%south%east%' OR dir_lower LIKE '%southeast%' THEN
        -- South-East bbox: bottom 75% AND right 75% (SOFTENED)
        directional_bbox := ST_MakeEnvelope(
            bbox_xmin + (bbox_width * 0.25),   -- Right 75% (was 70%)
            bbox_ymin, 
            bbox_xmax, 
            bbox_ymax - (bbox_height * 0.25),  -- Bottom 75% (was 70%)
            4326
        );
    ELSIF dir_lower LIKE '%south%west%' OR dir_lower LIKE '%southwest%' THEN
        -- South-West bbox: bottom 75% AND left 75% (SOFTENED)
        directional_bbox := ST_MakeEnvelope(
            bbox_xmin, 
            bbox_ymin, 
            bbox_xmax - (bbox_width * 0.25),   -- Left 75% (was 70%)
            bbox_ymax - (bbox_height * 0.25),  -- Bottom 75% (was 70%)
            4326
        );
    ELSIF dir_lower LIKE '%north%west%' OR dir_lower LIKE '%northwest%' THEN
        -- North-West bbox: top 75% AND left 75% (SOFTENED)
        directional_bbox := ST_MakeEnvelope(
            bbox_xmin, 
            bbox_ymin + (bbox_height * 0.25),  -- Top 75% (was 70%)
            bbox_xmax - (bbox_width * 0.25),   -- Left 75% (was 70%)
            bbox_ymax, 
            4326
        );
    ELSE
        -- No bbox filter for unrecognized directions
        directional_bbox := NULL;
    END IF;
    
    -- Step 6: DIRECTIONAL LOGIC - Azimuth-based radial sectors
    -- Cardinal directions use dynamic width (67.5° or 90° based on province size)
    -- Ordinal directions use dynamic width (33.75° or 45°)
    -- Combines azimuth filtering with optional bbox constraint
    RETURN QUERY
    SELECT 
        p.id,
        p.name,
        p.hierarchy_level,
        p.parent_id
    FROM places p,
         LATERAL (
             -- Calculate azimuth from base centroid to place centroid
             SELECT DEGREES(ST_Azimuth(
                 base_centroid,
                 ST_PointOnSurface(p.polygon)
             )) AS azimuth_deg
         ) AS az
    WHERE p.polygon IS NOT NULL
        -- CRITICAL: Prevent Level 0 (Country) and Level 1 (Province) from appearing in directional sub-queries
        -- Directional queries should only return districts (Level 2) or tehsils (Level 3)
        AND p.hierarchy_level >= 2
        -- Must be within base region - use ST_Covers on centroid to prevent cross-province leakage
        AND ST_Covers(combined_geom, ST_PointOnSurface(p.polygon))
        -- Exclude base places themselves
        AND NOT (p.id = ANY(base_place_ids))
        -- Optional directional bbox filter (only for cardinal directions)
        AND (directional_bbox IS NULL OR ST_Covers(directional_bbox, ST_PointOnSurface(p.polygon)))
        -- Azimuth-based sector filtering
        AND (
            -- North: Centered at 0° (wraps around 360°)
            (dir_lower IN ('north', 'northern') 
                AND (az.azimuth_deg >= (360 - cardinal_half_width) OR az.azimuth_deg < cardinal_half_width))
            
            -- East: Centered at 90°
            OR (dir_lower IN ('east', 'eastern') 
                AND az.azimuth_deg >= (90 - cardinal_half_width) 
                AND az.azimuth_deg < (90 + cardinal_half_width))
            
            -- South: Centered at 180°
            OR (dir_lower IN ('south', 'southern') 
                AND az.azimuth_deg >= (180 - cardinal_half_width) 
                AND az.azimuth_deg < (180 + cardinal_half_width))
            
            -- West: Centered at 270°
            OR (dir_lower IN ('west', 'western') 
                AND az.azimuth_deg >= (270 - cardinal_half_width) 
                AND az.azimuth_deg < (270 + cardinal_half_width))
            
            -- North-East: Centered at 45° (ordinal wedge)
            OR ((dir_lower LIKE '%north%east%' OR dir_lower LIKE '%northeast%')
                AND az.azimuth_deg >= (45 - ordinal_half_width) 
                AND az.azimuth_deg < (45 + ordinal_half_width))
            
            -- South-East: Centered at 135° (ordinal wedge)
            OR ((dir_lower LIKE '%south%east%' OR dir_lower LIKE '%southeast%')
                AND az.azimuth_deg >= (135 - ordinal_half_width) 
                AND az.azimuth_deg < (135 + ordinal_half_width))
            
            -- South-West: Centered at 225° (ordinal wedge)
            OR ((dir_lower LIKE '%south%west%' OR dir_lower LIKE '%southwest%')
                AND az.azimuth_deg >= (225 - ordinal_half_width) 
                AND az.azimuth_deg < (225 + ordinal_half_width))
            
            -- North-West: Centered at 315° (ordinal wedge)
            OR ((dir_lower LIKE '%north%west%' OR dir_lower LIKE '%northwest%')
                AND az.azimuth_deg >= (315 - ordinal_half_width) 
                AND az.azimuth_deg < (315 + ordinal_half_width))
        )
    ORDER BY p.hierarchy_level DESC;
END;
$$ LANGUAGE plpgsql;