# REACH Test Suite - Implementation Guide

This document provides instructions for running all implemented tests for the REACH project.

## Quick Start

### From Project Root (Windows)

**Using PowerShell (Recommended):**
```powershell
.\run_all_tests.ps1
```

**Using Batch:**
```batch
run_all_tests.bat
```

**With Coverage Reports:**
```powershell
.\run_all_tests.ps1 -Coverage
```

**Run Specific Test Suite:**
```powershell
# Backend unit tests only
.\run_all_tests.ps1 -Unit

# Integration tests only
.\run_all_tests.ps1 -Integration

# Frontend E2E tests only
.\run_all_tests.ps1 -E2E

# Performance tests only
.\run_all_tests.ps1 -Performance
```

---

## Test Organization

### Backend Tests (Python/PyTest)

**Location:** `Backend/processing_engine/tests/` and `Backend/tests/integration/`

#### Unit Tests: Processing Engine (10 cases)
Tests for document utilities, LLM client, and pipeline processor.

**Files:**
- `test_doc_utils.py` - Document conversion, PDF handling, URL fetching
- `test_llm_client.py` - LLM initialization and API calls
- `test_pipeline_processor.py` - JSON parsing and validation

**Run:**
```bash
cd Backend
pytest processing_engine/tests/ -v --cov=processing_engine
```

#### Integration Tests (5 cases)
Tests for API validation, error handling, and caching.

**File:**
- `test_validation_error_handling.py` - API validation, 500 errors, cache integration

**Run:**
```bash
cd Backend
pytest tests/integration/ -v
```

### Frontend Tests (TypeScript/Jest)

**Location:** `Frontend/src/test/`

#### Unit Tests: Frontend Logic (10 cases)

**Files:**
- `LRUCache.test.ts` - Cache set/get, eviction, TTL
- `alertsService.test.ts` - Geometry caching, cache invalidation
- `useAlerts.test.ts` - Data loading, error handling
- `components.test.ts` - Filter panel, date selector, severity helpers

**Run:**
```bash
cd Frontend
npm test
```

**With Coverage:**
```bash
cd Frontend
npm test -- --coverage
```

**Watch Mode:**
```bash
cd Frontend
npm run test:watch
```

### System Tests (E2E & Performance)

#### E2E Tests: Dashboard Workflows (Cypress)

**Location:** `Frontend/cypress/e2e/dashboard.cy.ts`

**Tests:**
- Dashboard loading
- Filtering by disaster type
- Filtering by severity
- Location search
- Date range filtering
- Alert detail view

**Prerequisites:**
The Cypress suite mocks the Supabase RPC calls used by the dashboard, so you only need the frontend running. Make sure the frontend environment variables are available (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and the Mapbox token the app expects).

**Terminal 1:**
```bash
cd Frontend
npm install
npm run dev
```

**Terminal 2 (Run tests):**
```bash
cd Frontend
npm run e2e:open   # Interactive mode
# or
npm run e2e        # Headless mode
```

#### Performance Tests: Load Testing (k6)

**Location:** `Tests/performance/load.js`

**Tests:**
- Homepage load time (< 3s target)
- API response time (< 2s target)
- Concurrent user handling (100+ VUs)
- Error rate monitoring (< 1% target)

**Prerequisites:**
Start backend and frontend as above.

**Run:**
```bash
k6 run Tests/performance/load.js
```

---

## Test Statistics

| Test Type | Count | Framework | Location |
|---|---|---|---|
| Backend Unit | 10 | PyTest | Backend/processing_engine/tests/ |
| Backend Integration | 5 | PyTest | Backend/tests/integration/ |
| Frontend Unit | 10 | Jest | Frontend/src/test/ |
| Frontend E2E | 6 | Cypress | Frontend/cypress/e2e/ |
| Performance | 5+ checks | k6 | Tests/performance/ |
| **Total** | **36+** | - | - |

---

## Mocking Strategy

All tests use comprehensive mocking to prevent external dependencies:

### LLM API (Gemini Flash)
- **Status:** 100% mocked
- **Fixture:** `Backend/processing_engine/tests/conftest.py`
- **Mock Response:** Sample alert JSON with standard fields

### Database (Supabase/PostgreSQL)
- **Status:** 100% mocked
- **Fixture:** `Backend/tests/conftest.py`
- **Mock Behavior:** Returns sample data, no actual writes

### Redis Cache
- **Status:** 100% mocked
- **Behavior:** Simulates get/set/delete operations

### External Services
- **HTTP Requests:** Mocked with sample responses
- **PDF Processing:** Mock PDF bytes and page data
- **Mapbox:** Not tested at unit level (handled by Cypress)

