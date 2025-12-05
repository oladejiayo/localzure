"""
Unit tests for Queue Storage backend message operations.

Tests message CRUD operations, visibility timeout, TTL, dequeue count.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from datetime import datetime, timezone, timedelta

from localzure.services.queue.backend import (
    QueueBackend,
    QueueNotFoundError,
    MessageNotFoundError,
    InvalidPopReceiptError,
)


@pytest.fixture
def backend():
    """Create a fresh backend for each test."""
    return QueueBackend()


@pytest.fixture
async def backend_with_queue(backend):
    """Create a backend with a test queue."""
    await backend.create_queue("test-queue")
    return backend


class TestPutMessage:
    """Tests for put_message operation."""
    
    @pytest.mark.asyncio
    async def test_put_message_basic(self, backend_with_queue):
        """Test putting a basic message."""
        message = await backend_with_queue.put_message("test-queue", "Hello")
        
        assert message.message_id is not None
        assert message.dequeue_count == 0
        assert message.message_text is not None
    
    @pytest.mark.asyncio
    async def test_put_message_with_visibility_timeout(self, backend_with_queue):
        """Test putting message with visibility timeout."""
        message = await backend_with_queue.put_message(
            "test-queue",
            "Hello",
            visibility_timeout=60,
        )
        
        assert not message.is_visible()
    
    @pytest.mark.asyncio
    async def test_put_message_with_ttl(self, backend_with_queue):
        """Test putting message with custom TTL."""
        message = await backend_with_queue.put_message(
            "test-queue",
            "Hello",
            message_ttl=3600,
        )
        
        delta = (message.expiration_time - message.insertion_time).total_seconds()
        assert abs(delta - 3600) < 1
    
    @pytest.mark.asyncio
    async def test_put_message_updates_count(self, backend_with_queue):
        """Test that putting message updates queue message count."""
        await backend_with_queue.put_message("test-queue", "Msg1")
        await backend_with_queue.put_message("test-queue", "Msg2")
        
        metadata, properties = await backend_with_queue.get_queue_metadata("test-queue")
        assert properties.approximate_message_count == 2
    
    @pytest.mark.asyncio
    async def test_put_message_queue_not_found(self, backend):
        """Test putting message to non-existent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.put_message("nonexistent", "Hello")


