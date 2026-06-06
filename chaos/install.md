# chaos-mesh install (EKS)

Notes for installing chaos-mesh into the prod cluster. Pin the version
because chaos-mesh CRDs shift between minor releases, and silent skew
between the operator and the CRDs breaks scenarios.

## Pinned version

- chart: `chaos-mesh-2.7.0`
- chart repo: `https://charts.chaos-mesh.org`
- image: `ghcr.io/chaos-mesh/chaos-mesh:v2.7.0`

## Install

```bash
kubectl create namespace chaos-mesh
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update
helm install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-mesh \
  --version 2.7.0 \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
  --set dashboard.create=true \
  --set dashboard.serviceType=ClusterIP \
  --wait --timeout 5m
```

EKS uses containerd by default - no need to switch `runtime=docker`.

## Verify

```bash
kubectl -n chaos-mesh get pods
# expected: chaos-controller-manager-* (3 replicas), chaos-daemon-* (one per node), chaos-dashboard-*

kubectl -n chaos-mesh get crd | grep chaos
# expected CRDs include: podchaos, networkchaos, iochaos, timechaos, schedules
```

## Dashboard

Tailscale-side access only (no public ingress for chaos):

```bash
kubectl -n chaos-mesh port-forward svc/chaos-dashboard 2333:2333
# open http://localhost:2333 - generate a token via:
kubectl -n chaos-mesh exec deploy/chaos-dashboard -- /usr/local/bin/chaos-dashboard token --serviceaccount default
```

## RBAC for in-cluster chaos

Chaos resources need a SA with permission to mutate workloads in target
namespaces. For `openproject-mcp` namespace:

```bash
kubectl -n openproject-mcp create sa chaos-runner
kubectl create clusterrolebinding chaos-runner-openproject-mcp \
  --clusterrole=chaos-mesh-target-namespace \
  --serviceaccount=openproject-mcp:chaos-runner
```

(`chaos-mesh-target-namespace` ClusterRole is created by the helm install.)

## Uninstall

```bash
helm uninstall chaos-mesh -n chaos-mesh
kubectl delete crd $(kubectl get crd | grep chaos-mesh.org | awk '{print $1}')
kubectl delete namespace chaos-mesh
```

CRDs do not delete on `helm uninstall` - drop them manually if not needed.
