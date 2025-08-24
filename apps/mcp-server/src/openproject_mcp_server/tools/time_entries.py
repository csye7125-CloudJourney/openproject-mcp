"""Time entry MCP tools."""

from typing import Any, Awaitable, Callable, Dict, List

from mcp.types import TextContent, Tool

from ._validate import validate_id, validate_input


TOOLS: List[Tool] = [
    Tool(
        name="list_time_entries",
        description="List time entries, optionally filtered by work package",
        inputSchema={
            "type": "object",
            "properties": {
                "work_package_id": {"type": "string"},
            },
        },
    ),
    Tool(
        name="create_time_entry",
        description="Log a time entry against a work package",
        inputSchema={
            "type": "object",
            "properties": {
                "work_package_id": {"type": "string"},
                "hours": {"type": "string", "description": "ISO 8601 duration e.g. PT1H30M"},
                "spent_on": {"type": "string", "description": "Date YYYY-MM-DD"},
                "comment": {"type": "string"},
            },
            "required": ["work_package_id", "hours"],
        },
    ),
]


async def list_time_entries_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = None
        if arguments.get("work_package_id"):
            wp_id = validate_id(arguments["work_package_id"], "work_package_id")
        entries = await api_client.list_time_entries(work_package_id=wp_id)
        if not entries:
            return [TextContent(type="text", text="No time entries found.")]
        lines = [f"Found {len(entries)} time entries:\n"]
        for entry in entries:
            lines.append(
                f"- ID: {entry.get('id')}, hours: {entry.get('hours', '?')}, "
                f"comment: {entry.get('comment', {}).get('raw', '') if isinstance(entry.get('comment'), dict) else entry.get('comment', '')}"
            )
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing time entries: {str(e)}")]


async def create_time_entry_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        hours = validate_input(arguments.get("hours"), "hours", 32)
        payload: Dict[str, Any] = {
            "hours": hours,
            "_links": {
                "workPackage": {"href": f"/api/v3/work_packages/{wp_id}"},
            },
        }
        if arguments.get("spent_on"):
            payload["spentOn"] = validate_input(arguments["spent_on"], "spent_on", 10)
        if arguments.get("comment"):
            payload["comment"] = {"raw": validate_input(arguments["comment"], "comment", 1000)}
        entry = await api_client.create_time_entry(payload)
        return [TextContent(type="text", text=f"Time entry created (ID: {entry.get('id')}, hours: {entry.get('hours')})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating time entry: {str(e)}")]


HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {
    "list_time_entries": list_time_entries_impl,
    "create_time_entry": create_time_entry_impl,
}
