"""Integration tests for the OpenProject MCP server."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import httpx

from openproject_mcp_server import server as server_module
from openproject_mcp_server.server import (
    handle_call_tool, 
    handle_list_tools,
)
from openproject_mcp_server.config import Config
from openproject_mcp_server.api_client import OpenProjectClient


@pytest.mark.asyncio
async def test_full_mcp_workflow():
    """Test complete MCP workflow from tool listing to execution."""
    # Mock API client
    mock_client = Mock(spec=OpenProjectClient)
    mock_client.get_projects = AsyncMock(return_value=[
        {"id": 1, "name": "Test Project", "status": {"name": "active"}}
    ])
    
    # Temporarily set the global api_client
    original_client = server_module.api_client
    server_module.api_client = mock_client
    
    try:
        # Test list tools
        tools = await handle_list_tools()
        assert len(tools) > 0
        assert any(tool.name == "list_projects" for tool in tools)
        
        # Test tool execution
        result = await handle_call_tool("list_projects", {})
        assert len(result) == 1
        assert "Found 1 projects" in result[0].text
        assert "Test Project" in result[0].text
        
    finally:
        server_module.api_client = original_client


@pytest.mark.asyncio
async def test_error_handling_integration():
    """Test error handling across the system."""
    # Mock API client that raises errors
    mock_client = Mock(spec=OpenProjectClient)
    mock_client.get_projects = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
    
    # Temporarily set the global api_client
    original_client = server_module.api_client
    server_module.api_client = mock_client
    
    try:
        # Test that errors are handled gracefully
        result = await handle_call_tool("list_projects", {})
        assert len(result) == 1
        assert "Error" in result[0].text
        assert "connect" in result[0].text.lower()
        
    finally:
        server_module.api_client = original_client


@pytest.mark.asyncio
async def test_input_validation_integration():
    """Test input validation across different tools."""
    # Mock API client
    mock_client = Mock(spec=OpenProjectClient)
    
    # Temporarily set the global api_client
    original_client = server_module.api_client
    server_module.api_client = mock_client
    
    try:
        # Test invalid project ID
        result = await handle_call_tool("get_project_details", {"project_id": ""})
        assert len(result) == 1
        assert "Error" in result[0].text
        assert ("cannot be empty" in result[0].text or "invalid characters" in result[0].text)
        
        # Test invalid work package creation
        result = await handle_call_tool("create_work_package", {
            "subject": "",  # Empty subject
            "project_id": "1",
            "type_id": "1"
        })
        assert len(result) == 1
        assert "Error" in result[0].text
        assert "cannot be empty" in result[0].text
        
        # Test injection attempt
        result = await handle_call_tool("create_work_package", {
            "subject": "<script>alert('xss')</script>",
            "project_id": "1",
            "type_id": "1"
        })
        # Should not fail but should sanitize the input
        assert len(result) == 1
        # The error might be from API call, but input should be sanitized
        
    finally:
        server_module.api_client = original_client


@pytest.mark.asyncio
async def test_configuration_integration():
    """Test configuration loading and validation integration."""
    with patch.dict('os.environ', {
        'OPENPROJECT_BASE_URL': 'https://test.openproject.com',
        'OPENPROJECT_API_KEY': 'test-key',
        'LOG_LEVEL': 'DEBUG'
    }):
        config = Config.from_env()
        
        assert config.openproject.base_url == 'https://test.openproject.com'
        assert config.openproject.api_key == 'test-key'
        assert config.logging.level == 'DEBUG'
        
        # Test that API client can be created with this config
        client = OpenProjectClient(
            base_url=config.openproject.base_url,
            api_key=config.openproject.api_key,
            timeout=config.openproject.timeout,
            verify_ssl=config.openproject.verify_ssl
        )
        
        assert client.base_url == 'https://test.openproject.com'
        await client.close()


@pytest.mark.asyncio
async def test_concurrent_tool_execution():
    """Test concurrent execution of multiple tools."""
    # Mock API client
    mock_client = Mock(spec=OpenProjectClient)
    mock_client.get_projects = AsyncMock(return_value=[])
    mock_client.get_users = AsyncMock(return_value=[])
    
    # Temporarily set the global api_client
    original_client = server_module.api_client
    server_module.api_client = mock_client
    
    try:
        # Execute multiple tools concurrently
        tasks = [
            handle_call_tool("list_projects", {}),
            handle_call_tool("list_users", {}),
            handle_call_tool("list_projects", {"filters": {"status": "active"}}),
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 3
        for result in results:
            assert len(result) == 1
            assert "Error:" not in result[0].text or "No" in result[0].text  # "No projects found" is OK
            
    finally:
        server_module.api_client = original_client


@pytest.mark.asyncio
async def test_tool_schema_validation():
    """Test that tool schemas are properly defined and valid."""
    tools = await handle_list_tools()
    
    for tool in tools:
        # Each tool should have required fields
        assert tool.name
        assert tool.description
        assert tool.inputSchema
        
        # Schema should be valid JSON Schema
        schema = tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        
        # If required fields exist, they should be in properties
        if "required" in schema:
            for required_field in schema["required"]:
                assert required_field in schema["properties"]


@pytest.mark.asyncio 
async def test_logging_integration():
    """Test that logging works correctly throughout the system."""
    import logging
    from io import StringIO
    
    # Capture log output
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        # Mock API client
        mock_client = Mock(spec=OpenProjectClient)
        mock_client.get_projects = AsyncMock(return_value=[])
        
        # Temporarily set the global api_client
        original_client = server_module.api_client
        server_module.api_client = mock_client
        
        try:
            # Execute a tool to generate logs
            await handle_call_tool("list_projects", {})
            
            # Check that logs were generated
            log_output = log_capture.getvalue()
            assert "Tool execution started" in log_output
            assert "Tool execution completed" in log_output
            
        finally:
            server_module.api_client = original_client
            
    finally:
        logger.removeHandler(handler)