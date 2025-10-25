output "namespace" {
  description = "istio-system namespace name; use when labeling app namespaces or wiring observability scrapes"
  value       = kubernetes_namespace.istio_system.metadata[0].name
}

output "istiod_release_name" {
  value = helm_release.istiod.name
}

output "chart_version" {
  description = "pinned chart version (base + istiod stay aligned)"
  value       = var.istio_version
}
