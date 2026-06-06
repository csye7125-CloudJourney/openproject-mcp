# observability

stack layout, access notes, and the PromQL/KQL queries I keep
re-typing. paired with `helm/observability/`.

## stack at a glance

```
  application pods (mcp-server)
        |
        +-- prometheus client metrics on :8000/metrics
        |       |
        |       +-- prometheus scrapes via ServiceMonitor
        |
        +-- OTLP traces -> otel-collector:4317
        |       |
        |       +-- otel-collector -> jaeger-collector:4317
        |       +-- otel-collector -> prometheus remote_write
        |
        +-- stdout logs -> fluent-bit daemonset -> elasticsearch -> kibana

  alertmanager <- prometheus rules (kube-prometheus-stack)
       |
       +-- pagerduty (critical)
       +-- slack #ops-alerts (warning)
```

## components

| component       | namespace      | port  | purpose                    |
|-----------------|----------------|-------|----------------------------|
| prometheus      | observability  | 9090  | metrics store              |
| grafana         | observability  | 80    | dashboard UI               |
| alertmanager    | observability  | 9093  | alert routing              |
| elasticsearch   | observability  | 9200  | logs + trace storage       |
| kibana          | observability  | 5601  | log search UI              |
| fluent-bit      | observability  | 2020  | log shipper (DaemonSet)    |
| otel-collector  | observability  | 4317  | OTLP gateway               |
| jaeger-query    | observability  | 16686 | trace search UI            |

## access (all via Tailscale)

no public ingress. install the Tailscale Operator (see
`tailscale/`), annotate the relevant Services, then dial the tailnet
hostnames.

| UI         | tailnet hostname                | local port-forward fallback                  |
|------------|---------------------------------|----------------------------------------------|
| grafana    | https://grafana.tailnet.ts.net  | `kubectl -n observability port-forward svc/obs-grafana 3000:80` |
| kibana     | https://kibana.tailnet.ts.net   | `kubectl -n observability port-forward svc/obs-kibana 5601:5601` |
| jaeger     | https://jaeger.tailnet.ts.net   | `kubectl -n observability port-forward svc/obs-jaeger-query 16686:16686` |
| prometheus | https://prom.tailnet.ts.net     | `kubectl -n observability port-forward svc/obs-kube-prometheus-stack-prometheus 9090:9090` |
| alertman   | https://alerts.tailnet.ts.net   | `kubectl -n observability port-forward svc/obs-kube-prometheus-stack-alertmanager 9093:9093` |

## example queries

### prometheus / grafana explore

```promql
# top 10 slowest tool calls (p95)
topk(10, histogram_quantile(0.95,
  sum by (tool, le) (rate(mcp_tool_latency_seconds_bucket[5m]))))

# error rate by tool
sum by (tool) (rate(mcp_tool_calls_total{status="error"}[5m]))
  / sum by (tool) (rate(mcp_tool_calls_total[5m]))

# webhook ingest rate vs replay consumer lag
sum(rate(mcp_webhook_events_total[1m]))
kafka_consumergroup_lag{group="mcp-replay"}

# istio 5xx rate per destination
sum by (destination_service_name)
  (rate(istio_requests_total{response_code=~"5.."}[5m]))
```

### kibana KQL

```
kubernetes.namespace_name : "openproject-mcp"
  and log : "error"
  and not log : "context canceled"

kubernetes.pod_name : "mcp-server-*"
  and "@timestamp" > now-15m
  and log : "kafka"
```

### jaeger trace search

- service: `openproject-mcp`
- operation: `POST /webhooks/openproject`
- tags: `http.status_code=500`
- min duration: `200ms`

## dashboards

four ConfigMap-defined dashboards live in
`helm/observability/templates/grafana-dashboards.yaml`:

1. **Cluster Overview** (`mcp-cluster-overview`) - node CPU + memory,
   pods by phase, PVC usage
2. **MCP Tool Latency** (`mcp-tool-latency`) - p50 + p95 + call rate +
   error rate, templated on `tool` label
3. **Kafka Consumer Lag** (`mcp-kafka-lag`) - consumer group lag,
   topic message rate, URP count
4. **Istio Request Rate** (`mcp-istio-rate`) - per-destination request
   + 5xx rate + p99 duration

To add another, drop a new `apiVersion: v1` / `kind: ConfigMap` block
into that template with label `grafana_dashboard: "1"`. The grafana
sidecar polls every 30s and reloads.

## alerts

defined upstream in `helm/openproject-mcp/templates/prometheusrule.yaml`
(the application chart) - the observability chart only owns the
routing config:

| alert              | severity | source            |
|--------------------|----------|-------------------|
| HighLatencyP95     | warning  | mcp PrometheusRule|
| ErrorRateHigh      | critical | mcp PrometheusRule|
| PodMemoryHigh      | warning  | mcp PrometheusRule|
| NoReadyPods        | critical | mcp PrometheusRule|
| KafkaConsumerLag   | warning  | kafka-exporter    |
| Watchdog           | none     | kube-prom-stack   |

## tracing

OTel SDK lives in `apps/mcp-server/src/openproject_mcp_server/tracing.py`.
gated by `OTEL_ENABLED=true`. exporter target controlled by
`OTEL_EXPORTER_OTLP_ENDPOINT`, default
`http://otel-collector.observability.svc.cluster.local:4317`.

Auto-instruments starlette + httpx so every inbound HTTP request +
every outbound httpx call to OpenProject is a span. Tool calls inside
`server.py` get manual spans named `tool.<name>`.

## logs

fluent-bit DaemonSet tails `/var/log/containers/*.log` + kubelet
systemd journal, ships to `elasticsearch-master:9200` with prefix
`mcp-logs-YYYY.MM.DD` (containers) and `host-logs-YYYY.MM.DD`
(kubelet). 14-day retention via the jaeger index cleaner is for
traces; log retention is handled by a separate ILM policy that lands
when ES `xpack.security.enabled: true` flips on in prod.

## what got wired

- prometheus + alertmanager via kube-prometheus-stack
- grafana via the same subchart
- EFK - elasticsearch + kibana + fluent-bit
- distributed tracing - jaeger + otel-collector + the app SDK
- istio telemetry feeds the same prom (request rate / 5xx / p99 by destination)
