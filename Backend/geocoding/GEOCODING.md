# Geocoding Microservice Documentation

## Overview

The Geocoding Microservice converts location references from disaster alert documents into standardized place IDs from Pakistan's administrative boundary hierarchy. It supports:

-   **Simple name matching**: Direct fuzzy matching against place names
-   **Directional processing**: Geographic descriptions like "Northern Punjab" or "Central Sindh"
-   **Hierarchical aggregation**: Smart consolidation to avoid redundant parent/child places
-   **Batch processing**: Multiple locations in a single request

---

## Directory Structure

```
geocoding/
├── GEOCODING.md                  # This file
├── start.sh                      # Quick setup and validation script
├── config.py                     # Environment configuration
├── __init__.py                   # Package exports (modularization)
├── models.py                     # Pydantic models for requests/responses
├── dependencies.py               # Dependency injection container
├── db_queries.sql               # PostgreSQL functions and indexes
│
├── api/
│   ├── __init__.py              # API module exports
│   └── routes.py                # FastAPI endpoint definitions
│
├── repositories/
│   ├── __init__.py              # Repository module exports
│   └── places_repository.py     # Database access layer
│
├── services/
│   ├── __init__.py              # Services module exports
│   ├── geocoding_service.py     # Main orchestration service
│   ├── name_matcher.py          # Fuzzy name matching logic
│   ├── directional_parser.py    # Directional phrase parser
│   └── external_geocoder.py     # LocationIQ API integration
│
└── tests/
    ├── __init__.py              # Tests module
    ├── test_api.py              # Integration tests with colored output
    ├── test_setup.py            # Setup validation (4 phases)
    └── test_curl_commands.sh    # Automated curl test script

Backend/
└── geocoder.py                   # FastAPI application entry point
```

### Modularization

The geocoding package is fully modularized with `__init__.py` files, enabling clean imports:

```python
# From Backend directory
from geocoding import GeocodingService, get_geocoding_service
from geocoding.services import DirectionalParser
from geocoding.repositories import PlacesRepository

# Simple batch interface
service = get_geocoding_service()
place_names = ["Islamabad", "Lahore", "Karachi"]
place_ids = await service.geocode_batch_simple(place_names)
# Returns: ["uuid-1", "uuid-2", "uuid-3"]
```

---

## Quick Start

### Using start.sh

The `start.sh` script automates the entire setup process:

```bash
cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding
chmod +x start.sh
./start.sh
```

**What start.sh does:**

1. ✅ **Checks Python installation** - Ensures Python 3 is available
2. ✅ **Creates virtual environment** - Sets up `Backend/venv` if not exists
3. ✅ **Installs dependencies** - Installs all packages from `requirements.txt`
4. ✅ **Validates .env file** - Ensures required environment variables are set
5. ✅ **Runs validation tests** - Executes all 4 phases of setup tests:
    - **Phase 1**: Configuration & connectivity (Supabase connection)
    - **Phase 2**: Database layer (SQL functions, PostGIS, pg_trgm)
    - **Phase 3**: Service layer (parsers, matchers, geocoder)
    - **Phase 4**: End-to-end integration test

**After successful setup:**

```bash
# Start the service (from Backend directory)
cd /home/ahmad_shahmeer/reach-geocoding/Backend
python -m geocoder

# Alternative: use uvicorn directly
uvicorn geocoder:app --reload --host 0.0.0.0 --port 8000

# Service will be available at:
# - http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

**Note:** The geocoding module is now fully modularized with `__init__.py` files in all subdirectories (api, services, repositories, tests), allowing clean imports from the Backend directory level.

**If setup fails:**

-   Check error messages - they indicate which phase failed
-   Common issues:
    -   Missing SQL functions in Supabase (run `db_queries.sql`)
    -   Missing PostgreSQL extensions (`pg_trgm`, `postgis`)
    -   Incorrect `.env` credentials

---

## Testing

### 1. Python Integration Tests (test_api.py)

Runs comprehensive tests with **colored terminal output** (no file output):

```bash
cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding
python tests/test_api.py
```

**Test Coverage:**

-   Health check endpoint
-   Simple place name (Islamabad)
-   Directional description (Central Sindh)
-   Batch geocoding (6 locations)
-   GET endpoint (single location)
-   Suggestions endpoint (typo handling)

**Features:**

-   ✅ Color-coded output (green=success, red=error, yellow=warning)
-   ✅ Pretty-printed JSON responses
-   ✅ Status indicators and summaries
-   ✅ Connection error handling
-   ✅ All output to terminal only

---

### 2. Automated Curl Tests (test_curl_commands.sh)

Bash script that runs 15 different test scenarios:

```bash
cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding/tests
chmod +x test_curl_commands.sh
./test_curl_commands.sh
```

**What it tests:**

-   Simple place names (Islamabad, Lahore)
-   Fuzzy matching (typos)
-   8 directional queries (all compass directions)
-   Province and district levels
-   Batch processing
-   Hierarchical aggregation
-   GET/Suggestions endpoints
-   Health check

---

### 3. Manual Curl Commands

Copy-paste these commands to test specific scenarios:

#### Simple Place Name - Islamabad

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Islamabad"]}' | jq
```

