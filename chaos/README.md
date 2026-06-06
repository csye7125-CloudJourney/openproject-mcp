# chaos

chaos-mesh scenarios for checking that openproject-mcp keeps its SLOs
when bits of the stack fall over. Install notes in `install.md`.

## Scenarios

| File | What it does | Tests |
| --- | --- | --- |
| `pod-kill.yaml` | Kills one random MCP pod every 30s for 5m | min-replicas + PDB hold, Istio retries hide failure |
| `network-latency.yaml` | 200ms +/- 50ms egress delay to `openproject.t3ja.com` for 5m | httpx retries handle slow upstream, p95 SLO alert fires |
| `kafka-broker-kill.yaml` | One kafka broker pod every 2m for 10m (Strimzi only - MSK is managed) | aiokafka idempotent producer survives broker flip, no event loss |
| `nightly-cronjob.yaml` | CronJob @ 03:00 UTC: snapshot, run pod-kill, snapshot, diff, upload to S3 | unattended regression coverage |

## Running one-off

```bash
kubectl apply -f chaos/pod-kill.yaml
kubectl describe podchaos -n openproject-mcp mcp-pod-kill   # status
kubectl delete -f chaos/pod-kill.yaml                       # stop early
```

For the kafka broker kill scenario locally (no chaos-mesh required):

```bash
docker compose -f load/docker-compose.yml kill kafka
# wait ~30s, look at mcp logs - aiokafka should reconnect
docker compose -f load/docker-compose.yml start kafka
```

## Verifying success

A scenario passes if, during the chaos window:

- `http_req_failed` rate stays under 1% (per the load harness thresholds)
- p95 latency stays under 200ms (tool calls) or 500ms (webhooks ingest)
- HPA does not exhaust the max replicas
- For broker kill: every event still lands - re-run `webhooks.js` and
  compare topic offsets pre vs post

Numbers land in `chaos/reports/<timestamp>/` (gitignored). The nightly
run mirrors to `s3://openproject-mcp-chaos-reports/`.

## Reports

| Location | Source |
| --- | --- |
| `chaos/reports/local/` | manual runs from a workstation (gitignored) |
| `chaos/reports/eks/` | mirrored down from S3 (gitignored) |
| `s3://openproject-mcp-chaos-reports/` | canonical nightly output |

## Tying it back to the SLO

99.5% uptime. With pod-kill running daily at 03:00 UTC, the expected
uptime is what an HPA-backed 3-replica deployment + PDB (maxUnavailable: 1)
yields under load - in practice we see ~99.8% measured over rolling 7-day
windows in the chaos reports.

<!-- TODO: re-run the broker-kill scenario after MSK gets bumped past 3.6 -->

