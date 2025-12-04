"""
Docker integration for LocalZure service emulators.

Manages Docker containers for services, including lifecycle management,
health checks, log integration, and volume mounting.
"""

import asyncio
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ContainerState(str, Enum):
    """Docker container states."""
    NOT_CREATED = "not_created"
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class DockerConfig:
    """Docker container configuration for a service."""
    image: str
    ports: Dict[str, str] = field(default_factory=dict)  # container_port -> host_port
    volumes: Dict[str, str] = field(default_factory=dict)  # host_path -> container_path
    environment: Dict[str, str] = field(default_factory=dict)
    command: Optional[List[str]] = None
    healthcheck: Optional[Dict[str, Any]] = None
    network_mode: str = "bridge"
    
    def __post_init__(self):
        """Validate Docker configuration."""
        if not self.image:
            raise ValueError("Docker image is required")


class DockerManager:
    """
    Manages Docker containers for LocalZure services.
    
    Responsibilities:
    - Detect Docker availability
    - Start/stop/manage containers
    - Monitor container health
    - Integrate container logs into LocalZure logging
    - Clean up containers on shutdown
    """
    
    def __init__(self):
        """Initialize Docker manager."""
        self._docker_client: Optional[Any] = None
        self._docker_available = False
        self._containers: Dict[str, Any] = {}
        self._container_states: Dict[str, ContainerState] = {}
        self._log_tasks: Dict[str, asyncio.Task] = {}
        
    async def initialize(self) -> bool:
        """
        Initialize Docker client and detect Docker availability.
        
        Returns:
            bool: True if Docker is available, False otherwise
        """
        try:
            import docker
            self._docker_client = docker.from_env()
            # Test connection
            self._docker_client.ping()
            self._docker_available = True
            logger.info("Docker is available and connected")
            return True
        except ImportError:
            logger.warning("Docker SDK not installed. Install with: pip install docker")
            self._docker_available = False
            return False
        except Exception as e:
            logger.warning(f"Docker is not available: {e}")
            self._docker_available = False
            return False
    
    def is_available(self) -> bool:
        """Check if Docker is available."""
        return self._docker_available
    
    async def start_container(
        self,
        service_name: str,
        config: DockerConfig,
        instance_id: Optional[str] = None
    ) -> bool:
        """
        Start a Docker container for a service.
        
        Args:
            service_name: Name of the service
            config: Docker configuration
            instance_id: Optional instance identifier for multiple instances
            
        Returns:
            bool: True if container started successfully
        """
        if not self._docker_available:
            logger.error("Docker is not available")
            return False
        
        container_name = self._get_container_name(service_name, instance_id)
        
        try:
            # Check if container already exists
            existing = self._get_existing_container(container_name)
            if existing:
                logger.info(f"Removing existing container: {container_name}")
                existing.remove(force=True)
            
            # Prepare port bindings
            port_bindings = {}
            if config.ports:
                for container_port, host_port in config.ports.items():
                    port_bindings[container_port] = host_port
            
            # Prepare volume bindings
            volumes = {}
            if config.volumes:
                for host_path, container_path in config.volumes.items():
                    volumes[host_path] = {
                        'bind': container_path,
                        'mode': 'rw'
                    }
            
            # Create container
            logger.info(f"Creating container {container_name} from image {config.image}")
            container = self._docker_client.containers.run(
                image=config.image,
                name=container_name,
                ports=port_bindings,
                volumes=volumes,
                environment=config.environment,
                command=config.command,
                network_mode=config.network_mode,
                detach=True,
                remove=False,
                labels={
                    'localzure.service': service_name,
                    'localzure.managed': 'true'
                }
            )
            
            self._containers[container_name] = container
            self._container_states[container_name] = ContainerState.RUNNING
            
            # Start log streaming
            await self._start_log_streaming(container_name, container)
            
            logger.info(f"Container {container_name} started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start container {container_name}: {e}")
            self._container_states[container_name] = ContainerState.FAILED
            return False
    
    async def stop_container(self, service_name: str, instance_id: Optional[str] = None) -> bool:
        """
        Stop a Docker container.
        
        Args:
            service_name: Name of the service
            instance_id: Optional instance identifier
            
        Returns:
            bool: True if container stopped successfully
        """
        container_name = self._get_container_name(service_name, instance_id)
        
        try:
            # Stop log streaming
            await self._stop_log_streaming(container_name)
            
            container = self._containers.get(container_name)
            if container:
                logger.info(f"Stopping container: {container_name}")
                container.stop(timeout=10)
                self._container_states[container_name] = ContainerState.STOPPED
                logger.info(f"Container {container_name} stopped")
                return True
            else:
                logger.warning(f"Container {container_name} not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to stop container {container_name}: {e}")
            return False
    
    async def remove_container(self, service_name: str, instance_id: Optional[str] = None) -> bool:
        """
        Remove a Docker container.
        
        Args:
            service_name: Name of the service
            instance_id: Optional instance identifier
            
        Returns:
            bool: True if container removed successfully
        """
        container_name = self._get_container_name(service_name, instance_id)
        
        try:
            # Ensure stopped first
            await self.stop_container(service_name, instance_id)
            
            container = self._containers.get(container_name)
            if container:
                logger.info(f"Removing container: {container_name}")
                container.remove(force=True)
                del self._containers[container_name]
                del self._container_states[container_name]
                logger.info(f"Container {container_name} removed")
                return True
            else:
                logger.warning(f"Container {container_name} not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove container {container_name}: {e}")
            return False
    
    async def get_container_health(self, service_name: str, instance_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get container health status.
        
        Args:
            service_name: Name of the service
            instance_id: Optional instance identifier
            
        Returns:
            dict: Health status information
        """
        container_name = self._get_container_name(service_name, instance_id)
        
        try:
            container = self._containers.get(container_name)
            if not container:
                return {
                    'status': 'not_found',
                    'state': ContainerState.NOT_CREATED
                }
            
            # Reload container to get latest status
            container.reload()
            
            state = container.attrs.get('State', {})
            health = state.get('Health', {})
            
            return {
                'status': state.get('Status', 'unknown'),
                'running': state.get('Running', False),
                'health_status': health.get('Status', 'none'),
                'exit_code': state.get('ExitCode'),
                'error': state.get('Error', ''),
                'started_at': state.get('StartedAt'),
                'finished_at': state.get('FinishedAt'),
                'state': self._container_states.get(container_name, ContainerState.NOT_CREATED)
            }
            
        except Exception as e:
            logger.error(f"Failed to get health for container {container_name}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'state': ContainerState.FAILED
            }
    
    async def cleanup_all(self) -> None:
        """Clean up all managed containers."""
        logger.info("Cleaning up all LocalZure containers")
        
        # Stop all log streaming
        for task in self._log_tasks.values():
            task.cancel()
        
        # Wait for log tasks to complete
        if self._log_tasks:
            await asyncio.gather(*self._log_tasks.values(), return_exceptions=True)
        
        self._log_tasks.clear()
        
        # Stop and remove all containers
        for container_name in list(self._containers.keys()):
            service_name = container_name.replace('localzure-', '').split('-')[0]
            await self.remove_container(service_name)
        
        logger.info("All containers cleaned up")
    
    async def cleanup_service_containers(self, service_pattern: Optional[str] = None) -> None:
        """
        Clean up containers matching a pattern (for crash recovery).
        
        Args:
            service_pattern: Optional pattern to match service names
        """
        if not self._docker_available:
            return
        
        try:
            filters = {'label': 'localzure.managed=true'}
            if service_pattern:
                filters['label'] = f'localzure.service={service_pattern}'
            
            containers = self._docker_client.containers.list(all=True, filters=filters)
            
            for container in containers:
                try:
                    logger.info(f"Cleaning up orphaned container: {container.name}")
                    container.remove(force=True)
                except Exception as e:
                    logger.error(f"Failed to remove container {container.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup service containers: {e}")
    
    def _get_container_name(self, service_name: str, instance_id: Optional[str] = None) -> str:
        """Generate container name following LocalZure convention."""
        if instance_id:
            return f"localzure-{service_name}-{instance_id}"
        return f"localzure-{service_name}"
    
    def _get_existing_container(self, container_name: str) -> Optional[Any]:
        """Get existing container by name."""
        try:
            return self._docker_client.containers.get(container_name)
        except Exception:
            return None
    
    async def _start_log_streaming(self, container_name: str, container: Any) -> None:
        """Start streaming container logs to LocalZure logging."""
        task = asyncio.create_task(self._stream_logs(container_name, container))
        self._log_tasks[container_name] = task
    
    async def _stop_log_streaming(self, container_name: str) -> None:
        """Stop streaming container logs."""
        task = self._log_tasks.get(container_name)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._log_tasks[container_name]
    
    async def _stream_logs(self, container_name: str, container: Any) -> None:
        """Stream container logs to LocalZure logger."""
        container_logger = logging.getLogger(f"localzure.container.{container_name}")
        
        try:
            # Stream logs in a separate thread to avoid blocking
            loop = asyncio.get_event_loop()
            
            def read_logs():
                try:
                    for line in container.logs(stream=True, follow=True):
                        decoded = line.decode('utf-8').strip()
                        if decoded:
                            container_logger.info(decoded)
                except Exception as e:
                    container_logger.error(f"Log streaming error: {e}")
            
            await loop.run_in_executor(None, read_logs)
            
        except asyncio.CancelledError:
            container_logger.info(f"Log streaming stopped for {container_name}")
        except Exception as e:
            container_logger.error(f"Failed to stream logs for {container_name}: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown Docker manager and cleanup resources."""
        await self.cleanup_all()
        
        if self._docker_client:
            try:
                self._docker_client.close()
            except Exception as e:
                logger.error(f"Error closing Docker client: {e}")
        
        logger.info("Docker manager shutdown complete")
