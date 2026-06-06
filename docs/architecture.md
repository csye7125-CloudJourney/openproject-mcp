# Architecture

System diagram, the webhook sequence, then the multi-account topology.
Component table at the bottom maps each piece to where it lives in the
repo and what it depends on.

## System

```mermaid
flowchart TB
    subgraph Edge [Edge]
      Laptop[Laptop / Claude Desktop / Cursor]
      OP_UI[OpenProject web UI<br/>openproject.t3ja.com]
    end

    subgraph Mesh [EKS - us-east-1]
      direction LR
      TS[Tailscale operator LB]
      Istio[Istio ingress gateway]
      MCP[mcp-server<br/>Deployment 2-5 replicas<br/>HPA on CPU+mem]
      OPPod[openproject<br/>Deployment + worker]
      OPCache[Memcached]
      Operator[openproject-mcp-operator<br/>Go / Kubebuilder CRD]
    end

    subgraph Data [AWS-managed]
      MSK[(MSK<br/>3x kafka.m5.large<br/>TLS+SASL/IAM)]
      RDS[(RDS Postgres 15.7<br/>multi-AZ KMS-encrypted)]
      SM[(Secrets Manager<br/>90d rotation)]
    end

    subgraph Obs [Observability]
      Prom[Prometheus]
      Graf[Grafana]
      Alert[Alertmanager]
      OTel[otel-collector]
      Jaeger[Jaeger]
      ES[Elasticsearch]
      Kibana[Kibana]
      FB[fluent-bit DaemonSet]
    end

    subgraph CICD [CI/CD]
      Jenkins[Jenkins<br/>management acct]
      ArgoCD[ArgoCD<br/>in-cluster]
      Manifests[(openproject-mcp-manifests<br/>GitOps repo)]
      Charts[(openproject-mcp-charts<br/>GH Pages)]
    end

    Laptop -- Tailnet --> TS
    TS --> Istio
    Istio -- mTLS STRICT --> MCP
    MCP -- HAL+JSON --> OPPod
    OP_UI --> OPPod
    OPPod --> RDS
    OPPod --> OPCache
    OP_UI -- POST /webhooks --> Istio
    MCP -- aiokafka SASL/IAM --> MSK
    MSK -- consumer --> MCP
    MCP -- ExternalSecret --> SM
    OPPod -- ExternalSecret --> SM

    MCP -- OTLP --> OTel
    OTel --> Prom
    OTel --> Jaeger
    Jaeger --> ES
    FB --> ES
    ES --> Kibana
    Prom --> Graf
    Prom --> Alert

    Operator -. reconciles .-> MCP
    Jenkins -- "helm upgrade atomic" --> MCP
    Jenkins -- bump tag --> Manifests
    Manifests -. watched .-> ArgoCD
    ArgoCD -. apply .-> MCP
    Charts -. helm pull .-> Jenkins
```

## Webhook sequence (push path)

```mermaid
sequenceDiagram
    autonumber
    participant OP as OpenProject
    participant ING as MCP /webhooks/openproject
    participant K as MSK topic openproject.events.raw
    participant CON as MCP consumer
    participant CACHE as in-memory LRU (10k)
    participant LLM as LLM via MCP get_recent_events

    OP->>ING: POST event + X-OP-Signature
    ING->>ING: HMAC-SHA256 constant-time verify
    ING->>K: producer.send(key=event_id, value=payload)
    ING-->>OP: 202 Accepted
    K-->>CON: aiokafka poll
    CON->>CON: transform_raw (drop poison, normalize)
    CON->>CACHE: write (LRU evict if >10k)
    CON->>K: commit offset
    LLM->>CACHE: get_recent_events(project_id, since)
    CACHE-->>LLM: filtered list
```

The non-obvious part: webhook ingest returns 202 *before* Kafka has
acked the produce. That gives OpenProject's webhook retry loop a
predictable ceiling on latency (target p95 < 50ms at the ingest
route, separate from the Kafka-to-cache p95 < 5s SLO). If MSK is
unavailable the route falls back to 503 and OpenProject's retry
budget takes over.

## Deployment topology

