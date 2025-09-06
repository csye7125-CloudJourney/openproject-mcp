variable "name" {
  description = "name prefix"
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "intra subnets, multiple AZs"
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "sgs allowed to hit 5432 (eks node sg)"
  type        = list(string)
}

variable "engine_version" {
  description = "Postgres minor. AWS's supported-version list drifts every few months so pin per env and bump intentionally."
  type        = string
  default     = "15.7"
}

variable "instance_class" {
  description = "RDS instance class. Graviton t4g family runs PG just fine at lower cost."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "initial gp3 storage in GiB. AWS floor on PG is 20."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "upper bound for storage autoscaling"
  type        = number
  default     = 500
}

variable "db_name" {
  type    = string
  default = "openproject"
}

variable "master_username" {
  description = "master user. password is auto-generated + held in Secrets Manager."
  type        = string
  default     = "openproject_admin"
}

variable "multi_az" {
  description = "standby in a second AZ. on for prod."
  type        = bool
  default     = false
}

variable "backup_retention_period" {
  description = "daily snapshot retention in days"
  type        = number
  default     = 7
}

variable "deletion_protection" {
  # flip false before destroying dev. otherwise terraform destroy fails
  # with a not-very-helpful error and you go hunt for this var.
  type    = bool
  default = true
}

variable "skip_final_snapshot" {
  description = "true only on dev. prod must snapshot on destroy."
  type        = bool
  default     = false
}

variable "rotation_lambda_arn" {
  description = "ARN of AWS-published SecretsManagerRDSPostgreSQLRotationSingleUser. empty = no rotation (dev only)."
  type        = string
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
