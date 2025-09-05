terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70"
    }
  }
}

# Jenkins lives in the management account. Each member account holds
# a role Jenkins can AssumeRole into for the per-env deploy stages.

data "aws_iam_policy_document" "jenkins_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.management_account_id}:root"]
    }
  }
}

resource "aws_iam_role" "jenkins_deploy" {
  name               = "openproject-mcp-jenkins-deploy"
  description        = "Cross-account deploy role - assumed by jenkins in the management acct"
  assume_role_policy = data.aws_iam_policy_document.jenkins_trust.json

  tags = merge(var.tags, {
    Name = "${var.name}-jenkins-deploy"
  })
}

locals {
  jenkins_managed_policies = [
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess",
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/SecretsManagerReadWrite",
    "arn:aws:iam::aws:policy/AmazonS3FullAccess",
    "arn:aws:iam::aws:policy/AmazonRoute53FullAccess",
  ]
}

resource "aws_iam_role_policy_attachment" "jenkins_managed" {
  for_each   = toset(local.jenkins_managed_policies)
  role       = aws_iam_role.jenkins_deploy.name
  policy_arn = each.value
}

data "aws_iam_policy_document" "jenkins_pass_role" {
  statement {
    actions = [
      "iam:PassRole",
      "iam:GetRole",
      "iam:ListRoles",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "jenkins_pass_role" {
  name   = "openproject-mcp-jenkins-pass-role"
  role   = aws_iam_role.jenkins_deploy.id
  policy = data.aws_iam_policy_document.jenkins_pass_role.json
}
