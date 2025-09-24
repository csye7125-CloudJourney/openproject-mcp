"""Bounded in-memory cache of recent OpenProject events.

The replay consumer writes here, the `get_recent_events` MCP tool reads
here. Backed by a single OrderedDict so we get LRU eviction for free.
Bumping an entry moves it to the end, evictions pop from the front.

Asyncio-safe: every read and write holds the same `asyncio.Lock`. Fine for
our workload (low thousands of events/sec, O(1) ops per entry).
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# default cap. keeps memory bounded to a few MB even with verbose payloads
DEFAULT_MAX_ENTRIES = 10_000


@dataclass
class Event:
    """Normalized event stored in the cache.

    Original raw bytes survive in `raw` so downstream tooling can replay,
    but most consumers just read the structured fields.
    """

    event_id: str
    project_id: str
    occurred_at: str  # ISO 8601 string, sourced from the webhook payload
    action: str
    payload: Dict[str, Any] = field(default_factory=dict)
    raw: bytes = b""


class EventsCache:
    """LRU-bounded cache keyed by event_id, indexed by project_id."""

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._max = int(max_entries)
        # ordered by insertion / last-touch. newest at the right end.
        self._store: "OrderedDict[str, Event]" = OrderedDict()
        # secondary index project_id -> [event_id, ...], arrival order
        self._by_project: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()

    @property
    def max_entries(self) -> int:
        return self._max

    async def put(self, event: Event) -> None:
        """Insert (or update) an event, evicting the oldest if over cap."""
        async with self._lock:
            if event.event_id in self._store:
                # bump: move to end so LRU semantics hold
                self._store.move_to_end(event.event_id)
                self._store[event.event_id] = event
                return
            self._store[event.event_id] = event
            self._by_project.setdefault(event.project_id, []).append(event.event_id)
            while len(self._store) > self._max:
                old_id, old_event = self._store.popitem(last=False)
                pid_list = self._by_project.get(old_event.project_id, [])
                if pid_list and pid_list[0] == old_id:
                    pid_list.pop(0)
                elif old_id in pid_list:
                    pid_list.remove(old_id)
                if not pid_list:
                    self._by_project.pop(old_event.project_id, None)

    async def get_recent(
        self,
        project_id: str,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Return events for `project_id` whose occurred_at >= `since`.

        `since` is compared lexicographically. ISO 8601 sorts correctly when
        the strings are well-formed UTC timestamps, which OpenProject emits.
        """
        async with self._lock:
            ids = list(self._by_project.get(project_id, []))
            out: List[Event] = []
            for eid in reversed(ids):  # newest-first
                event = self._store.get(eid)
                if event is None:
                    continue
                if since is not None and event.occurred_at < since:
                    continue
                out.append(event)
                if len(out) >= limit:
                    break
            return out

    async def size(self) -> int:
        async with self._lock:
            return len(self._store)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
            self._by_project.clear()


# process-wide singleton. consumer + MCP tool both reach for this
_GLOBAL = EventsCache()


def get_cache() -> EventsCache:
    return _GLOBAL
