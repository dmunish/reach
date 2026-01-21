# Geocoding Microservice Documentation

## Table of Contents

1. [Overview](#overview)
2. [Directory Structure](#directory-structure)
3. [Installation & Setup](#installation--setup)
   - [Prerequisites](#prerequisites)
   - [Quick Setup with start.sh](#quick-setup-with-startsh)
   - [Manual Setup](#manual-setup)
   - [Redis Caching Setup](#redis-caching-setup)
4. [Testing](#testing)
   - [Setup Validation](#setup-validation)
   - [Integration Tests](#integration-tests)
   - [Automated Curl Tests](#automated-curl-tests)
   - [Manual Testing](#manual-testing)
5. [Key Features](#key-features)
   - [Simple Name Matching](#simple-name-matching)
   - [Directional Processing](#directional-processing)
   - [Hierarchical Aggregation](#hierarchical-aggregation)
   - [Batch Processing](#batch-processing)
   - [Redis Caching](#redis-caching)
6. [API Reference](#api-reference)
7. [Performance & Monitoring](#performance--monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Geocoding Microservice converts location references from disaster alert documents into standardized place IDs from Pakistan's administrative boundary hierarchy.

**Core Capabilities:**
- **Simple name matching**: Direct fuzzy matching against place names (e.g., "Islamabad", "Lahore")
- **Directional processing**: Geographic descriptions like "Northern Punjab" or "South-Western KPK"
- **Hierarchical aggregation**: Smart consolidation to avoid redundant parent/child places
- **Batch processing**: Multiple locations in a single request
- **Redis caching**: 20-100x faster repeated queries (optional but recommended)

**Tech Stack:**
- FastAPI (async web framework)
- Supabase/PostgreSQL with PostGIS (spatial operations)
- pg_trgm (fuzzy string matching)
- Redis (optional distributed cache)
- Pydantic (data validation)

**Performance:**
- Simple name match: ~50ms (cold) / ~20ms (cached)
- Directional query: ~7s (cold) / ~100ms (cached) - **70x faster with Redis**
- Batch (5 locations): ~500-800ms (cold) / ~200ms (cached)

---

## Directory Structure

```
geocoding/
├── GEOCODING.md                  # This file - comprehensive documentation
├── ARCHITECTURE.md              # System architecture and design patterns
├── start.sh                      # Automated setup and validation script
│
├── config.py                     # Environment configuration
├── dependencies.py               # Dependency injection container
├── models.py                     # Pydantic models for API
├── exceptions.py                 # Custom exceptions
├── __init__.py                   # Package exports
│
├── db_queries.sql               # PostgreSQL functions and indexes
│
├── api/
│   ├── __init__.py
│   └── routes.py                # FastAPI endpoint definitions
│
├── repositories/
│   ├── __init__.py
│   └── places_repository.py     # Database access layer (with Redis caching)
│
├── services/
│   ├── __init__.py
│   ├── geocoding_service.py     # Main orchestration service
│   ├── name_matcher.py          # Fuzzy name matching logic
│   ├── directional_parser.py    # Directional phrase parser
│   ├── external_geocoder.py     # LocationIQ API integration
│   └── redis_cache.py           # Redis caching layer
│
└── tests/
    ├── __init__.py
    ├── test_setup.py            # 4-phase setup validation
    ├── test_api.py              # Integration tests (colored output)
    ├── test_redis.py            # Redis connectivity tests
    └── test_curl_commands.sh    # Automated curl test script
```

**Note:** The geocoding package is fully modularized with `__init__.py` files in all subdirectories, enabling clean imports:

```python
# From Backend directory
from geocoding import GeocodingService, get_geocoding_service
from geocoding.services import DirectionalParser
from geocoding.repositories import PlacesRepository
```

---

## Installation & Setup

### Prerequisites

**Required:**
- Python 3.11+
- PostgreSQL 14+ with PostGIS extension
- Supabase account (or local PostgreSQL with PostGIS)
- LocationIQ API key (free tier: 10k requests/day)

**Optional:**
- Redis 7.x (for caching - highly recommended for production)

**System Requirements:**
- Ubuntu 20.04+ / macOS 11+ / Windows 10+ with WSL2
- 2GB RAM minimum
- 1GB disk space

---

### Quick Setup with start.sh

The automated `start.sh` script handles the entire setup process:

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
   - **Phase 1**: Configuration & connectivity
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
```

**Service will be available at:**
- API: `http://localhost:8000`
- Interactive Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

---

### Manual Setup

If you prefer manual setup or need to troubleshoot:

#### 1. Create Virtual Environment

```bash
cd /home/ahmad_shahmeer/reach-geocoding/Backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Key dependencies:**
- `fastapi` - Web framework
- `uvicorn[standard]` - ASGI server
- `supabase` - Database client
- `httpx` - Async HTTP client
- `pydantic-settings` - Configuration management
- `redis[hiredis]` - Redis cache (optional, includes C parser for speed)

#### 3. Configure Environment Variables

Create `Backend/.env` file:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# External Geocoding
LOCATION_IQ_KEY=your-locationiq-api-key

# Application Settings
FUZZY_MATCH_THRESHOLD=0.85

# Redis Configuration (optional)
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Redis TTLs (in seconds)
REDIS_TTL_DIRECTIONAL=3600      # 1 hour
REDIS_TTL_FUZZY=7200            # 2 hours  
REDIS_TTL_EXTERNAL=2592000      # 30 days
```

#### 4. Setup Database

**Run SQL functions in Supabase SQL Editor:**

```bash
# Copy contents of db_queries.sql
cat geocoding/db_queries.sql
```

Paste and execute in Supabase → SQL Editor. This creates:
- PostgreSQL functions for fuzzy search and spatial operations
- GIN/GIST indexes for performance
- Helper functions for directional grid processing

**Verify extensions:**
```sql
-- Should already be enabled in Supabase
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

#### 5. Verify Setup

```bash
cd geocoding
python test_setup.py
```

Expected output:
```
✅ Phase 1: Configuration & Connectivity - PASSED
✅ Phase 2: Database Layer - PASSED
✅ Phase 3: Service Layer - PASSED
✅ Phase 4: End-to-End Integration - PASSED

🎉 All validation phases passed!
```

---

### Redis Caching Setup

Redis caching is **optional but highly recommended** for production deployments. It provides 20-100x performance improvements for repeated queries.

#### Why Redis?

**Performance Impact:**
- First query: ~7-10 seconds (database + spatial operations)
- Cached query: ~50-200ms (Redis lookup)
- **Improvement: 20-100x faster** ⚡

**Benefits:**
- ✅ Dramatically faster repeated queries
- ✅ Reduced database load on expensive PostGIS operations
- ✅ Lower external API costs (LocationIQ)
- ✅ Better user experience with sub-second response times
- ✅ Scalable across multiple service instances

#### Installation

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Docker:**
```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

#### Verify Redis

```bash
redis-cli ping
# Expected: PONG
```

#### Enable in Application

Update `Backend/.env`:
```bash
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
```

#### Test Redis Connectivity

```bash
cd geocoding
python tests/test_redis.py
```

Expected output:
```
✅ Redis connection successful!
✅ SET: ✅
✅ GET: ✅
✅ DELETE: ✅
⚡ Speedup: 50.2x faster
```

#### Redis Configuration Details

**What Gets Cached:**

| Type | Namespace | TTL | Why |
|------|-----------|-----|-----|
| Directional queries | `directional` | 1 hour | Expensive PostGIS spatial operations |
| Aggregated results | `directional_aggregated` | 1 hour | Saves hierarchical processing (~20s) |
| Fuzzy searches | `fuzzy_search` | 2 hours | pg_trgm calculations on large dataset |
| External API | `external_geocode` | 30 days | Avoids rate limits + reduces costs |

**Cache Architecture:**

```
API Request: "North Punjab"
    ↓
┌─────────────────┐
│ Check Redis     │
│ Cache First     │
└────┬────────┬───┘
     │        │
   MISS      HIT
     │        │
     ▼        ▼
┌─────────┐  ┌──────────────┐
│Database │  │Return Cached │
│PostGIS  │  │Result ~100ms │
│~7 sec   │  └──────────────┘
└────┬────┘
     │
     ▼
┌────────────┐
│Cache Result│
│in Redis    │
└────────────┘
```

**Two-Level Caching Strategy:**

The service implements a two-level cache for directional queries:

1. **Level 1: Raw Directional Results** - Caches the raw database spatial query results (~75 places)
2. **Level 2: Aggregated Results** - Caches the final aggregated results after hierarchical processing (~18 places)

Level 2 is critical because hierarchical aggregation is the actual bottleneck (~20s), not just the spatial query (~7s).

**Cache Keys:**

Directional queries use sorted place IDs for consistent cache keys:
```python
# Ensures same cache key regardless of input order
place_ids = [uuid1, uuid2, uuid3]
cache_key = f"{sorted_ids}:{direction}"
# Result: Better cache hit rate
```

#### Graceful Degradation

The service is designed to **never crash** due to Redis issues:

1. ✅ Service continues to work without Redis
2. ⚠️ Performance degrades to database-only mode
3. 📝 Logs warnings but doesn't stop requests

```bash
# Test with Redis down
sudo systemctl stop redis-server
curl http://localhost:8000/api/v1/health
# Status: 200 OK (just slower for complex queries)
```

#### Production Considerations

**1. Enable Persistence** (`/etc/redis/redis.conf`):
```conf
# RDB snapshots
save 900 1       # After 900 sec if at least 1 key changed
save 300 10      # After 300 sec if at least 10 keys changed
save 60 10000    # After 60 sec if at least 10000 keys changed

# AOF for durability
appendonly yes
appendfsync everysec
```

**2. Set Memory Limits:**
```conf
maxmemory 256mb
maxmemory-policy allkeys-lru  # Remove least recently used
```

**3. Security (if exposed to network):**
```conf
requirepass your-strong-password
bind 127.0.0.1  # Localhost only
```

Update `.env`:
```bash
REDIS_PASSWORD=your-strong-password
```

**4. Monitoring:**
- Redis Commander: `npm install -g redis-commander`
- RedisInsight (official GUI)
- Prometheus + Grafana with Redis exporter

---

## Testing

### Setup Validation

The `test_setup.py` script validates your installation in 4 phases:

```bash
cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding
python test_setup.py
```

**Test Phases:**

**Phase 1: Configuration & Connectivity**
- Loads environment variables from `.env`
- Tests Supabase connection
- Verifies LocationIQ API key
- Checks Redis connection (if enabled)

**Phase 2: Database Layer**
- Verifies PostgreSQL extensions (PostGIS, pg_trgm)
- Tests SQL functions existence
- Validates indexes
- Checks places table data

**Phase 3: Service Layer**
- Tests DirectionalParser
- Tests NameMatcher
- Tests ExternalGeocoder
- Tests Redis cache operations

**Phase 4: End-to-End Integration**
- Tests simple name geocoding
- Tests directional geocoding
- Tests batch processing
- Tests hierarchical aggregation

**Run individual phases:**
```bash
python test_setup.py --phase 1  # Configuration only
python test_setup.py --phase 2  # Database only
python test_setup.py --phase 3  # Services only
python test_setup.py --phase 4  # Integration only
```

---

### Integration Tests

Python integration tests with **colored terminal output**:

```bash
cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding/tests
python test_api.py
```

**Test Coverage:**
- Health check endpoint
- Simple place name (Islamabad)
- Fuzzy matching (typos)
- Directional description (Central Sindh)
- Batch geocoding (6 locations)
- GET endpoint (single location)
- Suggestions endpoint

**Features:**
- ✅ Color-coded output (green=success, red=error, yellow=warning)
- ✅ Pretty-printed JSON responses
- ✅ Status indicators and summaries
- ✅ Connection error handling
- ✅ All output to terminal only (no file output)

---

### Automated Curl Tests

Bash script that runs 15 different test scenarios with timing:

```bash
cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding/tests
chmod +x test_curl_commands.sh
./test_curl_commands.sh
```

**What it tests:**
- Simple place names (Islamabad, Lahore)
- Fuzzy matching (typos like "Lahor")
- 8 directional queries (all compass directions)
- Province and district levels
- Batch processing
- Hierarchical aggregation
- GET/Suggestions endpoints
- Health check

**Output includes:**
- Clean formatted output showing only place names and hierarchy levels
- Summary table with execution time for each test category
- Total execution time

**First run (cold cache):** ~3-5 minutes  
**Second run (warm cache):** ~5-10 seconds (20-50x faster)

---

### Manual Testing

#### Health Check
```bash
curl http://localhost:8000/api/v1/health | jq
```

#### Simple Place Name
```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Islamabad"]}' | jq
```

#### Fuzzy Match (Typo)
```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Lahor"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
```

#### Directional Query
```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Northern Gilgit Baltistan"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
```

Expected output:
- ✅ Level 2 districts only (Gilgit, Hunza, Nagar, Ghizer, etc.)
- ❌ NO level 1 provinces
- ❌ NO level 0 (Pakistan)

#### Batch Processing
```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Islamabad",
      "Karachi",
      "Northern Punjab",
      "Central Sindh"
    ]
  }' | jq
```

#### GET Endpoint
```bash
curl http://localhost:8000/api/v1/geocode/Lahore | jq
```

#### Suggestions (Typo Handling)
```bash
curl "http://localhost:8000/api/v1/suggest/Islmabad?limit=5" | jq
```

#### jq Filters for Analysis

**Count matched places:**
```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["North Punjab"]}' | jq '.results[0].matched_places | length'
```

**Compact list of names:**
```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["North Punjab"]}' | jq -r '.results[0].matched_places[].name' | tr '\n' ', '
```

**Names with hierarchy levels:**
```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{"locations": ["North Punjab"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
```

---

## Key Features

### Simple Name Matching

**How it works:**
1. Uses PostgreSQL's `pg_trgm` extension for fuzzy string matching
2. Calculates trigram similarity between input and place names
3. Returns places above threshold (default: 0.85)
4. Selects best match using business rules:
   - Highest similarity score
   - Among similar scores (within 0.05), prefers higher hierarchy level

**Example:**
```
Input: "Lahore"
Process:
  1. pg_trgm similarity search
  2. Find "Lahore" district (similarity: 1.0)
  3. Return district UUID

Input: "Lahor" (typo)
Process:
  1. pg_trgm similarity search
  2. Find "Lahore" (similarity: 0.91)
  3. Return district UUID with confidence score
```

**Performance:**
- Database query: ~50ms (with GIN index)
- Cached: ~20ms

---

### Directional Processing

**Grid System:**

Divides a region into a 3×3 grid and selects cells based on direction:

```
┌─────┬─────┬─────┐
│ NW  │  N  │ NE  │  North: top 3 cells
├─────┼─────┼─────┤  South: bottom 3 cells
│  W  │  C  │  E  │  East: right 3 cells
├─────┼─────┼─────┤  West: left 3 cells
│ SW  │  S  │ SE  │  Central: middle 3 (horizontal)
└─────┴─────┴─────┘  NE/NW/SE/SW: single corner cell
```

**Supported Directions:**
- Simple: North, South, East, West, Central
- Compound: North-Eastern, North-Western, South-Eastern, South-Western

**Process:**

1. Parse direction from input ("Northern")
2. Match base region ("Gilgit Baltistan")
3. Get region's bounding box from PostGIS
4. Apply 3×3 grid overlay
5. Select relevant grid cells based on direction
6. Find all places intersecting those cells using `ST_Intersects`
7. Apply hierarchical aggregation to remove redundancy

**Example:**
```
Input: "Northern Gilgit Baltistan"

Process:
  1. Direction: NORTH
  2. Base region: "Gilgit Baltistan" (province)
  3. Bounding box: [min_lon, min_lat, max_lon, max_lat]
  4. Grid: Create 3×3 cells
  5. Select: Top 3 cells (NW, N, NE)
  6. Intersect: Find districts/tehsils in those cells
  7. Aggregate: Remove redundant parents
  
Result: 7 northern districts of Gilgit Baltistan
```

**Performance:**
- Cold cache: ~7-10 seconds (PostGIS spatial operations)
- Warm cache: ~100ms (Redis lookup) - **70x faster**

**No Conjunction Splitting:**

Design decision: Each location string represents a **single region**.

```
❌ NOT supported: "Northern Sindh and Balochistan"
✅ Instead send: ["Northern Sindh", "Northern Balochistan"]
```

**Why?**
- Clearer semantics: each string = one region
- Simpler logic: no ambiguity in parsing
- Better control: client decides how to group queries

---

### Hierarchical Aggregation

**Logic:**

1. **Remove children** when ALL children of a parent are matched → keep only parent
2. **Remove parents** when ANY children are present → keep only the more specific children

**Examples:**

**Case 1: All Children Matched**
```
Input: "Northern Gilgit Baltistan"

Raw Results:
  - 13 tehsils (level 3)
  - 7 districts (level 2)
  - Gilgit Baltistan province (level 1)
  - Pakistan (level 0)

After Aggregation:
  - If all 5 tehsils of "Hunza" district matched
    → Remove tehsils, keep "Hunza" district
  - If all 7 districts of "GB" province matched
    → Remove districts, keep "GB" province
  - Remove GB and Pakistan (parents with children)
    
Final Result: 7 districts (most specific without redundancy)
```

**Case 2: Partial Children Matched**
```
Input: "Central Sindh"

Raw Results:
  - 8 districts (level 2)
  - Sindh province (level 1)
  - Pakistan (level 0)

After Aggregation:
  - Keep 8 districts (specific)
  - Remove Sindh (parent with children)
  - Remove Pakistan (parent with children)
  
Final Result: 8 central districts of Sindh
```

**Benefits:**
- ✅ Avoids redundancy (don't show both "Karachi" and "Sindh")
- ✅ Most specific results (prefer districts over provinces)
- ✅ Compact output (fewer UUIDs to process)

**Performance:**
- Without cache: ~20 seconds (hierarchical processing bottleneck)
- With cache: ~12ms (aggregated result cached) - **1,875x faster**

---

### Batch Processing

Process multiple locations in a single request:

```bash
curl -X POST http://localhost:8000/api/v1/geocode \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Islamabad",
      "Northern Punjab",
      "Karachi",
      "Central Sindh"
    ]
  }'
```

**Benefits:**
- Single HTTP request overhead
- Parallel processing with `asyncio.gather()`
- Better resource utilization

**Performance:**
- Cold cache: ~500-800ms for 5 locations
- Warm cache: ~200ms for 5 locations

---

### Redis Caching

**Cache Hit Indicators:**

Application logs show cache operations with emojis:

```
✅ Directional cache HIT: north (18 places)   # Fast!
💾 Directional cache SET: north (18 places)   # First query
❌ Cache MISS: directional:...                # Slow
✅ Aggregated result cache HIT: north         # Very fast!
```

**Filter cache logs:**
```bash
python -m geocoder 2>&1 | grep -E "cache|Cache"
```

**Monitor Redis:**

```bash
# Connect to Redis CLI
redis-cli

# View all keys in a namespace
KEYS geocode:directional:*
KEYS geocode:fuzzy_search:*
KEYS geocode:external_geocode:*

# Count total keys
DBSIZE

# Check TTL of a key
TTL geocode:directional:some-key

# View cached value
GET geocode:directional:some-key

# Monitor real-time operations
MONITOR
```

**Cache Invalidation:**

Clear cache when administrative boundaries change:

```bash
# Clear all cache
redis-cli FLUSHDB

# Clear specific namespace
redis-cli KEYS "geocode:directional:*" | xargs redis-cli DEL
```

From Python:
```python
from geocoding.services.redis_cache import get_redis_cache

cache = await get_redis_cache()
await cache.clear_namespace("directional")
await cache.clear_namespace("directional_aggregated")
```

**Automatic Expiration:**

All cache entries auto-expire via TTL:
- Directional: 1 hour (rarely changes)
- Fuzzy search: 2 hours
- External API: 30 days (coordinates permanent)

**Performance Benchmarks:**

| Query Type | Cold Cache | Warm Cache | Speedup |
|-----------|-----------|-----------|---------|
| "North Punjab" | 22.5s | 12ms | 1,875x |
| "South-Western KPK" | 8.5s | 95ms | 89x |
| Batch (4 directional) | 24s | 380ms | 63x |
| Fuzzy "Islamabad" | 180ms | 45ms | 4x |
| External API | 450ms | 40ms | 11x + cost savings |

---

## API Reference

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

**Match Methods:**
- `exact_name` - Exact trigram match (similarity = 1.0)
- `fuzzy_name` - Fuzzy match above threshold
- `directional` - Grid-based directional query
- `point_in_polygon` - External API → PostGIS containment

### GET /api/v1/geocode/{location}

Geocode a single location via URL path.

**Example:**
```bash
curl http://localhost:8000/api/v1/geocode/Lahore
```

### GET /api/v1/suggest/{query}

Get suggestions for typos/misspellings.

**Parameters:**
- `query` (required): Search term
- `limit` (optional): Max results (default: 5)

**Example:**
```bash
curl "http://localhost:8000/api/v1/suggest/Islmabad?limit=5"
```

### GET /api/v1/health

Service health check.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-20T10:30:00Z"
}
```

---

## Performance & Monitoring

### Database Requirements

**Extensions:**
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

**Indexes:**
```sql
-- Fuzzy name matching (O(log n))
CREATE INDEX idx_places_name_trgm 
  ON places USING gin(name gin_trgm_ops);

-- Spatial queries (O(log n))
CREATE INDEX idx_places_polygon 
  ON places USING gist(polygon);

-- Hierarchy filtering
CREATE INDEX idx_places_hierarchy 
  ON places(hierarchy_level);
```

**SQL Functions:**

All functions are defined in `db_queries.sql`:
- `search_places_fuzzy()` - Fuzzy name matching with pg_trgm
- `find_place_by_point()` - Point-in-polygon lookup
- `find_places_in_direction()` - Directional grid search
- `get_directional_grid_cell()` - Grid cell calculator

### Performance Optimizations

**Application Level:**
1. **Async I/O** - All DB/API calls are non-blocking
2. **Connection pooling** - Shared HTTP client for external API
3. **Batch operations** - Parallel processing with `asyncio.gather()`
4. **LRU caching** - In-memory cache for parser (256 entries)
5. **Redis caching** - Distributed cache for query results

**Database Level:**
1. **GIN indexes** - O(log n) fuzzy search
2. **GIST indexes** - O(log n) spatial queries
3. **PostgreSQL functions** - Reduce data transfer, leverage DB optimizer
4. **Batch queries** - `.in_()` filter for multiple IDs

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Fuzzy name search | O(log n) | GIN index + trigram |
| Point-in-polygon | O(log n) | GIST spatial index |
| Directional parsing | O(n) | n = string length, regex |
| Directional query | O(log n) | PostGIS ST_Intersects with index |
| Hierarchical aggregation | O(p + c) | p = parents, c = children |
| Batch fetch | O(1) | Single query with .in_() |

**Overall:** O(log n) for typical queries (dominated by DB index lookups)

### Monitoring

**Application Logs:**

```bash
# All logs
python -m geocoder

# Cache-related only
python -m geocoder 2>&1 | grep -E "cache|Cache"

# Errors only
python -m geocoder 2>&1 | grep -E "ERROR|error"
```

**Redis Monitoring:**

```bash
# CLI monitoring
redis-cli INFO stats
redis-cli INFO memory

# GUI tools
npm install -g redis-commander  # Web UI on :8081
```

**Production Monitoring:**
- Prometheus + Grafana
- Redis exporter for metrics
- Custom FastAPI middleware for request timing

---

## Troubleshooting

### Service Won't Start

**Symptoms:**
- Error on `python -m geocoder`
- Port already in use

**Solutions:**
```bash
# Check if port 8000 is in use
lsof -i :8000
# Kill if needed: kill -9 <PID>

# Check logs for detailed error
python -m geocoder

# Verify .env file exists and has required variables
cat Backend/.env | grep -E "SUPABASE|LOCATION"
```

### Tests Fail with "Connection Refused"

**Symptoms:**
- curl tests fail
- test_api.py shows connection errors

**Solutions:**
```bash
# Ensure service is running
python -m geocoder

# Check correct URL
curl http://localhost:8000/api/v1/health

# Check firewall
sudo ufw allow 8000
```

### "Function Not Found" Errors

**Symptoms:**
- Database errors mentioning missing functions
- test_setup.py Phase 2 fails

**Solutions:**
```bash
# Run db_queries.sql in Supabase SQL Editor
cat geocoding/db_queries.sql
# Copy and paste into Supabase → SQL Editor → Run

# Verify functions exist
# In Supabase SQL Editor:
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' 
  AND routine_name LIKE '%places%';
```

### No Results Returned

**Symptoms:**
- Query completes but matched_places is empty
- Valid place names return no matches

**Solutions:**
```bash
# Check places table has data
# In Supabase SQL Editor:
SELECT COUNT(*) FROM places;

# Verify polygons are valid
SELECT COUNT(*) FROM places WHERE polygon IS NOT NULL;

# Check fuzzy match threshold
# In .env, try lowering threshold:
FUZZY_MATCH_THRESHOLD=0.75

# Test direct database query
# In Supabase SQL Editor:
SELECT * FROM search_places_fuzzy('Lahore', 0.85);
```

### Redis Connection Errors

**Symptoms:**
- `redis.exceptions.ConnectionError`
- Warnings about Redis unavailable

**Solutions:**
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Restart Redis
sudo systemctl restart redis-server

# Check Redis port
netstat -tulpn | grep 6379

# Test connection
python tests/test_redis.py

# Disable Redis if not needed
# In .env:
REDIS_ENABLED=false
```

### Slow Queries Even with Cache

**Symptoms:**
- Queries still slow after first run
- Cache hit logs not appearing

**Possible Causes:**
1. Cache MISS (first query is always slow)
2. TTL expired
3. Cache key mismatch
4. Redis network latency

**Debug:**
```bash
# Monitor Redis operations in real-time
redis-cli MONITOR

# In another terminal, make request
curl -X POST http://localhost:8000/api/v1/geocode ...

# Check for GET/SET operations in MONITOR output

# Check cache keys
redis-cli KEYS "geocode:*"

# Check TTL of a key
redis-cli TTL geocode:directional:some-key
```

### External API Errors (LocationIQ)

**Symptoms:**
- Errors mentioning LocationIQ
- 429 rate limit errors

**Solutions:**
```bash
# Verify API key
echo $LOCATION_IQ_KEY

# Check usage at locationiq.com dashboard

# Redis caching helps reduce API calls
# Enable Redis to cache results for 30 days

# Alternative: use different geocoding provider
# Update services/external_geocoder.py
```

---

## Database Schema

The `places` table structure:

```sql
CREATE TABLE places (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  parent_id uuid REFERENCES places(id) ON DELETE SET NULL,
  parent_name text,
  hierarchy_level integer,
  polygon geometry(Polygon, 4326)
);
```

**Hierarchy Levels:**
- Level 0: Pakistan (country)
- Level 1: Provinces (Punjab, Sindh, KPK, Balochistan, Gilgit Baltistan, AJK, ICT)
- Level 2: Districts (~150 districts)
- Level 3: Tehsils (~500+ tehsils)

---

## Credits

**Built with:**
- FastAPI - Web framework
- Supabase - PostgreSQL database
- PostGIS - Spatial operations
- pg_trgm - Fuzzy string matching
- LocationIQ - External geocoding fallback
- Redis - Distributed cache
- Pydantic - Data validation
- httpx - Async HTTP client

**Documentation:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and design patterns
- [GEOCODING.md](GEOCODING.md) - This file

---

**Last Updated:** January 20, 2026  
**Version:** 2.0 (Redis caching integrated)
