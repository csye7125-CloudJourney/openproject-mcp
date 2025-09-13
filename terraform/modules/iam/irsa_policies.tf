# Workload-specific policies attached to each IRSA role. Each block is
# gated on the role being present (oidc_provider_arn populated) AND
# the relevant upstream resource arn being passed in.

# ---------------------------------------------------------------------
# mcp-server: writes events to MSK + reads artifact bundles from S3
# ---------------------------------------------------------------------
data "aws_iam_policy_document" "mcp_server" {
  count = local.irsa_enabled ? 1 : 0

  statement {
    sid = "MskClusterAccess"
    actions = [
      "kafka-cluster:Connect",
      "kafka-cluster:DescribeCluster",
      "kafka-cluster:DescribeClusterDynamicConfiguration",
    ]
    resources = [var.msk_cluster_arn]
  }

  statement {
    sid = "MskTopicAccess"
    actions = [
      "kafka-cluster:CreateTopic",
      "kafka-cluster:DescribeTopic",
      "kafka-cluster:DescribeTopicDynamicConfiguration",
      "kafka-cluster:WriteData",
      "kafka-cluster:ReadData",
    ]
    # MSK ARN format for topics: arn:aws:kafka:region:acct:topic/cluster_name/uuid/*
    # Derive from cluster_arn: swap the "cluster/" prefix for "topic/".
    resources = [
      replace(var.msk_cluster_arn, ":cluster/", ":topic/"),
      "${replace(var.msk_cluster_arn, ":cluster/", ":topic/")}/*",
    ]
  }

  statement {
    sid = "MskGroupAccess"
    actions = [
      "kafka-cluster:AlterGroup",
      "kafka-cluster:DescribeGroup",
    ]
    resources = [
      replace(var.msk_cluster_arn, ":cluster/", ":group/"),
      "${replace(var.msk_cluster_arn, ":cluster/", ":group/")}/*",
    ]
  }

  statement {
    sid = "ArtifactsRead"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::${var.name}-artifacts",
      "arn:aws:s3:::${var.name}-artifacts/*",
    ]
  }
}

resource "aws_iam_role_policy" "mcp_server" {
  count = local.irsa_enabled ? 1 : 0

  name   = "${var.name}-mcp-server"
  role   = aws_iam_role.irsa["mcp_server"].id
  policy = data.aws_iam_policy_document.mcp_server[0].json
}

# ---------------------------------------------------------------------
# external-secrets: pulls Secrets Manager values into K8s Secret objects
# ---------------------------------------------------------------------
data "aws_iam_policy_document" "external_secrets" {
  count = local.irsa_enabled ? 1 : 0

  statement {
    sid = "SecretsRead"
    actions = [
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:ListSecretVersionIds",
    ]
    # All openproject-mcp-prefixed secrets, plus the explicitly-passed
    # rds secret arn when present, plus any extra prefixes the env opts in
    # to (e.g. self-hosted OpenProject puts its secrets under openproject/*).
    resources = compact(concat(
      [
        "arn:aws:secretsmanager:*:*:secret:${var.name}/*",
        var.rds_secret_arn,
      ],
      [for p in var.external_secrets_extra_prefixes : "arn:aws:secretsmanager:*:*:secret:${p}/*"],
    ))
  }

  # AWS Secrets Manager transparently decrypts via KMS when the secret is
  # encrypted with a customer-managed key. Calling secretsmanager:GetSecretValue
  # on those secrets without kms:Decrypt on the underlying key returns
  # AccessDeniedException: Access to KMS is not allowed. Scope to keys the
  # env explicitly opts in to.
  dynamic "statement" {
    for_each = length(var.external_secrets_kms_key_arns) > 0 ? [1] : []
    content {
      sid = "KmsDecrypt"
      actions = [
        "kms:Decrypt",
        "kms:DescribeKey",
      ]
      resources = var.external_secrets_kms_key_arns
    }
  }

  statement {
    sid = "SecretsList"
    actions = [
      "secretsmanager:ListSecrets",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "external_secrets" {
  count = local.irsa_enabled ? 1 : 0

  name   = "${var.name}-external-secrets"
  role   = aws_iam_role.irsa["external_secrets"].id
  policy = data.aws_iam_policy_document.external_secrets[0].json
}

# ---------------------------------------------------------------------
# external-dns: writes A/CNAME records into the env hosted zone
# ---------------------------------------------------------------------
data "aws_iam_policy_document" "external_dns" {
  count = local.irsa_enabled && length(var.route53_zone_arns) > 0 ? 1 : 0

  statement {
    sid = "ZoneChange"
    actions = [
      "route53:ChangeResourceRecordSets",
    ]
    resources = var.route53_zone_arns
  }

  statement {
    sid = "ZoneList"
    actions = [
      "route53:ListHostedZones",
      "route53:ListResourceRecordSets",
      "route53:ListTagsForResource",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "external_dns" {
  count = local.irsa_enabled && length(var.route53_zone_arns) > 0 ? 1 : 0

  name   = "${var.name}-external-dns"
  role   = aws_iam_role.irsa["external_dns"].id
  policy = data.aws_iam_policy_document.external_dns[0].json
}

# ---------------------------------------------------------------------
# cluster-autoscaler: scales the managed node groups
# ---------------------------------------------------------------------
data "aws_iam_policy_document" "cluster_autoscaler" {
  count = local.irsa_enabled ? 1 : 0

  statement {
    sid = "DescribeAll"
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:DescribeLaunchConfigurations",
      "autoscaling:DescribeScalingActivities",
      "autoscaling:DescribeTags",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplateVersions",
      "ec2:DescribeImages",
      "ec2:GetInstanceTypesFromInstanceRequirements",
      "eks:DescribeNodegroup",
    ]
    resources = ["*"]
  }

  statement {
    sid = "Mutate"
    actions = [
      "autoscaling:SetDesiredCapacity",
      "autoscaling:TerminateInstanceInAutoScalingGroup",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/k8s.io/cluster-autoscaler/enabled"
      values   = ["true"]
    }
  }
}

resource "aws_iam_role_policy" "cluster_autoscaler" {
  count = local.irsa_enabled ? 1 : 0

  name   = "${var.name}-cluster-autoscaler"
  role   = aws_iam_role.irsa["cluster_autoscaler"].id
  policy = data.aws_iam_policy_document.cluster_autoscaler[0].json
}
