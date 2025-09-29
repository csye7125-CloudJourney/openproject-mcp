"""Tests for the replay consumer.

We exercise `transform_raw` directly and feed a fake async-iterable consumer
into `ReplayConsumer._poll_loop` so the test never touches real kafka.
"""

import json

import pytest

from openproject_mcp_server.webhooks.consumer import ReplayConsumer, transform_raw
from openproject_mcp_server.webhooks.events_cache import EventsCache


class FakeMsg:
    def __init__(self, value: bytes, offset: int = 0):
        self.value = value
        self.offset = offset


class FakeConsumer:
    """Minimal async-iterable + commit() that ReplayConsumer can drive."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.committed = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def commit(self):
        self.committed += 1


def test_transform_raw_basic():
    payload = {
        "id": "abc",
        "action": "work_package:updated",
        "_embedded": {"project": {"id": 7}},
        "created_at": "2025-08-29T10:00:00Z",
    }
    event = transform_raw(json.dumps(payload).encode())
    assert event is not None
    assert event.event_id == "abc"
    assert event.project_id == "7"
    assert event.action == "work_package:updated"
    assert event.occurred_at == "2025-08-29T10:00:00Z"


def test_transform_raw_invalid_json_returns_none():
    assert transform_raw(b"not json{") is None


def test_transform_raw_no_id_returns_none():
    assert transform_raw(json.dumps({"action": "x"}).encode()) is None


def test_transform_raw_top_level_project_id_fallback():
    payload = {"id": "evt", "project_id": "55", "action": "wp:new"}
    event = transform_raw(json.dumps(payload).encode())
    assert event is not None
    assert event.project_id == "55"


def test_transform_raw_action_id_fallback():
    payload = {"action_id": 42, "_embedded": {"project": {"id": 1}}}
    event = transform_raw(json.dumps(payload).encode())
    assert event is not None
    assert event.event_id == "42"


@pytest.mark.asyncio
async def test_poll_loop_writes_to_cache_and_commits():
    cache = EventsCache(max_entries=100)
    consumer = ReplayConsumer(cache=cache)
    messages = [
        FakeMsg(json.dumps({"id": "1", "_embedded": {"project": {"id": "p1"}}, "action": "a"}).encode()),
        FakeMsg(json.dumps({"id": "2", "_embedded": {"project": {"id": "p1"}}, "action": "b"}).encode()),
        FakeMsg(json.dumps({"id": "3", "_embedded": {"project": {"id": "p2"}}, "action": "c"}).encode()),
    ]
    fake = FakeConsumer(messages)
    consumer._consumer = fake
    await consumer._poll_loop()
    assert await cache.size() == 3
    assert fake.committed == 3
    p1 = await cache.get_recent("p1")
    assert {e.event_id for e in p1} == {"1", "2"}


@pytest.mark.asyncio
async def test_poll_loop_skips_poison_records():
    cache = EventsCache(max_entries=100)
    consumer = ReplayConsumer(cache=cache)
    fake = FakeConsumer([
        FakeMsg(b"this is not json{"),
        FakeMsg(json.dumps({"id": "good", "_embedded": {"project": {"id": "p1"}}}).encode()),
    ])
    consumer._consumer = fake
    await consumer._poll_loop()
    assert await cache.size() == 1
    # only the good record committed
    assert fake.committed == 1


def test_from_beginning_changes_offset_reset_mode():
    tail = ReplayConsumer(from_beginning=False)
    full = ReplayConsumer(from_beginning=True)
    assert tail.offset_reset_mode == "latest"
    assert full.offset_reset_mode == "earliest"


@pytest.mark.asyncio
async def test_poll_loop_records_counters():
    cache = EventsCache(max_entries=100)
    consumer = ReplayConsumer(cache=cache)
    fake = FakeConsumer([
        FakeMsg(b"junk{"),
        FakeMsg(json.dumps({"id": "ok", "_embedded": {"project": {"id": "p1"}}}).encode()),
    ])
    consumer._consumer = fake
    await consumer._poll_loop()
    assert consumer.records_consumed == 2
    assert consumer.records_skipped == 1
    assert consumer.commit_errors == 0


@pytest.mark.asyncio
async def test_poll_loop_continues_when_commit_fails():
    class FlakyConsumer(FakeConsumer):
        async def commit(self):
            self.committed += 1
            if self.committed == 1:
                raise RuntimeError("transient")

    cache = EventsCache(max_entries=100)
    consumer = ReplayConsumer(cache=cache)
    fake = FlakyConsumer([
        FakeMsg(json.dumps({"id": "1", "_embedded": {"project": {"id": "p1"}}}).encode()),
        FakeMsg(json.dumps({"id": "2", "_embedded": {"project": {"id": "p1"}}}).encode()),
    ])
    consumer._consumer = fake
    # should not raise even though first commit failed
    await consumer._poll_loop()
    assert await cache.size() == 2
