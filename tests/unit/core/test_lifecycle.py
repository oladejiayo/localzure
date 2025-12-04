"""
Unit tests for LocalZure Lifecycle Manager.

Tests signal handling, graceful shutdown, request tracking, and startup rollback.
"""

import asyncio
import signal
import pytest
from unittest.mock import AsyncMock, Mock, patch
import time

from localzure.core.lifecycle import (
    LifecycleManager,
    LifecycleState,
    ShutdownReason,
    RequestTracker
)


class TestRequestTracker:
    """Test request tracking functionality."""
    
    @pytest.mark.asyncio
    async def test_request_lifecycle(self):
        """Test basic request tracking."""
        tracker = RequestTracker()
        
        # Start a request
        assert await tracker.start_request("req-1") is True
        assert tracker.get_in_flight_count() == 1
        
        # Start another request
        assert await tracker.start_request("req-2") is True
        assert tracker.get_in_flight_count() == 2
        
        # End first request
        await tracker.end_request("req-1")
        assert tracker.get_in_flight_count() == 1
        
        # End second request
        await tracker.end_request("req-2")
        assert tracker.get_in_flight_count() == 0
    
    @pytest.mark.asyncio
    async def test_draining_mode(self):
        """Test request rejection during draining."""
        tracker = RequestTracker()
        
        # Start requests before draining
        assert await tracker.start_request("req-1") is True
        assert tracker.get_in_flight_count() == 1
        
        # Enter draining mode
        await tracker.start_draining()
        
        # New requests should be rejected
        assert await tracker.start_request("req-2") is False
        assert tracker.get_in_flight_count() == 1
        
        # Existing requests can complete
        await tracker.end_request("req-1")
        assert tracker.get_in_flight_count() == 0
    
    @pytest.mark.asyncio
    async def test_wait_for_drain_success(self):
        """Test successful drain within timeout."""
        tracker = RequestTracker()
        
        # Start requests
        await tracker.start_request("req-1")
        await tracker.start_request("req-2")
        
        await tracker.start_draining()
        
        # Complete requests in background
        async def complete_requests():
            await asyncio.sleep(0.1)
            await tracker.end_request("req-1")
            await asyncio.sleep(0.1)
            await tracker.end_request("req-2")
        
        asyncio.create_task(complete_requests())
        
        # Wait for drain
        result = await tracker.wait_for_drain(timeout=5.0)
        assert result is True
        assert tracker.get_in_flight_count() == 0
    
    @pytest.mark.asyncio
    async def test_wait_for_drain_timeout(self):
        """Test drain timeout with hanging requests."""
        tracker = RequestTracker()
        
        # Start requests that won't complete
        await tracker.start_request("req-1")
        await tracker.start_request("req-2")
        
        await tracker.start_draining()
        
        # Wait for drain with short timeout
        result = await tracker.wait_for_drain(timeout=0.5)
        assert result is False
        assert tracker.get_in_flight_count() == 2
    
    @pytest.mark.asyncio
    async def test_duplicate_request_end(self):
        """Test ending non-existent request is safe."""
        tracker = RequestTracker()
        
        await tracker.start_request("req-1")
        assert tracker.get_in_flight_count() == 1
        
        # End request twice
        await tracker.end_request("req-1")
        await tracker.end_request("req-1")  # Should not raise
        assert tracker.get_in_flight_count() == 0


