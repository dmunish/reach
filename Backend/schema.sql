-- PostgreSQL database dump

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

CREATE SCHEMA public;

COMMENT ON SCHEMA public IS 'standard public schema';

CREATE TYPE public.alert_category AS ENUM (
    'Geo',
    'Met',
    'Safety',
    'Security',
    'Rescue',
    'Fire',
    'Health',
    'Env',
    'Transport',
    'Infra',
    'CBRNE',
    'Other'
);

CREATE TYPE public.alert_severity AS ENUM (
    'Extreme',
    'Severe',
    'Moderate',
    'Minor',
    'Unknown'
);

CREATE TYPE public.alert_urgency AS ENUM (
    'Immediate',
    'Expected',
    'Future',
    'Past',
    'Unknown'
);

CREATE FUNCTION public.execute_readonly_sql(query_text text) RETURNS jsonb
    LANGUAGE plpgsql
    SET search_path TO 'public', 'extensions'
    AS $$
DECLARE
    result JSONB;
    current_role_name TEXT;
BEGIN
    -- Switch to restricted agent role
    current_role_name := current_setting('role');
    EXECUTE 'SET LOCAL ROLE agent';

    -- Limit resource usage
    EXECUTE 'SET LOCAL statement_timeout = ''30s''';
    EXECUTE 'SET LOCAL work_mem = ''512MB''';
    
    -- Enforce read-only transaction
    SET LOCAL TRANSACTION READ ONLY;
    
    -- Validate query (basic sanity checks)
    IF query_text IS NULL OR TRIM(query_text) = '' THEN
        RAISE EXCEPTION 'Query cannot be empty';
    END IF;
    
    -- Block dangerous commands (defense in depth)
    IF query_text ~* '\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|GRANT|REVOKE|TRUNCATE)\b' THEN
        RAISE EXCEPTION 'Only SELECT queries allowed';
    END IF;
    
    -- Execute query as agent (RLS applies)
    BEGIN
        EXECUTE 'SELECT jsonb_agg(row_to_json(t)) FROM (' || query_text || ') t' 
        INTO result;
    EXCEPTION
        WHEN OTHERS THEN
            -- Switch back to original role before re-raising
            EXECUTE 'SET LOCAL ROLE ' || quote_ident(current_role_name);
            RAISE;
    END;
    
    -- Switch back to original role
    EXECUTE 'SET LOCAL ROLE ' || quote_ident(current_role_name);
    
    RETURN COALESCE(result, '[]'::JSONB);
END;
$$;