class TestGetMessages:
    """Tests for get_messages operation."""
    
    @pytest.mark.asyncio
    async def test_get_messages_empty_queue(self, backend_with_queue):
        """Test getting messages from empty queue."""
        messages = await backend_with_queue.get_messages("test-queue")
        assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_get_single_message(self, backend_with_queue):
        """Test getting a single message."""
        await backend_with_queue.put_message("test-queue", "Test")
        
        messages = await backend_with_queue.get_messages("test-queue")
        
        assert len(messages) == 1
        assert messages[0].dequeue_count == 1
    
    @pytest.mark.asyncio
    async def test_get_multiple_messages(self, backend_with_queue):
        """Test getting multiple messages."""
        await backend_with_queue.put_message("test-queue", "Msg1")
        await backend_with_queue.put_message("test-queue", "Msg2")
        await backend_with_queue.put_message("test-queue", "Msg3")
        
        messages = await backend_with_queue.get_messages("test-queue", num_messages=3)
        
        assert len(messages) == 3
    
    @pytest.mark.asyncio
    async def test_get_messages_respects_num_messages(self, backend_with_queue):
        """Test that get_messages respects num_messages parameter."""
        for i in range(5):
            await backend_with_queue.put_message("test-queue", f"Msg{i}")
        
        messages = await backend_with_queue.get_messages("test-queue", num_messages=2)
        
        assert len(messages) == 2
    
    @pytest.mark.asyncio
    async def test_get_messages_sets_visibility_timeout(self, backend_with_queue):
        """Test that get_messages sets visibility timeout."""
        await backend_with_queue.put_message("test-queue", "Test")
        
        messages = await backend_with_queue.get_messages("test-queue", visibility_timeout=60)
        
        assert not messages[0].is_visible()
    
    @pytest.mark.asyncio
    async def test_get_messages_increments_dequeue_count(self, backend_with_queue):
        """Test that get_messages increments dequeue count."""
        await backend_with_queue.put_message("test-queue", "Test")
        
        # Get once
        messages1 = await backend_with_queue.get_messages("test-queue", visibility_timeout=0)
        assert messages1[0].dequeue_count == 1
        
        # Get again
        messages2 = await backend_with_queue.get_messages("test-queue", visibility_timeout=0)
        assert messages2[0].dequeue_count == 2
    
    @pytest.mark.asyncio
    async def test_get_messages_updates_pop_receipt(self, backend_with_queue):
        """Test that get_messages generates new pop receipt."""
        await backend_with_queue.put_message("test-queue", "Test")
        
        messages1 = await backend_with_queue.get_messages("test-queue", visibility_timeout=0)
        original_receipt = messages1[0].pop_receipt
        
        messages2 = await backend_with_queue.get_messages("test-queue", visibility_timeout=0)
        new_receipt = messages2[0].pop_receipt
        
        assert new_receipt != original_receipt
    
    @pytest.mark.asyncio
    async def test_get_messages_removes_expired(self, backend_with_queue):
        """Test that get_messages removes expired messages."""
        # Put message with 1 second TTL
        await backend_with_queue.put_message("test-queue", "Test", message_ttl=1)
        
        # Manually set expiration to past
        backend_with_queue._messages["test-queue"][0].expiration_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        messages = await backend_with_queue.get_messages("test-queue")
        
        assert len(messages) == 0
        assert len(backend_with_queue._messages["test-queue"]) == 0
    
    @pytest.mark.asyncio
    async def test_get_messages_skips_invisible(self, backend_with_queue):
        """Test that get_messages skips invisible messages."""
        await backend_with_queue.put_message("test-queue", "Msg1")
        await backend_with_queue.put_message("test-queue", "Msg2")
        
        # Get first message with visibility timeout
        await backend_with_queue.get_messages("test-queue", num_messages=1, visibility_timeout=3600)
        
        # Get messages again - should only get second message
        messages = await backend_with_queue.get_messages("test-queue", num_messages=2)
        
        assert len(messages) == 1
    
    @pytest.mark.asyncio
    async def test_get_messages_queue_not_found(self, backend):
        """Test getting messages from non-existent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.get_messages("nonexistent")


class TestPeekMessages:
    """Tests for peek_messages operation."""
    
    @pytest.mark.asyncio
    async def test_peek_messages_empty_queue(self, backend_with_queue):
        """Test peeking at empty queue."""
        messages = await backend_with_queue.peek_messages("test-queue")
        assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_peek_single_message(self, backend_with_queue):
        """Test peeking at a single message."""
        await backend_with_queue.put_message("test-queue", "Test")
        
        messages = await backend_with_queue.peek_messages("test-queue")
        
        assert len(messages) == 1
        assert messages[0].dequeue_count == 0  # Not incremented
    
    @pytest.mark.asyncio
    async def test_peek_does_not_change_visibility(self, backend_with_queue):
        """Test that peek doesn't change message visibility."""
        await backend_with_queue.put_message("test-queue", "Test")
        
        messages_before = await backend_with_queue.peek_messages("test-queue")
        time_before = messages_before[0].time_next_visible
        pop_receipt_before = messages_before[0].pop_receipt
        
        messages_after = await backend_with_queue.peek_messages("test-queue")
        
        assert messages_after[0].time_next_visible == time_before
        assert messages_after[0].pop_receipt == pop_receipt_before
    
    @pytest.mark.asyncio
    async def test_peek_multiple_messages(self, backend_with_queue):
        """Test peeking at multiple messages."""
        for i in range(3):
            await backend_with_queue.put_message("test-queue", f"Msg{i}")
        
        messages = await backend_with_queue.peek_messages("test-queue", num_messages=3)
        
        assert len(messages) == 3
    
    @pytest.mark.asyncio
    async def test_peek_respects_num_messages(self, backend_with_queue):
        """Test that peek respects num_messages parameter."""
        for i in range(5):
            await backend_with_queue.put_message("test-queue", f"Msg{i}")
        
        messages = await backend_with_queue.peek_messages("test-queue", num_messages=2)
        
        assert len(messages) == 2
    
    @pytest.mark.asyncio
    async def test_peek_removes_expired(self, backend_with_queue):
        """Test that peek removes expired messages."""
        await backend_with_queue.put_message("test-queue", "Test", message_ttl=1)
        
        # Manually expire the message
        backend_with_queue._messages["test-queue"][0].expiration_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        messages = await backend_with_queue.peek_messages("test-queue")
        
        assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_peek_queue_not_found(self, backend):
        """Test peeking at non-existent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.peek_messages("nonexistent")


class TestUpdateMessage:
    """Tests for update_message operation."""
    
    @pytest.mark.asyncio
    async def test_update_message_visibility(self, backend_with_queue):
        """Test updating message visibility timeout."""
        await backend_with_queue.put_message("test-queue", "Test")
        messages = await backend_with_queue.get_messages("test-queue")
        
        message = messages[0]
        old_receipt = message.pop_receipt
        
        new_receipt = await backend_with_queue.update_message(
            "test-queue",
            message.message_id,
            message.pop_receipt,
            60,
        )
        
        assert new_receipt != old_receipt
    
    @pytest.mark.asyncio
    async def test_update_message_text(self, backend_with_queue):
        """Test updating message text."""
        await backend_with_queue.put_message("test-queue", "Original")
        messages = await backend_with_queue.get_messages("test-queue")
        
        message = messages[0]
        new_text = "Updated"
        
        # Update with visibility=0 to make immediately visible
        await backend_with_queue.update_message(
            "test-queue",
            message.message_id,
            message.pop_receipt,
            0,
            new_text,
        )
        
        # Peek to verify text changed
        updated_messages = await backend_with_queue.peek_messages("test-queue")
        assert updated_messages[0].message_text == new_text
    
    @pytest.mark.asyncio
    async def test_update_message_invalid_pop_receipt(self, backend_with_queue):
        """Test updating with invalid pop receipt."""
        await backend_with_queue.put_message("test-queue", "Test")
        messages = await backend_with_queue.get_messages("test-queue")
        
        message = messages[0]
        
        with pytest.raises(InvalidPopReceiptError):
            await backend_with_queue.update_message(
                "test-queue",
                message.message_id,
                "invalid-receipt",
                30,
            )
    
    @pytest.mark.asyncio
    async def test_update_message_not_found(self, backend_with_queue):
        """Test updating non-existent message."""
        with pytest.raises(MessageNotFoundError):
            await backend_with_queue.update_message(
                "test-queue",
                "nonexistent-id",
                "some-receipt",
                30,
            )
    
    @pytest.mark.asyncio
    async def test_update_expired_message(self, backend_with_queue):
        """Test updating expired message."""
        await backend_with_queue.put_message("test-queue", "Test", message_ttl=1)
        messages = await backend_with_queue.get_messages("test-queue")
        
        message = messages[0]
        
        # Manually expire the message
        backend_with_queue._messages["test-queue"][0].expiration_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        with pytest.raises(MessageNotFoundError):
            await backend_with_queue.update_message(
                "test-queue",
                message.message_id,
                message.pop_receipt,
                30,
            )
    
    @pytest.mark.asyncio
    async def test_update_message_queue_not_found(self, backend):
        """Test updating message in non-existent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.update_message("nonexistent", "msg-id", "receipt", 30)


