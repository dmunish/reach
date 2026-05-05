# REACH Test Plan - Focused Execution Strategy

**Created:** May 5, 2026  
**Scope:** Unit + Integration + System tests excluding Geocoding (as requested)  
**Objective:** Validate Processing Engine, Frontend, and critical API error handling with mocked LLM/DB

---

## Executive Summary

This plan prioritizes **33 test cases** from the SQE proposal across three tiers:
1. **Unit Tests**: Backend Processing Engine (10) + Frontend Logic (10) = 20 tests
2. **Integration Tests**: API error handling & validation (5 key tests from original 15)
3. **System Tests**: Core workflows + performance + security (8 from original 10)

**All geocoding tests are excluded** as per requirements. **LLM and Database API calls are fully mocked** to prevent external dependencies during testing.

---

## Part 1: Unit Testing (20 Test Cases)

### 1.1 Backend Processing Engine Tests (10 cases)

**File Location:** `Backend/processing_engine/`  
**Testing Framework:** PyTest  
**Mocking Strategy:** Mock LLMClient API calls, mock document fetch operations

#### Test Setup
```python
# Mock fixtures required
@pytest.fixture
def mock_llm_client():
    """Mock Gemini Flash API responses"""
    with patch('Backend.processing_engine.processor_utils.llm_client.AsyncLLMClient') as mock:
        mock.call.return_value = {
            "alert_type": "FLOOD",
            "severity": "EXTREME",
            "location_mentions": ["Sindh", "Karachi"],
            "description": "Flash flooding in urban areas"
        }
        yield mock

@pytest.fixture
def mock_document_fetch():
    """Mock HTTP fetch and PDF conversion"""
    with patch('Backend.processing_engine.processor_utils.doc_utils.fetch_file') as mock:
        mock.return_value = b'PDF_MOCK_CONTENT'
        yield mock
```

#### Test Cases

| ID | Module | Function | Test Description | Mock Strategy | Expected Output |
|---|---|---|---|---|---|
| UT-M2-001 | doc_utils | to_base64 | Convert PIL image to base64 JPEG | PIL image fixture (no mock) | Non-empty base64 string |
| UT-M2-002 | doc_utils | pdf_to_images | Convert single-page PDF to images | Mock fetch_file, mock PyPDF2 | List with 1 image per page |
| UT-M2-003 | doc_utils | pdf_to_images | Corrupted PDF error handling | Mock PyPDF2 to raise exception | Controlled exception propagated |
| UT-M2-004 | doc_utils | fetch_file | Successful HTTP fetch returns bytes | Mock requests.get with 200 response | Byte content returned |
| UT-M2-005 | doc_utils | url_to_b64_strings | Image URL → data URI conversion | Mock fetch_file with image bytes | One data URI in output list |
| UT-M2-006 | doc_utils | url_to_b64_strings | PDF URL → data URIs per page | Mock fetch_file + pdf_to_images | One data URI per page |
| UT-M2-007 | LLMClient | __init__ | Unsupported model key rejected | Config fixture with invalid model | ValueError raised |
| UT-M2-008 | AsyncLLMClient | call | Runtime kwargs merged with defaults | Mock API client, verify params | API called with merged params |
| UT-M2-009 | PipelineProcessor | _parse | Valid JSON parsed into domain objects | Mock parser dependencies | Alert object + alert areas created |
| UT-M2-010 | PipelineProcessor | _parse | Invalid enum/category rejected | Validation active | Validation error triggered |

**Execution Command:**
```bash
cd Backend
pytest processing_engine/tests/ -v --cov=processing_engine --cov-report=html
```

---

### 1.2 Frontend Logic Tests (10 cases)

**File Location:** `Frontend/src/`  
**Testing Framework:** Jest + React Testing Library  
**Mocking Strategy:** Mock Supabase RPC calls, mock alertsService API responses

#### Test Setup
```typescript
// Mock fixtures required
jest.mock('../services/alertsService', () => ({
  getAlertGeometry: jest.fn(),
  getAllAlerts: jest.fn(),
}));

jest.mock('../lib/supabase', () => ({
  supabase: {
    rpc: jest.fn(),
  },
}));
```

#### Test Cases

