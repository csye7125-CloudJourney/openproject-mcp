"""Adds the webhook routes to an existing Starlette app.

`transport.build_app()` calls `register_webhook_routes(app)` so the
webhook endpoint shares the same uvicorn process and TLS termination
as the SSE/MCP transport.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.routing import Route

from .ingest import ingest

WEBHOOK_PATH = "/webhooks/openproject"


def register_webhook_routes(app: Starlette) -> None:
    """Append the /webhooks/openproject POST route to the running app."""
    app.router.routes.append(Route(WEBHOOK_PATH, endpoint=ingest, methods=["POST"]))
