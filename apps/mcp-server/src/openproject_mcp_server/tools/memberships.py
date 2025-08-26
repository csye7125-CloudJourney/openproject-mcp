"""Membership MCP tools."""

from typing import Any, Awaitable, Callable, Dict, List

from mcp.types import TextContent, Tool

from ._validate import validate_id


TOOLS: List[Tool] = [
    Tool(
        name="list_memberships",
        description="List project memberships, optionally filtered by project id",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
        },
    ),
    Tool(
        name="create_membership",
        description="Add a user to a project with a role",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "user_id": {"type": "string"},
                "role_id": {"type": "string"},
            },
            "required": ["project_id", "user_id", "role_id"],
        },
    ),
]


async def list_memberships_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        project_id = None
        if arguments.get("project_id"):
            project_id = validate_id(arguments["project_id"], "project_id")
        members = await api_client.list_memberships(project_id=project_id)
        if not members:
            return [TextContent(type="text", text="No memberships found.")]
        lines = [f"Found {len(members)} memberships:"]
        for m in members:
            lines.append(f"- ID: {m.get('id')}")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing memberships: {str(e)}")]


async def create_membership_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        project_id = validate_id(arguments.get("project_id"), "project_id")
        user_id = validate_id(arguments.get("user_id"), "user_id")
        role_id = validate_id(arguments.get("role_id"), "role_id")
        payload = {
            "_links": {
                "project": {"href": f"/api/v3/projects/{project_id}"},
                "principal": {"href": f"/api/v3/users/{user_id}"},
                "roles": [{"href": f"/api/v3/roles/{role_id}"}],
            }
        }
        membership = await api_client.create_membership(payload)
        return [TextContent(type="text", text=f"Membership created (ID: {membership.get('id')})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating membership: {str(e)}")]


HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {
    "list_memberships": list_memberships_impl,
    "create_membership": create_membership_impl,
}
