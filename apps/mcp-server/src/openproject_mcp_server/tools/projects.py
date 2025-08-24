"""Project-domain MCP tools."""

from typing import Any, Awaitable, Callable, Dict, List

from mcp.types import TextContent, Tool

from ._validate import validate_id, validate_input


TOOLS: List[Tool] = [
    Tool(
        name="list_projects",
        description="List all accessible OpenProject projects",
        inputSchema={
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "name": {"type": "string"},
                    },
                }
            },
        },
    ),
    Tool(
        name="get_project_details",
        description="Get detailed information about a specific OpenProject project",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    ),
    Tool(
        name="create_project",
        description="Create a new OpenProject project",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "identifier": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["name", "identifier"],
        },
    ),
    Tool(
        name="update_project",
        description="Update an existing project's name or description",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["project_id"],
        },
    ),
    Tool(
        name="delete_project",
        description="Delete a project by id",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    ),
]


async def list_projects_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        filters = arguments.get("filters", {}) or {}
        validated: Dict[str, Any] = {}
        if isinstance(filters, dict):
            for key, value in filters.items():
                if key in ("status", "name") and value:
                    validated[key] = validate_input(value, f"filter_{key}", 100)
        projects = await api_client.get_projects(filters=validated)
        if not projects:
            return [TextContent(type="text", text="No projects found matching the specified criteria.")]
        lines = [f"Found {len(projects)} projects:\n"]
        for project in projects:
            info = [
                f"**{project.get('name', 'Unnamed Project')}** (ID: {project.get('id')})",
                f"  Status: {project.get('status', {}).get('name', 'Unknown')}",
            ]
            if project.get('description'):
                desc = project['description']
                if isinstance(desc, dict):
                    desc = desc.get('raw', '')
                if len(desc) > 100:
                    desc = desc[:100] + "..."
                info.append(f"  Description: {desc}")
            if project.get('createdAt'):
                info.append(f"  Created: {project['createdAt']}")
            lines.append("\n".join(info))
            lines.append("")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error retrieving projects: {str(e)}")]


async def get_project_details_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        project_id = validate_id(arguments.get("project_id"), "project_id")
        project = await api_client.get_project_details(project_id)
        lines = [
            f"# Project Details: {project.get('name', 'Unnamed Project')}",
            "",
            f"**ID:** {project.get('id')}",
            f"**Status:** {project.get('status', {}).get('name', 'Unknown')}",
        ]
        if project.get('description'):
            lines.append(f"**Description:** {project['description']}")
        if project.get('createdAt'):
            lines.append(f"**Created:** {project['createdAt']}")
        if project.get('updatedAt'):
            lines.append(f"**Updated:** {project['updatedAt']}")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error retrieving project details: {str(e)}")]


async def create_project_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        name = validate_input(arguments.get("name"), "name", 255)
        identifier = validate_id(arguments.get("identifier"), "identifier")
        payload: Dict[str, Any] = {"name": name, "identifier": identifier}
        if arguments.get("description"):
            payload["description"] = {"raw": validate_input(arguments["description"], "description", 5000)}
        project = await api_client.create_project(payload)
        return [TextContent(type="text", text=f"Project created: {project.get('name')} (ID: {project.get('id')})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating project: {str(e)}")]


async def update_project_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        project_id = validate_id(arguments.get("project_id"), "project_id")
        payload: Dict[str, Any] = {}
        if arguments.get("name"):
            payload["name"] = validate_input(arguments["name"], "name", 255)
        if arguments.get("description"):
            payload["description"] = {"raw": validate_input(arguments["description"], "description", 5000)}
        if not payload:
            return [TextContent(type="text", text="Error: no fields to update")]
        project = await api_client.update_project(project_id, payload)
        return [TextContent(type="text", text=f"Project updated: {project.get('name')} (ID: {project.get('id')})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error updating project: {str(e)}")]


async def delete_project_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        project_id = validate_id(arguments.get("project_id"), "project_id")
        await api_client.delete_project(project_id)
        return [TextContent(type="text", text=f"Project {project_id} deleted")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error deleting project: {str(e)}")]


HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {
    "list_projects": list_projects_impl,
    "get_project_details": get_project_details_impl,
    "create_project": create_project_impl,
    "update_project": update_project_impl,
    "delete_project": delete_project_impl,
}
