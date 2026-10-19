import http from 'k6/http';
import { sleep, check } from 'k6';

// Staged ramp-up simulation for StockFlow API
export const options = {
  stages: [
    { duration: '30s', target: 20 },   // Warm-up to 20 VUs
    { duration: '1m', target: 50 },    // Ramp to 50 VUs
    { duration: '2m', target: 100 },   // Peak load test with 100 VUs
    { duration: '30s', target: 0 },    // Graceful ramp-down
  ],
  thresholds: {
    http_req_failed: ['rate<0.02'],     // Max 2% failure rate tolerated under peak load
    http_req_duration: ['p(95)<800'],   // 95% of requests completed under 800ms
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // 1. Test Categories Endpoint
  const resCat = http.get(`${BASE_URL}/categories`, {
    tags: { name: 'GetCategories' },
  });
  check(resCat, {
    'categories status is 200': (r) => r.status === 200,
  });

  // Human think time between requests (prevents unthrottled DDOS on connection pool)
  sleep(1);

  // 2. Test Available Products Endpoint
  const resProd = http.get(`${BASE_URL}/products/available`, {
    tags: { name: 'GetAvailableProducts' },
  });
  check(resProd, {
    'available products status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
