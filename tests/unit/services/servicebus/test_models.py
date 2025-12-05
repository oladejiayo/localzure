"""
Unit tests for Service Bus models.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest
from pydantic import ValidationError

from localzure.services.servicebus.models import (
    QueueNameValidator,
    QueueProperties,
    QueueRuntimeInfo,
    QueueDescription,
)


class TestQueueNameValidator:
    """Test queue name validation rules."""
    
    def test_valid_names(self):
        """Test valid queue names."""
        valid_names = [
            "myqueue",
            "my-queue",
            "my_queue",
            "my.queue",
            "queue123",
            "123queue",
            "a" * 260,  # Max length
            "My-Queue_123.test",
        ]
        
        for name in valid_names:
            is_valid, error = QueueNameValidator.validate(name)
            assert is_valid, f"Expected '{name}' to be valid, got error: {error}"
            assert error is None
    
    def test_invalid_empty_name(self):
        """Test empty queue name is invalid."""
        is_valid, error = QueueNameValidator.validate("")
        assert not is_valid
        assert "cannot be empty" in error
    
    def test_invalid_too_short(self):
        """Test queue name too short."""
        # Actually minimum is 1, so this shouldn't fail
        is_valid, error = QueueNameValidator.validate("a")
        assert is_valid  # 1 character is valid
    
    def test_invalid_too_long(self):
        """Test queue name too long."""
        name = "a" * 261
        is_valid, error = QueueNameValidator.validate(name)
        assert not is_valid
        assert "1-260 characters" in error
    
    def test_invalid_start_with_special_char(self):
        """Test queue name starting with special character."""
        invalid_names = ["-queue", "_queue", ".queue"]
        
        for name in invalid_names:
            is_valid, error = QueueNameValidator.validate(name)
            assert not is_valid
            assert "start with alphanumeric" in error
    
    def test_invalid_end_with_special_char(self):
        """Test queue name ending with special character."""
        invalid_names = ["queue-", "queue_", "queue."]
        
        for name in invalid_names:
            is_valid, error = QueueNameValidator.validate(name)
            assert not is_valid
            assert "end with alphanumeric" in error
    
    def test_invalid_characters(self):
        """Test queue name with invalid characters."""
        invalid_names = ["queue@test", "queue#123", "queue space"]
        
        for name in invalid_names:
            is_valid, error = QueueNameValidator.validate(name)
            assert not is_valid
            assert "alphanumeric, hyphens, underscores, and periods" in error
    
    def test_consecutive_special_chars(self):
        """Test queue name with consecutive special characters."""
        invalid_names = ["queue--test", "queue__test", "queue..test"]
        
        for name in invalid_names:
            is_valid, error = QueueNameValidator.validate(name)
            assert not is_valid
            assert "consecutive" in error


class TestQueueProperties:
    """Test queue properties model."""
    
    def test_default_properties(self):
        """Test default queue properties."""
        props = QueueProperties()
        
        assert props.max_size_in_megabytes == 1024
        assert props.default_message_time_to_live == 1209600  # 14 days
        assert props.lock_duration == 60
        assert props.requires_session is False
        assert props.requires_duplicate_detection is False
        assert props.enable_dead_lettering_on_message_expiration is False
        assert props.enable_batched_operations is True
        assert props.max_delivery_count == 10
    
    def test_custom_properties(self):
        """Test custom queue properties."""
        props = QueueProperties(
            max_size_in_megabytes=5120,
            default_message_time_to_live=3600,
            lock_duration=300,
            requires_session=True,
            requires_duplicate_detection=True,
            enable_dead_lettering_on_message_expiration=True,
            enable_batched_operations=False,
            max_delivery_count=5,
        )
        
        assert props.max_size_in_megabytes == 5120
        assert props.default_message_time_to_live == 3600
        assert props.lock_duration == 300
        assert props.requires_session is True
        assert props.requires_duplicate_detection is True
        assert props.enable_dead_lettering_on_message_expiration is True
        assert props.enable_batched_operations is False
        assert props.max_delivery_count == 5
    
    def test_invalid_max_size(self):
        """Test invalid max size values."""
        with pytest.raises(ValidationError):
            QueueProperties(max_size_in_megabytes=512)  # Too small
        
        with pytest.raises(ValidationError):
            QueueProperties(max_size_in_megabytes=10000)  # Too large
    
    def test_invalid_lock_duration(self):
        """Test invalid lock duration values."""
        with pytest.raises(ValidationError):
            QueueProperties(lock_duration=3)  # Too small
        
        with pytest.raises(ValidationError):
            QueueProperties(lock_duration=400)  # Too large
    
    def test_invalid_ttl(self):
        """Test invalid TTL value."""
        with pytest.raises(ValidationError):
            QueueProperties(default_message_time_to_live=999999999999)  # Too large
    
    def test_invalid_max_delivery_count(self):
        """Test invalid max delivery count."""
        with pytest.raises(ValidationError):
            QueueProperties(max_delivery_count=0)  # Too small
        
        with pytest.raises(ValidationError):
            QueueProperties(max_delivery_count=3000)  # Too large


class TestQueueRuntimeInfo:
    """Test queue runtime information model."""
    
    def test_default_runtime_info(self):
        """Test default runtime info."""
        info = QueueRuntimeInfo()
        
        assert info.message_count == 0
        assert info.active_message_count == 0
        assert info.dead_letter_message_count == 0
        assert info.scheduled_message_count == 0
        assert info.transfer_message_count == 0
        assert info.transfer_dead_letter_message_count == 0
        assert info.size_in_bytes == 0
    
    def test_custom_runtime_info(self):
        """Test custom runtime info."""
        info = QueueRuntimeInfo(
            message_count=100,
            active_message_count=80,
            dead_letter_message_count=10,
            scheduled_message_count=5,
            size_in_bytes=1024000,
        )
        
        assert info.message_count == 100
        assert info.active_message_count == 80
        assert info.dead_letter_message_count == 10
        assert info.scheduled_message_count == 5
        assert info.size_in_bytes == 1024000
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        info = QueueRuntimeInfo(
            message_count=50,
            active_message_count=40,
            dead_letter_message_count=5,
        )
        
        result = info.to_dict()
        
        assert result["MessageCount"] == 50
        assert result["ActiveMessageCount"] == 40
        assert result["DeadLetterMessageCount"] == 5
        assert "SizeInBytes" in result


class TestQueueDescription:
    """Test queue description model."""
    
    def test_default_queue(self):
        """Test default queue description."""
        queue = QueueDescription(name="test-queue")
        
        assert queue.name == "test-queue"
        assert isinstance(queue.properties, QueueProperties)
        assert isinstance(queue.runtime_info, QueueRuntimeInfo)
        assert queue.created_at is not None
        assert queue.updated_at is not None
    
    def test_custom_queue(self):
        """Test custom queue description."""
        props = QueueProperties(max_size_in_megabytes=2048)
        runtime = QueueRuntimeInfo(message_count=10)
        
        queue = QueueDescription(
            name="custom-queue",
            properties=props,
            runtime_info=runtime,
        )
        
        assert queue.name == "custom-queue"
        assert queue.properties.max_size_in_megabytes == 2048
        assert queue.runtime_info.message_count == 10
    
    def test_invalid_name_validation(self):
        """Test invalid queue name raises validation error."""
        with pytest.raises(ValidationError):
            QueueDescription(name="-invalid")
        
        with pytest.raises(ValidationError):
            QueueDescription(name="invalid--name")
        
        with pytest.raises(ValidationError):
            QueueDescription(name="")
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        queue = QueueDescription(name="test-queue")
        result = queue.to_dict()
        
        assert result["QueueName"] == "test-queue"
        assert result["MaxSizeInMegabytes"] == 1024
        assert "DefaultMessageTimeToLive" in result
        assert "LockDuration" in result
        assert result["MessageCount"] == 0
        assert "CreatedAt" in result
