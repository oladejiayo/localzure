"""
Unit tests for Queue Storage models.

Tests queue models, validators, and Pydantic validation.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from pydantic import ValidationError

from localzure.services.queue.models import (
    Queue,
    QueueMetadata,
    QueueProperties,
    QueueNameValidator,
    CreateQueueRequest,
    SetQueueMetadataRequest,
)


class TestQueueNameValidator:
    """Test queue name validation rules."""
    
    def test_valid_queue_names(self):
        """Test valid queue names."""
        valid_names = [
            "abc",  # Minimum length
            "my-queue",
            "queue123",
            "a-b-c-d-e",
            "queue-with-numbers-123",
            "a" * 63,  # Maximum length
        ]
        
        for name in valid_names:
            is_valid, error = QueueNameValidator.validate(name)
            assert is_valid, f"'{name}' should be valid, got error: {error}"
            assert error is None
    
    def test_invalid_queue_names_too_short(self):
        """Test queue names that are too short."""
        is_valid, error = QueueNameValidator.validate("ab")
        assert not is_valid
        assert "at least 3 characters" in error
    
    def test_invalid_queue_names_too_long(self):
        """Test queue names that are too long."""
        is_valid, error = QueueNameValidator.validate("a" * 64)
        assert not is_valid
        assert "at most 63 characters" in error
    
    def test_invalid_queue_names_uppercase(self):
        """Test queue names with uppercase letters."""
        is_valid, error = QueueNameValidator.validate("MyQueue")
        assert not is_valid
        assert "lowercase" in error.lower()
    
    def test_invalid_queue_names_special_chars(self):
        """Test queue names with special characters."""
        invalid_names = ["queue_name", "queue.name", "queue@name", "queue name"]
        
        for name in invalid_names:
            is_valid, error = QueueNameValidator.validate(name)
            assert not is_valid, f"'{name}' should be invalid"
            assert "lowercase letters, numbers, and hyphens" in error
    
    def test_invalid_queue_names_start_with_number(self):
        """Test queue names starting with number."""
        is_valid, error = QueueNameValidator.validate("123queue")
        assert not is_valid
        assert "start with a lowercase letter" in error
    
    def test_invalid_queue_names_start_with_hyphen(self):
        """Test queue names starting with hyphen."""
        is_valid, error = QueueNameValidator.validate("-queue")
        assert not is_valid
        assert "start with a lowercase letter" in error
    
    def test_invalid_queue_names_end_with_hyphen(self):
        """Test queue names ending with hyphen."""
        is_valid, error = QueueNameValidator.validate("queue-")
        assert not is_valid
    
    def test_invalid_queue_names_consecutive_hyphens(self):
        """Test queue names with consecutive hyphens."""
        is_valid, error = QueueNameValidator.validate("my--queue")
        assert not is_valid
        assert "consecutive hyphens" in error


class TestQueueMetadata:
    """Test QueueMetadata model."""
    
    def test_empty_metadata(self):
        """Test creating metadata with no entries."""
        metadata = QueueMetadata()
        assert metadata.metadata == {}
    
    def test_metadata_with_values(self):
        """Test creating metadata with values."""
        data = {"key1": "value1", "key2": "value2"}
        metadata = QueueMetadata(metadata=data)
        assert metadata.metadata == data
    
    def test_metadata_to_headers(self):
        """Test converting metadata to HTTP headers."""
        metadata = QueueMetadata(metadata={"key1": "value1", "key2": "value2"})
        headers = metadata.to_headers()
        
        assert headers == {
            "x-ms-meta-key1": "value1",
            "x-ms-meta-key2": "value2",
        }
    
    def test_invalid_metadata_key(self):
        """Test that invalid metadata keys are rejected."""
        with pytest.raises(ValidationError):
            QueueMetadata(metadata={"": "value"})


class TestQueueProperties:
    """Test QueueProperties model."""
    
    def test_default_properties(self):
        """Test default property values."""
        props = QueueProperties()
        assert props.approximate_message_count == 0
    
    def test_properties_with_values(self):
        """Test creating properties with specific values."""
        props = QueueProperties(approximate_message_count=42)
        assert props.approximate_message_count == 42
    
    def test_properties_to_headers(self):
        """Test converting properties to HTTP headers."""
        props = QueueProperties(approximate_message_count=10)
        headers = props.to_headers()
        
        assert headers == {
            "x-ms-approximate-messages-count": "10",
        }
    
    def test_negative_message_count(self):
        """Test that negative message count is rejected."""
        with pytest.raises(ValidationError):
            QueueProperties(approximate_message_count=-1)


class TestQueue:
    """Test Queue model."""
    
    def test_create_queue_minimal(self):
        """Test creating a queue with minimal parameters."""
        queue = Queue(name="myqueue")
        assert queue.name == "myqueue"
        assert queue.metadata.metadata == {}
        assert queue.properties.approximate_message_count == 0
        assert queue.created_time is not None
    
    def test_create_queue_with_metadata(self):
        """Test creating a queue with metadata."""
        metadata = QueueMetadata(metadata={"key": "value"})
        queue = Queue(name="myqueue", metadata=metadata)
        assert queue.metadata.metadata == {"key": "value"}
    
    def test_create_queue_invalid_name(self):
        """Test that invalid queue names are rejected."""
        with pytest.raises(ValidationError):
            Queue(name="InvalidQueue")
    
    def test_queue_to_dict(self):
        """Test converting queue to dictionary."""
        metadata = QueueMetadata(metadata={"key": "value"})
        queue = Queue(name="myqueue", metadata=metadata)
        
        queue_dict = queue.to_dict()
        assert queue_dict["Name"] == "myqueue"
        assert queue_dict["Metadata"] == {"key": "value"}
    
    def test_queue_to_dict_no_metadata(self):
        """Test converting queue with no metadata to dictionary."""
        queue = Queue(name="myqueue")
        queue_dict = queue.to_dict()
        
        assert queue_dict["Name"] == "myqueue"
        assert queue_dict["Metadata"] is None


class TestCreateQueueRequest:
    """Test CreateQueueRequest model."""
    
    def test_empty_request(self):
        """Test creating request with no metadata."""
        request = CreateQueueRequest()
        assert request.metadata == {}
    
    def test_request_with_metadata(self):
        """Test creating request with metadata."""
        request = CreateQueueRequest(metadata={"key": "value"})
        assert request.metadata == {"key": "value"}


class TestSetQueueMetadataRequest:
    """Test SetQueueMetadataRequest model."""
    
    def test_empty_request(self):
        """Test creating request with no metadata."""
        request = SetQueueMetadataRequest()
        assert request.metadata == {}
    
    def test_request_with_metadata(self):
        """Test creating request with metadata."""
        request = SetQueueMetadataRequest(metadata={"key": "value"})
        assert request.metadata == {"key": "value"}