class TestLifecycleManager:
    """Test lifecycle manager functionality."""
    
    def test_initialization(self):
        """Test lifecycle manager initialization."""
        manager = LifecycleManager(shutdown_timeout=45.0)
        
        assert manager.get_state() == LifecycleState.STOPPED
        assert manager.is_draining() is False
        assert manager._shutdown_timeout == 45.0
    
    def test_state_transitions(self):
        """Test state transitions and callbacks."""
        manager = LifecycleManager()
        
        # Track state changes
        states = []
        def track_state(old, new):
            states.append((old, new))
        
        manager.register_state_callback(track_state)
        
        # Transition states
        manager.set_state(LifecycleState.INITIALIZING)
        manager.set_state(LifecycleState.STARTING)
        manager.set_state(LifecycleState.RUNNING)
        
        assert len(states) == 3
        assert states[0] == (LifecycleState.STOPPED, LifecycleState.INITIALIZING)
        assert states[1] == (LifecycleState.INITIALIZING, LifecycleState.STARTING)
        assert states[2] == (LifecycleState.STARTING, LifecycleState.RUNNING)
    
    def test_state_transition_no_change(self):
        """Test setting same state doesn't trigger callback."""
        manager = LifecycleManager()
        
        callback = Mock()
        manager.register_state_callback(callback)
        
        manager.set_state(LifecycleState.STOPPED)
        callback.assert_not_called()
    
    def test_is_draining(self):
        """Test draining state detection."""
        manager = LifecycleManager()
        
        assert manager.is_draining() is False
        
        manager.set_state(LifecycleState.DRAINING)
        assert manager.is_draining() is True
        
        manager.set_state(LifecycleState.STOPPING)
        assert manager.is_draining() is False
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_success(self):
        """Test successful graceful shutdown."""
        manager = LifecycleManager(shutdown_timeout=5.0)
        manager.set_state(LifecycleState.RUNNING)
        
        # Register shutdown callback
        callback = AsyncMock()
        manager.register_shutdown_callback(callback)
        
        # Perform shutdown
        result = await manager.graceful_shutdown(reason=ShutdownReason.MANUAL)
        
        assert result is True
        assert manager.get_state() == LifecycleState.STOPPED
        callback.assert_awaited_once_with(ShutdownReason.MANUAL)
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_requests(self):
        """Test graceful shutdown with in-flight requests."""
        manager = LifecycleManager(shutdown_timeout=5.0)
        manager.set_state(LifecycleState.RUNNING)
        
        tracker = manager.get_request_tracker()
        
        # Start some requests
        await tracker.start_request("req-1")
        await tracker.start_request("req-2")
        
        # Complete requests in background
        async def complete_requests():
            await asyncio.sleep(0.2)
            await tracker.end_request("req-1")
            await asyncio.sleep(0.2)
            await tracker.end_request("req-2")
        
        asyncio.create_task(complete_requests())
        
        # Perform shutdown
        start = time.time()
        result = await manager.graceful_shutdown()
        duration = time.time() - start
        
        assert result is True
        assert duration < 1.0  # Should complete quickly
        assert manager.get_state() == LifecycleState.STOPPED
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_timeout(self):
        """Test forced shutdown after timeout."""
        manager = LifecycleManager(shutdown_timeout=0.5)
        manager.set_state(LifecycleState.RUNNING)
        
        tracker = manager.get_request_tracker()
        
        # Start requests that won't complete
        await tracker.start_request("req-1")
        await tracker.start_request("req-2")
        
        # Perform shutdown
        start = time.time()
        result = await manager.graceful_shutdown()
        duration = time.time() - start
        
        assert result is False  # Forced shutdown
        assert duration >= 0.5  # Took at least timeout duration
        assert manager.get_state() == LifecycleState.STOPPED
    
    @pytest.mark.asyncio
    async def test_shutdown_callback_timeout(self):
        """Test shutdown callback timeout."""
        manager = LifecycleManager(shutdown_timeout=1.0)
        manager.set_state(LifecycleState.RUNNING)
        
        # Register slow callback
        async def slow_callback(reason):
            await asyncio.sleep(10.0)
        
        manager.register_shutdown_callback(slow_callback)
        
        # Perform shutdown
        start = time.time()
        result = await manager.graceful_shutdown()
        duration = time.time() - start
        
        assert result is False  # Forced due to callback timeout
        assert duration < 2.0  # Should not wait full 10s
        assert manager.get_state() == LifecycleState.STOPPED
    
    @pytest.mark.asyncio
    async def test_shutdown_callback_error(self):
        """Test shutdown continues despite callback error."""
        manager = LifecycleManager()
        manager.set_state(LifecycleState.RUNNING)
        
        # Register callbacks
        async def error_callback(reason):
            raise ValueError("Test error")
        
        callback2 = AsyncMock()
        
        manager.register_shutdown_callback(error_callback)
        manager.register_shutdown_callback(callback2)
        
        # Perform shutdown
        result = await manager.graceful_shutdown()
        
        assert result is True
        assert manager.get_state() == LifecycleState.STOPPED
        callback2.assert_awaited_once()  # Second callback still executed
    
    @pytest.mark.asyncio
    async def test_startup_tracking(self):
        """Test service startup tracking."""
        manager = LifecycleManager()
        
        manager.track_service_startup("service1")
        manager.track_service_startup("service2")
        manager.track_service_startup("service3")
        
        metrics = manager.get_metrics()
        assert metrics["startup_services_tracked"] == 3
    
    @pytest.mark.asyncio
    async def test_rollback_startup(self):
        """Test startup rollback."""
        manager = LifecycleManager()
        
        # Track service startups
        manager.track_service_startup("service1")
        manager.track_service_startup("service2")
        manager.track_service_startup("service3")
        
        # Mock stop callback
        stopped_services = []
        async def stop_service(name):
            stopped_services.append(name)
        
        # Rollback
        await manager.rollback_startup(stop_service)
        
        # Services should be stopped in reverse order
        assert stopped_services == ["service3", "service2", "service1"]
        
        # Tracking should be cleared
        assert manager.get_metrics()["startup_services_tracked"] == 0
    
    @pytest.mark.asyncio
    async def test_rollback_startup_with_errors(self):
        """Test rollback continues despite errors."""
        manager = LifecycleManager()
        
        manager.track_service_startup("service1")
        manager.track_service_startup("service2")
        manager.track_service_startup("service3")
        
        stopped_services = []
        async def stop_service(name):
            stopped_services.append(name)
            if name == "service2":
                raise RuntimeError("Stop failed")
        
        # Rollback should continue despite error
        await manager.rollback_startup(stop_service)
        
        assert stopped_services == ["service3", "service2", "service1"]
    
    def test_clear_startup_tracking(self):
        """Test clearing startup tracking."""
        manager = LifecycleManager()
        
        manager.track_service_startup("service1")
        manager.track_service_startup("service2")
        
        manager.clear_startup_tracking()
        
        assert manager.get_metrics()["startup_services_tracked"] == 0
    
    @pytest.mark.asyncio
    async def test_wait_for_shutdown_signal(self):
        """Test waiting for shutdown signal."""
        manager = LifecycleManager(enable_signal_handlers=False)
        
        # Simulate signal in background
        async def send_signal():
            await asyncio.sleep(0.1)
            manager._signal_received = signal.SIGTERM
            manager._shutdown_event.set()
        
        asyncio.create_task(send_signal())
        
        # Wait for signal
        sig = await manager.wait_for_shutdown_signal()
        assert sig == signal.SIGTERM
    
    def test_get_metrics(self):
        """Test metrics collection."""
        manager = LifecycleManager(shutdown_timeout=60.0)
        manager.set_state(LifecycleState.RUNNING)
        
        metrics = manager.get_metrics()
        
        assert metrics["state"] == "running"
        assert metrics["in_flight_requests"] == 0
        assert metrics["shutdown_timeout"] == 60.0
        assert metrics["signal_received"] is None
        assert metrics["startup_services_tracked"] == 0
    
    def test_sync_shutdown_callback(self):
        """Test synchronous shutdown callback."""
        manager = LifecycleManager()
        manager.set_state(LifecycleState.RUNNING)
        
        callback_called = []
        def sync_callback(reason):
            callback_called.append(reason)
        
        manager.register_shutdown_callback(sync_callback)
        
        # Run shutdown
        result = asyncio.run(manager.graceful_shutdown(ShutdownReason.ERROR))
        
        assert result is True
        assert callback_called == [ShutdownReason.ERROR]
    
    def test_state_callback_error_handling(self):
        """Test state callback error doesn't break manager."""
        manager = LifecycleManager()
        
        def error_callback(old, new):
            raise ValueError("Callback error")
        
        manager.register_state_callback(error_callback)
        
        # Should not raise
        manager.set_state(LifecycleState.RUNNING)
        assert manager.get_state() == LifecycleState.RUNNING