CREATE FUNCTION public.filter_new_documents(filenames text[]) RETURNS TABLE(filename text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT f.filename
    FROM unnest(filenames) AS f(filename)
    EXCEPT
    SELECT d.filename FROM documents d
    WHERE d.filename = ANY(filenames);
END;
$$;

CREATE FUNCTION public.filter_new_hashes(hashes text[]) RETURNS TABLE(content_hash text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT h.hash
    FROM unnest(hashes) AS h(hash)
    EXCEPT
    SELECT d.content_hash FROM documents d
    WHERE d.content_hash = ANY(hashes);
END;
$$;

CREATE FUNCTION public.find_place_by_point(lon double precision, lat double precision) RETURNS TABLE(id uuid, name text, hierarchy_level integer)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT p.id, p.name, p.hierarchy_level
    FROM places p
    WHERE ST_Contains(p.polygon, ST_SetSRID(ST_MakePoint(lon, lat), 4326))
    ORDER BY hierarchy_level DESC
    LIMIT 1;
END;
$$;

CREATE FUNCTION public.find_places_in_direction(base_place_ids uuid[], direction text) RETURNS TABLE(id uuid, name text, hierarchy_level integer, parent_id uuid)
    LANGUAGE plpgsql
    AS $$
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
$$;

CREATE FUNCTION public.geocode(placenames text[], get_cols text[] DEFAULT ARRAY['id'::text, 'name'::text, 'sep_geo'::text, 'union_geo'::text]) RETURNS TABLE(search_phrase text, matched_id uuid, matched_name text, sep_geo extensions.geometry, union_geo extensions.geometry)
    LANGUAGE plpgsql
    AS $_$
DECLARE
    phrase text;
    clean_phrase text;
    regex_match text[];
    dir_part text;
    base_part text;
    escaped_base text;
    
    -- Parse which columns the user wants to return (using array overlap for case-insensitivity)
    req_id boolean := ARRAY['id', 'ID', 'Id'] && get_cols;
    req_name boolean := ARRAY['name', 'NAME', 'Name'] && get_cols;
    req_sep boolean := ARRAY['sep_geo', 'SEP_GEO', 'sep_Geo'] && get_cols;
    req_union boolean := ARRAY['union_geo', 'UNION_GEO', 'union_Geo'] && get_cols;
BEGIN
    FOREACH phrase IN ARRAY placenames LOOP
        clean_phrase := trim(phrase);
        
        -- 1. Extract Direction and Base Place Name using Regex
        -- Matches 'North', 'Northern', 'North-West', 'North West', etc.
        regex_match := regexp_match(
            clean_phrase, 
            '(?i)^(north\-?east|north\-?west|south\-?east|south\-?west|north|south|east|west|northern|southern|eastern|western|central)\s+(.+)$'
        );
        
        IF regex_match IS NOT NULL THEN
            -- Normalize direction (e.g., 'North-West' -> 'northwest')
            dir_part := lower(replace(regex_match[1], '-', ''));
            base_part := regex_match[2];
        ELSE
            dir_part := NULL;
            base_part := clean_phrase;
        END IF;

        -- Escape special regex characters in the place name to prevent errors during exact-word matching
        escaped_base := regexp_replace(base_part, '([!$()*+.:<=>?[\\\]^{|}-])', '\\\1', 'g');

        -- 2. Process Based on Direction Presence
        IF dir_part IS NOT NULL THEN
            -- ====================================================================
            -- DIRECTIONAL MATCH ("Northern Punjab")
            -- Find the single best parent match, grid its bbox, and intersect descendants
            -- ====================================================================
            RETURN QUERY
            WITH RECURSIVE 
            base_match AS (
                -- Find highest complete match
                SELECT p.id, p.name, p.polygon, ST_SRID(p.polygon) as srid 
                FROM places p
                WHERE p.name ~* ('\b' || escaped_base || '\b')
                ORDER BY similarity(p.name, base_part) DESC, p.hierarchy_level ASC
                LIMIT 1
            ),
            grid_calc AS (
                -- Precompute 3x3 dimensions to avoid repeating ST_ operations
                SELECT 
                    id as base_id, srid,
                    ST_XMin(polygon) as x0, ST_YMin(polygon) as y0,
                    ST_XMax(polygon) as x1, ST_YMax(polygon) as y1,
                    (ST_XMax(polygon) - ST_XMin(polygon)) / 3.0 as dx,
                    (ST_YMax(polygon) - ST_YMin(polygon)) / 3.0 as dy
                FROM base_match
            ),
            grid AS (
                -- Construct the target geometry based on the requested direction
                SELECT base_id,
                    CASE 
                        WHEN dir_part ILIKE '%northeast%' THEN ST_MakeEnvelope(x1-dx, y1-dy, x1, y1, srid)
                        WHEN dir_part ILIKE '%northwest%' THEN ST_MakeEnvelope(x0, y1-dy, x0+dx, y1, srid)
                        WHEN dir_part ILIKE '%southeast%' THEN ST_MakeEnvelope(x1-dx, y0, x1, y0+dy, srid)
                        WHEN dir_part ILIKE '%southwest%' THEN ST_MakeEnvelope(x0, y0, x0+dx, y0+dy, srid)
                        WHEN dir_part ILIKE '%north%'     THEN ST_MakeEnvelope(x0, y1-dy, x1, y1, srid)
                        WHEN dir_part ILIKE '%south%'     THEN ST_MakeEnvelope(x0, y0, x1, y0+dy, srid)
                        WHEN dir_part ILIKE '%east%'      THEN ST_MakeEnvelope(x1-dx, y0, x1, y1, srid)
                        WHEN dir_part ILIKE '%west%'      THEN ST_MakeEnvelope(x0, y0, x0+dx, y1, srid)
                        WHEN dir_part ILIKE '%central%'   THEN ST_MakeEnvelope(x0+dx, y0+dy, x1-dx, y1-dy, srid)
                    END as bbox
                FROM grid_calc
            ),
            hierarchy AS (
                -- Recursively fetch the base place and ALL its children
                SELECT id, name, polygon FROM places WHERE id = (SELECT base_id FROM grid)
                UNION ALL
                SELECT p.id, p.name, p.polygon 
                FROM places p
                INNER JOIN hierarchy h ON p.parent_id = h.id
            ),
            intersected AS (
                -- Intersect all descendants against the targeted grid sector
                SELECT 
                    h.id as m_id, 
                    h.name as m_name, 
                    -- ST_CollectionExtract ensures we only keep Polygons, discarding line/point slivers
                    ST_CollectionExtract(ST_Intersection(h.polygon, g.bbox), 3) as geom
                FROM hierarchy h
                CROSS JOIN grid g
                WHERE ST_Intersects(h.polygon, g.bbox)
            ),
            filtered AS (
                SELECT m_id, m_name, geom
                FROM intersected
                WHERE NOT ST_IsEmpty(geom)
            ),
            unioned AS (
                -- Conditionally compute the union geometry only if needed
                SELECT ST_Union(geom) as u_geom FROM filtered WHERE req_union
            )
            SELECT 
                clean_phrase, 
                CASE WHEN req_id THEN f.m_id ELSE NULL END,
                CASE WHEN req_name THEN f.m_name ELSE NULL END,
                CASE WHEN req_sep THEN f.geom ELSE NULL END,
                CASE WHEN req_union THEN (SELECT u_geom FROM unioned) ELSE NULL END
            FROM filtered f;

        ELSE
            -- ====================================================================
            -- NON-DIRECTIONAL MATCH ("Lahore")
            -- Find all places containing the word, and return them along with their descendants
            -- ====================================================================
            RETURN QUERY
            WITH RECURSIVE 
            matched_bases AS (
                SELECT id, name, polygon 
                FROM places 
                WHERE name ~* ('\b' || escaped_base || '\b')
            ),
            hierarchy AS (
                -- Traverse the hierarchy for all matched roots
                SELECT id, name, polygon FROM matched_bases
                UNION ALL
                SELECT p.id, p.name, p.polygon 
                FROM places p
                INNER JOIN hierarchy h ON p.parent_id = h.id
            ),
            distinct_hier AS (
                -- DISTINCT ON ensures that if a parent and child both match the base word,
                -- we don't output duplicated overlapping geometries.
                SELECT DISTINCT ON (id) id as m_id, name as m_name, polygon as geom
                FROM hierarchy
            ),
            unioned AS (
                SELECT ST_Union(geom) as u_geom FROM distinct_hier WHERE req_union
            )
            SELECT 
                clean_phrase,
                CASE WHEN req_id THEN d.m_id ELSE NULL END,
                CASE WHEN req_name THEN d.m_name ELSE NULL END,
                CASE WHEN req_sep THEN d.geom ELSE NULL END,
                CASE WHEN req_union THEN (SELECT u_geom FROM unioned) ELSE NULL END
            FROM distinct_hier d;
            
        END IF;
    END LOOP;
END;
$_$;

CREATE FUNCTION public.get_alert_geometry(alert_uuid uuid) RETURNS json
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN (
    SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology(unioned_polygon, 0.001), 5)::json
    FROM alert_search_index
    WHERE alert_id = alert_uuid
  );
END;
$$;

CREATE FUNCTION public.get_alerts(status_filter text DEFAULT 'active'::text, search_query text DEFAULT NULL::text, category_filter public.alert_category DEFAULT NULL::public.alert_category, severity_filter public.alert_severity DEFAULT NULL::public.alert_severity, urgency_filter public.alert_urgency DEFAULT NULL::public.alert_urgency, date_start timestamp with time zone DEFAULT NULL::timestamp with time zone, date_end timestamp with time zone DEFAULT NULL::timestamp with time zone, sort_by text DEFAULT 'posted_date'::text, sort_order text DEFAULT 'desc'::text, page_size integer DEFAULT 100, page_offset integer DEFAULT 0, user_lat double precision DEFAULT NULL::double precision, user_lng double precision DEFAULT NULL::double precision, radius_km double precision DEFAULT 30) RETURNS TABLE(id uuid, category public.alert_category, event text, severity public.alert_severity, urgency public.alert_urgency, description text, instruction text, source text, url text, posted_date date, effective_from timestamp with time zone, effective_until timestamp with time zone, affected_places text[], centroid_lat double precision, centroid_lng double precision, bbox_xmin double precision, bbox_ymin double precision, bbox_xmax double precision, bbox_ymax double precision)
    LANGUAGE plpgsql
    AS $_$
DECLARE
    where_parts text[] := ARRAY['1=1'];
    params text[] := ARRAY[]::text[]; 
    p_idx int := 1; 
    search_param_idx int := 0;
    sql_base text;
    sort_col text;
    v_search_place_ids uuid[];
BEGIN
    -- 1. Status Filter logic
    IF status_filter = 'active' THEN
        where_parts := where_parts || format(
            '((effective_from IS NULL OR effective_from <= COALESCE($1[%s]::timestamptz, NOW())) AND (effective_until IS NULL OR effective_until > NOW()))', 
            p_idx
        );
        params := array_append(params, CASE WHEN date_start IS NULL THEN (NOW() + INTERVAL '24 hours')::text ELSE NOW()::text END);
        p_idx := p_idx + 1;
    ELSIF status_filter = 'archived' THEN
        where_parts := where_parts || '(effective_until <= NOW())';
    END IF;

    -- 2. Attribute Filters
    IF category_filter IS NOT NULL THEN
        where_parts := where_parts || format('category = $1[%s]::alert_category', p_idx);
        params := array_append(params, category_filter::text); p_idx := p_idx + 1;
    END IF;
    IF severity_filter IS NOT NULL THEN
        where_parts := where_parts || format('severity = $1[%s]::alert_severity', p_idx);
        params := array_append(params, severity_filter::text); p_idx := p_idx + 1;
    END IF;
    IF urgency_filter IS NOT NULL THEN
        where_parts := where_parts || format('urgency = $1[%s]::alert_urgency', p_idx);
        params := array_append(params, urgency_filter::text); p_idx := p_idx + 1;
    END IF;

    -- 3. Date & Text
    IF date_start IS NOT NULL THEN
        where_parts := where_parts || format('(effective_until >= $1[%s]::timestamptz OR effective_until IS NULL)', p_idx);
        params := array_append(params, date_start::text); p_idx := p_idx + 1;
    END IF;
    IF date_end IS NOT NULL THEN
        where_parts := where_parts || format('(effective_from <= $1[%s]::timestamptz OR effective_from IS NULL)', p_idx);
        params := array_append(params, date_end::text); p_idx := p_idx + 1;
    END IF;

    IF search_query IS NOT NULL THEN
        SELECT ARRAY(
            WITH RECURSIVE ancestry AS (
                SELECT p.id, p.parent_id 
                FROM places p
                WHERE p.name ILIKE '%' || search_query || '%' OR similarity(p.name, search_query) > 0.5
                UNION ALL
                
                SELECT p.id, p.parent_id 
                FROM places p 
                INNER JOIN ancestry a ON p.id = a.parent_id
            )
            SELECT a.id FROM ancestry a)
            INTO v_search_place_ids;

        search_param_idx := p_idx;
        IF array_length(v_search_place_ids, 1) > 0 THEN
            where_parts := where_parts || format('(place_ids && $1[%s]::uuid[] OR search_text ILIKE (''%%'' || $1[%s+1] || ''%%''))', p_idx, p_idx+1);
            params := array_append(params, v_search_place_ids::text);
            params := array_append(params, search_query);
            p_idx := p_idx + 2;
        ELSE
            where_parts := where_parts || format('(search_text ILIKE (''%%'' || $1[%s] || ''%%'') OR $1[%s] <%% search_text)', p_idx, p_idx);
            params := array_append(params, search_query);
            p_idx := p_idx + 1;
        END IF;
    END IF;

    -- 4. Spatial Filter
    IF user_lat IS NOT NULL AND user_lng IS NOT NULL THEN
        where_parts := where_parts || format(
            'ST_DWithin(unioned_polygon::geography, ST_SetSRID(ST_MakePoint($1[%s]::float, $1[%s]::float), 4326)::geography, $1[%s]::float)', 
            p_idx, p_idx+1, p_idx+2
        );
        params := array_append(params, user_lng::text);
        params := array_append(params, user_lat::text);
        params := array_append(params, (radius_km * 1000)::text);
        p_idx := p_idx + 3;
    END IF;

    -- 5. Build Query
    sql_base := 'SELECT 
                    alert_id AS id, 
                    category, 
                    event, 
                    severity, 
                    urgency, 
                    description, 
                    instruction, 
                    source, 
                    url, 
                    posted_date, 
                    effective_from, 
                    effective_until, 
                    affected_places,
                    ST_Y(centroid::geometry) as centroid_lat, 
                    ST_X(centroid::geometry) as centroid_lng, 
                    ST_XMin(bbox) as bbox_xmin, 
                    ST_YMin(bbox) as bbox_ymin, 
                    ST_XMax(bbox) as bbox_xmax, 
                    ST_YMax(bbox) as bbox_ymax
                 FROM alert_search_index 
                 WHERE ' || array_to_string(where_parts, ' AND ');

    -- 6. Sorting
    CASE sort_by
        WHEN 'severity' THEN sort_col := 'severity';
        WHEN 'urgency' THEN sort_col := 'urgency';
        WHEN 'effective_from' THEN sort_col := 'effective_from';
        ELSE sort_col := 'posted_date';
    END CASE;
    
    IF sort_order NOT IN ('asc', 'desc') THEN sort_order := 'desc'; END IF;

    sql_base := sql_base || format(' ORDER BY %I %s', sort_col, sort_order);

    -- 7. Paging
    page_size := LEAST(page_size, 100);
    sql_base := sql_base || format(' LIMIT %s OFFSET %s', page_size, page_offset);

    -- 8. Execution
    RETURN QUERY EXECUTE sql_base USING params;
END;
$_$;

CREATE FUNCTION public.get_place(p_place_name text) RETURNS TABLE(place_id uuid, name text, lat double precision, lng double precision, bbox_xmin double precision, bbox_ymin double precision, bbox_xmax double precision, bbox_ymax double precision)
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY
        SELECT
            p.id, p.name,
            ST_Y(ST_Centroid(p.polygon))::FLOAT,
            ST_X(ST_Centroid(p.polygon))::FLOAT,
            ST_XMin(p.polygon)::FLOAT,
            ST_YMin(p.polygon)::FLOAT,
            ST_XMax(p.polygon)::FLOAT,
            ST_YMax(p.polygon)::FLOAT
        FROM places p
        WHERE p.polygon IS NOT NULL
            AND similarity(p.name, p_place_name) > 0.3
        ORDER BY similarity(p.name, p_place_name) DESC, p.hierarchy_level DESC
        LIMIT 1;
    END;
    $$;

CREATE FUNCTION public.get_places(place_names text[]) RETURNS TABLE(unioned_polygon jsonb, centroid jsonb, bbox jsonb)
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'extensions'
    AS $$
BEGIN
    RETURN QUERY
    WITH matched AS (
        SELECT p.polygon
        FROM public.places p
        WHERE p.polygon IS NOT NULL
          AND EXISTS (
              SELECT 1 
              FROM unnest(place_names) AS pn 
              WHERE p.name ILIKE '%' || pn || '%'
          )
    ),
    aggregated AS (
        SELECT ST_Union(m.polygon::geometry) AS raw_union
        FROM matched m
    )
    SELECT
        ST_AsGeoJSON(ST_Simplify(a.raw_union, 0.001, true), 5)::jsonb,
        ST_AsGeoJSON(ST_Centroid(a.raw_union), 5)::jsonb,
        ST_AsGeoJSON(ST_Envelope(a.raw_union), 5)::jsonb
    FROM aggregated a
    WHERE a.raw_union IS NOT NULL;
END;
$$;

CREATE FUNCTION public.queue_for_processing() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'vault', 'pg_catalog', 'pg_net', 'pgmq'
    AS $$
DECLARE
  v_processor_url text;
  v_key text;
BEGIN
  -- Send message to queue with document ID
  PERFORM pgmq.send(
    'processing_queue',
    jsonb_build_object(
      'document_id', NEW.id,
      'source', NEW.source,
      'posted_date', NEW.posted_date,
      'title', NEW.title,
      'url', NEW.url,
      'filename', NEW.filename,
      'filetype', NEW.filetype,
      'raw_text', NEW.raw_text
    )
  );

  -- Retrieve Vault Secrets safely
  SELECT decrypted_secret INTO v_processor_url 
  FROM vault.decrypted_secrets 
  WHERE name = 'processor_server';

  SELECT decrypted_secret INTO v_key 
  FROM vault.decrypted_secrets 
  WHERE name = 'key';

  -- Ensure secrets exist before sending the request
  IF v_processor_url IS NULL OR v_key IS NULL THEN
    RAISE EXCEPTION 'Processor configuration or API key missing from Vault';
  END IF;

  -- Fire HTTP request
  PERFORM net.http_post(
    url := v_processor_url,
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || v_key,
      'Content-Type', 'application/json'
    ),
    body := jsonb_build_object(
      'limit', 3, 
      'worker_count', 1
    )
  );

  RETURN NEW;
