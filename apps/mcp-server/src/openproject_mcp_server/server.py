"""MCP server for OpenProject.

Tool definitions live under `openproject_mcp_server.tools.*`. This module
holds the registration surface (TOOLS list + dispatch) and the stdio entry
point.
"""

import asyncio
import logging
import sys
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from openproject_mcp_server.api_client import OpenProjectClient
from openproject_mcp_server.config import Config
from openproject_mcp_server.metrics import tool_calls_total, tool_latency_seconds
from openproject_mcp_server.tools import (
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
from openproject_mcp_server.tools._validate import validate_id as _validate_id  # re-export
from openproject_mcp_server.tools._validate import validate_input as _validate_input  # re-export

# Global API client (initialized in main)
api_client: Optional[OpenProjectClient] = None

# Create the MCP server instance
server = Server("openproject-mcp-server")


def _collect_tools() -> List[Tool]:
    out: List[Tool] = []
    for mod in (projects, work_packages, users, time_entries, lookups, relations, memberships, misc, events):
        out.extend(mod.TOOLS)
    return out


def _collect_handlers() -> Dict[str, Callable[..., Awaitable[List[TextContent]]]]:
    out: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = {}
    for mod in (projects, work_packages, users, time_entries, lookups, relations, memberships, misc, events):
        out.update(mod.HANDLERS)
    return out


TOOLS: List[Tool] = _collect_tools()
HANDLERS: Dict[str, Callable[..., Awaitable[List[TextContent]]]] = _collect_handlers()


# Backwards-compat single-arg shims so older tests still resolve
# `server.list_projects_impl({...})` etc. New code goes via HANDLERS.
async def list_projects_impl(arguments: Dict[str, Any]) -> List[TextContent]:
    return await projects.list_projects_impl(api_client, arguments)


async def get_project_details_impl(arguments: Dict[str, Any]) -> List[TextContent]:
    return await projects.get_project_details_impl(api_client, arguments)


async def list_work_packages_impl(arguments: Dict[str, Any]) -> List[TextContent]:
    return await work_packages.list_work_packages_impl(api_client, arguments)


async def get_work_package_impl(arguments: Dict[str, Any]) -> List[TextContent]:
    return await work_packages.get_work_package_impl(api_client, arguments)


async def create_work_package_impl(arguments: Dict[str, Any]) -> List[TextContent]:
    return await work_packages.create_work_package_impl(api_client, arguments)


async def list_users_impl(arguments: Dict[str, Any]) -> List[TextContent]:
    return await users.list_users_impl(api_client, arguments)


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """Handle list tools request."""
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool execution request."""
    request_id = str(uuid.uuid4())
    sanitized_args = _sanitize_arguments(arguments)
    logging.info(
        f"Tool execution started: {name}",
        extra={"request_id": request_id, "tool_name": name, "arguments": sanitized_args},
    )

    handler = HANDLERS.get(name)
    if handler is None:
        logging.warning(f"Unknown tool requested: {name}", extra={"request_id": request_id})
        tool_calls_total.labels(tool_name=name, outcome="unknown").inc()
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    start = time.perf_counter()
    outcome = "success"
    try:
        result = await handler(api_client, arguments)
        logging.info(
            f"Tool execution completed: {name}",
            extra={"request_id": request_id, "tool_name": name, "success": True},
        )
        return result
    except Exception as e:  # noqa: BLE001
        outcome = "error"
        error_category = _categorize_error(e)
        logging.error(
            f"Tool execution failed: {name}",
            extra={
                "request_id": request_id,
                "tool_name": name,
                "error_category": error_category,
                "error_message": str(e),
                "success": False,
            },
            exc_info=True,
        )
        user_message = _get_user_friendly_error_message(e, error_category)
        return [TextContent(type="text", text=f"Error: {user_message}")]
    finally:
        tool_calls_total.labels(tool_name=name, outcome=outcome).inc()
        tool_latency_seconds.labels(tool_name=name, outcome=outcome).observe(
            time.perf_counter() - start
        )


def _sanitize_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    sensitive_keys = {"api_key", "password", "token", "secret"}
    for key, value in arguments.items():
        if key.lower() in sensitive_keys:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_arguments(value)
        else:
            sanitized[key] = value
    return sanitized


def _categorize_error(error: Exception) -> str:
    if isinstance(error, ValueError):
        return "validation_error"
    if isinstance(error, ConnectionError):
        return "connection_error"
    if isinstance(error, TimeoutError):
        return "timeout_error"
    msg = str(error).lower()
    if "rate limit" in msg:
        return "rate_limit_error"
    if "authentication" in msg or "unauthorized" in msg:
        return "auth_error"
    if "not found" in msg:
        return "not_found_error"
    return "internal_error"


def _get_user_friendly_error_message(error: Exception, category: str) -> str:
    if category == "validation_error":
        return str(error)
    if category == "connection_error":
        return "Unable to connect to OpenProject. Please check your configuration and network connection."
    if category == "timeout_error":
        return "Request timed out. Please try again later."
    if category == "rate_limit_error":
        return "Rate limit exceeded. Please wait a moment before trying again."
    if category == "auth_error":
        return "Authentication failed. Please check your OpenProject API key and permissions."
    if category == "not_found_error":
        return str(error)
    return "An internal error occurred. Please try again or contact support if the problem persists."


async def main() -> None:
    """Entry point for the MCP server."""
    global api_client

    try:
        config = Config.from_env()

        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if config.logging.format == "json":
            import json

            class JsonFormatter(logging.Formatter):
                def format(self, record: logging.LogRecord) -> str:
                    log_entry: Dict[str, Any] = {
                        "timestamp": self.formatTime(record),
                        "level": record.levelname,
                        "logger": record.name,
                        "message": record.getMessage(),
                    }
                    if hasattr(record, "request_id"):
                        log_entry["request_id"] = record.request_id
                    if hasattr(record, "tool_name"):
                        log_entry["tool_name"] = record.tool_name
                    if hasattr(record, "error_category"):
                        log_entry["error_category"] = record.error_category
                    return json.dumps(log_entry)

            handler = logging.StreamHandler()
            handler.setFormatter(JsonFormatter())
            logging.basicConfig(level=getattr(logging, config.logging.level), handlers=[handler])
        else:
            logging.basicConfig(level=getattr(logging, config.logging.level), format=log_format)

        logging.info(
            "Starting OpenProject MCP Server",
            extra={
                "version": "0.1.0",
                "openproject_url": config.openproject.base_url,
                "log_level": config.logging.level,
            },
        )

        api_client = OpenProjectClient(
            base_url=config.openproject.base_url,
            api_key=config.openproject.api_key,
            timeout=config.openproject.timeout,
            verify_ssl=config.openproject.verify_ssl,
        )

        try:
            await api_client.get_projects()
            logging.info("Successfully connected to OpenProject API")
        except Exception as e:  # noqa: BLE001
            logging.warning(f"Could not connect to OpenProject API: {e}")
            logging.warning("Server will start anyway for testing.")

        logging.info("MCP Server started and ready to accept connections")

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, shutting down...")
    except Exception as e:  # noqa: BLE001
        logging.error(f"Fatal error during startup: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if api_client:
            try:
                await api_client.close()
                logging.info("API client closed")
            except Exception as e:  # noqa: BLE001
                logging.error(f"Error closing API client: {e}")
        logging.info("OpenProject MCP Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
