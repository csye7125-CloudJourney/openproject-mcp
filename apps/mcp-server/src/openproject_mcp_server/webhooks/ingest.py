"""Starlette POST endpoint that ingests OpenProject webhooks into kafka.

Flow:
  1. read body (raw bytes. can't decode then re-encode, the signature is
     over the original bytes)
  2. verify HMAC-SHA256 over body using `X-OP-Signature` + WEBHOOK_HMAC_SECRET
  3. parse JSON for the event id (used as kafka key for partition stickiness)
  4. fire-and-forget produce to `openproject.events.raw`
  5. return 202 Accepted immediately

We don't await the broker ack inside the request. OpenProject retries on
non-2xx, and the producer already gives us at-least-once semantics via
enable_idempotence=True. Latency stays sub-50ms because the route returns
as soon as the message is buffered.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from .hmac_validator import SIGNATURE_HEADER, InvalidSignature, verify_signature
from .kafka_client import EVENTS_TOPIC

logger = logging.getLogger(__name__)


# Type alias for the producer-like callable an injected test producer must expose.
# Real path uses aiokafka.AIOKafkaProducer.send_and_wait, but the route only
# needs `await producer.send(topic, value, key)`.
ProducerLike = Any


# Module-level handle so transport.py lifespan can set/clear the live producer
# without threading state through every request. Tests inject directly via
# `set_producer(fake)`.
_producer: Optional[ProducerLike] = None


def set_producer(producer: Optional[ProducerLike]) -> None:
    """Install (or remove) the kafka producer used by the ingest route."""
    global _producer
    _producer = producer


def _extract_event_key(payload: dict) -> bytes:
    """Best-effort partition key from the webhook payload.

    OpenProject payloads usually have a top-level event `id` and a
    `project.id` under `_embedded`. We key by event id so retries of the
    same event hash to the same partition (idempotent consumer wins).
    """
    candidate = payload.get("id") or payload.get("action_id")
    if candidate is None:
        emb = payload.get("_embedded", {})
        candidate = emb.get("project", {}).get("id") if isinstance(emb, dict) else None
    if candidate is None:
        return b""
    return str(candidate).encode("utf-8")


async def ingest(request: Request) -> JSONResponse:
    """POST /webhooks/openproject handler.

    Returns:
      202: signature valid, event buffered for produce
      400: body not JSON or producer not initialized
      401: missing or invalid signature
      503: producer raised on send
    """
    body = await request.body()
    supplied_sig = request.headers.get(SIGNATURE_HEADER)
    try:
        verify_signature(body, supplied_sig)
    except InvalidSignature as exc:
        logger.warning("webhook rejected: %s", exc)
        return JSONResponse({"error": "invalid signature"}, status_code=401)

    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return JSONResponse({"error": "body is not valid json"}, status_code=400)

    if _producer is None:
        # producer not wired yet (transport lifespan hasn't run). surface a
        # clear error so the upstream retries instead of dropping events
        logger.error("webhook ingest hit before kafka producer was initialized")
        return JSONResponse({"error": "ingest not ready"}, status_code=503)

    key = _extract_event_key(payload)
    try:
        await _producer.send(EVENTS_TOPIC, value=body, key=key or None)
    except Exception as exc:  # noqa: BLE001 - we don't want to leak broker stack
        logger.exception("kafka produce failed: %s", exc)
        return JSONResponse({"error": "kafka unavailable"}, status_code=503)

    return JSONResponse({"status": "accepted"}, status_code=202)
