locals {
  environment  = var.aws_profile
  state_bucket = "openproject-mcp-tfstate-${local.environment}"
  lock_table   = "openproject-mcp-tflock"
}

data "aws_caller_identity" "current" {}

# state bucket, one per env account. versioned + SSE so a fat-fingered
# destroy still has a recovery path via the prior version.
resource "aws_s3_bucket" "tfstate" {
  bucket = local.state_bucket
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# dynamodb lock table; shared across stacks in this account
resource "aws_dynamodb_table" "tflock" {
  name         = local.lock_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

output "state_bucket" {
  value       = aws_s3_bucket.tfstate.id
  description = "state bucket. other stacks point backend.tf at this."
}

output "lock_table" {
  value = aws_dynamodb_table.tflock.name
}

output "account_id" {
  value = data.aws_caller_identity.current.account_id
}
