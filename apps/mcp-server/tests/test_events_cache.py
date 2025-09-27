"""Tests for the bounded LRU events cache."""

import asyncio

import pytest

from openproject_mcp_server.webhooks.events_cache import Event, EventsCache


def _evt(eid: str, pid: str, ts: str = "2025-08-28T00:00:00Z", action: str = "wp:updated"):
    return Event(event_id=eid, project_id=pid, occurred_at=ts, action=action, payload={})


@pytest.mark.asyncio
async def test_put_and_get_recent_returns_event():
    cache = EventsCache(max_entries=10)
    await cache.put(_evt("e1", "p1"))
    out = await cache.get_recent("p1")
    assert len(out) == 1
    assert out[0].event_id == "e1"


@pytest.mark.asyncio
async def test_get_recent_is_newest_first():
    cache = EventsCache(max_entries=10)
    await cache.put(_evt("e1", "p1", ts="2025-08-28T00:00:00Z"))
    await cache.put(_evt("e2", "p1", ts="2025-08-28T00:00:01Z"))
    await cache.put(_evt("e3", "p1", ts="2025-08-28T00:00:02Z"))
    out = await cache.get_recent("p1")
    assert [e.event_id for e in out] == ["e3", "e2", "e1"]


@pytest.mark.asyncio
async def test_get_recent_filters_by_since():
    cache = EventsCache(max_entries=10)
    await cache.put(_evt("e1", "p1", ts="2025-08-28T00:00:00Z"))
    await cache.put(_evt("e2", "p1", ts="2025-08-28T01:00:00Z"))
    await cache.put(_evt("e3", "p1", ts="2025-08-28T02:00:00Z"))
    out = await cache.get_recent("p1", since="2025-08-28T01:00:00Z")
    assert {e.event_id for e in out} == {"e2", "e3"}


@pytest.mark.asyncio
async def test_get_recent_other_project_isolated():
    cache = EventsCache(max_entries=10)
    await cache.put(_evt("e1", "p1"))
    await cache.put(_evt("e2", "p2"))
    out = await cache.get_recent("p1")
    assert [e.event_id for e in out] == ["e1"]


@pytest.mark.asyncio
async def test_get_recent_limit():
    cache = EventsCache(max_entries=100)
    for i in range(20):
        await cache.put(_evt(f"e{i}", "p1", ts=f"2025-08-28T00:00:{i:02d}Z"))
    out = await cache.get_recent("p1", limit=5)
    assert len(out) == 5
    # newest first => e19, e18, e17, e16, e15
    assert [e.event_id for e in out] == [f"e{19 - i}" for i in range(5)]


@pytest.mark.asyncio
async def test_lru_eviction_drops_oldest():
    cache = EventsCache(max_entries=3)
    await cache.put(_evt("a", "p"))
    await cache.put(_evt("b", "p"))
    await cache.put(_evt("c", "p"))
    await cache.put(_evt("d", "p"))  # evicts 'a'
    assert await cache.size() == 3
    ids = {e.event_id for e in await cache.get_recent("p")}
    assert ids == {"b", "c", "d"}


@pytest.mark.asyncio
async def test_update_existing_event_moves_to_end():
    cache = EventsCache(max_entries=3)
    await cache.put(_evt("a", "p"))
    await cache.put(_evt("b", "p"))
    await cache.put(_evt("c", "p"))
    # touch 'a' so it is now newest in insertion order. eviction should now
    # drop 'b' (the new oldest).
    await cache.put(_evt("a", "p"))
    await cache.put(_evt("d", "p"))
    ids = {e.event_id for e in await cache.get_recent("p")}
    assert ids == {"a", "c", "d"}


@pytest.mark.asyncio
async def test_project_index_cleared_when_last_event_evicted():
    cache = EventsCache(max_entries=2)
    await cache.put(_evt("a", "p1"))
    await cache.put(_evt("b", "p2"))
    await cache.put(_evt("c", "p3"))  # evicts 'a' -> p1 has no events
    out_p1 = await cache.get_recent("p1")
    assert out_p1 == []


@pytest.mark.asyncio
async def test_concurrent_writes_are_safe():
    cache = EventsCache(max_entries=500)

    async def writer(start: int):
        for i in range(start, start + 100):
            await cache.put(_evt(f"e{i}", "p1", ts=f"2025-08-28T00:{i // 60:02d}:{i % 60:02d}Z"))

    await asyncio.gather(writer(0), writer(100), writer(200), writer(300))
    # 400 unique ids, well under the cap, so all survive
    assert await cache.size() == 400


@pytest.mark.asyncio
async def test_clear_resets_state():
    cache = EventsCache(max_entries=10)
    await cache.put(_evt("a", "p"))
    await cache.clear()
    assert await cache.size() == 0
    assert await cache.get_recent("p") == []
