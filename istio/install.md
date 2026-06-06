# Istio install runbook

Step-by-step for getting Istio up on the EKS cluster before applying the
manifests in this dir. Versions pinned because control plane vs. data plane
skew over 2 minor versions breaks injection.

## Versions

- Istio: `1.23.2` (matches EKS 1.30 support matrix)
- istioctl: same as control plane
- Profile: `default` (we tune individual settings, no minimal/demo)

## Prereqs

- EKS 1.30 cluster up (terraform/modules/eks)
- `kubectl` context pointing at the right cluster (`kubectl config current-context`)
- `helm` 3.14+ available
- metrics-server installed with `--kubelet-insecure-tls` flag - Istio dashboards
  fail without it (learned this the hard way)

## Install

```bash
# 1. download istioctl pinned to control plane version
curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.23.2 TARGET_ARCH=x86_64 sh -
cd istio-1.23.2
export PATH=$PWD/bin:$PATH

# 2. preflight
istioctl x precheck

# 3. install control plane with custom values
istioctl install --set profile=default \
  --set values.global.proxy.resources.requests.cpu=50m \
  --set values.global.proxy.resources.requests.memory=64Mi \
  --set values.global.proxy.resources.limits.cpu=500m \
  --set values.global.proxy.resources.limits.memory=256Mi \
  --set meshConfig.accessLogFile=/dev/stdout \
  --set meshConfig.accessLogEncoding=JSON \
  -y

# 4. addons (kiali, jaeger, prom) - dev clusters only, prod uses managed
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.23/samples/addons/jaeger.yaml
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.23/samples/addons/kiali.yaml
```

## Enable injection on namespace

```bash
# create ns then label
kubectl create namespace openproject-mcp
kubectl label namespace openproject-mcp istio-injection=enabled

# verify - any new pod here should get 2 containers (app + istio-proxy)
kubectl get ns openproject-mcp --show-labels
```

## Apply manifests in this dir

```bash
# order matters: peer-auth + dr first (so mTLS is on before traffic),
# then gateway + vs (routing), then authz (last - default deny would otherwise
# block traffic during the install window).
kubectl apply -f istio/peer-authentication.yaml
kubectl apply -f istio/destination-rule.yaml
kubectl apply -f istio/gateway.yaml
kubectl apply -f istio/virtual-service.yaml
kubectl apply -f istio/telemetry.yaml
kubectl apply -f istio/authorization-policy.yaml
```

## Verify mTLS is actually on

```bash
# pick an mcp pod
POD=$(kubectl -n openproject-mcp get pod -l app=openproject-mcp -o jsonpath='{.items[0].metadata.name}')

# istioctl reports per-cert status
istioctl proxy-config secret $POD.openproject-mcp

# test from outside - this should fail (no client cert)
kubectl run -it --rm curl --image=curlimages/curl --restart=Never -- \
  curl -sk https://openproject-mcp.openproject-mcp.svc.cluster.local/healthz
# expect: connection reset / 503

# test from inside ns w/ injection - should work
kubectl -n openproject-mcp run -it --rm curl --image=curlimages/curl --restart=Never -- \
  curl -sk http://openproject-mcp:8000/healthz
```

## Common breaks

- Pod crashloops with `RBAC: access denied` - default-deny is on, but the SA
  the pod runs as is not in any allow rule. Add it to `authorization-policy.yaml`.
- 503 NR (no route) - VirtualService host doesn't match the gateway host. Check
  both list the same FQDN.
- `connection reset by peer` from a sidecar - PeerAuth STRICT vs. peer that
  isn't injected. Either inject the peer or relax mode to PERMISSIVE temporarily.
- `istioctl proxy-status` shows `STALE` for a pod - the pod restarted but
  istiod hasn't pushed new config. Restart istiod or wait the push interval.

## Teardown

```bash
istioctl uninstall --purge -y
kubectl delete ns istio-system
kubectl label namespace openproject-mcp istio-injection-
```
