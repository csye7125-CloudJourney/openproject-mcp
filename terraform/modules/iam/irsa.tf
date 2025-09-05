# IRSA roles. Each role trusts the cluster's OIDC provider for a
# specific service account, then attaches the policy the workload
# needs. var.oidc_provider_arn empty => everything in this file no-ops
# so the module is still consumable before EKS lands.

locals {
  irsa_enabled = var.enable_irsa
  # Derive issuer hostpath from arn: arn:aws:iam::ACCT:oidc-provider/oidc.eks.region.amazonaws.com/id/HEX
  # We split on "oidc-provider/" because that's the stable delimiter.
  oidc_issuer = local.irsa_enabled ? split("oidc-provider/", var.oidc_provider_arn)[1] : ""
}

data "aws_iam_policy_document" "irsa_assume" {
  for_each = local.irsa_enabled ? var.irsa_service_accounts : {}

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_issuer}:sub"
      values   = ["system:serviceaccount:${each.value.namespace}:${each.value.service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

# Generic role per service-account binding. Policies attach in the
# workload-specific files (mcp_server.tf, external_secrets.tf, etc).
resource "aws_iam_role" "irsa" {
  for_each = local.irsa_enabled ? var.irsa_service_accounts : {}

  name               = "${var.name}-irsa-${each.key}"
  description        = "IRSA role for ${each.value.namespace}/${each.value.service_account}"
  assume_role_policy = data.aws_iam_policy_document.irsa_assume[each.key].json

  tags = merge(var.tags, {
    Name      = "${var.name}-irsa-${each.key}"
    Workload  = each.key
    Namespace = each.value.namespace
  })
}