class TestDeleteMessage:
    """Tests for delete_message operation."""
    
    @pytest.mark.asyncio
    async def test_delete_message(self, backend_with_queue):
        """Test deleting a message."""
        await backend_with_queue.put_message("test-queue", "Test")
        messages = await backend_with_queue.get_messages("test-queue")
        
        message = messages[0]
        
        await backend_with_queue.delete_message(
            "test-queue",
            message.message_id,
            message.pop_receipt,
        )
        
        # Verify message is gone
        remaining = await backend_with_queue.peek_messages("test-queue")
        assert len(remaining) == 0
    
    @pytest.mark.asyncio
    async def test_delete_message_updates_count(self, backend_with_queue):
        """Test that deleting message updates queue count."""
        await backend_with_queue.put_message("test-queue", "Test")
        messages = await backend_with_queue.get_messages("test-queue")
        
        await backend_with_queue.delete_message(
            "test-queue",
            messages[0].message_id,
            messages[0].pop_receipt,
        )
        
        metadata, properties = await backend_with_queue.get_queue_metadata("test-queue")
        assert properties.approximate_message_count == 0
    
    @pytest.mark.asyncio
    async def test_delete_message_invalid_pop_receipt(self, backend_with_queue):
        """Test deleting with invalid pop receipt."""
        await backend_with_queue.put_message("test-queue", "Test")
        messages = await backend_with_queue.get_messages("test-queue")
        
        message = messages[0]
        
        with pytest.raises(InvalidPopReceiptError):
            await backend_with_queue.delete_message(
                "test-queue",
                message.message_id,
                "invalid-receipt",
            )
    
    @pytest.mark.asyncio
    async def test_delete_message_not_found(self, backend_with_queue):
        """Test deleting non-existent message."""
        with pytest.raises(MessageNotFoundError):
            await backend_with_queue.delete_message(
                "test-queue",
                "nonexistent-id",
                "some-receipt",
            )
    
    @pytest.mark.asyncio
    async def test_delete_message_queue_not_found(self, backend):
        """Test deleting message from non-existent queue."""
        with pytest.raises(QueueNotFoundError):
            await backend.delete_message("nonexistent", "msg-id", "receipt")


