"""
Unit tests for LocalZure Service Manager.
"""

import pytest
from typing import Dict, Any, List

from localzure.core.service_manager import (
    ServiceManager,
    ServiceDependencyError,
    ServiceStateError,
    ServiceEvent
)
from localzure.core.service import (
    LocalZureService,
    ServiceState,
    ServiceMetadata,
    ServiceRoute
)


class MockService(LocalZureService):
    """Mock service for testing."""
    
    def __init__(self, config: Dict[str, Any] = None, name: str = "mock", 
                 dependencies: List[str] = None, fail_start: bool = False,
                 fail_stop: bool = False, enabled: bool = True):
        super().__init__(config)
        self._name = name
        self._dependencies = dependencies or []
        self._fail_start = fail_start
        self._fail_stop = fail_stop
        self._enabled = enabled
        self._start_called = 0
        self._stop_called = 0
        self._reset_called = 0
    
    def get_metadata(self) -> ServiceMetadata:
        return ServiceMetadata(
            name=self._name,
            version="1.0.0",
            description=f"Mock service {self._name}",
            dependencies=self._dependencies,
            enabled=self._enabled
        )
    
    async def start(self) -> None:
        if self._fail_start:
            raise RuntimeError(f"Service {self._name} failed to start")
        self._start_called += 1
    
    async def stop(self) -> None:
        if self._fail_stop:
            raise RuntimeError(f"Service {self._name} failed to stop")
        self._stop_called += 1
    
    async def reset(self) -> None:
        self._reset_called += 1
    
    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self.state == ServiceState.RUNNING else "unhealthy",
            "details": {"starts": self._start_called}
        }
    
    def get_routes(self) -> List[ServiceRoute]:
        return []


class TestServiceManager:
    """Test ServiceManager basic functionality."""
    
    def test_manager_initialization(self):
        """Test service manager initializes correctly."""
        manager = ServiceManager()
        
        assert manager.service_count == 0
        assert manager.running_services == []
        assert manager.failed_services == []
    
    def test_manager_with_config(self):
        """Test service manager accepts configuration."""
        config = {
            "service-a": {"port": 8080},
            "service-b": {"port": 8081}
        }
        manager = ServiceManager(config=config)
        
        assert manager._config == config
    
    def test_register_service(self):
        """Test manually registering a service."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        
        manager.register_service(service)
        
        assert manager.service_count == 1
        assert "test-service" in manager._services
    
    def test_register_duplicate_service_fails(self):
        """Test registering a service with duplicate name fails."""
        manager = ServiceManager()
        service1 = MockService(name="test-service")
        service2 = MockService(name="test-service")
        
        manager.register_service(service1)
        
        with pytest.raises(ValueError, match="already registered"):
            manager.register_service(service2)
    
    def test_register_disabled_service_skipped(self):
        """Test disabled services are not registered."""
        manager = ServiceManager()
        service = MockService(name="disabled-service", enabled=False)
        
        manager.register_service(service)
        
        assert manager.service_count == 0
    
    @pytest.mark.asyncio
    async def test_initialize_manager(self):
        """Test initializing service manager."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        
        await manager.initialize()
        
        assert manager._initialized is True
        assert manager._startup_order == ["test-service"]
    
    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test initialize can be called multiple times."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        
        await manager.initialize()
        await manager.initialize()  # Should not error
        
        assert manager._initialized is True


