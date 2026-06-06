# observability wrapper chart

one helm release that lands the whole stack for the openproject-mcp
platform - prometheus + grafana + alertmanager (via kube-prometheus-stack),
EFK (elasticsearch + kibana + fluent-bit), OpenTelemetry collector,
and Jaeger backed by the same elasticsearch.

## why a wrapper

each upstream chart can be released on its own but the platform wants
a single `helm upgrade` to ship coordinated changes - bumping the
collector pipeline and a grafana dashboard in the same PR. the wrapper
also owns the cross-cutting bits the subcharts can't template
(alertmanager routes referencing shared secrets, otel pipeline pointing
at this release's jaeger + prom, grafana dashboards as ConfigMaps).

## components

| component             | purpose                                  | subchart                |
|-----------------------|------------------------------------------|-------------------------|
| prometheus            | metrics scrape + storage                 | kube-prometheus-stack   |
| alertmanager          | route alerts to pagerduty + slack        | kube-prometheus-stack   |
| grafana               | dashboards + visualization               | kube-prometheus-stack   |
| node + ksm exporters  | host + cluster object metrics            | kube-prometheus-stack   |
| elasticsearch         | log + trace storage backend              | elasticsearch (elastic) |
| kibana                | log search UI                            | kibana (elastic)        |
| fluent-bit            | log shipping daemonset                   | fluent-bit (fluent)     |
| otel-collector        | OTLP gateway, fan-out traces + metrics   | opentelemetry-collector |
| jaeger                | distributed tracing UI + storage         | jaeger                  |

## install

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add elastic https://helm.elastic.co
helm repo add fluent https://fluent.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm repo update

helm dependency update helm/observability/
kubectl create ns observability --dry-run=client -o yaml | kubectl apply -f -

# dev
helm install obs ./helm/observability -n observability \
  -f helm/observability/values.yaml

# prod
helm install obs ./helm/observability -n observability \
  -f helm/observability/values.yaml \
  -f helm/observability/values-prod.yaml
```

## verify

```bash
helm lint helm/observability/ -f helm/observability/values.yaml
helm template helm/observability/ | head -50
kubectl -n observability get pods
kubectl -n observability port-forward svc/obs-grafana 3000:80
```

## cross-namespace scraping

The Prometheus CR rendered by kube-prometheus-stack ships with two
defaults that bite anyone who points ServiceMonitors at it from another
namespace. `serviceMonitorSelector` is pinned to `release: <name>` and
`serviceMonitorNamespaceSelector` is empty, which the operator reads as
"only this namespace" rather than "anywhere". Same story for
PodMonitor and PrometheusRule.

The trick the upstream chart exposes is the
`*SelectorNilUsesHelmValues` knob. When that is true (the default) an
empty selector silently expands to the helm release label match, and
SMs without that label go unscraped. Flip it to false and an empty
selector behaves like "select everything". This wrapper pins all three
to false and supplies explicit `{}` selectors plus `{}` namespace
selectors, so ServiceMonitors created in `openproject`,
`openproject-mcp`, `kafka`, `istio-system`, and anything else get
scraped on first install with no follow-up `kubectl patch prometheus`.

Concretely, the bits in `values.yaml` under
`kube-prometheus-stack.prometheus.prometheusSpec`:

```
serviceMonitorSelectorNilUsesHelmValues: false
serviceMonitorSelector: {}
serviceMonitorNamespaceSelector: {}
podMonitorSelectorNilUsesHelmValues: false
podMonitorSelector: {}
podMonitorNamespaceSelector: {}
ruleSelectorNilUsesHelmValues: false
ruleSelector: {}
ruleNamespaceSelector: {}
```

Sanity check after a render:

```bash
helm template observability helm/observability/ --include-crds \
  | awk '/^kind: Prometheus$/{flag=1} flag; /^---/{flag=0}' \
  | grep -E "ServiceMonitor|PodMonitor|Rule|NamespaceSelector"
```

The selectors should come out as `{}` (or `null`, which yaml emits as
the same thing) on every line.

## dashboards

four templates auto-loaded via the grafana sidecar (ConfigMaps labelled
`grafana_dashboard=1` are picked up cluster-wide):

- `dashboard-cluster-overview` - node CPU/mem, pods by phase, PV usage
- `dashboard-mcp-tool-latency` - p50/p95 + call rate + error rate per
  MCP tool, templated on `tool` label from `mcp_tool_calls_total`
- `dashboard-kafka-lag` - consumer group lag, topic message rate,
  under-replicated partitions
- `dashboard-istio-request-rate` - request rate, 5xx rate, p99 latency
  by destination service

## alerts

`AlertmanagerConfig` CRD in `templates/alertmanager-config.yaml`:

- `severity: critical` -> PagerDuty (continue: true so slack also fires)
- `severity: warning` -> ops-slack
- `Watchdog` -> blackhole (heartbeat, not a real alert)
- inhibit: critical suppresses warning on same alertname+namespace

Routing keys + slack webhook expected in `alertmanager-pagerduty` and
`alertmanager-slack` secrets, both managed by ExternalSecrets.

## otel pipeline

defined in `templates/otel-collector-config.yaml` (rendered as
ConfigMap, mounted by the subchart deployment):

```
receivers:  otlp (grpc 4317 + http 4318) + prometheus scrape of mcp app
processors: memory_limiter, k8sattributes, batch
exporters:  otlp/jaeger (traces), prometheusremotewrite (metrics),
            debug (logs - placeholder, real log shipping via fluent-bit)
```

## jaeger

production strategy: agent daemonset + 2 collector replicas + 1 query
replica, backed by the same ES cluster. sampling defaults to 10% with
`POST /webhooks/openproject` always-on and probes (healthz/readyz)
always-off. defined in `templates/jaeger-instance.yaml`.

## access

all UIs run as ClusterIP behind the Tailscale operator - no public
ingress. set up a Tailscale service annotation on the grafana / kibana
/ jaeger-query Services after install. see `docs/observability.md`
for the full list of tailnet hostnames.
