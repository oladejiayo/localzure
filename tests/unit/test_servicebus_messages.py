"""
Unit Tests for Service Bus Message Operations

Tests for message send, receive, complete, abandon, dead-letter, and lock renewal.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta

from localzure.services.servicebus.backend import (
    ServiceBusBackend,
    QueueNotFoundError,
    MessageNotFoundError,
    MessageLockLostError,
)
from localzure.services.servicebus.models import (
    QueueProperties,
    ServiceBusMessage,
    SendMessageRequest,
    ReceiveMode,
)


@pytest.fixture
async def backend():
    """Create a fresh backend for each test."""
    b = ServiceBusBackend()
    await b.reset()
    yield b
    await b.reset()


@pytest.fixture
async def backend_with_queue(backend):
    """Create a backend with a test queue."""
    props = QueueProperties(
        max_size_in_megabytes=1024,
        default_message_time_to_live=1209600,
        lock_duration=60,
        requires_session=False,
        requires_duplicate_detection=False,
        enable_dead_lettering_on_message_expiration=False,
        enable_batched_operations=True,
        max_delivery_count=10,
    )
    await backend.create_queue("test-queue", props)
    return backend


class TestSendMessage:
    """Tests for sending messages."""
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, backend_with_queue):
        """Test sending a message successfully."""
        request = SendMessageRequest(
            body="Test message body",
            label="test-label",
            content_type="text/plain",
        )
        
        message = await backend_with_queue.send_message("test-queue", request)
        
        assert message.message_id is not None
        assert message.body == "Test message body"
        assert message.label == "test-label"
        assert message.content_type == "text/plain"
        assert message.sequence_number == 1
        assert message.delivery_count == 0
        assert message.is_locked is False
        assert message.lock_token is None
    
    @pytest.mark.asyncio
    async def test_send_message_with_all_properties(self, backend_with_queue):
        """Test sending a message with all properties."""
        request = SendMessageRequest(
            body="Full message",
            session_id="session-123",
            correlation_id="corr-456",
            content_type="application/json",
            label="important",
            to="recipient",
            reply_to="sender",
            time_to_live=3600,
            user_properties={"key1": "value1", "key2": "value2"},
        )
        
        message = await backend_with_queue.send_message("test-queue", request)
        
        assert message.session_id == "session-123"
        assert message.correlation_id == "corr-456"
        assert message.content_type == "application/json"
        assert message.label == "important"
        assert message.to == "recipient"
        assert message.reply_to == "sender"
        assert message.time_to_live == 3600
        assert message.user_properties == {"key1": "value1", "key2": "value2"}
    
    @pytest.mark.asyncio
    async def test_send_message_increments_sequence_number(self, backend_with_queue):
        """Test that sequence numbers increment."""
        request = SendMessageRequest(body="Message 1")
        msg1 = await backend_with_queue.send_message("test-queue", request)
        
        request = SendMessageRequest(body="Message 2")
        msg2 = await backend_with_queue.send_message("test-queue", request)
        
        request = SendMessageRequest(body="Message 3")
        msg3 = await backend_with_queue.send_message("test-queue", request)
        
        assert msg1.sequence_number == 1
        assert msg2.sequence_number == 2
        assert msg3.sequence_number == 3
    
    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_queue(self, backend):
        """Test sending to a queue that doesn't exist."""
        request = SendMessageRequest(body="Test")
        
        with pytest.raises(QueueNotFoundError):
            await backend.send_message("nonexistent-queue", request)
    
    @pytest.mark.asyncio
    async def test_send_message_updates_runtime_info(self, backend_with_queue):
        """Test that sending updates queue runtime info."""
        request = SendMessageRequest(body="Test")
        await backend_with_queue.send_message("test-queue", request)
        
        queue = await backend_with_queue.get_queue("test-queue")
        assert queue.runtime_info.message_count == 1
        assert queue.runtime_info.active_message_count == 1


