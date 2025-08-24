"""Tool implementations, split by domain.

Each module exposes a TOOLS list (mcp.types.Tool definitions) and a HANDLERS
dict mapping tool name to async impl. server.py aggregates these at import
time.
"""

from . import (  # noqa: F401
    events,
    lookups,
    memberships,
    misc,
    projects,
    relations,
    time_entries,
    users,
    work_packages,
)
