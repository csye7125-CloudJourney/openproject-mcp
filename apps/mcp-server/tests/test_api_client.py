"""Tests for the OpenProject API client."""

import pytest
import httpx
from unittest.mock import Mock, AsyncMock, patch

from openproject_mcp_server.api_client import OpenProjectClient


@pytest.fixture
def api_client():
    """Create an API client instance for testing."""
    return OpenProjectClient(
        base_url="https://openproject.example.com",
        api_key="test-api-key",
        timeout=30,
        verify_ssl=True
    )


def test_api_client_initialization(api_client):
    """Test API client initialization."""
    assert api_client.base_url == "https://openproject.example.com"
    assert api_client.api_key == "test-api-key"
    assert api_client.timeout == 30
    assert api_client.verify_ssl is True
    assert str(api_client.client.base_url) == "https://openproject.example.com/api/v3/"


def test_encode_api_key(api_client):
    """Test API key encoding for basic auth."""
    encoded = api_client._encode_api_key()
    
    # Should be base64 encoded "apikey:test-api-key"
    import base64
    expected = base64.b64encode(b"apikey:test-api-key").decode()
    assert encoded == expected


@pytest.mark.asyncio
async def test_get_projects_success(api_client):
    """Test successful get_projects call."""
    mock_response_data = {
        "_embedded": {
            "elements": [
                {"id": 1, "name": "Project 1", "status": {"name": "active"}},
                {"id": 2, "name": "Project 2", "status": {"name": "active"}}
            ]
        }
    }
    
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await api_client.get_projects()
        
        assert len(result) == 2
        assert result[0]["name"] == "Project 1"
        assert result[1]["name"] == "Project 2"
        mock_request.assert_called_once_with("GET", "/projects", params={})


@pytest.mark.asyncio
async def test_get_projects_with_filters(api_client):
    """Test get_projects with filters."""
    mock_response_data = {
        "_embedded": {
            "elements": [
                {"id": 1, "name": "Active Project", "status": {"name": "active"}}
            ]
        }
    }
    
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        filters = {"status": "active"}
        result = await api_client.get_projects(filters=filters)
        
        assert len(result) == 1
        assert result[0]["name"] == "Active Project"
        
        # Check that filters were properly formatted
        call_args = mock_request.call_args
        assert 'params' in call_args[1]
        assert 'filters' in call_args[1]['params']


@pytest.mark.asyncio
async def test_get_projects_http_error(api_client):
    """Test get_projects with HTTP error."""
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_request.side_effect = httpx.HTTPError("Connection failed")
        
        with pytest.raises(Exception, match="Failed to get projects"):
            await api_client.get_projects()


@pytest.mark.asyncio
async def test_get_project_details_success(api_client):
    """Test successful get_project_details call."""
    mock_project = {
        "id": 1,
        "name": "Test Project",
        "status": {"name": "active"},
        "description": "A test project"
    }
    
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = mock_project
        mock_request.return_value = mock_response
        
        result = await api_client.get_project_details("1")
        
        assert result["id"] == 1
        assert result["name"] == "Test Project"
        mock_request.assert_called_once_with("GET", "/projects/1")


@pytest.mark.asyncio
async def test_get_project_details_not_found(api_client):
    """Test get_project_details with project not found."""
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError("Not found", request=Mock(), response=mock_response)
        mock_request.side_effect = error
        
        with pytest.raises(ValueError, match="Project with ID 999 not found"):
            await api_client.get_project_details("999")


@pytest.mark.asyncio
async def test_get_work_packages_success(api_client):
    """Test successful get_work_packages call."""
    mock_response_data = {
        "_embedded": {
            "elements": [
                {"id": 1, "subject": "Task 1", "_embedded": {"status": {"name": "New"}}},
                {"id": 2, "subject": "Task 2", "_embedded": {"status": {"name": "In Progress"}}}
            ]
        }
    }
    
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await api_client.get_work_packages()
        
        assert len(result) == 2
        assert result[0]["subject"] == "Task 1"
        assert result[1]["subject"] == "Task 2"
        mock_request.assert_called_once_with("GET", "/work_packages", params={})


