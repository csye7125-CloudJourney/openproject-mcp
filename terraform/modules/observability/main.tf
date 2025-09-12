terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70"
    }
  }
}

# cloudwatch log groups for the app / ingress / audit log destinations.
# the cluster itself logs to /aws/eks/... separately. app logs arrive
# via fluentd or the otel collector configured in helm/observability/.

resource "aws_cloudwatch_log_group" "app" {
  name              = "/openproject-mcp/${var.name}/app"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name   = "${var.name}-app-logs"
    Stream = "app"
  })
}

resource "aws_cloudwatch_log_group" "ingress" {
  name              = "/openproject-mcp/${var.name}/ingress"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name   = "${var.name}-ingress-logs"
    Stream = "ingress"
  })
}

resource "aws_cloudwatch_log_group" "audit" {
  name              = "/openproject-mcp/${var.name}/audit"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name   = "${var.name}-audit-logs"
    Stream = "audit"
  })
}
