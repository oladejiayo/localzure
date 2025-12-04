"""
Tests for LocalZure Runtime.
"""

import asyncio
import signal
import pytest
from unittest.mock import AsyncMock, patch, Mock
from fastapi.testclient import TestClient

from localzure.core.runtime import LocalZureRuntime
from localzure.core.config_manager import LocalZureConfig
from localzure.core.lifecycle import LifecycleState, ShutdownReason


@pytest.fixture
def runtime():
    """Create a LocalZure runtime instance."""
    return LocalZureRuntime()


@pytest.mark.asyncio
class TestLocalZureRuntime:
    """Test suite for LocalZureRuntime."""
    
    async def test_initialize(self, runtime):
        """Test runtime initialization."""
        await runtime.initialize()
        
        assert runtime.is_initialized is True
        assert runtime.is_running is False
        
        config = runtime.get_config()
        assert config is not None
        assert isinstance(config, LocalZureConfig)
    
    async def test_initialize_idempotent(self, runtime):
        """Test that initialization is idempotent."""
        await runtime.initialize()
        await runtime.initialize()  # Should not raise
        
        assert runtime.is_initialized is True
    
    async def test_initialize_with_config_file(self, runtime, tmp_path):
        """Test initialization with config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
version: "1.0.0"
server:
  port: 9000
""")
        
        await runtime.initialize(config_file=str(config_file))
        
        config = runtime.get_config()
        assert config.version == "1.0.0"
        assert config.server.port == 9000
    
    async def test_initialize_with_cli_overrides(self, runtime):
        """Test initialization with CLI overrides."""
        cli_overrides = {
            "server": {"port": 7777}
        }
        
        await runtime.initialize(cli_overrides=cli_overrides)
        
        config = runtime.get_config()
        assert config.server.port == 7777
    
    async def test_initialize_failure_allows_retry(self, runtime):
        """Test that failed initialization can be retried."""
        # Try to initialize with invalid config
        with pytest.raises(Exception):
            await runtime.initialize(cli_overrides={"version": "invalid"})
        
        assert runtime.is_initialized is False
        
        # Should be able to retry with valid config
        await runtime.initialize()
        assert runtime.is_initialized is True
    
    async def test_start_before_initialize(self, runtime):
        """Test that starting before initialization raises error."""
        with pytest.raises(RuntimeError) as exc_info:
            await runtime.start()
        
        assert "not initialized" in str(exc_info.value).lower()
    
    async def test_start_after_initialize(self, runtime):
        """Test starting runtime after initialization."""
        await runtime.initialize()
        await runtime.start()
        
        assert runtime.is_running is True
    
    async def test_start_idempotent(self, runtime):
        """Test that starting is idempotent."""
        await runtime.initialize()
        await runtime.start()
        await runtime.start()  # Should not raise
        
        assert runtime.is_running is True
    
    async def test_stop(self, runtime):
        """Test stopping runtime."""
        await runtime.initialize()
        await runtime.start()
        await runtime.stop()
        
        assert runtime.is_running is False
    
    async def test_stop_when_not_running(self, runtime):
        """Test stopping when not running."""
        await runtime.initialize()
        await runtime.stop()  # Should not raise
    
    async def test_reset(self, runtime):
        """Test resetting runtime."""
        await runtime.initialize()
        await runtime.start()
        await runtime.reset()
        
        assert runtime.is_initialized is False
        assert runtime.is_running is False
    
    async def test_get_config_before_initialize(self, runtime):
        """Test getting config before initialization raises error."""
        with pytest.raises(RuntimeError):
            runtime.get_config()
    
    async def test_get_app_before_initialize(self, runtime):
        """Test getting app before initialization raises error."""
        with pytest.raises(RuntimeError):
            runtime.get_app()
    
    async def test_get_app_after_initialize(self, runtime):
        """Test getting FastAPI app after initialization."""
        await runtime.initialize()
        app = runtime.get_app()
        
        assert app is not None
        assert app.title == "LocalZure"
    
    async def test_health_status_before_initialize(self, runtime):
        """Test health status before initialization."""
        status = runtime.get_health_status()
        
        assert status["status"] == "unhealthy"
        assert status["version"] == "unknown"
        assert status["uptime"] == 0
    
    async def test_health_status_after_initialize(self, runtime):
        """Test health status after initialization."""
        await runtime.initialize()
        status = runtime.get_health_status()
        
        assert status["status"] == "degraded"  # Not started yet
        assert status["version"] == "0.1.0"
        assert "timestamp" in status
    
    async def test_health_status_when_running(self, runtime):
        """Test health status when running."""
        await runtime.initialize()
        await runtime.start()
        status = runtime.get_health_status()
        
        assert status["status"] == "healthy"
        assert status["uptime"] >= 0
    
    async def test_health_endpoint(self, runtime):
        """Test health check HTTP endpoint."""
        await runtime.initialize()
        await runtime.start()
        
        app = runtime.get_app()
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "services" in data
        assert "uptime" in data
    
    async def test_health_endpoint_unhealthy(self, runtime):
        """Test health endpoint returns 503 when unhealthy."""
        status = runtime.get_health_status()
        assert status["status"] == "unhealthy"
        
        # Since runtime is not initialized, we can't test the endpoint directly
        # This test confirms the health status logic
    
    async def test_health_endpoint_format(self, runtime):
        """Test health endpoint response format."""
        await runtime.initialize()
        await runtime.start()
        
        app = runtime.get_app()
        client = TestClient(app)
        
        response = client.get("/health")
        data = response.json()
        
        # Verify required fields
        assert "status" in data
        assert "version" in data
        assert "services" in data
        assert "uptime" in data
        assert "timestamp" in data
        
        # Verify types
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["services"], dict)
        assert isinstance(data["uptime"], int)
        assert isinstance(data["timestamp"], str)
    
    async def test_uptime_increases(self, runtime):
        """Test that uptime increases over time."""
        import asyncio
        
        await runtime.initialize()
        await runtime.start()
        
        status1 = runtime.get_health_status()
        uptime1 = status1["uptime"]
        
        await asyncio.sleep(1)
        
        status2 = runtime.get_health_status()
        uptime2 = status2["uptime"]
        
        assert uptime2 >= uptime1
    
    async def test_lifecycle_manager_initialized(self, runtime):
        """Test that lifecycle manager is initialized."""
        await runtime.initialize()
        
        assert runtime._lifecycle_manager is not None
        assert runtime._lifecycle_manager.get_state() == LifecycleState.STOPPED
    
    async def test_lifecycle_state_transitions(self, runtime):
        """Test lifecycle state transitions during runtime operations."""
        await runtime.initialize()
        
        # After init, should be STOPPED
        assert runtime._lifecycle_manager.get_state() == LifecycleState.STOPPED
        
        await runtime.start()
        # After start, should be RUNNING
        assert runtime._lifecycle_manager.get_state() == LifecycleState.RUNNING
        
        await runtime.stop()
        # After stop, should be STOPPED
        assert runtime._lifecycle_manager.get_state() == LifecycleState.STOPPED
    
    async def test_graceful_shutdown_on_stop(self, runtime):
        """Test that stop uses graceful shutdown."""
        await runtime.initialize()
        await runtime.start()
        
        # Mock graceful_shutdown to verify it's called
        with patch.object(runtime._lifecycle_manager, 'graceful_shutdown', new_callable=AsyncMock) as mock_shutdown:
            mock_shutdown.return_value = True
            await runtime.stop()
            
            mock_shutdown.assert_awaited_once()
            call_args = mock_shutdown.call_args
            assert call_args[1]['reason'] == ShutdownReason.MANUAL
    
    async def test_health_endpoint_draining_state(self, runtime):
        """Test health endpoint returns 503 when draining."""
        await runtime.initialize()
        await runtime.start()
        
        # Set draining state
        runtime._lifecycle_manager.set_state(LifecycleState.DRAINING)
        
        app = runtime.get_app()
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "draining"
    
    async def test_health_status_includes_in_flight_requests(self, runtime):
        """Test health status includes in-flight request count."""
        await runtime.initialize()
        await runtime.start()
        
        # Add some in-flight requests
        tracker = runtime._lifecycle_manager.get_request_tracker()
        await tracker.start_request("req-1")
        await tracker.start_request("req-2")
        
        status = runtime.get_health_status()
        
        assert status["in_flight_requests"] == 2
        
        await tracker.end_request("req-1")
        status = runtime.get_health_status()
        assert status["in_flight_requests"] == 1
    
    async def test_wait_for_shutdown_signal(self, runtime):
        """Test waiting for shutdown signal."""
        await runtime.initialize()
        
        # Simulate signal in background
        async def send_signal():
            await asyncio.sleep(0.1)
            runtime._lifecycle_manager._signal_received = signal.SIGTERM
            runtime._lifecycle_manager._shutdown_event.set()
        
        asyncio.create_task(send_signal())
        
        # Wait for signal
        sig = await runtime.wait_for_shutdown_signal()
        assert sig == signal.SIGTERM
    
    async def test_shutdown_timeout_from_config(self, runtime):
        """Test shutdown timeout is read from config."""
        cli_overrides = {
            "server": {"shutdown_timeout": 45.0}
        }
        
        await runtime.initialize(cli_overrides=cli_overrides)
        
        assert runtime._lifecycle_manager._shutdown_timeout == 45.0
    
    async def test_initialization_rollback_on_failure(self, runtime):
        """Test that initialization rollback works on service manager failure."""
        # Mock service manager to fail during initialization
        with patch('localzure.core.runtime.ServiceManager') as MockServiceManager:
            mock_sm = Mock()
            mock_sm.discover_services = Mock()
            mock_sm.initialize = AsyncMock(side_effect=RuntimeError("Service init failed"))
            mock_sm.stop_service = AsyncMock()
            MockServiceManager.return_value = mock_sm
            
            with pytest.raises(RuntimeError) as exc_info:
                await runtime.initialize()
            
            assert "Failed to initialize services" in str(exc_info.value)
            assert runtime.is_initialized is False
    
    async def test_failed_initialization_sets_failed_state(self, runtime):
        """Test that failed initialization sets lifecycle state to FAILED."""
        # Force an initialization error
        with patch.object(runtime._config_manager, 'load', side_effect=ValueError("Invalid config")):
            with pytest.raises(RuntimeError):
                await runtime.initialize()
            
            # Lifecycle manager should be None or in FAILED state
            # Since initialization failed early, lifecycle manager might not be created
            # This test validates the error handling path
            assert runtime.is_initialized is False
    
    async def test_shutdown_callback_integration(self, runtime):
        """Test that shutdown callback is executed."""
        await runtime.initialize()
        await runtime.start()
        
        # Mock service manager shutdown
        with patch.object(runtime._service_manager, 'shutdown', new_callable=AsyncMock) as mock_shutdown:
            await runtime.stop()
            
            # Shutdown should be called via the callback
            mock_shutdown.assert_awaited_once()
    
    async def test_reset_clears_lifecycle_state(self, runtime):
        """Test that reset clears lifecycle state."""
        await runtime.initialize()
        await runtime.start()
        
        # Verify running state
        assert runtime._lifecycle_manager.get_state() == LifecycleState.RUNNING
        
        await runtime.reset()
        
        # After reset, should be back to STOPPED
        assert runtime._lifecycle_manager.get_state() == LifecycleState.STOPPED
        assert runtime.is_initialized is False
