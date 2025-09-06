locals {
  environment = var.aws_profile
  fqdn        = "${var.subdomain}.${var.domain}"

  common_tags = {
    Project     = "openproject-mcp"
    Environment = local.environment
    ManagedBy   = "terraform"
  }
}
