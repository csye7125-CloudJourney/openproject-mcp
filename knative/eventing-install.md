# knative eventing install

eventing layer turns kafka topics into CloudEvent streams that
Triggers can subscribe to, fanning into Knative Services. lets us
build event-driven MCP variants (e.g. a "process webhook" ksvc that
scales to zero when the topic is idle).

## prereqs

- knative-operator already installed (see `install.md`)
- KnativeServing CR Ready
- MSK cluster reachable from the EKS cluster
- topic `openproject.events.raw` exists with sufficient partitions

## install knative eventing

```bash
KNATIVE_VERSION=v1.15.4

kubectl create ns knative-eventing --dry-run=client -o yaml | kubectl apply -f -

cat <<'EOF' | kubectl apply -f -
apiVersion: operator.knative.dev/v1beta1
kind: KnativeEventing
metadata:
  name: knative-eventing
  namespace: knative-eventing
spec:
  version: 1.15.4
  config:
    config-features:
      kreference-group: "enabled"
      new-trigger-filters: "enabled"
EOF

kubectl wait --for=condition=Ready knativeeventing/knative-eventing \
  -n knative-eventing --timeout=300s
```

## install kafka source controller

KafkaSource is the kafka-specific CRD that bridges a topic into the
eventing broker. it ships as a separate kafka extension - not bundled
with the core eventing operator.

```bash
kubectl apply -f https://github.com/knative-extensions/eventing-kafka-broker/releases/download/knative-v1.15.4/eventing-kafka-controller.yaml
kubectl apply -f https://github.com/knative-extensions/eventing-kafka-broker/releases/download/knative-v1.15.4/eventing-kafka-source.yaml

kubectl wait --for=condition=Available deployment/kafka-controller \
  -n knative-eventing --timeout=180s
kubectl wait --for=condition=Available deployment/kafka-source-dispatcher \
  -n knative-eventing --timeout=180s
```

## kafka credentials

MSK uses IAM auth. KafkaSource doesn't speak IAM directly so we proxy
through a Secret with SASL/SCRAM creds OR use a plain bootstrap from
inside the VPC. Two paths:

### path A - msk plain text inside vpc (cheap)

Set MSK config `allow.everyone.if.no.acl.found=false` + create an SCRAM
user via `aws kafka batch-associate-scram-secret`, then store creds
in a Secret:

```bash
kubectl create secret generic msk-scram \
  --from-literal=username=mcp-knative \
  --from-literal=password=<from secretsmanager> \
  -n openproject-mcp
```

### path B - IAM via sidecar (preferred long-term)

Run the MSK IAM SASL signer as a sidecar in the dispatcher pod -
documented in `apps/mcp-server/docs/kafka-replay.md` for the python
consumer; the same pattern translates to KafkaSource via a custom
KafkaSourceSpec.auth config block once
https://github.com/knative-extensions/eventing-kafka-broker/issues/2987
is resolved.

For now KafkaSource here uses SASL/SCRAM (path A).

## verify

```bash
kubectl get crd | grep eventing
# expect: brokers, triggers, channels, subscriptions, kafkasources, kafkachannels

kubectl get pods -n knative-eventing
# expect: eventing-controller, eventing-webhook, kafka-controller,
#         kafka-source-dispatcher, mt-broker-controller all Running
```

## next

apply `eventing/kafka-source.yaml` + `eventing/trigger.yaml` to wire
the `openproject.events.raw` topic into a Knative Service via Trigger.
