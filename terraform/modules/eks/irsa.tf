# OIDC provider; lets service accounts AssumeRoleWithWebIdentity into IAM
# roles (IRSA). actual role-per-SA wiring lives in modules/iam/irsa.tf and
# consumes the outputs below.

data "tls_certificate" "oidc" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "this" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.oidc.certificates[0].sha1_fingerprint]

  tags = merge(var.tags, {
    Name = "${var.name}-eks-oidc"
  })
}
