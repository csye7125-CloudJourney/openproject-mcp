"""OpenProject REST API client."""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
import httpx

from openproject_mcp_server.metrics import openproject_api_latency_seconds


class OpenProjectClient:
    """Async HTTP client for the OpenProject API."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # retry knobs
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 60.0

        # http client
        self.client = httpx.AsyncClient(
            base_url=f"{self.base_url}/api/v3",
            headers={
                "Authorization": f"Basic {self._encode_api_key()}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=timeout,
            verify=verify_ssl
        )
        
        self.logger = logging.getLogger(__name__)
    
    def _encode_api_key(self) -> str:
        """Encode the API key for basic auth."""
        import base64
        # OpenProject uses "apikey" as username, API key as password
        credentials = f"apikey:{self.api_key}"
        return base64.b64encode(credentials.encode()).decode()

    async def _make_request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """HTTP request with retry + exponential backoff."""
        last_exception = None
        start = time.perf_counter()

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(method, url, **kwargs)

                # rate limited?
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        # Retry-After header wins, otherwise exponential backoff
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            delay = min(float(retry_after), self.max_delay)
                        else:
                            delay = min(self.base_delay * (2 ** attempt), self.max_delay)

                        self.logger.warning(f"rate limited, retrying in {delay}s (attempt {attempt + 1})")
                        await asyncio.sleep(delay)
                        continue

                # other HTTP errors: raise immediately, don't retry
                response.raise_for_status()
                openproject_api_latency_seconds.labels(
                    method=method.upper(), outcome="success"
                ).observe(time.perf_counter() - start)
                return response
                
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    self.logger.warning(f"request timeout, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue

            except httpx.ConnectError as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    self.logger.warning(f"connection error, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue

            except httpx.HTTPStatusError as e:
                # don't retry client errors (4xx) except rate limiting
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    openproject_api_latency_seconds.labels(
                        method=method.upper(), outcome="error"
                    ).observe(time.perf_counter() - start)
                    raise

                last_exception = e
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    self.logger.warning(f"http {e.response.status_code}, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue

        # all retries failed
        openproject_api_latency_seconds.labels(
            method=method.upper(), outcome="error"
        ).observe(time.perf_counter() - start)
        if last_exception:
            raise last_exception
        else:
            raise Exception("All retry attempts failed")
    
    async def get_projects(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List accessible projects, optionally filtered."""
        try:
            params = {}
            if filters:
                if filters.get('status'):
                    params['filters'] = f'[{{"status":{{"operator":"=","values":["{filters["status"]}"]}}}}]'
                if filters.get('name'):
                    params['filters'] = f'[{{"name":{{"operator":"~","values":["{filters["name"]}"]}}}}]'
            
            response = await self._make_request_with_retry("GET", "/projects", params=params)
            data = response.json()
            return data.get('_embedded', {}).get('elements', [])
            
        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error getting projects: {e}")
            raise Exception(f"Failed to get projects: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error getting projects: {e}")
            raise
    
    async def get_project_details(self, project_id: str) -> Dict[str, Any]:
        """Detail for a single project."""
        try:
            response = await self._make_request_with_retry("GET", f"/projects/{project_id}")
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Project with ID {project_id} not found")
            self.logger.error(f"HTTP error getting project details: {e}")
            raise Exception(f"Failed to get project details: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error getting project details: {e}")
            raise
    
    async def get_work_packages(
        self,
        project_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """List work packages, optionally filtered by project + assignee/status/type."""
        try:
            params = {}
            filter_conditions = []
            
            if project_id:
                filter_conditions.append(f'{{"project":{{"operator":"=","values":["{project_id}"]}}}}')
            
            if filters:
                if filters.get('assignee'):
                    filter_conditions.append(f'{{"assignee":{{"operator":"=","values":["{filters["assignee"]}"]}}}}')
                if filters.get('status'):
                    filter_conditions.append(f'{{"status":{{"operator":"=","values":["{filters["status"]}"]}}}}')
                if filters.get('type'):
                    filter_conditions.append(f'{{"type":{{"operator":"=","values":["{filters["type"]}"]}}}}')
            
            if filter_conditions:
                params['filters'] = f'[{",".join(filter_conditions)}]'
            
            response = await self._make_request_with_retry("GET", "/work_packages", params=params)
            
            data = response.json()
            return data.get('_embedded', {}).get('elements', [])
            
        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error getting work packages: {e}")
            raise Exception(f"Failed to get work packages: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error getting work packages: {e}")
            raise
    
    async def get_work_package(self, work_package_id: str) -> Dict[str, Any]:
        """Detail for a single work package."""
        try:
            response = await self._make_request_with_retry("GET", f"/work_packages/{work_package_id}")
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Work package with ID {work_package_id} not found")
            self.logger.error(f"HTTP error getting work package: {e}")
            raise Exception(f"Failed to get work package: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error getting work package: {e}")
            raise
    
    async def create_work_package(self, work_package_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a work package."""
        try:
            response = await self._make_request_with_retry("POST", "/work_packages", json=work_package_data)
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"http error creating work package: {e}")
            if e.response.status_code == 422:
                # validation error
                error_data = e.response.json()
                error_msg = "Validation failed: "
                if 'message' in error_data:
                    error_msg += error_data['message']
                elif '_embedded' in error_data and 'errors' in error_data['_embedded']:
                    errors = error_data['_embedded']['errors']
                    error_messages = [err.get('message', 'Unknown error') for err in errors]
                    error_msg += "; ".join(error_messages)
                raise Exception(error_msg)
            raise Exception(f"Failed to create work package: {str(e)}")
        except Exception as e:
            self.logger.error(f"error creating work package: {e}")
            raise
    
    async def list_memberships(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if project_id:
            params['filters'] = f'[{{"project":{{"operator":"=","values":["{project_id}"]}}}}]'
        response = await self._make_request_with_retry("GET", "/memberships", params=params)
        return response.json().get('_embedded', {}).get('elements', [])

    async def create_membership(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = await self._make_request_with_retry("POST", "/memberships", json=payload)
        return response.json()

    async def list_attachments(self, work_package_id: str) -> List[Dict[str, Any]]:
        response = await self._make_request_with_retry(
            "GET", f"/work_packages/{work_package_id}/attachments"
        )
        return response.json().get('_embedded', {}).get('elements', [])

    async def list_categories(self, project_id: str) -> List[Dict[str, Any]]:
        response = await self._make_request_with_retry("GET", f"/projects/{project_id}/categories")
        return response.json().get('_embedded', {}).get('elements', [])

    async def list_versions(self, project_id: str) -> List[Dict[str, Any]]:
        response = await self._make_request_with_retry("GET", f"/projects/{project_id}/versions")
        return response.json().get('_embedded', {}).get('elements', [])

    async def create_version(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self._make_request_with_retry(
                "POST", f"/projects/{project_id}/versions", json=payload
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                raise Exception(e.response.json().get('message', 'Validation failed creating version'))
            raise

    async def list_activities(self, work_package_id: str) -> List[Dict[str, Any]]:
        response = await self._make_request_with_retry(
            "GET", f"/work_packages/{work_package_id}/activities"
        )
        return response.json().get('_embedded', {}).get('elements', [])

    async def list_queries(self) -> List[Dict[str, Any]]:
        response = await self._make_request_with_retry("GET", "/queries")
        return response.json().get('_embedded', {}).get('elements', [])

    async def search_work_packages(self, query: str) -> List[Dict[str, Any]]:
        """Free-text search across work packages via the typeahead filter."""
        params = {
            'filters': f'[{{"typeahead":{{"operator":"**","values":["{query}"]}}}}]',
        }
        response = await self._make_request_with_retry("GET", "/work_packages", params=params)
        return response.json().get('_embedded', {}).get('elements', [])

    async def get_project_hierarchy(self) -> List[Dict[str, Any]]:
        """Return projects with their parent links so caller can build a tree."""
        response = await self._make_request_with_retry("GET", "/projects")
        return response.json().get('_embedded', {}).get('elements', [])

    async def list_relations(self, work_package_id: str) -> List[Dict[str, Any]]:
        """List relations for a work package."""
        response = await self._make_request_with_retry("GET", f"/work_packages/{work_package_id}/relations")
        return response.json().get('_embedded', {}).get('elements', [])

    async def create_relation(self, work_package_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a relation on a work package."""
        try:
            response = await self._make_request_with_retry(
                "POST", f"/work_packages/{work_package_id}/relations", json=payload
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                raise Exception(e.response.json().get('message', 'Validation failed creating relation'))
            raise

    async def list_watchers(self, work_package_id: str) -> List[Dict[str, Any]]:
        response = await self._make_request_with_retry("GET", f"/work_packages/{work_package_id}/watchers")
        return response.json().get('_embedded', {}).get('elements', [])

    async def add_watcher(self, work_package_id: str, user_id: str) -> Dict[str, Any]:
        payload = {"user": {"href": f"/api/v3/users/{user_id}"}}
        response = await self._make_request_with_retry(
            "POST", f"/work_packages/{work_package_id}/watchers", json=payload
        )
        return response.json()

    async def list_statuses(self) -> List[Dict[str, Any]]:
        """List work package statuses."""
        response = await self._make_request_with_retry("GET", "/statuses")
        return response.json().get('_embedded', {}).get('elements', [])

    async def list_types(self) -> List[Dict[str, Any]]:
        """List work package types."""
        response = await self._make_request_with_retry("GET", "/types")
        return response.json().get('_embedded', {}).get('elements', [])

    async def list_priorities(self) -> List[Dict[str, Any]]:
        """List work package priorities."""
        response = await self._make_request_with_retry("GET", "/priorities")
        return response.json().get('_embedded', {}).get('elements', [])

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get a single user by id."""
        try:
            response = await self._make_request_with_retry("GET", f"/users/{user_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"User {user_id} not found")
            raise

    async def create_time_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a time entry."""
        try:
            response = await self._make_request_with_retry("POST", "/time_entries", json=payload)
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                error_data = e.response.json()
                raise Exception(error_data.get('message', 'Validation failed creating time entry'))
            raise Exception(f"Failed to create time entry: {str(e)}")

    async def list_time_entries(self, work_package_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List time entries optionally filtered by work package."""
        params: Dict[str, Any] = {}
        if work_package_id:
            params['filters'] = f'[{{"work_package":{{"operator":"=","values":["{work_package_id}"]}}}}]'
        try:
            response = await self._make_request_with_retry("GET", "/time_entries", params=params)
            return response.json().get('_embedded', {}).get('elements', [])
        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error listing time entries: {e}")
            raise Exception(f"Failed to list time entries: {str(e)}")

    async def update_work_package(self, work_package_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Patch a work package. OpenProject requires a lockVersion in the payload."""
        try:
            response = await self._make_request_with_retry("PATCH", f"/work_packages/{work_package_id}", json=payload)
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Work package {work_package_id} not found")
            if e.response.status_code == 422:
                error_data = e.response.json()
                msg = error_data.get('message', 'Validation failed updating work package')
                raise Exception(msg)
            raise Exception(f"Failed to update work package: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error updating work package: {e}")
            raise

    async def delete_work_package(self, work_package_id: str) -> None:
        """Delete a work package."""
        try:
            await self._make_request_with_retry("DELETE", f"/work_packages/{work_package_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Work package {work_package_id} not found")
            raise Exception(f"Failed to delete work package: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error deleting work package: {e}")
            raise

    async def get_users(self) -> List[Dict[str, Any]]:
        """List all users in the OpenProject instance."""
        try:
            response = await self._make_request_with_retry("GET", "/users")

            data = response.json()
            return data.get('_embedded', {}).get('elements', [])

        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error getting users: {e}")
            raise Exception(f"Failed to get users: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error getting users: {e}")
            raise

    async def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a project. Payload needs name + identifier, description optional."""
        try:
            response = await self._make_request_with_retry("POST", "/projects", json=project_data)
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                error_data = e.response.json()
                msg = error_data.get('message', 'Validation failed creating project')
                raise Exception(msg)
            self.logger.error(f"HTTP error creating project: {e}")
            raise Exception(f"Failed to create project: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error creating project: {e}")
            raise

    async def update_project(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Patch an existing project."""
        try:
            response = await self._make_request_with_retry("PATCH", f"/projects/{project_id}", json=payload)
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Project with ID {project_id} not found")
            self.logger.error(f"HTTP error updating project: {e}")
            raise Exception(f"Failed to update project: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error updating project: {e}")
            raise

    async def delete_project(self, project_id: str) -> None:
        """Delete a project by id."""
        try:
            await self._make_request_with_retry("DELETE", f"/projects/{project_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Project with ID {project_id} not found")
            self.logger.error(f"HTTP error deleting project: {e}")
            raise Exception(f"Failed to delete project: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error deleting project: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()