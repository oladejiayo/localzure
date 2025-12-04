"""
Integration tests for Blob Storage API endpoints.

Tests complete workflows including container operations, metadata, and error handling.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from localzure.services.blob.api import router, backend


@pytest.fixture
def app():
    """Create a FastAPI application for testing."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
async def reset_backend():
    """Reset backend before each test."""
    await backend.reset()
    yield
    await backend.reset()


class TestCreateContainer:
    """Test container creation endpoint."""
    
    def test_create_container_success(self, client):
        """Test successful container creation."""
        response = client.put("/blob/testaccount/test-container")
        assert response.status_code == 201
        assert 'ETag' in response.headers
        assert 'Last-Modified' in response.headers
        assert response.headers['x-ms-version'] == '2021-08-06'
    
    def test_create_container_with_metadata(self, client):
        """Test creating container with metadata."""
        headers = {
            'x-ms-meta-key1': 'value1',
            'x-ms-meta-key2': 'value2',
        }
        response = client.put("/blob/testaccount/test-container", headers=headers)
        assert response.status_code == 201
    
    def test_create_container_with_public_access(self, client):
        """Test creating container with public access."""
        headers = {'x-ms-blob-public-access': 'blob'}
        response = client.put("/blob/testaccount/test-container", headers=headers)
        assert response.status_code == 201
        assert response.headers['x-ms-blob-public-access'] == 'blob'
    
    def test_create_container_invalid_name(self, client):
        """Test creating container with invalid name."""
        response = client.put("/blob/testaccount/INVALID")
        assert response.status_code == 400
        assert 'InvalidContainerName' in response.text
    
    def test_create_duplicate_container(self, client):
        """Test creating duplicate container."""
        client.put("/blob/testaccount/test-container")
        response = client.put("/blob/testaccount/test-container")
        assert response.status_code == 409
        assert 'ContainerAlreadyExists' in response.text


