"""
Tests for Docker Manager.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from localzure.core.docker_manager import DockerManager, DockerConfig, ContainerState


@pytest.fixture
def docker_config():
    """Create a sample Docker configuration."""
    return DockerConfig(
        image="test/image:latest",
        ports={"8080": "8080", "9000": "9000"},
        volumes={"/host/path": "/container/path"},
        environment={"TEST_VAR": "test_value"},
        command=["run", "--verbose"]
    )


@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client."""
    client = MagicMock()
    client.ping.return_value = True
    client.containers = MagicMock()
    return client


class TestDockerConfig:
    """Tests for DockerConfig dataclass."""
    
    def test_docker_config_creation(self):
        """Test creating a Docker configuration."""
        config = DockerConfig(
            image="nginx:latest",
            ports={"80": "8080"},
            volumes={"/data": "/app/data"}
        )
        
        assert config.image == "nginx:latest"
        assert config.ports == {"80": "8080"}
        assert config.volumes == {"/data": "/app/data"}
        assert config.network_mode == "bridge"  # default
    
    def test_docker_config_requires_image(self):
        """Test that image is required."""
        with pytest.raises(ValueError, match="Docker image is required"):
            DockerConfig(image="")
    
    def test_docker_config_defaults(self):
        """Test default values."""
        config = DockerConfig(image="test:latest")
        
        assert config.ports == {}
        assert config.volumes == {}
        assert config.environment == {}
        assert config.command is None
        assert config.healthcheck is None


