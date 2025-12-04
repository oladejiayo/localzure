"""
Unit tests for Blob Storage container backend.

Tests container storage, lifecycle, metadata operations, and error handling.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from datetime import datetime

from localzure.services.blob.backend import (
    ContainerAlreadyExistsError,
    ContainerBackend,
    ContainerNotFoundError,
    InvalidContainerNameError,
)
from localzure.services.blob.models import PublicAccessLevel


@pytest.fixture
def backend():
    """Create a fresh backend for each test."""
    return ContainerBackend()


class TestContainerBackend:
    """Test container backend operations."""
    
    @pytest.mark.asyncio
    async def test_create_container(self, backend):
        """Test creating a container."""
        container = await backend.create_container("test-container")
        assert container.name == "test-container"
        assert container.properties.etag is not None
        assert container.properties.last_modified is not None
        assert container.metadata.metadata == {}
    
    @pytest.mark.asyncio
    async def test_create_container_with_metadata(self, backend):
        """Test creating a container with metadata."""
        metadata = {"key1": "value1", "key2": "value2"}
        container = await backend.create_container("test-container", metadata=metadata)
        assert container.metadata.metadata == {"key1": "value1", "key2": "value2"}
    
    @pytest.mark.asyncio
    async def test_create_container_with_public_access(self, backend):
        """Test creating a container with public access."""
        container = await backend.create_container(
            "test-container",
            public_access=PublicAccessLevel.BLOB,
        )
        assert container.properties.public_access == PublicAccessLevel.BLOB
    
    @pytest.mark.asyncio
    async def test_create_container_invalid_name(self, backend):
        """Test creating a container with invalid name."""
        with pytest.raises(InvalidContainerNameError):
            await backend.create_container("INVALID")
    
    @pytest.mark.asyncio
    async def test_create_duplicate_container(self, backend):
        """Test creating a duplicate container."""
        await backend.create_container("test-container")
        with pytest.raises(ContainerAlreadyExistsError):
            await backend.create_container("test-container")
    
    @pytest.mark.asyncio
    async def test_list_containers_empty(self, backend):
        """Test listing containers when empty."""
        containers = await backend.list_containers()
        assert containers == []
    
    @pytest.mark.asyncio
    async def test_list_containers(self, backend):
        """Test listing containers."""
        await backend.create_container("container-a")
        await backend.create_container("container-b")
        await backend.create_container("container-c")
        
        containers = await backend.list_containers()
        assert len(containers) == 3
        names = [c.name for c in containers]
        assert names == ["container-a", "container-b", "container-c"]
    
    @pytest.mark.asyncio
    async def test_list_containers_with_prefix(self, backend):
        """Test listing containers with prefix filter."""
        await backend.create_container("test-a")
        await backend.create_container("test-b")
        await backend.create_container("other-c")
        
        containers = await backend.list_containers(prefix="test-")
        assert len(containers) == 2
        names = [c.name for c in containers]
        assert names == ["test-a", "test-b"]
    
    @pytest.mark.asyncio
    async def test_list_containers_with_max_results(self, backend):
        """Test listing containers with max results."""
        await backend.create_container("container-a")
        await backend.create_container("container-b")
        await backend.create_container("container-c")
        
        containers = await backend.list_containers(max_results=2)
        assert len(containers) == 2
    
    @pytest.mark.asyncio
    async def test_get_container(self, backend):
        """Test getting a container."""
        await backend.create_container("test-container")
        container = await backend.get_container("test-container")
        assert container.name == "test-container"
    
    @pytest.mark.asyncio
    async def test_get_container_not_found(self, backend):
        """Test getting a non-existent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.get_container("nonexistent")
    
    @pytest.mark.asyncio
    async def test_get_container_properties(self, backend):
        """Test getting container properties."""
        await backend.create_container("test-container")
        props = await backend.get_container_properties("test-container")
        assert props.etag is not None
        assert props.last_modified is not None
    
    @pytest.mark.asyncio
    async def test_set_container_metadata(self, backend):
        """Test setting container metadata."""
        container = await backend.create_container("test-container")
        original_etag = container.properties.etag
        
        updated = await backend.set_container_metadata(
            "test-container",
            {"new-key": "new-value"},
        )
        
        assert updated.metadata.metadata == {"new-key": "new-value"}
        assert updated.properties.etag != original_etag  # ETag should change
    
    @pytest.mark.asyncio
    async def test_set_container_metadata_not_found(self, backend):
        """Test setting metadata on non-existent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.set_container_metadata("nonexistent", {})
    
    @pytest.mark.asyncio
    async def test_delete_container(self, backend):
        """Test deleting a container."""
        await backend.create_container("test-container")
        await backend.delete_container("test-container")
        
        with pytest.raises(ContainerNotFoundError):
            await backend.get_container("test-container")
    
    @pytest.mark.asyncio
    async def test_delete_container_not_found(self, backend):
        """Test deleting a non-existent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.delete_container("nonexistent")
    
    @pytest.mark.asyncio
    async def test_container_exists(self, backend):
        """Test checking if container exists."""
        assert not await backend.container_exists("test-container")
        await backend.create_container("test-container")
        assert await backend.container_exists("test-container")
    
    @pytest.mark.asyncio
    async def test_reset(self, backend):
        """Test resetting the backend."""
        await backend.create_container("container-a")
        await backend.create_container("container-b")
        
        await backend.reset()
        
        containers = await backend.list_containers()
        assert containers == []
    
    @pytest.mark.asyncio
    async def test_etag_uniqueness(self, backend):
        """Test that ETags are unique."""
        container1 = await backend.create_container("container-1")
        container2 = await backend.create_container("container-2")
        assert container1.properties.etag != container2.properties.etag
    
    @pytest.mark.asyncio
    async def test_last_modified_updated(self, backend):
        """Test that last_modified is updated on metadata change."""
        container = await backend.create_container("test-container")
        original_time = container.properties.last_modified
        
        # Small delay to ensure time difference
        import asyncio
        await asyncio.sleep(0.01)
        
        updated = await backend.set_container_metadata("test-container", {"key": "value"})
        assert updated.properties.last_modified > original_time