class TestDependencyResolution:
    """Test service dependency resolution."""
    
    @pytest.mark.asyncio
    async def test_resolve_no_dependencies(self):
        """Test resolving services with no dependencies."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-a"))
        manager.register_service(MockService(name="service-b"))
        manager.register_service(MockService(name="service-c"))
        
        await manager.initialize()
        
        assert len(manager._startup_order) == 3
        assert set(manager._startup_order) == {"service-a", "service-b", "service-c"}
    
    @pytest.mark.asyncio
    async def test_resolve_simple_dependency_chain(self):
        """Test resolving simple dependency chain: A -> B -> C."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-c"))
        manager.register_service(MockService(name="service-b", dependencies=["service-c"]))
        manager.register_service(MockService(name="service-a", dependencies=["service-b"]))
        
        await manager.initialize()
        
        order = manager._startup_order
        assert order.index("service-c") < order.index("service-b")
        assert order.index("service-b") < order.index("service-a")
    
    @pytest.mark.asyncio
    async def test_resolve_diamond_dependency(self):
        """Test resolving diamond dependency: D -> B,C -> A."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-a"))
        manager.register_service(MockService(name="service-b", dependencies=["service-a"]))
        manager.register_service(MockService(name="service-c", dependencies=["service-a"]))
        manager.register_service(MockService(name="service-d", dependencies=["service-b", "service-c"]))
        
        await manager.initialize()
        
        order = manager._startup_order
        # A must come first
        assert order.index("service-a") == 0
        # B and C must come before D
        assert order.index("service-b") < order.index("service-d")
        assert order.index("service-c") < order.index("service-d")
    
    @pytest.mark.asyncio
    async def test_missing_dependency_fails(self):
        """Test that missing dependencies cause initialization to fail."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-a", dependencies=["missing-service"]))
        
        with pytest.raises(RuntimeError, match="not available"):
            await manager.initialize()
    
    @pytest.mark.asyncio
    async def test_circular_dependency_fails(self):
        """Test that circular dependencies are detected."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-a", dependencies=["service-b"]))
        manager.register_service(MockService(name="service-b", dependencies=["service-a"]))
        
        with pytest.raises(RuntimeError, match="Circular dependency"):
            await manager.initialize()
    
    @pytest.mark.asyncio
    async def test_complex_circular_dependency_fails(self):
        """Test detection of circular dependency in longer chain."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-a", dependencies=["service-b"]))
        manager.register_service(MockService(name="service-b", dependencies=["service-c"]))
        manager.register_service(MockService(name="service-c", dependencies=["service-a"]))
        
        with pytest.raises(RuntimeError, match="Circular dependency"):
            await manager.initialize()


class TestServiceLifecycle:
    """Test service lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_start_single_service(self):
        """Test starting a single service."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        
        await manager.start_service("test-service")
        
        assert service.state == ServiceState.RUNNING
        assert service._start_called == 1
    
    @pytest.mark.asyncio
    async def test_start_nonexistent_service_fails(self):
        """Test starting a service that doesn't exist."""
        manager = ServiceManager()
        await manager.initialize()
        
        with pytest.raises(ValueError, match="not found"):
            await manager.start_service("nonexistent")
    
    @pytest.mark.asyncio
    async def test_start_service_already_running(self):
        """Test starting an already running service is idempotent."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        
        await manager.start_service("test-service")
        await manager.start_service("test-service")  # Should not error
        
        assert service._start_called == 1  # Only called once
    
    @pytest.mark.asyncio
    async def test_start_service_with_dependencies(self):
        """Test starting service checks dependencies are running."""
        manager = ServiceManager()
        service_a = MockService(name="service-a")
        service_b = MockService(name="service-b", dependencies=["service-a"])
        manager.register_service(service_a)
        manager.register_service(service_b)
        await manager.initialize()
        
        # Try to start B without A running
        with pytest.raises(ServiceStateError, match="dependency.*not running"):
            await manager.start_service("service-b")
        
        # Start A first
        await manager.start_service("service-a")
        
        # Now B can start
        await manager.start_service("service-b")
        assert service_b.state == ServiceState.RUNNING
    
    @pytest.mark.asyncio
    async def test_stop_single_service(self):
        """Test stopping a service."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        await manager.start_service("test-service")
        
        await manager.stop_service("test-service")
        
        assert service.state == ServiceState.STOPPED
        assert service._stop_called == 1
    
    @pytest.mark.asyncio
    async def test_stop_already_stopped_service(self):
        """Test stopping an already stopped service is idempotent."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        
        await manager.stop_service("test-service")  # Already stopped
        
        assert service._stop_called == 0  # Never called
    
    @pytest.mark.asyncio
    async def test_start_all_services(self):
        """Test starting all services in correct order."""
        manager = ServiceManager()
        service_a = MockService(name="service-a")
        service_b = MockService(name="service-b", dependencies=["service-a"])
        service_c = MockService(name="service-c", dependencies=["service-b"])
        
        manager.register_service(service_a)
        manager.register_service(service_b)
        manager.register_service(service_c)
        await manager.initialize()
        
        await manager.start_all()
        
        assert service_a.state == ServiceState.RUNNING
        assert service_b.state == ServiceState.RUNNING
        assert service_c.state == ServiceState.RUNNING
        assert manager.running_services == ["service-a", "service-b", "service-c"]
    
    @pytest.mark.asyncio
    async def test_start_all_without_initialize_fails(self):
        """Test start_all fails if manager not initialized."""
        manager = ServiceManager()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.start_all()
    
    @pytest.mark.asyncio
    async def test_start_all_with_failure(self):
        """Test start_all handles service failures."""
        manager = ServiceManager()
        service_a = MockService(name="service-a")
        service_b = MockService(name="service-b", fail_start=True)
        service_c = MockService(name="service-c")
        
        manager.register_service(service_a)
        manager.register_service(service_b)
        manager.register_service(service_c)
        await manager.initialize()
        
        with pytest.raises(RuntimeError, match="Failed to start some services"):
            await manager.start_all()
        
        # A and C should still have been attempted
        assert service_a.state == ServiceState.RUNNING
        assert service_b.state == ServiceState.FAILED
        assert service_c.state == ServiceState.RUNNING
    
    @pytest.mark.asyncio
    async def test_stop_all_services(self):
        """Test stopping all services in reverse order."""
        manager = ServiceManager()
        service_a = MockService(name="service-a")
        service_b = MockService(name="service-b", dependencies=["service-a"])
        service_c = MockService(name="service-c", dependencies=["service-b"])
        
        manager.register_service(service_a)
        manager.register_service(service_b)
        manager.register_service(service_c)
        await manager.initialize()
        await manager.start_all()
        
        await manager.stop_all()
        
        assert service_a.state == ServiceState.STOPPED
        assert service_b.state == ServiceState.STOPPED
        assert service_c.state == ServiceState.STOPPED
    
    @pytest.mark.asyncio
    async def test_stop_all_continues_on_failure(self):
        """Test stop_all attempts to stop all services even if some fail."""
        manager = ServiceManager()
        service_a = MockService(name="service-a")
        service_b = MockService(name="service-b", fail_stop=True)
        service_c = MockService(name="service-c")
        
        manager.register_service(service_a)
        manager.register_service(service_b)
        manager.register_service(service_c)
        await manager.initialize()
        await manager.start_all()
        
        await manager.stop_all()  # Should not raise
        
        # A and C should be stopped despite B failing
        assert service_a.state == ServiceState.STOPPED
        assert service_b.state == ServiceState.FAILED
        assert service_c.state == ServiceState.STOPPED
    
    @pytest.mark.asyncio
    async def test_reset_service(self):
        """Test resetting a service."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        await manager.start_service("test-service")
        
        await manager.reset_service("test-service")
        
        assert service._reset_called == 1


class TestServiceStatus:
    """Test service status and health reporting."""
    
    @pytest.mark.asyncio
    async def test_get_service_status(self):
        """Test getting status for a single service."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        await manager.start_service("test-service")
        
        status = manager.get_service_status("test-service")
        
        assert status["name"] == "test-service"
        assert status["version"] == "1.0.0"
        assert status["state"] == "running"
        assert status["uptime"] is not None
        assert status["error"] is None
        assert status["dependencies"] == []
    
    @pytest.mark.asyncio
    async def test_get_service_status_with_error(self):
        """Test getting status for a failed service."""
        manager = ServiceManager()
        service = MockService(name="test-service", fail_start=True)
        manager.register_service(service)
        await manager.initialize()
        
        try:
            await manager.start_service("test-service")
        except RuntimeError:
            pass
        
        status = manager.get_service_status("test-service")
        
        assert status["state"] == "failed"
        assert status["error"] is not None
    
    def test_get_service_status_not_found(self):
        """Test getting status for nonexistent service fails."""
        manager = ServiceManager()
        
        with pytest.raises(ValueError, match="not found"):
            manager.get_service_status("nonexistent")
    
    @pytest.mark.asyncio
    async def test_get_all_status(self):
        """Test getting status for all services."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-a"))
        manager.register_service(MockService(name="service-b"))
        await manager.initialize()
        await manager.start_all()
        
        all_status = manager.get_all_status()
        
        assert len(all_status) == 2
        assert "service-a" in all_status
        assert "service-b" in all_status
        assert all_status["service-a"]["state"] == "running"
        assert all_status["service-b"]["state"] == "running"
    
    @pytest.mark.asyncio
    async def test_get_service_health(self):
        """Test getting health for a service."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        await manager.start_service("test-service")
        
        health = await manager.get_service_health("test-service")
        
        assert health["status"] == "healthy"
        assert "details" in health
    
    @pytest.mark.asyncio
    async def test_get_all_health(self):
        """Test getting health for all services."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-a"))
        manager.register_service(MockService(name="service-b"))
        await manager.initialize()
        await manager.start_all()
        
        all_health = await manager.get_all_health()
        
        assert len(all_health) == 2
        assert "service-a" in all_health
        assert "service-b" in all_health


class TestEventSystem:
    """Test service event emission."""
    
    @pytest.mark.asyncio
    async def test_event_listener_receives_events(self):
        """Test event listeners receive state change events."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        
        received_events = []
        
        def listener(event: ServiceEvent):
            received_events.append(event)
        
        manager.add_event_listener(listener)
        
        await manager.start_service("test-service")
        
        assert len(received_events) == 1
        event = received_events[0]
        assert event.service_name == "test-service"
        assert event.old_state == ServiceState.UNINITIALIZED
        assert event.new_state == ServiceState.RUNNING
        assert event.error is None
    
    @pytest.mark.asyncio
    async def test_event_listener_receives_error_events(self):
        """Test event listeners receive error information."""
        manager = ServiceManager()
        service = MockService(name="test-service", fail_start=True)
        manager.register_service(service)
        await manager.initialize()
        
        received_events = []
        manager.add_event_listener(lambda e: received_events.append(e))
        
        try:
            await manager.start_service("test-service")
        except RuntimeError:
            pass
        
        assert len(received_events) == 1
        event = received_events[0]
        assert event.new_state == ServiceState.FAILED
        assert event.error is not None
    
    @pytest.mark.asyncio
    async def test_remove_event_listener(self):
        """Test removing event listeners."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        
        received_events = []
        listener = lambda e: received_events.append(e)
        
        manager.add_event_listener(listener)
        manager.remove_event_listener(listener)
        
        await manager.start_service("test-service")
        
        assert len(received_events) == 0  # Listener was removed
    
    @pytest.mark.asyncio
    async def test_multiple_event_listeners(self):
        """Test multiple listeners all receive events."""
        manager = ServiceManager()
        service = MockService(name="test-service")
        manager.register_service(service)
        await manager.initialize()
        
        events1 = []
        events2 = []
        
        manager.add_event_listener(lambda e: events1.append(e))
        manager.add_event_listener(lambda e: events2.append(e))
        
        await manager.start_service("test-service")
        
        assert len(events1) == 1
        assert len(events2) == 1


