import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // Fast ramp to 50 VUs
    { duration: '3m', target: 100 },   // 3 minutes of unthrottled 100 VUs
    { duration: '30s', target: 0 },    // Cool down
  ],
  thresholds: {
    http_req_failed: ['rate<0.10'],    // Track failure rate under extreme stress
  },
};

const BASE_URL = __ENV.BASE || __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // 1. Uncached Product Search (forces DB query)
  const resSearch = http.get(`${BASE_URL}/products/search/by-name?q=test&limit=20`, {
    tags: { endpoint: 'search' },
  });
  check(resSearch, { 'search status 200': (r) => r.status === 200 });

  // 2. Uncached Inventory/Product Join
  const resProd = http.get(`${BASE_URL}/products/available?limit=20`, {
    tags: { endpoint: 'available_products' },
  });
  check(resProd, { 'products status 200': (r) => r.status === 200 });

  // Zero sleep = 100 VUs generate maximum possible requests/sec
}