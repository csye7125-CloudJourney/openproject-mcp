# argocd/

GitOps glue. ArgoCD itself lives in-cluster (install via `install.md`).
This dir holds the declarative config we apply on top to make ArgoCD watch
the `openproject-mcp-manifests` repo and deploy the three envs.

## Layout

```
argocd/
  install.md                       # install runbook + initial admin pw + UI access
  README.md                        # this file
  projects/
    openproject-mcp.yaml           # AppProject - sources, destinations, RBAC
  applications/
    openproject-mcp-dev.yaml       # auto-sync, prune+selfHeal
    openproject-mcp-staging.yaml   # auto-sync, prune+selfHeal
    openproject-mcp-prod.yaml      # auto-sync (selfHeal only, no prune)
  image-updater-config.yaml        # docker hub watch -> manifests repo writeback
  repositories/
    manifests-repo.yaml            # SealedSecret with ssh deploy key (placeholder)
```

## Apply order

1. `kubectl apply -f argocd/projects/openproject-mcp.yaml`
   - AppProject must exist before Applications referencing it
2. `kubectl apply -f argocd/repositories/manifests-repo.yaml`
   - sealed secret with deploy key, lets argocd pull the manifests repo
3. `kubectl apply -f argocd/applications/openproject-mcp-dev.yaml`
   - first env, watch sync status before moving on
4. `kubectl apply -f argocd/applications/openproject-mcp-staging.yaml`
5. `kubectl apply -f argocd/applications/openproject-mcp-prod.yaml`
6. `kubectl apply -f argocd/image-updater-config.yaml`
   - optional, only if argocd-image-updater is installed

## Manifests repo

Lives separately at `github.com/csye7125-CloudJourney/openproject-mcp-manifests`. Kustomize
overlays per env. ArgoCD watches its `main` branch. Jenkins + the image
updater both push new image tags to it - never pushes to this repo.

That separation is intentional: this repo is the *source*, the manifests
repo is the *target*. Mixing them means a build can race a sync.

## Verifying a sync

```bash
argocd app list
argocd app get openproject-mcp-dev
argocd app sync openproject-mcp-dev      # force a refresh
argocd app diff openproject-mcp-dev      # what would change
argocd app rollback openproject-mcp-dev 0 # revert to last good revision
```

## Drift demo (self-heal)

```bash
# someone runs kubectl edit and drops replicas to 0
kubectl -n openproject-mcp scale deploy/dev-openproject-mcp --replicas=0
# wait ~30s, watch argocd revert it
kubectl -n openproject-mcp get deploy/dev-openproject-mcp -w
```

## See also

- `../helm/openproject-mcp/` - the Helm chart the manifests repo eventually
  consumes (current manifests repo is kustomize-only for simplicity, the
  chart is published separately for downstream consumers)
