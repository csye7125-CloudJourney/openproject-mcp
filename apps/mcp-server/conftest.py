"""pytest config + shared fixtures."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from openproject_mcp_server.config import Config, OpenProjectConfig, LoggingConfig
from openproject_mcp_server.api_client import OpenProjectClient

# register the asyncio marker so warnings stop
pytestmark = pytest.mark.asyncio


@pytest.fixture
def config() -> Config:
    """Test config fixture."""
    return Config(
        openproject=OpenProjectConfig(
            base_url="https://test.openproject.com",
            api_key="test_api_key",
            timeout=30,
            verify_ssl=True
        ),
        logging=LoggingConfig(
            level="INFO",
            format="json"
        )
    )


@pytest.fixture
def mock_api_client() -> Mock:
    """Mock API client with every async method stubbed."""
    client = Mock(spec=OpenProjectClient)

    # async methods
    client.get_projects = AsyncMock(return_value=[])
    client.get_project_details = AsyncMock(return_value={})
    client.get_work_packages = AsyncMock(return_value=[])
    client.get_work_package = AsyncMock(return_value={})
    client.create_work_package = AsyncMock(return_value={})
    client.get_users = AsyncMock(return_value=[])
    client.create_project = AsyncMock(return_value={"id": 1, "name": "demo"})
    client.update_project = AsyncMock(return_value={"id": 1, "name": "demo-renamed"})
    client.delete_project = AsyncMock(return_value=None)
    client.update_work_package = AsyncMock(return_value={"id": 5, "subject": "renamed"})
    client.delete_work_package = AsyncMock(return_value=None)
    client.list_time_entries = AsyncMock(return_value=[])
    client.create_time_entry = AsyncMock(return_value={"id": 11, "hours": "PT1H"})
    client.list_statuses = AsyncMock(return_value=[])
    client.list_types = AsyncMock(return_value=[])
    client.list_priorities = AsyncMock(return_value=[])
    client.get_user = AsyncMock(return_value={"id": 1, "name": "test-user"})
    client.list_relations = AsyncMock(return_value=[])
    client.create_relation = AsyncMock(return_value={"id": 3, "type": "relates"})
    client.list_watchers = AsyncMock(return_value=[])
    client.add_watcher = AsyncMock(return_value={"id": 4})
    client.list_memberships = AsyncMock(return_value=[])
    client.create_membership = AsyncMock(return_value={"id": 7})
    client.list_attachments = AsyncMock(return_value=[])
    client.list_categories = AsyncMock(return_value=[])
    client.list_versions = AsyncMock(return_value=[])
    client.create_version = AsyncMock(return_value={"id": 2, "name": "v1"})
    client.list_activities = AsyncMock(return_value=[])
    client.list_queries = AsyncMock(return_value=[])
    client.search_work_packages = AsyncMock(return_value=[])
    client.get_project_hierarchy = AsyncMock(return_value=[])
    client.close = AsyncMock()

    return client