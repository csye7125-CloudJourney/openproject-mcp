"""Catch-all tools that don't justify their own domain module yet.

Holds attachments, categories, versions, activities, queries, search,
hierarchy. Will probably split out if any of these grow more endpoints.
"""

from typing import Any, Awaitable, Callable, Dict, List

from mcp.types import TextContent, Tool

from ._validate import validate_id, validate_input


TOOLS: List[Tool] = [
    Tool(
        name="list_attachments",
        description="List attachments on a work package",
        inputSchema={
            "type": "object",
            "properties": {"work_package_id": {"type": "string"}},
            "required": ["work_package_id"],
        },
    ),
    Tool(
        name="list_categories",
        description="List categories for a project",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    ),
    Tool(
        name="list_versions",
        description="List versions for a project",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    ),
    Tool(
        name="create_version",
        description="Create a version inside a project",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["project_id", "name"],
        },
    ),
    Tool(
        name="list_activities",
        description="List activities (changes/comments) on a work package",
        inputSchema={
            "type": "object",
            "properties": {"work_package_id": {"type": "string"}},
            "required": ["work_package_id"],
        },
    ),
    Tool(
        name="list_queries",
        description="List saved queries",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="search_work_packages",
        description="Free-text search across work packages",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    ),
    Tool(
        name="get_project_hierarchy",
        description="Get the project tree (parent-child relationships)",
        inputSchema={"type": "object", "properties": {}},
    ),
]


def _format_named(items: List[Dict[str, Any]], label: str) -> List[TextContent]:
    if not items:
        return [TextContent(type="text", text=f"No {label} found.")]
    lines = [f"Found {len(items)} {label}:"]
    for i in items:
        lines.append(f"- {i.get('name', i.get('id', '?'))} (ID: {i.get('id', '?')})")
    return [TextContent(type="text", text="\n".join(lines))]


async def list_attachments_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        return _format_named(await api_client.list_attachments(wp_id), "attachments")
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing attachments: {str(e)}")]


async def list_categories_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        project_id = validate_id(arguments.get("project_id"), "project_id")
        return _format_named(await api_client.list_categories(project_id), "categories")
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing categories: {str(e)}")]


async def list_versions_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        project_id = validate_id(arguments.get("project_id"), "project_id")
        return _format_named(await api_client.list_versions(project_id), "versions")
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing versions: {str(e)}")]


async def create_version_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        project_id = validate_id(arguments.get("project_id"), "project_id")
        name = validate_input(arguments.get("name"), "name", 255)
        v = await api_client.create_version(project_id, {"name": name})
        return [TextContent(type="text", text=f"Version created: {v.get('name')} (ID: {v.get('id')})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating version: {str(e)}")]


async def list_activities_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        wp_id = validate_id(arguments.get("work_package_id"), "work_package_id")
        acts = await api_client.list_activities(wp_id)
        if not acts:
            return [TextContent(type="text", text="No activities found.")]
        lines = [f"Found {len(acts)} activities:"]
        for a in acts:
            lines.append(f"- ID: {a.get('id')}, type: {a.get('_type', '?')}")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing activities: {str(e)}")]


async def list_queries_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        return _format_named(await api_client.list_queries(), "queries")
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing queries: {str(e)}")]


async def search_work_packages_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        query = validate_input(arguments.get("query"), "query", 200)
        wps = await api_client.search_work_packages(query)
        if not wps:
            return [TextContent(type="text", text=f"No work packages matched '{query}'.")]
        lines = [f"Found {len(wps)} matching work packages:"]
        for wp in wps:
            lines.append(f"- {wp.get('subject', '?')} (ID: {wp.get('id')})")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error searching work packages: {str(e)}")]


async def get_project_hierarchy_impl(api_client, arguments: Dict[str, Any]) -> List[TextContent]:
    if not api_client:
        return [TextContent(type="text", text="Error: API client not initialized")]
    try:
        projects = await api_client.get_project_hierarchy()
        if not projects:
            return [TextContent(type="text", text="No projects found.")]
        lines = [f"Project hierarchy ({len(projects)} nodes):"]
        for p in projects:
            parent = p.get('_links', {}).get('parent', {}).get('href')
            parent_str = f" -> parent: {parent}" if parent else " (root)"
            lines.append(f"- {p.get('name', '?')} (ID: {p.get('id')}){parent_str}")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching hierarchy: {str(e)}")]


HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {
    "list_attachments": list_attachments_impl,
    "list_categories": list_categories_impl,
    "list_versions": list_versions_impl,
    "create_version": create_version_impl,
    "list_activities": list_activities_impl,
    "list_queries": list_queries_impl,
    "search_work_packages": search_work_packages_impl,
    "get_project_hierarchy": get_project_hierarchy_impl,
}
