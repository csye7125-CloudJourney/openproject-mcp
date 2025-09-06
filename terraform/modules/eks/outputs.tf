output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "cluster_ca_certificate" {
  description = "Base64-encoded cluster CA. Feed into helm/kubernetes provider config alongside cluster_endpoint + an EKS auth token."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_arn" {
  value = aws_eks_cluster.this.arn
}

output "cluster_security_group_id" {
  value = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "node_security_group_ids" {
  description = "SGs to allow MSK / RDS ingress from."
  value       = [aws_eks_cluster.this.vpc_config[0].cluster_security_group_id]
}

output "oidc_issuer_url" {
  value = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

output "oidc_provider_arn" {
  description = "Used by modules/iam to mint IRSA roles for in-cluster workloads."
  value       = aws_iam_openid_connect_provider.this.arn
}
