"""
Tests for Service Bus Metrics and Health Checks

Comprehensive tests for Prometheus metrics collection,
health check endpoints, and monitoring functionality.

Author: Ayodele Oladeji
Date: 2025-12-08
"""

import asyncio
import pytest
from datetime import datetime, timezone

from localzure.services.servicebus.backend import ServiceBusBackend
from localzure.services.servicebus.metrics import ServiceBusMetrics, get_metrics, reset_metrics
from localzure.services.servicebus.health_check import (
    ServiceBusHealthCheck,
    HealthStatus,
    init_health_check,
    reset_health_check,
)
from localzure.services.servicebus.models import (
    QueueProperties,
    SendMessageRequest,
    ReceiveMode,
)
from prometheus_client import REGISTRY


class TestServiceBusMetrics:
    """Test cases for Prometheus metrics collection."""
    
    @pytest.fixture
    def metrics(self):
        """Create metrics instance for testing."""
        reset_metrics()
        return get_metrics()
    
    @pytest.fixture
    async def backend(self):
        """Create backend instance for testing."""
        backend = ServiceBusBackend()
        await backend.create_queue("test-queue")
        yield backend
    
    def test_track_message_sent(self, metrics):
        """Test tracking sent messages."""
        metrics.track_message_sent('queue', 'test-queue', 1024, 0.05)
        
        # Verify counter incremented
        counter_value = metrics.messages_sent_total.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert counter_value == 1
    
    def test_track_message_received(self, metrics):
        """Test tracking received messages."""
        metrics.track_message_received('queue', 'test-queue', 0.03)
        
        counter_value = metrics.messages_received_total.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert counter_value == 1
    
    def test_track_message_completed(self, metrics):
        """Test tracking completed messages."""
        metrics.track_message_completed('queue', 'test-queue')
        
        counter_value = metrics.messages_completed_total.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert counter_value == 1
    
    def test_track_message_abandoned(self, metrics):
        """Test tracking abandoned messages."""
        metrics.track_message_abandoned('queue', 'test-queue')
        
        counter_value = metrics.messages_abandoned_total.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert counter_value == 1
    
    def test_track_message_deadlettered(self, metrics):
        """Test tracking dead-lettered messages."""
        metrics.track_message_deadlettered('queue', 'test-queue', 'MaxDeliveryCountExceeded')
        
        counter_value = metrics.messages_deadlettered_total.labels(
            entity_type='queue',
            entity_name='test-queue',
            reason='MaxDeliveryCountExceeded'
        )._value.get()
        assert counter_value == 1
    
    def test_track_multiple_messages(self, metrics):
        """Test tracking multiple messages increments counter."""
        metrics.track_message_sent('queue', 'test-queue', 1024, 0.05)
        metrics.track_message_sent('queue', 'test-queue', 2048, 0.06)
        metrics.track_message_sent('queue', 'test-queue', 512, 0.04)
        
        counter_value = metrics.messages_sent_total.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert counter_value == 3
    
    def test_track_error(self, metrics):
        """Test tracking errors."""
        metrics.track_error('send_message', 'QueueNotFoundError')
        
        counter_value = metrics.errors_total.labels(
            operation='send_message',
            error_type='QueueNotFoundError'
        )._value.get()
        assert counter_value == 1
    
    def test_update_active_messages_gauge(self, metrics):
        """Test updating active messages gauge."""
        metrics.update_active_messages('queue', 'test-queue', 5)
        
        gauge_value = metrics.active_messages.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert gauge_value == 5
    
    def test_update_deadletter_messages_gauge(self, metrics):
        """Test updating dead-letter messages gauge."""
        metrics.update_deadletter_messages('queue', 'test-queue', 2)
        
        gauge_value = metrics.deadletter_messages.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert gauge_value == 2
    
    def test_update_scheduled_messages_gauge(self, metrics):
        """Test updating scheduled messages gauge."""
        metrics.update_scheduled_messages('queue', 'test-queue', 3)
        
        gauge_value = metrics.scheduled_messages.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert gauge_value == 3
    
    def test_update_active_locks_gauge(self, metrics):
        """Test updating active locks gauge."""
        metrics.update_active_locks('queue', 'test-queue', 4)
        
        gauge_value = metrics.active_locks.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert gauge_value == 4
    
    def test_update_entity_count_gauge(self, metrics):
        """Test updating entity count gauge."""
        metrics.update_entity_count('queue', 10)
        
        gauge_value = metrics.entity_count.labels(
            entity_type='queue'
        )._value.get()
        assert gauge_value == 10
    
    def test_track_filter_evaluation(self, metrics):
        """Test tracking filter evaluation time."""
        metrics.track_filter_evaluation(0.002)
        
        # Check histogram recorded the value
        histogram = metrics.filter_evaluation_seconds
        assert histogram._sum.get() > 0
    
    def test_generate_metrics(self, metrics):
        """Test generating Prometheus metrics output."""
        metrics.track_message_sent('queue', 'test-queue', 1024, 0.05)
        
        output = metrics.generate_metrics()
        assert isinstance(output, bytes)
        # Note: Output includes default Python metrics, so check for any metrics
        assert len(output) > 0
        assert b'#' in output  # Prometheus format includes comments
    
    def test_metrics_labels_separation(self, metrics):
        """Test that metrics for different entities are tracked separately."""
        metrics.track_message_sent('queue', 'queue-a', 1024, 0.05)
        metrics.track_message_sent('queue', 'queue-b', 2048, 0.06)
        
        counter_a = metrics.messages_sent_total.labels(
            entity_type='queue',
            entity_name='queue-a'
        )._value.get()
        counter_b = metrics.messages_sent_total.labels(
            entity_type='queue',
            entity_name='queue-b'
        )._value.get()
        
        assert counter_a == 1
        assert counter_b == 1
    
    @pytest.mark.asyncio
    async def test_backend_metrics_integration_send(self, backend):
        """Test backend integration - send message tracks metrics."""
        metrics = get_metrics()
        
        request = SendMessageRequest(body="Test message")
        await backend.send_message("test-queue", request)
        
        counter_value = metrics.messages_sent_total.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert counter_value >= 1
    
    @pytest.mark.asyncio
    async def test_backend_metrics_integration_receive(self, backend):
        """Test backend integration - receive message tracks metrics."""
        metrics = get_metrics()
        
        # Send a message first
        request = SendMessageRequest(body="Test message")
        await backend.send_message("test-queue", request)
        
        # Receive it
        await backend.receive_message("test-queue", ReceiveMode.PEEK_LOCK)
        
        counter_value = metrics.messages_received_total.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert counter_value >= 1
    
    @pytest.mark.asyncio
    async def test_backend_metrics_integration_complete(self, backend):
        """Test backend integration - complete message tracks metrics."""
        metrics = get_metrics()
        
        # Send and receive a message
        request = SendMessageRequest(body="Test message")
        await backend.send_message("test-queue", request)
        message = await backend.receive_message("test-queue", ReceiveMode.PEEK_LOCK)
        
        # Complete it
        await backend.complete_message("test-queue", message.message_id, message.lock_token)
        
        counter_value = metrics.messages_completed_total.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert counter_value >= 1
    
    @pytest.mark.asyncio
    async def test_backend_metrics_integration_abandon(self, backend):
        """Test backend integration - abandon message tracks metrics."""
        metrics = get_metrics()
        
        # Send and receive a message
        request = SendMessageRequest(body="Test message")
        await backend.send_message("test-queue", request)
        message = await backend.receive_message("test-queue", ReceiveMode.PEEK_LOCK)
        
        # Abandon it
        await backend.abandon_message("test-queue", message.message_id, message.lock_token)
        
        counter_value = metrics.messages_abandoned_total.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert counter_value >= 1
    
    @pytest.mark.asyncio
    async def test_backend_metrics_integration_deadletter(self, backend):
        """Test backend integration - dead-letter message tracks metrics."""
        metrics = get_metrics()
        
        # Send and receive a message
        request = SendMessageRequest(body="Test message")
        await backend.send_message("test-queue", request)
        message = await backend.receive_message("test-queue", ReceiveMode.PEEK_LOCK)
        
        # Dead-letter it
        await backend.dead_letter_message(
            "test-queue",
            message.message_id,
            message.lock_token,
            "TestReason",
            "Test dead-letter"
        )
        
        counter_value = metrics.messages_deadlettered_total.labels(
            entity_type='queue',
            entity_name='test-queue',
            reason='TestReason'
        )._value.get()
        assert counter_value >= 1


