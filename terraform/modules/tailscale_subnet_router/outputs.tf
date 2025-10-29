output "instance_id" {
  description = "EC2 instance id; useful for SSM if Tailscale fails to come up"
  value       = aws_instance.router.id
}

output "private_ip" {
  description = "VPC-private IP (Tailscale presents this as 100.x.x.x on the tailnet)"
  value       = aws_instance.router.private_ip
}

output "advertised_routes" {
  value = var.advertise_routes
}

output "security_group_id" {
  description = "sg on the router instance. wire into other modules (e.g. EKS cluster SG) so tailnet traffic reaches private endpoints."
  value       = aws_security_group.router.id
}
