# modules/msk

Amazon MSK, Kafka 3.6.0. TLS-only listener with SASL/IAM auth, per-cluster
KMS for encryption at rest. Broker logs ship to CloudWatch (14d retention).

## Inputs

| Name | Default | Notes |
| --- | --- | --- |
| `name` | (required) | prefix |
| `vpc_id` | (required) | |
| `subnet_ids` | (required) | private subnets, 3 AZs - one broker per |
| `allowed_security_group_ids` | (required) | EKS node sg(s) |
| `kafka_version` | `3.6.0` | bump alongside server_properties review |
| `broker_instance_type` | `kafka.t3.small` | |
| `broker_ebs_volume_size` | `1` | per-broker gp2, MSK does not yet support gp3 |
| `number_of_broker_nodes` | `2` | must be multiple of subnet count |

## Outputs

- `cluster_arn` - used by IRSA policy (`kafka-cluster:Connect/WriteData/ReadData`)
- `bootstrap_brokers_sasl_iam` - app's `KAFKA_BOOTSTRAP` env var
- `security_group_id`, `kms_key_arn`, `broker_log_group_name`

## Server properties

Locked at the cluster configuration:

- `auto.create.topics.enable=false` (topics are explicitly created)
- `default.replication.factor=3`
- `min.insync.replicas=2`
- `num.partitions=12`
- `log.retention.hours=168` (7d)
- `unclean.leader.election.enable=false`

## Auth model

`client_authentication.sasl.iam = true` is the only enabled path.
`unauthenticated = false` and SCRAM is not configured. Apps connect on
port 9098 with `SASL_SSL` + `AWS_MSK_IAM` mechanism. Pods get the perms
via IRSA; see `modules/iam/irsa.tf` for the `mcp-server` role bound to
`kafka-cluster:{Connect,WriteData,ReadData}` on the cluster ARN.

## Monitoring

- `enhanced_monitoring = PER_TOPIC_PER_BROKER`
- JMX + node exporters via `open_monitoring.prometheus`
- Broker logs to CloudWatch `/aws/msk/<name>/broker`

## Topic creation

This module does NOT create topics. Topics get created post-cluster via
a one-shot Kubernetes Job in the helm chart (`helm/openproject-mcp/templates/topic-init-job.yaml`)
that runs `kafka-topics.sh` with the IAM client. The default config above
gives that job sane fallbacks.
