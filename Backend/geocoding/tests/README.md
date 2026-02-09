# Geocoding Microservice - Tests

This directory contains all testing utilities for the geocoding microservice.

## Test Files

### test_setup.py
**Purpose**: 4-phase validation script to verify installation and configuration

**Phases:**
1. Configuration & Connectivity - Validates .env, Supabase, LocationIQ, Redis
2. Database Layer - Checks PostgreSQL extensions, functions, indexes
3. Service Layer - Tests parsers, matchers, external geocoder, cache
4. End-to-End Integration - Full geocoding workflow validation

**Usage:**
```bash
# Run all phases
python test_setup.py

# Run specific phase
python test_setup.py --phase 1
```

### test_api.py
**Purpose**: Python integration tests with colored terminal output

**Features:**
- Color-coded results (green=success, red=error, yellow=warning)
- Pretty-printed JSON responses
- Tests all major endpoints
- Connection error handling
- No file output (terminal only)

**Usage:**
```bash
python test_api.py
```

**Tests:**
- Health check
- Simple place name (Islamabad)
- Fuzzy matching (typos)
- Directional queries (Central Sindh)
- Batch processing (6 locations)
- GET endpoint
- Suggestions endpoint

### test_redis.py
**Purpose**: Redis connectivity and performance validation

**Tests:**
- Connection establishment
- Basic operations (SET/GET/DELETE)
- Performance comparison (with/without cache)
- Error handling

**Usage:**
```bash
python test_redis.py
```

**Expected Output:**
```
✅ Redis connection successful!
✅ SET: ✅
✅ GET: ✅
✅ DELETE: ✅
⚡ Speedup: 50.2x faster
```

### test_comprehensive.sh
**Purpose**: Unified comprehensive bash script testing 42 scenarios with full coverage

**Features:**
- Color-coded output (green=success, red=error, yellow=metrics, blue=headers)
- Formatted output (names + hierarchy levels only)
- Execution time tracking for each test
- Summary table at the end with 60-character column widths
- Total execution time calculation

**Usage:**
```bash
chmod +x test_comprehensive.sh
./test_comprehensive.sh
```

**Performance:**
- First run (cold cache): ~50-60 seconds (database queries)
- Second run (warm cache): <5 seconds with Redis (10-20x faster)

