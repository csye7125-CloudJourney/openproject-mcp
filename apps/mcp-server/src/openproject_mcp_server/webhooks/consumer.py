"""Replay consumer. Pulls events from kafka into the in-memory cache.

Flow:
  raw bytes on topic openproject.events.raw
    -> transform_raw() parses + normalizes to Event
    -> EventsCache.put()
    -> consumer commits the offset (manual commit, only after cache write)

The consumer runs as a background asyncio task started by
transport.lifespan. On graceful shutdown the cancellation propagates through
`stop()`. Auto-commit is off so the cache write is the source of truth for
replay safety.

CLI shim at the bottom (`python -m ... --from-beginning`) does a full
replay from the earliest offset.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from .events_cache import Event, EventsCache, get_cache
from .kafka_client import KafkaSettings

logger = logging.getLogger(__name__)


def transform_raw(raw: bytes) -> Optional[Event]:
    """Parse a raw webhook payload into a structured `Event`.

    Returns None when the payload can't be coerced (logged at warning) so
    the consumer can skip + commit instead of getting stuck on poison
    records.
    """
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("dropping unparseable kafka record (%d bytes)", len(raw or b""))
        return None
    if not isinstance(payload, dict):
        return None

    event_id = str(payload.get("id") or payload.get("action_id") or "")
    if not event_id:
        return None
    project_id = ""
    emb = payload.get("_embedded")
    if isinstance(emb, dict):
        proj = emb.get("project")
        if isinstance(proj, dict):
            project_id = str(proj.get("id", ""))
    if not project_id:
        project_id = str(payload.get("project_id") or "unknown")
    occurred_at = str(
        payload.get("created_at")
        or payload.get("updated_at")
        or payload.get("timestamp")
        or ""
    )
    action = str(payload.get("action") or payload.get("event") or "unknown")

    return Event(
        event_id=event_id,
        project_id=project_id,
        occurred_at=occurred_at,
        action=action,
        payload=payload,
        raw=raw,
    )


class ReplayConsumer:
    """Owns the consumer loop. transport lifespan starts + stops it.

    `cache` is injectable so tests can pass a fresh EventsCache and assert
    on it without poking globals.
    """

    def __init__(
        self,
        cache: Optional[EventsCache] = None,
        from_beginning: bool = False,
    ) -> None:
        self.cache = cache or get_cache()
        self.from_beginning = from_beginning
        self._consumer: Optional[Any] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        # observable counters. read by tests + (later) prom exporter
        self.records_consumed = 0
        self.records_skipped = 0
        self.commit_errors = 0

    @property
    def offset_reset_mode(self) -> str:
        """Returns 'earliest' for full replay, 'latest' for tail-mode."""
        return "earliest" if self.from_beginning else "latest"

    async def _poll_loop(self) -> None:
        """Drain records one at a time, commit on success."""
        assert self._consumer is not None
        async for msg in self._consumer:
            if self._stop_event.is_set():
                return
            self.records_consumed += 1
            event = transform_raw(getattr(msg, "value", b""))
            if event is None:
                self.records_skipped += 1
                continue
            await self.cache.put(event)
            try:
                await self._consumer.commit()
            except Exception as exc:  # noqa: BLE001
                self.commit_errors += 1
                offset = getattr(msg, "offset", "?")
                logger.exception("commit failed for offset %s: %s", offset, exc)

    async def start(self) -> None:  # pragma: no cover - exercised via integration
        from aiokafka import AIOKafkaConsumer  # noqa: WPS433 - lazy import

        from .kafka_client import _common_consumer_kwargs  # noqa: WPS433

        settings = KafkaSettings.from_env()
        kwargs = _common_consumer_kwargs(settings)
        if self.from_beginning:
            kwargs["auto_offset_reset"] = "earliest"
        if settings.is_msk_iam:
            kwargs["security_protocol"] = settings.security_protocol
            kwargs["sasl_mechanism"] = settings.sasl_mechanism
        self._consumer = AIOKafkaConsumer(settings.topic, **kwargs)
        await self._consumer.start()
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:  # pragma: no cover - exercised via integration
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:  # noqa: BLE001
                logger.exception("error stopping kafka consumer")


def _cli_main(argv: Optional[list] = None) -> None:  # pragma: no cover - CLI glue
    """`python -m openproject_mcp_server.webhooks.consumer` entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="openproject-mcp replay consumer")
    parser.add_argument(
        "--from-beginning",
        action="store_true",
        help="reset consumer group to the earliest offset (full replay)",
    )
    args = parser.parse_args(argv)

    async def _run() -> None:
        c = ReplayConsumer(from_beginning=args.from_beginning)
        await c.start()
        try:
            await asyncio.Event().wait()  # park forever
        finally:
            await c.stop()

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    _cli_main()
