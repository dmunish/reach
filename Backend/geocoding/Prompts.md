# Scrapers

The scrapers will visit the target URLs, and for each

1. Extract all content from page
2. Check if any new entries found
3. If found, extract and process and append to list else exit
4. Continue to next page and repeat
5. If no new entries found, exit loop
6. Upload processed entries to Supabase

# Dashboard

1. Filters - Done
2. Area highlighting color - Fucked forever
3. Alerts for areas
4. Placeholder alerts pop up on click - Done
5. Alert presentation structure
6. Design of alert pins - Done
7. Zooming scale on alert click - Done
8. Alert pin clustering - Fucked
9. Color of space
10. Icons

# Geocoder

This microservice geocodes location references from disaster alert documents, converting place names and directional descriptions into standardized place IDs from Pakistan's administrative boundary hierarchy.

## Core Functionality

The service accepts location strings (e.g., "Islamabad", "Northern Gilgit-Baltistan and KPK") and returns corresponding UUIDs from the `places` table, enabling spatial queries and alert routing based on administrative boundaries.

## PostgreSQL Schema

The existing `places` table contains Pakistan's administrative hierarchy from country (level 0) → province (level 1) → district (level 2) → tehsil (level 3):

```sql
table places (
  id uuid not null default gen_random_uuid (),
  name text not null,
  parent_id uuid null,
  parent_name text null,
  hierarchy_level integer null,
  polygon geometry null,
  constraint places_pkey primary key (id),
  constraint places_parent_id_fkey foreign key (parent_id) references places (id) on delete set null
);
```

## API Endpoint

**`GET /geocode`**

Accepts a list of location references and returns matched place IDs with confidence metadata.
**Request Format:**

```json
{
  "locations": [
    "Islamabad",
    "Northern Gilgit-Baltistan and KPK",
    "Central Sindh"
  ],
  "options": {
    "prefer_lower_admin_levels": true,
    "include_confidence_scores": false
  }
}
```

**Response Format:**

```json
{
  "results": [
    {
      "input": "Islamabad",
      "matched_places": [
        {
          "id": "uuid-here",
          "name": "Islamabad",
          "hierarchy_level": 1,
          "match_method": "exact_name",
          "confidence": 1.0
        }
      ]
    },
    {
      "input": "Northern Gilgit-Baltistan and KPK",
      "matched_places": [
        {
          "id": "uuid-1",
          "name": "Ghizer",
          "hierarchy_level": 2,
          "match_method": "directional_intersection"
        }
        // ... more IDs
      ],
      "regions_processed": ["Gilgit-Baltistan", "KPK"],
      "direction": "Northern"
    }
  ],
  "errors": []
}
```

## Processing Workflow

### Simple Place Name Resolution

1. **Fuzzy Name Matching**: Query the `name` column using fuzzy string matching (Levenshtein distance, trigram similarity) to handle typos and variations

   - Return match if similarity score exceeds threshold (e.g., 0.85)
   - Prefer matches at lower hierarchy levels when multiple candidates exist

2. **Fallback: Point-in-Polygon Resolution**
   - Geocode the place name using LocationIQ API (only get results that are in Pakistan)
   - **Multi-result handling**: If multiple coordinates returned:
     - Calculate centroid of all other locations being geocoded in the same batch
     - Select the result closest to this centroid (spatial context disambiguation)
     - If only one location in batch, use the first result
   - Perform ST_Contains query to find the lowest-level polygon containing the point
   - Return the matched place ID

### Directional Description Processing

For inputs like "Central Sindh and Balochistan" or "North-Western KPK":

1. **Parse Components**
   - Extract directional indicator: {North, South, East, West, Central, North-Eastern, etc.}
   - Extract place names: Split on conjunctions ("and", "or", commas)
   - Example: "Central Sindh and Balochistan" → direction: "Central", places: `["Sindh", "Balochistan"]`
2. **Geocode Base Regions**
   - Resolve each place name to its polygon using the simple name workflow
   - Combine multiple polygons using ST_Union if needed
3. **Apply Directional Grid Filter**
   - Compute bounding box of the combined geometry
   - Overlay a 3×3 grid on the bounding box
   - **Grid cell mapping**:
     - North: top 3 cells
     - South: bottom 3 cells
     - East: right 3 cells
     - West: left 3 cells
     - Central: middle 3 cells (horizontally)
     - North-Western: top-left cell
     - North-Eastern: top-right cell
     - South-Western: bottom-left cell
     - South-Eastern: bottom-right cell
4. **Spatial Intersection**
   - Use ST_Intersects to find all places whose polygons overlap with the selected grid cells
   - Filter to only return lowest appropriate hierarchy level
5. **Hierarchical Aggregation**
   - If all level 3 (tehsil) places within a level 2 (district) are matched, return only the level 2 ID
   - Apply this logic recursively up the hierarchy to minimize redundant IDs
   - Example: If all 5 tehsils of District X are matched, return District X's ID instead

## Error Handling & Edge Cases

- **No match found**: Return error with suggestion for closest match
- **Ambiguous matches**: Return multiple candidates with confidence scores
- **Invalid directional terms**: Reject with specific error message
- **Empty geometries**: Log warning and attempt name-only matching
- **API rate limits**: Implement caching for LocationIQ responses (TTL: 30 days)

## Performance Considerations

- Index `name` column with trigram GIN index for fuzzy matching: `CREATE INDEX idx_places_name_trgm ON places USING gin(name gin_trgm_ops);`
- Spatial index on `polygon`: `CREATE INDEX idx_places_polygon ON places USING GIST(polygon);`
- Cache geocoding API responses to reduce external calls
- Batch process multiple locations in single database query where possible
