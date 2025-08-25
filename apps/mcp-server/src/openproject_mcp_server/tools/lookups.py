"""Simple lookup tools: statuses, types, priorities."""

from typing import Any, Awaitable, Callable, Dict, List

from mcp.types import TextContent, Tool


TOOLS: List[Tool] = [
    Tool(
        name="list_statuses",
        description="List work package statuses",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="list_types",
        description="List work package types",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="list_priorities",
        description="List work package priorities",
        inputSchema={"type": "object", "properties": {}},
    ),
]


def _format(items: List[Dict[str, Any]], label: str) -> List[TextContent]:
    if not items:
        return [TextContent(type="text", text=f"No {label} found.")]
    lines = [f"Found {len(items)} {label}:\n"]
    for i in items:
        lines.append(f"- {i.get('name', '?')} (ID: {i.get('id', '?')})")
    return [TextContent(type="text", text="\n".join(lines))]


async def list_statuses_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        return _format(await api_client.list_statuses(), "statuses")
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing statuses: {str(e)}")]


async def list_types_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        return _format(await api_client.list_types(), "types")
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing types: {str(e)}")]


async def list_priorities_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        return _format(await api_client.list_priorities(), "priorities")
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing priorities: {str(e)}")]


HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {
    "list_statuses": list_statuses_impl,
    "list_types": list_types_impl,
    "list_priorities": list_priorities_impl,
}
