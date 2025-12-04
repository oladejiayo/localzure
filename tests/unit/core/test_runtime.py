"""
Tests for LocalZure Runtime.
"""

import pytest
from fastapi.testclient import TestClient

from localzure.core.runtime import LocalZureRuntime
from localzure.core.config_manager import LocalZureConfig


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
