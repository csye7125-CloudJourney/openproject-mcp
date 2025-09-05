output "public_zone_id" {
  value = aws_route53_zone.public.zone_id
}

output "public_zone_name" {
  value = aws_route53_zone.public.name
}

output "public_zone_ns" {
  description = "NS records to wire into the parent zone for delegation."
  value       = aws_route53_zone.public.name_servers
}

output "private_zone_id" {
  value = aws_route53_zone.private.zone_id
}

output "private_zone_name" {
  value = aws_route53_zone.private.name
}
