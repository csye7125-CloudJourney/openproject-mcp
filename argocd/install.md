# ArgoCD install runbook

Single ArgoCD instance per cluster. Lives in `argocd` ns, manages workloads
in `openproject-mcp` (and any other app ns we add later).

## Prereqs

- `kubectl` context pointing at the target cluster (dev/staging/prod)
- cluster-admin on that context (only needed during install; afterwards
  ArgoCD has its own RBAC + UI auth)
- outbound 443 from the cluster to github.com (ArgoCD pulls manifests)

## Install

```bash
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Wait for the 5 deployments (server, repo-server, applicationset-controller,
notifications-controller, dex) + the statefulset (application-controller)
to be Available:

```bash
kubectl -n argocd rollout status deploy/argocd-server
kubectl -n argocd rollout status deploy/argocd-repo-server
kubectl -n argocd rollout status deploy/argocd-applicationset-controller
kubectl -n argocd rollout status statefulset/argocd-application-controller
```

## Initial admin password

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
echo
```

Login user is `admin`. Rotate immediately after first login via UI
(User Info -> Update Password) then delete the secret:

```bash
kubectl -n argocd delete secret argocd-initial-admin-secret
```

## UI access (Tailscale-only)

No public LB. Pin the argocd-server Service annotation so the Tailscale
operator picks it up, or use raw port-forward for one-off access:

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
# then https://localhost:8080 in a browser, accept self-signed cert
```

Long-term path: annotate the service for the tailscale operator -
matches how we expose the MCP service itself.

```bash
kubectl -n argocd annotate svc argocd-server \
  tailscale.com/expose=true \
  tailscale.com/hostname=argocd-${ENV}
```

Resolves at `argocd-${ENV}.tailnet-xxxx.ts.net` from any tailnet member.

## CLI

```bash
brew install argocd
argocd login argocd-${ENV}.tailnet-xxxx.ts.net --grpc-web
argocd cluster list
argocd app list
```

## Next

- apply `projects/openproject-mcp.yaml` first (AppProject must exist before
  Applications can reference it)
- apply `applications/openproject-mcp-dev.yaml`
- then staging + prod
- then `image-updater-config.yaml` to wire registry watch -> manifests
  repo write-back
