terraform {
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

resource "kubernetes_namespace" "istio_system" {
  metadata {
    name = "istio-system"
    labels = merge(var.namespace_labels, {
      "topology.istio.io/network" = var.network_name
    })
  }
}

resource "helm_release" "istio_base" {
  name       = "istio-base"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "base"
  version    = var.istio_version
  namespace  = kubernetes_namespace.istio_system.metadata[0].name
  timeout    = 300

  values = [yamlencode({
    defaultRevision = "default"
  })]
}

resource "helm_release" "istiod" {
  name       = "istiod"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "istiod"
  version    = var.istio_version
  namespace  = kubernetes_namespace.istio_system.metadata[0].name
  timeout    = 300

  values = [yamlencode({
    pilot = {
      resources = {
        requests = {
          cpu    = var.istiod_cpu_request
          memory = var.istiod_memory_request
        }
      }
      autoscaleEnabled = false
      replicaCount     = 1
    }
    global = {
      meshID       = var.mesh_id
      multiCluster = { clusterName = var.cluster_name }
      network      = var.network_name
    }
    meshConfig = {
      accessLogFile = "/dev/stdout"
      defaultConfig = {
        proxyMetadata = {
          ISTIO_META_DNS_CAPTURE       = "true"
          ISTIO_META_DNS_AUTO_ALLOCATE = "true"
        }
      }
    }
  })]

  depends_on = [helm_release.istio_base]
}
