"""MCP tool: get_recent_events.

Reads from the in-memory events cache that the kafka replay consumer
populates. This is the user-facing read path for the webhook pipeline.
Other tools call OpenProject directly. this one is fed by kafka.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict, List

from mcp.types import TextContent, Tool

from ..webhooks.events_cache import get_cache
from ._validate import validate_id, validate_input

TOOLS: List[Tool] = [
    Tool(
        name="get_recent_events",
        description=(
            "Return recent OpenProject events (webhook-sourced, kafka-replayed) "
            "for a project. Optionally filter by an ISO 8601 timestamp via `since`."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "OpenProject project id",
                },
                "since": {
                    "type": "string",
                    "description": (
                        "ISO 8601 timestamp; "
                        "only events with occurred_at >= since are returned"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": (
                        "Maximum number of events to return (default 50, max 500)"
                    ),
                    "minimum": 1,
                    "maximum": 500,
                },
            },
            "required": ["project_id"],
        },
    ),
]


async def get_recent_events_impl(
    api_client,  # noqa: ARG001 - kept for handler signature uniformity
    arguments: Dict[str, Any],
) -> List[TextContent]:
    """Read recent events for `project_id` from the in-memory cache."""
    try:
        project_id = validate_id(arguments.get("project_id"), "project_id")
    except ValueError as exc:
        return [TextContent(type="text", text=f"Error: {exc}")]

    since = arguments.get("since")
    if since is not None:
        try:
            since = validate_input(since, "since", max_length=64)
        except ValueError as exc:
            return [TextContent(type="text", text=f"Error: {exc}")]

    raw_limit = arguments.get("limit", 50)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return [TextContent(type="text", text="Error: limit must be an integer")]
    if limit < 1 or limit > 500:
        return [TextContent(type="text", text="Error: limit must be between 1 and 500")]

    cache = get_cache()
    events = await cache.get_recent(project_id, since=since, limit=limit)
    if not events:
        msg = f"No recent events found for project {project_id}."
        return [TextContent(type="text", text=msg)]

    summary = [f"Found {len(events)} events for project {project_id}:"]
    for event in events:
        summary.append(
            f"- {event.occurred_at} {event.action} (id: {event.event_id})"
        )
    payload = json.dumps(
        [
            {
                "event_id": e.event_id,
                "project_id": e.project_id,
                "occurred_at": e.occurred_at,
                "action": e.action,
            }
            for e in events
        ],
        sort_keys=True,
    )
    return [
        TextContent(type="text", text="\n".join(summary)),
        TextContent(type="text", text=payload),
    ]


HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {
    "get_recent_events": get_recent_events_impl,
}
