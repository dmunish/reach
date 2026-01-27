CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fuzzy matching

-- Check existing indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'places';

-- Trigram index for fuzzy name matching
CREATE INDEX IF NOT EXISTS idx_places_name_trgm 
ON places USING gin(name gin_trgm_ops);

-- GIN index for word_similarity (better for partial matches)
CREATE INDEX IF NOT EXISTS idx_places_name_gist
ON places USING gist(name gist_trgm_ops);

-- Spatial index for polygon operations (O(log n) for ST_Contains, ST_Intersects)
CREATE INDEX IF NOT EXISTS idx_places_polygon 
ON places USING gist(polygon);

-- Hierarchy level index
CREATE INDEX IF NOT EXISTS idx_places_hierarchy 
ON places(hierarchy_level);

-- Function 1: Fuzzy name search with trigram similarity
CREATE OR REPLACE FUNCTION search_places_fuzzy(
    search_name TEXT,
    similarity_threshold REAL DEFAULT 0.85
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
        -- Use word_similarity for better partial matching on short strings
        GREATEST(
            similarity(p.name, search_name),
            word_similarity(search_name, p.name)
        )::REAL as similarity_score
    FROM places p
    WHERE (
        similarity(p.name, search_name) > similarity_threshold
        OR word_similarity(search_name, p.name) > similarity_threshold
    )
    ORDER BY 
        -- Prioritize: 1) similarity score, 2) prefer exact name matches, 3) lower hierarchy levels (L2 before L3)
        similarity_score DESC, 
        CASE WHEN p.name = search_name THEN 0 ELSE 1 END,
        hierarchy_level ASC
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

-- Helper function for directional grid
CREATE OR REPLACE FUNCTION get_directional_grid_cell(
    bbox GEOMETRY,
    direction TEXT
)
RETURNS GEOMETRY AS $$
DECLARE
    minx FLOAT; miny FLOAT; maxx FLOAT; maxy FLOAT;
    width FLOAT; height FLOAT;
    cell_width FLOAT; cell_height FLOAT;
    result_geom GEOMETRY;
BEGIN
    -- Get bounding box coordinates
    minx := ST_XMin(bbox);
    miny := ST_YMin(bbox);
    maxx := ST_XMax(bbox);
    maxy := ST_YMax(bbox);
    
    width := maxx - minx;
    height := maxy - miny;
    cell_width := width / 3.0;
    cell_height := height / 3.0;
    
    -- Create geometry based on direction
    CASE LOWER(direction)
        WHEN 'north', 'northern' THEN
            -- Top 3 cells
            result_geom := ST_MakeEnvelope(minx, miny + 2*cell_height, maxx, maxy, 4326);
        WHEN 'south', 'southern' THEN
            -- Bottom 3 cells
            result_geom := ST_MakeEnvelope(minx, miny, maxx, miny + cell_height, 4326);
        WHEN 'east', 'eastern' THEN
            -- Right 3 cells
            result_geom := ST_MakeEnvelope(minx + 2*cell_width, miny, maxx, maxy, 4326);
        WHEN 'west', 'western' THEN
            -- Left 3 cells
            result_geom := ST_MakeEnvelope(minx, miny, minx + cell_width, maxy, 4326);
        WHEN 'central', 'middle' THEN
            -- Middle 3 cells horizontally
            result_geom := ST_MakeEnvelope(minx + cell_width, miny, minx + 2*cell_width, maxy, 4326);
        WHEN 'north-eastern', 'northeastern', 'north eastern' THEN
            -- Top-right cell
            result_geom := ST_MakeEnvelope(minx + 2*cell_width, miny + 2*cell_height, maxx, maxy, 4326);
        WHEN 'north-western', 'northwestern', 'north western' THEN
            -- Top-left cell
            result_geom := ST_MakeEnvelope(minx, miny + 2*cell_height, minx + cell_width, maxy, 4326);
        WHEN 'south-eastern', 'southeastern', 'south eastern' THEN
            -- Bottom-right cell
            result_geom := ST_MakeEnvelope(minx + 2*cell_width, miny, maxx, miny + cell_height, 4326);
        WHEN 'south-western', 'southwestern', 'south western' THEN
            -- Bottom-left cell
            result_geom := ST_MakeEnvelope(minx, miny, minx + cell_width, miny + cell_height, 4326);
        ELSE
            -- Default to full bounding box
            result_geom := bbox;
    END CASE;
    
    RETURN result_geom;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