class TestListContainers:
    """Test list containers endpoint."""
    
    def test_list_containers_empty(self, client):
        """Test listing containers when empty."""
        response = client.get("/blob/testaccount")
        assert response.status_code == 200
        data = response.json()
        assert data['Containers'] == []
    
    def test_list_containers(self, client):
        """Test listing containers."""
        client.put("/blob/testaccount/container-a")
        client.put("/blob/testaccount/container-b")
        
        response = client.get("/blob/testaccount")
        assert response.status_code == 200
        data = response.json()
        assert len(data['Containers']) == 2
        names = [c['Name'] for c in data['Containers']]
        assert 'container-a' in names
        assert 'container-b' in names
    
    def test_list_containers_with_prefix(self, client):
        """Test listing containers with prefix."""
        client.put("/blob/testaccount/test-a")
        client.put("/blob/testaccount/test-b")
        client.put("/blob/testaccount/other-c")
        
        response = client.get("/blob/testaccount?prefix=test-")
        assert response.status_code == 200
        data = response.json()
        assert len(data['Containers']) == 2
    
    def test_list_containers_with_max_results(self, client):
        """Test listing containers with max results."""
        client.put("/blob/testaccount/container-a")
        client.put("/blob/testaccount/container-b")
        client.put("/blob/testaccount/container-c")
        
        response = client.get("/blob/testaccount?maxresults=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data['Containers']) == 2


class TestGetContainerProperties:
    """Test get container properties endpoint."""
    
    def test_get_container_properties(self, client):
        """Test getting container properties."""
        client.put("/blob/testaccount/test-container")
        response = client.get("/blob/testaccount/test-container")
        assert response.status_code == 200
        assert 'ETag' in response.headers
        assert 'Last-Modified' in response.headers
        assert 'x-ms-lease-status' in response.headers
        assert 'x-ms-lease-state' in response.headers
    
    def test_get_container_properties_with_metadata(self, client):
        """Test getting properties includes metadata."""
        headers = {'x-ms-meta-key': 'value'}
        client.put("/blob/testaccount/test-container", headers=headers)
        
        response = client.get("/blob/testaccount/test-container")
        assert response.status_code == 200
        assert 'x-ms-meta-key' in response.headers
        assert response.headers['x-ms-meta-key'] == 'value'
    
    def test_get_container_properties_not_found(self, client):
        """Test getting properties of non-existent container."""
        response = client.get("/blob/testaccount/nonexistent")
        assert response.status_code == 404
        assert 'ContainerNotFound' in response.text


class TestSetContainerMetadata:
    """Test set container metadata endpoint."""
    
    def test_set_container_metadata(self, client):
        """Test setting container metadata."""
        client.put("/blob/testaccount/test-container")
        
        headers = {
            'x-ms-meta-key1': 'value1',
            'x-ms-meta-key2': 'value2',
        }
        response = client.put("/blob/testaccount/test-container/metadata", headers=headers)
        assert response.status_code == 200
        assert 'ETag' in response.headers
    
    def test_set_container_metadata_updates_etag(self, client):
        """Test that setting metadata updates ETag."""
        create_response = client.put("/blob/testaccount/test-container")
        original_etag = create_response.headers['ETag']
        
        headers = {'x-ms-meta-key': 'value'}
        update_response = client.put("/blob/testaccount/test-container/metadata", headers=headers)
        new_etag = update_response.headers['ETag']
        
        assert new_etag != original_etag
    
    def test_set_container_metadata_not_found(self, client):
        """Test setting metadata on non-existent container."""
        response = client.put("/blob/testaccount/nonexistent/metadata")
        assert response.status_code == 404
        assert 'ContainerNotFound' in response.text


class TestDeleteContainer:
    """Test delete container endpoint."""
    
    def test_delete_container(self, client):
        """Test deleting a container."""
        client.put("/blob/testaccount/test-container")
        response = client.delete("/blob/testaccount/test-container")
        assert response.status_code == 202
    
    def test_delete_container_not_found(self, client):
        """Test deleting non-existent container."""
        response = client.delete("/blob/testaccount/nonexistent")
        assert response.status_code == 404
        assert 'ContainerNotFound' in response.text
    
    def test_delete_container_verify_gone(self, client):
        """Test that deleted container is gone."""
        client.put("/blob/testaccount/test-container")
        client.delete("/blob/testaccount/test-container")
        
        response = client.get("/blob/testaccount/test-container")
        assert response.status_code == 404


class TestContainerWorkflow:
    """Test complete container workflows."""
    
    def test_full_lifecycle(self, client):
        """Test full container lifecycle."""
        # Create
        create_resp = client.put(
            "/blob/testaccount/workflow-container",
            headers={'x-ms-meta-created': 'true'}
        )
        assert create_resp.status_code == 201
        
        # List
        list_resp = client.get("/blob/testaccount")
        assert list_resp.status_code == 200
        containers = list_resp.json()['Containers']
        assert len(containers) == 1
        assert containers[0]['Name'] == 'workflow-container'
        
        # Get properties
        props_resp = client.get("/blob/testaccount/workflow-container")
        assert props_resp.status_code == 200
        assert 'x-ms-meta-created' in props_resp.headers
        
        # Update metadata
        update_resp = client.put(
            "/blob/testaccount/workflow-container/metadata",
            headers={'x-ms-meta-updated': 'true'}
        )
        assert update_resp.status_code == 200
        
        # Verify metadata updated
        props_resp2 = client.get("/blob/testaccount/workflow-container")
        assert 'x-ms-meta-updated' in props_resp2.headers
        assert 'x-ms-meta-created' not in props_resp2.headers  # Old metadata replaced
        
        # Delete
        delete_resp = client.delete("/blob/testaccount/workflow-container")
        assert delete_resp.status_code == 202
        
        # Verify gone
        list_resp2 = client.get("/blob/testaccount")
        assert len(list_resp2.json()['Containers']) == 0
    
    def test_multiple_containers(self, client):
        """Test managing multiple containers."""
        # Create multiple containers
        for i in range(5):
            response = client.put(f"/blob/testaccount/container-{i}")
            assert response.status_code == 201
        
        # List all
        response = client.get("/blob/testaccount")
        assert len(response.json()['Containers']) == 5
        
        # Delete some
        client.delete("/blob/testaccount/container-0")
        client.delete("/blob/testaccount/container-2")
        
        # Verify count
        response = client.get("/blob/testaccount")
        assert len(response.json()['Containers']) == 3
