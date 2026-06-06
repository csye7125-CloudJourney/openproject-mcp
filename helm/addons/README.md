# addons

Wrapper Helm chart for the platform addons that the `openproject-mcp` chart
depends on at runtime. One release per cluster, installed before any
workload chart.

## What's in here

| Addon              | Upstream chart                                       | Why                                                                                  |
|--------------------|------------------------------------------------------|--------------------------------------------------------------------------------------|
| External Secrets   | `external-secrets/external-secrets` ~> 0.10          | Pulls AWS Secrets Manager values into K8s Secret objects on a schedule.              |
| Sealed Secrets     | `sealed-secrets/sealed-secrets` ~> 2.16              | Break-glass fallback when ESO can't reach AWS - encrypted secrets live in git.       |
| External DNS       | `external-dns/external-dns` ~> 1.15                  | Reconciles Route53 records from Service + Ingress annotations on the t3ja.com zone. |

Each is gated behind its own `.enabled` toggle so a clean-room cluster
can stage them in one at a time.

## Install order

This chart MUST land before any workload chart that references the CRDs it
brings up. The `openproject-mcp` chart references:

- `ExternalSecret` (CRD from external-secrets)
- `SealedSecret` (CRD from sealed-secrets)

Applying `openproject-mcp` against a cluster where `addons` has not yet
synced will fail with `no matches for kind ExternalSecret`. ArgoCD users
set this Application to `sync-wave: -1`; vanilla Helm users run
`helm upgrade --install addons` first.

## Dependencies on terraform

`addons` does not provision any AWS resources. It expects the following
to already exist (output by `terraform/modules/iam/`):

| Terraform output                            | Used by                                                                  |
|---------------------------------------------|--------------------------------------------------------------------------|
| `module.iam.irsa_role_arns["external_secrets"]` | `.Values.externalSecrets.serviceAccount.roleArn`                     |
| `module.iam.irsa_role_arns["external_dns"]`     | `.Values.externalDns.serviceAccount.roleArn`                         |
| `module.route53` hosted zone                | `external-dns` writes records into it (matched by `domainFilters`).      |

If `serviceAccount.roleArn` is empty the pod falls back to the node role
and ClusterSecretStore will surface an `InvalidIdentityToken` error.

The IAM policy doc shipped in `files/external-dns-iam-policy.json` is a
reference copy of what the terraform module attaches - useful when running
the chart against a cluster whose IAM is managed elsewhere.

## Usage

```bash
# 1. pull upstream charts
helm dependency update helm/addons/

# 2. install
helm upgrade --install addons helm/addons/ \
  -n addons --create-namespace \
  -f helm/addons/values-dev.yaml \
  --set externalSecrets.serviceAccount.roleArn=$(terraform -chdir=terraform/envs/dev output -raw external_secrets_role_arn) \
  --set externalDns.serviceAccount.roleArn=$(terraform -chdir=terraform/envs/dev output -raw external_dns_role_arn)
```

## Key rotation

`templates/sealedsecret-key-rotation.yaml` ships a quarterly CronJob
(`0 3 1 */3 *` UTC) that restarts the sealed-secrets controller. On
restart the controller mints a new active key when `keyrenewperiod`
(2160h / 90d) has elapsed. Old keys remain in-cluster as decryption-only
material so previously sealed payloads still apply.

90d matches the KMS key rotation cadence we use on the rest of the
stack - keeping one number across all key-rotation policies makes auditing
easier.

To force an out-of-cycle rotation (e.g. after a suspected compromise):

```bash
kubectl -n sealed-secrets create job manual-rotate --from=cronjob/sealed-secrets-key-rotation
```

## Verification

```bash
helm lint helm/addons/ -f helm/addons/values.yaml
helm template helm/addons/ -f helm/addons/values-dev.yaml | kubectl apply --dry-run=client -f -
```
