"""
Unit Tests for Service Bus Exceptions

Tests for custom exception hierarchy and error handling.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest
from localzure.services.servicebus.exceptions import (
    ServiceBusError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    InvalidEntityNameError,
    QueueNotFoundError,
    QueueAlreadyExistsError,
    InvalidQueueNameError,
    TopicNotFoundError,
    TopicAlreadyExistsError,
    SubscriptionNotFoundError,
    SubscriptionAlreadyExistsError,
    RuleNotFoundError,
    RuleAlreadyExistsError,
    MessageNotFoundError,
    MessageSizeExceededError,
    MessageLockLostError,
    SessionNotFoundError,
    SessionLockLostError,
    SessionAlreadyLockedError,
    QuotaExceededError,
    InvalidOperationError,
    TimeoutError,
    ServiceBusConnectionError,
    DeadLetterReason,
    is_transient_error,
)


class TestServiceBusError:
    """Tests for base ServiceBusError class."""
    
    def test_basic_error(self):
        """Test basic error creation."""
        error = ServiceBusError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.error_code == "ServiceBusError"
        assert error.details == {}
    
    def test_error_with_custom_code(self):
        """Test error with custom code."""
        error = ServiceBusError(
            "Custom error",
            error_code="CustomCode",
            details={"key": "value"}
        )
        assert error.error_code == "CustomCode"
        assert error.details == {"key": "value"}
    
    def test_to_dict(self):
        """Test converting error to dictionary."""
        error = ServiceBusError(
            "Test error",
            error_code="TestCode",
            details={"foo": "bar"}
        )
        error_dict = error.to_dict()
        
        assert error_dict == {
            "error": {
                "code": "TestCode",
                "message": "Test error",
                "details": {"foo": "bar"}
            }
        }


class TestEntityErrors:
    """Tests for entity-related errors."""
    
    def test_entity_not_found(self):
        """Test EntityNotFoundError."""
        error = EntityNotFoundError("queue", "myqueue")
        assert error.error_code == "EntityNotFound"
        assert "myqueue" in error.message
        assert "Queue" in error.message
        assert error.details["entity_type"] == "queue"
        assert error.details["entity_name"] == "myqueue"
    
    def test_entity_already_exists(self):
        """Test EntityAlreadyExistsError."""
        error = EntityAlreadyExistsError("topic", "mytopic")
        assert error.error_code == "EntityAlreadyExists"
        assert "mytopic" in error.message
        assert "Topic" in error.message
        assert error.details["entity_type"] == "topic"
        assert error.details["entity_name"] == "mytopic"
    
    def test_invalid_entity_name(self):
        """Test InvalidEntityNameError."""
        error = InvalidEntityNameError("queue", "bad name", "contains spaces")
        assert error.error_code == "InvalidEntityName"
        assert "bad name" in error.message
        assert "contains spaces" in error.message
        assert error.details["entity_type"] == "queue"
        assert error.details["entity_name"] == "bad name"
        assert error.details["reason"] == "contains spaces"
    
    def test_queue_not_found(self):
        """Test QueueNotFoundError."""
        error = QueueNotFoundError("testqueue")
        assert isinstance(error, EntityNotFoundError)
        assert error.error_code == "EntityNotFound"
        assert error.details["entity_type"] == "queue"
        assert error.details["entity_name"] == "testqueue"
    
    def test_queue_already_exists(self):
        """Test QueueAlreadyExistsError."""
        error = QueueAlreadyExistsError("testqueue")
        assert isinstance(error, EntityAlreadyExistsError)
        assert error.error_code == "EntityAlreadyExists"
        assert error.details["entity_type"] == "queue"
        assert error.details["entity_name"] == "testqueue"
    
    def test_invalid_queue_name(self):
        """Test InvalidQueueNameError."""
        error = InvalidQueueNameError("bad-queue", "invalid characters")
        assert isinstance(error, InvalidEntityNameError)
        assert error.error_code == "InvalidQueueName"
        assert error.details["entity_type"] == "queue"
        assert error.details["entity_name"] == "bad-queue"
        assert error.details["reason"] == "invalid characters"
    
    def test_topic_not_found(self):
        """Test TopicNotFoundError."""
        error = TopicNotFoundError("testtopic")
        assert isinstance(error, EntityNotFoundError)
        assert error.details["entity_type"] == "topic"
        assert error.details["entity_name"] == "testtopic"
    
    def test_subscription_not_found(self):
        """Test SubscriptionNotFoundError."""
        error = SubscriptionNotFoundError("mytopic", "mysub")
        assert isinstance(error, EntityNotFoundError)
        assert error.details["entity_type"] == "subscription"
        assert error.details["entity_name"] == "mysub"
        assert error.details["topic_name"] == "mytopic"
        assert "mytopic" in error.message
        assert "mysub" in error.message
    
    def test_rule_not_found(self):
        """Test RuleNotFoundError."""
        error = RuleNotFoundError("myrule", "mysub")
        assert isinstance(error, EntityNotFoundError)
        assert error.details["entity_type"] == "rule"
        assert error.details["entity_name"] == "myrule"
        assert error.details["subscription_name"] == "mysub"


class TestMessageErrors:
    """Tests for message-related errors."""
    
    def test_message_not_found(self):
        """Test MessageNotFoundError."""
        error = MessageNotFoundError("msg-123", "myqueue")
        assert error.error_code == "MessageNotFound"
        assert "msg-123" in error.message
        assert "myqueue" in error.message
        assert error.details["message_id"] == "msg-123"
        assert error.details["entity_name"] == "myqueue"
    
    def test_message_size_exceeded(self):
        """Test MessageSizeExceededError."""
        error = MessageSizeExceededError(2000, 1024)
        assert error.error_code == "MessageSizeExceeded"
        assert "2000" in error.message
        assert "1024" in error.message
        assert error.details["actual_size"] == 2000
        assert error.details["max_size"] == 1024
    
    def test_message_lock_lost(self):
        """Test MessageLockLostError."""
        error = MessageLockLostError("msg-123", "lock-token-abc")
        assert error.error_code == "MessageLockLost"
        assert "msg-123" in error.message
        assert error.details["message_id"] == "msg-123"
        assert error.details["lock_token"] == "lock-token-abc"


class TestSessionErrors:
    """Tests for session-related errors."""
    
    def test_session_not_found(self):
        """Test SessionNotFoundError."""
        error = SessionNotFoundError("session-1", "myqueue")
        assert error.error_code == "SessionNotFound"
        assert "session-1" in error.message
        assert "myqueue" in error.message
        assert error.details["session_id"] == "session-1"
        assert error.details["entity_name"] == "myqueue"
    
    def test_session_lock_lost(self):
        """Test SessionLockLostError."""
        error = SessionLockLostError("session-1", "myqueue")
        assert error.error_code == "SessionLockLost"
        assert "session-1" in error.message
        assert error.details["session_id"] == "session-1"
        assert error.details["entity_name"] == "myqueue"
    
    def test_session_already_locked(self):
        """Test SessionAlreadyLockedError."""
        error = SessionAlreadyLockedError("session-1", "myqueue")
        assert error.error_code == "SessionAlreadyLocked"
        assert "session-1" in error.message
        assert "already locked" in error.message.lower()
        assert error.details["session_id"] == "session-1"
        assert error.details["entity_name"] == "myqueue"


class TestQuotaAndResourceErrors:
    """Tests for quota and resource errors."""
    
    def test_quota_exceeded(self):
        """Test QuotaExceededError."""
        error = QuotaExceededError("message_count", 1000, 1000, "myqueue")
        assert error.error_code == "QuotaExceeded"
        assert "message_count" in error.message
        assert "1000" in error.message
        assert error.details["quota_type"] == "message_count"
        assert error.details["current_value"] == 1000
        assert error.details["max_value"] == 1000
        assert error.details["entity_name"] == "myqueue"
    
    def test_invalid_operation(self):
        """Test InvalidOperationError."""
        error = InvalidOperationError("complete_message", "message not locked")
        assert error.error_code == "InvalidOperation"
        assert "complete_message" in error.message
        assert "message not locked" in error.message
        assert error.details["operation"] == "complete_message"
        assert error.details["reason"] == "message not locked"


class TestTimeoutAndTransientErrors:
    """Tests for timeout and transient errors."""
    
    def test_timeout_error(self):
        """Test TimeoutError."""
        error = TimeoutError("send_message", 30.0)
        assert error.error_code == "OperationTimeout"
        assert "send_message" in error.message
        assert "30.0" in error.message
        assert error.details["operation"] == "send_message"
        assert error.details["timeout_seconds"] == 30.0
        assert hasattr(error, 'is_transient')
        assert error.is_transient is True
    
    def test_connection_error(self):
        """Test ServiceBusConnectionError."""
        error = ServiceBusConnectionError("Connection refused")
        assert error.error_code == "ConnectionError"
        assert "Connection refused" in error.message
        assert error.details["reason"] == "Connection refused"
        assert hasattr(error, 'is_transient')
        assert error.is_transient is True


class TestDeadLetterReason:
    """Tests for dead letter reasons."""
    
    def test_dead_letter_reasons(self):
        """Test all dead letter reason constants."""
        assert DeadLetterReason.MAX_DELIVERY_COUNT_EXCEEDED == "MaxDeliveryCountExceeded"
        assert DeadLetterReason.TTL_EXPIRED == "TTLExpired"
        assert DeadLetterReason.FILTER_EVALUATION_ERROR == "FilterEvaluationError"
        assert DeadLetterReason.LOCK_LOST == "LockLost"
        assert DeadLetterReason.PROCESSING_ERROR == "ProcessingError"
        assert DeadLetterReason.INVALID_MESSAGE_FORMAT == "InvalidMessageFormat"


class TestTransientErrorDetection:
    """Tests for is_transient_error function."""
    
    def test_transient_service_bus_errors(self):
        """Test transient ServiceBusError detection."""
        timeout_error = TimeoutError("op", 30.0)
        assert is_transient_error(timeout_error) is True
        
        connection_error = ServiceBusConnectionError("refused")
        assert is_transient_error(connection_error) is True
    
    def test_non_transient_service_bus_errors(self):
        """Test non-transient ServiceBusError detection."""
        not_found = QueueNotFoundError("queue")
        assert is_transient_error(not_found) is False
        
        already_exists = QueueAlreadyExistsError("queue")
        assert is_transient_error(already_exists) is False
        
        invalid_name = InvalidQueueNameError("bad", "reason")
        assert is_transient_error(invalid_name) is False
    
    def test_standard_transient_exceptions(self):
        """Test standard Python transient exceptions."""
        assert is_transient_error(ConnectionError("test")) is True
        assert is_transient_error(ConnectionRefusedError("test")) is True
        assert is_transient_error(ConnectionResetError("test")) is True
        assert is_transient_error(TimeoutError("test", 1.0)) is True
    
    def test_non_transient_standard_exceptions(self):
        """Test non-transient standard exceptions."""
        assert is_transient_error(ValueError("test")) is False
        assert is_transient_error(KeyError("test")) is False
        assert is_transient_error(RuntimeError("test")) is False


class TestExceptionInheritance:
    """Tests for exception inheritance hierarchy."""
    
    def test_all_inherit_from_service_bus_error(self):
        """Test that all custom exceptions inherit from ServiceBusError."""
        exceptions = [
            EntityNotFoundError("queue", "test"),
            QueueNotFoundError("test"),
            MessageNotFoundError("msg", "queue"),
            SessionNotFoundError("session", "queue"),
            QuotaExceededError("type", 1, 1),
            InvalidOperationError("op", "reason"),
            TimeoutError("op", 1.0),
        ]
        
        for exc in exceptions:
            assert isinstance(exc, ServiceBusError)
            assert isinstance(exc, Exception)
    
    def test_specific_exceptions_inherit_from_generic(self):
        """Test specific exceptions inherit from generic."""
        queue_error = QueueNotFoundError("test")
        assert isinstance(queue_error, EntityNotFoundError)
        assert isinstance(queue_error, ServiceBusError)
        
        topic_error = TopicAlreadyExistsError("test")
        assert isinstance(topic_error, EntityAlreadyExistsError)
        assert isinstance(topic_error, ServiceBusError)
