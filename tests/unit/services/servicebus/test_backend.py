"""
Unit tests for Service Bus backend.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest

from localzure.services.servicebus.backend import (
    ServiceBusBackend,
    QueueAlreadyExistsError,
    QueueNotFoundError,
    InvalidQueueNameError,
    QuotaExceededError,
)
from localzure.services.servicebus.models import QueueProperties, QueueRuntimeInfo


@pytest.fixture
async def backend():
    """Create a fresh backend for each test."""
    backend = ServiceBusBackend()
    await backend.reset()
    return backend


class TestCreateQueue:
    """Test queue creation."""
    
    @pytest.mark.asyncio
    async def test_create_queue_default_properties(self, backend):
        """Test creating a queue with default properties."""
        queue = await backend.create_queue("test-queue")
        
        assert queue.name == "test-queue"
        assert queue.properties.max_size_in_megabytes == 1024
        assert queue.properties.lock_duration == 60
        assert queue.runtime_info.message_count == 0
    
    @pytest.mark.asyncio
    async def test_create_queue_custom_properties(self, backend):
        """Test creating a queue with custom properties."""
        props = QueueProperties(
            max_size_in_megabytes=2048,
            lock_duration=120,
            requires_session=True,
        )
        
        queue = await backend.create_queue("custom-queue", props)
        
        assert queue.name == "custom-queue"
        assert queue.properties.max_size_in_megabytes == 2048
        assert queue.properties.lock_duration == 120
        assert queue.properties.requires_session is True
    
    @pytest.mark.asyncio
    async def test_create_queue_already_exists(self, backend):
        """Test creating a queue that already exists."""
        await backend.create_queue("test-queue")
        
        with pytest.raises(QueueAlreadyExistsError) as exc_info:
            await backend.create_queue("test-queue")
        
        assert "already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_queue_invalid_name(self, backend):
        """Test creating a queue with invalid name."""
        with pytest.raises(InvalidQueueNameError):
            await backend.create_queue("-invalid")
        
        with pytest.raises(InvalidQueueNameError):
            await backend.create_queue("invalid--name")
    
    @pytest.mark.asyncio
    async def test_create_queue_quota_exceeded(self, backend):
        """Test quota exceeded error."""
        # Create maximum number of queues
        for i in range(100):
            await backend.create_queue(f"queue-{i}")
        
        # Try to create one more
        with pytest.raises(QuotaExceededError) as exc_info:
            await backend.create_queue("queue-101")
        
        assert "exceeded" in str(exc_info.value)


class TestListQueues:
    """Test queue listing."""
    
    @pytest.mark.asyncio
    async def test_list_empty_queues(self, backend):
        """Test listing queues when none exist."""
        queues = await backend.list_queues()
        assert queues == []
    
    @pytest.mark.asyncio
    async def test_list_single_queue(self, backend):
        """Test listing a single queue."""
        await backend.create_queue("test-queue")
        
        queues = await backend.list_queues()
        
        assert len(queues) == 1
        assert queues[0].name == "test-queue"
    
    @pytest.mark.asyncio
    async def test_list_multiple_queues(self, backend):
        """Test listing multiple queues."""
        await backend.create_queue("queue-a")
        await backend.create_queue("queue-c")
        await backend.create_queue("queue-b")
        
        queues = await backend.list_queues()
        
        assert len(queues) == 3
        # Should be sorted by name
        assert queues[0].name == "queue-a"
        assert queues[1].name == "queue-b"
        assert queues[2].name == "queue-c"
    
    @pytest.mark.asyncio
    async def test_list_queues_with_pagination(self, backend):
        """Test listing queues with pagination."""
        # Create 10 queues
        for i in range(10):
            await backend.create_queue(f"queue-{i:02d}")
        
        # Get first 5
        queues = await backend.list_queues(skip=0, top=5)
        assert len(queues) == 5
        assert queues[0].name == "queue-00"
        assert queues[4].name == "queue-04"
        
        # Get next 5
        queues = await backend.list_queues(skip=5, top=5)
        assert len(queues) == 5
        assert queues[0].name == "queue-05"
        assert queues[4].name == "queue-09"
    
    @pytest.mark.asyncio
    async def test_list_queues_skip_beyond_length(self, backend):
        """Test listing queues with skip beyond total length."""
        await backend.create_queue("queue-1")
        
        queues = await backend.list_queues(skip=10, top=5)
        assert queues == []


class TestGetQueue:
    """Test getting a queue."""
    
    @pytest.mark.asyncio
    async def test_get_existing_queue(self, backend):
        """Test getting an existing queue."""
        created_queue = await backend.create_queue("test-queue")
        
        queue = await backend.get_queue("test-queue")
        
        assert queue.name == created_queue.name
        assert queue.properties.max_size_in_megabytes == created_queue.properties.max_size_in_megabytes
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_queue(self, backend):
        """Test getting a nonexistent queue."""
        with pytest.raises(QueueNotFoundError) as exc_info:
            await backend.get_queue("nonexistent")
        
        assert "not found" in str(exc_info.value)


class TestUpdateQueue:
    """Test queue update."""
    
    @pytest.mark.asyncio
    async def test_update_queue_properties(self, backend):
        """Test updating queue properties."""
        await backend.create_queue("test-queue")
        
        new_props = QueueProperties(
            max_size_in_megabytes=2048,
            lock_duration=120,
            requires_session=True,
        )
        
        updated_queue = await backend.update_queue("test-queue", new_props)
        
        assert updated_queue.properties.max_size_in_megabytes == 2048
        assert updated_queue.properties.lock_duration == 120
        assert updated_queue.properties.requires_session is True
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_queue(self, backend):
        """Test updating a nonexistent queue."""
        props = QueueProperties()
        
        with pytest.raises(QueueNotFoundError):
            await backend.update_queue("nonexistent", props)
    
    @pytest.mark.asyncio
    async def test_update_queue_updates_timestamp(self, backend):
        """Test that update changes the updated_at timestamp."""
        queue = await backend.create_queue("test-queue")
        original_updated_at = queue.updated_at
        
        # Small delay to ensure timestamp changes
        import asyncio
        await asyncio.sleep(0.01)
        
        new_props = QueueProperties(max_size_in_megabytes=2048)
        updated_queue = await backend.update_queue("test-queue", new_props)
        
        assert updated_queue.updated_at > original_updated_at


class TestDeleteQueue:
    """Test queue deletion."""
    
    @pytest.mark.asyncio
    async def test_delete_existing_queue(self, backend):
        """Test deleting an existing queue."""
        await backend.create_queue("test-queue")
        
        await backend.delete_queue("test-queue")
        
        # Queue should no longer exist
        with pytest.raises(QueueNotFoundError):
            await backend.get_queue("test-queue")
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_queue(self, backend):
        """Test deleting a nonexistent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.delete_queue("nonexistent")
    
    @pytest.mark.asyncio
    async def test_delete_queue_removes_messages(self, backend):
        """Test that deleting a queue also removes its messages."""
        await backend.create_queue("test-queue")
        
        # Verify messages dict exists
        assert "test-queue" in backend._messages
        
        await backend.delete_queue("test-queue")
        
        # Messages should be removed
        assert "test-queue" not in backend._messages


