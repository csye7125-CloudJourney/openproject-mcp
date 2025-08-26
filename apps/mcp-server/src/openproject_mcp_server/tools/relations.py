"""Work package relation tools."""

from typing import Any, Awaitable, Callable, Dict, List

from mcp.types import TextContent, Tool

from ._validate import validate_id, validate_input


TOOLS: List[Tool] = [
    Tool(
        name="list_relations",
        description="List relations for a work package",
        inputSchema={
            "type": "object",
            "properties": {"work_package_id": {"type": "string"}},
            "required": ["work_package_id"],
        },
    ),
    Tool(
        name="create_relation",
        description="Create a relation between two work packages",
        inputSchema={
            "type": "object",
            "properties": {
                "work_package_id": {"type": "string"},
                "to_work_package_id": {"type": "string"},
                "type": {"type": "string", "description": "relates|blocks|precedes|follows|duplicates|..."},
            },
            "required": ["work_package_id", "to_work_package_id", "type"],
        },
    ),
    Tool(
        name="list_watchers",
        description="List watchers on a work package",
        inputSchema={
            "type": "object",
            "properties": {"work_package_id": {"type": "string"}},
            "required": ["work_package_id"],
        },
    ),
    Tool(
        name="add_watcher",
        description="Add a watcher (user) to a work package",
        inputSchema={
            "type": "object",
            "properties": {
                "work_package_id": {"type": "string"},
                "user_id": {"type": "string"},
            },
            "required": ["work_package_id", "user_id"],
        },
    ),
]


async def list_relations_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        relations = await api_client.list_relations(wp_id)
        if not relations:
            return [TextContent(type="text", text="No relations found.")]
        lines = [f"Found {len(relations)} relations:\n"]
        for r in relations:
            lines.append(f"- ID: {r.get('id')}, type: {r.get('type', 'relates')}")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing relations: {str(e)}")]


async def create_relation_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        to_id = validate_id(arguments.get("to_work_package_id"), "to_work_package_id")
        rel_type = validate_input(arguments.get("type"), "type", 32)
        payload = {
            "type": rel_type,
            "_links": {"to": {"href": f"/api/v3/work_packages/{to_id}"}},
        }
        relation = await api_client.create_relation(wp_id, payload)
        return [TextContent(type="text", text=f"Relation created (ID: {relation.get('id')}, type: {relation.get('type')})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating relation: {str(e)}")]


async def list_watchers_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        watchers = await api_client.list_watchers(wp_id)
        if not watchers:
            return [TextContent(type="text", text="No watchers.")]
        lines = [f"{len(watchers)} watcher(s):"]
        for w in watchers:
            lines.append(f"- {w.get('name', 'unknown')} (ID: {w.get('id')})")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing watchers: {str(e)}")]


async def add_watcher_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        user_id = validate_id(arguments.get("user_id"), "user_id")
        await api_client.add_watcher(wp_id, user_id)
        return [TextContent(type="text", text=f"User {user_id} added as watcher on {wp_id}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error adding watcher: {str(e)}")]


HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {
    "list_relations": list_relations_impl,
    "create_relation": create_relation_impl,
    "list_watchers": list_watchers_impl,
    "add_watcher": add_watcher_impl,
}