class TestMessageIntegration:
    """Integration tests for message operations."""
    
    @pytest.mark.asyncio
    async def test_put_get_delete_workflow(self, backend_with_queue):
        """Test complete message lifecycle."""
        # Put message
        put_msg = await backend_with_queue.put_message("test-queue", "Test")
        assert put_msg.message_id is not None
        
        # Get message
        get_msgs = await backend_with_queue.get_messages("test-queue")
        assert len(get_msgs) == 1
        assert get_msgs[0].message_id == put_msg.message_id
        assert get_msgs[0].dequeue_count == 1
        
        # Delete message
        await backend_with_queue.delete_message(
            "test-queue",
            get_msgs[0].message_id,
            get_msgs[0].pop_receipt,
        )
        
        # Verify gone
        remaining = await backend_with_queue.peek_messages("test-queue")
        assert len(remaining) == 0
    
    @pytest.mark.asyncio
    async def test_peek_does_not_affect_get(self, backend_with_queue):
        """Test that peek doesn't interfere with get."""
        await backend_with_queue.put_message("test-queue", "Test")
        
        # Peek first
        peek_msgs = await backend_with_queue.peek_messages("test-queue")
        assert len(peek_msgs) == 1
        
        # Get should still work
        get_msgs = await backend_with_queue.get_messages("test-queue")
        assert len(get_msgs) == 1
        assert get_msgs[0].message_id == peek_msgs[0].message_id
    
    @pytest.mark.asyncio
    async def test_multiple_queues_isolated(self, backend):
        """Test that messages in different queues are isolated."""
        await backend.create_queue("queue1")
        await backend.create_queue("queue2")
        
        await backend.put_message("queue1", "Msg1")
        await backend.put_message("queue2", "Msg2")
        
        msgs1 = await backend.get_messages("queue1")
        msgs2 = await backend.get_messages("queue2")
        
        assert len(msgs1) == 1
        assert len(msgs2) == 1
        assert msgs1[0].message_id != msgs2[0].message_id