class TestReceiveMessage:
    """Tests for receiving messages."""
    
    @pytest.mark.asyncio
    async def test_receive_message_peek_lock_mode(self, backend_with_queue):
        """Test receiving a message in PeekLock mode."""
        # Send a message
        request = SendMessageRequest(body="Test message")
        await backend_with_queue.send_message("test-queue", request)
        
        # Receive it
        message = await backend_with_queue.receive_message("test-queue", ReceiveMode.PEEK_LOCK)
        
        assert message is not None
        assert message.body == "Test message"
        assert message.lock_token is not None
        assert message.is_locked is True
        assert message.locked_until_utc is not None
        assert message.delivery_count == 1
    
    @pytest.mark.asyncio
    async def test_receive_message_receive_and_delete_mode(self, backend_with_queue):
        """Test receiving a message in ReceiveAndDelete mode."""
        # Send a message
        request = SendMessageRequest(body="Test message")
        await backend_with_queue.send_message("test-queue", request)
        
        # Receive it
        message = await backend_with_queue.receive_message("test-queue", ReceiveMode.RECEIVE_AND_DELETE)
        
        assert message is not None
        assert message.body == "Test message"
        assert message.lock_token is None
        assert message.is_locked is False
        
        # Try to receive again - should be None
        message2 = await backend_with_queue.receive_message("test-queue")
        assert message2 is None
    
    @pytest.mark.asyncio
    async def test_receive_from_empty_queue(self, backend_with_queue):
        """Test receiving from an empty queue."""
        message = await backend_with_queue.receive_message("test-queue")
        assert message is None
    
    @pytest.mark.asyncio
    async def test_receive_from_nonexistent_queue(self, backend):
        """Test receiving from a queue that doesn't exist."""
        with pytest.raises(QueueNotFoundError):
            await backend.receive_message("nonexistent-queue")
    
    @pytest.mark.asyncio
    async def test_receive_message_fifo_order(self, backend_with_queue):
        """Test that messages are received in FIFO order."""
        # Send 3 messages
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Message 1"))
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Message 2"))
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Message 3"))
        
        # Receive them
        msg1 = await backend_with_queue.receive_message("test-queue", ReceiveMode.RECEIVE_AND_DELETE)
        msg2 = await backend_with_queue.receive_message("test-queue", ReceiveMode.RECEIVE_AND_DELETE)
        msg3 = await backend_with_queue.receive_message("test-queue", ReceiveMode.RECEIVE_AND_DELETE)
        
        assert msg1.body == "Message 1"
        assert msg2.body == "Message 2"
        assert msg3.body == "Message 3"


class TestCompleteMessage:
    """Tests for completing messages."""
    
    @pytest.mark.asyncio
    async def test_complete_message_success(self, backend_with_queue):
        """Test completing a message successfully."""
        # Send and receive a message
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Test"))
        message = await backend_with_queue.receive_message("test-queue")
        
        # Complete it
        await backend_with_queue.complete_message("test-queue", message.message_id, message.lock_token)
        
        # Should not be able to receive it again
        msg2 = await backend_with_queue.receive_message("test-queue")
        assert msg2 is None
    
    @pytest.mark.asyncio
    async def test_complete_message_with_invalid_lock_token(self, backend_with_queue):
        """Test completing with invalid lock token."""
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Test"))
        message = await backend_with_queue.receive_message("test-queue")
        
        with pytest.raises(MessageLockLostError):
            await backend_with_queue.complete_message("test-queue", message.message_id, "invalid-token")
    
    @pytest.mark.asyncio
    async def test_complete_message_with_wrong_message_id(self, backend_with_queue):
        """Test completing with wrong message ID."""
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Test"))
        message = await backend_with_queue.receive_message("test-queue")
        
        with pytest.raises(MessageNotFoundError):
            await backend_with_queue.complete_message("test-queue", "wrong-id", message.lock_token)


class TestAbandonMessage:
    """Tests for abandoning messages."""
    
    @pytest.mark.asyncio
    async def test_abandon_message_success(self, backend_with_queue):
        """Test abandoning a message successfully."""
        # Send and receive a message
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Test"))
        message = await backend_with_queue.receive_message("test-queue")
        
        # Abandon it
        await backend_with_queue.abandon_message("test-queue", message.message_id, message.lock_token)
        
        # Should be able to receive it again
        msg2 = await backend_with_queue.receive_message("test-queue")
        assert msg2 is not None
        assert msg2.message_id == message.message_id
        assert msg2.delivery_count == 2
    
    @pytest.mark.asyncio
    async def test_abandon_message_max_delivery_count(self, backend_with_queue):
        """Test that messages move to DLQ after max delivery count."""
        # Send a message
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Test"))
        
        # Abandon it 10 times (max_delivery_count)
        for _ in range(10):
            message = await backend_with_queue.receive_message("test-queue")
            await backend_with_queue.abandon_message("test-queue", message.message_id, message.lock_token)
        
        # Should not be able to receive it again (moved to DLQ)
        msg = await backend_with_queue.receive_message("test-queue")
        assert msg is None
        
        # Check DLQ count
        queue = await backend_with_queue.get_queue("test-queue")
        assert queue.runtime_info.dead_letter_message_count == 1


