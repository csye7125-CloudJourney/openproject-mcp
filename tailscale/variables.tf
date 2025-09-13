variable "env" {
  description = "Environment label - feeds into the operator hostname so multiple envs in one tailnet are distinguishable."
  type        = string
}

variable "operator_chart_version" {
  description = "Tailscale operator helm chart version. Pin per env."
  type        = string
  default     = "1.74.0"
}

variable "oauth_client_id" {
  description = "Tailscale OAuth client id. The secret comes from the external data source (env.local file)."
  type        = string
  default     = "" # passed in from the env stack; empty makes init fail loudly when wired
}
