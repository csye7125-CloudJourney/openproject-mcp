# modules/eks

EKS 1.30 cluster. Private endpoint, two managed node groups (on-demand +
spot), IRSA wired up, baseline managed addons.

## Inputs

| Name | Default | Notes |
| --- | --- | --- |
| `name` | (required) | prefix - eg `openproject-mcp-dev` |
| `vpc_id` | (required) | VPC the cluster lives in |
| `private_subnet_ids` | (required) | min 2 AZs, 3 recommended |
| `kubernetes_version` | `1.30` | bump cluster + addons together |
| `ondemand_desired_size` | `2` | m5.xlarge |
| `ondemand_max_size` | `5` | cluster-autoscaler ceiling |
| `spot_max_size` | `3` | t3.medium / t3a.medium / t3.large mix |

## Outputs

- `cluster_name`, `cluster_endpoint`, `cluster_arn`
- `oidc_issuer_url`, `oidc_provider_arn` - feed these into `modules/iam`
- `cluster_security_group_id` - used by MSK + RDS sg ingress

## Node configuration

`kube-reserved=cpu=100m,memory=512Mi` and `system-reserved=cpu=100m,memory=512Mi`
plumbed via launch template user_data. Without these the kubelet daemons
were getting OOM-killed under load; leaving the values as a tombstone.

Spot pool has a `spot=true:NoSchedule` taint. Workloads opt in via
toleration; everything else stays on the on-demand pool.

## Addons

- coredns
- kube-proxy
- vpc-cni
- aws-ebs-csi-driver (IRSA-scoped `ebs-csi-controller-sa`)

All four use `most_recent = true` data lookups so the version tracks
the cluster's k8s minor.

## Access

The cluster endpoint is private. To reach it:

1. Connect to the tailnet (`tailscale up`).
2. `aws eks update-kubeconfig --name <cluster_name> --region us-east-1 --profile <env_profile>`.

The Tailscale subnet router (deployed via `tailscale/k8s-operator.tf`)
exposes the EKS API endpoint into the tailnet.
