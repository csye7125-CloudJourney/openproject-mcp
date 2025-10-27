terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.11"
    }
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# Tailscale auth key lives in Secrets Manager. Created out-of-band via
# CLI so the value stays outside Terraform state. Module reads it via
# data source at apply time.
data "aws_secretsmanager_secret_version" "tailscale_auth_key" {
  secret_id = var.tailscale_auth_key_secret_name
}

resource "aws_security_group" "router" {
  name        = "${var.name}-ts-router-sg"
  description = "Tailscale subnet router - outbound only (peer-to-peer over WireGuard handles inbound)"
  vpc_id      = var.vpc_id

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name}-ts-router-sg"
  })
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "router" {
  name               = "${var.name}-ts-router"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.router.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "router" {
  name = "${var.name}-ts-router"
  role = aws_iam_role.router.name
}

# IAM instance profile creation is async on AWS side. EC2 launch races
# the propagation and errors with "Invalid IAM Instance Profile name".
# 15s sleep is overkill on warm accounts, fine on cold ones.
resource "time_sleep" "iam_propagate" {
  depends_on      = [aws_iam_instance_profile.router]
  create_duration = "15s"
}

locals {
  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    apt-get update
    apt-get install -y curl iptables
    curl -fsSL https://tailscale.com/install.sh | sh
    # Enable IP forwarding for subnet routing
    echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.d/99-tailscale.conf
    echo 'net.ipv6.conf.all.forwarding = 1' >> /etc/sysctl.d/99-tailscale.conf
    sysctl -p /etc/sysctl.d/99-tailscale.conf
    tailscale up \
      --authkey='${data.aws_secretsmanager_secret_version.tailscale_auth_key.secret_string}' \
      --advertise-routes='${join(",", var.advertise_routes)}' \
      --advertise-tags='${join(",", var.advertise_tags)}' \
      --hostname='${var.name}-ts-router' \
      --ssh
  EOT
}

resource "aws_instance" "router" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.router.id]
  iam_instance_profile        = aws_iam_instance_profile.router.name
  associate_public_ip_address = true
  user_data                   = local.user_data

  # Tailscale subnet router needs source/dest check disabled to route VPC traffic
  source_dest_check = false

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  depends_on = [time_sleep.iam_propagate]

  tags = merge(var.tags, {
    Name = "${var.name}-ts-router"
    role = "tailscale-subnet-router"
  })
}
