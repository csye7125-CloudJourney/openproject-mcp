import http from 'k6/http';
import { check } from 'k6';

// hello world. hits /healthz to confirm the harness works.
// run: k6 run load/healthz.js

export const options = {
  vus: 1,
  duration: '10s',
};

export default function () {
  const res = http.get('http://localhost:8080/healthz');
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
}
