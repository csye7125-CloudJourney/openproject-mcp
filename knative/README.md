# knative

scale-to-zero + event-driven variants of the openproject-mcp server,
running on top of the EKS cluster.

## layout

```
knative/
  install.md             - knative-operator + KnativeServing install + istio pick
  service.yaml           - the scale-to-zero MCP Service (min=0 max=10)
  traffic-split-demo.yaml- 80/20 v1/v2 split + header-based steering
  eventing-install.md    - KnativeEventing + kafka source extension install
  eventing/
    kafka-source.yaml    - KafkaSource pulling openproject.events.raw from MSK
    trigger.yaml         - default Broker + Trigger routing to the ksvc + tap
  README.md              - this file
```

## install order

1. `install.md` - knative-operator + KnativeServing CR
2. `service.yaml` - apply once to seed `openproject-mcp-v1`
3. `eventing-install.md` - KnativeEventing + kafka extension
4. `eventing/kafka-source.yaml` + `eventing/trigger.yaml` - wire kafka
5. `traffic-split-demo.yaml` - only for canary rollouts

Knative CRDs are not installed locally in this dev box - the YAML
validates structurally via `python -c "yaml.safe_load_all(...)"`
but `kubectl apply --dry-run=client` will fail without the CRDs
present. Once the cluster is up, dry-run against the live cluster:

```bash
kubectl apply --dry-run=server -f knative/service.yaml \
  -f knative/traffic-split-demo.yaml \
  -f knative/eventing/
```

## scale-to-zero math

container concurrency = 20, target = 15. knative scales up when
average pending requests > 15 per pod. with 100 concurrent clients
that means 100/15 ~= 7 pods. max is 10 so the autoscaler caps at 10
and queues the rest.

cold start budget: ~2s for python interpreter + httpx client init.
not ideal for sub-second SLOs - use the regular `helm/openproject-mcp/`
deployment with min replicas if hot-path latency matters. knative
shines for the webhook ingest path where idle hours dominate.

## related

- `helm/openproject-mcp/` - the "always-warm" Deployment variant
- `helm/observability/` - prometheus + jaeger receive ksvc telemetry
- `apps/mcp-server/src/openproject_mcp_server/tracing.py` - emits spans
  from inside the ksvc to the otel-collector
