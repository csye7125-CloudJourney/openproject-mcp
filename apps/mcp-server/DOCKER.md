# Docker deployment

How to run the OpenProject MCP server in Docker.

## Quick start

### Option 1: MCP server only (existing OpenProject)

If you already have OpenProject running:

```bash
# 1. copy env template
cp .env.docker .env

# 2. edit .env with your OpenProject details
nano .env

# 3. run MCP server only
docker-compose -f docker-compose.mcp-only.yml up -d
```

### Option 2: complete stack (OpenProject + MCP server)

For a full local setup:

```bash
# 1. copy env template
cp .env.docker .env

# 2. edit .env with your config
nano .env

# 3. bring everything up
docker-compose up -d
```

## Configuration

### Environment variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENPROJECT_BASE_URL` | OpenProject URL | `http://openproject:8080` | yes |
| `OPENPROJECT_API_KEY` | OpenProject API key | - | yes |
| `OPENPROJECT_TIMEOUT` | Request timeout (s) | `30` | no |
| `OPENPROJECT_VERIFY_SSL` | Verify SSL certs | `true` | no |
| `LOG_LEVEL` | Log level | `INFO` | no |
| `LOG_FORMAT` | Log format (json/text) | `json` | no |

### Getting an OpenProject API key

1. Log into OpenProject
2. **My Account** -> **Access tokens**
3. Click **+ API token**
4. Name it, click **Create**
5. Copy the token

## Docker commands

### Build

```bash
# build the image
docker build -t openproject-mcp-server:latest .

# tagged build
docker build -t openproject-mcp-server:v0.1.0 .
```

### Run

```bash
# with env file
docker run --env-file .env openproject-mcp-server:latest

# with inline env
docker run \
  -e OPENPROJECT_BASE_URL=http://your-openproject.com \
  -e OPENPROJECT_API_KEY=your-api-key \
  openproject-mcp-server:latest

# detached
docker run -d --name openproject-mcp \
  --env-file .env \
  openproject-mcp-server:latest
```

### docker compose

```bash
# start
docker-compose up -d

# tail logs
docker-compose logs -f openproject-mcp

# stop
docker-compose down

# rebuild and restart
docker-compose up -d --build

# nuke including volumes
docker-compose down -v
```

## Integrating with existing OpenProject

### Join the existing OpenProject docker network

```bash
# find the network
docker network ls | grep openproject

# update docker-compose.mcp-only.yml to point at that network
# then start
docker-compose -f docker-compose.mcp-only.yml up -d
```

### External OpenProject

```bash
# point at the external URL in .env
OPENPROJECT_BASE_URL=https://your-openproject-domain.com
OPENPROJECT_API_KEY=your-api-key

# run MCP server
docker-compose -f docker-compose.mcp-only.yml up -d
```

## Health checks

The container has a built-in health check.

```bash
# container health
docker ps

# health check logs
docker inspect openproject-mcp-server | grep -A 10 Health
```

## Logs and monitoring

### Viewing logs

```bash
# follow
docker-compose logs -f openproject-mcp

# last N lines
docker-compose logs --tail=100 openproject-mcp

# with timestamps
docker-compose logs -t openproject-mcp
```

### Log files

Logs land in `./logs`:

```bash
# files
ls -la logs/

# tail
tail -f logs/openproject-mcp.log
```

## Troubleshooting

### Common issues

**1. Connection refused**

```bash
# is OpenProject running?
docker ps | grep openproject

# network check
docker exec openproject-mcp-server ping openproject
```

**2. 401 unauthorized**

```bash
# verify API key
docker exec openproject-mcp-server env | grep OPENPROJECT_API_KEY

# test it directly
curl -u apikey:YOUR_API_KEY http://your-openproject/api/v3/projects
```

**3. Container won't start**

```bash
# logs
docker logs openproject-mcp-server

# config check
docker exec openproject-mcp-server python -c "from openproject_mcp_server.config import Config; print(Config.from_env())"
```

### Debug mode

Run with debug logs:

```bash
# debug logging
docker run --env-file .env \
  -e LOG_LEVEL=DEBUG \
  openproject-mcp-server:latest

# interactive
docker run -it --env-file .env \
  openproject-mcp-server:latest /bin/sh
```

## Production deployment

### Security

1. Use Docker secrets for sensitive data:

```yaml
secrets:
  openproject_api_key:
    external: true

services:
  openproject-mcp:
    secrets:
      - openproject_api_key
```

2. Run as non-root (already set in Dockerfile)
3. Use specific image tags, not `latest`
4. Use SSL/TLS for OpenProject connections

### Resource limits

```yaml
services:
  openproject-mcp:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.1'
          memory: 128M
```

### Backup and persistence

```bash
# backup logs
docker run --rm -v openproject-mcp_logs:/backup alpine tar czf - /backup > logs-backup.tar.gz

# restore
docker run --rm -v openproject-mcp_logs:/backup alpine tar xzf - < logs-backup.tar.gz
```

## Claude Desktop integration

Claude Desktop needs direct stdio access, so the MCP server should run on
the host system when wired to Claude Desktop, not inside Docker.

For Docker deployments, options are:

1. Run the MCP server on the host
2. Use Docker only for OpenProject
3. Point the host MCP server at the dockerized OpenProject

## Support

For Docker issues:

1. Check logs: `docker-compose logs openproject-mcp`
2. Verify config: `docker exec openproject-mcp-server env`
3. Test connectivity: `docker exec openproject-mcp-server ping openproject`
4. Re-read this doc
5. Check the main README.md for general troubleshooting