END;
$$;

CREATE FUNCTION public.run_readonly_sql(query text) RETURNS jsonb
    LANGUAGE plpgsql
    SET search_path TO 'public'
    SET statement_timeout TO '8s'
    AS $$
DECLARE
    result jsonb;
    clean_query text;
BEGIN
    -- ── Guard 1: strip leading whitespace/comments and check for SELECT ──────
    clean_query := trim(regexp_replace(query, '^\s*(--[^\n]*\n\s*)*', '', 'g'));
    IF upper(left(clean_query, 6)) <> 'SELECT' THEN
        RAISE EXCEPTION 'Only SELECT statements are permitted.';
    END IF;

    -- ── Guard 2: block disallowed keywords ───────────────────────────────────
    IF clean_query ~* '\m(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|EXECUTE|PERFORM)\M' THEN
        RAISE EXCEPTION 'Statement contains disallowed keywords.';
    END IF;

    -- ── Guard 3: only allow reads from allowed tables ────────────────────────
    -- This runs the query as `agent`, which has no access to other tables.
    -- Any attempt to query unlisted tables will fail with a permissions error.
    SET LOCAL ROLE agent;

    EXECUTE 'SELECT jsonb_agg(row_to_json(t)) FROM (' || clean_query || ') t'
        INTO result;

    RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

