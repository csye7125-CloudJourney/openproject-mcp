# helm/openproject

Wrapper around the upstream `opf/openproject` Helm chart. Self-hosted
OpenProject for environments that don't have an external instance to
point at. The MCP server (sibling chart `helm/openproject-mcp/`) talks
to this OpenProject; the k6 harness drives traffic against the MCP,
which fans out webhook events into MSK.

Gated end-to-end by `var.deploy_openproject = true` in
`terraform/envs/{dev,staging,prod}/`. Default is false so a normal
`terraform apply` doesn't spin OpenProject up.

## Why this wrapper exists

`opf/openproject` is the upstream community chart. The wrapper layers
on the bits that don't fit the subchart values surface.

Istio routing: upstream ships an Ingress resource, but we run Istio
with one shared gateway (`istio/gateway.yaml`) and a VirtualService
per backend. The wrapper adds the VirtualService + DestinationRule and
disables the subchart Ingress.

External secrets: upstream wants kube Secrets present at install time.
The wrapper renders `ExternalSecret` objects that pull DB password,
`SECRET_KEY_BASE`, and admin password from AWS Secrets Manager via
External-Secrets-Operator.

Seed job: a Helm post-install hook Job loads OpenProject's stock seed
data plus a synthetic dataset (N projects x M work packages) so the
load harness has real volume to hit.

## Choice: opf/openproject over bitnami/openproject

Picked `opf/openproject` (upstream OpenProject org) over the
`bitnami/openproject` chart because:

- opf tracks the Rails ENV map directly - `externalDatabase`,
  `existingSecret`, `attachments_storage` keys are the names the rails
  app reads
- bitnami bundles its own postgresql + memcached subcharts which we
  don't need (we use external RDS + a tiny in-cluster memcached)
- opf is what the OpenProject docs reference, so docs are accurate

Pinned at `5.0.5` in `Chart.yaml` - bump manually.

## Prerequisites

Per cluster, install order matters:

1. `helm/addons/` - installs External-Secrets-Operator +
   the `aws-secrets-manager` `ClusterSecretStore`. Without this the
   `ExternalSecret` resources here have nothing to sync from.
2. Istio control plane + `istio/gateway.yaml` + `openproject-mcp`
   namespace.
3. Terraform applied with `deploy_openproject = true` in the target
   env (see below).

RDS prerequisite:

- The shared RDS instance from `terraform/modules/rds` must exist with
  an admin user (`openproject_admin` by default) and the RDS-side
  master secret synced to AWS Secrets Manager at
  `openproject-mcp-<env>/rds/master`. The chart now creates the
  `openproject` database + `openproject` user itself via the
  `db-bootstrap` Helm hook (see "first install" below), so no manual
  `psql` step is required. Terraform still doesn't manage the postgres
  provider here - the bootstrap Job is what fills that gap from
  inside the cluster.

## First install - db bootstrap

The chart ships a `pre-install,pre-upgrade` Helm hook Job
(`templates/db-bootstrap-job.yaml`) that runs a `postgres:15` pod
against RDS as the admin user and idempotently:

1. Creates the `openproject` postgres role if it doesn't exist
2. Resets that role's password to whatever the `openproject-db` kube
   Secret (synced from Secrets Manager) currently holds
3. Creates the `openproject` database if it doesn't exist
4. Grants `ALL PRIVILEGES ON DATABASE openproject` to the role

All four steps are gated on existence checks so re-running on every
`helm upgrade` is a no-op past the initial bootstrap. The Job's
delete policy is `before-hook-creation,hook-succeeded` so completed
pods don't pile up in the namespace.

Credentials wire-up: `PGPASSWORD` comes from the `openproject-rds-master`
kube Secret (synced from `rds.masterSecretId` by ESO), and the OP user
password the Job sets comes from the same `openproject-db` Secret the
rails pod reads. Flip `dbBootstrap.enabled=false` (default in
`values-prod.yaml`) when a DBA owns the OP database out of band.

## Install

```bash
# 1. terraform - flip the flag, populate the ingress LB hostname.
cd terraform/envs/dev
LB=$(kubectl -n istio-system get svc istio-ingressgateway \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
terraform apply -var deploy_openproject=true -var istio_ingress_lb_hostname="${LB}"

# 2. helm dependency update - pulls opf/openproject into charts/
cd ../../..
helm repo add openproject https://charts.openproject.org
helm dependency update helm/openproject/

# 3. helm install with the rds endpoint from terraform output.
RDS=$(cd terraform/envs/dev && terraform output -raw rds_endpoint)
helm install openproject helm/openproject/ \
  -n openproject-mcp \
  --create-namespace \
  --set rds.endpoint="${RDS}" \
  --set openproject.externalDatabase.host="${RDS}" \
  --set host=openproject.dev.t3ja.com \
  --wait --timeout 10m

# 4. optional - seed load data (post-install hook Job).
helm upgrade openproject helm/openproject/ \
  -n openproject-mcp \
  --reuse-values \
  --set seed.enabled=true
```

## Post-install - admin setup

OpenProject's first-run wizard wants an admin account. Two paths:

- **Headless via env var (preferred).** The seed Job uses the password
  from Secrets Manager (`openproject/<env>/admin-password`). Login as
  `admin` with that value. Pull it with:
  ```bash
  aws secretsmanager get-secret-value \
    --secret-id openproject/dev/admin-password \
    --query SecretString --output text
  ```
- **Manual wizard.** Browse to `https://openproject.<subdomain>.t3ja.com`
  and walk through the wizard. SMTP and outbound mail must be
  configured here (the chart leaves SMTP placeholders in
  `values.yaml` - flip `openproject.smtp.enabled` on with real values
  when a mail provider is wired).

## Teardown

```bash
helm uninstall openproject -n openproject-mcp
cd terraform/envs/dev
terraform apply -var deploy_openproject=false
```

The attachments PVC and the openproject database in RDS persist by
default - drop them explicitly if you want a clean slate:

```bash
kubectl -n openproject-mcp delete pvc openproject-files
psql -h "${RDS}" -U postgres -c "DROP DATABASE openproject;"
```

## Files

```
helm/openproject/
├── Chart.yaml                          # opf/openproject 5.0.5 dep
├── values.yaml                         # dev defaults
├── values-prod.yaml                    # prod sizing overrides
├── README.md                           # this file
└── templates/
    ├── _helpers.tpl                    # naming + label helpers
    ├── istio-virtualservice.yaml       # routes openproject.<sub>.t3ja.com
    ├── istio-destinationrule.yaml      # ISTIO_MUTUAL + outlier detection
    ├── db-bootstrap-job.yaml           # pre-install hook: CREATE USER/DATABASE
    ├── seed-job.yaml                   # rake seed + synthetic load data
    └── database-secret.yaml            # ExternalSecret for db + rails + rds master
```