**Test Coverage (42 tests):**
1. **Simple Place Names (6 tests)**: Islamabad, Karachi, Lahore, Peshawar, Quetta, Multan
2. **Fuzzy Matching (4 tests)**: \"Lahor\", \"Multn\", \"Peshwar\", \"Islmabad\" (typo tolerance)
3. **Directional - Cardinals (4 tests)**: Northern GB, Southern Punjab, Eastern Punjab, Western Punjab
4. **Directional - Central (1 test)**: Central Sindh
5. **Directional - Ordinals (3 tests)**: SE Sindh, Central Balochistan, SW Balochistan, NW Balochistan, NE KP
6. **Cross-Border Validation (4 tests)**: Northern Sindh (no Punjab), Western KP (no Balochistan), Eastern Balochistan (no Punjab), Western Sindh (no Balochistan)
7. **Hierarchy Precision (2 tests)**: Quetta City vs Quetta, Swat District
8. **Enclaves (1 test)**: Orangi Town (Karachi subdivision without \"Karachi\" in query)
9. **Batch Processing (3 tests)**: Multiple cities, mixed provinces, multiple directional
10. **Aggregation (2 tests)**: Central Punjab, Southern Sindh
11. **Province-Level (4 tests)**: Punjab, Sindh, KP, Balochistan
12. **GET Endpoint (2 tests)**: Lahore, Karachi
13. **Suggestions (2 tests)**: \"Islmabad\", \"Peshwar\" typos
14. **Health Check (1 test)**: Service status

**Expected Accuracy**: 95-98% (40-41 of 42 tests passing)

**Output Format:**
```
=== Test #1: Simple - Islamabad ===
Islamabad (Level 2)
Result Count: 1 places

=== Test #2: Simple - Karachi ===
South Karachi (Level 2)
Result Count: 1 places

...

Test Execution Summary
===========================================================================
Test Name                                                    Results    Time (s)       
---------------------------------------------------------------------------
Simple - Islamabad                                           1          .799715529     
Simple - Karachi                                             1          .362036977     
...
---------------------------------------------------------------------------
TOTAL                                                        340        52.232801068   

Performance Metrics:
  Total Tests: 42
  Total Results: 340 places
  Total Execution Time: 52.232801068s
  Average Time per Test: 1.243s
```
## Prerequisites

All tests require:
- Service running: `python -m geocoding` (from Backend directory)
- Valid .env configuration
- Database with SQL functions installed

Additional requirements for bash scripts:
- `jq` for JSON parsing: `sudo apt install jq`
- `bc` for timing calculations: `sudo apt install bc`

## Testing Workflow

1. **Setup Validation**
   ```bash
   python test_setup.py
   ```

2. **Start Service**
   ```bash
   cd /home/ahmad_shahmeer/reach-geocoding/Backend
   python -m geocoding
   ```

3. **Run Integration Tests**
   ```bash
   python tests/test_api.py
   ```

4. **Run Comprehensive Test Suite**
   ```bash
   ./tests/test_comprehensive.sh
   ```

5. **Test Redis (if enabled)**
   ```bash
   python tests/test_redis.py
   ```

## Expected Results

### First Run (Cold Cache)
- Simple queries: ~50-200ms
- Directional queries: ~2-3 seconds
- Batch queries: ~2-3 seconds
- **Total for 42 tests**: ~50-60 seconds

### Second Run (Warm Cache with Redis)
- Simple queries: ~20-50ms (2-4x faster)
- Directional queries: ~50-100ms (20-30x faster)
- Batch queries: ~100-200ms (10-15x faster)
- **Total for 42 tests**: <5 seconds (10-20x faster overall)

**Performance Gains:**
- In-memory LRU cache: 500 most frequently accessed places (sub-ms access)
- Redis distributed cache: All query types (10-100ms)
- 7 database indexes: O(log n) queries for cold cache misses
- Parallel batch processing: ~10-30x speedup for batch operations

## Test Results Storage

Test results are automatically saved to `test_results.txt` with:
- Individual test outputs with color formatting
- Execution time for each test
- Summary table with test names, result counts, and timings
- Overall performance metrics

## Manual Testing with curl

For manual testing or debugging individual queries, use these curl commands with jq filters to format output:

### Simple Place Name Query
```bash
# Single location
curl -s -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Islamabad"]}' | \
  jq -r '.results[] | .matched_places[] | "\(.name) (Level \(.hierarchy_level))"'

# Output: Islamabad (Level 2)
```

### Fuzzy Matching (Typo Tolerance)
```bash
# Typo: "Lahor" instead of "Lahore"
curl -s -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Lahor"]}' | \
  jq -r '.results[] | .matched_places[] | "\(.name) (Level \(.hierarchy_level))"'

# Output: Lahor (Level 3)
```

### Directional Query
```bash
# Northern region
curl -s -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Northern Gilgit Baltistan"]}' | \
  jq -r '.results[] | .matched_places[] | "\(.name) (Level \(.hierarchy_level))"'

# Output: 
# Nagar (Level 3)
# Hunza (Level 2)
```

### Batch Query (Multiple Locations)
```bash
# Multiple cities at once
curl -s -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Islamabad",
      "Central Sindh",
      "Lahore"
    ]
  }' | \
  jq -r '.results[] | .matched_places[] | "\(.name) (Level \(.hierarchy_level))"'

# Output:
# Islamabad (Level 2)
# Mehrab Pur (Level 3)
# Naushahro Feroze (Level 3)
# ... (more Central Sindh places)
# Lahore (Level 2)
```

### GET Endpoint (Simple)
```bash
# Single location via GET
curl -s -X GET "http://localhost:8000/api/v1/geocode/Lahore" | \
  jq -r '.results[] | .matched_places[] | "\(.name) (Level \(.hierarchy_level))"'

# Output: Lahore (Level 2)
```

### Suggestions Endpoint (Typo Correction)
```bash
# Get suggestions for typo
curl -s -X GET "http://localhost:8000/api/v1/suggest/Islmabad?limit=5" | \
  jq -r '.suggestions[] | "\(.name) (Level \(.hierarchy_level))"'

# Output:
# Islamabad (Level 1)
# Islamabad (Level 2)
# Islamabad (Level 3)
```

### With Input Tracking
```bash
# Show which input matched which result
curl -s -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Northern Sindh",
      "Peshawar City",
      "Lahor"
    ]
  }' | \
  jq -r '.results[] | .input as $q | .matched_places[] | "Query: [\($q)] -> \(.name) (Level \(.hierarchy_level))"'

# Output:
# Query: [Northern Sindh] -> Mehrab Pur (Level 3)
# Query: [Northern Sindh] -> Naushahro Feroze (Level 3)
# ...
# Query: [Peshawar City] -> Town-I (Level 3)
# Query: [Lahor] -> Lahor (Level 3)
```

### Full JSON Response (Debugging)
```bash
# See complete response with all fields
curl -s -X POST "http://localhost:8000/api/v1/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Islamabad"]}' | jq '.'

# Output includes: id, name, hierarchy_level, match_method, confidence, etc.
```

### Health Check
```bash
curl -s -X GET "http://localhost:8000/api/v1/health" | jq '.'

# Output:
# {
#   "status": "healthy",
#   "service": "geocoding-microservice",
#   "version": "1.0.0"
# }
```

## Troubleshooting

### "Connection Refused" errors
Service not running. Start with:
```bash
python -m geocoding
```

### "Command not found: jq"
Install jq:
```bash
sudo apt install jq
```

### "bc: command not found"
Install bc:
```bash
sudo apt install bc
```

### Redis errors in test_redis.py
Either:
1. Install and start Redis
2. Set `REDIS_ENABLED=false` in .env

### Test failures
Run setup validation:
```bash
python test_setup.py
```

Check which phase fails and address the specific issue.
