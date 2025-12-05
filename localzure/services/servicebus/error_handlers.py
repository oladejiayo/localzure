"""
FastAPI Exception Handlers for Service Bus

Maps Service Bus exceptions to standardized HTTP error responses.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from .exceptions import (
    ServiceBusError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    InvalidEntityNameError,
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
)
from .resilience import CircuitBreakerError
from .error_models import ErrorResponse
from .logging_utils import CorrelationContext, StructuredLogger


logger = StructuredLogger('localzure.services.servicebus.api.errors')


# Exception to HTTP status code mapping
EXCEPTION_STATUS_CODES = {
    EntityNotFoundError: status.HTTP_404_NOT_FOUND,
    EntityAlreadyExistsError: status.HTTP_409_CONFLICT,
    InvalidEntityNameError: status.HTTP_400_BAD_REQUEST,
    MessageNotFoundError: status.HTTP_404_NOT_FOUND,
    MessageSizeExceededError: status.HTTP_413_CONTENT_TOO_LARGE,
    MessageLockLostError: status.HTTP_410_GONE,
    SessionNotFoundError: status.HTTP_404_NOT_FOUND,
    SessionLockLostError: status.HTTP_410_GONE,
    SessionAlreadyLockedError: status.HTTP_409_CONFLICT,
    QuotaExceededError: status.HTTP_507_INSUFFICIENT_STORAGE,
    InvalidOperationError: status.HTTP_400_BAD_REQUEST,
    TimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
    ServiceBusConnectionError: status.HTTP_503_SERVICE_UNAVAILABLE,
    CircuitBreakerError: status.HTTP_503_SERVICE_UNAVAILABLE,
}


def get_status_code_for_exception(exc: Exception) -> int:
    """
    Get HTTP status code for exception type.
    
    Args:
        exc: Exception instance
        
    Returns:
        HTTP status code
    """
    # Check exact type first
    exc_type = type(exc)
    if exc_type in EXCEPTION_STATUS_CODES:
        return EXCEPTION_STATUS_CODES[exc_type]
    
    # Check if it's a subclass
    for exception_type, status_code in EXCEPTION_STATUS_CODES.items():
        if isinstance(exc, exception_type):
            return status_code
    
    # Default to 500 for unknown errors
    return status.HTTP_500_INTERNAL_SERVER_ERROR


async def service_bus_exception_handler(
    request: Request,
    exc: ServiceBusError
) -> JSONResponse:
    """
    Handle ServiceBusError exceptions.
    
    Args:
        request: FastAPI request
        exc: ServiceBusError instance
        
    Returns:
        JSONResponse with standardized error format
    """
    correlation_id = CorrelationContext.get_correlation_id()
    status_code = get_status_code_for_exception(exc)
    
    # Create error response
    error_response = ErrorResponse.from_exception(exc, correlation_id)
    
    # Log error
    logger.log_error(
        operation="api_error",
        error_type=type(exc).__name__,
        error_message=str(exc),
        error_code=exc.error_code,
        status_code=status_code,
        correlation_id=correlation_id,
        path=str(request.url)
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle generic exceptions.
    
    Args:
        request: FastAPI request
        exc: Exception instance
        
    Returns:
        JSONResponse with standardized error format
    """
    correlation_id = CorrelationContext.get_correlation_id()
    
    # Create error response
    error_response = ErrorResponse.from_exception(exc, correlation_id)
    
    # Log error
    logger.log_error(
        operation="unexpected_error",
        error_type=type(exc).__name__,
        error_message=str(exc),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        correlation_id=correlation_id,
        path=str(request.url)
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump()
    )


def register_exception_handlers(app_or_router):
    """
    Register exception handlers with FastAPI app or router.
    
    Args:
        app_or_router: FastAPI app or APIRouter instance
    """
    # Register ServiceBusError handler
    app_or_router.add_exception_handler(
        ServiceBusError,
        service_bus_exception_handler
    )
    
    # Register generic exception handler
    app_or_router.add_exception_handler(
        Exception,
        generic_exception_handler
    )
