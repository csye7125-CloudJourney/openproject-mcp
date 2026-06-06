# modules/istio

Installs Istio (base + istiod) into the EKS cluster via the upstream
Helm charts at `istio-release.storage.googleapis.com/charts`.

## Why Istio

What it gives me that's hard to get otherwise:

- mTLS between pods without app-level changes. A PeerAuthentication
  resource flips the whole namespace to STRICT in one apply.
- Traffic shifting via VirtualService weights; the openproject-mcp
  rollout uses these for canary percentages on deploys.
- L7 observability via the sidecar (Prometheus metrics + access logs),
  picked up by the obs stack running in cluster. Distributed tracing
  also works once the workload propagates B3 headers.
- Ingress gateway is the single LB hostname the Route53 CNAME points
  at, so `kubectl get svc -n istio-system istio-ingressgateway` is the
  only DNS-relevant lookup during a deploy.

## helm_release vs istioctl

`helm_release` is declarative and state-tracked, so `terraform destroy`
actually removes the control plane (`istioctl x uninstall` is a separate
step that's easy to forget). Version pin is one variable so bumping
1.23.2 -> 1.24.x is a one-line diff. It also hooks into the same
provider chain the rest of the stack uses, so IRSA / auth refresh just
works. istioctl is still useful for `analyze` + `proxy-config` debugging;
this module replaces the install step, not the CLI.

## Labeling app namespaces for sidecar injection

The module installs the control plane only. App namespaces opt in to
sidecar injection with the standard istio label:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: openproject-mcp
  labels:
    istio-injection: enabled
```

For namespaces created by helm, add the label on the chart's namespace
template or `kubectl label ns openproject-mcp istio-injection=enabled`
once per environment. Pods need a restart after the label is added;
the webhook only mutates new pods.

## Inputs

| Name | Default | Notes |
| --- | --- | --- |
| `istio_version` | `1.23.2` | chart version, same value for base + istiod |
| `cluster_name` | (required) | passes through to `global.multiCluster.clusterName` |
| `mesh_id` | `openproject-mcp` | constant across clusters joining the same mesh |
| `network_name` | `openproject-mcp-network` | drops onto `topology.istio.io/network` |
| `namespace_labels` | `{}` | extra labels on istio-system |
| `istiod_cpu_request` | `100m` | pilot cpu request |
| `istiod_memory_request` | `512Mi` | pilot memory request |

## Outputs

- `namespace`: `istio-system`. Plumb into observability scrape configs.
- `istiod_release_name`: `istiod`. Used by `helm status` from CI.
- `chart_version`: the pinned version installed.

## Two-stage apply

The module assumes the EKS API endpoint is already reachable from
wherever Terraform runs (tailnet from a laptop, in-VPC runner from CI).
For a clean apply on an empty account, gate the module call with
`var.deploy_istio = false` on the first pass and flip to `true` once
the EKS module is healthy. Same pattern as the `enable_irsa` flag in
`modules/iam`.
