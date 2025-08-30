terraform {
  backend "s3" {
    # Bucket + table provisioned by terraform/bootstrap in this account.
    # Override per env via `terraform init -backend-config=...` if needed.
    bucket         = "openproject-mcp-tfstate-openproject-mcp-dev"
    key            = "envs/dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "openproject-mcp-tflock"
    encrypt        = true
    profile        = "openproject-mcp-dev"
  }
}
