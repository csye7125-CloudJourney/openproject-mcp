"""User MCP tools."""

from typing import Any, Awaitable, Callable, Dict, List

from mcp.types import TextContent, Tool

from ._validate import validate_id


TOOLS: List[Tool] = [
    Tool(
        name="list_users",
        description="List all users in the OpenProject instance",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_user",
        description="Get a single user by id",
        inputSchema={
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
            "required": ["user_id"],
        },
    ),
]


async def list_users_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        users = await api_client.get_users()
        if not users:
            return [TextContent(type="text", text="No users found.")]
        lines = [f"Found {len(users)} users:\n"]
        for user in users:
            info = [
                f"**{user.get('name', 'Unknown User')}** (ID: {user.get('id')})",
                f"  Email: {user.get('email', 'No email')}",
                f"  Status: {user.get('status', 'Unknown')}",
            ]
            lines.append("\n".join(info))
            lines.append("")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error retrieving users: {str(e)}")]


async def get_user_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        user_id = validate_id(arguments.get("user_id"), "user_id")
        user = await api_client.get_user(user_id)
        lines = [
            f"# User: {user.get('name', 'Unknown')}",
            "",
            f"**ID:** {user.get('id')}",
            f"**Email:** {user.get('email', 'No email')}",
            f"**Status:** {user.get('status', 'Unknown')}",
        ]
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error retrieving user: {str(e)}")]


HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {
    "list_users": list_users_impl,
    "get_user": get_user_impl,
}
