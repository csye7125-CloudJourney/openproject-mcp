"""Tests for the HTTP/SSE transport scaffold."""

import pytest

from openproject_mcp_server.transport import build_app


def test_build_app_exposes_sse_and_messages():
    app = build_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/sse" in paths
    # Mount uses path prefix; starlette stores it on the route too
    assert any(getattr(r, "path", "").startswith("/messages") for r in app.routes)


def test_healthz_and_readyz_routes():
    app = build_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/healthz" in paths
    assert "/readyz" in paths


def test_healthz_responds_ok():
    from starlette.testclient import TestClient
    app = build_app()
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
        r = client.get("/readyz")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


def test_metrics_endpoint_returns_prometheus_format():
    from starlette.testclient import TestClient
    app = build_app()
    with TestClient(app) as client:
        r = client.get("/metrics")
        assert r.status_code == 200
        # prometheus exposition format is text/plain
        assert "text/plain" in r.headers["content-type"]
        # at least the counter we registered should be in there
        assert "openproject_mcp_tool_calls_total" in r.text


def test_webhook_route_mounted_on_app():
    app = build_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/webhooks/openproject" in paths
