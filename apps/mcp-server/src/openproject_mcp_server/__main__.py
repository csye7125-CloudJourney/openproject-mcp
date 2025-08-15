"""Entry point for the OpenProject MCP server.

Dispatches transport based on MCP_TRANSPORT. Default is stdio so existing
Claude Desktop / stdio consumers keep working. Other values landed in
later commits.
"""

import asyncio
import os

from openproject_mcp_server.server import main as stdio_main


def _entrypoint() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "stdio":
        asyncio.run(stdio_main())
    elif transport in ("http", "sse", "http-sse"):
        from openproject_mcp_server.transport import run_http_sse
        host = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_HTTP_PORT", "8080"))
        asyncio.run(run_http_sse(host=host, port=port))
    else:
        raise SystemExit(f"Unknown MCP_TRANSPORT={transport!r}")


if __name__ == "__main__":
    _entrypoint()
