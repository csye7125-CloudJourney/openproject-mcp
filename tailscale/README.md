# tailscale/

Tailscale wiring: the Kubernetes operator install and the tailnet ACL
policy. This dir is referenced by env stacks but the helm_release runs
out-of-band of the per-account terraform - it needs the kubeconfig that
comes out of `aws eks update-kubeconfig` after the cluster is up.

## Files

- `k8s-operator.tf` - `helm_release` for `tailscale/tailscale-operator`.
  Reads the OAuth client secret from `~/.config/openproject-mcp/.env.local`
  via an `external` data source. Run with `TF_VAR_oauth_client_id=...`
  from the same env.local.
- `acls.hujson` - tailnet-wide ACL. Apply via the admin console (`Access
  controls` tab) or the API. See "Pushing ACLs" below.
- `variables.tf` - `env`, `operator_chart_version`, `oauth_client_id`.

## Pushing ACLs

The ACL lives on the Tailscale control plane, not in any AWS account.
Two ways:

1. Copy the file into the admin console at
   <https://login.tailscale.com/admin/acls>. Validate -> Save.
2. API push (CI-friendly):
   ```bash
   curl -X POST \
     -H "Authorization: Bearer $TAILSCALE_API_KEY" \
     -H "Content-Type: application/hujson" \
     --data-binary @acls.hujson \
     "https://api.tailscale.com/api/v2/tailnet/-/acl"
   ```

## Operator install

Pre-reqs: cluster exists, `KUBECONFIG` points at it, tailscale OAuth
client created (admin console -> Settings -> OAuth clients) with the
`devices`, `auth_keys` scopes.

```bash
cd tailscale
terraform init
terraform apply -var env=dev -var oauth_client_id=tskey-client-...
```

The operator namespace gets `pod-security.kubernetes.io/enforce=privileged`
because the subnet-router pod needs `NET_ADMIN`.

## How the mcp-server gets exposed

The helm chart at `helm/openproject-mcp/templates/service.yaml` annotates
its Service with:

```yaml
metadata:
  annotations:
    tailscale.com/expose: "true"
    tailscale.com/hostname: "mcp-openproject"
    tailscale.com/tags: "tag:mcp-server"
```

The operator watches for that annotation, creates a Tailscale ingress
machine bound to the service, and registers `mcp-openproject` in tailnet
DNS. Devs hit `https://mcp-openproject.<tailnet>.ts.net`. Tailscale owns
the cert and the hostname, the EKS Service stays ClusterIP.
