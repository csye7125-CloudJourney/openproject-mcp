variable "name" {
  description = "name prefix"
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "private subnets, multiple AZs; count has to match number_of_broker_nodes"
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "sgs allowed to hit 9098 (eks node sg)"
  type        = list(string)
}

variable "kafka_version" {
  description = "MSK-supported Kafka version"
  type        = string
  default     = "3.6.0"
}

variable "broker_instance_type" {
  description = "broker EC2 type. MSK has no kafka.micro; t3.small is the smallest the API will take."
  type        = string
  default     = "kafka.t3.small"
}

variable "broker_ebs_volume_size" {
  description = "per-broker EBS in GiB (AWS floor: 1)"
  type        = number
  default     = 1
}

variable "number_of_broker_nodes" {
  # has to be a multiple of subnet count so replicas balance across AZs.
  # AWS floor is 2. 3 across 3 AZ subnets is what replication factor 3 needs.
  type    = number
  default = 2
}

variable "tags" {
  type    = map(string)
  default = {}
}
