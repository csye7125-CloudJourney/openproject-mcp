# terraform/bootstrap

Chicken-and-egg stack. Creates the S3 bucket + DynamoDB table the other
stacks point their remote backend at.

## When to run

**Once per env account** before any other stack in that account.
Uses **local state** because the remote backend doesn't exist yet.

```bash
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: set aws_profile to one of
#   openproject-mcp-dev | openproject-mcp-staging | openproject-mcp-prod

terraform init
terraform apply
```

After it applies, the outputs `state_bucket` and `lock_table` feed
the `backend.tf` of `terraform/envs/<env>/`.

## Why local state here

Storing the bootstrap state in the bucket it provisions is a circular
dep. Keep `terraform.tfstate` in this dir, gitignored, and re-run
this stack only when rotating bucket/table config (rare).

## What it builds

- `openproject-mcp-tfstate-<env>` S3 bucket. Versioning on, SSE-S3,
  public access blocked.
- `openproject-mcp-tflock` DynamoDB table, PAY_PER_REQUEST, `LockID`
  hash key.
