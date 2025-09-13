# AWS Managed Prometheus + AWS Managed Grafana.
#
# AMP we control fully here. AMG needs SSO identity store wiring +
# role bindings that aren't fully terraformable (SAML/SSO mapping is
# Console-driven). We provision the workspace + the IAM role for the
# data-source binding here; the user-role assignment is a one-time
# manual Console step.

resource "aws_prometheus_workspace" "this" {
  alias = "${var.name}-amp"

  logging_configuration {
    log_group_arn = "${aws_cloudwatch_log_group.app.arn}:*"
  }

  tags = merge(var.tags, {
    Name = "${var.name}-amp"
  })
}

# Grafana workspace. IAM_IDENTITY_CENTER auth type means the SSO group
# mappings happen post-creation via the Console.
resource "aws_grafana_workspace" "this" {
  count = var.enable_managed_grafana ? 1 : 0

  name                     = "${var.name}-amg"
  account_access_type      = "CURRENT_ACCOUNT"
  authentication_providers = ["AWS_SSO"]
  permission_type          = "SERVICE_MANAGED"

  data_sources = ["PROMETHEUS", "CLOUDWATCH"]

  tags = merge(var.tags, {
    Name = "${var.name}-amg"
  })
}
