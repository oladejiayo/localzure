"""
Unit Tests for Service Bus Resilience Utilities

Tests for timeout, retry, and circuit breaker patterns.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from localzure.services.servicebus.resilience import (
    OperationType,
    TimeoutConfig,
    RetryConfig,
    with_timeout,
    with_retry,
    CircuitBreaker,
    CircuitState,
    CircuitBreakerError,
    get_circuit_breaker,
    with_circuit_breaker,
)
from localzure.services.servicebus.exceptions import (
    TimeoutError as ServiceBusTimeoutError,
    ServiceBusConnectionError,
)


class TestTimeoutConfig:
    """Tests for timeout configuration."""
    
    def test_default_timeouts(self):
        """Test default timeout values."""
        assert TimeoutConfig.get_timeout(OperationType.SEND) == 30.0
        assert TimeoutConfig.get_timeout(OperationType.RECEIVE) == 60.0
        assert TimeoutConfig.get_timeout(OperationType.ADMIN) == 30.0
        assert TimeoutConfig.get_timeout(OperationType.LOCK) == 10.0
        assert TimeoutConfig.get_timeout(OperationType.SESSION) == 60.0


class TestRetryConfig:
    """Tests for retry configuration."""
    
    def test_retry_defaults(self):
        """Test retry default values."""
        assert RetryConfig.MAX_ATTEMPTS == 3
        assert RetryConfig.INITIAL_BACKOFF == 1.0
        assert RetryConfig.MAX_BACKOFF == 30.0
        assert RetryConfig.BACKOFF_MULTIPLIER == 2.0


class TestWithTimeout:
    """Tests for with_timeout decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_operation_within_timeout(self):
        """Test successful operation completes within timeout."""
        @with_timeout(OperationType.SEND, timeout_seconds=1.0)
        async def quick_operation():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await quick_operation()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_operation_timeout(self):
        """Test operation raises timeout error."""
        @with_timeout(OperationType.SEND, timeout_seconds=0.1)
        async def slow_operation():
            await asyncio.sleep(1.0)
            return "should not reach"
        
        with pytest.raises(ServiceBusTimeoutError) as exc_info:
            await slow_operation()
        
        error = exc_info.value
        assert error.error_code == "OperationTimeout"
        assert "slow_operation" in error.message
        assert error.details["timeout_seconds"] == 0.1
    
    @pytest.mark.asyncio
    async def test_default_timeout_used(self):
        """Test default timeout is used when not specified."""
        @with_timeout(OperationType.LOCK)
        async def operation_with_default_timeout():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await operation_with_default_timeout()
        assert result == "success"


