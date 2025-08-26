"""Transport adapters for the MCP server.

stdio is the original path. HTTP/SSE landed in a later commit. This module
lets __main__ dispatch based on `MCP_TRANSPORT` without touching the guts
of server.py's main().
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import AsyncIterator

import uvicorn
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from openproject_mcp_server.server import server
from openproject_mcp_server.tracing import (
    instrument_httpx,
    instrument_starlette,
    setup_tracing,
)
from openproject_mcp_server.webhooks import ingest as webhook_ingest
from openproject_mcp_server.webhooks.consumer import ReplayConsumer
from openproject_mcp_server.webhooks.routes import register_webhook_routes


async def run_stdio() -> None:
    """Thin wrapper around the existing stdio_server bootstrap."""
    logging.info("MCP transport: stdio")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def build_app() -> Starlette:
    """Build the Starlette app exposing the MCP server over SSE.

    Two routes:
      GET /sse        opens the event stream
      POST /messages/ client posts JSON-RPC frames back to the server
    """
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request):  # noqa: ANN001
        # SseServerTransport drives the response stream itself via request._send.
        # This coroutine has to stay alive until server.run returns, otherwise
        # Starlette will send its own 404 over the stream and clients see the
        # SSE close right after the first message with a malformed body.
        # Returning an empty Response after the context manager exits is fine
        # because the response was already started by the SSE transport.
        async with sse.connect_sse(request.scope, request.receive, request._send) as (read, write):
            await server.run(read, write, server.create_initialization_options())
        return Response()

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def readyz(_: Request) -> JSONResponse:
        # could probe the OpenProject API here, for now liveness == readiness
        return JSONResponse({"status": "ready"})

    async def metrics(_: Request) -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    routes = [
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
        Route("/healthz", endpoint=healthz),
        Route("/readyz", endpoint=readyz),
        Route("/metrics", endpoint=metrics),
    ]
    # init OTel BEFORE building the app + before any httpx client downstream.
    # setup_tracing is gated by OTEL_ENABLED env so stdio transport pays
    # nothing.
    setup_tracing()
    instrument_httpx()
    app = Starlette(debug=False, routes=routes, lifespan=_lifespan)
    instrument_starlette(app)
    register_webhook_routes(app)
    return app


def _kafka_enabled() -> bool:
    """Kafka producer/consumer only start when explicitly turned on.

    Default off so unit tests + local dev that don't care about webhooks
    don't have to run a broker. Set `MCP_KAFKA_ENABLED=1` in dev/prod.
    """
    return os.environ.get("MCP_KAFKA_ENABLED", "").lower() in {"1", "true", "yes"}


@contextlib.asynccontextmanager
async def _lifespan(app: Starlette) -> AsyncIterator[None]:  # noqa: ARG001
    """Boot the kafka producer + replay consumer alongside the http server.

    Skips both if kafka isn't enabled via env so the http transport can
    still run standalone in dev. Failures during start are logged but
    never abort the server: the webhook route surfaces 503 if the
    producer never came up.
    """
    producer = None
    consumer: ReplayConsumer | None = None
    if _kafka_enabled():
        try:
            from openproject_mcp_server.webhooks.kafka_client import build_producer

            producer = build_producer()
            await producer.start()
            webhook_ingest.set_producer(producer)
            logging.info("kafka producer started for webhook ingest")
        except Exception as exc:  # noqa: BLE001
            logging.exception("kafka producer failed to start: %s", exc)
            producer = None
        try:
            consumer = ReplayConsumer(
                from_beginning=os.environ.get("MCP_KAFKA_FROM_BEGINNING", "").lower()
                in {"1", "true", "yes"}
            )
            await consumer.start()
            logging.info("kafka replay consumer started")
        except Exception as exc:  # noqa: BLE001
            logging.exception("kafka consumer failed to start: %s", exc)
            consumer = None
    try:
        yield
    finally:
        if consumer is not None:
            await consumer.stop()
        if producer is not None:
            webhook_ingest.set_producer(None)
            try:
                await producer.stop()
            except Exception:  # noqa: BLE001
                logging.exception("error stopping kafka producer")


async def run_http_sse(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Serve the MCP server over HTTP/SSE on (host, port)."""
    logging.info(f"MCP transport: http+sse on {host}:{port}")
    config = uvicorn.Config(build_app(), host=host, port=port, log_level="info")
    server_inst = uvicorn.Server(config)
    await server_inst.serve()
