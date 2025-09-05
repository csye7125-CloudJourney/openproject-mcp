output "jenkins_deploy_role_arn" {
  value       = aws_iam_role.jenkins_deploy.arn
  description = "ARN Jenkins assumes from the management account."
}

output "jenkins_deploy_role_name" {
  value = aws_iam_role.jenkins_deploy.name
}

output "irsa_role_arns" {
  description = "Map workload-key -> role ARN. Empty when oidc_provider_arn is not wired in."
  value       = { for k, r in aws_iam_role.irsa : k => r.arn }
}

output "irsa_role_names" {
  value = { for k, r in aws_iam_role.irsa : k => r.name }
}
