# OpenProject MCP Server

MCP server for OpenProject. Talks to OP's REST + HAL+JSON API over httpx, exposes tools to Claude over stdio or HTTP+SSE.

## tools

projects, work packages, users, time entries, memberships, attachments, versions, categories, relations, watchers, statuses/types/priorities, search. ~25 right now.

## install

```bash
cd apps/mcp-server
pip install -e .[dev]
```

set `OPENPROJECT_URL` + `OPENPROJECT_API_KEY` in env, then:

```bash
python -m openproject_mcp_server
```

stdio by default. set `MCP_TRANSPORT=http` for HTTP+SSE on :8000.

## docker

```bash
docker compose -f apps/mcp-server/docker-compose.yml up
```

## tests

```bash
cd apps/mcp-server && pytest -q
```

## infra

terraform/ + helm/ + k8s/ + jenkins/ — wip, building the EKS deploy out for the cloud computing class. see subdirs.