---

## Running Individual Test Files

### Backend Unit Tests
```bash
cd Backend
pytest processing_engine/tests/test_doc_utils.py -v
pytest processing_engine/tests/test_llm_client.py -v
pytest processing_engine/tests/test_pipeline_processor.py -v
```

### Backend Integration Tests
```bash
cd Backend
pytest tests/integration/test_validation_error_handling.py -v
```

### Frontend Unit Tests
```bash
cd Frontend
npm test LRUCache.test.ts
npm test alertsService.test.ts
npm test useAlerts.test.ts
npm test components.test.ts
```

---

## Coverage Reports

### Backend Coverage
```bash
cd Backend
pytest processing_engine/tests/ --cov=processing_engine --cov-report=html
# Open: Backend/htmlcov/index.html
```

### Frontend Coverage
```bash
cd Frontend
npm test -- --coverage
# Open: Frontend/coverage/lcov-report/index.html
```

---

## Expected Results

### Unit Tests
- ✅ All 20 unit tests should **PASS**
- ✅ Coverage should be **>80%**
- ⏱️ Execution time: **~30-60 seconds**

### Integration Tests
- ✅ All 5 integration tests should **PASS**
- ✅ No external API calls made (all mocked)
- ⏱️ Execution time: **~20-30 seconds**

### E2E Tests (Optional - Requires Frontend Dev Server)
- ✅ All 6 Cypress tests should **PASS**
- ✅ API mocking verified
- ⏱️ Execution time: **~2-3 minutes**

### Performance Tests (Optional - Requires Running Services)
- ✅ p95 latency < 2 seconds
- ✅ Error rate < 1%
- ✅ Homepage load < 3 seconds
- ⏱️ Execution time: **~3-5 minutes**

---

## Troubleshooting

### Backend Tests Fail
1. **Ensure dependencies installed:**
   ```bash
   pip install pytest pytest-cov pytest-mock pytest-asyncio httpx
   ```
2. **Check Python version:** Python 3.9+ required
3. **Verify fixtures:** Ensure `conftest.py` files exist in test directories

### Frontend Tests Fail
1. **Install dependencies:**
   ```bash
   cd Frontend
   npm install
   ```
2. **Clear Jest cache:**
   ```bash
   npm test -- --clearCache
   ```
3. **Check Node version:** Node 16+ required

### E2E Tests Fail
1. **Verify services running:**
   - Frontend: `http://localhost:3000`
   - Backend: `http://localhost:8000`
2. **Clear browser cache:** Cypress clears automatically, but try:
   ```bash
   npx cypress cache clear
   ```
3. **Check port conflicts:** Use different ports if needed

### Performance Tests Fail
1. **k6 not found:** Install k6 from https://k6.io/docs/get-started/install/
2. **Port conflicts:** Ensure ports 3000 and 8000 are available
3. **Timeout issues:** Increase thresholds in `Tests/performance/load.js`

---

## Configuration Files

### pytest.ini
- Configures test discovery and coverage
- Located: `pytest.ini` (project root)

### jest.config.js
- Configures Jest for TypeScript support
- Located: `Frontend/jest.config.js`

### cypress.config.ts
- Configures Cypress timeouts and viewport
- Located: `Frontend/cypress.config.ts`

---

## Continuous Integration (CI)

For CI/CD pipelines, use:

```bash
# Run all tests (recommended)
.\run_all_tests.ps1 -Unit -Integration

# Skip E2E and performance tests (no running services)
# Just run unit and integration tests
```

---

## Test Maintenance

### Adding New Tests
1. Place in appropriate directory
2. Follow naming convention: `test_*.py` or `*.test.ts`
3. Use existing fixtures from `conftest.py`
4. Update plan.md with new test cases

### Updating Mocks
- Backend mocks: `Backend/processing_engine/tests/conftest.py`
- Backend mocks: `Backend/tests/conftest.py`
- Frontend setup: `Frontend/src/test/setup.ts`

### Updating Fixtures
- Ensure fixtures match actual API responses
- Keep fixture data realistic and diverse
- Update error scenarios as needed

---

## Next Steps

1. ✅ **Run unit tests first** - Should always pass
2. ✅ **Run integration tests** - Validates API contracts
3. 🟡 **Run E2E tests** - Requires running services
4. 🟡 **Run performance tests** - Validates load handling

---

**Last Updated:** May 5, 2026  
**Total Tests Implemented:** 36+  
**Target Coverage:** 80%+  
**Expected Total Execution Time:** 5-10 minutes (all tests, with services)
