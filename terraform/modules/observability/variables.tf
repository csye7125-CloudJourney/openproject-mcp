variable "name" {
  description = "name prefix"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch retention. 14d default; prod wants 30+."
  type        = number
  default     = 14
}

variable "enable_managed_grafana" {
  # SSO group mapping is a console step so leave AMG off until that's done.
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
