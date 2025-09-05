variable "name" {
  description = "name prefix"
  type        = string
}

variable "management_account_id" {
  description = "AWS acct Jenkins runs in. role trust policy points at its root."
  type        = string
  default     = "772147490037"
}

variable "oidc_provider_arn" {
  description = "EKS cluster OIDC provider arn. empty = IRSA wiring skipped."
  type        = string
  default     = ""
}

variable "enable_irsa" {
  # static gate so plan works before EKS exists. first apply: false
  # (only jenkins-deploy role lands). second apply once the OIDC ARN
  # output is populated: flip to true.
  type    = bool
  default = false
}

variable "irsa_service_accounts" {
  description = "workload key -> { namespace, service_account }. policies attach in irsa_policies.tf keyed on the same workload key."
  type = map(object({
    namespace       = string
    service_account = string
  }))
  default = {
    mcp_server = {
      namespace       = "openproject-mcp"
      service_account = "mcp-server"
    }
    external_secrets = {
      namespace       = "external-secrets"
      service_account = "external-secrets"
    }
    external_dns = {
      namespace       = "kube-system"
      service_account = "external-dns"
    }
    cluster_autoscaler = {
      namespace       = "kube-system"
      service_account = "cluster-autoscaler"
    }
  }
}

variable "msk_cluster_arn" {
  description = "MSK cluster ARN for kafka-cluster:* policies. empty disables MSK perms on mcp-server."
  type        = string
  default     = ""
}

variable "rds_secret_arn" {
  description = "RDS master secret ARN read by external-secrets"
  type        = string
  default     = ""
}

variable "external_secrets_extra_prefixes" {
  # extra Secrets Manager prefixes external-secrets can GetSecretValue
  # against, on top of var.name. useful when app secrets sit under a
  # different prefix (self-hosted OpenProject puts things under
  # openproject/<env>/...).
  type    = list(string)
  default = []
}

variable "external_secrets_kms_key_arns" {
  # KMS key ARNs external-secrets is allowed to kms:Decrypt for.
  # needed when a Secrets Manager entry is encrypted with a CMK (RDS
  # master secrets are the usual case here). Secrets Manager decrypts
  # transparently, so without kms:Decrypt on the key, GetSecretValue
  # returns "Access to KMS is not allowed".
  type    = list(string)
  default = []
}

variable "route53_zone_arns" {
  description = "hosted zones external-dns can update"
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
