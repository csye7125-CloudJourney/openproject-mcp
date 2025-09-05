variable "name" {
  description = "name prefix"
  type        = string
}

variable "requester_vpc_id" {
  type = string
}

variable "requester_cidr" {
  description = "requester VPC IPv4 CIDR. written into the accepter's route tables."
  type        = string
}

variable "requester_route_table_ids" {
  description = "rt ids on the requester side that need the peer route"
  type        = list(string)
  default     = []
}

variable "accepter_vpc_id" {
  type = string
}

variable "accepter_cidr" {
  description = "accepter VPC IPv4 CIDR. written into the requester's route tables."
  type        = string
}

variable "accepter_route_table_ids" {
  description = "rt ids on the accepter side that need the peer route"
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
