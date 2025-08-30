variable "name" {
  description = "name prefix"
  type        = string
}

variable "cidr_block" {
  description = "primary IPv4 CIDR"
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