#### Simple Place - Lahore

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Lahore"]}' | jq
```

#### Fuzzy Match - Typo "Lahor"

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Lahor"]}' | jq
```

#### Directional - Northern Gilgit Baltistan

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Northern Gilgit Baltistan"]}' | jq
```

**Expected Output:**

-   ✅ Level 2 districts only (Gilgit, Hunza, Nagar, Ghizer, etc.)
-   ❌ NO level 1 provinces (Gilgit Baltistan, KPK)
-   ❌ NO level 0 (Pakistan)
-   Hierarchical aggregation removes redundant parents

#### Directional - Central Sindh

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Central Sindh"]}' | jq
```

#### Directional - Eastern Punjab

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Eastern Punjab"]}' | jq
```

#### Directional - Western Balochistan

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Western Balochistan"]}' | jq
```

#### Directional - South-Western KPK

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["South-Western Khyber Pakhtunkhwa"]}' | jq
```

#### Directional - North-Eastern KPK

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["North-Eastern Khyber Pakhtunkhwa"]}' | jq
```

#### Directional - Southern Sindh

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Southern Sindh"]}' | jq
```

#### Province-level - Sindh

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Sindh"]}' | jq
```

#### District-level - Swat

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Swat"]}' | jq
```

#### Batch - Multiple Locations

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Islamabad",
      "Karachi",
      "Northern Punjab",
      "Central Sindh",
      "Western Balochistan"
    ]
  }' | jq
```

#### Multiple Directional Queries

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Southern Sindh",
      "Northern Gilgit Baltistan",
      "Western Balochistan",
      "Eastern Punjab"
    ]
  }' | jq
```

#### Test Hierarchical Aggregation

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Central Punjab"]}' | jq
```

#### GET Endpoint - Single Location

```bash
curl -X GET http://localhost:8000/api/v1/geocode/Lahore | jq
```

#### Suggestions - Typo "Islmabad"

```bash
curl -X GET "http://localhost:8000/api/v1/suggest/Islmabad?limit=5" | jq
```

#### Health Check

```bash
curl -X GET http://localhost:8000/api/v1/health | jq
```

---

## Key Features Explained

### 1. No Conjunction Splitting

**Design Decision:**

-   Input: `"Northern Sindh"` → Processes as **single region**
-   ❌ NO support for: `"Northern Sindh and Balochistan"`
-   ✅ Instead send: `["Northern Sindh", "Northern Balochistan"]`

**Why?**

-   Clearer semantics: each location string = one region
-   Simpler logic: no ambiguity in parsing
-   Better control: client decides how to group queries

---

### 2. Hierarchical Aggregation

**Logic:**

1. **Remove children** when ALL children of a parent are matched → keep only parent
2. **Remove parents** when ANY children are present → keep only the more specific children

**Examples:**

**Case 1: All children matched**

```
Input: "Northern Gilgit Baltistan"
Raw Results: 13 tehsils (level 3) + 7 districts (level 2) + 2 provinces + Pakistan
After Aggregation:
  - If all 5 tehsils of "Hunza" district matched → Remove tehsils, keep "Hunza" district
  - If all 7 districts of "GB" province matched → Remove districts, keep "GB" province
  - Parents (GB, KPK, Pakistan) removed because children exist
```

