variable "name" {
  description = "name prefix"
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  description = "public subnet"
  type        = string
}

variable "instance_type" {
  description = "x86_64 burstable; runs sshd + tailscale + fail2ban"
  type        = string
  default     = "t3.nano"
}

variable "allowed_ssh_cidr" {
  description = "source CIDR allowed to SSH. tailscale is the preferred path, keep this tight."
  type        = string
  default     = "0.0.0.0/0"
}

variable "key_name" {
  description = "EC2 key pair. empty => no ssh-key login (tailscale ssh only)."
  type        = string
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
