import http from 'k6/http';
import { check } from 'k6';
import { sign } from './lib/hmac.js';
import { makeEvent } from './lib/payloads.js';

// ramps vus 0 -> 1000 over 5m, holds 10m, ramps down 2m.
// payload is randomized via makeEvent() so cache hits don't skew p95.
// TODO: tag tool=webhooks once we add a per-route trend

const BASE = __ENV.MCP_BASE_URL || 'http://localhost:8080';
const SECRET = __ENV.WEBHOOK_HMAC_SECRET || 'load-test-secret';

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '5m', target: 1000 },
        { duration: '10m', target: 1000 },
        { duration: '2m', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<200', 'p(99)<500'],
  },
};

export default function () {
  const body = JSON.stringify(makeEvent());
  const headers = {
    'Content-Type': 'application/json',
    'X-OpenProject-Signature': sign(body, SECRET),
  };
  const res = http.post(`${BASE}/webhooks/openproject`, body, { headers });
  check(res, {
    'status 2xx': (r) => r.status >= 200 && r.status < 300,
  });
}
