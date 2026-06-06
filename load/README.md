# load

k6 load tests for the openproject-mcp server.

Same scripts run in two places. Local docker-compose brings up kafka +
mcp + a k6 runner for fast feedback (kafka is single-broker PLAINTEXT
there). The EKS path uses `k6-eks.yaml` and the
[k6-operator](https://github.com/grafana/k6-operator) inside the cluster,
so traffic goes through the real Istio mTLS path and writes to MSK over
IAM auth. Reports go to S3.

## Scripts

| File | What it does |
| --- | --- |
| `healthz.js` | smoke. 1 VU, 10s, hits `/healthz` |
| `webhooks.js` | hmac-signed OP webhooks. ramps 0->1000 VUs over 5m, holds 10m, ramps down 2m |
| `mcp_tools.js` | opens SSE + calls 20 read-only tools. per-tool `p(95)<200ms` threshold |
| `lib/hmac.js` | sha256 hmac signing helper (matches `webhooks/ingest.py`) |
| `lib/payloads.js` | randomized synthetic openproject event generator |

## Local run

```bash
cd load
docker compose up -d kafka mcp
# wait ~10s for mcp to start
docker compose run --rm k6 run /scripts/healthz.js
docker compose run --rm k6 run /scripts/mcp_tools.js
docker compose run --rm k6 run /scripts/webhooks.js
```

Reports land in `./reports/` (gitignored). Swap scripts with
`docker compose run --rm k6 run /scripts/<script>.js`.

## EKS run

Prereqs: `kubectl` context points at the prod cluster, k6-operator is
installed (`kubectl apply -f https://github.com/grafana/k6-operator/releases/latest/download/bundle.yaml`),
and the `webhook-hmac` secret + `k6-s3-uploader` IRSA SA exist in the `load`
namespace.

```bash
kubectl create namespace load --dry-run=client -o yaml | kubectl apply -f -
kubectl -n load create configmap k6-scripts \
  --from-file=webhooks.js \
  --from-file=mcp_tools.js \
  --from-file=lib/hmac.js \
  --from-file=lib/payloads.js \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f k6-eks.yaml
kubectl -n load get testrun -w

# once TestRun status is Finished, kick the upload job:
kubectl -n load create job --from=cronjob/k6-reports-upload k6-upload-$(date +%s)
```

## Reports

| Location | Source |
| --- | --- |
| `load/reports/local/` | local docker-compose runs (gitignored) |
| `load/reports/eks/` | mirrored from S3 after EKS runs (gitignored) |
| `s3://openproject-mcp-load-reports/` | EKS run output, uploaded by post-run sidecar Job |

Headline numbers come from the EKS run. Pull JSON from S3 and eyeball
the per-tool Trend metrics for p50/p95/p99.

## Thresholds

Both `mcp_tools.js` and `webhooks.js` fail the run if:

- `http_req_failed` rate >= 1%
- `http_req_duration` p95 >= 200ms or p99 >= 500ms
- per-tool p95 >= 200ms (`mcp_tools.js` only)

CI gates on the exit code. If it fails, fix latency before merging.
