"""OpenTelemetry tracing for the MCP server.

Gated by the `OTEL_ENABLED` env var so unit tests + local dev that don't
care about traces don't have to spin up a collector. When on, sends OTLP
spans to `OTEL_EXPORTER_OTLP_ENDPOINT` (default the in-cluster
otel-collector). Idempotent init: calling `setup_tracing()` twice is a
no-op.

This module imports the OTel SDK at top level so the import cost is paid
once at process startup. The actual provider install only happens inside
`setup_tracing()`.
"""

from __future__ import annotations

import logging
import os
from threading import Lock
from typing import Optional

log = logging.getLogger(__name__)

# guard so setup_tracing is idempotent across tests / multiple lifespan
# boots. _initialized flips true on the first successful call; later
# calls return early.
_init_lock = Lock()
_initialized = False
_tracer_provider = None  # type: ignore[var-annotated]


def _otel_enabled() -> bool:
    """Toggle. Defaults to off so dev + ci stays quiet."""
    return os.environ.get("OTEL_ENABLED", "").lower() in {"1", "true", "yes"}


def _exporter_endpoint() -> str:
    """OTLP gRPC endpoint. Default targets the in-cluster collector."""
    return os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://otel-collector.observability.svc.cluster.local:4317",
    )


def _service_name() -> str:
    return os.environ.get("OTEL_SERVICE_NAME", "openproject-mcp")


def setup_tracing(force: bool = False) -> Optional[object]:
    """Wire up the global TracerProvider + OTLP exporter.

    Returns the TracerProvider so callers (mostly tests) can inspect it.
    Returns None when OTEL is off. `force=True` re-installs even if a
    previous call ran. Tests use it to swap exporters.
    """
    global _initialized, _tracer_provider

    if not _otel_enabled() and not force:
        log.debug("otel disabled via OTEL_ENABLED env, skipping setup")
        return None

    with _init_lock:
        if _initialized and not force:
            return _tracer_provider

        # imports inside the function so the cost only hits when tracing
        # actually turns on. matters for stdio transport where the otel
        # deps would otherwise be deadweight.
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": _service_name(),
                "service.version": os.environ.get("MCP_SERVICE_VERSION", "0.4.0"),
                "deployment.environment": os.environ.get("MCP_ENV", "dev"),
            }
        )
        provider = TracerProvider(resource=resource)

        endpoint = _exporter_endpoint()
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _tracer_provider = provider
        _initialized = True
        log.info(
            "otel tracing ready - service=%s endpoint=%s",
            _service_name(),
            endpoint,
        )
        return provider


def get_tracer(name: str = "openproject-mcp"):
    """Convenience getter so tool handlers don't have to import OTel."""
    from opentelemetry import trace

    return trace.get_tracer(name)


def instrument_starlette(app: object) -> None:
    """Wrap a Starlette app with the OTel ASGI middleware.

    No-op when OTEL is off so transport.build_app() can call this
    unconditionally without a feature flag on its side. Safe to call
    multiple times on the same app: the instrumentor detects
    double-wrapping and skips.
    """
    if not _otel_enabled():
        return
    try:
        from opentelemetry.instrumentation.starlette import StarletteInstrumentor

        StarletteInstrumentor.instrument_app(app)  # type: ignore[arg-type]
        log.info("starlette otel instrumentation installed")
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to instrument starlette: %s", exc)


def instrument_httpx() -> None:
    """Auto-trace outbound httpx calls (api_client uses httpx).

    Global instrumentation. Patches the httpx classes so any AsyncClient +
    Client instantiated AFTER this runs emits spans. Has to be called
    before the api_client builds its client, which is why setup_tracing's
    caller invokes it first.
    """
    if not _otel_enabled():
        return
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        log.info("httpx otel instrumentation installed")
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to instrument httpx: %s", exc)


def reset_for_tests() -> None:
    """Clear init state. Tests only - never call from production paths."""
    global _initialized, _tracer_provider
    with _init_lock:
        _initialized = False
        _tracer_provider = None
