#!/usr/bin/env python3
"""Bench MCP tool latency.

Stubs the OpenProject upstream with httpx.MockTransport so we're measuring
just in-process handler + httpx round-trip overhead. Fires N calls per
tool, prints p50/p95/p99 per tool, writes bench/results.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx

# default tools to bench. covers the GET-shaped ones that don't need extra
# setup. keep this list short, the goal is a gate, not coverage.
DEFAULT_TOOLS = [
    "list_projects",
    "list_users",
    "list_statuses",
    "list_types",
    "list_priorities",
    "list_queries",
]


def _make_mock_handler() -> httpx.MockTransport:
    """Transport that fakes the bits of the OpenProject API we hit."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        # most list_* endpoints return _embedded.elements with one fake item
        if path.endswith("/projects") or path.endswith("/users") or path.endswith("/statuses") \
                or path.endswith("/types") or path.endswith("/priorities") or path.endswith("/queries"):
            return httpx.Response(
                200,
                json={"_embedded": {"elements": [{"id": 1, "name": "stub"}]}},
            )
        # project details / work package details fall through here
        return httpx.Response(200, json={"id": 1, "name": "stub"})

    return httpx.MockTransport(handler)


async def _bench_tool(name: str, iterations: int) -> List[float]:
    """Time `iterations` handler calls for one tool. Returns seconds per call."""
    from openproject_mcp_server import api_client as api_client_mod
    from openproject_mcp_server import server

    # build a real client but inject the mock transport
    fake_client = api_client_mod.OpenProjectClient(
        base_url="http://bench.local",
        api_key="bench-key",
        timeout=5,
        verify_ssl=False,
    )
    # swap the underlying httpx client for one wired to our MockTransport
    await fake_client.client.aclose()
    fake_client.client = httpx.AsyncClient(
        base_url="http://bench.local/api/v3",
        headers={"Accept": "application/json"},
        transport=_make_mock_handler(),
    )

    original = server.api_client
    server.api_client = fake_client
    samples: List[float] = []
    try:
        # warm up so first-call JIT / cache effects don't skew the numbers
        await server.handle_call_tool(name, {})
        for _ in range(iterations):
            t0 = time.perf_counter()
            await server.handle_call_tool(name, {})
            samples.append(time.perf_counter() - t0)
    finally:
        server.api_client = original
        await fake_client.close()
    return samples


def _percentile(samples: List[float], pct: float) -> float:
    if not samples:
        return 0.0
    s = sorted(samples)
    k = int(round((pct / 100.0) * (len(s) - 1)))
    return s[k]


async def _run(tools: List[str], iterations: int) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for tool in tools:
        samples = await _bench_tool(tool, iterations)
        results[tool] = {
            "n": len(samples),
            "mean_ms": statistics.mean(samples) * 1000,
            "p50_ms": _percentile(samples, 50) * 1000,
            "p95_ms": _percentile(samples, 95) * 1000,
            "p99_ms": _percentile(samples, 99) * 1000,
            "max_ms": max(samples) * 1000,
        }
    return results


def main() -> int:
    p = argparse.ArgumentParser(description="Bench openproject-mcp tool latency.")
    p.add_argument("--iterations", "-n", type=int, default=100)
    p.add_argument("--tool", action="append", help="Run only these tools (repeatable).")
    p.add_argument("--output", default=str(Path(__file__).resolve().parent.parent / "bench" / "results.json"))
    p.add_argument(
        "--p95-budget-ms",
        type=float,
        default=200.0,
        help="Fail the run if any tool's p95 exceeds this threshold.",
    )
    args = p.parse_args()

    tools = args.tool or DEFAULT_TOOLS
    results = asyncio.run(_run(tools, args.iterations))

    print(f"{'tool':<28} {'n':>5} {'mean':>8} {'p50':>8} {'p95':>8} {'p99':>8} {'max':>8}")
    print("-" * 80)
    for name, stats in results.items():
        print(
            f"{name:<28} {stats['n']:>5} "
            f"{stats['mean_ms']:>7.2f}ms {stats['p50_ms']:>7.2f}ms "
            f"{stats['p95_ms']:>7.2f}ms {stats['p99_ms']:>7.2f}ms "
            f"{stats['max_ms']:>7.2f}ms"
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"\nWrote results to {out}")

    # CI gate: any tool over budget -> nonzero exit
    breaches = [(t, s["p95_ms"]) for t, s in results.items() if s["p95_ms"] > args.p95_budget_ms]
    if breaches:
        print(
            f"\nFAIL: {len(breaches)} tool(s) over p95 budget of {args.p95_budget_ms}ms:",
            flush=True,
        )
        for name, p95 in breaches:
            print(f"  - {name}: {p95:.2f}ms", flush=True)
        return 1

    print(f"\nOK: all tools under p95 budget of {args.p95_budget_ms}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
