locals {
  environment = var.aws_profile
  # Prod sits at the apex. dev/staging append their subdomain.
  fqdn = var.subdomain == "" ? var.domain : "${var.subdomain}.${var.domain}"

  common_tags = {
    Project     = "openproject-mcp"
    Environment = local.environment
    ManagedBy   = "terraform"
  }
}
