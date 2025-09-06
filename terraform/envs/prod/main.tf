# prod env wiring. keep diff vs envs/dev minimal so promotion is a copy.

module "vpc" {
  source = "../../modules/vpc"

  name       = "openproject-mcp-${var.subdomain}"
  cidr_block = var.vpc_cidr
  tags       = local.common_tags
}

module "tailscale_subnet_router" {
  source = "../../modules/tailscale_subnet_router"

  name             = "openproject-mcp-${var.subdomain}"
  vpc_id           = module.vpc.vpc_id
  subnet_id        = module.vpc.public_subnet_ids[0]
  advertise_routes = [var.vpc_cidr]
  tags             = local.common_tags
}

module "route53" {
  source = "../../modules/route53"

  name         = "openproject-mcp-${var.subdomain}"
  domain       = var.domain
  subdomain    = var.subdomain
  is_root_zone = false
  vpc_id       = module.vpc.vpc_id
  tags         = local.common_tags
}

module "eks" {
  source = "../../modules/eks"

  name               = "openproject-mcp-${var.subdomain}"
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  kubernetes_version = "1.30"

  ondemand_desired_size = 3
  ondemand_min_size     = 2
  ondemand_max_size     = 5
  spot_max_size         = 3

  # tailnet sg needs to reach the private EKS API on 443.
  # without this rule, kubectl times out on cold apply until i poke
  # the sg by hand.
  extra_cluster_sg_ingress_sg_ids = { tailscale = module.tailscale_subnet_router.security_group_id }

  tags = local.common_tags
}

module "rds" {
  source = "../../modules/rds"

  name                       = "openproject-mcp-${var.subdomain}"
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.intra_subnet_ids
  allowed_security_group_ids = module.eks.node_security_group_ids

  instance_class      = "db.t4g.micro"
  allocated_storage   = 20
  multi_az            = false
  skip_final_snapshot = true
  deletion_protection = false

  tags = local.common_tags
}

module "msk" {
  source = "../../modules/msk"

  name                       = "openproject-mcp-${var.subdomain}"
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_subnet_ids
  allowed_security_group_ids = module.eks.node_security_group_ids

  number_of_broker_nodes = 3

  tags = local.common_tags
}

module "observability" {
  source = "../../modules/observability"

  name               = "openproject-mcp-${var.subdomain}"
  log_retention_days = 14
  # flip on once AMG SSO is wired in the console
  enable_managed_grafana = false

  tags = local.common_tags
}

# istio control plane via upstream helm charts. gated on var.deploy_istio
# so a cold apply against an empty account brings up EKS first and only
# then flips this on (two-pass apply, same as enable_irsa).
module "istio" {
  count  = var.deploy_istio ? 1 : 0
  source = "../../modules/istio"

  cluster_name = module.eks.cluster_name
  mesh_id      = "openproject-mcp"
  network_name = "openproject-mcp-${var.subdomain}"
}

module "iam" {
  source = "../../modules/iam"

  name                  = "openproject-mcp-${var.subdomain}"
  management_account_id = "772147490037"

  enable_irsa       = true
  oidc_provider_arn = module.eks.oidc_provider_arn
  msk_cluster_arn   = module.msk.cluster_arn
  rds_secret_arn    = module.rds.secret_arn
  route53_zone_arns = [
    "arn:aws:route53:::hostedzone/${module.route53.public_zone_id}",
    "arn:aws:route53:::hostedzone/${module.route53.private_zone_id}",
  ]
  external_secrets_extra_prefixes = ["openproject", "openproject-mcp"]
  external_secrets_kms_key_arns   = [module.rds.kms_key_arn]

  tags = local.common_tags
}

# openproject.t3ja.com CNAME -> istio ingress LB.
# target hostname comes from `kubectl get svc -n istio-system istio-ingressgateway`
# once the chart is up; the bench script writes it back into tfvars.
resource "aws_route53_record" "openproject" {
  count = var.deploy_openproject ? 1 : 0

  zone_id = module.route53.public_zone_id
  name    = "openproject.${var.subdomain}.${var.domain}"
  type    = "CNAME"
  ttl     = 60
  records = [var.istio_ingress_lb_hostname]
}

# secrets the helm/openproject chart consumes via ESO: db password,
# rails SECRET_KEY_BASE, admin user password. random_password generates
# the values, ESO syncs them into kube Secrets at install time.
# TODO bump recovery_window_in_days before flipping deploy_openproject on.
resource "random_password" "openproject_db" {
  count   = var.deploy_openproject ? 1 : 0
  length  = 32
  special = false
}

resource "random_password" "openproject_secret_key_base" {
  count   = var.deploy_openproject ? 1 : 0
  length  = 64
  special = false
}

resource "random_password" "openproject_admin" {
  count   = var.deploy_openproject ? 1 : 0
  length  = 24
  special = true
}

resource "aws_secretsmanager_secret" "openproject_db" {
  count                   = var.deploy_openproject ? 1 : 0
  name                    = "openproject/${var.subdomain}/db-password"
  recovery_window_in_days = 0
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "openproject_db" {
  count         = var.deploy_openproject ? 1 : 0
  secret_id     = aws_secretsmanager_secret.openproject_db[0].id
  secret_string = random_password.openproject_db[0].result
}

resource "aws_secretsmanager_secret" "openproject_secret_key_base" {
  count                   = var.deploy_openproject ? 1 : 0
  name                    = "openproject/${var.subdomain}/secret-key-base"
  recovery_window_in_days = 0
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "openproject_secret_key_base" {
  count         = var.deploy_openproject ? 1 : 0
  secret_id     = aws_secretsmanager_secret.openproject_secret_key_base[0].id
  secret_string = random_password.openproject_secret_key_base[0].result
}

resource "aws_secretsmanager_secret" "openproject_admin" {
  count                   = var.deploy_openproject ? 1 : 0
  name                    = "openproject/${var.subdomain}/admin-password"
  recovery_window_in_days = 0
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "openproject_admin" {
  count         = var.deploy_openproject ? 1 : 0
  secret_id     = aws_secretsmanager_secret.openproject_admin[0].id
  secret_string = random_password.openproject_admin[0].result
}

# mcp-server side: OpenProject API token (REST API on behalf of the
# agent) and HMAC secret (signs webhook callbacks). same gate as the
# openproject secrets above since these only matter when both charts run.
resource "random_password" "openproject_api_key" {
  count   = var.deploy_openproject ? 1 : 0
  length  = 48
  special = false
}

resource "random_password" "webhook_hmac_secret" {
  count   = var.deploy_openproject ? 1 : 0
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "openproject_api_key" {
  count                   = var.deploy_openproject ? 1 : 0
  name                    = "openproject-mcp/${var.subdomain}/openproject-api-key"
  recovery_window_in_days = 0
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "openproject_api_key" {
  count         = var.deploy_openproject ? 1 : 0
  secret_id     = aws_secretsmanager_secret.openproject_api_key[0].id
  secret_string = random_password.openproject_api_key[0].result
}

resource "aws_secretsmanager_secret" "webhook_hmac_secret" {
  count                   = var.deploy_openproject ? 1 : 0
  name                    = "openproject-mcp/${var.subdomain}/webhook-hmac-secret"
  recovery_window_in_days = 0
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "webhook_hmac_secret" {
  count         = var.deploy_openproject ? 1 : 0
  secret_id     = aws_secretsmanager_secret.webhook_hmac_secret[0].id
  secret_string = random_password.webhook_hmac_secret[0].result
}