class TestDeadLetterMessage:
    """Tests for dead-lettering messages."""
    
    @pytest.mark.asyncio
    async def test_dead_letter_message_success(self, backend_with_queue):
        """Test dead-lettering a message successfully."""
        # Send and receive a message
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Test"))
        message = await backend_with_queue.receive_message("test-queue")
        
        # Dead-letter it
        await backend_with_queue.dead_letter_message(
            "test-queue",
            message.message_id,
            message.lock_token,
            "ProcessingError",
            "Failed to process message",
        )
        
        # Should not be able to receive it again
        msg2 = await backend_with_queue.receive_message("test-queue")
        assert msg2 is None
        
        # Check DLQ count
        queue = await backend_with_queue.get_queue("test-queue")
        assert queue.runtime_info.dead_letter_message_count == 1
    
    @pytest.mark.asyncio
    async def test_dead_letter_message_with_invalid_lock_token(self, backend_with_queue):
        """Test dead-lettering with invalid lock token."""
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Test"))
        message = await backend_with_queue.receive_message("test-queue")
        
        with pytest.raises(MessageLockLostError):
            await backend_with_queue.dead_letter_message("test-queue", message.message_id, "invalid-token")


class TestRenewLock:
    """Tests for renewing message locks."""
    
    @pytest.mark.asyncio
    async def test_renew_lock_success(self, backend_with_queue):
        """Test renewing a lock successfully."""
        # Send and receive a message
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Test"))
        message = await backend_with_queue.receive_message("test-queue")
        
        original_locked_until = message.locked_until_utc
        
        # Wait a bit
        await asyncio.sleep(0.1)
        
        # Renew lock
        new_locked_until = await backend_with_queue.renew_lock("test-queue", message.message_id, message.lock_token)
        
        assert new_locked_until > original_locked_until
    
    @pytest.mark.asyncio
    async def test_renew_lock_with_invalid_token(self, backend_with_queue):
        """Test renewing with invalid lock token."""
        await backend_with_queue.send_message("test-queue", SendMessageRequest(body="Test"))
        message = await backend_with_queue.receive_message("test-queue")
        
        with pytest.raises(MessageLockLostError):
            await backend_with_queue.renew_lock("test-queue", message.message_id, "invalid-token")


class TestLockExpiration:
    """Tests for lock expiration handling."""
    
    @pytest.mark.asyncio
    async def test_expired_lock_returns_message_to_queue(self, backend):
        """Test that expired locks return messages to queue."""
        # Create queue with very short lock duration
        props = QueueProperties(
            max_size_in_megabytes=1024,
            default_message_time_to_live=1209600,
            lock_duration=5,  # 5 seconds (minimum)
            requires_session=False,
            requires_duplicate_detection=False,
            enable_dead_lettering_on_message_expiration=False,
            enable_batched_operations=True,
            max_delivery_count=10,
        )
        await backend.create_queue("test-queue", props)
        
        # Send and receive a message
        await backend.send_message("test-queue", SendMessageRequest(body="Test"))
        message = await backend.receive_message("test-queue")
        
        # Wait for lock to expire
        await asyncio.sleep(5.5)
        
        # Try to complete - should fail
        with pytest.raises(MessageLockLostError):
            await backend.complete_message("test-queue", message.message_id, message.lock_token)
        
        # Should be able to receive again
        msg2 = await backend.receive_message("test-queue")
        assert msg2 is not None
        assert msg2.message_id == message.message_id
        assert msg2.delivery_count == 2


class TestMessageModel:
    """Tests for the ServiceBusMessage model."""
    
    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        message = ServiceBusMessage(
            message_id="test-id",
            body="test body",
            label="test-label",
            content_type="text/plain",
        )
        
        d = message.model_dump(mode="json")
        
        assert d["message_id"] == "test-id"
        assert d["body"] == "test body"
        assert d["label"] == "test-label"
        assert d["content_type"] == "text/plain"
        assert "enqueued_time_utc" in d
    
    def test_message_defaults(self):
        """Test message default values."""
        message = ServiceBusMessage(body="test")
        
        assert message.message_id is not None
        assert message.sequence_number == 0
        assert message.delivery_count == 0
        assert message.is_locked is False
        assert message.is_dead_lettered is False
        assert message.lock_token is None
        assert message.user_properties == {}