class TestDockerManager:
    """Tests for DockerManager."""
    
    @pytest.mark.asyncio
    async def test_initialize_with_docker_available(self, mock_docker_client):
        """Test initialization when Docker is available."""
        manager = DockerManager()
        
        with patch('builtins.__import__', side_effect=lambda name, *args, **kwargs: 
                   Mock(from_env=Mock(return_value=mock_docker_client)) if name == 'docker' 
                   else __import__(name, *args, **kwargs)):
            result = await manager.initialize()
        
        assert result is True
        assert manager.is_available() is True
    
    @pytest.mark.asyncio
    async def test_initialize_with_docker_unavailable(self):
        """Test initialization when Docker is not available."""
        manager = DockerManager()
        
        def mock_import(name, *args, **kwargs):
            if name == 'docker':
                mock_docker = Mock()
                mock_docker.from_env = Mock(side_effect=Exception("Docker not found"))
                return mock_docker
            return __import__(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            result = await manager.initialize()
        
        assert result is False
        assert manager.is_available() is False
    
    @pytest.mark.asyncio
    async def test_initialize_with_missing_docker_sdk(self):
        """Test initialization when Docker SDK not installed."""
        manager = DockerManager()
        
        def mock_import(name, *args, **kwargs):
            if name == 'docker':
                raise ImportError("No module named 'docker'")
            return __import__(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            result = await manager.initialize()
        
        assert result is False
        assert manager.is_available() is False
    
    @pytest.mark.asyncio
    async def test_start_container_success(self, mock_docker_client, docker_config):
        """Test successfully starting a container."""
        manager = DockerManager()
        manager._docker_client = mock_docker_client
        manager._docker_available = True
        
        mock_container = MagicMock()
        mock_docker_client.containers.run.return_value = mock_container
        mock_docker_client.containers.get.side_effect = Exception("Not found")
        
        # Mock log streaming
        with patch.object(manager, '_start_log_streaming', new_callable=AsyncMock):
            result = await manager.start_container("test-service", docker_config)
        
        assert result is True
        assert "localzure-test-service" in manager._containers
        assert manager._container_states["localzure-test-service"] == ContainerState.RUNNING
        
        # Verify container creation
        mock_docker_client.containers.run.assert_called_once()
        call_kwargs = mock_docker_client.containers.run.call_args.kwargs
        assert call_kwargs['image'] == "test/image:latest"
        assert call_kwargs['name'] == "localzure-test-service"
        assert call_kwargs['detach'] is True
    
    @pytest.mark.asyncio
    async def test_start_container_removes_existing(self, mock_docker_client, docker_config):
        """Test that existing container is removed before starting new one."""
        manager = DockerManager()
        manager._docker_client = mock_docker_client
        manager._docker_available = True
        
        # Mock existing container
        existing_container = MagicMock()
        mock_docker_client.containers.get.return_value = existing_container
        
        new_container = MagicMock()
        mock_docker_client.containers.run.return_value = new_container
        
        with patch.object(manager, '_start_log_streaming', new_callable=AsyncMock):
            result = await manager.start_container("test-service", docker_config)
        
        assert result is True
        existing_container.remove.assert_called_once_with(force=True)
    
    @pytest.mark.asyncio
    async def test_start_container_without_docker(self, docker_config):
        """Test starting container when Docker is not available."""
        manager = DockerManager()
        manager._docker_available = False
        
        result = await manager.start_container("test-service", docker_config)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_start_container_failure(self, mock_docker_client, docker_config):
        """Test container start failure."""
        manager = DockerManager()
        manager._docker_client = mock_docker_client
        manager._docker_available = True
        
        mock_docker_client.containers.get.side_effect = Exception("Not found")
        mock_docker_client.containers.run.side_effect = Exception("Failed to start")
        
        result = await manager.start_container("test-service", docker_config)
        
        assert result is False
        assert manager._container_states.get("localzure-test-service") == ContainerState.FAILED
    
    @pytest.mark.asyncio
    async def test_stop_container_success(self, mock_docker_client):
        """Test successfully stopping a container."""
        manager = DockerManager()
        manager._docker_client = mock_docker_client
        manager._docker_available = True
        
        # Setup existing container
        mock_container = MagicMock()
        manager._containers["localzure-test-service"] = mock_container
        manager._container_states["localzure-test-service"] = ContainerState.RUNNING
        
        with patch.object(manager, '_stop_log_streaming', new_callable=AsyncMock):
            result = await manager.stop_container("test-service")
        
        assert result is True
        mock_container.stop.assert_called_once_with(timeout=10)
        assert manager._container_states["localzure-test-service"] == ContainerState.STOPPED
    
    @pytest.mark.asyncio
    async def test_stop_container_not_found(self):
        """Test stopping a non-existent container."""
        manager = DockerManager()
        manager._docker_available = True
        
        with patch.object(manager, '_stop_log_streaming', new_callable=AsyncMock):
            result = await manager.stop_container("nonexistent")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_remove_container_success(self, mock_docker_client):
        """Test successfully removing a container."""
        manager = DockerManager()
        manager._docker_client = mock_docker_client
        manager._docker_available = True
        
        # Setup existing container
        mock_container = MagicMock()
        manager._containers["localzure-test-service"] = mock_container
        manager._container_states["localzure-test-service"] = ContainerState.STOPPED
        
        with patch.object(manager, '_stop_log_streaming', new_callable=AsyncMock):
            result = await manager.remove_container("test-service")
        
        assert result is True
        mock_container.remove.assert_called_once_with(force=True)
        assert "localzure-test-service" not in manager._containers
        assert "localzure-test-service" not in manager._container_states
    
    @pytest.mark.asyncio
    async def test_get_container_health_running(self, mock_docker_client):
        """Test getting health of a running container."""
        manager = DockerManager()
        manager._docker_available = True
        
        mock_container = MagicMock()
        mock_container.attrs = {
            'State': {
                'Status': 'running',
                'Running': True,
                'ExitCode': 0,
                'Error': '',
                'StartedAt': '2025-12-04T10:00:00Z',
                'FinishedAt': '0001-01-01T00:00:00Z',
                'Health': {
                    'Status': 'healthy'
                }
            }
        }
        manager._containers["localzure-test-service"] = mock_container
        manager._container_states["localzure-test-service"] = ContainerState.RUNNING
        
        health = await manager.get_container_health("test-service")
        
        assert health['status'] == 'running'
        assert health['running'] is True
        assert health['health_status'] == 'healthy'
        assert health['state'] == ContainerState.RUNNING
    
    @pytest.mark.asyncio
    async def test_get_container_health_not_found(self):
        """Test getting health of non-existent container."""
        manager = DockerManager()
        
        health = await manager.get_container_health("nonexistent")
        
        assert health['status'] == 'not_found'
        assert health['state'] == ContainerState.NOT_CREATED
    
    @pytest.mark.asyncio
    async def test_cleanup_all(self, mock_docker_client):
        """Test cleaning up all containers."""
        manager = DockerManager()
        manager._docker_client = mock_docker_client
        manager._docker_available = True
        
        # Setup multiple containers
        mock_container1 = MagicMock()
        mock_container2 = MagicMock()
        manager._containers["localzure-service1"] = mock_container1
        manager._containers["localzure-service2"] = mock_container2
        
        # Mock remove_container to avoid actual removal
        with patch.object(manager, 'remove_container', new_callable=AsyncMock) as mock_remove:
            await manager.cleanup_all()
        
        # Verify containers were removed
        assert mock_remove.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_service_containers(self, mock_docker_client):
        """Test cleaning up service containers by pattern."""
        manager = DockerManager()
        manager._docker_client = mock_docker_client
        manager._docker_available = True
        
        # Mock orphaned containers
        orphan1 = MagicMock()
        orphan1.name = "localzure-service1"
        orphan2 = MagicMock()
        orphan2.name = "localzure-service2"
        
        mock_docker_client.containers.list.return_value = [orphan1, orphan2]
        
        await manager.cleanup_service_containers()
        
        orphan1.remove.assert_called_once_with(force=True)
        orphan2.remove.assert_called_once_with(force=True)
    
    @pytest.mark.asyncio
    async def test_container_naming_convention(self):
        """Test container naming follows LocalZure convention."""
        manager = DockerManager()
        
        # Without instance ID
        name = manager._get_container_name("blob")
        assert name == "localzure-blob"
        
        # With instance ID
        name = manager._get_container_name("blob", "instance-1")
        assert name == "localzure-blob-instance-1"
    
    @pytest.mark.asyncio
    async def test_shutdown(self, mock_docker_client):
        """Test manager shutdown."""
        manager = DockerManager()
        manager._docker_client = mock_docker_client
        manager._docker_available = True
        
        # Setup container
        mock_container = MagicMock()
        manager._containers["localzure-test"] = mock_container
        
        with patch.object(manager, 'cleanup_all', new_callable=AsyncMock) as mock_cleanup:
            await manager.shutdown()
        
        mock_cleanup.assert_called_once()
        mock_docker_client.close.assert_called_once()


class TestDockerIntegrationWithService:
    """Tests for Docker integration with services."""
    
    @pytest.mark.asyncio
    async def test_service_with_docker_config(self):
        """Test service that provides Docker configuration."""
        from localzure.core.service import LocalZureService, ServiceMetadata, ServiceRoute
        
        class TestDockerService(LocalZureService):
            def get_metadata(self):
                return ServiceMetadata(
                    name="test",
                    version="1.0.0",
                    description="Test service"
                )
            
            async def start(self):
                pass
            
            async def stop(self):
                pass
            
            async def reset(self):
                pass
            
            async def health(self):
                return {"status": "healthy"}
            
            def get_routes(self):
                return []
            
            def docker_config(self):
                return DockerConfig(
                    image="test/service:latest",
                    ports={"8080": "8080"}
                )
        
        service = TestDockerService()
        config = service.docker_config()
        
        assert config is not None
        assert config.image == "test/service:latest"
        assert config.ports == {"8080": "8080"}
    
    @pytest.mark.asyncio
    async def test_service_without_docker_config(self):
        """Test service that runs in host mode (no Docker config)."""
        from localzure.core.service import LocalZureService, ServiceMetadata
        
        class TestHostService(LocalZureService):
            def get_metadata(self):
                return ServiceMetadata(
                    name="test",
                    version="1.0.0",
                    description="Test service"
                )
            
            async def start(self):
                pass
            
            async def stop(self):
                pass
            
            async def reset(self):
                pass
            
            async def health(self):
                return {"status": "healthy"}
            
            def get_routes(self):
                return []
        
        service = TestHostService()
        config = service.docker_config()
        
        assert config is None  # Defaults to host mode
