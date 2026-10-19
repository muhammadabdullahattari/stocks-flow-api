import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 },   // Warm-up to 20 VUs
    { duration: '1m', target: 50 },    // Ramp to 50 VUs
    { duration: '2m', target: 100 },   // Peak load test with 100 VUs
    { duration: '30s', target: 0 },    // Graceful ramp-down
  ],
  thresholds: {
    http_req_failed: ['rate<0.02'],     // Under 2% errors tolerated
    http_req_duration: ['p(95)<800'],   // 95% of requests under 800ms
  },
};

const BASE_URL = __ENV.BASE || __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // 1. Categories endpoint
  const resCat = http.get(`${BASE_URL}/categories`, { tags: { endpoint: 'categories' } });
  check(resCat, { 'categories status is 200': (res) => res.status === 200 });
  sleep(1);   // Think time

  // 2. Available products endpoint
  const resProd = http.get(`${BASE_URL}/products/available`, { tags: { endpoint: 'available_products' } });
  check(resProd, { 'products status is 200': (res) => res.status === 200 });
  sleep(1);
}