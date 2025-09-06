terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }
  }
}

# Postgres 15. KMS-encrypted, intra subnets only, multi-AZ optional.
# master password lands in Secrets Manager (see secrets.tf for rotation).

resource "aws_kms_key" "rds" {
  description             = "${var.name}-rds kms"
  enable_key_rotation     = true
  deletion_window_in_days = 14

  tags = merge(var.tags, {
    Name = "${var.name}-rds-kms"
  })
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.name}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

resource "aws_db_subnet_group" "this" {
  name        = "${var.name}-rds"
  description = "${var.name} rds subnet group (intra subnets, 3 AZs)"
  subnet_ids  = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.name}-rds-subnet-group"
  })
}

resource "aws_db_parameter_group" "this" {
  name        = "${var.name}-pg15"
  family      = "postgres15"
  description = "${var.name} postgres 15 params"

  parameter {
    name  = "timezone"
    value = "UTC"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  # max_connections is pending-reboot. bumped for OpenProject's pool
  # default (50 per pod, room for ~20 pods).
  parameter {
    name         = "max_connections"
    value        = "1024"
    apply_method = "pending-reboot"
  }

  tags = merge(var.tags, {
    Name = "${var.name}-pg15"
  })
}

resource "aws_security_group" "rds" {
  name        = "${var.name}-rds-sg"
  description = "Postgres ingress from eks node sgs"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
    description     = "Postgres from EKS nodes"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name}-rds-sg"
  })
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name}-postgres"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = var.db_name
  username = var.master_username
  password = random_password.master.result

  multi_az               = var.multi_az
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.this.name

  backup_retention_period = var.backup_retention_period
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:30-Mon:05:30"

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name}-postgres-final-${formatdate("YYYYMMDDhhmmss", timestamp())}"

  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.rds.arn
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = merge(var.tags, {
    Name = "${var.name}-postgres"
  })

  lifecycle {
    ignore_changes = [final_snapshot_identifier]
  }
}
