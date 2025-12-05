"""
Resilience Utilities for Service Bus

Implements timeout handling, retry logic, and circuit breaker pattern.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import asyncio
import time
from enum import Enum
from functools import wraps
from typing import Optional, Callable, Any, TypeVar, cast
from datetime import datetime, timedelta, timezone

from .exceptions import ServiceBusError, TimeoutError as ServiceBusTimeoutError, is_transient_error
from .logging_utils import StructuredLogger


logger = StructuredLogger('localzure.services.servicebus.resilience')

T = TypeVar('T')


# ========== Configuration ==========

class OperationType(str, Enum):
    """Operation types with different timeout configurations."""
    SEND = "send"
    RECEIVE = "receive"
    ADMIN = "admin"
    LOCK = "lock"
    SESSION = "session"


class TimeoutConfig:
    """Timeout configuration for different operation types."""
    
    # Default timeouts in seconds
    DEFAULTS = {
        OperationType.SEND: 30.0,
        OperationType.RECEIVE: 60.0,
        OperationType.ADMIN: 30.0,
        OperationType.LOCK: 10.0,
        OperationType.SESSION: 60.0,
    }
    
    @classmethod
    def get_timeout(cls, operation_type: OperationType) -> float:
        """Get timeout for operation type."""
        return cls.DEFAULTS.get(operation_type, 60.0)


class RetryConfig:
    """Retry configuration."""
    
    MAX_ATTEMPTS = 3
    INITIAL_BACKOFF = 1.0  # seconds
    MAX_BACKOFF = 30.0  # seconds
    BACKOFF_MULTIPLIER = 2.0  # exponential backoff


# ========== Timeout Handling ==========

def with_timeout(
    operation_type: OperationType,
    timeout_seconds: Optional[float] = None
):
    """
    Decorator to add timeout handling to async functions.
    
    Args:
        operation_type: Type of operation for default timeout
        timeout_seconds: Optional override timeout in seconds
        
    Usage:
        @with_timeout(OperationType.SEND)
        async def send_message(...):
            ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            timeout = timeout_seconds or TimeoutConfig.get_timeout(operation_type)
            operation_name = func.__name__
            
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout
                )
                return result
                
            except asyncio.TimeoutError:
                error = ServiceBusTimeoutError(
                    operation=operation_name,
                    timeout_seconds=timeout
                )
                logger.error(
                    f"Operation timeout: {operation_name}",
                    exc_info=False,
                    operation_name=operation_name,
                    timeout_seconds=timeout,
                    error_type=type(error).__name__
                )
                raise error
        
        return wrapper
    return decorator


# ========== Retry Logic ==========

