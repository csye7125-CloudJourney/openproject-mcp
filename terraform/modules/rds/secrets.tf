# master creds in Secrets Manager. apps pull via ESO so the password
# never lands in env files. 90-day rotation cadence.

resource "random_password" "master" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "master" {
  name        = "${var.name}/rds/master"
  description = "RDS master creds for ${var.name}-postgres"
  kms_key_id  = aws_kms_key.rds.arn

  recovery_window_in_days = 7

  tags = merge(var.tags, {
    Name = "${var.name}-rds-master-secret"
  })
}

resource "aws_secretsmanager_secret_version" "master" {
  secret_id = aws_secretsmanager_secret.master.id
  secret_string = jsonencode({
    username = var.master_username
    password = random_password.master.result
    engine   = "postgres"
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = aws_db_instance.this.db_name
  })
}

# rotation. lambda-driven via the AWS-published rotation template.
# the lambda itself isn't deployed from this module; assumed already
# present via the serverlessrepo `SecretsManagerRDSPostgreSQLRotationSingleUser`
# app. empty var.rotation_lambda_arn => skip the rotation block (dev only).
resource "aws_secretsmanager_secret_rotation" "master" {
  count               = var.rotation_lambda_arn == "" ? 0 : 1
  secret_id           = aws_secretsmanager_secret.master.id
  rotation_lambda_arn = var.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = 90
  }
}