```mermaid
flowchart LR
    subgraph Mgmt [Management acct 772147490037]
      JenkinsHost[Jenkins host EC2]
      ECR[(ECR / Docker Hub)]
    end

    subgraph Dev [Dev acct 938184884486]
      DevEKS[EKS mcp-dev]
      DevRDS[(RDS dev)]
      DevMSK[(MSK dev)]
    end

    subgraph Staging [Staging acct 875285643901]
      StgEKS[EKS mcp-staging]
      StgRDS[(RDS staging)]
      StgMSK[(MSK staging)]
    end

    subgraph Prod [Prod acct 137451610850]
      ProdEKS[EKS mcp-prod]
      ProdRDS[(RDS prod multi-AZ)]
      ProdMSK[(MSK prod 3-broker)]
      R53[Route53 t3ja.com<br/>public hosted zone]
    end

    JenkinsHost -- AssumeRole openproject-mcp-jenkins-deploy --> DevEKS
    JenkinsHost -- AssumeRole --> StgEKS
    JenkinsHost -- AssumeRole + manual approve --> ProdEKS
    JenkinsHost -- push image --> ECR
    DevEKS -- pull image --> ECR
    StgEKS -- pull image --> ECR
    ProdEKS -- pull image --> ECR
    R53 -. NS delegate .-> DevEKS
    R53 -. NS delegate .-> StgEKS
    R53 -. apex .-> ProdEKS
```

State backends + KMS keys per env, never shared across accounts.
Subdomain pattern `mcp-dev.t3ja.com`, `mcp-staging.t3ja.com`,
`mcp.t3ja.com` matches the CSYE6225 convention I carried over.

## Component table

| Piece | Where in repo | Depends on | Notes |
|---|---|---|---|
| MCP server | `apps/mcp-server/` | OpenProject API, MSK, otel-collector | 32 tools, HTTP+SSE+stdio |
| Webhook ingest | `apps/mcp-server/src/openproject_mcp_server/webhooks/` | HMAC secret, MSK | 202-first design |
| Kafka consumer | same | MSK SASL/IAM | manual commit after cache write |
| Events cache | same | none | bounded LRU 10k + project index |
| Helm app chart | `helm/openproject-mcp/` | ESO, sealed-secrets, Istio CRDs | values per env |
| Helm OpenProject wrapper | `helm/openproject/` | external RDS, in-cluster memcached | subchart pin 8.0.0 |
| Helm observability | `helm/observability/` | kube-prometheus-stack, ES, Jaeger, OTel | sidecar dashboards |
| Helm addons | `helm/addons/` | ESO, sealed-secrets, external-dns | install order: this first |
| Kustomize | `k8s/` | nothing external | base + 3 env overlays |
| Istio | `istio/` | EKS + istio CRDs | mTLS STRICT + default-deny AuthPolicy |
| Terraform | `terraform/` | bootstrap (S3+DDB) | env per dir, profile per acct |
| Ansible | `ansible/` | dynamic aws_ec2 inventory | bastion + ssh-keys + networking |
| Jenkins | `jenkins/` | Docker host + AssumeRole IAM | JCasC-provisioned, multibranch pipeline |
| ArgoCD | `argocd/` + `openproject-mcp-manifests` repo | EKS + sealed-secrets | image updater on dev/staging |
| Knative | `knative/` | Istio + KnativeServing operator | scale-to-zero variant + KafkaSource |
| Operator | separate repo `openproject-mcp-operator/` | EKS + cert-manager | `OpenProjectMCP` CRD, Go/Kubebuilder |
| Load harness | `load/` | k6-operator on EKS | webhooks + 20 MCP tools scenarios |
| Chaos | `chaos/` | chaos-mesh 2.7 | pod-kill, net-latency, broker-kill |
| Tailscale | `tailscale/` | EKS + auth key | k8s-operator + ACLs |

## Why these specific choices

Helm gives templating, Kustomize gives the overlay model ArgoCD wants, so both live side-by-side. Jenkins-direct deploys use the Helm path; ArgoCD reconciles the Kustomize overlays in the manifests repo.

Jenkins owns the push deploy contract end-to-end (semver bump, image build, trivy scan, helm upgrade, smoke check, promote, rollback). GitHub Actions only runs lint and tests on PRs - it never touches a cluster.

Push and pull are both wired. Push (Jenkins helm upgrade) is the deploy default. Pull (ArgoCD watching the manifests repo, Image Updater writing tags back) is wired so the GitOps loop is observable end-to-end.
