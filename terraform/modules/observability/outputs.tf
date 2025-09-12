output "app_log_group_name" {
  value = aws_cloudwatch_log_group.app.name
}

output "app_log_group_arn" {
  value = aws_cloudwatch_log_group.app.arn
}

output "ingress_log_group_name" {
  value = aws_cloudwatch_log_group.ingress.name
}

output "ingress_log_group_arn" {
  value = aws_cloudwatch_log_group.ingress.arn
}

output "audit_log_group_name" {
  value = aws_cloudwatch_log_group.audit.name
}

output "audit_log_group_arn" {
  value = aws_cloudwatch_log_group.audit.arn
}

output "amp_workspace_id" {
  value = aws_prometheus_workspace.this.id
}

output "amp_endpoint" {
  description = "Remote-write endpoint for Prometheus agents."
  value       = aws_prometheus_workspace.this.prometheus_endpoint
}

output "amp_workspace_arn" {
  value = aws_prometheus_workspace.this.arn
}

output "amg_workspace_id" {
  value       = try(aws_grafana_workspace.this[0].id, "")
  description = "Empty when enable_managed_grafana=false."
}

output "amg_endpoint" {
  value = try(aws_grafana_workspace.this[0].endpoint, "")
}
