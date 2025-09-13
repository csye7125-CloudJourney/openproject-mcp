# Tailscale Kubernetes Operator install. Runs in its own namespace, owns
# Tailscale-managed Service exposure (the `tailscale.com/expose` annotation
# in the helm chart's service.yaml) and the subnet router that lets the
# tailnet reach the cluster's internal subnets.
#
# Auth key sourcing: we read from the user's local secrets file at
# ~/.config/openproject-mcp/.env.local (chmod 600, not in repo). The
# `external` data source shells out to a tiny script that emits JSON.
# Alternative considered: `pass openproject-mcp/tailscale-authkey`. Went
# with the env.local file because every dev box already has that path,
# whereas `pass` requires GPG setup.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30"
    }
    external = {
      source  = "hashicorp/external"
      version = ">= 2.3"
    }
  }
}

data "external" "tailscale_authkey" {
  program = ["bash", "-c", <<-SCRIPT
    set -euo pipefail
    f="$${HOME}/.config/openproject-mcp/.env.local"
    if [[ ! -r "$f" ]]; then
      echo '{"value":""}' && exit 0
    fi
    key=$(grep -E '^TAILSCALE_AUTHKEY=' "$f" | head -1 | cut -d= -f2- | tr -d '"' || true)
    printf '{"value":"%s"}\n' "$${key:-}"
  SCRIPT
  ]
}

resource "kubernetes_namespace" "tailscale" {
  metadata {
    name = "tailscale"
    labels = {
      "app.kubernetes.io/managed-by"       = "terraform"
      "pod-security.kubernetes.io/enforce" = "privileged"
    }
  }
}

resource "helm_release" "tailscale_operator" {
  name       = "tailscale-operator"
  repository = "https://pkgs.tailscale.com/helmcharts"
  chart      = "tailscale-operator"
  version    = var.operator_chart_version
  namespace  = kubernetes_namespace.tailscale.metadata[0].name

  set {
    name  = "oauth.clientId"
    value = var.oauth_client_id
  }

  set_sensitive {
    name  = "oauth.clientSecret"
    value = data.external.tailscale_authkey.result.value
  }

  set {
    name  = "apiServerProxyConfig.mode"
    value = "true"
  }

  values = [yamlencode({
    operatorConfig = {
      hostname    = "tailscale-operator-${var.env}"
      defaultTags = ["tag:k8s-operator"]
    }
  })]

  depends_on = [kubernetes_namespace.tailscale]
}
