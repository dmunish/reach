/**
 * Performance load test using k6
 * Tests system under concurrent load during hypothetical disaster event
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 },   // Ramp up to 20 VUs
    { duration: '1m30s', target: 100 }, // Increase to 100 VUs
    { duration: '20s', target: 200 },  // Spike to 200 VUs
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<3000'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  // ST-007: Initial load time target
  const homepage = http.get('http://localhost:5173/');
  check(homepage, {
    'homepage status is 200': (r) => r.status === 200,
    'homepage load time < 3s': (r) => r.timings.duration < 3000,
  });

  sleep(1);

  // ST-008: API under concurrent load
  const getAlerts = http.get('http://localhost:8000/api/v1/alerts?limit=50');
  check(getAlerts, {
    'alerts API status is 200': (r) => r.status === 200,
    'alerts API response < 2s': (r) => r.timings.duration < 2000,
    'alerts response has data': (r) => r.body.includes('alert'),
  });

  sleep(2);

  // Filter test
  const filteredAlerts = http.get(
    'http://localhost:8000/api/v1/alerts?alert_type=FLOOD&limit=50'
  );
  check(filteredAlerts, {
    'filtered alerts status is 200': (r) => r.status === 200,
    'filtered API response < 2s': (r) => r.timings.duration < 2000,
  });

  sleep(1);

  // Search test
  const searchResults = http.get(
    'http://localhost:8000/api/v1/alerts?location=Karachi&limit=50'
  );
  check(searchResults, {
    'search status is 200': (r) => r.status === 200,
    'search response < 2s': (r) => r.timings.duration < 2000,
  });

  sleep(1);

  // Geometry fetch test
  const geometry = http.get('http://localhost:8000/api/v1/geometry?alert_id=1');
  check(geometry, {
    'geometry fetch status is 200': (r) => r.status === 200,
    'geometry fetch < 1.5s': (r) => r.timings.duration < 1500,
  });

  sleep(2);
}

/**
 * To run this test:
 * 
 * 1. Ensure backend and frontend are running:
 *    - Frontend: npm run dev (on port 3000)
 *    - Backend: python -m uvicorn Backend.app:app --port 8000
 * 
 * 2. Run k6 test:
 *    k6 run tests/performance/load.js
 * 
 * Expected results:
 * - p95 API latency: < 2000ms
 * - p99 API latency: < 3000ms
 * - Error rate: < 1%
 * - Homepage load: < 3000ms
 */