class TestGetQueueCount:
    """Test getting queue count."""
    
    @pytest.mark.asyncio
    async def test_queue_count_empty(self, backend):
        """Test queue count when no queues exist."""
        count = await backend.get_queue_count()
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_queue_count_with_queues(self, backend):
        """Test queue count with multiple queues."""
        await backend.create_queue("queue-1")
        await backend.create_queue("queue-2")
        await backend.create_queue("queue-3")
        
        count = await backend.get_queue_count()
        assert count == 3


class TestUpdateRuntimeInfo:
    """Test updating runtime information."""
    
    @pytest.mark.asyncio
    async def test_update_runtime_info(self, backend):
        """Test updating queue runtime information."""
        await backend.create_queue("test-queue")
        
        new_runtime = QueueRuntimeInfo(
            message_count=100,
            active_message_count=80,
            dead_letter_message_count=10,
        )
        
        await backend.update_runtime_info("test-queue", new_runtime)
        
        queue = await backend.get_queue("test-queue")
        assert queue.runtime_info.message_count == 100
        assert queue.runtime_info.active_message_count == 80
        assert queue.runtime_info.dead_letter_message_count == 10
    
    @pytest.mark.asyncio
    async def test_update_runtime_info_nonexistent_queue(self, backend):
        """Test updating runtime info for nonexistent queue."""
        runtime = QueueRuntimeInfo()
        
        with pytest.raises(QueueNotFoundError):
            await backend.update_runtime_info("nonexistent", runtime)


class TestReset:
    """Test backend reset."""
    
    @pytest.mark.asyncio
    async def test_reset_clears_all_queues(self, backend):
        """Test that reset clears all queues."""
        await backend.create_queue("queue-1")
        await backend.create_queue("queue-2")
        
        await backend.reset()
        
        queues = await backend.list_queues()
        assert queues == []
        
        count = await backend.get_queue_count()
        assert count == 0
