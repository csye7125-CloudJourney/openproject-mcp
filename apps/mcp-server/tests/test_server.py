"""Tests for the MCP server implementation."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from mcp.types import TextContent
from openproject_mcp_server import server
from openproject_mcp_server.config import Config, OpenProjectConfig, LoggingConfig


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return Config(
        openproject=OpenProjectConfig(
            base_url="https://openproject.example.com",
            api_key="test-api-key",
            timeout=30,
            verify_ssl=True
        ),
        logging=LoggingConfig(level="INFO", format="json")
    )


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = Mock()
    client.get_projects = AsyncMock(return_value=[])
    client.get_project_details = AsyncMock(return_value={})
    client.get_work_packages = AsyncMock(return_value=[])
    client.get_work_package = AsyncMock(return_value={})
    client.create_work_package = AsyncMock(return_value={})
    client.get_users = AsyncMock(return_value=[])
    return client


def test_tools_registration():
    """Test that expected tools are registered."""
    expected_tools = {
        "list_projects",
        "get_project_details",
        "list_work_packages",
        "get_work_package",
        "create_work_package",
        "list_users",
        "create_project",
        "delete_project",
    }

    registered = {t.name for t in server.TOOLS}
    assert expected_tools.issubset(registered)
    for tool in server.TOOLS:
        assert tool.description
        assert tool.inputSchema
        assert tool.inputSchema["type"] == "object"


def test_list_projects_tool_schema():
    """Test list_projects tool schema."""
    list_projects_tool = next(tool for tool in server.TOOLS if tool.name == "list_projects")
    
    assert list_projects_tool.name == "list_projects"
    assert "projects" in list_projects_tool.description.lower()
    assert list_projects_tool.inputSchema["type"] == "object"
    assert "filters" in list_projects_tool.inputSchema["properties"]


def test_create_work_package_tool_schema():
    """Test create_work_package tool schema."""
    create_wp_tool = next(tool for tool in server.TOOLS if tool.name == "create_work_package")
    
    assert create_wp_tool.name == "create_work_package"
    required_fields = create_wp_tool.inputSchema["required"]
    assert "subject" in required_fields
    assert "project_id" in required_fields
    assert "type_id" in required_fields


@pytest.mark.asyncio
async def test_list_projects_impl_success(mock_api_client):
    """Test successful list_projects implementation."""
    mock_projects = [
        {
            "id": 1,
            "name": "Test Project 1",
            "status": {"name": "active"},
            "description": "A test project",
            "createdAt": "2023-01-01T00:00:00Z"
        },
        {
            "id": 2,
            "name": "Test Project 2",
            "status": {"name": "active"},
            "createdAt": "2023-01-02T00:00:00Z"
        }
    ]
    
    mock_api_client.get_projects.return_value = mock_projects
    
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        result = await server.list_projects_impl({})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Found 2 projects" in result[0].text
        assert "Test Project 1" in result[0].text
        assert "Test Project 2" in result[0].text
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_list_projects_impl_with_filters(mock_api_client):
    """Test list_projects implementation with filters."""
    mock_projects = [
        {
            "id": 1,
            "name": "Active Project",
            "status": {"name": "active"}
        }
    ]
    
    mock_api_client.get_projects.return_value = mock_projects
    
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        filters = {"status": "active"}
        result = await server.list_projects_impl({"filters": filters})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Found 1 projects" in result[0].text
        assert "Active Project" in result[0].text
        
        # Verify the API client was called with filters
        mock_api_client.get_projects.assert_called_once_with(filters=filters)
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_list_projects_impl_no_results(mock_api_client):
    """Test list_projects implementation with no results."""
    mock_api_client.get_projects.return_value = []
    
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        result = await server.list_projects_impl({})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "No projects found" in result[0].text
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_list_projects_impl_api_error(mock_api_client):
    """Test list_projects implementation with API error."""
    mock_api_client.get_projects.side_effect = Exception("API Error")
    
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        result = await server.list_projects_impl({})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Error retrieving projects" in result[0].text
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_get_project_details_impl_success(mock_api_client):
    """Test successful get_project_details implementation."""
    mock_project = {
        "id": 1,
        "name": "Test Project",
        "status": {"name": "active"},
        "description": "A detailed test project",
        "createdAt": "2023-01-01T00:00:00Z",
        "updatedAt": "2023-01-02T00:00:00Z"
    }
    
    mock_api_client.get_project_details.return_value = mock_project
    
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        result = await server.get_project_details_impl({"project_id": "1"})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        response_text = result[0].text
        
        assert "# Project Details: Test Project" in response_text
        assert "**ID:** 1" in response_text
        assert "**Status:** active" in response_text
        assert "**Description:** A detailed test project" in response_text
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_get_project_details_impl_missing_id(mock_api_client):
    """Test get_project_details implementation without project_id."""
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        result = await server.get_project_details_impl({})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "project_id is required" in result[0].text
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_create_work_package_impl_success(mock_api_client):
    """Test successful create_work_package implementation."""
    mock_created_wp = {
        "id": 456,
        "subject": "New Test Task"
    }
    
    mock_api_client.create_work_package.return_value = mock_created_wp
    
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        arguments = {
            "subject": "New Test Task",
            "project_id": "1",
            "type_id": "2",
            "description": "Task description",
            "assignee_id": "3"
        }
        result = await server.create_work_package_impl(arguments)
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        response_text = result[0].text
        
        assert "Work package created successfully" in response_text
        assert "New Test Task" in response_text
        assert "ID: 456" in response_text
        
        # Verify API client was called with correct data
        expected_data = {
            "subject": "New Test Task",
            "_links": {
                "project": {"href": "/api/v3/projects/1"},
                "type": {"href": "/api/v3/types/2"},
                "assignee": {"href": "/api/v3/users/3"}
            },
            "description": {"raw": "Task description"}
        }
        mock_api_client.create_work_package.assert_called_once_with(expected_data)
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_create_work_package_impl_missing_required_fields(mock_api_client):
    """Test create_work_package implementation with missing required fields."""
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        # Missing subject
        result = await server.create_work_package_impl({
            "project_id": "1",
            "type_id": "2"
        })
        assert "cannot be None" in result[0].text
        
        # Missing project_id
        result = await server.create_work_package_impl({
            "subject": "Test",
            "type_id": "2"
        })
        assert ("cannot be None" in result[0].text or "is required" in result[0].text)
        
        # Missing type_id
        result = await server.create_work_package_impl({
            "subject": "Test",
            "project_id": "1"
        })
        assert ("cannot be None" in result[0].text or "is required" in result[0].text)
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_list_users_impl_success(mock_api_client):
    """Test successful list_users implementation."""
    mock_users = [
        {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "status": "active"
        },
        {
            "id": 2,
            "name": "Jane Smith",
            "email": "jane@example.com",
            "status": "active"
        }
    ]
    
    mock_api_client.get_users.return_value = mock_users
    
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        result = await server.list_users_impl({})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        response_text = result[0].text
        
        assert "Found 2 users" in response_text
        assert "John Doe" in response_text
        assert "Jane Smith" in response_text
        assert "john@example.com" in response_text
        assert "jane@example.com" in response_text
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_handle_call_tool_unknown_tool():
    """Test handling unknown tool calls."""
    result = await server.handle_call_tool("unknown_tool", {})
    
    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert "Unknown tool: unknown_tool" in result[0].text


@pytest.mark.asyncio
async def test_handle_call_tool_success(mock_api_client):
    """Test successful tool call handling."""
    mock_api_client.get_projects.return_value = []
    
    # Temporarily set the global api_client
    original_client = server.api_client
    server.api_client = mock_api_client
    
    try:
        result = await server.handle_call_tool("list_projects", {})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        # Should return a response (either success or no results message)
        assert len(result[0].text) > 0
    finally:
        server.api_client = original_client


@pytest.mark.asyncio
async def test_handle_list_tools():
    """Test list tools handler."""
    tools = await server.handle_list_tools()
    
    assert len(tools) == len(server.TOOLS)
    assert all(tool.name for tool in tools)
    assert all(tool.description for tool in tools)
    assert all(tool.inputSchema for tool in tools)