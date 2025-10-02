"""Tests for the get_recent_events MCP tool."""

import json

import pytest
import pytest_asyncio

from openproject_mcp_server import server
from openproject_mcp_server.tools.events import (
    HANDLERS,
    TOOLS,
    get_recent_events_impl,
)
from openproject_mcp_server.webhooks.events_cache import Event, get_cache


@pytest_asyncio.fixture(autouse=True)
async def _clean_cache():
    cache = get_cache()
    await cache.clear()
    yield
    await cache.clear()


def test_tool_registered_in_server_tools():
    names = {t.name for t in server.TOOLS}
    assert "get_recent_events" in names
    assert "get_recent_events" in server.HANDLERS


def test_tool_schema_requires_project_id():
    tool = next(t for t in TOOLS if t.name == "get_recent_events")
    assert "project_id" in tool.inputSchema["required"]


def test_tool_registered_in_module_handlers():
    assert "get_recent_events" in HANDLERS


@pytest.mark.asyncio
async def test_returns_empty_message_when_cache_empty():
    out = await get_recent_events_impl(None, {"project_id": "42"})
    assert len(out) == 1
    assert "No recent events" in out[0].text


@pytest.mark.asyncio
async def test_returns_recent_events_summary_and_json():
    cache = get_cache()
    await cache.put(Event(
        event_id="e1", project_id="42", occurred_at="2025-08-31T00:00:00Z",
        action="work_package:created", payload={},
    ))
    await cache.put(Event(
        event_id="e2", project_id="42", occurred_at="2025-08-31T01:00:00Z",
        action="work_package:updated", payload={},
    ))
    out = await get_recent_events_impl(None, {"project_id": "42"})
    # text content is the summary, json content is structured payload
    assert len(out) == 2
    assert "Found 2 events" in out[0].text
    assert "e1" in out[0].text and "e2" in out[0].text
    parsed = json.loads(out[1].text)
    assert {e["event_id"] for e in parsed} == {"e1", "e2"}


@pytest.mark.asyncio
async def test_since_filter_applied():
    cache = get_cache()
    await cache.put(Event(
        event_id="old", project_id="p", occurred_at="2025-08-30T00:00:00Z",
        action="wp:a", payload={},
    ))
    await cache.put(Event(
        event_id="new", project_id="p", occurred_at="2025-08-31T00:00:00Z",
        action="wp:b", payload={},
    ))
    out = await get_recent_events_impl(None, {
        "project_id": "p",
        "since": "2025-08-30T12:00:00Z",
    })
    assert "Found 1 events" in out[0].text
    parsed = json.loads(out[1].text)
    assert [e["event_id"] for e in parsed] == ["new"]


@pytest.mark.asyncio
async def test_limit_capped():
    out = await get_recent_events_impl(None, {"project_id": "p", "limit": 9999})
    assert "limit must be between" in out[0].text


@pytest.mark.asyncio
async def test_limit_zero_rejected():
    out = await get_recent_events_impl(None, {"project_id": "p", "limit": 0})
    assert "limit must be between" in out[0].text


@pytest.mark.asyncio
async def test_invalid_project_id_rejected():
    out = await get_recent_events_impl(None, {"project_id": "bad id!!"})
    assert out[0].text.startswith("Error:")


@pytest.mark.asyncio
async def test_dispatch_via_server_handler(mock_api_client):
    """Calling through server.handle_call_tool exercises the dispatch table."""
    original = server.api_client
    server.api_client = mock_api_client
    try:
        result = await server.handle_call_tool("get_recent_events", {"project_id": "42"})
    finally:
        server.api_client = original
    # cache empty -> 1 message
    assert len(result) >= 1
    assert "No recent events" in result[0].text
