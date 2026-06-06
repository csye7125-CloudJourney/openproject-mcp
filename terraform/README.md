# terraform/

Per-account stacks for openproject-mcp. Profile-per-account; AssumeRole
isn't done at the TF layer. Jenkins handles cross-account stuff at the
pipeline layer instead.

## Layout

```
terraform/
  bootstrap/        one-shot state bucket + lock table. RUN FIRST per env.
  envs/
    dev/            account: openproject-mcp-dev     (938184884486)
    staging/        account: openproject-mcp-staging (875285643901)
    prod/           account: openproject-mcp-prod    (137451610850)
  modules/
    vpc/            3az vpc + igw + nat + flow logs
    vpc_peering/    cross-vpc peering helper
    bastion/        hardened t3.nano (fallback; tailscale is the daily path)
    route53/        public + private zones, root vs subdomain mode
    iam/            jenkins-deploy cross-account role + irsa
    eks/            cluster + node groups + addons
    rds/            postgres15, secrets manager creds
    msk/            kafka, SASL/IAM auth
    observability/  cloudwatch log groups + AMP + AMG
    istio/          control plane via helm
    tailscale_subnet_router/  ec2 advertising the vpc cidr to the tailnet
```

## First run, per env

```bash
# 1. set up named profile (one-time per account)
aws configure --profile openproject-mcp-dev

# 2. bring up the state bucket + lock table
cd terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars
# edit aws_profile = "openproject-mcp-dev"
terraform init
terraform apply

# 3. now apply the env stack
cd ../envs/dev
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## CIDR map (non-overlapping for peering)

| Env     | IPv4 CIDR     |
|---------|---------------|
| dev     | 10.10.0.0/16  |
| staging | 10.20.0.0/16  |
| prod    | 10.30.0.0/16  |

IPv6 blocks come from `assign_generated_ipv6_cidr_block = true` in the
vpc module; AWS hands out a /56 per VPC so overlap isn't a concern.

## Promoting changes dev -> staging -> prod

The env dirs are diff-clean by design. To roll out a change:

1. Land it in `envs/dev/`, plan + apply
2. Copy the same edit into `envs/staging/`, plan + apply
3. Same for `envs/prod/`

Modules are shared so `modules/` only ever moves forward once.

## Verify before commit

```bash
terraform fmt -check -recursive .
( cd envs/dev     && terraform init -backend=false && terraform validate )
( cd envs/staging && terraform init -backend=false && terraform validate )
( cd envs/prod    && terraform init -backend=false && terraform validate )
( cd bootstrap    && terraform init -backend=false && terraform validate )
```
