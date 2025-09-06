variable "aws_profile" {
  description = "named AWS profile; also drives the environment label"
  type        = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "domain" {
  description = "apex domain. prod owns the public zone, dev/staging delegate from it."
  type        = string
  default     = "t3ja.com"
}

variable "subdomain" {
  description = "per-env subdomain label. prod uses the bare apex."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "vpc cidr"
  type        = string
  default     = "10.10.0.0/16"
}

variable "allowed_ssh_cidr" {
  description = "source CIDR allowed to SSH the bastion (tailscale is the preferred path)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "deploy_istio" {
  # two-pass apply like enable_irsa. first run: false, so the helm +
  # kubernetes providers don't try to dial a cluster that doesn't exist.
  # flip to true once EKS is up and the API is reachable.
  type    = bool
  default = false
}

variable "deploy_openproject" {
  # flips on the Route53 CNAME + Secrets Manager entries the openproject
  # helm release wants. off by default; only on during a bench session.
  type    = bool
  default = false
}

variable "istio_ingress_lb_hostname" {
  description = "istio ingress gateway LB hostname (abc123.elb.amazonaws.com). populated by the bench script from `kubectl get svc -n istio-system istio-ingressgateway`. only consumed when deploy_openproject=true."
  type        = string
  default     = ""
}
