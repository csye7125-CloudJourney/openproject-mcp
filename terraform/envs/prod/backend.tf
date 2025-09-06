terraform {
  backend "s3" {
    bucket         = "openproject-mcp-tfstate-openproject-mcp-prod"
    key            = "envs/prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "openproject-mcp-tflock"
    encrypt        = true
    profile        = "openproject-mcp-prod"
  }
}
