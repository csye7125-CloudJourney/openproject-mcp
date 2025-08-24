"""Work package MCP tools."""

from typing import Any, Awaitable, Callable, Dict, List

from mcp.types import TextContent, Tool

from ._validate import validate_id, validate_input


TOOLS: List[Tool] = [
    Tool(
        name="list_work_packages",
        description="List work packages with optional filtering",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "filters": {
                    "type": "object",
                    "properties": {
                        "assignee": {"type": "string"},
                        "status": {"type": "string"},
                        "type": {"type": "string"},
                    },
                },
            },
        },
    ),
    Tool(
        name="get_work_package",
        description="Get detailed information about a specific work package",
        inputSchema={
            "type": "object",
            "properties": {"work_package_id": {"type": "string"}},
            "required": ["work_package_id"],
        },
    ),
    Tool(
        name="create_work_package",
        description="Create a new work package in OpenProject",
        inputSchema={
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "project_id": {"type": "string"},
                "type_id": {"type": "string"},
                "description": {"type": "string"},
                "assignee_id": {"type": "string"},
            },
            "required": ["subject", "project_id", "type_id"],
        },
    ),
    Tool(
        name="update_work_package",
        description="Update an existing work package (subject/description/etc.)",
        inputSchema={
            "type": "object",
            "properties": {
                "work_package_id": {"type": "string"},
                "lock_version": {"type": "integer"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["work_package_id", "lock_version"],
        },
    ),
    Tool(
        name="delete_work_package",
        description="Delete a work package by id",
        inputSchema={
            "type": "object",
            "properties": {"work_package_id": {"type": "string"}},
            "required": ["work_package_id"],
        },
    ),
]


async def list_work_packages_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        project_id = None
        if arguments.get("project_id"):
            project_id = validate_id(arguments["project_id"], "project_id")
        filters = arguments.get("filters", {}) or {}
        validated: Dict[str, Any] = {}
        if isinstance(filters, dict):
            for key, value in filters.items():
                if key in ("assignee", "status", "type") and value:
                    validated[key] = validate_input(value, f"filter_{key}", 100)
        work_packages = await api_client.get_work_packages(project_id=project_id, filters=validated)
        if not work_packages:
            return [TextContent(type="text", text="No work packages found matching the specified criteria.")]
        lines = [f"Found {len(work_packages)} work packages:\n"]
        for wp in work_packages:
            info = [
                f"**{wp.get('subject', 'Untitled Work Package')}** (ID: {wp.get('id')})",
                f"  Status: {wp.get('_embedded', {}).get('status', {}).get('name', 'Unknown')}",
                f"  Type: {wp.get('_embedded', {}).get('type', {}).get('name', 'Unknown')}",
            ]
            assignee = wp.get('_embedded', {}).get('assignee')
            if assignee:
                info.append(f"  Assignee: {assignee.get('name', 'Unknown')}")
            if wp.get('dueDate'):
                info.append(f"  Due Date: {wp['dueDate']}")
            lines.append("\n".join(info))
            lines.append("")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error retrieving work packages: {str(e)}")]


async def get_work_package_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        wp = await api_client.get_work_package(wp_id)
        lines = [
            f"# Work Package Details: {wp.get('subject', 'Untitled Work Package')}",
            "",
            f"**ID:** {wp.get('id')}",
            f"**Status:** {wp.get('_embedded', {}).get('status', {}).get('name', 'Unknown')}",
            f"**Type:** {wp.get('_embedded', {}).get('type', {}).get('name', 'Unknown')}",
        ]
        description = wp.get('description')
        if description and isinstance(description, dict) and description.get('raw'):
            lines.extend(["", "**Description:**", description['raw']])
        assignee = wp.get('_embedded', {}).get('assignee')
        if assignee:
            lines.append(f"**Assignee:** {assignee.get('name', 'Unknown')}")
        if wp.get('createdAt'):
            lines.append(f"**Created:** {wp['createdAt']}")
        if wp.get('dueDate'):
            lines.append(f"**Due Date:** {wp['dueDate']}")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error retrieving work package details: {str(e)}")]


async def create_work_package_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        subject = validate_input(arguments.get("subject"), "subject", 255)
        project_id = validate_id(arguments.get("project_id"), "project_id")
        type_id = validate_id(arguments.get("type_id"), "type_id")
        payload: Dict[str, Any] = {
            "subject": subject,
            "_links": {
                "project": {"href": f"/api/v3/projects/{project_id}"},
                "type": {"href": f"/api/v3/types/{type_id}"},
            },
        }
        if arguments.get("description"):
            payload["description"] = {"raw": validate_input(arguments["description"], "description", 5000)}
        if arguments.get("assignee_id"):
            assignee_id = validate_id(arguments["assignee_id"], "assignee_id")
            payload["_links"]["assignee"] = {"href": f"/api/v3/users/{assignee_id}"}
        wp = await api_client.create_work_package(payload)
        return [TextContent(type="text", text=f"Work package created successfully: {wp.get('subject')} (ID: {wp.get('id')})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating work package: {str(e)}")]


async def update_work_package_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        lock_version = arguments.get("lock_version")
        if lock_version is None:
            return [TextContent(type="text", text="Error: lock_version required")]
        payload: Dict[str, Any] = {"lockVersion": int(lock_version)}
        if arguments.get("subject"):
            payload["subject"] = validate_input(arguments["subject"], "subject", 255)
        if arguments.get("description"):
            payload["description"] = {"raw": validate_input(arguments["description"], "description", 5000)}
        wp = await api_client.update_work_package(wp_id, payload)
        return [TextContent(type="text", text=f"Work package updated: {wp.get('subject')} (ID: {wp.get('id')})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error updating work package: {str(e)}")]


async def delete_work_package_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        await api_client.delete_work_package(wp_id)
        return [TextContent(type="text", text=f"Work package {wp_id} deleted")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error deleting work package: {str(e)}")]


HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {
    "list_work_packages": list_work_packages_impl,
    "get_work_package": get_work_package_impl,
    "create_work_package": create_work_package_impl,
    "update_work_package": update_work_package_impl,
    "delete_work_package": delete_work_package_impl,
}
