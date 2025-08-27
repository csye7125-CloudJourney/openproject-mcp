"""Tests for prometheus metrics wiring."""

import pytest

from openproject_mcp_server import server
from openproject_mcp_server.metrics import tool_calls_total, tool_latency_seconds


@pytest.mark.asyncio
async def test_tool_calls_counter_increments_on_known_tool(mock_api_client):
    """Calling a known tool should bump the success-outcome counter."""
    original = server.api_client
    server.api_client = mock_api_client
    before = tool_calls_total.labels(tool_name="list_projects", outcome="success")._value.get()
    try:
        await server.handle_call_tool("list_projects", {})
    finally:
        server.api_client = original
    after = tool_calls_total.labels(tool_name="list_projects", outcome="success")._value.get()
    assert after == before + 1


@pytest.mark.asyncio
async def test_tool_calls_counter_increments_on_unknown_tool():
    before = tool_calls_total.labels(tool_name="nope_not_real", outcome="unknown")._value.get()
    await server.handle_call_tool("nope_not_real", {})
    after = tool_calls_total.labels(tool_name="nope_not_real", outcome="unknown")._value.get()
    assert after == before + 1


@pytest.mark.asyncio
async def test_tool_latency_histogram_observes(mock_api_client):
    original = server.api_client
    server.api_client = mock_api_client
    metric = tool_latency_seconds.labels(tool_name="list_users", outcome="success")
    before = metric._sum.get()
    try:
        await server.handle_call_tool("list_users", {})
    finally:
        server.api_client = original
    after = metric._sum.get()
    assert after > before