**Case 2: Partial children matched**

```
Input: "Central Sindh"
Raw Results: 8 districts (level 2) + Sindh province (level 1) + Pakistan (level 0)
After Aggregation:
  - Keep 8 districts (specific)
  - Remove Sindh province (parent with children)
  - Remove Pakistan (parent with children)
```

**Benefits:**

-   ✅ Avoids redundancy (don't show both "Karachi" and "Sindh")
-   ✅ Most specific results (prefer districts over provinces)
-   ✅ Compact output (fewer UUIDs to process)

---

### 3. Directional Processing

**Grid System:**

-   Divides region into 3×3 grid
-   Selects cells based on direction:
    -   **North**: top 3 cells
    -   **South**: bottom 3 cells
    -   **East**: right 3 cells
    -   **West**: left 3 cells
    -   **Central**: middle 3 cells (horizontal)
    -   **North-Eastern**: top-right cell
    -   **North-Western**: top-left cell
    -   **South-Eastern**: bottom-right cell
    -   **South-Western**: bottom-left cell

**Process:**

1. Parse direction from input ("Northern")
2. Match base region ("Gilgit Baltistan")
3. Get region's bounding box
4. Apply 3×3 grid
5. Select relevant cells
6. Find all places intersecting those cells
7. Apply hierarchical aggregation

---

## Database Requirements

### Extensions

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_places_name_trgm
  ON places USING gin(name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_places_polygon
  ON places USING gist(polygon);

CREATE INDEX IF NOT EXISTS idx_places_hierarchy
  ON places(hierarchy_level);
```

### Functions

Run all SQL from `db_queries.sql` in Supabase SQL Editor:

-   `search_places_fuzzy()` - Fuzzy name matching
-   `find_place_by_point()` - Point-in-polygon lookup
-   `find_places_in_direction()` - Directional grid search
-   `get_directional_grid_cell()` - Grid cell calculator

---

## API Endpoints

### POST /api/v1/geocode

Geocode one or more location strings.

**Request:**

```json
{
    "locations": ["Islamabad", "Northern Punjab"],
    "options": {
        "prefer_lower_admin_levels": true,
        "include_confidence_scores": false
    }
}
```

**Response:**

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
            ],
            "error": null
        }
    ],
    "errors": []
}
```

### GET /api/v1/geocode/{location}

Geocode a single location (URL path).

### GET /api/v1/suggest/{query}

Get suggestions for typos/misspellings.

### GET /api/v1/health

Service health check.

---

## Troubleshooting

### Service won't start

```bash
# Check if port 8000 is already in use
lsof -i :8000

# Check logs for errors
cd /home/ahmad_shahmeer/reach-geocoding/Backend
python -m geocoder
```

### Tests fail with "Connection refused"

-   Make sure service is running: `python -m geocoder` (from Backend directory)
-   Check correct port: `http://localhost:8000`

### "Function not found" errors

-   Run `db_queries.sql` in Supabase SQL Editor
-   Ensure all functions are created

### No results returned

-   Check places table has data
-   Verify polygons are valid (PostGIS)
-   Check fuzzy match threshold (default 0.85)

---

## Performance

**Query Times:**

-   Simple name match: ~50ms
-   Directional query: ~200-500ms
-   Batch (5 locations): ~500-800ms

**Optimizations:**

-   GIN/GIST indexes on database
-   LRU caching on parser (256 entries)
-   Connection pooling for external API
-   Async/await for non-blocking I/O

---

## Development

### Adding a new endpoint

1. Add route in `api/routes.py`
2. Add business logic in `services/geocoding_service.py`
3. Add repository method if needed in `repositories/places_repository.py`
4. Update models in `models.py` if new request/response types needed

### Running individual test phases

```bash
cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding
python tests/test_setup.py --phase 1  # Configuration
python tests/test_setup.py --phase 2  # Database
python tests/test_setup.py --phase 3  # Services
python tests/test_setup.py --phase 4  # Integration
```

---

## Credits

Built with:

-   **FastAPI** - Web framework
-   **Supabase** - PostgreSQL database
-   **PostGIS** - Spatial operations
-   **pg_trgm** - Fuzzy string matching
-   **LocationIQ** - External geocoding fallback
-   **Pydantic** - Data validation
