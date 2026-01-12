CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fuzzy matching

-- Check existing indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'places';

-- Trigram index for fuzzy name matching
CREATE INDEX IF NOT EXISTS idx_places_name_trgm 
ON places USING gin(name gin_trgm_ops);

-- Spatial index for polygon operations
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
        similarity(p.name, search_name)::REAL as similarity_score
    FROM places p
    WHERE similarity(p.name, search_name) > similarity_threshold
    ORDER BY similarity_score DESC, hierarchy_level DESC
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
BEGIN
    SELECT ST_Union(p.polygon) INTO combined_geom
    FROM places p
    WHERE p.id = ANY(base_place_ids);
    
    IF combined_geom IS NULL THEN
        RETURN;
    END IF;
    
    bbox := ST_Envelope(combined_geom);
    grid_cell := get_directional_grid_cell(bbox, direction);
    
    RETURN QUERY
    SELECT 
        p.id,
        p.name,
        p.hierarchy_level,
        p.parent_id
    FROM places p
    WHERE ST_Intersects(p.polygon, grid_cell)
        AND p.polygon IS NOT NULL
    ORDER BY p.hierarchy_level DESC;
END;
$$ LANGUAGE plpgsql;