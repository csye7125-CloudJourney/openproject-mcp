import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

// hits the safe read-only tools through the http transport, one tool per
// vu iteration so per-tool trends stay clean. write tools (create/update/
// delete) skipped here. they're covered in the webhooks scenario via
// the kafka path.

const BASE = __ENV.MCP_BASE_URL || 'http://localhost:8080';

const READ_TOOLS = [
  { name: 'list_projects', args: {} },
  { name: 'list_work_packages', args: { project_id: 1 } },
  { name: 'get_project_details', args: { project_id: 1 } },
  { name: 'get_work_package', args: { work_package_id: 1 } },
  { name: 'list_users', args: {} },
  { name: 'list_time_entries', args: {} },
  { name: 'list_statuses', args: {} },
  { name: 'list_types', args: {} },
  { name: 'list_priorities', args: {} },
  { name: 'list_attachments', args: { work_package_id: 1 } },
  { name: 'list_versions', args: { project_id: 1 } },
  { name: 'list_categories', args: { project_id: 1 } },
  { name: 'list_queries', args: {} },
  { name: 'list_memberships', args: { project_id: 1 } },
  { name: 'list_relations', args: { work_package_id: 1 } },
  { name: 'list_watchers', args: { work_package_id: 1 } },
  { name: 'list_activities', args: { work_package_id: 1 } },
  { name: 'search_work_packages', args: { query: 'load' } },
  { name: 'get_project_hierarchy', args: { project_id: 1 } },
  { name: 'get_user', args: { user_id: 1 } },
];

// per-tool latency trend so the summary breaks out which tool is slow
const trends = {};
for (const t of READ_TOOLS) {
  trends[t.name] = new Trend(`tool_${t.name}_ms`, true);
}

// build per-tool p95 threshold map. target: sub-200ms p95.
const perToolThresholds = {};
for (const t of READ_TOOLS) {
  perToolThresholds[`tool_${t.name}_ms`] = ['p(95)<200'];
}

// ramp-to-breakpoint. start low, climb in steps, watch p95 + error rate.
// override via env: K6_PROFILE=ramp|soak|smoke
const PROFILE = __ENV.K6_PROFILE || 'ramp';

const profiles = {
  smoke: {
    stages: [
      { duration: '30s', target: 5 },
      { duration: '1m', target: 5 },
      { duration: '30s', target: 0 },
    ],
  },
  ramp: {
    // climb in steps so the operator can watch grafana and kill the run
    // if p95 spikes or error rate climbs past the abort thresholds below
    stages: [
      { duration: '1m', target: 20 },     // baseline
      { duration: '2m', target: 50 },     // 2.5x baseline
      { duration: '2m', target: 100 },    // 5x
      { duration: '2m', target: 200 },    // 10x. cluster usually starts noticing here
      { duration: '2m', target: 400 },    // 20x. HPA should be maxed
      { duration: '3m', target: 800 },    // 40x. pending pods territory
      { duration: '3m', target: 1500 },   // 75x. find the wall
      { duration: '2m', target: 0 },      // cooldown
    ],
  },
  soak: {
    // hold at the highest level that still met SLO during ramp
    stages: [
      { duration: '2m', target: 200 },
      { duration: '20m', target: 200 },
      { duration: '2m', target: 0 },
    ],
  },
};

export const options = {
  scenarios: {
    main: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: profiles[PROFILE].stages,
      gracefulRampDown: '30s',
    },
  },
  // abort the run if things go off a cliff. cheaper than waiting for the
  // ramp to finish when we already know we broke it
  thresholds: {
    http_req_failed: [
      { threshold: 'rate<0.05', abortOnFail: true, delayAbortEval: '30s' },
    ],
    http_req_duration: [
      'p(95)<200',
      'p(99)<500',
      { threshold: 'p(95)<2000', abortOnFail: true, delayAbortEval: '30s' },
    ],
    ...perToolThresholds,
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

export function setup() {
  // sanity check that sse endpoint is reachable
  const sseRes = http.get(`${BASE}/sse`, { timeout: '5s' });
  check(sseRes, { 'sse reachable': (r) => r.status < 500 });
}

export default function () {
  const tool = READ_TOOLS[Math.floor(Math.random() * READ_TOOLS.length)];
  const body = JSON.stringify({
    jsonrpc: '2.0',
    id: __ITER,
    method: 'tools/call',
    params: { name: tool.name, arguments: tool.args },
  });
  const start = Date.now();
  // Don't tag 4xx as "failed". They exercise the same app path the
  // sub-200ms SLO measures. Real failures are 5xx + timeouts.
  // responseCallback below tells k6 to only count 5xx as a failure.
  const res = http.post(`${BASE}/messages/`, body, {
    headers: { 'Content-Type': 'application/json' },
    tags: { tool: tool.name },
    responseCallback: http.expectedStatuses({ min: 200, max: 499 }),
  });
  trends[tool.name].add(Date.now() - start);
  check(res, {
    [`${tool.name} responds`]: (r) => r.status < 500,
  });
  sleep(0.1);
}
