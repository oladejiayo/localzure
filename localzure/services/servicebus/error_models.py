"""
Error Response Models for Service Bus API

Standardized error response format for API endpoints.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class ErrorDetails(BaseModel):
    """Additional error context details."""
    
    entity_type: Optional[str] = Field(None, description="Type of entity (queue, topic, subscription)")
    entity_name: Optional[str] = Field(None, description="Name of entity")
    message_id: Optional[str] = Field(None, description="Message identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")
    correlation_id: Optional[str] = Field(None, description="Request correlation identifier")
    operation: Optional[str] = Field(None, description="Operation that failed")
    reason: Optional[str] = Field(None, description="Failure reason")
    
    # Quota errors
    quota_type: Optional[str] = None
    current_value: Optional[int] = None
    max_value: Optional[int] = None
    
    # Timeout errors
    timeout_seconds: Optional[float] = None
    
    # Size errors
    actual_size: Optional[int] = None
    max_size: Optional[int] = None
    
    model_config = ConfigDict(extra="allow")  # Allow additional fields


class ErrorInfo(BaseModel):
    """Error information in API response."""
    
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: ErrorDetails = Field(default_factory=ErrorDetails, description="Additional context")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "code": "EntityNotFound",
            "message": "Queue 'myqueue' does not exist",
            "details": {
                "entity_type": "queue",
                "entity_name": "myqueue",
                "correlation_id": "abc-123"
            }
        }
    })


class ErrorResponse(BaseModel):
    """Standard API error response format."""
    
    error: ErrorInfo = Field(..., description="Error information")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": {
                "code": "EntityNotFound",
                "message": "Queue 'myqueue' does not exist",
                "details": {
                    "entity_type": "queue",
                    "entity_name": "myqueue",
                    "correlation_id": "abc-123"
                }
            }
        }
    })
    
    @classmethod
    def from_exception(cls, exc: Exception, correlation_id: Optional[str] = None) -> "ErrorResponse":
        """
        Create ErrorResponse from exception.
        
        Args:
            exc: Exception to convert
            correlation_id: Optional correlation ID to include
            
        Returns:
            ErrorResponse instance
        """
        from .exceptions import ServiceBusError
        
        if isinstance(exc, ServiceBusError):
            # Use exception's built-in error dict
            error_dict = exc.to_dict()["error"]
            details_dict = error_dict.get("details", {})
            
            # Add correlation ID if provided
            if correlation_id:
                details_dict["correlation_id"] = correlation_id
            
            return cls(
                error=ErrorInfo(
                    code=error_dict["code"],
                    message=error_dict["message"],
                    details=ErrorDetails(**details_dict)
                )
            )
        else:
            # Generic error for non-ServiceBusError exceptions
            details_dict = {}
            if correlation_id:
                details_dict["correlation_id"] = correlation_id
            
            return cls(
                error=ErrorInfo(
                    code="InternalError",
                    message=str(exc) or "An unexpected error occurred",
                    details=ErrorDetails(**details_dict)
                )
            )
