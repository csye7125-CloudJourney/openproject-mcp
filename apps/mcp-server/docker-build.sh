#!/bin/bash
# build + smoke the openproject-mcp container image locally.

set -e

echo "building openproject-mcp-server image..."
docker build -t openproject-mcp-server:latest .

echo "smoke 1: imports + config load"
docker run --rm \
  -e OPENPROJECT_BASE_URL=http://test.example.com \
  -e OPENPROJECT_API_KEY=test-key \
  openproject-mcp-server:latest \
  python -c "
from openproject_mcp_server.config import Config
from openproject_mcp_server.api_client import OpenProjectClient
config = Config.from_env()
client = OpenProjectClient(
    base_url=config.openproject.base_url,
    api_key=config.openproject.api_key,
    timeout=config.openproject.timeout,
    verify_ssl=config.openproject.verify_ssl
)
print('ok: imports + client init')
print(f'ok: base_url={config.openproject.base_url}')
print(f'ok: timeout={client.timeout}s')
"

echo "smoke 2: health command"
docker run --rm \
  -e OPENPROJECT_BASE_URL=http://test.example.com \
  -e OPENPROJECT_API_KEY=test-key \
  openproject-mcp-server:latest \
  python -c "from openproject_mcp_server.config import Config; Config.from_env(); print('ok: healthcheck')"

echo ""
echo "image ready. quickstart:"
echo "  docker run --env-file .env openproject-mcp-server:latest"
echo "  docker-compose up -d"
echo "  docker-compose -f docker-compose.mcp-only.yml up -d"