| ID | Module | Function | Test Description | Mock Strategy | Expected Output |
|---|---|---|---|---|---|
| UT-M3-001 | LRUCache | set/get | Retrieve inserted value & update recency | Cache initialized (no mock) | Returned value = inserted value |
| UT-M3-002 | LRUCache | set | Evict LRU when full | Small cache size (e.g., 2) | LRU key evicted |
| UT-M3-003 | LRUCache | get | Expired entry returns undefined | TTL configured (no mock) | Undefined result, stale key removed |
| UT-M3-004 | alertsService | getAlertGeometry | Geometry cache used on repeat | Mock Supabase RPC | RPC called once, 2nd from cache |
| UT-M3-005 | alertsService | invalidateStaleGeo | Remove cache entries not in active IDs | Cache pre-populated | Non-current keys removed |
| UT-M3-006 | useAlerts | initial fetch flow | autoFetch loads data & clears loading | Mock alertsService success | alerts populated, loading = false |
| UT-M3-007 | useAlerts | error handling flow | Failed service call sets error & empties alerts | Mock alertsService failure | error populated, alerts empty |
| UT-M3-008 | FilterPanel | severity mapping helper | Moderate default includes upward severities | Component logic isolated | Returned severities match policy |
| UT-M3-009 | DateRangeSelector | date normalization | Start date after end date triggers swap | Component mounted | Callback receives corrected order |
| UT-M3-010 | RecentAlertsPanel | severity helper | Unknown severity uses fallback style | Helper callable | Default/fallback mapping returned |

**Execution Command:**
```bash
cd Frontend
npm test -- --coverage --testPathPattern="(unit|spec)" --no-coverage-threshold
```

**Setup:** Ensure Jest is configured in `package.json`:
```json
{
  "jest": {
    "testEnvironment": "jsdom",
    "setupFilesAfterEnv": ["<rootDir>/src/test/setup.ts"]
  }
}
```

---

## Part 2: Integration Testing (5 Key Test Cases)

**File Location:** `Backend/geocoding/api/` and `Backend/processing_engine/`  
**Testing Framework:** PyTest + FastAPI TestClient  
**Mocking Strategy:** Mock database writes, mock Redis, mock external geocoder fallback

### 2.1 Focus Areas (Excluding Geocoding Endpoints)

We select 5 critical integration tests that avoid geocoding but validate error handling, validation, and caching:

| ID | Scenario | Endpoint | Mock Strategy | Expected Result | Status |
|---|---|---|---|---|---|
| IT-008 | Validation: empty locations rejected | POST /api/v1/geocode | Request validation | 422 Unprocessable Entity | Not geocoding-dependent |
| IT-009 | Validation: malformed options | POST /api/v1/geocode | Pydantic validation | 422 Unprocessable Entity | Not geocoding-dependent |
| IT-012 | Internal service exception → 500 | POST /api/v1/geocode | Mock service to throw | 500 with generic message | Error handling test |
| IT-013 | Cache integration on repeat | POST /api/v1/geocode (twice) | Mock Redis caching | 2nd response faster | Caching behavior test |
| IT-014 | Concurrent requests stability | POST /api/v1/geocode (50x) | Load simulation | No 5xx, success rate ≥99% | Concurrency test |

**Test Implementation:**
```python
from fastapi.testclient import TestClient
from Backend.app import app  # Your FastAPI app
from unittest.mock import patch

client = TestClient(app)

def test_validation_empty_locations():
    """Test IT-008: Empty locations list rejected"""
    response = client.post("/api/v1/geocode", json={"locations": []})
    assert response.status_code == 422
    assert "validation" in response.json()["detail"][0]["type"].lower()

def test_cache_integration():
    """Test IT-013: Cache integration on repeated geocode"""
    with patch('Backend.geocoding.services.redis_cache.RedisCache.get') as mock_cache:
        mock_cache.side_effect = [None, {"cached": True}]  # Cache miss, then hit
        
        # First call
        resp1 = client.post("/api/v1/geocode", json={"locations": ["Islamabad"]})
        assert resp1.status_code == 200
        
        # Second call (should be faster due to cache)
        resp2 = client.post("/api/v1/geocode", json={"locations": ["Islamabad"]})
        assert resp2.status_code == 200
```

**Execution Command:**
```bash
cd Backend
pytest tests/integration/ -v -k "not geocod" --tb=short
```

---

## Part 3: System Testing (8 Key Test Cases)

**File Location:** Entire stack (Frontend + Backend)  
**Testing Frameworks:** Cypress (functional), k6 (load), OWASP ZAP (security)  
**Mocking Strategy:** Full mock backend API, mock Mapbox GL JS, no external Gemini calls

### 3.1 Functional UI Tests (6 cases)

Use Cypress for automated browser testing:

