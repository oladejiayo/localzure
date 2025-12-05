"""
Unit tests for Queue Storage message models.

Tests message creation, validation, base64 encoding, visibility logic.

Author: Ayodele Oladeji
Date: 2025
"""

import base64
import pytest
from datetime import datetime, timezone, timedelta

from localzure.services.queue.models import (
    Message,
    PutMessageRequest,
    UpdateMessageRequest,
)


class TestMessage:
    """Tests for Message model."""
    
    def test_create_message_basic(self):
        """Test creating a basic message."""
        text = "Hello, World!"
        message = Message.create(text)
        
        assert message.message_id is not None
        assert message.insertion_time <= datetime.now(timezone.utc)
        assert message.expiration_time > message.insertion_time
        assert message.pop_receipt is not None
        assert message.time_next_visible <= datetime.now(timezone.utc)
        assert message.dequeue_count == 0
        # Text should be base64-encoded
        decoded = base64.b64decode(message.message_text).decode('utf-8')
        assert decoded == text
    
    def test_create_message_with_visibility_timeout(self):
        """Test creating message with visibility timeout."""
        text = "Test"
        visibility_timeout = 60
        message = Message.create(text, visibility_timeout=visibility_timeout)
        
        assert message.time_next_visible > datetime.now(timezone.utc)
        # Should be roughly visibility_timeout seconds in future
        delta = (message.time_next_visible - message.insertion_time).total_seconds()
        assert abs(delta - visibility_timeout) < 1  # Within 1 second
    
    def test_create_message_with_ttl(self):
        """Test creating message with custom TTL."""
        text = "Test"
        message_ttl = 3600  # 1 hour
        message = Message.create(text, message_ttl=message_ttl)
        
        delta = (message.expiration_time - message.insertion_time).total_seconds()
        assert abs(delta - message_ttl) < 1  # Within 1 second
    
    def test_create_message_already_base64(self):
        """Test creating message with already base64-encoded text."""
        original = "Hello"
        encoded = base64.b64encode(original.encode('utf-8')).decode('utf-8')
        message = Message.create(encoded)
        
        # Should detect it's already base64 and not double-encode
        assert message.message_text == encoded
    
    def test_update_visibility(self):
        """Test updating message visibility."""
        message = Message.create("Test")
        old_pop_receipt = message.pop_receipt
        old_time = message.time_next_visible
        
        new_receipt = message.update_visibility(30)
        
        assert new_receipt != old_pop_receipt
        assert message.pop_receipt == new_receipt
        assert message.time_next_visible > old_time
    
    def test_update_visibility_with_new_text(self):
        """Test updating both visibility and message text."""
        message = Message.create("Original")
        new_text = base64.b64encode("Updated".encode('utf-8')).decode('utf-8')
        
        message.update_visibility(30, new_text)
        
        assert message.message_text == new_text
    
    def test_is_visible_initially(self):
        """Test message is visible when visibility timeout is 0."""
        message = Message.create("Test", visibility_timeout=0)
        assert message.is_visible()
    
    def test_is_not_visible_with_timeout(self):
        """Test message is not visible with future timeout."""
        message = Message.create("Test", visibility_timeout=3600)
        assert not message.is_visible()
    
    def test_is_expired(self):
        """Test message expiration check."""
        message = Message.create("Test", message_ttl=1)
        assert not message.is_expired()
        
        # Manually set expiration to past
        message.expiration_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert message.is_expired()
    
    def test_to_dict_with_pop_receipt(self):
        """Test converting message to dict with pop receipt."""
        message = Message.create("Test")
        result = message.to_dict(include_pop_receipt=True)
        
        assert "MessageId" in result
        assert "InsertionTime" in result
        assert "ExpirationTime" in result
        assert "PopReceipt" in result
        assert "TimeNextVisible" in result
        assert "DequeueCount" in result
        assert "MessageText" in result
    
    def test_to_dict_without_pop_receipt(self):
        """Test converting message to dict without pop receipt (peek)."""
        message = Message.create("Test")
        result = message.to_dict(include_pop_receipt=False)
        
        assert "MessageId" in result
        assert "InsertionTime" in result
        assert "ExpirationTime" in result
        assert "PopReceipt" not in result
        assert "TimeNextVisible" not in result
        assert "DequeueCount" in result
        assert "MessageText" in result
    
    def test_message_id_unique(self):
        """Test that each message gets a unique ID."""
        msg1 = Message.create("Test1")
        msg2 = Message.create("Test2")
        assert msg1.message_id != msg2.message_id
    
    def test_pop_receipt_unique(self):
        """Test that each message gets a unique pop receipt."""
        msg1 = Message.create("Test1")
        msg2 = Message.create("Test2")
        assert msg1.pop_receipt != msg2.pop_receipt


class TestPutMessageRequest:
    """Tests for PutMessageRequest model."""
    
    def test_put_message_request_defaults(self):
        """Test default values for put message request."""
        request = PutMessageRequest(message_text="Test")
        assert request.message_text == "Test"
        assert request.visibility_timeout == 0
        assert request.message_ttl == 604800  # 7 days
    
    def test_put_message_request_custom_values(self):
        """Test custom values for put message request."""
        request = PutMessageRequest(
            message_text="Test",
            visibility_timeout=60,
            message_ttl=3600,
        )
        assert request.message_text == "Test"
        assert request.visibility_timeout == 60
        assert request.message_ttl == 3600
    
    def test_put_message_request_validates_visibility_timeout(self):
        """Test validation of visibility timeout bounds."""
        # Valid range: 0 to 604800
        with pytest.raises(Exception):
            PutMessageRequest(message_text="Test", visibility_timeout=-1)
        
        with pytest.raises(Exception):
            PutMessageRequest(message_text="Test", visibility_timeout=604801)
    
    def test_put_message_request_validates_ttl(self):
        """Test validation of message TTL bounds."""
        # Valid range: 1 to 604800
        with pytest.raises(Exception):
            PutMessageRequest(message_text="Test", message_ttl=0)
        
        with pytest.raises(Exception):
            PutMessageRequest(message_text="Test", message_ttl=604801)


class TestUpdateMessageRequest:
    """Tests for UpdateMessageRequest model."""
    
    def test_update_message_request_visibility_only(self):
        """Test update request with only visibility timeout."""
        request = UpdateMessageRequest(visibility_timeout=30)
        assert request.visibility_timeout == 30
        assert request.message_text is None
    
    def test_update_message_request_with_text(self):
        """Test update request with new message text."""
        request = UpdateMessageRequest(
            visibility_timeout=30,
            message_text="Updated",
        )
        assert request.visibility_timeout == 30
        assert request.message_text == "Updated"
    
    def test_update_message_request_requires_visibility_timeout(self):
        """Test that visibility timeout is required."""
        with pytest.raises(Exception):
            UpdateMessageRequest()
    
    def test_update_message_request_validates_visibility_timeout(self):
        """Test validation of visibility timeout bounds."""
        with pytest.raises(Exception):
            UpdateMessageRequest(visibility_timeout=-1)
        
        with pytest.raises(Exception):
            UpdateMessageRequest(visibility_timeout=604801)