class TestHealthCheck:
    """Test cases for health check functionality."""
    
    @pytest.fixture
    async def backend(self):
        """Create backend instance for testing."""
        backend = ServiceBusBackend()
        await backend.create_queue("test-queue")
        return backend
    
    @pytest.fixture
    def health_check(self, backend):
        """Create health check instance for testing."""
        reset_health_check()
        return init_health_check(backend)
    
    @pytest.mark.asyncio
    async def test_get_health_status(self, health_check):
        """Test getting health status."""
        status = await health_check.get_health_status()
        
        assert "status" in status
        assert "timestamp" in status
        assert "uptime_seconds" in status
        assert "version" in status
        assert "checks" in status
        assert status["version"] == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_health_status_healthy(self, health_check):
        """Test health status is healthy when backend is working."""
        status = await health_check.get_health_status()
        
        assert status["status"] == HealthStatus.HEALTHY.value
        assert status["checks"]["storage"]["status"] == "healthy"
        assert status["checks"]["backend"]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_is_ready(self, health_check):
        """Test readiness check returns True when ready."""
        is_ready = await health_check.is_ready()
        assert is_ready is True
    
    @pytest.mark.asyncio
    async def test_is_alive(self, health_check):
        """Test liveness check returns True when alive."""
        is_alive = await health_check.is_alive()
        assert is_alive is True
    
    def test_get_uptime(self, health_check):
        """Test getting service uptime."""
        import time
        time.sleep(0.1)
        uptime = health_check.get_uptime()
        assert uptime >= 0.1
    
    @pytest.mark.asyncio
    async def test_get_last_check_status(self, health_check):
        """Test getting last check status."""
        # Initially should be None
        assert health_check.get_last_check_status() is None
        
        # After health check, should have status
        await health_check.get_health_status()
        last_status = health_check.get_last_check_status()
        assert last_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
    
    @pytest.mark.asyncio
    async def test_get_last_check_time(self, health_check):
        """Test getting last check timestamp."""
        # Initially should be None
        assert health_check.get_last_check_time() is None
        
        # After health check, should have timestamp
        await health_check.get_health_status()
        last_time = health_check.get_last_check_time()
        assert isinstance(last_time, datetime)
    
    def test_reset_failure_count(self, health_check):
        """Test resetting failure counter."""
        health_check._consecutive_failures = 5
        health_check.reset_failure_count()
        assert health_check._consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_health_check_without_backend(self):
        """Test health check with no backend initialized."""
        reset_health_check()
        health_check = init_health_check(None)
        
        status = await health_check.get_health_status()
        assert status["status"] == HealthStatus.UNHEALTHY.value
        
        is_ready = await health_check.is_ready()
        assert is_ready is False
        
        is_alive = await health_check.is_alive()
        assert is_alive is False