```javascript
// cypress/e2e/dashboard.cy.ts
describe('REACH Dashboard', () => {
  beforeEach(() => {
    // Mock API responses
    cy.intercept('GET', '/api/v1/alerts*', { fixture: 'alerts.json' })
    cy.intercept('GET', '/api/v1/geometry*', { fixture: 'geometry.json' })
    cy.visit('/')
  })

  it('ST-001: User loads dashboard and map renders alerts', () => {
    cy.get('[data-testid="map-container"]').should('be.visible')
    cy.get('[data-testid="alert-list"]').children().should('have.length.greaterThan', 0)
  })

  it('ST-002: Filter by disaster type', () => {
    cy.get('[data-testid="filter-category"]').click()
    cy.contains('Flood').click()
    cy.get('[data-testid="alert-list"] li').each(($el) => {
      expect($el.text()).to.include('Flood')
    })
  })

  it('ST-003: Filter by severity', () => {
    cy.get('[data-testid="filter-severity"]').select('Severe')
    cy.get('[data-testid="alert-list"] li').each(($el) => {
      expect(['Severe', 'Extreme']).to.include(
        $el.find('[data-severity]').attr('data-severity')
      )
    })
  })

  it('ST-004: Search by location', () => {
    cy.get('[data-testid="search-input"]').type('Lahore')
    cy.contains('Search').click()
    cy.get('[data-testid="map-container"]').should('be.visible')
    cy.get('[data-testid="alert-list"] li').first().should('contain', 'Lahore')
  })

  it('ST-005: Date range filter', () => {
    cy.get('[data-testid="date-start"]').type('2026-04-01')
    cy.get('[data-testid="date-end"]').type('2026-05-05')
    cy.contains('Apply').click()
    // Verify filtered results
  })

  it('ST-006: View alert detail card', () => {
    cy.get('[data-testid="alert-item"]').first().click()
    cy.get('[data-testid="detail-panel"]').should('be.visible')
    cy.get('[data-testid="alert-title"]').should('not.be.empty')
    cy.get('[data-testid="alert-severity"]').should('not.be.empty')
  })
})
```

### 3.2 Performance Test (1 case)

Use k6 for load testing:

```javascript
// tests/performance/load.js (k6)
import http from 'k6/http'
import { check, sleep } from 'k6'

export const options = {
  stages: [
    { duration: '30s', target: 20 },   // Ramp up
    { duration: '1m30s', target: 100 }, // Stay at 100 VUs
    { duration: '30s', target: 0 },     // Ramp down
  ],
}

export default function () {
  // ST-007: Initial load time target
  let res = http.get('http://localhost:3000/')
  check(res, {
    'page loaded': (r) => r.status === 200,
    'load time < 3s': (r) => r.timings.duration < 3000,
  })

  // ST-008: API under concurrent load
  res = http.get('http://localhost:8000/api/v1/alerts?limit=50')
  check(res, {
    'api status 200': (r) => r.status === 200,
    'api response < 2s': (r) => r.timings.duration < 2000,
  })

  sleep(1)
}
```

**Execution:**
```bash
# Terminal 1: Start mock backend + frontend
npm run dev  # Frontend on :3000
python -m uvicorn Backend.app:app --port 8000  # Backend on :8000

# Terminal 2: Run k6 test
k6 run tests/performance/load.js
```

### 3.3 Security Test (1 case)

Use OWASP ZAP for baseline scan:

```bash
# ST-009: Baseline vulnerability scan
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t http://localhost:3000 \
  -r zap-report.html
# Check for High/Critical findings - none allowed
# Medium findings logged for review
```

---

## Part 4: Mocking Strategy

### 4.1 LLM API Mocking (Gemini Flash)

**File:** `Backend/processing_engine/processor_utils/llm_client.py`

Mock at the request level:
```python
@pytest.fixture
def mock_gemini_api():
    """Mock all Gemini API calls"""
    responses = {
        "alert_type": "FLOOD",
        "severity": "EXTREME",
        "location_mentions": ["Sindh"],
        "description": "Heavy rainfall"
    }
    with patch('google.generativeai.GenerativeModel.generate_content') as mock:
        mock.return_value.text = json.dumps(responses)
        yield mock
```

### 4.2 Database Mocking

**File:** `Backend/geocoding/tests/conftest.py`

```python
@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    with patch('Backend.geocoding.repositories.places_repository.supabase') as mock:
        mock.table.return_value.select.return_value.execute.return_value = {
            "data": [{"id": 1, "name": "Islamabad", "place_id": 100}]
        }
        yield mock

@pytest.fixture
def mock_redis():
    """Mock Redis cache"""
    with patch('Backend.geocoding.services.redis_cache.redis.Redis') as mock:
        mock.get.return_value = None  # Cache miss
        mock.set.return_value = True
        yield mock
```

### 4.3 Document Fetch Mocking

**File:** `Backend/processing_engine/tests/test_doc_utils.py`

```python
@pytest.fixture
def mock_requests():
    """Mock HTTP requests"""
    with patch('requests.get') as mock:
        mock.return_value.status_code = 200
        mock.return_value.content = b'PDF_MOCK_BYTES'
        yield mock
```

---

## Part 5: Test Execution Plan

