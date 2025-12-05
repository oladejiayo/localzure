"""
Queue Storage Models

Pydantic models for Azure Queue Storage queues, metadata, properties, and messages.

Author: Ayodele Oladeji
Date: 2025
"""

import base64
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueueNameValidator:
    """
    Validates Azure Queue Storage queue names.
    
    Rules:
    - 3-63 characters
    - Lowercase letters, numbers, hyphens only
    - Must start with letter
    - No consecutive hyphens
    """
    
    # Queue name pattern
    PATTERN = re.compile(r'^[a-z]([a-z0-9-]*[a-z0-9])?$')
    MIN_LENGTH = 3
    MAX_LENGTH = 63
    
    @classmethod
    def validate(cls, name: str) -> tuple[bool, Optional[str]]:
        """
        Validate queue name against Azure rules.
        
        Args:
            name: Queue name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check length
        if len(name) < cls.MIN_LENGTH:
            return False, f"Queue name must be at least {cls.MIN_LENGTH} characters"
        if len(name) > cls.MAX_LENGTH:
            return False, f"Queue name must be at most {cls.MAX_LENGTH} characters"
        
        # Check for consecutive hyphens first
        if '--' in name:
            return False, "Queue name cannot contain consecutive hyphens"
        
        # Check pattern
        if not cls.PATTERN.match(name):
            if not name[0].isalpha() or not name[0].islower():
                return False, "Queue name must start with a lowercase letter"
            return False, "Queue name can only contain lowercase letters, numbers, and hyphens"
        
        return True, None


class QueueMetadata(BaseModel):
    """Queue metadata model."""
    model_config = ConfigDict(extra='forbid')
    
    metadata: Dict[str, str] = Field(default_factory=dict)
    
    @field_validator('metadata')
    @classmethod
    def validate_metadata_keys(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Ensure metadata keys are valid."""
        for key in v.keys():
            if not key or not isinstance(key, str):
                raise ValueError(f"Invalid metadata key: {key}")
        return v
    
    def to_headers(self) -> Dict[str, str]:
        """Convert metadata to HTTP headers."""
        return {f"x-ms-meta-{k}": v for k, v in self.metadata.items()}


class QueueProperties(BaseModel):
    """Queue properties model."""
    model_config = ConfigDict(extra='forbid')
    
    approximate_message_count: int = Field(default=0, ge=0)
    
    def to_headers(self) -> Dict[str, str]:
        """Convert properties to HTTP headers."""
        return {
            "x-ms-approximate-messages-count": str(self.approximate_message_count),
        }


