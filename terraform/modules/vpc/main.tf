terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70"
    }
  }
}

# vpc + ipv6 block. subnets/igw/nat/flow-logs are in sibling files.
resource "aws_vpc" "this" {
  cidr_block                       = var.cidr_block
  assign_generated_ipv6_cidr_block = true
  enable_dns_hostnames             = true
  enable_dns_support               = true

  tags = merge(var.tags, {
    Name = "${var.name}-vpc"
  })
}