CREATE FUNCTION public.search_places_fuzzy(search_name text, similarity_threshold real DEFAULT 0.30) RETURNS TABLE(id uuid, name text, hierarchy_level integer, similarity_score real)
    LANGUAGE plpgsql
    AS $$
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
$$;

CREATE FUNCTION public.update_conversation_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE conversations
    SET updated_at = NOW()
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$;

CREATE FUNCTION public.upload_processed_alert(p_document_id uuid, p_processed_at timestamp with time zone, p_structured_text jsonb, p_alert jsonb, p_alert_areas jsonb[]) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_alert_id UUID;
    v_area     JSONB;
BEGIN
    -- 1. Update document
    UPDATE documents
    SET processed_at    = p_processed_at,
        structured_text = p_structured_text
    WHERE id = p_document_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Document % not found', p_document_id;
    END IF;

    -- 2. Upsert alert
    INSERT INTO alerts (id, document_id, category, event, urgency, severity,
                        description, instruction, effective_from, effective_until)
    VALUES (
        (p_alert->>'id')::UUID, p_document_id, (p_alert->>'category')::alert_category,
        p_alert->>'event', (p_alert->>'urgency')::alert_urgency, (p_alert->>'severity')::alert_severity,
        p_alert->>'description', (p_alert->>'instruction'),
        (p_alert->>'effective_from')::TIMESTAMPTZ, (p_alert->>'effective_until')::TIMESTAMPTZ
    )
    ON CONFLICT (document_id) DO UPDATE SET
        category        = EXCLUDED.category,
        event           = EXCLUDED.event,
        urgency         = EXCLUDED.urgency,
        severity        = EXCLUDED.severity,
        description     = EXCLUDED.description,
        instruction     = EXCLUDED.instruction,
        effective_from  = EXCLUDED.effective_from,
        effective_until = EXCLUDED.effective_until
    RETURNING id INTO v_alert_id;

    -- 3. Replace areas
    DELETE FROM alert_areas WHERE alert_id = v_alert_id;

    IF p_alert_areas IS NOT NULL AND array_length(p_alert_areas, 1) > 0 THEN
        FOREACH v_area IN ARRAY p_alert_areas LOOP
            INSERT INTO alert_areas (alert_id, place_id, specific_effective_from,
                                     specific_effective_until, specific_urgency,
                                     specific_severity, specific_instruction)
            VALUES (
                v_alert_id,
                (v_area->>'place_id')::UUID,
                (v_area->>'specific_effective_from')::TIMESTAMPTZ,
                (v_area->>'specific_effective_until')::TIMESTAMPTZ,
                (v_area->>'specific_urgency')::alert_urgency,
                (v_area->>'specific_severity')::alert_severity,
                v_area->>'specific_instruction'
            );
        END LOOP;
    END IF;

    -- 4. Incrementally maintain search index (replaces REFRESH MATERIALIZED VIEW)
    DELETE FROM alert_search_index WHERE alert_id = v_alert_id;

    INSERT INTO alert_search_index (
        alert_id, centroid, bbox, unioned_polygon, search_text,
        category, severity, urgency, event, description, instruction,
        source, url, posted_date, effective_from, effective_until,
        affected_places, place_ids
    )
    SELECT
        a.id,
        ST_Centroid(g.geom),
        ST_Envelope(g.geom),
        g.geom,
        concat_ws(' ', a.event, a.description, a.instruction,
                  string_agg(p.name, ' ' ORDER BY p.name)),
        a.category, a.severity, a.urgency, a.event, a.description, a.instruction,
        d.source, d.url, d.posted_date, a.effective_from, a.effective_until,
        array_agg(p.name ORDER BY p.name),
        array_agg(p.id)
    FROM alerts a
    JOIN documents d    ON d.id = a.document_id
    JOIN alert_areas aa ON aa.alert_id = a.id
    JOIN places p       ON p.id = aa.place_id
    JOIN LATERAL (
        SELECT ST_Multi(ST_Union(ST_SimplifyPreserveTopology(p2.polygon, 0.001))) AS geom
        FROM alert_areas aa2
        JOIN places p2 ON p2.id = aa2.place_id
        WHERE aa2.alert_id = a.id
    ) g ON true
    WHERE a.id = v_alert_id
    GROUP BY a.id, d.source, d.url, d.posted_date, g.geom;

    RETURN v_alert_id;
