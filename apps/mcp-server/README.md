# openproject-mcp-server

Model Context Protocol (MCP) server for OpenProject. Exposes the OpenProject
REST API as MCP tools so Claude can list projects, manage work packages, look
up users, etc.

## Features

- 31 MCP tools for projects, work packages, time entries, memberships,
  relations, watchers, attachments, categories, versions, queries, search,
  hierarchy, status/type/priority lookups, and per-user fetch. Full list
  under "Registered tools" below.
- Two transports. stdio for Claude Desktop, HTTP/SSE for hosted setups.
  Switch via `MCP_TRANSPORT={stdio,http}`.
- Prometheus metrics on every tool call and every outbound OpenProject
  request. Exposed at `/metrics` under the HTTP transport.
- `/healthz` and `/readyz` for k8s liveness/readiness probes.
- `scripts/bench_latency.py` fires N calls per tool through an in-process
  `httpx.MockTransport`, prints p50/p95/p99, writes `bench/results.json`,
  and exits non-zero if any tool's p95 > 200ms.
- Built on the official MCP Python SDK, fully async.

### Registered tools

Projects: `list_projects`, `get_project_details`, `create_project`,
`update_project`, `delete_project`, `get_project_hierarchy`.

Work packages: `list_work_packages`, `get_work_package`,
`create_work_package`, `update_work_package`, `delete_work_package`,
`search_work_packages`, `list_relations`, `create_relation`,
`list_watchers`, `add_watcher`, `list_activities`, `list_attachments`.

Time entries: `list_time_entries`, `create_time_entry`.

Lookups: `list_statuses`, `list_types`, `list_priorities`.

Project ops: `list_memberships`, `create_membership`, `list_categories`,
`list_versions`, `create_version`, `list_queries`.

Users: `list_users`, `get_user`.

## Install

### From source

```bash
git clone <repository-url>
cd openproject-mcp-server
pip install -e .
```

## Configuration

Configured via environment variables.

### Required

- `OPENPROJECT_BASE_URL`: OpenProject instance URL (e.g. `https://openproject.example.com`)
- `OPENPROJECT_API_KEY`: OpenProject API key

### Optional

- `OPENPROJECT_TIMEOUT`: request timeout in seconds (default 30)
- `OPENPROJECT_VERIFY_SSL`: verify SSL certs (default true)
- `LOG_LEVEL`: log level (default INFO)
- `LOG_FORMAT`: log format, json or text (default json)

## Usage

### With Claude Desktop

Add to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "openproject": {
      "command": "python",
      "args": ["-m", "openproject_mcp_server"],
      "env": {
        "OPENPROJECT_BASE_URL": "https://your-openproject.com",
        "OPENPROJECT_API_KEY": "your-api-key"
      }
    }
  }
}
```

### HTTP/SSE transport

For hosted setups (k8s/Tailscale/Istio in front), run the same binary with
`MCP_TRANSPORT=http`. The server listens on `MCP_HTTP_HOST` (default
`0.0.0.0`) and `MCP_HTTP_PORT` (default `8080`) and exposes:

- `GET /sse` SSE stream for MCP clients
- `POST /messages/` inbound JSON-RPC frames
- `GET /healthz` liveness (always 200 when the process is up)
- `GET /readyz` readiness
- `GET /metrics` Prometheus exposition

```bash
MCP_TRANSPORT=http MCP_HTTP_PORT=8080 python -m openproject_mcp_server
# in another shell:
curl localhost:8080/healthz
curl localhost:8080/metrics
```

### Metrics

Prometheus histograms emitted out of the box:

- `openproject_mcp_tool_calls_total{tool_name, outcome}` counter
- `openproject_mcp_tool_latency_seconds{tool_name, outcome}` histogram
- `openproject_api_latency_seconds{method, outcome}` histogram for the
  outbound OpenProject HTTP path

Scrape `/metrics` with whatever Prometheus operator you've got.

### Benchmark

```bash
python scripts/bench_latency.py --iterations 100
# prints p50/p95/p99 per tool and writes bench/results.json
# exits 1 if any tool's p95 > 200ms (override with --p95-budget-ms)
```

The script stubs OpenProject with `httpx.MockTransport`, so it measures
handler + httpx overhead only. It's a regression gate, not an SLA number.
Real numbers come from k6 against the deployed service (see `load/`).

### Standalone (for testing)

```bash
# set env
export OPENPROJECT_BASE_URL="https://your-openproject.com"
export OPENPROJECT_API_KEY="your-api-key"

# run the server
python -m openproject_mcp_server
```

### Docker

#### Quick start

```bash
# 1. copy env template
cp .env.docker .env

# 2. edit .env
nano .env

# 3. build and run
./docker-build.sh
docker-compose -f docker-compose.mcp-only.yml up -d
```

#### Docker commands

```bash
# build the image
docker build -t openproject-mcp-server:latest .

# run with env file
docker run --env-file .env openproject-mcp-server:latest

# run with inline env
docker run \
  -e OPENPROJECT_BASE_URL=https://your-openproject.com \
  -e OPENPROJECT_API_KEY=your-api-key \
  openproject-mcp-server:latest
```

#### Compose options

- `docker-compose.yml` complete setup with OpenProject + MCP server
- `docker-compose.mcp-only.yml` MCP server only (for existing OpenProject)

See [DOCKER.md](DOCKER.md) for the full Docker guide.

## Available tools

### Project management

- **list_projects**: list all accessible projects with optional filtering
  - Optional filters: status, name (partial match)
- **get_project_details**: get detailed info about a specific project
  - Required: project_id

### Work package management

- **list_work_packages**: list work packages with optional filtering
  - Optional: project_id, filters (assignee, status, type)
- **get_work_package**: get detailed info about a specific work package
  - Required: work_package_id
- **create_work_package**: create a work package
  - Required: subject, project_id, type_id
  - Optional: description, assignee_id

### User management

- **list_users**: list all users in the OpenProject instance

## Example conversations with Claude

Once configured, ask Claude things like:

- "Show me all active projects"
- "What work packages are in project 5?"
- "Create a new task called 'Update documentation' in project 1 with type 1"
- "What's the status of work package 123?"
- "List all users in the system"

## Development

### Setup

```bash
# clone the repo
git clone <repository-url>
cd openproject-mcp-server

# install dev deps
pip install -e ".[dev]"

# tests
pytest

# lint
ruff check .
black --check .
mypy .
```

### Project structure

```
openproject-mcp-server/
├── src/openproject_mcp_server/
│   ├── __init__.py
│   ├── __main__.py        # entry point
│   ├── server.py          # main MCP server
│   ├── api_client.py      # OpenProject API client
│   └── config.py          # config
├── tests/
└── pyproject.toml
```

## Security

- API keys never logged
- All inputs validated to block injection attacks
- SSL cert verification on by default
- Simple error handling with user-friendly messages

## Contributing

1. Fork
2. Branch
3. Change
4. Add tests
5. Run the test suite
6. PR

## License

MIT.

## Changelog

### v0.1.0

- Initial release on the official MCP Python SDK
- Project and work package management
- Async HTTP client with retry + rate-limit handling
- Config via Pydantic v2
- Input validation
- Structured logging with JSON option
- Graceful shutdown
- Test suite (47 tests passing)
- Integration tests for the full MCP workflow
- Docker multi-stage build
- docker-compose configs
- Docker deployment docs
