# modules/rds

Postgres 15. KMS-encrypted, intra subnets, multi-AZ optional per env.
Master credentials auto-generated and held in Secrets Manager with
90-day rotation.

## Inputs

| Name | Default | Notes |
| --- | --- | --- |
| `name` | (required) | prefix |
| `vpc_id` | (required) | |
| `subnet_ids` | (required) | intra subnets, 3 AZs |
| `allowed_security_group_ids` | (required) | EKS node sg(s) |
| `engine_version` | `15.7` | bump in tandem with OpenProject support |
| `instance_class` | `db.t4g.micro` | Graviton arm64 |
| `multi_az` | `false` | required for prod |
| `skip_final_snapshot` | `false` | flip true ONLY on dev |
| `deletion_protection` | `true` | flip false before tearing down |
| `rotation_lambda_arn` | `""` | empty disables rotation - dev-only |

## Outputs

- `endpoint`, `address`, `port`
- `db_name`
- `secret_arn` - feed into ExternalSecret in the helm chart
- `security_group_id`

## Secrets

`{name}/rds/master` in Secrets Manager. Shape:

```json
{
  "username": "openproject_admin",
  "password": "...",
  "engine": "postgres",
  "host": "...",
  "port": 5432,
  "dbname": "openproject"
}
```

Rotation runs the AWS-published `SecretsManagerRDSPostgreSQLRotationSingleUser`
Lambda. Deploy that app once per region from the Serverless Application
Repository, pass its ARN as `rotation_lambda_arn`.

## Parameter group

Custom `postgres15` params: `timezone=UTC`, `log_min_duration_statement=500`
(slow query log), connection logging, `max_connections=1024`. The last is
pending-reboot - first apply will trigger a planned restart.