DROP FUNCTION IF EXISTS find_places_in_direction(uuid[], text);

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
    bbox GEOMETRY;
    grid_cell GEOMETRY;
    clipped_search_area GEOMETRY;
BEGIN
    -- Get the combined polygon of all base regions (works for any hierarchy level)
    SELECT ST_Union(p.polygon) INTO combined_geom
    FROM places p
    WHERE p.id = ANY(base_place_ids);
    
    -- Early exit if no base geometry found
    IF combined_geom IS NULL THEN
        RETURN;
    END IF;
    
    -- Validate geometry before processing
    IF NOT ST_IsValid(combined_geom) THEN
        RAISE WARNING 'Invalid geometry detected for base places, attempting repair';
        combined_geom := ST_MakeValid(combined_geom);
    END IF;
    
    -- Calculate bounding box for grid generation
    bbox := ST_Envelope(combined_geom);
    
    -- Step 3: Adjust sector widths based on province size
    -- Large provinces (Punjab, Sindh, Balochistan) get narrower sectors to reduce over-inclusion
    -- Small provinces (GB, AJK, KP) keep wide 90° beams for better coverage
    -- Lowered threshold from 200,000 km² to 150,000 km² to catch Sindh
    IF bbox_area > 150000000000 THEN  -- ~150,000 km² threshold (catches Sindh, Punjab, Balochistan)
        cardinal_half_width := 33.75;  -- 67.5° total width (narrower)
        ordinal_half_width := 16.875;  -- 33.75° total width
        RAISE NOTICE 'Large province detected (area: % km²), using narrow sectors (67.5°)', bbox_area / 1000000;
    ELSE  -- Small provinces
        cardinal_half_width := 45.0;   -- 90° total width (wide beam)
        ordinal_half_width := 22.5;    -- 45° total width
        RAISE NOTICE 'Small province detected (area: % km²), using wide sectors (90°)', bbox_area / 1000000;
    END IF;
    
    -- POLYGON CLIPPING: Intersect grid cell with actual province boundary
    -- This "cookie-cutters" the rectangular grid to the actual shape of the region
    -- Prevents leakage into neighboring provinces (e.g., KPK places in "North Punjab")
    clipped_search_area := ST_Intersection(grid_cell, combined_geom);
    
    -- Validate the clipped area is not empty
    IF clipped_search_area IS NULL OR ST_IsEmpty(clipped_search_area) THEN
        RAISE NOTICE 'Directional grid does not overlap with base region for direction: %', direction;
        RETURN; -- Empty result set
    END IF;
    
    -- CRITICAL CONSTRAINT: Return only places that:
    -- 1. Intersect the CLIPPED search area (grid cell ∩ base polygon)
    -- 2. Are spatially within the base region's polygon
    -- 3. Are not the base region itself
    -- Works at all hierarchy levels: province, district, tehsil
    RETURN QUERY
    SELECT 
        p.id,
        p.name,
        p.hierarchy_level,
        p.parent_id
    FROM places p
    WHERE p.polygon IS NOT NULL
        AND ST_Intersects(p.polygon, clipped_search_area)  -- In the clipped directional area
        AND ST_Within(p.polygon, combined_geom)             -- Within base region boundary
        AND NOT (p.id = ANY(base_place_ids))                -- Exclude base region itself
    ORDER BY p.hierarchy_level DESC;
END;
$$ LANGUAGE plpgsql;