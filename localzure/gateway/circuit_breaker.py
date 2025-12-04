"""Circuit breaker pattern for LocalZure Gateway.

This module provides circuit breaker functionality for fault tolerance
and graceful degradation when downstream services fail.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Callable, Any
import logging
import asyncio

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker state."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes before closing from half-open
    timeout_seconds: float = 60.0  # Time before half-open retry
    half_open_max_calls: int = 3  # Max calls in half-open state
    excluded_exceptions: tuple = ()  # Exceptions that don't count as failures

    def __post_init__(self):
        """Validate configuration."""
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be at least 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""

    state: CircuitState
    failure_count: int
    success_count: int
    total_calls: int
    total_failures: int
    total_successes: int
    last_failure_time: Optional[float]
    last_state_change: float
    half_open_calls: int


class CircuitBreakerError(Exception):
    """Exception raised when circuit is open."""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker open for {service_name}, retry after {retry_after:.1f}s"
        )


class CircuitBreaker:
    """Production-grade circuit breaker for service resilience."""

    def __init__(self, service_name: str, config: Optional[CircuitBreakerConfig] = None):
        """Initialize circuit breaker.

        Args:
            service_name: Name of the service
            config: Circuit breaker configuration
        """
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change = time.time()
        self._half_open_calls = 0
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current state."""
        return self._state

    async def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            fallback: Optional fallback function if circuit is open
            **kwargs: Keyword arguments for func

        Returns:
            Result from func or fallback

        Raises:
            CircuitBreakerError: If circuit is open and no fallback provided
        """
        self._total_calls += 1

        # Check if we should allow the call
        if not await self._should_allow_call():
            if fallback:
                logger.info(
                    f"Circuit breaker open for {self.service_name}, using fallback"
                )
                return await self._execute_fallback(fallback, *args, **kwargs)
            else:
                retry_after = self._get_retry_after()
                raise CircuitBreakerError(self.service_name, retry_after)

        # Execute the call
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except Exception as e:
            # Check if this exception should be excluded
            if isinstance(e, self.config.excluded_exceptions):
                logger.debug(
                    f"Exception {type(e).__name__} excluded from circuit breaker"
                )
                raise

            await self._on_failure()
            raise

    async def _should_allow_call(self) -> bool:
        """Check if call should be allowed.

        Returns:
            True if call is allowed
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if self._should_attempt_reset():
                    await self._transition_to_half_open()
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset from open state.

        Returns:
            True if timeout has elapsed
        """
        if self._last_failure_time is None:
            return False
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.timeout_seconds

    async def _transition_to_half_open(self) -> None:
        """Transition to half-open state."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._last_state_change = time.time()
        logger.info(f"Circuit breaker {self.service_name} transitioned to HALF_OPEN")

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self._total_successes += 1

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    await self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                await self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    await self._transition_to_open()

    async def _transition_to_closed(self) -> None:
        """Transition to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_state_change = time.time()
        logger.info(f"Circuit breaker {self.service_name} transitioned to CLOSED")

    async def _transition_to_open(self) -> None:
        """Transition to open state."""
        self._state = CircuitState.OPEN
        self._success_count = 0
        self._last_state_change = time.time()
        logger.warning(
            f"Circuit breaker {self.service_name} transitioned to OPEN "
            f"({self._failure_count} failures)"
        )

    async def _execute_fallback(
        self, fallback: Callable, *args, **kwargs
    ) -> Any:
        """Execute fallback function.

        Args:
            fallback: Fallback function
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result from fallback
        """
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            else:
                return fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fallback function failed for {self.service_name}: {e}")
            raise

    def _get_retry_after(self) -> float:
        """Calculate retry after time.

        Returns:
            Seconds until circuit may be retried
        """
        if self._last_failure_time is None:
            return 0.0
        elapsed = time.time() - self._last_failure_time
        remaining = max(0.0, self.config.timeout_seconds - elapsed)
        return remaining

    async def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        async with self._lock:
            await self._transition_to_closed()
            self._last_failure_time = None
            logger.info(f"Circuit breaker {self.service_name} manually reset")

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics.

        Returns:
            Statistics object
        """
        return CircuitBreakerStats(
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            total_calls=self._total_calls,
            total_failures=self._total_failures,
            total_successes=self._total_successes,
            last_failure_time=self._last_failure_time,
            last_state_change=self._last_state_change,
            half_open_calls=self._half_open_calls,
        )


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self, default_config: Optional[CircuitBreakerConfig] = None):
        """Initialize registry.

        Args:
            default_config: Default configuration for new breakers
        """
        self.default_config = default_config or CircuitBreakerConfig()
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_breaker(
        self, service_name: str, config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get or create circuit breaker for service.

        Args:
            service_name: Name of the service
            config: Optional configuration (uses default if not provided)

        Returns:
            Circuit breaker instance
        """
        async with self._lock:
            if service_name not in self._breakers:
                breaker_config = config or self.default_config
                self._breakers[service_name] = CircuitBreaker(
                    service_name, breaker_config
                )
                logger.info(f"Created circuit breaker for {service_name}")

            return self._breakers[service_name]

    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        async with self._lock:
            for breaker in self._breakers.values():
                await breaker.reset()
            logger.info("Reset all circuit breakers")

    def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers.

        Returns:
            Dictionary of service name to stats
        """
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}
