"""
Service Bus Models

Pydantic models for Azure Service Bus queue management.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueueNameValidator:
    """
    Validates Service Bus queue names according to Azure rules:
    - 1-260 characters
    - Alphanumeric characters, hyphens (-), underscores (_), and periods (.)
    - Must start and end with alphanumeric character
    - No consecutive hyphens, underscores, or periods
    """
    
    @staticmethod
    def validate(name: str) -> tuple[bool, Optional[str]]:
        """
        Validate queue name.
        
        Args:
            name: Queue name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name:
            return False, "Queue name cannot be empty"
        
        if len(name) < 1 or len(name) > 260:
            return False, f"Queue name must be 1-260 characters, got {len(name)}"
        
        # Must start and end with alphanumeric
        if not name[0].isalnum():
            return False, "Queue name must start with alphanumeric character"
        
        if not name[-1].isalnum():
            return False, "Queue name must end with alphanumeric character"
        
        # Check for invalid characters (only alphanumeric, hyphen, underscore, period allowed)
        if not re.match(r'^[a-zA-Z0-9\-_.]+$', name):
            return False, "Queue name can only contain alphanumeric, hyphens, underscores, and periods"
        
        # Check for consecutive special characters
        if '--' in name or '__' in name or '..' in name:
            return False, "Queue name cannot contain consecutive hyphens, underscores, or periods"
        
        return True, None


class QueueProperties(BaseModel):
    """Queue properties model for Service Bus queues."""
    model_config = ConfigDict(extra='forbid')
    
    max_size_in_megabytes: int = Field(default=1024, ge=1024, le=5120)
    default_message_time_to_live: int = Field(default=1209600)  # 14 days in seconds
    lock_duration: int = Field(default=60, ge=5, le=300)  # 5 seconds to 5 minutes
    requires_session: bool = Field(default=False)
    requires_duplicate_detection: bool = Field(default=False)
    enable_dead_lettering_on_message_expiration: bool = Field(default=False)
    enable_batched_operations: bool = Field(default=True)
    max_delivery_count: int = Field(default=10, ge=1, le=2000)
    
    @field_validator('default_message_time_to_live')
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        """Validate TTL is reasonable (max 10 years)."""
        max_ttl = 315360000  # ~10 years in seconds
        if v > max_ttl:
            raise ValueError(f"DefaultMessageTimeToLive cannot exceed {max_ttl} seconds")
        return v


class QueueRuntimeInfo(BaseModel):
    """Queue runtime information model."""
    model_config = ConfigDict(extra='forbid')
    
    message_count: int = Field(default=0, ge=0)
    active_message_count: int = Field(default=0, ge=0)
    dead_letter_message_count: int = Field(default=0, ge=0)
    scheduled_message_count: int = Field(default=0, ge=0)
    transfer_message_count: int = Field(default=0, ge=0)
    transfer_dead_letter_message_count: int = Field(default=0, ge=0)
    size_in_bytes: int = Field(default=0, ge=0)
    
    def to_dict(self) -> Dict[str, int]:
        """Convert runtime info to dictionary."""
        return {
            "MessageCount": self.message_count,
            "ActiveMessageCount": self.active_message_count,
            "DeadLetterMessageCount": self.dead_letter_message_count,
            "ScheduledMessageCount": self.scheduled_message_count,
            "TransferMessageCount": self.transfer_message_count,
            "TransferDeadLetterMessageCount": self.transfer_dead_letter_message_count,
            "SizeInBytes": self.size_in_bytes,
        }