class TestBackgroundMetricsCollection:
    """Test cases for background gauge metrics collection."""
    
    @pytest.fixture
    async def backend(self):
        """Create backend instance for testing."""
        backend = ServiceBusBackend()
        return backend
    
    @pytest.mark.asyncio
    async def test_start_metrics_collection(self, backend):
        """Test starting background metrics collection."""
        await backend.start_metrics_collection()
        assert backend._metrics_running is True
        assert backend._metrics_task is not None
        
        # Clean up
        await backend.stop_metrics_collection()
    
    @pytest.mark.asyncio
    async def test_stop_metrics_collection(self, backend):
        """Test stopping background metrics collection."""
        await backend.start_metrics_collection()
        await backend.stop_metrics_collection()
        
        assert backend._metrics_running is False
    
    @pytest.mark.asyncio
    async def test_metrics_collection_updates_gauges(self, backend):
        """Test that metrics collection updates gauge values."""
        metrics = get_metrics()
        
        # Create queue and send messages
        await backend.create_queue("test-queue")
        request = SendMessageRequest(body="Test message 1")
        await backend.send_message("test-queue", request)
        request = SendMessageRequest(body="Test message 2")
        await backend.send_message("test-queue", request)
        
        # Manually trigger metrics collection
        await backend._collect_gauge_metrics()
        
        # Check entity count gauge
        queue_count = metrics.entity_count.labels(entity_type='queue')._value.get()
        assert queue_count >= 1
        
        # Check active messages gauge
        active_count = metrics.active_messages.labels(
            entity_type='queue',
            entity_name='test-queue'
        )._value.get()
        assert active_count == 2
    
    @pytest.mark.asyncio
    async def test_metrics_collection_handles_errors(self, backend):
        """Test that metrics collection handles errors gracefully."""
        await backend.start_metrics_collection()
        
        # Should not crash even with errors
        await asyncio.sleep(0.2)
        
        await backend.stop_metrics_collection()
        assert backend._metrics_running is False


class TestMetricsPerformance:
    """Test cases for metrics performance overhead."""
    
    @pytest.mark.asyncio
    async def test_metrics_overhead_is_minimal(self):
        """Test that metrics tracking has minimal performance overhead."""
        import time
        
        backend = ServiceBusBackend()
        await backend.create_queue("test-queue")
        
        # Send 100 messages and measure time
        start_time = time.perf_counter()
        for i in range(100):
            request = SendMessageRequest(body=f"Test message {i}")
            await backend.send_message("test-queue", request)
        duration = time.perf_counter() - start_time
        
        # Should complete in reasonable time (< 1 second for 100 messages)
        assert duration < 1.0, f"Metrics overhead too high: {duration}s for 100 messages"
