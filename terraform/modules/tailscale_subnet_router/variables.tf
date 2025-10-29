variable "name" {
  description = "name prefix"
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  description = "public subnet; instance needs outbound to talk to Tailscale coordination"
  type        = string
}

variable "advertise_routes" {
  description = "CIDRs the router exposes to the tailnet. Typically the VPC CIDR."
  type        = list(string)
}

variable "tailscale_auth_key_secret_name" {
  # Secrets Manager entry holding the Tailscale auth key. created out-of-band
  # via `aws secretsmanager create-secret` so the value stays out of TF state.
  type    = string
  default = "openproject-mcp/tailscale/auth-key"
}

variable "instance_type" {
  description = "EC2 type. box just forwards packets."
  type        = string
  default     = "t3.nano"
}

variable "advertise_tags" {
  description = "tailnet tags applied to this node. must already exist in tailnet ACLs."
  type        = list(string)
  default     = ["tag:cloud-vm"]
}

variable "tags" {
  type    = map(string)
  default = {}
}
