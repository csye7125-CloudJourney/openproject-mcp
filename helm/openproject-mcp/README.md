# openproject-mcp

Helm chart for the MCP server backed by an OpenProject instance.

## Image pull secret

The chart renders a Docker Hub pull secret via External Secrets Operator and
wires it onto the ServiceAccount. Source of truth is AWS Secrets Manager at:

```
openproject-mcp/<env>/dockerhub-pull
{
  "username": "gsst3ja",
  "token": "dckr_pat_..."
}
```

That secret has to be created via the AWS CLI (or console). It is not managed
in Terraform because the token is an account-wide Docker Hub PAT and rotates
out of band from infra changes.

Example one-time bootstrap:

```
aws secretsmanager create-secret \
  --name openproject-mcp/dev/dockerhub-pull \
  --secret-string '{"username":"gsst3ja","token":"dckr_pat_xxx"}'
```

ESO renders a `kubernetes.io/dockerconfigjson` Secret named `dockerhub-pull` in
the chart namespace. The chart's ServiceAccount references it under
`imagePullSecrets`, so any pod using that SA pulls Docker Hub images without
the prior manual `kubectl create secret docker-registry` step.

Disable with `--set imagePullSecret.enabled=false` if the registry is public
or the cluster already has a tenant-wide pull secret.

## Namespace

`namespace.create=true` makes the chart own its namespace, which is needed for
ArgoCD-driven installs that don't pass `--create-namespace`. The default is
false so plain `helm install --create-namespace` keeps working.

When namespace creation is on, `istio.injection=true` (default) adds the
`istio-injection=enabled` label so the sidecar gets injected on pod start.
