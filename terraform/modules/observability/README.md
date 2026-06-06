# modules/observability

CloudWatch log groups for app / ingress / audit, plus the managed
metrics stack: AWS Managed Prometheus (AMP) and AWS Managed Grafana (AMG).

## Inputs

| Name | Default | Notes |
| --- | --- | --- |
| `name` | (required) | prefix |
| `log_retention_days` | `14` | bump to 30+ in prod |
| `enable_managed_grafana` | `false` | flip on per-env; needs SSO follow-up |

## Outputs

- `app_log_group_arn`, `ingress_log_group_arn`, `audit_log_group_arn`
- `amp_endpoint`: Prometheus remote-write target. Wire into
  `prometheus.prometheusSpec.remoteWrite` in the kube-prometheus-stack
  helm values.
- `amp_workspace_arn`: referenced by the `amp-iamproxy-ingest` IRSA role.
- `amg_workspace_id`, `amg_endpoint`: empty when AMG is disabled.

## Managed Grafana setup (manual follow-up)

AMG can be created via Terraform (auth_providers + permission_type), but
the actual user-to-role mapping is a Console step:

1. IAM Identity Center > Users: create or import.
2. AMG workspace > Configure users and groups: bind users to Admin /
   Editor / Viewer.
3. Add data sources from the workspace UI. Prometheus URL = `amp_endpoint`,
   CloudWatch via the workspace service role.

Mapping is Console-only because the SSO directory sits at the
management-account level and crosses Terraform state boundaries. Stays a
runbook item rather than wedging cross-account providers.

## What this module does NOT do

- AMP scrapers live in the EKS cluster, deployed via `helm/observability/`.
  The endpoint output above is consumed there.
- Kibana / OpenSearch / EFK ships from a separate Helm chart on the
  cluster.
- Alerting rules land in `helm/observability/templates/prometheusrule.yaml`.