### Phase 1: Setup (1 hour)
- [ ] Create `Backend/processing_engine/tests/` directory
- [ ] Create `Backend/tests/integration/` directory
- [ ] Create `Frontend/src/test/` directory with Jest setup
- [ ] Create `cypress/e2e/` directory with Cypress config
- [ ] Install test dependencies: `pytest`, `jest`, `cypress`, `k6`

### Phase 2: Backend Unit Tests (2 hours)
```bash
cd Backend
pytest processing_engine/tests/ -v --cov=processing_engine
# Expected: 10/10 tests pass, >80% coverage
```

### Phase 3: Frontend Unit Tests (2 hours)
```bash
cd Frontend
npm test -- --coverage
# Expected: 10/10 tests pass, >80% coverage
```

### Phase 4: Integration Tests (1 hour)
```bash
cd Backend
pytest tests/integration/ -v --tb=short
# Expected: 5/5 tests pass
```

### Phase 5: System Tests (2 hours)
```bash
# Terminal 1
npm run dev
python -m uvicorn Backend.app:app --port 8000

# Terminal 2
npx cypress run --e2e
k6 run tests/performance/load.js
# OWASP ZAP scan
```

---

## Part 6: Safety & Risk Mitigation

### ✅ Safe Practices
- **No production data touched**: All mocks isolate external services
- **No rate-limit violations**: LLM API is fully mocked
- **No credential exposure**: Test `.env` uses dummy values
- **Rollback ready**: Tests are read-only until assertions

### ⚠️ Risk Mitigation
| Risk | Mitigation |
|---|---|
| LLM API quota exceeded | ✅ 100% mocked in tests |
| Database locks/deadlocks | ✅ No DB writes; read-only or mocked |
| Mapbox rendering failures | ✅ Mocked in Cypress; no rendering during test |
| Redis connection failures | ✅ Redis mocked in unit/integration tests |
| External service rate limits | ✅ All external calls mocked |

---

## Part 7: Test File Structure

```
Tests/
├── plan.md (this file)
├── Backend/
│   ├── processing_engine/
│   │   ├── __init__.py
│   │   ├── conftest.py (fixtures)
│   │   ├── test_doc_utils.py (UT-M2-001 to 006)
│   │   ├── test_llm_client.py (UT-M2-007, 008)
│   │   └── test_pipeline_processor.py (UT-M2-009, 010)
│   └── tests/
│       ├── integration/
│       │   └── test_validation_error_handling.py (IT-008, 009, 012, 013, 014)
│       └── conftest.py (shared fixtures)
├── Frontend/
│   ├── src/
│   │   └── test/
│   │       ├── setup.ts (Jest configuration)
│   │       ├── LRUCache.test.ts (UT-M3-001 to 003)
│   │       ├── alertsService.test.ts (UT-M3-004, 005)
│   │       ├── useAlerts.test.ts (UT-M3-006, 007)
│   │       └── components.test.ts (UT-M3-008 to 010)
│   └── cypress/
│       ├── e2e/
│       │   └── dashboard.cy.ts (ST-001 to 006)
│       └── cypress.config.ts
├── tests/
│   ├── performance/
│   │   └── load.js (k6, ST-007, 008)
│   └── security/
│       └── owasp.sh (ST-009)
```

---

## Part 8: Success Criteria

| Phase | Metric | Target | Acceptance |
|---|---|---|---|
| Backend Unit | Coverage | >80% | All 10 tests pass, coverage report generated |
| Frontend Unit | Coverage | >80% | All 10 tests pass, coverage report generated |
| Integration | Pass Rate | 100% | All 5 tests pass without mocking issues |
| System Functional | Pass Rate | 100% | All 6 Cypress tests pass |
| System Performance | Load Test | <2s p95 latency, <1% error | k6 report shows acceptable thresholds |
| System Security | Vulnerabilities | No High/Critical | OWASP ZAP report reviewed |

---

## Part 9: Dependencies to Install

```bash
# Backend
pip install pytest pytest-cov pytest-mock pytest-asyncio httpx

# Frontend
npm install --save-dev jest @testing-library/react @testing-library/jest-dom jest-mock-extended

# System tests
npm install --save-dev cypress
brew install k6  # macOS
# or https://github.com/grafana/k6/releases for Windows

# Security
docker pull owasp/zap2docker-stable
```

---

## Appendix: Quick Reference

**Run all unit tests:**
```bash
pytest Backend/processing_engine/tests/ -v
npm test Frontend/
```

**Run all integration tests:**
```bash
pytest Backend/tests/integration/ -v
```

**Run all system tests:**
```bash
npx cypress run --e2e
k6 run tests/performance/load.js
```

**Generate coverage reports:**
```bash
pytest --cov --cov-report=html  # Creates htmlcov/index.html
npm test -- --coverage  # Creates coverage/lcov-report/index.html
```

---

**Last Updated:** May 5, 2026  
**Next Review:** After Phase 1 setup completion