END;
$$;

SET default_tablespace = '';

SET default_table_access_method = heap;

CREATE TABLE public.alert_areas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    alert_id uuid NOT NULL,
    place_id uuid,
    specific_effective_from timestamp with time zone,
    specific_effective_until timestamp with time zone,
    specific_urgency public.alert_urgency,
    specific_severity public.alert_severity,
    specific_instruction text
);

CREATE TABLE public.alert_search_index (
    alert_id uuid NOT NULL,
    centroid extensions.geometry,
    bbox extensions.geometry,
    unioned_polygon extensions.geometry,
    search_text text,
    category public.alert_category,
    severity public.alert_severity,
    urgency public.alert_urgency,
    event text,
    description text,
    instruction text,
    source text,
    url text,
    posted_date date,
    effective_from timestamp with time zone,
    effective_until timestamp with time zone,
    affected_places text[],
    place_ids uuid[]
);

CREATE TABLE public.alerts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    category public.alert_category,
    event text,
    urgency public.alert_urgency,
    severity public.alert_severity,
    description text,
    instruction text,
    effective_from timestamp with time zone NOT NULL,
    effective_until timestamp with time zone NOT NULL
);

CREATE TABLE public.conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    title text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE TABLE public.documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source text NOT NULL,
    posted_date date,
    title text,
    url text,
    filename text,
    filetype text,
    processed_at timestamp with time zone,
    structured_text jsonb,
    scraped_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    raw_text text,
    content_hash text NOT NULL
);