@pytest.mark.asyncio
async def test_get_work_packages_with_project_filter(api_client):
    """Test get_work_packages with project filter."""
    mock_response_data = {"_embedded": {"elements": []}}
    
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await api_client.get_work_packages(project_id="123")
        
        assert len(result) == 0
        
        # Check that project filter was properly formatted
        call_args = mock_request.call_args
        assert 'params' in call_args[1]
        assert 'filters' in call_args[1]['params']


@pytest.mark.asyncio
async def test_get_work_package_success(api_client):
    """Test successful get_work_package call."""
    mock_work_package = {
        "id": 123,
        "subject": "Test Work Package",
        "_embedded": {
            "status": {"name": "In Progress"},
            "type": {"name": "Task"}
        }
    }
    
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = mock_work_package
        mock_request.return_value = mock_response
        
        result = await api_client.get_work_package("123")
        
        assert result["id"] == 123
        assert result["subject"] == "Test Work Package"
        mock_request.assert_called_once_with("GET", "/work_packages/123")


@pytest.mark.asyncio
async def test_get_work_package_not_found(api_client):
    """Test get_work_package with work package not found."""
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError("Not found", request=Mock(), response=mock_response)
        mock_request.side_effect = error
        
        with pytest.raises(ValueError, match="Work package with ID 999 not found"):
            await api_client.get_work_package("999")


@pytest.mark.asyncio
async def test_create_work_package_success(api_client):
    """Test successful create_work_package call."""
    work_package_data = {
        "subject": "New Task",
        "_links": {
            "project": {"href": "/api/v3/projects/1"},
            "type": {"href": "/api/v3/types/1"}
        }
    }
    
    mock_created_wp = {
        "id": 456,
        "subject": "New Task",
        "_embedded": {"status": {"name": "New"}}
    }
    
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = mock_created_wp
        mock_request.return_value = mock_response
        
        result = await api_client.create_work_package(work_package_data)
        
        assert result["id"] == 456
        assert result["subject"] == "New Task"
        mock_request.assert_called_once_with("POST", "/work_packages", json=work_package_data)


@pytest.mark.asyncio
async def test_create_work_package_validation_error(api_client):
    """Test create_work_package with validation error."""
    work_package_data = {"subject": ""}
    
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "message": "Subject cannot be blank",
            "_embedded": {
                "errors": [
                    {"message": "Subject cannot be blank"}
                ]
            }
        }
        error = httpx.HTTPStatusError("Validation failed", request=Mock(), response=mock_response)
        mock_request.side_effect = error
        
        with pytest.raises(Exception, match="Validation failed"):
            await api_client.create_work_package(work_package_data)


@pytest.mark.asyncio
async def test_get_users_success(api_client):
    """Test successful get_users call."""
    mock_response_data = {
        "_embedded": {
            "elements": [
                {"id": 1, "name": "John Doe", "email": "john@example.com", "status": "active"},
                {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "status": "active"}
            ]
        }
    }
    
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await api_client.get_users()
        
        assert len(result) == 2
        assert result[0]["name"] == "John Doe"
        assert result[1]["name"] == "Jane Smith"
        mock_request.assert_called_once_with("GET", "/users")


