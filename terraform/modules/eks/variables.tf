variable "name" {
  description = "name prefix"
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  description = "subnets the control plane + node groups attach to"
  type        = list(string)
}

variable "kubernetes_version" {
  description = "EKS minor. bump cluster + addons together."
  type        = string
  default     = "1.30"
}

variable "ondemand_instance_type" {
  description = "EC2 type for the on-demand pool. has to fit kubelet + the EKS DaemonSets (CNI, kube-proxy, ebs-csi) + workload pods. t3.medium just barely does."
  type        = string
  default     = "t3.medium"
}

variable "spot_instance_types" {
  description = "candidates for the spot pool; AWS picks the cheapest available match at fulfillment"
  type        = list(string)
  default     = ["t3.small", "t3a.small", "t3.medium", "t3a.medium"]
}

variable "ondemand_desired_size" {
  description = "steady-state node count"
  type        = number
  default     = 2
}

variable "ondemand_min_size" {
  type    = number
  default = 2
}

variable "ondemand_max_size" {
  description = "cluster-autoscaler upper bound for the on-demand pool"
  type        = number
  default     = 5
}

variable "spot_desired_size" {
  description = "spot pool desired. 0 = pool sits empty until something tolerates the taint."
  type        = number
  default     = 0
}

variable "spot_min_size" {
  type    = number
  default = 0
}

variable "spot_max_size" {
  type    = number
  default = 3
}

variable "extra_cluster_sg_ingress_sg_ids" {
  # map of stable-key -> sg id allowed to reach the EKS API on 443.
  # keys have to be known at plan time (no derived-from-module-output);
  # typical use: { tailscale = module.tailscale_subnet_router.security_group_id }
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
