"""
Structured Logging Infrastructure for LocalZure Service Bus

Provides correlation tracking, JSON formatting, and context-aware logging
for async operations.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import contextvars
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from functools import wraps
import traceback


# Context variable for correlation ID (thread-safe for async)
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)


class CorrelationContext:
    """Manages correlation ID context for request tracing."""
    
    @staticmethod
    def get_correlation_id() -> str:
        """Get current correlation ID or generate new one."""
        corr_id = correlation_id_var.get()
        if not corr_id:
            corr_id = str(uuid.uuid4())
            correlation_id_var.set(corr_id)
        return corr_id
    
    @staticmethod
    def set_correlation_id(corr_id: str) -> None:
        """Set correlation ID for current context."""
        correlation_id_var.set(corr_id)
    
    @staticmethod
    def clear_correlation_id() -> None:
        """Clear correlation ID from current context."""
        correlation_id_var.set(None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': CorrelationContext.get_correlation_id(),
        }
        
        # Add extra fields from record (exclude standard LogRecord attributes)
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname', 
            'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
            'exc_text', 'stack_info', 'getMessage', 'taskName'
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                log_data[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': ''.join(traceback.format_exception(*record.exc_info))
            }
        
        return json.dumps(log_data)


class StructuredLogger:
    """Structured logger with correlation tracking."""
    
    def __init__(self, name: str):
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)
        self._setup_handler()
    
    def _setup_handler(self) -> None:
        """Setup JSON handler if not already configured."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _log(self, level: int, message: str, **kwargs) -> None:
        """Log with extra context fields."""
        extra = {k: v for k, v in kwargs.items() if v is not None}
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log error message."""
        if exc_info:
            self.logger.error(message, exc_info=True, extra=kwargs)
        else:
            self._log(logging.ERROR, message, **kwargs)
    
    def log_operation(self, operation: str, entity_type: str, entity_name: str, **kwargs) -> None:
        """Log entity operation."""
        self.info(
            f"{operation}: {entity_type}/{entity_name}",
            operation=operation,
            entity_type=entity_type,
            entity_name=entity_name,
            **kwargs
        )
    
    def log_message_operation(
        self,
        operation: str,
        entity_type: str,
        entity_name: str,
        message_id: str,
        **kwargs
    ) -> None:
        """Log message operation."""
        self.info(
            f"{operation}: {entity_type}/{entity_name} message={message_id}",
            operation=operation,
            entity_type=entity_type,
            entity_name=entity_name,
            message_id=message_id,
            **kwargs
        )
    
    def log_filter_evaluation(
        self,
        filter_expression: str,
        filter_result: bool,
        message_id: str,
        subscription_name: str,
        **kwargs
    ) -> None:
        """Log filter evaluation result."""
        self.debug(
            f"Filter evaluation: subscription={subscription_name} message={message_id} result={filter_result}",
            operation="filter_evaluated",
            filter_expression=filter_expression,
            filter_result=filter_result,
            message_id=message_id,
            subscription_name=subscription_name,
            **kwargs
        )
    
    def log_lock_operation(
        self,
        operation: str,
        entity_type: str,
        entity_name: str,
        message_id: str,
        lock_token: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log lock-related operation."""
        self.debug(
            f"{operation}: {entity_type}/{entity_name} message={message_id}",
            operation=operation,
            entity_type=entity_type,
            entity_name=entity_name,
            message_id=message_id,
            lock_token=lock_token,
            **kwargs
        )
    
    def log_error(
        self,
        operation: str,
        error_type: str,
        error_message: str,
        **kwargs
    ) -> None:
        """Log error with context."""
        self.error(
            f"Error in {operation}: {error_message}",
            operation=operation,
            error_type=error_type,
            error_message=error_message,
            **kwargs
        )


def track_operation_time(logger: StructuredLogger, operation: str):
    """Decorator to track operation execution time."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(
                    f"Operation completed: {operation}",
                    operation=operation,
                    duration_ms=round(duration_ms, 2)
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Operation failed: {operation}",
                    exc_info=True,
                    operation=operation,
                    duration_ms=round(duration_ms, 2),
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise
        return wrapper
    return decorator


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    Configure global logging settings.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON formatting (True) or plain text (False)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add new handler with appropriate formatter
    handler = logging.StreamHandler()
    if json_format:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
    
    root_logger.addHandler(handler)
    
    # Configure service bus logger
    sb_logger = logging.getLogger('localzure.services.servicebus')
    sb_logger.setLevel(log_level)


# Module-level logger for this package
logger = StructuredLogger('localzure.services.servicebus')
