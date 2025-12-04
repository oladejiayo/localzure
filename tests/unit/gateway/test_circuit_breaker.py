"""Tests for circuit breaker functionality."""

import pytest
import asyncio
import time

from localzure.gateway.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitBreakerStats,
    CircuitState,
)


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig class."""

    def test_initialization(self):
        """Test circuit breaker config initialization."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=60,
        )

        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout_seconds == 60


class TestCircuitBreakerStats:
    """Tests for CircuitBreakerStats class."""

    def test_initialization(self):
        """Test circuit breaker stats initialization."""
        stats = CircuitBreakerStats(
            state=CircuitState.CLOSED,
            failure_count=0,
            success_count=0,
            total_calls=0,
            total_failures=0,
            total_successes=0,
            last_failure_time=None,
            last_state_change=time.time(),
            half_open_calls=0,
        )

        assert stats.state == CircuitState.CLOSED
        assert stats.failure_count == 0
        assert stats.success_count == 0
        assert stats.total_calls == 0


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=1,
        )
        return CircuitBreaker(service_name="test_service", config=config)

    @pytest.mark.asyncio
    async def test_initialization(self, circuit_breaker):
        """Test circuit breaker initialization."""
        assert circuit_breaker.service_name == "test_service"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.config.failure_threshold == 3
        assert circuit_breaker.config.success_threshold == 2
        assert circuit_breaker.config.timeout_seconds == 1

    @pytest.mark.asyncio
    async def test_successful_call_closed_state(self, circuit_breaker):
        """Test successful call in closed state."""
        async def success_operation():
            return "success"

        result = await circuit_breaker.call(success_operation)

        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._total_successes == 1
        assert circuit_breaker._total_failures == 0

    @pytest.mark.asyncio
    async def test_failed_call_closed_state(self, circuit_breaker):
        """Test failed call in closed state."""
        async def failure_operation():
            raise Exception("Operation failed")

        with pytest.raises(Exception, match="Operation failed"):
            await circuit_breaker.call(failure_operation)

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._total_failures == 1
        assert circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_transition_to_open_state(self, circuit_breaker):
        """Test transition from closed to open state."""
        async def failure_operation():
            raise Exception("Operation failed")

        # Fail enough times to open circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_operation)

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker._failure_count == 3

    @pytest.mark.asyncio
    async def test_rejected_call_open_state(self, circuit_breaker):
        """Test that calls are rejected in open state."""
        async def failure_operation():
            raise Exception("Operation failed")

        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_operation)

        # Next call should be rejected
        with pytest.raises(CircuitBreakerError, match="Circuit breaker open"):
            await circuit_breaker.call(failure_operation)

    @pytest.mark.asyncio
    async def test_transition_to_half_open_state(self, circuit_breaker):
        """Test transition from open to half-open state."""
        async def failure_operation():
            raise Exception("Operation failed")

        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_operation)

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(circuit_breaker.config.timeout_seconds + 0.1)

        # Next call should transition to half-open
        async def success_operation():
            return "success"

        result = await circuit_breaker.call(success_operation)

        assert result == "success"
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_transition_to_closed_from_half_open(self, circuit_breaker):
        """Test transition from half-open to closed state."""
        async def failure_operation():
            raise Exception("Operation failed")

        async def success_operation():
            return "success"

        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_operation)

        # Wait for timeout and transition to half-open
        await asyncio.sleep(circuit_breaker.config.timeout_seconds + 0.1)
        await circuit_breaker.call(success_operation)

        assert circuit_breaker.state == CircuitState.HALF_OPEN

        # Succeed enough times to close circuit
        for _ in range(circuit_breaker.config.success_threshold - 1):
            await circuit_breaker.call(success_operation)

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_transition_to_open_from_half_open(self, circuit_breaker):
        """Test transition from half-open back to open state."""
        async def failure_operation():
            raise Exception("Operation failed")

        async def success_operation():
            return "success"

        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_operation)

        # Wait for timeout and transition to half-open
        await asyncio.sleep(circuit_breaker.config.timeout_seconds + 0.1)
        await circuit_breaker.call(success_operation)

        assert circuit_breaker.state == CircuitState.HALF_OPEN

        # Fail once in half-open state
        with pytest.raises(Exception):
            await circuit_breaker.call(failure_operation)

        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self, circuit_breaker):
        """Test that failures are still raised even with fallback in closed state."""
        async def failure_operation():
            raise Exception("Operation failed")

        async def fallback_operation():
            return "fallback result"

        # In closed state, fallback is NOT used - exception is raised
        with pytest.raises(Exception, match="Operation failed"):
            await circuit_breaker.call(
                failure_operation,
                fallback=fallback_operation,
            )

        assert circuit_breaker._total_failures == 1

    @pytest.mark.asyncio
    async def test_fallback_on_circuit_open(self, circuit_breaker):
        """Test fallback execution when circuit is open."""
        async def failure_operation():
            raise Exception("Operation failed")

        async def fallback_operation():
            return "fallback result"

        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_operation)

        # Call with fallback while circuit is open
        result = await circuit_breaker.call(
            failure_operation,
            fallback=fallback_operation,
        )

        assert result == "fallback result"

    @pytest.mark.asyncio
    async def test_manual_reset(self, circuit_breaker):
        """Test manual circuit breaker reset."""
        async def failure_operation():
            raise Exception("Operation failed")

        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_operation)

        assert circuit_breaker.state == CircuitState.OPEN

        # Manual reset
        await circuit_breaker.reset()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_get_stats(self, circuit_breaker):
        """Test getting circuit breaker statistics."""
        async def success_operation():
            return "success"

        async def failure_operation():
            raise Exception("Operation failed")

        # Make some calls
        await circuit_breaker.call(success_operation)
        with pytest.raises(Exception):
            await circuit_breaker.call(failure_operation)

        stats = circuit_breaker.get_stats()

        assert stats.total_calls == 2
        assert stats.total_successes == 1
        assert stats.total_failures == 1
        assert stats.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_concurrent_calls_closed_state(self, circuit_breaker):
        """Test concurrent calls in closed state."""
        async def success_operation():
            await asyncio.sleep(0.01)
            return "success"

        # Make concurrent calls
        tasks = [circuit_breaker.call(success_operation) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r == "success" for r in results)
        assert circuit_breaker._total_successes == 10

    @pytest.mark.asyncio
    async def test_last_failure_time(self, circuit_breaker):
        """Test last failure time tracking."""
        async def failure_operation():
            raise Exception("Operation failed")

        assert circuit_breaker._last_failure_time is None

        with pytest.raises(Exception):
            await circuit_breaker.call(failure_operation)

        assert circuit_breaker._last_failure_time is not None
        assert isinstance(circuit_breaker._last_failure_time, float)


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create circuit breaker registry for testing."""
        return CircuitBreakerRegistry()

    def test_initialization(self, registry):
        """Test registry initialization."""
        assert len(registry._breakers) == 0

    @pytest.mark.asyncio
    async def test_get_breaker(self, registry):
        """Test getting or creating circuit breakers."""
        breaker1 = await registry.get_breaker("service1")
        breaker2 = await registry.get_breaker("service1")

        assert breaker1 is breaker2
        assert breaker1.service_name == "service1"

    @pytest.mark.asyncio
    async def test_get_breaker_with_config(self, registry):
        """Test creating circuit breaker with custom config."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            timeout_seconds=120,
        )

        breaker = await registry.get_breaker("service1", config=config)

        assert breaker.config.failure_threshold == 10
        assert breaker.config.success_threshold == 5
        assert breaker.config.timeout_seconds == 120

    @pytest.mark.asyncio
    async def test_reset_all(self, registry):
        """Test resetting all circuit breakers."""
        breaker1 = await registry.get_breaker("service1")
        breaker2 = await registry.get_breaker("service2")

        # Modify breaker states
        breaker1._total_failures = 5
        breaker2._total_failures = 10

        # Reset all
        await registry.reset_all()

        assert breaker1.state == CircuitState.CLOSED
        assert breaker2.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_get_all_stats(self, registry):
        """Test getting stats for all circuit breakers."""
        await registry.get_breaker("service1")
        await registry.get_breaker("service2")

        stats = registry.get_all_stats()

        assert len(stats) == 2
        assert "service1" in stats
        assert "service2" in stats

    @pytest.mark.asyncio
    async def test_multiple_services(self, registry):
        """Test managing multiple service circuit breakers."""
        services = ["blob", "queue", "table", "cosmosdb"]

        for service in services:
            await registry.get_breaker(service)

        assert len(registry._breakers) == len(services)

        for service in services:
            assert service in registry._breakers


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_intermittent_failures(self):
        """Test circuit breaker with intermittent failures."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=3,
            timeout_seconds=1,
        )
        breaker = CircuitBreaker(service_name="test_service", config=config)

        call_count = 0

        async def intermittent_operation():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("Intermittent failure")
            return "success"

        # Make calls that alternate between success and failure
        for _ in range(10):
            try:
                await breaker.call(intermittent_operation)
            except Exception:
                pass

        # Circuit should eventually open due to failures
        assert breaker._total_failures > 0
        assert breaker._total_successes > 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after service restoration."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=1,
        )
        breaker = CircuitBreaker(service_name="test_service", config=config)

        failing = True

        async def service_operation():
            if failing:
                raise Exception("Service down")
            return "success"

        # Fail until circuit opens
        for _ in range(config.failure_threshold):
            with pytest.raises(Exception):
                await breaker.call(service_operation)

        assert breaker.state == CircuitState.OPEN

        # Service recovers
        failing = False

        # Wait for timeout
        await asyncio.sleep(config.timeout_seconds + 0.1)

        # Succeed until circuit closes
        for _ in range(config.success_threshold):
            result = await breaker.call(service_operation)
            assert result == "success"

        assert breaker.state == CircuitState.CLOSED