@pytest.mark.asyncio
async def test_retry_logic_rate_limiting(api_client):
    """Test retry logic with rate limiting."""
    with patch.object(api_client.client, 'request') as mock_request:
        # First call: rate limited
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "0.1"}
        rate_limit_error = httpx.HTTPStatusError(
            "Rate limited", 
            request=Mock(), 
            response=rate_limit_response
        )
        
        # Second call: success
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"_embedded": {"elements": []}}
        success_response.raise_for_status.return_value = None
        
        mock_request.side_effect = [rate_limit_error, success_response]
        
        # Should succeed after retry
        result = await api_client.get_projects()
        assert result == []
        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_retry_logic_connection_error(api_client):
    """Test retry logic with connection errors."""
    with patch.object(api_client.client, 'request') as mock_request:
        # All calls fail with connection error
        mock_request.side_effect = httpx.ConnectError("Connection failed")
        
        # Should fail after all retries
        with pytest.raises(Exception, match="Failed to get projects"):
            await api_client.get_projects()
        
        # Should have tried max_retries + 1 times
        assert mock_request.call_count == api_client.max_retries + 1


@pytest.mark.asyncio
async def test_close_client(api_client):
    """Test closing the HTTP client."""
    with patch.object(api_client.client, 'aclose') as mock_close:
        await api_client.close()
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_context_manager(api_client):
    """Test using the client as an async context manager."""
    with patch.object(api_client.client, 'aclose') as mock_close:
        async with api_client as client:
            assert client is api_client
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_create_project_success(api_client):
    """create_project posts and returns created project."""
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = {"id": 7, "name": "new-proj"}
        mock_request.return_value = mock_response
        result = await api_client.create_project({"name": "new-proj", "identifier": "new-proj"})
        assert result["id"] == 7
        mock_request.assert_called_once_with("POST", "/projects", json={"name": "new-proj", "identifier": "new-proj"})


@pytest.mark.asyncio
async def test_delete_project_calls_delete(api_client):
    """delete_project hits DELETE /projects/{id}."""
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_request.return_value = Mock()
        await api_client.delete_project("42")
        mock_request.assert_called_once_with("DELETE", "/projects/42")


@pytest.mark.asyncio
async def test_update_project_patch(api_client):
    """update_project PATCHes the project endpoint."""
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = {"id": 9, "name": "renamed"}
        mock_request.return_value = mock_response
        result = await api_client.update_project("9", {"name": "renamed"})
        assert result["name"] == "renamed"
        mock_request.assert_called_once_with("PATCH", "/projects/9", json={"name": "renamed"})


@pytest.mark.asyncio
async def test_update_work_package_patch(api_client):
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = {"id": 12, "subject": "renamed"}
        mock_request.return_value = mock_response
        result = await api_client.update_work_package("12", {"lockVersion": 3, "subject": "renamed"})
        assert result["subject"] == "renamed"
        mock_request.assert_called_once_with("PATCH", "/work_packages/12", json={"lockVersion": 3, "subject": "renamed"})


@pytest.mark.asyncio
async def test_delete_work_package(api_client):
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_request.return_value = Mock()
        await api_client.delete_work_package("12")
        mock_request.assert_called_once_with("DELETE", "/work_packages/12")


@pytest.mark.asyncio
async def test_search_work_packages(api_client):
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = {"_embedded": {"elements": [{"id": 9, "subject": "found"}]}}
        mock_request.return_value = mock_response
        result = await api_client.search_work_packages("auth")
        assert len(result) == 1
        assert result[0]["subject"] == "found"


@pytest.mark.asyncio
async def test_list_statuses(api_client):
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = {"_embedded": {"elements": [{"id": 1, "name": "open"}]}}
        mock_request.return_value = mock_response
        result = await api_client.list_statuses()
        assert result[0]["name"] == "open"


@pytest.mark.asyncio
async def test_list_time_entries(api_client):
    with patch.object(api_client, '_make_request_with_retry') as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = {"_embedded": {"elements": [{"id": 1, "hours": "PT1H"}]}}
        mock_request.return_value = mock_response
        result = await api_client.list_time_entries(work_package_id="5")
        assert len(result) == 1
        assert result[0]["id"] == 1
        # ensure filters were passed for the work package
        call = mock_request.call_args
        assert "filters" in call[1]["params"]