terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70"
    }
  }
}

# 3-broker MSK cluster, Kafka 3.6. TLS listeners, SASL/IAM auth so EKS
# pods authenticate via IRSA (no static SASL passwords to rotate). KMS
# at rest, broker logs to CloudWatch, retention + replication factor
# pinned in the cluster config.

resource "aws_kms_key" "msk" {
  description             = "${var.name}-msk kms"
  enable_key_rotation     = true
  deletion_window_in_days = 14

  tags = merge(var.tags, {
    Name = "${var.name}-msk-kms"
  })
}

resource "aws_kms_alias" "msk" {
  name          = "alias/${var.name}-msk"
  target_key_id = aws_kms_key.msk.key_id
}

resource "aws_security_group" "msk" {
  name        = "${var.name}-msk-sg"
  description = "MSK ingress: IAM-auth port from EKS node sg"
  vpc_id      = var.vpc_id

  # 9098 = TLS+SASL/IAM. plain 9092 stays closed; we never want
  # PLAINTEXT brokers.
  ingress {
    from_port       = 9098
    to_port         = 9098
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
    description     = "Kafka IAM-auth from EKS"
  }

  # ZK is deprecated in 3.6 KRaft but the broker-to-broker port still
  # needs to be open within the cluster sg itself.
  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name}-msk-sg"
  })
}

resource "aws_cloudwatch_log_group" "broker" {
  name              = "/aws/msk/${var.name}/broker"
  retention_in_days = 14

  tags = var.tags
}
