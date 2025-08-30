output "vpc_id" {
  value = aws_vpc.this.id
}

output "vpc_cidr" {
  value = aws_vpc.this.cidr_block
}

output "ipv6_cidr" {
  value = aws_vpc.this.ipv6_cidr_block
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "intra_subnet_ids" {
  value = aws_subnet.intra[*].id
}

output "azs" {
  value = local.azs
}
