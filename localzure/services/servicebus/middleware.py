"""
Correlation ID Middleware for Service Bus API

Extracts or generates correlation IDs and propagates them through requests.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .logging_utils import CorrelationContext, StructuredLogger


logger = StructuredLogger('localzure.services.servicebus.middleware')


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle correlation ID extraction and propagation."""
    
    def __init__(self, app: ASGIApp):
        """Initialize middleware."""
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Process request and inject correlation ID."""
        # Extract or generate correlation ID
        correlation_id = request.headers.get('x-correlation-id') or request.headers.get('correlation-id')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Set in context for this request
        CorrelationContext.set_correlation_id(correlation_id)
        
        # Log request
        start_time = time.time()
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            operation="request_started",
            method=request.method,
            path=request.url.path,
            correlation_id=correlation_id
        )
        
        try:
            # Process request
            response: Response = await call_next(request)
            
            # Add correlation ID to response headers
            response.headers['x-correlation-id'] = correlation_id
            
            # Log response
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                operation="request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2)
            )
            
            return response
            
        except Exception as e:
            # Log error
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=True,
                operation="request_failed",
                method=request.method,
                path=request.url.path,
                error_type=type(e).__name__,
                error_message=str(e),
                duration_ms=round(duration_ms, 2)
            )
            raise
        finally:
            # Clear correlation ID after request
            CorrelationContext.clear_correlation_id()
