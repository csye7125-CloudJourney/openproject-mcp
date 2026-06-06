# knative serving install

knative serving = scale-to-zero + revision-based traffic split layer
sitting on top of vanilla k8s. used for the event-driven variants of
the MCP server where idle cost matters.

## prereqs

- EKS 1.30+
- kubectl context pointing at the cluster
- helm 3.x
- istio already installed - knative reuses istio for sidecars +
  ingress so we don't double up on service meshes

## install knative-operator

knative-operator manages KnativeServing + KnativeEventing CRs so we
don't have to apply 50 raw manifests on every upgrade. one CR per
component.

```bash
KNATIVE_VERSION=v1.15.4

kubectl apply -f https://github.com/knative/operator/releases/download/knative-operator-${KNATIVE_VERSION}/operator.yaml
kubectl wait --for=condition=Available deployment/knative-operator -n default --timeout=180s
```

## install knative serving

```bash
kubectl create ns knative-serving --dry-run=client -o yaml | kubectl apply -f -

cat <<'EOF' | kubectl apply -f -
apiVersion: operator.knative.dev/v1beta1
kind: KnativeServing
metadata:
  name: knative-serving
  namespace: knative-serving
spec:
  version: 1.15.4
  ingress:
    istio:
      enabled: true
  config:
    autoscaler:
      min-scale: "0"
      max-scale: "10"
      stable-window: "60s"
      scale-to-zero-grace-period: "30s"
    domain:
      mcp.t3ja.com: ""
    network:
      ingress-class: "istio.ingress.networking.knative.dev"
EOF

kubectl wait --for=condition=Ready knativeserving/knative-serving \
  -n knative-serving --timeout=300s
```

## networking layer pick

knative ships with kourier, istio, and contour as options. We use
istio because the cluster already runs it for mTLS and telemetry -
adding kourier would mean two ingress controllers fighting for
:80/:443, and we'd lose the trace propagation the istio sidecars
already do.

If you wanted a pure-knative deploy without istio, install kourier
instead with `spec.ingress.kourier.enabled: true` and skip the istio
block.

## verify

```bash
kubectl get pods -n knative-serving
# expect: activator + autoscaler + controller + webhook + net-istio-* all Running

kubectl get crd | grep knative
# expect: services / configurations / revisions / routes from serving.knative.dev
```

## image registry

knative pulls images on cold start, so DockerHub rate limits matter.
the platform tag prefix is `gsst3ja/openproject-mcp`. Either:

- create a `regcred` Secret in each ns that hosts ksvc resources, and
  reference via `spec.template.spec.imagePullSecrets[]`
- or set up ECR pull-through cache + IRSA on the activator (preferred,
  see the iam module in `terraform/modules/iam/`)

## common breaks

| symptom                                              | fix                                                        |
|------------------------------------------------------|------------------------------------------------------------|
| ksvc stuck `RevisionMissing`                         | check imagePullSecret + image tag actually exists          |
| `Error: KingressNotConfigured`                       | net-istio not installed; reapply KnativeServing CR         |
| cold start latency > 15s                             | bump `containerConcurrency` + tune `min-scale: "1"`        |
| `0/3 nodes available: 3 Insufficient cpu`            | activator/autoscaler resources too high for small node    |

## next

apply `service.yaml` in this dir to deploy the scale-to-zero MCP
variant, then `traffic-split-demo.yaml` for revision rollout demo.
