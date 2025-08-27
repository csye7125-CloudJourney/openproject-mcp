"""Prometheus metrics for the MCP server.

Started small with a tool-call counter. More instrumentation gets added as
new bits of the server land.
"""

from prometheus_client import Counter, Histogram


tool_calls_total = Counter(
    "openproject_mcp_tool_calls_total",
    "Total MCP tool invocations",
    labelnames=("tool_name", "outcome"),
)

# Buckets aimed at the p95 < 200ms SLO. Tail buckets catch the long tail
# without blowing up cardinality.
tool_latency_seconds = Histogram(
    "openproject_mcp_tool_latency_seconds",
    "Wall-clock duration of MCP tool invocations, in seconds",
    labelnames=("tool_name", "outcome"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# lower-level latency for outbound OpenProject calls so we can separate
# tool overhead from a slow upstream
openproject_api_latency_seconds = Histogram(
    "openproject_api_latency_seconds",
    "Latency of outbound calls to the OpenProject REST API",
    labelnames=("method", "outcome"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.5, 5.0),
)
