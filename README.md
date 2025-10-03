# OpenProject MCP Server

MCP server for OpenProject. Talks to OP's REST + HAL+JSON API over httpx, exposes 30+ tools to Claude over stdio or HTTP+SSE. Webhook ingest path produces to Kafka so the in-memory recent-events cache survives pod restarts.

## tools

projects, work packages, users, time entries, memberships, attachments, versions, categories, relations, watchers, statuses/types/priorities, search, get_recent_events (kafka-fed).

## install

```bash
cd apps/mcp-server
pip install -e .[dev]
```

`OPENPROJECT_URL` + `OPENPROJECT_API_KEY` env vars, then:

```bash
python -m openproject_mcp_server                       # stdio (default)
MCP_TRANSPORT=http python -m openproject_mcp_server    # http+sse :8000
```

## docker

```bash
docker compose -f apps/mcp-server/docker-compose.yml up
```

## metrics + traces

prometheus histograms on every tool call (`openproject_mcp_tool_latency_seconds`, `openproject_mcp_tool_calls_total`). OTLP spans via `tracing.py` when `OTEL_ENABLED=true`.

## tests

```bash
cd apps/mcp-server && pytest -q
```

## infra

- terraform/ — VPC + EKS + RDS + MSK + IAM, env-per-dir, profile-per-account
- helm/ — openproject-mcp + openproject + addons + observability charts
- k8s/ — kustomize base + dev/staging/prod overlays
- jenkins/ — JCasC dockerfile + casc.yaml + multibranch pipeline
- ansible/ — bastion + ssh-keys playbooks
- istio/, knative/, chaos/, load/, tailscale/, argocd/ — see dirs

semester project for advanced cloud computing. WIP.