def with_retry(
    max_attempts: Optional[int] = None,
    initial_backoff: Optional[float] = None,
    max_backoff: Optional[float] = None,
    backoff_multiplier: Optional[float] = None,
    retry_on: Optional[Callable[[Exception], bool]] = None
):
    """
    Decorator to add retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum retry attempts (default: 3)
        initial_backoff: Initial backoff delay in seconds (default: 1.0)
        max_backoff: Maximum backoff delay in seconds (default: 30.0)
        backoff_multiplier: Backoff multiplier (default: 2.0)
        retry_on: Custom function to determine if error is retryable
        
    Usage:
        @with_retry(max_attempts=3)
        async def send_message(...):
            ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempts = max_attempts or RetryConfig.MAX_ATTEMPTS
            backoff = initial_backoff or RetryConfig.INITIAL_BACKOFF
            max_delay = max_backoff or RetryConfig.MAX_BACKOFF
            multiplier = backoff_multiplier or RetryConfig.BACKOFF_MULTIPLIER
            
            operation_name = func.__name__
            last_error: Optional[Exception] = None
            
            for attempt in range(1, attempts + 1):
                try:
                    result = await func(*args, **kwargs)
                    
                    # Log successful retry
                    if attempt > 1:
                        logger.info(
                            f"Operation succeeded after {attempt} attempts: {operation_name}",
                            operation=operation_name,
                            attempt=attempt,
                            total_attempts=attempts
                        )
                    
                    return result
                    
                except Exception as e:
                    last_error = e
                    
                    # Determine if error is retryable
                    should_retry = (
                        retry_on(e) if retry_on else is_transient_error(e)
                    )
                    
                    if not should_retry or attempt >= attempts:
                        logger.error(
                            f"Operation failed (non-retryable or max attempts): {operation_name}",
                            exc_info=False,
                            operation_name=operation_name,
                            attempt=attempt,
                            max_attempts=attempts,
                            retryable=should_retry,
                            error_type=type(e).__name__,
                            error_message=str(e)
                        )
                        raise
                    
                    # Calculate backoff delay
                    delay = min(backoff * (multiplier ** (attempt - 1)), max_delay)
                    
                    logger.warning(
                        f"Operation failed, retrying: {operation_name}",
                        operation_name=operation_name,
                        attempt=attempt,
                        max_attempts=attempts,
                        error_type=type(e).__name__,
                        error_message=str(e),
                        retry_delay_seconds=delay
                    )
                    
                    await asyncio.sleep(delay)
            
            # Should never reach here, but just in case
            if last_error:
                raise last_error
                
        return wrapper
    return decorator


# ========== Circuit Breaker ==========

class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(ServiceBusError):
    """Raised when circuit breaker is open."""
    error_code = "CircuitBreakerOpen"
    
    def __init__(
        self,
        operation: str,
        failure_count: int,
        message: Optional[str] = None
    ):
        message = message or f"Circuit breaker open for '{operation}' after {failure_count} failures"
        details = {"operation": operation, "failure_count": failure_count}
        super().__init__(message, details=details)


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Tracks failures and opens circuit when threshold is exceeded.
    Automatically attempts recovery after reset timeout.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 1
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name (for logging)
            failure_threshold: Number of consecutive failures before opening
            reset_timeout: Seconds to wait before attempting recovery
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Async function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from function
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise CircuitBreakerError(
                        operation=self.name,
                        failure_count=self._failure_count
                    )
            
            # In HALF_OPEN, limit concurrent calls
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerError(
                        operation=self.name,
                        failure_count=self._failure_count
                    )
                self._half_open_calls += 1
        
        # Execute function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except Exception as e:
            await self._on_failure(e)
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return True
        
        elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
        return elapsed >= self.reset_timeout
    
    def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN state."""
        logger.info(
            f"Circuit breaker transitioning to HALF_OPEN: {self.name}",
            circuit_breaker=self.name,
            previous_state=self._state.value,
            new_state=CircuitState.HALF_OPEN.value
        )
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
    
    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Successful call in HALF_OPEN closes circuit
                logger.info(
                    f"Circuit breaker closing after successful test: {self.name}",
                    circuit_breaker=self.name,
                    previous_state=self._state.value,
                    new_state=CircuitState.CLOSED.value
                )
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
    
    async def _on_failure(self, error: Exception) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)
            
            if self._state == CircuitState.HALF_OPEN:
                # Failure in HALF_OPEN reopens circuit
                logger.warning(
                    f"Circuit breaker reopening after failed test: {self.name}",
                    circuit_breaker=self.name,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    failure_count=self._failure_count
                )
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                
            elif self._state == CircuitState.CLOSED:
                # Check if threshold exceeded
                if self._failure_count >= self.failure_threshold:
                    logger.error(
                        f"Circuit breaker opening after {self._failure_count} failures: {self.name}",
                        exc_info=False,
                        circuit_breaker=self.name,
                        failure_count=self._failure_count,
                        threshold=self.failure_threshold,
                        error_type=type(error).__name__,
                        error_message=str(error)
                    )
                    self._state = CircuitState.OPEN
    
    async def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        async with self._lock:
            logger.info(
                f"Circuit breaker manually reset: {self.name}",
                circuit_breaker=self.name,
                previous_state=self._state.value
            )
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0


# ========== Global Circuit Breakers ==========

# Circuit breakers for different subsystems
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs: Any) -> CircuitBreaker:
    """
    Get or create circuit breaker for named operation.
    
    Args:
        name: Circuit breaker name
        **kwargs: Circuit breaker configuration
        
    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, **kwargs)
    return _circuit_breakers[name]


def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    reset_timeout: float = 60.0
):
    """
    Decorator to protect async function with circuit breaker.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening
        reset_timeout: Seconds before attempting recovery
        
    Usage:
        @with_circuit_breaker("queue_operations")
        async def send_message(...):
            ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            breaker = get_circuit_breaker(
                name,
                failure_threshold=failure_threshold,
                reset_timeout=reset_timeout
            )
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator
