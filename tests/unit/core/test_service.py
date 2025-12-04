"""
Unit tests for LocalZure Service abstract interface.
"""

import pytest
from datetime import datetime
from typing import Dict, Any, List

from localzure.core.service import (
    LocalZureService,
    ServiceState,
    ServiceMetadata,
    ServiceRoute
)


class MockService(LocalZureService):
    """Mock service for testing."""
    
    def __init__(self, config: Dict[str, Any] = None, name: str = "mock-service"):
        super().__init__(config)
        self._name = name
        self._should_fail_start = False
        self._should_fail_stop = False
        self._started_count = 0
        self._stopped_count = 0
    
    def get_metadata(self) -> ServiceMetadata:
        return ServiceMetadata(
            name=self._name,
            version="1.0.0",
            description="Mock service for testing",
            dependencies=[],
            port=8080
        )
    
    async def start(self) -> None:
        if self._should_fail_start:
            raise RuntimeError("Intentional start failure")
        self._started_count += 1
    
    async def stop(self) -> None:
        if self._should_fail_stop:
            raise RuntimeError("Intentional stop failure")
        self._stopped_count += 1
    
    async def reset(self) -> None:
        pass
    
    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "details": {"started": self._started_count}
        }
    
    def get_routes(self) -> List[ServiceRoute]:
        return [
            ServiceRoute(path="/test", methods=["GET"], handler=lambda: "test")
        ]


class TestServiceState:
    """Test ServiceState enum."""
    
    def test_service_states_exist(self):
        """Test that all required states are defined."""
        assert ServiceState.UNINITIALIZED == "uninitialized"
        assert ServiceState.STARTING == "starting"
        assert ServiceState.RUNNING == "running"
        assert ServiceState.STOPPING == "stopping"
        assert ServiceState.STOPPED == "stopped"
        assert ServiceState.FAILED == "failed"


class TestServiceMetadata:
    """Test ServiceMetadata dataclass."""
    
    def test_metadata_creation(self):
        """Test creating service metadata."""
        metadata = ServiceMetadata(
            name="test-service",
            version="1.0.0",
            description="Test service",
            dependencies=["dep1", "dep2"],
            port=8080,
            enabled=True
        )
        
        assert metadata.name == "test-service"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test service"
        assert metadata.dependencies == ["dep1", "dep2"]
        assert metadata.port == 8080
        assert metadata.enabled is True
    
    def test_metadata_defaults(self):
        """Test metadata with default values."""
        metadata = ServiceMetadata(
            name="test",
            version="1.0.0",
            description="Test"
        )
        
        assert metadata.dependencies == []
        assert metadata.port is None
        assert metadata.enabled is True


class TestServiceRoute:
    """Test ServiceRoute dataclass."""
    
    def test_route_creation(self):
        """Test creating a service route."""
        handler = lambda: "test"
        route = ServiceRoute(
            path="/api/test",
            methods=["GET", "POST"],
            handler=handler
        )
        
        assert route.path == "/api/test"
        assert route.methods == ["GET", "POST"]
        assert route.handler == handler
    
    def test_route_auto_adds_slash(self):
        """Test that route automatically adds leading slash."""
        route = ServiceRoute(
            path="api/test",
            methods=["GET"],
            handler=lambda: "test"
        )
        
        assert route.path == "/api/test"


