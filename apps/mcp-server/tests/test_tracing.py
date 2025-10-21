"""Tests for the OpenTelemetry tracing wiring.

Uses InMemorySpanExporter so we can assert spans were emitted without
spinning up an actual otel-collector. Each test resets the global
TracerProvider via tracing.reset_for_tests() so state doesn't leak.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

from openproject_mcp_server import tracing


def _set_otel_on() -> None:
    os.environ["OTEL_ENABLED"] = "true"


def _set_otel_off() -> None:
    os.environ.pop("OTEL_ENABLED", None)


@pytest.fixture(autouse=True)
def _reset_tracing():
    """Wipe init state + OTEL_ENABLED before each test."""
    tracing.reset_for_tests()
    _set_otel_off()
    yield
    tracing.reset_for_tests()
    _set_otel_off()


def test_setup_tracing_noop_when_disabled():
    """No OTEL_ENABLED -> setup returns None without touching the SDK."""
    assert tracing.setup_tracing() is None


def test_setup_tracing_returns_provider_when_enabled():
    """OTEL_ENABLED=true + no real collector reachable -> still installs.

    The BatchSpanProcessor doesn't crash on a missing collector; it
    just queues + drops. So the init itself must succeed.
    """
    _set_otel_on()
    provider = tracing.setup_tracing()
    assert provider is not None


def test_setup_tracing_is_idempotent():
    """Second call returns the same provider as the first."""
    _set_otel_on()
    p1 = tracing.setup_tracing()
    p2 = tracing.setup_tracing()
    assert p1 is p2


def test_setup_tracing_force_reinstalls():
    """force=True re-runs even when already initialized."""
    _set_otel_on()
    p1 = tracing.setup_tracing()
    p2 = tracing.setup_tracing(force=True)
    # both are valid TracerProvider instances; force can return the same
    # provider object or a fresh one - the contract is just that init
    # ran a second time without raising.
    assert p1 is not None
    assert p2 is not None


def test_span_emitted_via_in_memory_exporter():
    """End-to-end: install in-memory exporter, emit a span, see it.

    OTel forbids replacing the global TracerProvider once set (logs
    `Overriding of current TracerProvider is not allowed`), so we grab
    the tracer off the provider directly rather than via the global
    `trace.get_tracer(...)`. This is the standard pattern in OTel
    unit tests.
    """
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # bypass the global so we don't trip OTel's "TracerProvider already
    # set" guard left over from the earlier setup_tracing tests
    tracer = provider.get_tracer("test-tracer")
    with tracer.start_as_current_span("tool.list_projects") as span:
        span.set_attribute("tool.arg.project_id", 42)

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "tool.list_projects"
    assert spans[0].attributes.get("tool.arg.project_id") == 42


def test_instrument_starlette_noop_when_disabled():
    """No env -> no patching attempted, no raise even on bogus arg."""
    # bogus app object - never touched because the gate short-circuits
    tracing.instrument_starlette(object())  # must not raise


def test_instrument_httpx_noop_when_disabled():
    tracing.instrument_httpx()  # must not raise


def test_instrument_starlette_called_when_enabled():
    """Confirm the StarletteInstrumentor is actually invoked."""
    _set_otel_on()
    from starlette.applications import Starlette

    app = Starlette()
    with mock.patch(
        "opentelemetry.instrumentation.starlette.StarletteInstrumentor.instrument_app"
    ) as instrument:
        tracing.instrument_starlette(app)
        instrument.assert_called_once_with(app)


def test_instrument_httpx_called_when_enabled():
    _set_otel_on()
    with mock.patch(
        "opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor.instrument"
    ) as instrument:
        tracing.instrument_httpx()
        instrument.assert_called_once()