class TestServiceManagerProperties:
    """Test ServiceManager convenience properties."""
    
    @pytest.mark.asyncio
    async def test_service_count(self):
        """Test service_count property."""
        manager = ServiceManager()
        assert manager.service_count == 0
        
        manager.register_service(MockService(name="service-a"))
        assert manager.service_count == 1
        
        manager.register_service(MockService(name="service-b"))
        assert manager.service_count == 2
    
    @pytest.mark.asyncio
    async def test_running_services(self):
        """Test running_services property."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-a"))
        manager.register_service(MockService(name="service-b"))
        await manager.initialize()
        
        assert manager.running_services == []
        
        await manager.start_service("service-a")
        assert manager.running_services == ["service-a"]
        
        await manager.start_service("service-b")
        assert set(manager.running_services) == {"service-a", "service-b"}
    
    @pytest.mark.asyncio
    async def test_failed_services(self):
        """Test failed_services property."""
        manager = ServiceManager()
        manager.register_service(MockService(name="service-a", fail_start=True))
        manager.register_service(MockService(name="service-b"))
        await manager.initialize()
        
        assert manager.failed_services == []
        
        try:
            await manager.start_service("service-a")
        except RuntimeError:
            pass
        
        assert manager.failed_services == ["service-a"]


class TestDockerIntegration:
    """Tests for Docker integration with ServiceManager."""
    
    @pytest.mark.asyncio
    async def test_manager_with_docker_enabled(self):
        """Test manager initialization with Docker enabled."""
        from unittest.mock import patch, AsyncMock, MagicMock
        
        manager = ServiceManager(docker_enabled=True)
        
        # Mock DockerManager class
        mock_docker_manager = MagicMock()
        mock_docker_manager.initialize = AsyncMock(return_value=True)
        mock_docker_manager.is_available = MagicMock(return_value=True)
        
        with patch('localzure.core.service_manager.DockerManager', return_value=mock_docker_manager):
            await manager.initialize()
        
        assert manager.is_docker_enabled() is True
        assert manager._docker_manager is not None
    
    @pytest.mark.asyncio
    async def test_manager_with_docker_unavailable(self):
        """Test manager when Docker is requested but unavailable."""
        from unittest.mock import patch, AsyncMock
        
        manager = ServiceManager(docker_enabled=True)
        
        # Mock Docker unavailable
        with patch('localzure.core.docker_manager.DockerManager.initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = False
            await manager.initialize()
        
        # Should fallback to host mode
        assert manager.is_docker_enabled() is False
    
    @pytest.mark.asyncio
    async def test_start_service_in_docker(self):
        """Test starting a service in Docker container."""
        from unittest.mock import patch, AsyncMock, MagicMock
        from localzure.core.docker_manager import DockerConfig
        
        class DockerMockService(MockService):
            def docker_config(self):
                return DockerConfig(
                    image="test/service:latest",
                    ports={"8080": "8080"}
                )
        
        manager = ServiceManager(docker_enabled=True)
        manager.register_service(DockerMockService(name="docker-service"))
        
        # Mock Docker manager
        with patch('localzure.core.docker_manager.DockerManager.initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            await manager.initialize()
        
        # Mock Docker manager methods
        manager._docker_manager.is_available = MagicMock(return_value=True)
        manager._docker_manager.start_container = AsyncMock(return_value=True)
        
        # Start service
        await manager.start_service("docker-service")
        
        # Verify Docker was used
        assert "docker-service" in manager._docker_services
        manager._docker_manager.start_container.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_service_in_host_mode(self):
        """Test starting a service in host mode (no Docker config)."""
        from unittest.mock import patch, AsyncMock, MagicMock
        
        manager = ServiceManager(docker_enabled=True)
        manager.register_service(MockService(name="host-service"))
        
        with patch('localzure.core.docker_manager.DockerManager.initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            await manager.initialize()
        
        manager._docker_manager.is_available = MagicMock(return_value=True)
        
        # Start service (should use host mode)
        await manager.start_service("host-service")
        
        # Verify Docker was not used
        assert "host-service" not in manager._docker_services
    
    @pytest.mark.asyncio
    async def test_stop_docker_service(self):
        """Test stopping a Docker-based service."""
        from unittest.mock import patch, AsyncMock, MagicMock
        from localzure.core.docker_manager import DockerConfig
        
        class DockerMockService(MockService):
            def docker_config(self):
                return DockerConfig(image="test:latest")
        
        manager = ServiceManager(docker_enabled=True)
        manager.register_service(DockerMockService(name="docker-service"))
        
        with patch('localzure.core.docker_manager.DockerManager.initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            await manager.initialize()
        
        manager._docker_manager.is_available = MagicMock(return_value=True)
        manager._docker_manager.start_container = AsyncMock(return_value=True)
        manager._docker_manager.stop_container = AsyncMock(return_value=True)
        
        # Start then stop
        await manager.start_service("docker-service")
        await manager.stop_service("docker-service")
        
        # Verify Docker stop was called
        manager._docker_manager.stop_container.assert_called_once_with("docker-service")
        assert "docker-service" not in manager._docker_services
    
    @pytest.mark.asyncio
    async def test_service_status_shows_execution_mode(self):
        """Test that service status includes execution mode."""
        from unittest.mock import patch, AsyncMock, MagicMock
        from localzure.core.docker_manager import DockerConfig
        
        class DockerMockService(MockService):
            def docker_config(self):
                return DockerConfig(image="test:latest")
        
        manager = ServiceManager(docker_enabled=True)
        manager.register_service(DockerMockService(name="docker-service"))
        manager.register_service(MockService(name="host-service"))
        
        with patch('localzure.core.docker_manager.DockerManager.initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            await manager.initialize()
        
        manager._docker_manager.is_available = MagicMock(return_value=True)
        manager._docker_manager.start_container = AsyncMock(return_value=True)
        
        # Start both services
        await manager.start_service("docker-service")
        await manager.start_service("host-service")
        
        # Check status
        docker_status = manager.get_service_status("docker-service")
        host_status = manager.get_service_status("host-service")
        
        assert docker_status["execution_mode"] == "docker"
        assert host_status["execution_mode"] == "host"
    
    @pytest.mark.asyncio
    async def test_manager_shutdown_with_docker(self):
        """Test manager shutdown cleans up Docker resources."""
        from unittest.mock import patch, AsyncMock, MagicMock
        
        manager = ServiceManager(docker_enabled=True)
        manager.register_service(MockService(name="test-service"))
        
        with patch('localzure.core.docker_manager.DockerManager.initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            await manager.initialize()
        
        manager._docker_manager.shutdown = AsyncMock()
        manager._docker_manager.is_available = MagicMock(return_value=True)
        
        await manager.shutdown()
        
        # Verify Docker cleanup was called
        manager._docker_manager.shutdown.assert_called_once()
