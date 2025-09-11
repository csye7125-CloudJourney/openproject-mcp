output "cluster_arn" {
  value = aws_msk_cluster.this.arn
}

output "cluster_name" {
  value = aws_msk_cluster.this.cluster_name
}

output "bootstrap_brokers_sasl_iam" {
  description = "Comma-separated host:port for SASL/IAM clients. Feed into KAFKA_BOOTSTRAP for mcp-server."
  value       = aws_msk_cluster.this.bootstrap_brokers_sasl_iam
}

output "zookeeper_connect_string" {
  description = "Empty when using KRaft - kept for compatibility with older tools."
  value       = aws_msk_cluster.this.zookeeper_connect_string
}

output "security_group_id" {
  value = aws_security_group.msk.id
}

output "kms_key_arn" {
  value = aws_kms_key.msk.arn
}

output "broker_log_group_name" {
  value = aws_cloudwatch_log_group.broker.name
}