class Queue(BaseModel):
    """Queue model representing an Azure Queue Storage queue."""
    model_config = ConfigDict(extra='forbid')
    
    name: str
    metadata: QueueMetadata = Field(default_factory=QueueMetadata)
    properties: QueueProperties = Field(default_factory=QueueProperties)
    created_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate queue name."""
        is_valid, error = QueueNameValidator.validate(v)
        if not is_valid:
            raise ValueError(error)
        return v
    
    def to_dict(self) -> Dict[str, any]:
        """Convert queue to dictionary for XML serialization."""
        return {
            "Name": self.name,
            "Metadata": self.metadata.metadata if self.metadata.metadata else None,
        }


class CreateQueueRequest(BaseModel):
    """Request model for creating a queue."""
    model_config = ConfigDict(extra='forbid')
    
    metadata: Dict[str, str] = Field(default_factory=dict)


class SetQueueMetadataRequest(BaseModel):
    """Request model for setting queue metadata."""
    model_config = ConfigDict(extra='forbid')
    
    metadata: Dict[str, str] = Field(default_factory=dict)


class Message(BaseModel):
    """
    Queue message model representing an Azure Queue Storage message.
    
    Attributes:
        message_id: Unique identifier for the message
        insertion_time: Time when message was inserted into queue
        expiration_time: Time when message expires and is automatically deleted
        pop_receipt: Receipt string required for update/delete operations
        time_next_visible: Time when message will become visible again
        dequeue_count: Number of times message has been dequeued
        message_text: Message content (base64-encoded)
    """
    model_config = ConfigDict(extra='forbid')
    
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    insertion_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expiration_time: datetime
    pop_receipt: str = Field(default_factory=lambda: base64.b64encode(uuid.uuid4().bytes).decode('utf-8'))
    time_next_visible: datetime
    dequeue_count: int = Field(default=0, ge=0)
    message_text: str  # base64-encoded content
    
    @classmethod
    def create(
        cls,
        message_text: str,
        visibility_timeout: int = 0,
        message_ttl: int = 604800,  # 7 days default
    ) -> "Message":
        """
        Create a new message with calculated times.
        
        Args:
            message_text: Message content (will be base64-encoded if not already)
            visibility_timeout: Seconds until message becomes visible (default: 0)
            message_ttl: Message time-to-live in seconds (default: 7 days)
            
        Returns:
            New Message instance
        """
        now = datetime.now(timezone.utc)
        
        # Ensure message text is base64-encoded
        try:
            # Test if it's already base64
            base64.b64decode(message_text)
            encoded_text = message_text
        except Exception:
            # Not base64, encode it
            encoded_text = base64.b64encode(message_text.encode('utf-8')).decode('utf-8')
        
        # If visibility_timeout is 0, make immediately visible
        if visibility_timeout == 0:
            time_next_visible = now - timedelta(seconds=1)
        else:
            time_next_visible = now + timedelta(seconds=visibility_timeout)
        
        return cls(
            message_text=encoded_text,
            insertion_time=now,
            expiration_time=now + timedelta(seconds=message_ttl),
            time_next_visible=time_next_visible,
        )
    
    def update_visibility(self, visibility_timeout: int, new_text: Optional[str] = None) -> str:
        """
        Update message visibility timeout and optionally message text.
        Generates new pop receipt.
        
        Args:
            visibility_timeout: New visibility timeout in seconds
            new_text: Optional new message text (should be base64-encoded)
            
        Returns:
            New pop receipt
        """
        now = datetime.now(timezone.utc)
        # If visibility_timeout is 0, make immediately visible by setting time in the past
        if visibility_timeout == 0:
            self.time_next_visible = now - timedelta(seconds=1)
        else:
            self.time_next_visible = now + timedelta(seconds=visibility_timeout)
        self.pop_receipt = base64.b64encode(uuid.uuid4().bytes).decode('utf-8')
        if new_text is not None:
            self.message_text = new_text
        return self.pop_receipt
    
    def is_visible(self) -> bool:
        """Check if message is currently visible."""
        return datetime.now(timezone.utc) >= self.time_next_visible
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        return datetime.now(timezone.utc) >= self.expiration_time
    
    def to_dict(self, include_pop_receipt: bool = True) -> Dict[str, any]:
        """
        Convert message to dictionary for XML serialization.
        
        Args:
            include_pop_receipt: Whether to include pop receipt (False for peek)
            
        Returns:
            Dictionary representation
        """
        result = {
            "MessageId": self.message_id,
            "InsertionTime": self.insertion_time.strftime('%a, %d %b %Y %H:%M:%S GMT'),
            "ExpirationTime": self.expiration_time.strftime('%a, %d %b %Y %H:%M:%S GMT'),
            "DequeueCount": str(self.dequeue_count),
            "MessageText": self.message_text,
        }
        
        if include_pop_receipt:
            result["PopReceipt"] = self.pop_receipt
            result["TimeNextVisible"] = self.time_next_visible.strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        return result


class PutMessageRequest(BaseModel):
    """Request model for putting a message into queue."""
    model_config = ConfigDict(extra='forbid')
    
    message_text: str
    visibility_timeout: int = Field(default=0, ge=0, le=604800)  # 0 to 7 days
    message_ttl: int = Field(default=604800, ge=1, le=604800)  # 1 second to 7 days


class UpdateMessageRequest(BaseModel):
    """Request model for updating a message."""
    model_config = ConfigDict(extra='forbid')
    
    message_text: Optional[str] = None
    visibility_timeout: int = Field(..., ge=0, le=604800)  # Required, 0 to 7 days