class TestWithRetry:
    """Tests for with_retry decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test successful operation on first attempt."""
        call_count = 0
        
        @with_retry(max_attempts=3)
        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await successful_operation()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Test retry on transient error."""
        call_count = 0
        
        @with_retry(max_attempts=3, initial_backoff=0.01)
        async def transient_failure():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ServiceBusConnectionError("temporary failure")
            return "success"
        
        result = await transient_failure()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test max retries exceeded."""
        call_count = 0
        
        @with_retry(max_attempts=3, initial_backoff=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ServiceBusConnectionError("persistent failure")
        
        with pytest.raises(ServiceBusConnectionError):
            await always_fails()
        
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_no_retry_on_non_transient_error(self):
        """Test no retry on non-transient error."""
        call_count = 0
        
        @with_retry(max_attempts=3)
        async def non_transient_failure():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")
        
        with pytest.raises(ValueError):
            await non_transient_failure()
        
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff timing."""
        import time
        
        call_times = []
        
        @with_retry(max_attempts=3, initial_backoff=0.1, backoff_multiplier=2.0)
        async def failing_operation():
            call_times.append(time.time())
            raise ServiceBusConnectionError("fail")
        
        with pytest.raises(ServiceBusConnectionError):
            await failing_operation()
        
        assert len(call_times) == 3
        
        # Check backoff delays (with some tolerance)
        delay_1 = call_times[1] - call_times[0]
        delay_2 = call_times[2] - call_times[1]
        
        # First delay should be ~0.1s, second ~0.2s
        assert 0.08 < delay_1 < 0.15
        assert 0.15 < delay_2 < 0.25
    
    @pytest.mark.asyncio
    async def test_custom_retry_condition(self):
        """Test custom retry condition function."""
        call_count = 0
        
        def retry_on_value_error(error):
            return isinstance(error, ValueError)
        
        @with_retry(max_attempts=3, initial_backoff=0.01, retry_on=retry_on_value_error)
        async def custom_retry_logic():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("retryable")
            return "success"
        
        result = await custom_retry_logic()
        assert result == "success"
        assert call_count == 3


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""
    
    @pytest.mark.asyncio
    async def test_closed_state_allows_calls(self):
        """Test closed circuit allows calls."""
        breaker = CircuitBreaker("test", failure_threshold=3)
        
        async def successful_operation():
            return "success"
        
        result = await breaker.call(successful_operation)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        """Test circuit opens after threshold failures."""
        breaker = CircuitBreaker("test", failure_threshold=3)
        
        async def failing_operation():
            raise ValueError("failure")
        
        # First 3 failures should open the circuit
        for i in range(3):
            with pytest.raises(ValueError):
                await breaker.call(failing_operation)
        
        assert breaker.state == CircuitState.OPEN
        
        # Next call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError) as exc_info:
            await breaker.call(failing_operation)
        
        error = exc_info.value
        assert error.error_code == "CircuitBreakerOpen"
        assert "test" in error.message
    
    @pytest.mark.asyncio
    async def test_half_open_state_after_reset_timeout(self):
        """Test circuit transitions to half-open after reset timeout."""
        breaker = CircuitBreaker("test", failure_threshold=2, reset_timeout=0.1)
        
        async def operation():
            return "success"
        
        # Cause failures to open circuit
        async def failing_operation():
            raise ValueError("failure")
        
        for i in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_operation)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for reset timeout
        await asyncio.sleep(0.15)
        
        # Next call should be allowed (half-open)
        result = await breaker.call(operation)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """Test failed call in half-open reopens circuit."""
        breaker = CircuitBreaker("test", failure_threshold=2, reset_timeout=0.1)
        
        async def failing_operation():
            raise ValueError("failure")
        
        # Open circuit
        for i in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_operation)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for reset
        await asyncio.sleep(0.15)
        
        # Fail in half-open
        with pytest.raises(ValueError):
            await breaker.call(failing_operation)
        
        assert breaker.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_manual_reset(self):
        """Test manual circuit reset."""
        breaker = CircuitBreaker("test", failure_threshold=2)
        
        async def failing_operation():
            raise ValueError("failure")
        
        # Open circuit
        for i in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_operation)
        
        assert breaker.state == CircuitState.OPEN
        
        # Manual reset
        await breaker.reset()
        assert breaker.state == CircuitState.CLOSED


class TestWithCircuitBreaker:
    """Tests for with_circuit_breaker decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_creates_breaker(self):
        """Test decorator creates and uses circuit breaker."""
        call_count = 0
        
        @with_circuit_breaker("test-op", failure_threshold=2)
        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("failure")
            return "success"
        
        # First 2 calls fail
        with pytest.raises(ValueError):
            await operation()
        with pytest.raises(ValueError):
            await operation()
        
        # Circuit should be open
        with pytest.raises(CircuitBreakerError):
            await operation()
    
    @pytest.mark.asyncio
    async def test_get_circuit_breaker_reuses_instance(self):
        """Test get_circuit_breaker reuses same instance."""
        breaker1 = get_circuit_breaker("test-circuit")
        breaker2 = get_circuit_breaker("test-circuit")
        
        assert breaker1 is breaker2


class TestIntegrationCombinations:
    """Tests for combined resilience patterns."""
    
    @pytest.mark.asyncio
    async def test_timeout_with_retry(self):
        """Test combining timeout and retry decorators."""
        call_count = 0
        
        @with_retry(max_attempts=3, initial_backoff=0.01)
        @with_timeout(OperationType.SEND, timeout_seconds=0.5)
        async def operation_with_both():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ServiceBusConnectionError("transient")
            await asyncio.sleep(0.1)
            return "success"
        
        result = await operation_with_both()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_all_three_patterns(self):
        """Test timeout + retry + circuit breaker together."""
        call_count = 0
        
        @with_circuit_breaker("complex-op", failure_threshold=5)
        @with_retry(max_attempts=2, initial_backoff=0.01)
        @with_timeout(OperationType.SEND, timeout_seconds=0.5)
        async def complex_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ServiceBusConnectionError("transient")
            return "success"
        
        result = await complex_operation()
        assert result == "success"
        assert call_count == 2
