# tailscale_subnet_router

Small EC2 in a VPC public subnet. Joins the tailnet on boot and
advertises the VPC CIDR so any device on the tailnet can reach
anything inside the VPC at its private IP.

## Why Tailscale

EKS API endpoint here is private-only (`endpointPublicAccess=false`),
so `kubectl get nodes` from a laptop has to enter the VPC somehow.

Options I weighed:

| Path | What | Trade-off |
|---|---|---|
| Public EKS endpoint | flip `endpointPublicAccess=true` | reopens what i just closed; needs IP allowlist + auth that won't always be there |
| Bastion + kubectl proxy | SSH/SSM into bastion in VPC, run kubectl from there | tedious; every command goes through a hop, UI access needs port-forwards |
| Tailscale subnet router | one EC2 in VPC advertises VPC CIDR to tailnet | laptop joins tailnet once, then native `kubectl` + Grafana + Kibana + Jaeger UIs all reachable at private IPs |

Tailscale wins on two practical points: kubectl and the observability
dashboards take the same network path, and tailnet ACLs are identity
based so revoking a laptop is a console toggle instead of a key rotation.
It also pairs cleanly with Istio: tailnet handles laptop -> VPC, Istio
mTLS handles pod -> pod.

Down the road this gets paired with `tailscale/tailscale-operator` via
Helm so individual Services in EKS get tailnet hostnames directly (e.g.
`mcp-server.tailnet-xxxx.ts.net`). The subnet router stays as the
fallback path for the EKS API itself.

## What this module creates

- 1x `t3.nano` EC2 in a public subnet
- IAM role with `AmazonSSMManagedInstanceCore` so SSM still works as a
  backdoor if Tailscale fails to come up on boot
- Security group, outbound only (Tailscale uses NAT traversal)
- User-data:
  - installs Tailscale
  - turns on IPv4/v6 forwarding (sysctl)
  - `tailscale up --authkey=... --advertise-routes=<VPC CIDR> --ssh`
- `source_dest_check = false` (required for subnet routing; AWS otherwise
  blocks packets to/from IPs that don't match the instance)

## First-run setup

**Step 1: create the auth-key secret in Secrets Manager** (one-time per
account, via CLI). 3rd-party API keys belong in Secrets Manager directly;
Terraform references them via data source.

```bash
aws secretsmanager create-secret \
  --name openproject-mcp/tailscale/auth-key \
  --description "Reusable Tailscale auth key" \
  --secret-string "$(grep TAILSCALE_AUTHKEY ~/.config/openproject-mcp/.env.local | cut -d= -f2-)" \
  --tags Key=Project,Value=openproject-mcp Key=ManagedBy,Value=manual-cli \
  --region us-east-1 --profile <env-profile>
```

To rotate: `aws secretsmanager put-secret-value --secret-id openproject-mcp/tailscale/auth-key --secret-string <new-key>`.
Existing router instances keep working; the next launch picks up the new value.

**Step 2: wire the module** (no key arg, defaults to the secret name above):

```hcl
module "tailscale_subnet_router" {
  source = "../../modules/tailscale_subnet_router"

  name             = "openproject-mcp-${var.subdomain}"
  vpc_id           = module.vpc.vpc_id
  subnet_id        = module.vpc.public_subnet_ids[0]
  advertise_routes = [var.vpc_cidr]

  tags = local.common_tags
}

terraform apply
```

After apply, approve the advertised route in the Tailscale admin
console (Machines -> click the new node -> Edit route settings ->
toggle the VPC CIDR on). One-time step; the approval persists across
instance replacements.

## Verify

From the laptop (already on tailnet):

```bash
tailscale status  # should list the new node
ping 10.10.0.1    # VPC's private DNS resolver, sanity check
```

Then `kubectl` against the now-reachable private EKS API.

## When to destroy

Destroy with the rest of the env via `terraform destroy`. Once the
K8s operator is in place, this module reduces to the fallback path
for the EKS API itself.
