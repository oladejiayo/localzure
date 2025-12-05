"""
Unit tests for Queue Storage backend operations.

Tests queue CRUD operations, list, metadata, and error handling.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest

from localzure.services.queue.backend import (
    QueueAlreadyExistsError,
    QueueBackend,
    QueueNotFoundError,
    InvalidQueueNameError,
)


@pytest.fixture
def backend():
    """Create a fresh backend for each test."""
    return QueueBackend()


@pytest.fixture
async def backend_with_queue(backend):
    """Create a backend with a test queue."""
    await backend.create_queue("test-queue", {"key": "value"})
    return backend


class TestCreateQueue:
    """Test queue creation operations."""
    
    @pytest.mark.asyncio
    async def test_create_queue_minimal(self, backend):
        """Test creating a queue with minimal parameters."""
        queue = await backend.create_queue("myqueue")
        
        assert queue.name == "myqueue"
        assert queue.metadata.metadata == {}
        assert queue.properties.approximate_message_count == 0
    
    @pytest.mark.asyncio
    async def test_create_queue_with_metadata(self, backend):
        """Test creating a queue with metadata."""
        metadata = {"key1": "value1", "key2": "value2"}
        queue = await backend.create_queue("myqueue", metadata)
        
        assert queue.metadata.metadata == metadata
    
    @pytest.mark.asyncio
    async def test_create_queue_invalid_name(self, backend):
        """Test creating queue with invalid name."""
        with pytest.raises(InvalidQueueNameError):
            await backend.create_queue("InvalidQueue")
    
    @pytest.mark.asyncio
    async def test_create_duplicate_queue(self, backend_with_queue):
        """Test creating duplicate queue returns error."""
        with pytest.raises(QueueAlreadyExistsError):
            await backend_with_queue.create_queue("test-queue")


class TestGetQueue:
    """Test queue retrieval operations."""
    
    @pytest.mark.asyncio
    async def test_get_existing_queue(self, backend_with_queue):
        """Test getting an existing queue."""
        queue = await backend_with_queue.get_queue("test-queue")
        assert queue.name == "test-queue"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_queue(self, backend):
        """Test getting a non-existent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.get_queue("nonexistent")


class TestListQueues:
    """Test queue listing operations."""
    
    @pytest.mark.asyncio
    async def test_list_empty_queues(self, backend):
        """Test listing when no queues exist."""
        queues, marker = await backend.list_queues()
        assert queues == []
        assert marker is None
    
    @pytest.mark.asyncio
    async def test_list_single_queue(self, backend_with_queue):
        """Test listing single queue."""
        queues, marker = await backend_with_queue.list_queues()
        
        assert len(queues) == 1
        assert queues[0].name == "test-queue"
        assert marker is None
    
    @pytest.mark.asyncio
    async def test_list_multiple_queues(self, backend):
        """Test listing multiple queues."""
        await backend.create_queue("queue1")
        await backend.create_queue("queue2")
        await backend.create_queue("queue3")
        
        queues, _ = await backend.list_queues()
        
        assert len(queues) == 3
        assert [q.name for q in queues] == ["queue1", "queue2", "queue3"]
    
    @pytest.mark.asyncio
    async def test_list_queues_with_prefix(self, backend):
        """Test listing queues with prefix filter."""
        await backend.create_queue("test-queue-1")
        await backend.create_queue("test-queue-2")
        await backend.create_queue("other-queue")
        
        queues, _ = await backend.list_queues(prefix="test-")
        
        assert len(queues) == 2
        assert all(q.name.startswith("test-") for q in queues)
    
    @pytest.mark.asyncio
    async def test_list_queues_with_max_results(self, backend):
        """Test listing queues with max results."""
        await backend.create_queue("queue1")
        await backend.create_queue("queue2")
        await backend.create_queue("queue3")
        
        queues, marker = await backend.list_queues(max_results=2)
        
        assert len(queues) == 2
        assert marker == "queue2"
    
    @pytest.mark.asyncio
    async def test_list_queues_with_marker(self, backend):
        """Test listing queues with continuation marker."""
        await backend.create_queue("queue1")
        await backend.create_queue("queue2")
        await backend.create_queue("queue3")
        
        queues, _ = await backend.list_queues(marker="queue1")
        
        assert len(queues) == 2
        assert queues[0].name == "queue2"
        assert queues[1].name == "queue3"
    
    @pytest.mark.asyncio
    async def test_list_queues_without_metadata(self, backend):
        """Test listing queues excludes metadata by default."""
        await backend.create_queue("queue1", {"key": "value"})
        
        queues, _ = await backend.list_queues(include_metadata=False)
        
        assert queues[0].metadata.metadata == {}
    
    @pytest.mark.asyncio
    async def test_list_queues_with_metadata(self, backend):
        """Test listing queues with metadata included."""
        metadata = {"key": "value"}
        await backend.create_queue("queue1", metadata)
        
        queues, _ = await backend.list_queues(include_metadata=True)
        
        assert queues[0].metadata.metadata == metadata


class TestGetQueueMetadata:
    """Test queue metadata retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_queue_metadata(self, backend_with_queue):
        """Test getting queue metadata."""
        metadata, properties = await backend_with_queue.get_queue_metadata("test-queue")
        
        assert metadata.metadata == {"key": "value"}
        assert properties.approximate_message_count == 0
    
    @pytest.mark.asyncio
    async def test_get_queue_metadata_nonexistent(self, backend):
        """Test getting metadata for non-existent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.get_queue_metadata("nonexistent")


class TestSetQueueMetadata:
    """Test queue metadata updates."""
    
    @pytest.mark.asyncio
    async def test_set_queue_metadata(self, backend_with_queue):
        """Test setting queue metadata."""
        new_metadata = {"new-key": "new-value"}
        await backend_with_queue.set_queue_metadata("test-queue", new_metadata)
        
        metadata, _ = await backend_with_queue.get_queue_metadata("test-queue")
        assert metadata.metadata == new_metadata
    
    @pytest.mark.asyncio
    async def test_set_queue_metadata_empty(self, backend_with_queue):
        """Test setting empty metadata."""
        await backend_with_queue.set_queue_metadata("test-queue", {})
        
        metadata, _ = await backend_with_queue.get_queue_metadata("test-queue")
        assert metadata.metadata == {}
    
    @pytest.mark.asyncio
    async def test_set_queue_metadata_nonexistent(self, backend):
        """Test setting metadata for non-existent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.set_queue_metadata("nonexistent", {})


class TestDeleteQueue:
    """Test queue deletion operations."""
    
    @pytest.mark.asyncio
    async def test_delete_queue(self, backend_with_queue):
        """Test deleting a queue."""
        await backend_with_queue.delete_queue("test-queue")
        
        with pytest.raises(QueueNotFoundError):
            await backend_with_queue.get_queue("test-queue")
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_queue(self, backend):
        """Test deleting non-existent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.delete_queue("nonexistent")


class TestResetBackend:
    """Test backend reset operation."""
    
    @pytest.mark.asyncio
    async def test_reset_clears_all_queues(self, backend):
        """Test that reset clears all queues."""
        await backend.create_queue("queue1")
        await backend.create_queue("queue2")
        
        await backend.reset()
        
        queues, _ = await backend.list_queues()
        assert len(queues) == 0
