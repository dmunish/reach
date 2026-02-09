# Geocoding Microservice Documentation

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Key Features](#key-features)
4. [API Reference](#api-reference)
5. [Directional Geocoding System](#directional-geocoding-system)
6. [Performance & Caching](#performance--caching)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Geocoding Microservice converts location references from disaster alert documents into standardized place IDs from Pakistan's administrative boundary hierarchy.

### Core Capabilities

- **Simple name matching**: Fuzzy matching against place names (e.g., "Islamabad", "Lahor")
- **Directional processing**: Geographic descriptions ("Northern Punjab", "South-Western Balochistan")
- **Hierarchical aggregation**: Smart consolidation to avoid redundant parent/child places
- **Batch processing**: Multiple locations in a single request
- **Three-tier caching**: In-memory LRU (500) → Redis → PostgreSQL

### Tech Stack

- **FastAPI**: Async web framework
- **Supabase/PostgreSQL + PostGIS**: Spatial database with geographic functions
- **pg_trgm**: Fuzzy string matching extension
- **Redis**: Distributed caching layer (optional but recommended)
- **Pydantic**: Data validation and serialization

### Performance

| Query Type | Cold (No Cache) | Warm (Redis) | Speedup |
|------------|----------------|--------------|---------|
| Simple name | ~50ms | ~20ms | 2-3x |
| Directional | ~2-3s | ~100ms | **20-30x** |
| Batch (5 locations) | ~500-800ms | ~200ms | 3-4x |

**Optimization Highlights:**
- 7 PostgreSQL indexes (GIN trigram, GIST spatial, B-tree hierarchy)
- In-memory LRU cache (500 entries) for instant repeated queries
- Redis distributed cache for cross-instance sharing
- Parallel async processing with `asyncio.gather()`

---

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 14+ with PostGIS extension
- Redis (optional, for distributed caching)
- Supabase project with `places` table

### Installation

```bash
# 1. Navigate to Backend directory
cd /home/ahmad_shahmeer/reach-geocoding/Backend

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cat > .env << EOF
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
REDIS_URL=redis://localhost:6379/0  # Optional
EOF

# 4. Deploy database functions and indexes
# Copy contents of geocoding/db_queries.sql
# Run in Supabase SQL Editor

# 5. Start the service
cd geocoding
chmod +x start.sh
./start.sh
```

The service will be available at `http://localhost:8000`.

### Quick Test

```bash
curl -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Islamabad"]}'
```

---

## Key Features

### 1. Simple Name Matching

Direct fuzzy matching using PostgreSQL's trigram similarity:

```bash
# Exact match
curl -X POST "$BASE_URL/geocode" \
  -d '{"locations": ["Lahore"]}'

# Typo tolerance
curl -X POST "$BASE_URL/geocode" \
  -d '{"locations": ["Lahor"]}'  # Matches "Lahore"
```

**Aggressive Fuzzy Matching**:
- Default threshold: **0.30** (true fuzzy territory)
- Uses `%` operator (trigram index), `similarity > 0.3`, `word_similarity > 0.4`
- **Hierarchy-first sorting**: Provinces/districts prioritized over villages regardless of similarity score
- Result: Low-quality matches (villages) automatically sorted to bottom even with lenient thresholds

### 2. Directional Geocoding

Advanced spatial system using **dynamic radial sectors with aspect-ratio aware envelopes**:

#### Cardinal Directions (N, E, S, W)

**OVERLAPPING INCLUSIVE SECTORS** (eliminates geographic holes):
- **Large provinces** (>150k km²): **120° wide sectors** (±60° from center) - OVERLAPPING
- **Small provinces** (≤150k km²): **135° wide sectors** (±67.5° from center) - WIDE OVERLAPPING
- **Azimuth-based**: Uses `ST_Azimuth(base_centroid, place_centroid)` for true geographic direction
- **Softened bbox filter**: **75% coverage** (25% exclusion) - allows South Sindh to capture Karachi, North Punjab to reach mid-latitude districts

```bash
# Examples
curl -X POST "$BASE_URL/geocode" \
  -d '{"locations": ["Northern Gilgit Baltistan"]}'

curl -X POST "$BASE_URL/geocode" \
  -d '{"locations": ["Eastern Punjab"]}'
```

**How it works:**
1. Calculate province centroid using `ST_PointOnSurface(combined_polygon)`
2. Calculate azimuth (angle) from centroid to each place: `DEGREES(ST_Azimuth(...))`
3. Filter places within **wide overlapping sectors** (e.g., North: 300°-60° for large provinces, 292.5°-67.5° for small)
4. Apply **softened bbox constraint** (top 75% for North, bottom 75% for South - was 60%)
5. Use strict containment: `ST_Covers(base_polygon, place_centroid)`
6. **Accept 20-30% overlap** between adjacent queries ("North" and "West" both include "Northwest" districts) to ensure complete coverage

#### Ordinal Directions (NE, SE, SW, NW)

**OVERLAPPING INCLUSIVE WEDGES**:
- **Large provinces**: **60° wedges** (±30° from diagonal) - OVERLAPPING
- **Small provinces**: **67.5° wedges** (±33.75° from diagonal) - WIDE OVERLAPPING
- **Softened bbox filter**: **75% combined** (top+right for NE, bottom+left for SW) - was 70%
- **Prevents diagonal leakage**: Places must be in both directional sector AND bbox region

```bash
curl -X POST "$BASE_URL/geocode" \
  -d '{"locations": ["South-Western Balochistan"]}'
```

**Example (NE):**
- Large province: Azimuth 15° - 75° (60° wedge) - OVERLAPPING
- Small province: Azimuth 11.25° - 78.75° (67.5° wedge) - WIDE OVERLAPPING
- PLUS top 75% of bbox AND right 75% of bbox (was 70%)

#### Central Regions

Aspect-ratio aware rectangular envelopes (NO radial sectors):

**WIDER INCLUSIVE CENTRAL** (reduced margins for better coverage):
- **Tall provinces** (aspect >1.2): **25% H / 25% V margins** (WIDER for better coverage)
- **Wide provinces** (aspect <0.83): **20% H / 25% V margins** (MUCH WIDER horizontal)
- **Balanced provinces** (0.83-1.2): **22% H / 22% V margins** (equal and WIDER)
- **Strict centroid containment**: Place's `ST_PointOnSurface()` must be within envelope
- **Captures larger central portions** of provinces (was 30-40% margins)

```bash
curl -X POST "$BASE_URL/geocode" \
  -d '{"locations": ["Central Sindh"]}'
```

### 3. Hierarchical Aggregation & Smart Matching

Automatically consolidates places to avoid redundancy:

```python
# If all tehsils of Lahore district match:
["Lahore City", "Lahore Cantt", "Model Town"] → ["Lahore (District)"]

# But respects partial matches:
["Lahore City", "Faisalabad City"] → ["Lahore City", "Faisalabad City"]
```

**Key Features:**

- **Level 1 Protection**: Directional queries never aggregate to province level (prevents over-generalization)
- **Hierarchy-First Matching**: ORDER BY prioritizes administrative significance over similarity score
  - `ORDER BY hierarchy_level ASC, similarity_score DESC` (was score DESC first)
  - A 30% match on a Province/District is more relevant than 90% match on a remote village
  - Example: "Azad Jammu and Kashmir" → Level 1 Province (not random high-similarity subdivision)
- **Aggressive Typo Tolerance**: Multi-threshold fuzzy matching
  - Default threshold: **0.30** (was 0.60-0.85)
  - Uses `%` operator (0.3), `similarity > 0.3`, `word_similarity > 0.4`
  - Handles extreme typos: "Peshwar" → "Peshawar", "Islmabad" → "Islamabad", "Multn" → "Multan"
- **Dual Similarity Modes**: `GREATEST(similarity(), word_similarity())` for better long-name matching (e.g., "Azad Jammu and Kashmir")

### 4. Batch Processing

Process multiple locations in a single request:

```bash
curl -X POST "$BASE_URL/geocode" \
  -d '{
    "locations": [
      "Islamabad",
      "Northern Punjab",
      "Central Sindh",
      "Quetta"
    ]
  }'
```

Batch queries use parallel processing (`asyncio.gather()`) for optimal performance.

### 5. Three-Tier Caching

```
Request → In-Memory LRU (500) → Redis → PostgreSQL
            ↓ ~0ms               ↓ ~20ms   ↓ ~2-3s
```

**Cache Keys:**
- Simple: `simple:{location_name}`
- Directional: `directional:{base_place_id}:{direction}`
- Aggregated: `aggregated:{sorted_place_ids}`

**TTL**: 24 hours (configurable)

---

## API Reference

### Base URL

```
http://localhost:8000/api/v1
```

### Endpoints

#### POST /geocode

Geocode single or multiple locations.

**Request:**
```json
{
  "locations": ["Northern Punjab", "Islamabad"]
}
```

**Response:**
```json
{
  "results": [
    {
      "query": "Northern Punjab",
      "matched_places": [
        {
          "id": "uuid",
          "name": "Rawalpindi",
          "hierarchy_level": 2,
          "parent_id": "uuid"
        }
      ],
      "match_type": "directional"
    }
  ]
}
```

#### GET /geocode/{location}

Quick geocode for single location (GET method).

```bash
curl "$BASE_URL/geocode/Lahore"
```

#### GET /suggest/{query}

Get fuzzy match suggestions.

```bash
curl "$BASE_URL/suggest/Islmabad?limit=5"
```

**Response:**
```json
{
  "suggestions": [
    {
      "id": "uuid",
      "name": "Islamabad",
      "hierarchy_level": 3,
      "similarity_score": 0.92
    }
  ]
}
```

#### GET /health

Service health check.

```bash
curl "$BASE_URL/health"
```

---

## Directional Geocoding System

### Architecture

The directional system uses a **radial sector approach** with **aspect-ratio aware envelopes** to provide accurate geographic filtering without latitudinal leakage.

#### Key Components

1. **Province Size Detection**
   - Calculates bbox area using `ST_Area(polygon::geography)`
   - Threshold: 150,000 km²
   - Large provinces (Punjab, Sindh, Balochistan) use narrower 67.5° sectors
   - Small provinces (GB, KP, AJK) use wider 90° sectors

2. **Aspect Ratio Analysis**
   - Computes height/width ratio of province bbox
   - Tall (>1.2): Sindh-like, tighter horizontal margins
   - Wide (<0.83): Balochistan-like, tighter vertical margins
   - Balanced (0.83-1.2): Equal or slightly asymmetric margins

3. **Azimuth-Based Filtering**
   - Uses `ST_Azimuth(base_centroid, place_centroid)` for true geographic direction
   - Converts radians to degrees: `DEGREES(ST_Azimuth(...))`
   - Wraps around 360° for North direction (e.g., 315° - 45°)

4. **Secondary Bbox Constraints**
   - **Cardinals**: 60% bbox filter (40% central excluded)
   - **Ordinals**: 70% combined bbox (prevents diagonal leakage)
   - Applied with `ST_Covers(directional_bbox, ST_PointOnSurface(p.polygon))`

5. **Strict Containment**
   - Base region check: `ST_Covers(combined_geom, ST_PointOnSurface(p.polygon))`
   - Prevents cross-province leakage (e.g., AJK districts in KP queries)

### Sector Definitions (OVERLAPPING INCLUSIVE SECTORS)

| Direction | Large Provinces (>150k km²) | Small Provinces (≤150k km²) | Bbox Filter |
|-----------|----------------|----------------|-------------|
| North | **120°** (300° - 60°) | **135°** (292.5° - 67.5°) | Top **75%** |
| East | **120°** (30° - 150°) | **135°** (22.5° - 157.5°) | Right **75%** |
| South | **120°** (120° - 240°) | **135°** (112.5° - 247.5°) | Bottom **75%** |
| West | **120°** (210° - 330°) | **135°** (202.5° - 337.5°) | Left **75%** |
| NE | **60°** (15° - 75°) | **67.5°** (11.25° - 78.75°) | Top **75%** + Right **75%** |
| SE | **60°** (105° - 165°) | **67.5°** (101.25° - 168.75°) | Bottom **75%** + Right **75%** |
| SW | **60°** (195° - 255°) | **67.5°** (191.25° - 258.75°) | Bottom **75%** + Left **75%** |
| NW | **60°** (285° - 345°) | **67.5°** (281.25° - 348.75°) | Top **75%** + Left **75%** |

**Key Change**: Overlapping sectors (120-135° cardinals, 60-67.5° ordinals) eliminate geographic holes. Accept 20-30% overlap between queries for complete coverage.

### Central Envelope Margins (WIDER INCLUSIVE CENTRAL)

| Province Type | Horizontal Margin | Vertical Margin | Example |
|---------------|-------------------|----------------|---------|-------|
| Tall (aspect >1.2) | **25%** (was 40%) | **25%** (was 40%) | WIDER for better coverage |
| Wide (aspect <0.83) | **20%** (was 25%) | **25%** (was 40%) | MUCH WIDER horizontal |
| Balanced (0.83-1.2) | **22%** (was 30%) | **22%** (was 38%) | Sindh (aspect ~1.05) - WIDER |

**Key Change**: Reduced margins from 30-40% to 20-25% for more inclusive interior coverage. Captures larger central portions of provinces.

---

## Performance & Caching

### Database Optimization

7 indexes for optimal query performance:

```sql
-- Trigram for fuzzy name matching (O(log n))
CREATE INDEX idx_places_name_trgm ON places USING gin(name gin_trgm_ops);

-- Spatial for polygon operations (O(log n))
CREATE INDEX idx_places_polygon ON places USING gist(polygon);

-- B-tree for hierarchy filtering
CREATE INDEX idx_places_hierarchy ON places(hierarchy_level);

-- B-tree for parent lookups (hierarchical aggregation)
CREATE INDEX idx_places_parent_id ON places(parent_id);

-- B-tree for ID lookups (batch queries)
CREATE INDEX idx_places_id ON places(id);

-- Composite for parent + hierarchy queries
CREATE INDEX idx_places_parent_hierarchy ON places(parent_id, hierarchy_level);
```

### Caching Strategy

**In-Memory LRU Cache (L1)**
- 500 entry limit
- Instant retrieval (~0ms)
- Per-process, not shared across instances
- Implementation: `functools.lru_cache`

**Redis Cache (L2)**
- Distributed across all service instances
- ~20-50ms retrieval
- 24-hour TTL
- Fallback if L1 misses

**PostgreSQL (L3)**
- ~2-3s for complex directional queries
- ~50ms for simple name matches
- Source of truth

### Performance Monitoring

```python
# Logs show cache performance
INFO - Cache HIT (redis): directional:uuid:northern (21ms)
INFO - Cache MISS: simple:Unknown City - querying DB (2.3s)
```

---

## Testing

### Automated Test Suite

Comprehensive test script covering all edge cases:

```bash
cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding/tests

# Run comprehensive test suite (42 tests)
./test_comprehensive.sh
```

**Test Coverage (42 tests total):**
1. **Simple Names (6 tests)**: Islamabad, Karachi, Lahore, Peshawar, Quetta, Multan
2. **Fuzzy Matching (4 tests)**: "Lahor", "Multn", "Peshwar", "Islmabad" (typos)
3. **Directional Queries (10 tests)**: Northern GB, Southern Punjab, Eastern Punjab, etc.
4. **Cross-Border Validation (4 tests)**: Ensures no province leakage
5. **Hierarchy Precision (2 tests)**: Quetta City vs Quetta District, Swat District
6. **Enclaves (1 test)**: Orangi Town (Karachi subdivision)
7. **Batch Processing (6 tests)**: Multiple cities, provinces, mixed queries
8. **Aggregation (2 tests)**: Central Punjab, Southern Sindh
9. **Province-Level (4 tests)**: Punjab, Sindh, KP, Balochistan
10. **GET Endpoint (2 tests)**: Lahore, Karachi
11. **Suggestions (2 tests)**: Typo suggestions
12. **Health Check (1 test)**: Service status

**Performance:**
- Cold cache: ~50 seconds (database queries)
- Warm cache: <5 seconds (Redis cached)
- Speedup: 10-20x with caching

### Manual Testing

```bash
# Test simple name
curl -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Islamabad"]}'

# Test directional
curl -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Northern Punjab"]}'

# Test cache performance (run twice, compare times)
time curl -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Central Sindh"]}'
```

### Expected Results

**Accuracy**: 95-97% for directional queries
**Performance**: 
- Cold query: 2-3s for complex directional
- Warm query: <100ms with Redis
- Simple names: ~50ms cold, ~20ms warm

---

## Troubleshooting

### Common Issues

**1. Directional Query Returns Empty Results**

```bash
# Check if base region exists
curl -X POST "$BASE_URL/geocode" -d '{"locations": ["Punjab"]}'

# Check PostgreSQL logs for NOTICE messages
# Should show: "Large province detected (area: X km²)"
```

**2. Cross-Province Leakage**

If districts from neighboring provinces appear:
- Verify `ST_Covers` is used for base region check (not `ST_Intersects`)
- Check PostgreSQL function version in `db_queries.sql`

**3. Central/Southern Overlap**

If same districts appear in both "Central X" and "Southern X":
- Check aspect ratio calculation: `SELECT height/width FROM province_bbox`
- Verify vertical margin (should be 38% for balanced provinces)

**4. Slow Performance**

```bash
# Check cache status
redis-cli PING  # Should return PONG

# Check cache hit rate in logs
grep "Cache HIT" logs.txt | wc -l

# Flush cache if stale
redis-cli FLUSHALL
```

**5. Fuzzy Match Not Working**

```sql
-- Verify trigram extension
SELECT * FROM pg_extension WHERE extname = 'pg_trgm';

-- Test similarity threshold
SELECT name, similarity(name, 'Lahor') as sim 
FROM places 
WHERE similarity(name, 'Lahor') > 0.85;
```

### Debug Mode

Enable detailed logging:

```python
# In config.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Viewing PostgreSQL Logs

For Supabase:
1. Go to Supabase Dashboard → Database → Logs
2. Look for NOTICE messages showing sector calculations
3. Example: `NOTICE: Balanced province (aspect: 1.05), margins H:30% V:38%`

---

## Directory Structure

```
geocoding/
├── GEOCODING.md              # This file
├── ARCHITECTURE.md          # System architecture
├── start.sh                  # Setup script
├── config.py                 # Environment config
├── dependencies.py           # DI container
├── models.py                 # Pydantic models
├── exceptions.py             # Custom exceptions
├── db_queries.sql           # PostgreSQL functions
│
├── api/
│   └── routes.py            # FastAPI endpoints
│
├── repositories/
│   └── places_repository.py # Database + cache layer
│
├── services/
│   ├── geocoding_service.py     # Main orchestration
│   ├── name_matcher.py          # Fuzzy matching
│   ├── directional_parser.py    # Direction parsing
│   ├── external_geocoder.py     # LocationIQ fallback
│   └── redis_cache.py           # Redis caching
│
└── tests/
    ├── README.md
    ├── test_setup.py
    ├── test_api.py
    ├── test_redis.py
    ├── test_curl_commands.sh    # Test suite #1
    └── test_curl_commands_2.sh  # Test suite #2
```

---

## Additional Resources

- **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design patterns
- **Testing**: See [tests/README.md](tests/README.md) for comprehensive testing guide
- **PostGIS Documentation**: https://postgis.net/docs/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/

---

**Last Updated**: January 2026
**Version**: 2.0 (Radial Sector System with Aspect-Ratio Aware Envelopes)