COMMENT ON COLUMN public.documents.structured_text IS 'Processed, structured text from LLM';

CREATE TABLE public.echarts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    type character varying(50) NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    data text,
    option text NOT NULL,
    source_url text
);

CREATE TABLE public.messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid NOT NULL,
    type text NOT NULL,
    data jsonb,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT messages_role_check CHECK ((type = ANY (ARRAY['human'::text, 'ai'::text, 'tool'::text, 'system'::text])))
);

CREATE TABLE public.places (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    parent_id uuid,
    parent_name text,
    hierarchy_level integer,
    polygon extensions.geometry(Polygon,4326)
);

CREATE TABLE public.user_settings (
    user_id uuid NOT NULL,
    email_alerts boolean DEFAULT true,
    push_notifications boolean DEFAULT false,
    push_subscription jsonb,
    auto_refresh boolean DEFAULT true,
    show_polygons boolean DEFAULT true,
    map_theme text DEFAULT 'custom'::text,
    min_severity text DEFAULT 'all'::text,
    default_time_range text DEFAULT 'all'::text,
    updated_at timestamp with time zone DEFAULT now()
);

ALTER TABLE ONLY public.alert_areas
    ADD CONSTRAINT alert_areas_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.alert_search_index
    ADD CONSTRAINT alert_search_index_new_pkey PRIMARY KEY (alert_id);

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_document_id_key UNIQUE (document_id);

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_content_hash_key UNIQUE (content_hash);

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_filename_key UNIQUE (filename);

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.echarts
    ADD CONSTRAINT echarts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.places
    ADD CONSTRAINT places_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.user_settings
    ADD CONSTRAINT user_settings_pkey PRIMARY KEY (user_id);