class TestSignalHandling:
    """Test signal handling functionality."""
    
    @pytest.mark.skipif(
        not hasattr(signal, 'SIGTERM'),
        reason="SIGTERM not available on this platform"
    )
    @pytest.mark.asyncio
    async def test_signal_handler_registration(self):
        """Test signal handler registration."""
        manager = LifecycleManager(enable_signal_handlers=True)
        
        # Note: Can't easily test actual signal registration without mocking
        # This test verifies the method doesn't raise
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.add_signal_handler = Mock()
            manager.register_signal_handlers()
            
            # Should register for SIGTERM and SIGINT
            assert mock_loop.return_value.add_signal_handler.call_count == 2
    
    def test_signal_handlers_disabled(self):
        """Test signal handlers can be disabled."""
        manager = LifecycleManager(enable_signal_handlers=False)
        
        # Should log but not raise
        manager.register_signal_handlers()
        
        # Manager should still function
        assert manager.get_state() == LifecycleState.STOPPED
    
    @pytest.mark.asyncio
    async def test_handle_signal(self):
        """Test signal handling."""
        manager = LifecycleManager(enable_signal_handlers=False)
        
        # Simulate signal
        await manager._handle_signal(signal.SIGTERM)
        
        # Should set shutdown event
        assert manager._shutdown_event.is_set()
        assert manager._signal_received == signal.SIGTERM


class TestShutdownReasons:
    """Test shutdown reason tracking."""
    
    @pytest.mark.asyncio
    async def test_shutdown_reason_manual(self):
        """Test manual shutdown reason."""
        manager = LifecycleManager()
        manager.set_state(LifecycleState.RUNNING)
        
        callback_reasons = []
        async def track_reason(reason):
            callback_reasons.append(reason)
        
        manager.register_shutdown_callback(track_reason)
        
        await manager.graceful_shutdown(reason=ShutdownReason.MANUAL)
        
        assert callback_reasons == [ShutdownReason.MANUAL]
    
    @pytest.mark.asyncio
    async def test_shutdown_reason_signal(self):
        """Test signal shutdown reason."""
        manager = LifecycleManager()
        manager.set_state(LifecycleState.RUNNING)
        
        callback_reasons = []
        async def track_reason(reason):
            callback_reasons.append(reason)
        
        manager.register_shutdown_callback(track_reason)
        
        await manager.graceful_shutdown(reason=ShutdownReason.SIGNAL)
        
        assert callback_reasons == [ShutdownReason.SIGNAL]
    
    @pytest.mark.asyncio
    async def test_shutdown_reason_error(self):
        """Test error shutdown reason."""
        manager = LifecycleManager()
        manager.set_state(LifecycleState.RUNNING)
        
        callback_reasons = []
        async def track_reason(reason):
            callback_reasons.append(reason)
        
        manager.register_shutdown_callback(track_reason)
        
        await manager.graceful_shutdown(reason=ShutdownReason.ERROR)
        
        assert callback_reasons == [ShutdownReason.ERROR]
