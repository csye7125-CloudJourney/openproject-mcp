variable "name" {
  description = "name prefix (tagging)"
  type        = string
}

variable "domain" {
  description = "apex domain, e.g. t3ja.com"
  type        = string
}

variable "subdomain" {
  description = "per-env subdomain label (dev | staging). ignored if is_root_zone=true."
  type        = string
  default     = ""
}

variable "is_root_zone" {
  # true => this stack owns the apex public zone. prod only.
  type    = bool
  default = false
}

variable "vpc_id" {
  description = "vpc bound to the private hosted zone"
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