class QueueDescription(BaseModel):
    """
    Service Bus Queue Description model.
    
    This represents a Service Bus queue with its properties and runtime information.
    """
    model_config = ConfigDict(extra='forbid')
    
    name: str
    properties: QueueProperties = Field(default_factory=QueueProperties)
    runtime_info: QueueRuntimeInfo = Field(default_factory=QueueRuntimeInfo)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate queue name."""
        is_valid, error = QueueNameValidator.validate(v)
        if not is_valid:
            raise ValueError(error)
        return v
    
    def to_dict(self) -> Dict:
        """Convert queue description to dictionary for XML/JSON serialization."""
        return {
            "QueueName": self.name,
            "MaxSizeInMegabytes": self.properties.max_size_in_megabytes,
            "DefaultMessageTimeToLive": f"PT{self.properties.default_message_time_to_live}S",
            "LockDuration": f"PT{self.properties.lock_duration}S",
            "RequiresSession": self.properties.requires_session,
            "RequiresDuplicateDetection": self.properties.requires_duplicate_detection,
            "EnableDeadLetteringOnMessageExpiration": self.properties.enable_dead_lettering_on_message_expiration,
            "EnableBatchedOperations": self.properties.enable_batched_operations,
            "MaxDeliveryCount": self.properties.max_delivery_count,
            "MessageCount": self.runtime_info.message_count,
            "ActiveMessageCount": self.runtime_info.active_message_count,
            "DeadLetterMessageCount": self.runtime_info.dead_letter_message_count,
            "ScheduledMessageCount": self.runtime_info.scheduled_message_count,
            "SizeInBytes": self.runtime_info.size_in_bytes,
            "CreatedAt": self.created_at.isoformat(),
            "UpdatedAt": self.updated_at.isoformat(),
        }


class CreateQueueRequest(BaseModel):
    """Request model for creating a Service Bus queue."""
    model_config = ConfigDict(extra='forbid')
    
    properties: QueueProperties = Field(default_factory=QueueProperties)


class UpdateQueueRequest(BaseModel):
    """Request model for updating a Service Bus queue."""
    model_config = ConfigDict(extra='forbid')
    
    properties: QueueProperties


class ServiceBusMessage(BaseModel):
    """
    Service Bus Message model.
    
    Represents a message in a Service Bus queue with properties and state.
    """
    model_config = ConfigDict(extra='forbid')
    
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    content_type: Optional[str] = None
    label: Optional[str] = None
    to: Optional[str] = None
    reply_to: Optional[str] = None
    time_to_live: int = Field(default=1209600)  # 14 days in seconds
    scheduled_enqueue_time_utc: Optional[datetime] = None
    user_properties: Dict[str, str] = Field(default_factory=dict)
    
    # Message body
    body: str = ""  # Base64 encoded
    
    # System properties
    enqueued_time_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_number: int = 0
    delivery_count: int = 0
    lock_token: Optional[str] = None
    locked_until_utc: Optional[datetime] = None
    
    # Dead-letter properties
    dead_letter_reason: Optional[str] = None
    dead_letter_description: Optional[str] = None
    
    # State
    is_locked: bool = False
    is_dead_lettered: bool = False


class SendMessageRequest(BaseModel):
    """Request model for sending a message to Service Bus queue."""
    model_config = ConfigDict(extra='forbid')
    
    body: str
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    content_type: Optional[str] = None
    label: Optional[str] = None
    to: Optional[str] = None
    reply_to: Optional[str] = None
    time_to_live: Optional[int] = None
    scheduled_enqueue_time_utc: Optional[datetime] = None
    user_properties: Dict[str, str] = Field(default_factory=dict)


class ReceiveMode(str):
    """Message receive modes."""
    PEEK_LOCK = "PeekLock"
    RECEIVE_AND_DELETE = "ReceiveAndDelete"


# Topic and Subscription Models

class TopicProperties(BaseModel):
    """Properties for a Service Bus topic."""
    model_config = ConfigDict(extra='forbid')
    
    max_size_in_megabytes: int = Field(default=1024, ge=1, le=5120)
    default_message_time_to_live: int = Field(default=1209600)  # 14 days in seconds
    requires_duplicate_detection: bool = False
    enable_batched_operations: bool = True
    support_ordering: bool = False
    
    @field_validator('default_message_time_to_live')
    @classmethod
    def validate_ttl(cls, v):
        """Validate TTL is positive."""
        if v <= 0:
            raise ValueError("default_message_time_to_live must be positive")
        return v


class TopicRuntimeInfo(BaseModel):
    """Runtime information for a Service Bus topic."""
    model_config = ConfigDict(extra='forbid')
    
    subscription_count: int = 0
    size_in_bytes: int = 0
    scheduled_message_count: int = 0


class TopicDescription(BaseModel):
    """Complete description of a Service Bus topic."""
    model_config = ConfigDict(extra='forbid')
    
    name: str
    properties: TopicProperties
    runtime_info: TopicRuntimeInfo = Field(default_factory=TopicRuntimeInfo)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionProperties(BaseModel):
    """Properties for a Service Bus subscription."""
    model_config = ConfigDict(extra='forbid')
    
    lock_duration: int = Field(default=60, ge=5, le=300)  # 5-300 seconds
    requires_session: bool = False
    default_message_time_to_live: int = Field(default=1209600)  # 14 days
    auto_delete_on_idle: Optional[int] = None  # seconds
    dead_lettering_on_message_expiration: bool = False
    max_delivery_count: int = Field(default=10, ge=1, le=2000)
    enable_batched_operations: bool = True
    forward_to: Optional[str] = None
    
    @field_validator('lock_duration')
    @classmethod
    def validate_lock_duration(cls, v):
        """Validate lock duration is between 5 and 300 seconds."""
        if not (5 <= v <= 300):
            raise ValueError("lock_duration must be between 5 and 300 seconds")
        return v


class SubscriptionRuntimeInfo(BaseModel):
    """Runtime information for a subscription."""
    model_config = ConfigDict(extra='forbid')
    
    message_count: int = 0
    active_message_count: int = 0
    dead_letter_message_count: int = 0


class FilterType(str):
    """Types of subscription filters."""
    TRUE_FILTER = "TrueFilter"
    FALSE_FILTER = "FalseFilter"
    SQL_FILTER = "SqlFilter"
    CORRELATION_FILTER = "CorrelationFilter"


class SubscriptionFilter(BaseModel):
    """Base filter for subscriptions."""
    model_config = ConfigDict(extra='forbid')
    
    filter_type: str
    sql_expression: Optional[str] = None  # For SqlFilter
    correlation_id: Optional[str] = None  # For CorrelationFilter
    content_type: Optional[str] = None
    label: Optional[str] = None
    message_id: Optional[str] = None
    reply_to: Optional[str] = None
    session_id: Optional[str] = None
    to: Optional[str] = None
    properties: Dict[str, str] = Field(default_factory=dict)  # User properties for CorrelationFilter


class RuleDescription(BaseModel):
    """Rule containing filter for subscription."""
    model_config = ConfigDict(extra='forbid')
    
    name: str = "$Default"
    filter: SubscriptionFilter = Field(default_factory=lambda: SubscriptionFilter(filter_type=FilterType.TRUE_FILTER))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionDescription(BaseModel):
    """Complete description of a Service Bus subscription."""
    model_config = ConfigDict(extra='forbid')
    
    topic_name: str
    subscription_name: str
    properties: SubscriptionProperties
    runtime_info: SubscriptionRuntimeInfo = Field(default_factory=SubscriptionRuntimeInfo)
    rules: list[RuleDescription] = Field(default_factory=lambda: [RuleDescription()])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateTopicRequest(BaseModel):
    """Request model for creating a topic."""
    model_config = ConfigDict(extra='forbid')
    
    properties: TopicProperties


class UpdateTopicRequest(BaseModel):
    """Request model for updating a topic."""
    model_config = ConfigDict(extra='forbid')
    
    properties: TopicProperties


class CreateSubscriptionRequest(BaseModel):
    """Request model for creating a subscription."""
    model_config = ConfigDict(extra='forbid')
    
    properties: SubscriptionProperties
    filter: Optional[SubscriptionFilter] = None


class UpdateSubscriptionRequest(BaseModel):
    """Request model for updating a subscription."""
    model_config = ConfigDict(extra='forbid')
    
    properties: SubscriptionProperties
