variable "istio_version" {
  description = "chart version. base + istiod stay aligned; bump alongside the sidecar image in helm/openproject-mcp."
  type        = string
  default     = "1.23.2"
}

variable "cluster_name" {
  description = "EKS cluster name. lands on istiod's global.multiCluster.clusterName so future multi-cluster topologies have a stable identity."
  type        = string
}

variable "mesh_id" {
  description = "mesh id; same value across clusters joining the same mesh"
  type        = string
  default     = "openproject-mcp"
}

variable "network_name" {
  # logical network. shows up on topology.istio.io/network on istio-system
  # and each app namespace.
  type    = string
  default = "openproject-mcp-network"
}

variable "namespace_labels" {
  description = "extra labels on istio-system. topology.istio.io/network is always added by the module."
  type        = map(string)
  default     = {}
}

variable "istiod_cpu_request" {
  description = "pilot.resources.requests.cpu"
  type        = string
  default     = "100m"
}

variable "istiod_memory_request" {
  type    = string
  default = "512Mi"
}
