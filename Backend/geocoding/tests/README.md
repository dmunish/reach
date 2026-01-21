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

### test_curl_commands.sh
**Purpose**: Comprehensive bash script testing 15 different scenarios with timing

**Features:**
- Formatted output (names + hierarchy levels only)
- Execution time tracking for each test
- Summary table at the end
- Total execution time calculation

**Usage:**
```bash
chmod +x test_curl_commands.sh
./test_curl_commands.sh
```

**Performance:**
- First run (cold cache): ~3-5 minutes
- Second run (warm cache): ~5-10 seconds (20-50x faster)

**Tests:**
1. Simple Place Name - Islamabad
2. Fuzzy Match - Typo "Lahor"
3. Directional - Northern Gilgit Baltistan
4. Directional - Central Sindh
5. Directional - Eastern Punjab
6. Directional - South-Western Balochistan
7. Directional - North-Eastern KPK
8. Batch Processing - Multiple Locations
9. Province-level - Sindh
10. District-level - Swat
11. GET Endpoint - Single Location
12. Suggestions - Typo "Islmabad"
13. Health Check
14. Multiple Directional Queries
15. Hierarchical Aggregation Test

## Prerequisites

All tests require:
- Service running: `python -m geocoder` (from Backend directory)
- Valid .env configuration
- Database with SQL functions installed

Additional requirements:
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
   python -m geocoder
   ```

3. **Run Integration Tests**
   ```bash
   python tests/test_api.py
   ```

4. **Run Comprehensive Curl Tests**
   ```bash
   ./tests/test_curl_commands.sh
   ```

5. **Test Redis (if enabled)**
   ```bash
   python tests/test_redis.py
   ```

## Expected Results

### First Run (Cold Cache)
- Simple queries: ~50-200ms
- Directional queries: ~7-10 seconds
- Batch queries: ~30-60 seconds

### Second Run (Warm Cache with Redis)
- Simple queries: ~20-50ms (2-4x faster)
- Directional queries: ~100-200ms (70x faster)
- Batch queries: ~500ms-2s (60x faster)

## Troubleshooting

### "Connection Refused" errors
Service not running. Start with:
```bash
python -m geocoder
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
