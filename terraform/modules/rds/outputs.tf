output "endpoint" {
  value = aws_db_instance.this.endpoint
}

output "address" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

output "security_group_id" {
  value = aws_security_group.rds.id
}

output "kms_key_arn" {
  value = aws_kms_key.rds.arn
}

output "secret_arn" {
  description = "Secrets Manager secret holding master creds. Apps consume via ExternalSecret."
  value       = aws_secretsmanager_secret.master.arn
}

output "secret_name" {
  value = aws_secretsmanager_secret.master.name
}