CREATE INDEX alert_areas_alert_id_idx ON public.alert_areas USING btree (alert_id);

CREATE INDEX alert_areas_alert_id_place_id_idx ON public.alert_areas USING btree (alert_id, place_id);

CREATE INDEX alerts_effective_from_idx ON public.alerts USING btree (effective_from);

CREATE INDEX idx_alerts_filters ON public.alerts USING btree (category, severity, urgency, effective_from);

CREATE INDEX idx_asi_bbox ON public.alert_search_index USING gist (bbox);

CREATE INDEX idx_asi_category ON public.alert_search_index USING btree (category);

CREATE INDEX idx_asi_centroid ON public.alert_search_index USING gist (centroid);

CREATE INDEX idx_asi_effective_range ON public.alert_search_index USING btree (effective_from, effective_until);

CREATE INDEX idx_asi_place_ids ON public.alert_search_index USING gin (place_ids);

CREATE INDEX idx_asi_posted_date ON public.alert_search_index USING btree (posted_date);

CREATE INDEX idx_asi_search_text ON public.alert_search_index USING gin (to_tsvector('simple'::regconfig, search_text));

CREATE INDEX idx_asi_severity ON public.alert_search_index USING btree (severity);

CREATE INDEX idx_asi_unioned_polygon ON public.alert_search_index USING gist (unioned_polygon);

