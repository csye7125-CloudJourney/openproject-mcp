"""Tests for the /webhooks/openproject ingest route.

The producer is a fake `AsyncMock`-backed object - we don't touch real kafka.
Verifies status codes for bad sig, bad body, no producer, and that a good
request actually invokes `producer.send(topic, value=body, key=...)`.
"""

import hashlib
import hmac
import json

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from openproject_mcp_server.webhooks import ingest as ingest_mod
from openproject_mcp_server.webhooks.routes import register_webhook_routes


SECRET = "test-secret"


class FakeProducer:
    def __init__(self):
        self.calls = []

    async def send(self, topic, value, key=None):
        self.calls.append({"topic": topic, "value": value, "key": key})


@pytest.fixture(autouse=True)
def _set_hmac_secret(monkeypatch):
    monkeypatch.setenv("WEBHOOK_HMAC_SECRET", SECRET)


@pytest.fixture
def app_with_producer():
    """Starlette app with webhook route + a fake producer installed."""
    app = Starlette()
    register_webhook_routes(app)
    producer = FakeProducer()
    ingest_mod.set_producer(producer)
    yield app, producer
    ingest_mod.set_producer(None)


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_route_registered():
    app = Starlette()
    register_webhook_routes(app)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/webhooks/openproject" in paths


def test_post_returns_202_on_valid_signature(app_with_producer):
    app, producer = app_with_producer
    payload = {"id": "evt-1", "action": "work_package:created"}
    body = json.dumps(payload).encode()
    sig = _sign(body)
    with TestClient(app) as client:
        r = client.post(
            "/webhooks/openproject",
            content=body,
            headers={"X-OP-Signature": sig, "Content-Type": "application/json"},
        )
    assert r.status_code == 202
    assert r.json() == {"status": "accepted"}
    assert len(producer.calls) == 1
    assert producer.calls[0]["topic"] == "openproject.events.raw"
    assert producer.calls[0]["value"] == body
    assert producer.calls[0]["key"] == b"evt-1"


def test_post_rejects_bad_signature(app_with_producer):
    app, producer = app_with_producer
    body = b'{"hello":"world"}'
    with TestClient(app) as client:
        r = client.post(
            "/webhooks/openproject",
            content=body,
            headers={"X-OP-Signature": "deadbeef" * 8},
        )
    assert r.status_code == 401
    assert producer.calls == []


def test_post_rejects_missing_signature(app_with_producer):
    app, _ = app_with_producer
    with TestClient(app) as client:
        r = client.post("/webhooks/openproject", content=b'{"x":1}')
    assert r.status_code == 401


def test_post_rejects_bad_json(app_with_producer):
    app, producer = app_with_producer
    body = b"this is not json{"
    with TestClient(app) as client:
        r = client.post(
            "/webhooks/openproject",
            content=body,
            headers={"X-OP-Signature": _sign(body)},
        )
    assert r.status_code == 400
    assert producer.calls == []


def test_post_returns_503_when_producer_unset():
    app = Starlette()
    register_webhook_routes(app)
    ingest_mod.set_producer(None)
    body = b'{"id":"abc"}'
    with TestClient(app) as client:
        r = client.post(
            "/webhooks/openproject",
            content=body,
            headers={"X-OP-Signature": _sign(body)},
        )
    assert r.status_code == 503


def test_post_returns_503_when_producer_raises():
    class BoomProducer:
        async def send(self, *a, **kw):
            raise RuntimeError("broker is sad")

    app = Starlette()
    register_webhook_routes(app)
    ingest_mod.set_producer(BoomProducer())
    body = b'{"id":"x"}'
    try:
        with TestClient(app) as client:
            r = client.post(
                "/webhooks/openproject",
                content=body,
                headers={"X-OP-Signature": _sign(body)},
            )
        assert r.status_code == 503
    finally:
        ingest_mod.set_producer(None)


def test_key_falls_back_to_project_id_when_no_event_id(app_with_producer):
    app, producer = app_with_producer
    payload = {"_embedded": {"project": {"id": 99}}}
    body = json.dumps(payload).encode()
    with TestClient(app) as client:
        r = client.post(
            "/webhooks/openproject",
            content=body,
            headers={"X-OP-Signature": _sign(body)},
        )
    assert r.status_code == 202
    assert producer.calls[0]["key"] == b"99"
