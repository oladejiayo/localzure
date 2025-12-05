"""
Service Bus Exception Hierarchy

Comprehensive exception types for Service Bus operations with error codes and context.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

from typing import Optional, Dict, Any


class ServiceBusError(Exception):
    """
    Base exception for all Service Bus errors.
    
    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code (e.g., 'EntityNotFound')
        details: Additional context (entity_type, entity_name, etc.)
    """
    
    error_code: str = "ServiceBusError"
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.error_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format for API responses."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }


# ========== Entity Errors ==========

class EntityError(ServiceBusError):
    """Base class for entity-related errors."""
    error_code = "EntityError"


class EntityNotFoundError(EntityError):
    """Raised when an entity (queue, topic, subscription) is not found."""
    error_code = "EntityNotFound"
    
    def __init__(
        self,
        entity_type: str,
        entity_name: str,
        message: Optional[str] = None
    ):
        message = message or f"{entity_type.capitalize()} '{entity_name}' not found"
        details = {"entity_type": entity_type, "entity_name": entity_name}
        super().__init__(message, details=details)


class EntityAlreadyExistsError(EntityError):
    """Raised when attempting to create an entity that already exists."""
    error_code = "EntityAlreadyExists"
    
    def __init__(
        self,
        entity_type: str,
        entity_name: str,
        message: Optional[str] = None
    ):
        message = message or f"{entity_type.capitalize()} '{entity_name}' already exists"
        details = {"entity_type": entity_type, "entity_name": entity_name}
        super().__init__(message, details=details)


class InvalidEntityNameError(EntityError):
    """Raised when entity name is invalid."""
    error_code = "InvalidEntityName"
    
    def __init__(
        self,
        entity_type: str,
        entity_name: str,
        reason: str,
        message: Optional[str] = None
    ):
        message = message or f"Invalid {entity_type} name '{entity_name}': {reason}"
        details = {
            "entity_type": entity_type,
            "entity_name": entity_name,
            "reason": reason
        }
        super().__init__(message, details=details)


# Specific entity errors (for backward compatibility)
class QueueNotFoundError(EntityNotFoundError):
    """Raised when queue is not found."""
    def __init__(self, queue_name: str, message: Optional[str] = None):
        super().__init__("queue", queue_name, message)


class QueueAlreadyExistsError(EntityAlreadyExistsError):
    """Raised when queue already exists."""
    def __init__(self, queue_name: str, message: Optional[str] = None):
        super().__init__("queue", queue_name, message)


class InvalidQueueNameError(InvalidEntityNameError):
    """Raised when queue name is invalid."""
    def __init__(self, queue_name: str, reason: str, message: Optional[str] = None):
        super().__init__("queue", queue_name, reason, message)


class TopicNotFoundError(EntityNotFoundError):
    """Raised when topic is not found."""
    def __init__(self, topic_name: str, message: Optional[str] = None):
        super().__init__("topic", topic_name, message)


class TopicAlreadyExistsError(EntityAlreadyExistsError):
    """Raised when topic already exists."""
    def __init__(self, topic_name: str, message: Optional[str] = None):
        super().__init__("topic", topic_name, message)


class SubscriptionNotFoundError(EntityNotFoundError):
    """Raised when subscription is not found."""
    def __init__(
        self,
        topic_name: str,
        subscription_name: str,
        message: Optional[str] = None
    ):
        message = message or f"Subscription '{subscription_name}' not found on topic '{topic_name}'"
        super().__init__("subscription", subscription_name, message)
        self.details["topic_name"] = topic_name


class SubscriptionAlreadyExistsError(EntityAlreadyExistsError):
    """Raised when subscription already exists."""
    def __init__(
        self,
        topic_name: str,
        subscription_name: str,
        message: Optional[str] = None
    ):
        message = message or f"Subscription '{subscription_name}' already exists on topic '{topic_name}'"
        super().__init__("subscription", subscription_name, message)
        self.details["topic_name"] = topic_name


class RuleNotFoundError(EntityNotFoundError):
    """Raised when rule is not found."""
    def __init__(
        self,
        rule_name: str,
        subscription_name: str,
        message: Optional[str] = None
    ):
        message = message or f"Rule '{rule_name}' not found on subscription '{subscription_name}'"
        super().__init__("rule", rule_name, message)
        self.details["subscription_name"] = subscription_name


class RuleAlreadyExistsError(EntityAlreadyExistsError):
    """Raised when rule already exists."""
    def __init__(
        self,
        rule_name: str,
        subscription_name: str,
        message: Optional[str] = None
    ):
        message = message or f"Rule '{rule_name}' already exists on subscription '{subscription_name}'"
        super().__init__("rule", rule_name, message)
        self.details["subscription_name"] = subscription_name


# ========== Message Errors ==========

class MessageError(ServiceBusError):
    """Base class for message-related errors."""
    error_code = "MessageError"


class MessageNotFoundError(MessageError):
    """Raised when a message is not found."""
    error_code = "MessageNotFound"
    
    def __init__(
        self,
        message_id: str,
        entity_name: str,
        message: Optional[str] = None
    ):
        message = message or f"Message '{message_id}' not found in '{entity_name}'"
        details = {"message_id": message_id, "entity_name": entity_name}
        super().__init__(message, details=details)


class MessageSizeExceededError(MessageError):
    """Raised when message size exceeds limits."""
    error_code = "MessageSizeExceeded"
    
    def __init__(
        self,
        actual_size: int,
        max_size: int,
        message: Optional[str] = None
    ):
        message = message or f"Message size {actual_size} bytes exceeds maximum {max_size} bytes"
        details = {"actual_size": actual_size, "max_size": max_size}
        super().__init__(message, details=details)


class MessageLockLostError(MessageError):
    """Raised when a message lock has expired or is invalid."""
    error_code = "MessageLockLost"
    
    def __init__(
        self,
        message_id: str,
        lock_token: Optional[str] = None,
        message: Optional[str] = None
    ):
        message = message or f"Message lock lost for message '{message_id}'"
        details = {"message_id": message_id}
        if lock_token:
            details["lock_token"] = lock_token
        super().__init__(message, details=details)


# ========== Session Errors ==========

class SessionError(ServiceBusError):
    """Base class for session-related errors."""
    error_code = "SessionError"


class SessionNotFoundError(SessionError):
    """Raised when session is not found."""
    error_code = "SessionNotFound"
    
    def __init__(
        self,
        session_id: str,
        entity_name: str,
        message: Optional[str] = None
    ):
        message = message or f"Session '{session_id}' not found in '{entity_name}'"
        details = {"session_id": session_id, "entity_name": entity_name}
        super().__init__(message, details=details)


class SessionLockLostError(SessionError):
    """Raised when a session lock has expired or is invalid."""
    error_code = "SessionLockLost"
    
    def __init__(
        self,
        session_id: str,
        entity_name: str,
        message: Optional[str] = None
    ):
        message = message or f"Session lock lost for session '{session_id}' in '{entity_name}'"
        details = {"session_id": session_id, "entity_name": entity_name}
        super().__init__(message, details=details)


class SessionAlreadyLockedError(SessionError):
    """Raised when attempting to acquire a session that is already locked."""
    error_code = "SessionAlreadyLocked"
    
    def __init__(
        self,
        session_id: str,
        entity_name: str,
        message: Optional[str] = None
    ):
        message = message or f"Session '{session_id}' in '{entity_name}' is already locked"
        details = {"session_id": session_id, "entity_name": entity_name}
        super().__init__(message, details=details)


# ========== Quota and Resource Errors ==========

class QuotaExceededError(ServiceBusError):
    """Raised when a quota is exceeded."""
    error_code = "QuotaExceeded"
    
    def __init__(
        self,
        quota_type: str,
        current_value: int,
        max_value: int,
        entity_name: Optional[str] = None,
        message: Optional[str] = None
    ):
        message = message or f"{quota_type} quota exceeded: {current_value}/{max_value}"
        details = {
            "quota_type": quota_type,
            "current_value": current_value,
            "max_value": max_value
        }
        if entity_name:
            details["entity_name"] = entity_name
        super().__init__(message, details=details)


class InvalidOperationError(ServiceBusError):
    """Raised when an operation is invalid in the current state."""
    error_code = "InvalidOperation"
    
    def __init__(
        self,
        operation: str,
        reason: str,
        message: Optional[str] = None
    ):
        message = message or f"Invalid operation '{operation}': {reason}"
        details = {"operation": operation, "reason": reason}
        super().__init__(message, details=details)


# ========== Timeout and Transient Errors ==========

class TimeoutError(ServiceBusError):
    """Raised when an operation times out."""
    error_code = "OperationTimeout"
    is_transient = True
    
    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        message: Optional[str] = None
    ):
        message = message or f"Operation '{operation}' timed out after {timeout_seconds}s"
        details = {"operation": operation, "timeout_seconds": timeout_seconds}
        super().__init__(message, details=details)


class ServiceBusConnectionError(ServiceBusError):
    """Raised when connection to Service Bus fails."""
    error_code = "ConnectionError"
    is_transient = True
    
    def __init__(
        self,
        reason: str,
        message: Optional[str] = None
    ):
        message = message or f"Connection error: {reason}"
        details = {"reason": reason}
        super().__init__(message, details=details)


# ========== Dead Letter Reasons ==========

class DeadLetterReason:
    """Standard dead letter reasons."""
    MAX_DELIVERY_COUNT_EXCEEDED = "MaxDeliveryCountExceeded"
    TTL_EXPIRED = "TTLExpired"
    FILTER_EVALUATION_ERROR = "FilterEvaluationError"
    LOCK_LOST = "LockLost"
    PROCESSING_ERROR = "ProcessingError"
    INVALID_MESSAGE_FORMAT = "InvalidMessageFormat"


# ========== Utility Functions ==========

def is_transient_error(error: Exception) -> bool:
    """
    Determine if an error is transient and can be retried.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is transient and operation should be retried
    """
    if isinstance(error, ServiceBusError):
        return getattr(error, 'is_transient', False)
    
    # Standard transient exceptions
    if isinstance(error, (
        ConnectionError,
        ConnectionRefusedError,
        ConnectionResetError,
        TimeoutError,
    )):
        return True
    
    return False
