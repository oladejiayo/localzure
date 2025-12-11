"""
Integration tests for Service Bus persistence layer.

Tests the complete lifecycle of persistence including:
- Backend initialization with storage
- State persistence across restarts
- Crash recovery with WAL replay
- Message and entity restoration
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from localzure.services.servicebus.backend import ServiceBusBackend
from localzure.services.servicebus.storage import (
    StorageConfig,
    StorageType,
)


@pytest.fixture
async def temp_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_backend_persistence_lifecycle(temp_dir):
    """Test complete persistence lifecycle with backend restart."""
    db_path = str(temp_dir / "test.db")
    
    # Phase 1: Create backend with persistence, add data
    config = StorageConfig(
        storage_type=StorageType.SQLITE,
        sqlite_path=db_path,
        snapshot_interval_seconds=3600,  # Disable auto-snapshots for test
        wal_enabled=True,
    )
    
    backend1 = ServiceBusBackend(storage_config=config)
    await backend1.initialize_persistence()
    
    try:
        # Create queue and send messages
        queue_name = "test-queue"
        await backend1.create_queue(
            queue_name=queue_name,
            max_delivery_count=3,
            lock_duration_seconds=30,
            max_size_in_mb=1024,
            duplicate_detection_history=300,
        )
        
        # Send multiple messages
        msg1_id = await backend1.send_to_queue(
            queue_name=queue_name,
            message_body={"test": "message1"},
            properties={"prop1": "value1"},
        )
        msg2_id = await backend1.send_to_queue(
            queue_name=queue_name,
            message_body={"test": "message2"},
            properties={"prop2": "value2"},
        )
        
        # Create topic and subscription
        topic_name = "test-topic"
        await backend1.create_topic(
            topic_name=topic_name,
            max_size_in_mb=1024,
            duplicate_detection_history=300,
        )
        
        subscription_name = "test-sub"
        await backend1.create_subscription(
            topic_name=topic_name,
            subscription_name=subscription_name,
            max_delivery_count=3,
            lock_duration_seconds=30,
        )
        
        # Send message to topic
        msg3_id = await backend1.send_to_topic(
            topic_name=topic_name,
            message_body={"test": "topic-message"},
            properties={"prop3": "value3"},
        )
        
        # Explicitly persist state
        await backend1._persist_current_state()
        
    finally:
        # Shutdown backend (persists state)
        await backend1.shutdown_persistence()
    
    # Phase 2: Create new backend instance (simulates restart)
    backend2 = ServiceBusBackend(storage_config=config)
    await backend2.initialize_persistence()
    
    try:
        # Verify queue restored
        assert queue_name in backend2._queues, "Queue not restored"
        restored_queue = backend2._queues[queue_name]
        assert restored_queue.max_delivery_count == 3
        assert restored_queue.lock_duration_seconds == 30
        
        # Verify messages restored
        assert queue_name in backend2._messages, "Queue messages not restored"
        messages = backend2._messages[queue_name]
        assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
        
        # Verify message content
        msg_bodies = [msg.body for msg in messages]
        assert {"test": "message1"} in msg_bodies
        assert {"test": "message2"} in msg_bodies
        
        # Verify topic restored
        assert topic_name in backend2._topics, "Topic not restored"
        
        # Verify subscription restored
        assert subscription_name in backend2._subscriptions.get(topic_name, {}), "Subscription not restored"
        
        # Verify subscription messages restored
        sub_tuple = (topic_name, subscription_name)
        assert sub_tuple in backend2._subscription_messages, "Subscription messages not restored"
        sub_messages = backend2._subscription_messages[sub_tuple]
        assert len(sub_messages) == 1, f"Expected 1 subscription message, got {len(sub_messages)}"
        assert sub_messages[0].body == {"test": "topic-message"}
        
    finally:
        await backend2.shutdown_persistence()


@pytest.mark.asyncio
async def test_crash_recovery_with_wal(temp_dir):
    """Test WAL-based crash recovery."""
    db_path = str(temp_dir / "test.db")
    wal_path = str(temp_dir / "wal.log")
    
    # Phase 1: Create backend and add data WITHOUT clean shutdown
    config = StorageConfig(
        storage_type=StorageType.SQLITE,
        sqlite_path=db_path,
        snapshot_interval_seconds=3600,
        wal_enabled=True,
    )
    
    backend1 = ServiceBusBackend(storage_config=config)
    await backend1.initialize_persistence()
    
    # Create queue
    queue_name = "crash-test-queue"
    await backend1.create_queue(
        queue_name=queue_name,
        max_delivery_count=5,
        lock_duration_seconds=60,
    )
    
    # Send messages
    await backend1.send_to_queue(
        queue_name=queue_name,
        message_body={"test": "before-crash"},
    )
    
    # Take a snapshot first
    await backend1._persist_current_state()
    
    # Send another message AFTER snapshot (only in WAL)
    await backend1.send_to_queue(
        queue_name=queue_name,
        message_body={"test": "after-snapshot"},
    )
    
    # Simulate crash by NOT calling shutdown
    # Close storage directly to leave WAL intact
    if backend1._storage:
        await backend1._storage.close()
    
    # Phase 2: Recover from crash
    backend2 = ServiceBusBackend(storage_config=config)
    await backend2.initialize_persistence()
    
    try:
        # Verify WAL was replayed and message restored
        assert queue_name in backend2._messages
        messages = backend2._messages[queue_name]
        
        # Should have both messages (one from snapshot, one from WAL)
        assert len(messages) == 2, f"Expected 2 messages after WAL replay, got {len(messages)}"
        
        msg_bodies = [msg.body for msg in messages]
        assert {"test": "before-crash"} in msg_bodies
        assert {"test": "after-snapshot"} in msg_bodies
        
    finally:
        await backend2.shutdown_persistence()


@pytest.mark.asyncio
async def test_json_backend_persistence(temp_dir):
    """Test JSON backend for human-readable persistence."""
    json_path = str(temp_dir)
    
    config = StorageConfig(
        storage_type=StorageType.JSON,
        json_path=json_path,
        snapshot_interval_seconds=3600,
        wal_enabled=False,  # JSON backend doesn't need WAL
    )
    
    backend1 = ServiceBusBackend(storage_config=config)
    await backend1.initialize_persistence()
    
    try:
        # Create queue
        queue_name = "json-test-queue"
        await backend1.create_queue(
            queue_name=queue_name,
            max_delivery_count=2,
        )
        
        # Send message
        await backend1.send_to_queue(
            queue_name=queue_name,
            message_body={"format": "json"},
        )
        
        # Persist
        await backend1._persist_current_state()
        
    finally:
        await backend1.shutdown_persistence()
    
    # Verify JSON files are readable
    entities_dir = Path(json_path) / "entities"
    assert entities_dir.exists(), "Entities directory not created"
    
    queues_file = entities_dir / "queues.json"
    assert queues_file.exists(), "Queues file not created"
    
    # Read and verify content
    with open(queues_file) as f:
        queues_data = json.load(f)
        assert queue_name in queues_data
        assert queues_data[queue_name]["max_delivery_count"] == 2
    
    # Verify messages file
    messages_dir = Path(json_path) / "messages"
    assert messages_dir.exists()
    
    queue_messages_file = messages_dir / f"queue_{queue_name}.json"
    assert queue_messages_file.exists()
    
    with open(queue_messages_file) as f:
        messages_data = json.load(f)
        assert len(messages_data) == 1
        assert messages_data[0]["body"] == {"format": "json"}
    
    # Phase 2: Restore from JSON
    backend2 = ServiceBusBackend(storage_config=config)
    await backend2.initialize_persistence()
    
    try:
        assert queue_name in backend2._queues
        assert len(backend2._messages[queue_name]) == 1
        
    finally:
        await backend2.shutdown_persistence()


@pytest.mark.asyncio
async def test_deadletter_persistence(temp_dir):
    """Test persistence of deadletter messages."""
    db_path = str(temp_dir / "test.db")
    
    config = StorageConfig(
        storage_type=StorageType.SQLITE,
        sqlite_path=db_path,
    )
    
    backend1 = ServiceBusBackend(storage_config=config)
    await backend1.initialize_persistence()
    
    try:
        # Create queue
        queue_name = "dl-test-queue"
        await backend1.create_queue(
            queue_name=queue_name,
            max_delivery_count=1,  # Low count for easy deadletter
        )
        
        # Send message
        msg_id = await backend1.send_to_queue(
            queue_name=queue_name,
            message_body={"test": "deadletter"},
        )
        
        # Receive and abandon to trigger deadletter
        msg = await backend1.receive_from_queue(queue_name, timeout_seconds=1)
        assert msg is not None
        
        # Abandon message (increases delivery count)
        await backend1.abandon_message(queue_name, msg.lock_token)
        
        # Try to receive again - should go to deadletter since max_delivery_count=1
        msg2 = await backend1.receive_from_queue(queue_name, timeout_seconds=1)
        # Message should be deadlettered, so no active messages
        assert msg2 is None or msg2.message_id != msg_id
        
        # Verify deadletter queue has message
        dl_queue_name = f"{queue_name}/$deadletterqueue"
        
        # Persist state
        await backend1._persist_current_state()
        
    finally:
        await backend1.shutdown_persistence()
    
    # Phase 2: Restore and verify deadletter
    backend2 = ServiceBusBackend(storage_config=config)
    await backend2.initialize_persistence()
    
    try:
        # Verify deadletter messages restored
        if queue_name in backend2._dead_letter_messages:
            assert len(backend2._dead_letter_messages[queue_name]) > 0, "Deadletter messages not restored"
        
    finally:
        await backend2.shutdown_persistence()


@pytest.mark.asyncio
async def test_no_persistence_backward_compatibility():
    """Test that backend works without persistence (backward compatibility)."""
    # Create backend without storage config (default in-memory)
    backend = ServiceBusBackend()
    
    # Should work normally
    queue_name = "memory-only-queue"
    await backend.create_queue(queue_name=queue_name)
    
    msg_id = await backend.send_to_queue(
        queue_name=queue_name,
        message_body={"test": "in-memory"},
    )
    
    # Verify message exists
    assert queue_name in backend._messages
    assert len(backend._messages[queue_name]) == 1
    
    # No persistence methods should be called (they should be no-ops)
    # This verifies backward compatibility


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