class TestLocalZureService:
    """Test LocalZureService abstract class."""
    
    def test_service_initialization(self):
        """Test service initializes with correct default state."""
        service = MockService()
        
        assert service.state == ServiceState.UNINITIALIZED
        assert service.error is None
        assert service.uptime is None
    
    def test_service_with_config(self):
        """Test service accepts configuration."""
        config = {"setting1": "value1", "setting2": 42}
        service = MockService(config=config)
        
        assert service._config == config
    
    def test_get_metadata(self):
        """Test getting service metadata."""
        service = MockService(name="test-service")
        metadata = service.get_metadata()
        
        assert metadata.name == "test-service"
        assert metadata.version == "1.0.0"
        assert isinstance(metadata, ServiceMetadata)
    
    @pytest.mark.asyncio
    async def test_safe_start_success(self):
        """Test successful service start."""
        service = MockService()
        
        await service._safe_start()
        
        assert service.state == ServiceState.RUNNING
        assert service.error is None
        assert service._started_count == 1
        assert service.uptime is not None
    
    @pytest.mark.asyncio
    async def test_safe_start_already_running(self):
        """Test starting an already running service is idempotent."""
        service = MockService()
        
        await service._safe_start()
        await service._safe_start()  # Should not start again
        
        assert service.state == ServiceState.RUNNING
        assert service._started_count == 1  # Only started once
    
    @pytest.mark.asyncio
    async def test_safe_start_failure(self):
        """Test service start failure transitions to FAILED state."""
        service = MockService()
        service._should_fail_start = True
        
        with pytest.raises(RuntimeError, match="Intentional start failure"):
            await service._safe_start()
        
        assert service.state == ServiceState.FAILED
        assert service.error is not None
        assert "Intentional start failure" in str(service.error)
    
    @pytest.mark.asyncio
    async def test_safe_stop_success(self):
        """Test successful service stop."""
        service = MockService()
        await service._safe_start()
        
        await service._safe_stop()
        
        assert service.state == ServiceState.STOPPED
        assert service.error is None
        assert service._stopped_count == 1
    
    @pytest.mark.asyncio
    async def test_safe_stop_already_stopped(self):
        """Test stopping an already stopped service is idempotent."""
        service = MockService()
        
        await service._safe_stop()  # Stop when uninitialized
        
        assert service.state == ServiceState.UNINITIALIZED
        assert service._stopped_count == 0  # Not called
    
    @pytest.mark.asyncio
    async def test_safe_stop_failure(self):
        """Test service stop failure transitions to FAILED state."""
        service = MockService()
        await service._safe_start()
        service._should_fail_stop = True
        
        with pytest.raises(RuntimeError, match="Intentional stop failure"):
            await service._safe_stop()
        
        assert service.state == ServiceState.FAILED
        assert service.error is not None
    
    def test_state_transition(self):
        """Test state transitions."""
        service = MockService()
        
        service._transition_state(ServiceState.STARTING)
        assert service.state == ServiceState.STARTING
        
        service._transition_state(ServiceState.RUNNING)
        assert service.state == ServiceState.RUNNING
        assert service._start_time is not None
        
        service._transition_state(ServiceState.STOPPED)
        assert service.state == ServiceState.STOPPED
        assert service._start_time is None
    
    def test_state_transition_with_error(self):
        """Test state transition to FAILED with error."""
        service = MockService()
        error = RuntimeError("Test error")
        
        service._transition_state(ServiceState.FAILED, error)
        
        assert service.state == ServiceState.FAILED
        assert service.error == error
    
    @pytest.mark.asyncio
    async def test_uptime_calculation(self):
        """Test uptime is calculated correctly."""
        service = MockService()
        
        assert service.uptime is None  # Not running
        
        await service._safe_start()
        
        import asyncio
        await asyncio.sleep(0.1)  # Wait a bit
        
        uptime = service.uptime
        assert uptime is not None
        assert uptime >= 0.1
        assert uptime < 1.0  # Should be less than 1 second
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check returns expected format."""
        service = MockService()
        await service._safe_start()
        
        health = await service.health()
        
        assert "status" in health
        assert health["status"] == "healthy"
        assert "details" in health
    
    def test_get_routes(self):
        """Test getting service routes."""
        service = MockService()
        routes = service.get_routes()
        
        assert len(routes) == 1
        assert routes[0].path == "/test"
        assert routes[0].methods == ["GET"]
    
    @pytest.mark.asyncio
    async def test_reset(self):
        """Test service reset."""
        service = MockService()
        await service._safe_start()
        
        await service.reset()
        
        # Service should still be running after reset
        assert service.state == ServiceState.RUNNING
    
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete service lifecycle."""
        service = MockService()
        
        # Initial state
        assert service.state == ServiceState.UNINITIALIZED
        
        # Start
        await service._safe_start()
        assert service.state == ServiceState.RUNNING
        assert service._started_count == 1
        
        # Reset
        await service.reset()
        assert service.state == ServiceState.RUNNING
        
        # Stop
        await service._safe_stop()
        assert service.state == ServiceState.STOPPED
        assert service._stopped_count == 1
        
        # Restart
        await service._safe_start()
        assert service.state == ServiceState.RUNNING
        assert service._started_count == 2


class TestServiceWithDependencies:
    """Test services with dependencies."""
    
    def test_service_with_dependencies(self):
        """Test service metadata includes dependencies."""
        
        class DependentService(MockService):
            def get_metadata(self) -> ServiceMetadata:
                return ServiceMetadata(
                    name="dependent-service",
                    version="1.0.0",
                    description="Service with dependencies",
                    dependencies=["service-a", "service-b"]
                )
        
        service = DependentService()
        metadata = service.get_metadata()
        
        assert metadata.dependencies == ["service-a", "service-b"]