CREATE INDEX idx_asi_urgency ON public.alert_search_index USING btree (urgency);

CREATE INDEX idx_echarts ON public.echarts USING btree (lower((type)::text));

CREATE INDEX idx_messages ON public.messages USING btree (conversation_id, created_at);

CREATE INDEX idx_places_hierarchy ON public.places USING btree (hierarchy_level);

CREATE INDEX idx_places_id ON public.places USING btree (id);

CREATE INDEX idx_places_name_gist ON public.places USING gist (name extensions.gist_trgm_ops);

CREATE INDEX idx_places_name_trgm ON public.places USING gin (name extensions.gin_trgm_ops);

CREATE INDEX idx_places_parent_hierarchy ON public.places USING btree (parent_id, hierarchy_level);

CREATE INDEX idx_places_parent_id ON public.places USING btree (parent_id);

CREATE INDEX idx_places_polygon ON public.places USING gist (polygon);

CREATE TRIGGER on_document_insert AFTER INSERT ON public.documents FOR EACH ROW WHEN ((new.processed_at IS NULL)) EXECUTE FUNCTION public.queue_for_processing();

CREATE TRIGGER trigger_update_conversation_time AFTER INSERT OR DELETE OR UPDATE ON public.messages FOR EACH ROW EXECUTE FUNCTION public.update_conversation_timestamp();

ALTER TABLE ONLY public.alert_areas
    ADD CONSTRAINT alert_areas_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.alert_areas
    ADD CONSTRAINT alert_areas_place_id_fkey FOREIGN KEY (place_id) REFERENCES public.places(id);

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.places
    ADD CONSTRAINT places_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.places(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.user_settings
    ADD CONSTRAINT user_settings_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id);

CREATE POLICY "Enable read access for all users" ON public.alert_areas FOR SELECT USING (true);

CREATE POLICY "Enable read access for all users" ON public.alert_search_index FOR SELECT TO authenticated, anon, agent USING (true);

CREATE POLICY "Enable read access for all users" ON public.alerts FOR SELECT USING (true);

CREATE POLICY "Enable read access for all users" ON public.documents FOR SELECT USING (true);

CREATE POLICY "Enable read access for all users" ON public.places FOR SELECT USING (true);

CREATE POLICY "Users can delete their own conversations" ON public.conversations FOR DELETE USING ((auth.uid() = user_id));

CREATE POLICY "Users can insert their own settings" ON public.user_settings FOR INSERT WITH CHECK ((auth.uid() = user_id));

CREATE POLICY "Users can update their own conversations" ON public.conversations FOR UPDATE USING ((auth.uid() = user_id));

CREATE POLICY "Users can update their own settings" ON public.user_settings FOR UPDATE USING ((auth.uid() = user_id));

CREATE POLICY "Users can view messages from their conversations" ON public.messages FOR SELECT USING ((EXISTS ( SELECT 1
   FROM public.conversations
  WHERE ((conversations.id = messages.conversation_id) AND (conversations.user_id = auth.uid())))));

CREATE POLICY "Users can view their own conversations" ON public.conversations FOR SELECT USING ((auth.uid() = user_id));

CREATE POLICY "Users can view their own settings" ON public.user_settings FOR SELECT USING ((auth.uid() = user_id));

ALTER TABLE public.alert_areas ENABLE ROW LEVEL SECURITY;

CREATE POLICY alert_areas_agent_read ON public.alert_areas FOR SELECT TO agent USING (true);

CREATE POLICY alert_areas_public_read ON public.alert_areas FOR SELECT TO authenticated, anon USING (true);

ALTER TABLE public.alert_search_index ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY alerts_agent_read ON public.alerts FOR SELECT TO agent USING (true);

CREATE POLICY alerts_public_read ON public.alerts FOR SELECT TO authenticated, anon USING (true);

ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.echarts ENABLE ROW LEVEL SECURITY;

CREATE POLICY echarts_select ON public.echarts FOR SELECT TO postgres, authenticated, agent USING (true);

ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.places ENABLE ROW LEVEL SECURITY;

CREATE POLICY places_agent_read ON public.places FOR SELECT TO agent USING (true);

CREATE POLICY places_public_read ON public.places FOR SELECT TO authenticated, anon USING (true);

ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;

-- PostgreSQL database dump complete

