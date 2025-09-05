terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70"
    }
  }
}

locals {
  zone_name = var.is_root_zone ? var.domain : "${var.subdomain}.${var.domain}"
  private_zone_name = var.is_root_zone ? (
    "internal.${var.domain}"
    ) : (
    "internal.${var.subdomain}.${var.domain}"
  )
}

# Public hosted zone. Prod env owns t3ja.com directly; dev/staging
# own their own delegated subzone.
resource "aws_route53_zone" "public" {
  name = local.zone_name

  tags = merge(var.tags, {
    Name = "${var.name}-public-zone"
    Type = "public"
  })
}

# Private zone for internal service discovery within the VPC.
resource "aws_route53_zone" "private" {
  name = local.private_zone_name

  vpc {
    vpc_id = var.vpc_id
  }

  tags = merge(var.tags, {
    Name = "${var.name}-private-zone"
    Type = "private"
  })
}
