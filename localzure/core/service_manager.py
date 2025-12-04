"""
LocalZure Service Manager.

Manages the lifecycle of all service emulators, including discovery, dependency
resolution, startup, shutdown, and health monitoring. Supports both host-mode
and Docker container execution.
"""

import asyncio
import logging
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict, deque
from importlib.metadata import entry_points

from .service import LocalZureService, ServiceState, ServiceMetadata
from .docker_manager import DockerManager, DockerConfig
from .logging_config import get_logger

logger = get_logger(__name__)


class ServiceDependencyError(Exception):
    """Raised when service dependencies cannot be resolved."""
    pass


class ServiceStateError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class ServiceEvent:
    """Event emitted when a service state changes."""
    
    def __init__(self, service_name: str, old_state: ServiceState, new_state: ServiceState, error: Optional[Exception] = None):
        self.service_name = service_name
        self.old_state = old_state
        self.new_state = new_state
        self.error = error
        self.timestamp = asyncio.get_event_loop().time()


class ServiceManager:
    """
    Manages all LocalZure service emulators.
    
    Responsibilities:
    - Discover services via Python entrypoints
    - Resolve service dependencies
    - Start/stop services in correct order (host or Docker)
    - Monitor service health
    - Emit events for state changes
    - Integrate with Docker for containerized services
    """
    
    ENTRYPOINT_GROUP = "localzure.services"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, docker_enabled: bool = False):
        """
        Initialize the service manager.
        
        Args:
            config: Configuration dictionary for services
            docker_enabled: Whether to enable Docker integration
        """
        self._config = config or {}
        self._services: Dict[str, LocalZureService] = {}
        self._metadata: Dict[str, ServiceMetadata] = {}
        self._event_listeners: List[Any] = []  # Callables that receive ServiceEvent
        self._startup_order: List[str] = []
        self._initialized = False
        self._docker_enabled = docker_enabled
        self._docker_manager: Optional[DockerManager] = None
        self._docker_services: Set[str] = set()  # Services running in Docker
    
    def discover_services(self) -> None:
        """
        Discover available services via entrypoints.
        
        Services are registered using Python entrypoints:
        [project.entry-points."localzure.services"]
        blob = "localzure.services.blob:BlobStorageService"
        
        Raises:
            RuntimeError: If service discovery fails
        """
        logger.info("Discovering services via entrypoints")
        
        try:
            eps = entry_points()
            if hasattr(eps, 'select'):
                # Python 3.10+
                service_entries = eps.select(group=self.ENTRYPOINT_GROUP)
            else:
                # Python 3.9
                service_entries = eps.get(self.ENTRYPOINT_GROUP, [])
            
            for ep in service_entries:
                try:
                    service_class = ep.load()
                    service_config = self._config.get(ep.name, {})
                    service_instance = service_class(config=service_config)
                    
                    metadata = service_instance.get_metadata()
                    
                    # Skip disabled services
                    if not metadata.enabled:
                        logger.info(f"Service '{metadata.name}' is disabled, skipping")
                        continue
                    
                    self._services[metadata.name] = service_instance
                    self._metadata[metadata.name] = metadata
                    
                    logger.info(f"Discovered service: {metadata.name} v{metadata.version}")
                    
                except Exception as e:
                    logger.error(f"Failed to load service from entrypoint '{ep.name}': {e}")
                    # Continue with other services
            
            logger.info(f"Service discovery complete. Found {len(self._services)} service(s)")
            
        except Exception as e:
            logger.error(f"Service discovery failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to discover services: {e}") from e
    
    def register_service(self, service: LocalZureService) -> None:
        """
        Manually register a service (alternative to entrypoint discovery).
        
        Args:
            service: Service instance to register
        
        Raises:
            ValueError: If service with same name already registered
        """
        metadata = service.get_metadata()
        
        if metadata.name in self._services:
            raise ValueError(f"Service '{metadata.name}' is already registered")
        
        if not metadata.enabled:
            logger.info(f"Service '{metadata.name}' is disabled, skipping registration")
            return
        
        self._services[metadata.name] = service
        self._metadata[metadata.name] = metadata
        
        logger.info(f"Manually registered service: {metadata.name}")
    
    def _resolve_dependencies(self) -> List[str]:
        """
        Resolve service dependencies using topological sort.
        
        Returns:
            List of service names in startup order
        
        Raises:
            ServiceDependencyError: If circular dependencies detected or missing dependencies
        """
        logger.debug("Resolving service dependencies")
        
        # Build dependency graph
        graph: Dict[str, Set[str]] = defaultdict(set)
        in_degree: Dict[str, int] = defaultdict(int)
        
        for name, metadata in self._metadata.items():
            graph[name]  # Ensure all services are in graph
            for dep in metadata.dependencies:
                if dep not in self._services:
                    raise ServiceDependencyError(
                        f"Service '{name}' depends on '{dep}' which is not available"
                    )
                graph[dep].add(name)
                in_degree[name] += 1
        
        # Kahn's algorithm for topological sort
        queue = deque([name for name in self._services if in_degree[name] == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(result) != len(self._services):
            remaining = set(self._services.keys()) - set(result)
            raise ServiceDependencyError(
                f"Circular dependency detected involving services: {remaining}"
            )
        
        logger.debug(f"Dependency resolution complete. Startup order: {result}")
        return result
    
    async def initialize(self) -> None:
        """
        Initialize the service manager.
        
        This resolves dependencies, initializes Docker (if enabled), and prepares services.
        
        Raises:
            ServiceDependencyError: If dependencies cannot be resolved
            RuntimeError: If initialization fails
        """
        if self._initialized:
            logger.info("Service manager already initialized")
            return
        
        logger.info("Initializing service manager")
        
        try:
            # Initialize Docker if enabled
            if self._docker_enabled:
                self._docker_manager = DockerManager()
                docker_available = await self._docker_manager.initialize()
                if docker_available:
                    logger.info("Docker integration enabled and available")
                else:
                    logger.warning("Docker integration requested but Docker is not available. Services will run in host mode.")
                    self._docker_enabled = False
            
            # Resolve startup order
            self._startup_order = self._resolve_dependencies()
            self._initialized = True
            
            logger.info(f"Service manager initialized with {len(self._services)} service(s)")
            
        except Exception as e:
            logger.error(f"Service manager initialization failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize service manager: {e}") from e
    
    async def start_service(self, name: str) -> None:
        """
        Start a specific service (in Docker or host mode).
        
        Args:
            name: Service name
        
        Raises:
            ValueError: If service not found
            ServiceStateError: If service is in invalid state
            RuntimeError: If service fails to start
        """
        if name not in self._services:
            raise ValueError(f"Service '{name}' not found")
        
        service = self._services[name]
        metadata = self._metadata[name]
        
        # Check dependencies are running
        for dep in metadata.dependencies:
            dep_service = self._services[dep]
            if dep_service.state != ServiceState.RUNNING:
                raise ServiceStateError(
                    f"Cannot start '{name}': dependency '{dep}' is not running (state: {dep_service.state})"
                )
        
        if service.state == ServiceState.RUNNING:
            logger.info(f"Service '{name}' is already running")
            return
        
        logger.info(f"Starting service: {name}")
        old_state = service.state
        
        try:
            # Check if service should run in Docker
            docker_config = service.docker_config()
            use_docker = (
                self._docker_enabled 
                and self._docker_manager 
                and self._docker_manager.is_available()
                and docker_config is not None
            )
            
            if use_docker:
                logger.info(f"Starting service '{name}' in Docker container")
                success = await self._docker_manager.start_container(name, docker_config)
                if success:
                    self._docker_services.add(name)
                    # Service state managed by container, mark as running
                    service._transition_state(ServiceState.RUNNING)
                else:
                    raise RuntimeError(f"Failed to start Docker container for '{name}'")
            else:
                # Host mode
                logger.info(f"Starting service '{name}' in host mode")
                await service._safe_start()
            
            self._emit_event(ServiceEvent(name, old_state, service.state))
            logger.info(f"Service '{name}' started successfully")
            
        except Exception as e:
            self._emit_event(ServiceEvent(name, old_state, service.state, e))
            logger.error(f"Failed to start service '{name}': {e}", exc_info=True)
            raise RuntimeError(f"Service '{name}' failed to start: {e}") from e
    
    async def stop_service(self, name: str) -> None:
        """
        Stop a specific service (Docker or host mode).
        
        Args:
            name: Service name
        
        Raises:
            ValueError: If service not found
            RuntimeError: If service fails to stop
        """
        if name not in self._services:
            raise ValueError(f"Service '{name}' not found")
        
        service = self._services[name]
        
        if service.state in (ServiceState.STOPPED, ServiceState.UNINITIALIZED):
            logger.info(f"Service '{name}' is already stopped")
            return
        
        logger.info(f"Stopping service: {name}")
        old_state = service.state
        
        try:
            # Check if service is running in Docker
            if name in self._docker_services:
                logger.info(f"Stopping Docker container for service '{name}'")
                await self._docker_manager.stop_container(name)
                self._docker_services.discard(name)
                service._transition_state(ServiceState.STOPPED)
            else:
                # Host mode
                await service._safe_stop()
            
            self._emit_event(ServiceEvent(name, old_state, service.state))
            logger.info(f"Service '{name}' stopped successfully")
            
        except Exception as e:
            self._emit_event(ServiceEvent(name, old_state, service.state, e))
            logger.error(f"Failed to stop service '{name}': {e}", exc_info=True)
            raise RuntimeError(f"Service '{name}' failed to stop: {e}") from e
    
    async def start_all(self) -> None:
        """
        Start all services in dependency order.
        
        Raises:
            RuntimeError: If any service fails to start
        """
        if not self._initialized:
            raise RuntimeError("Service manager not initialized. Call initialize() first.")
        
        logger.info("Starting all services")
        
        failed_services = []
        
        for name in self._startup_order:
            try:
                await self.start_service(name)
            except Exception as e:
                logger.error(f"Failed to start service '{name}': {e}")
                failed_services.append((name, e))
                # Continue with other services to see full picture
        
        if failed_services:
            error_msg = "; ".join([f"{name}: {str(e)}" for name, e in failed_services])
            raise RuntimeError(f"Failed to start some services: {error_msg}")
        
        logger.info("All services started successfully")
    
    async def stop_all(self) -> None:
        """
        Stop all services in reverse dependency order.
        
        This method attempts to stop all services even if some fail.
        """
        logger.info("Stopping all services")
        
        failed_services = []
        
        # Stop in reverse order
        for name in reversed(self._startup_order):
            try:
                await self.stop_service(name)
            except Exception as e:
                logger.error(f"Failed to stop service '{name}': {e}")
                failed_services.append((name, e))
                # Continue stopping other services
        
        if failed_services:
            logger.warning(f"Some services failed to stop cleanly: {[name for name, _ in failed_services]}")
        else:
            logger.info("All services stopped successfully")
    
    async def reset_service(self, name: str) -> None:
        """
        Reset a specific service to initial state.
        
        Args:
            name: Service name
        
        Raises:
            ValueError: If service not found
            RuntimeError: If reset fails
        """
        if name not in self._services:
            raise ValueError(f"Service '{name}' not found")
        
        service = self._services[name]
        
        logger.info(f"Resetting service: {name}")
        
        try:
            await service.reset()
            logger.info(f"Service '{name}' reset successfully")
            
        except Exception as e:
            logger.error(f"Failed to reset service '{name}': {e}", exc_info=True)
            raise RuntimeError(f"Service '{name}' failed to reset: {e}") from e
    
    def get_service_status(self, name: str) -> Dict[str, Any]:
        """
        Get status information for a specific service.
        
        Args:
            name: Service name
        
        Returns:
            Dictionary with service status
        
        Raises:
            ValueError: If service not found
        """
        if name not in self._services:
            raise ValueError(f"Service '{name}' not found")
        
        service = self._services[name]
        metadata = self._metadata[name]
        
        return {
            "name": metadata.name,
            "version": metadata.version,
            "state": service.state.value,
            "uptime": service.uptime,
            "error": str(service.error) if service.error else None,
            "dependencies": metadata.dependencies,
            "execution_mode": "docker" if name in self._docker_services else "host"
        }
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status information for all services.
        
        Returns:
            Dictionary mapping service names to status information
        """
        return {
            name: self.get_service_status(name)
            for name in self._services
        }
    
    async def get_service_health(self, name: str) -> Dict[str, Any]:
        """
        Get health status for a specific service (including Docker container health).
        
        Args:
            name: Service name
        
        Returns:
            Health status dictionary
        
        Raises:
            ValueError: If service not found
        """
        if name not in self._services:
            raise ValueError(f"Service '{name}' not found")
        
        service = self._services[name]
        
        try:
            # Get service health
            service_health = await service.health()
            
            # If running in Docker, also get container health
            if name in self._docker_services and self._docker_manager:
                container_health = await self._docker_manager.get_container_health(name)
                service_health['container'] = container_health
            
            return service_health
        except Exception as e:
            logger.error(f"Failed to get health for service '{name}': {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """
        Get health status for all services.
        
        Returns:
            Dictionary mapping service names to health information
        """
        health = {}
        
        for name in self._services:
            health[name] = await self.get_service_health(name)
        
        return health
    
    def add_event_listener(self, listener: Any) -> None:
        """
        Add a listener for service state change events.
        
        Args:
            listener: Callable that accepts ServiceEvent
        """
        self._event_listeners.append(listener)
        logger.debug(f"Added event listener: {listener}")
    
    def remove_event_listener(self, listener: Any) -> None:
        """
        Remove an event listener.
        
        Args:
            listener: Listener to remove
        """
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)
            logger.debug(f"Removed event listener: {listener}")
    
    def _emit_event(self, event: ServiceEvent) -> None:
        """
        Emit a service state change event to all listeners.
        
        Args:
            event: ServiceEvent to emit
        """
        logger.debug(
            f"Service event: {event.service_name} {event.old_state.value} -> {event.new_state.value}"
        )
        
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Event listener failed: {e}", exc_info=True)
    
    @property
    def service_count(self) -> int:
        """Get total number of registered services."""
        return len(self._services)
    
    @property
    def running_services(self) -> List[str]:
        """Get list of currently running service names."""
        return [
            name for name, service in self._services.items()
            if service.state == ServiceState.RUNNING
        ]
    
    @property
    def failed_services(self) -> List[str]:
        """Get list of failed service names."""
        return [
            name for name, service in self._services.items()
            if service.state == ServiceState.FAILED
        ]
    
    async def shutdown(self) -> None:
        """
        Shutdown service manager and cleanup all resources.
        
        This stops all services and cleans up Docker containers.
        """
        logger.info("Shutting down service manager")
        
        try:
            # Stop all services
            await self.stop_all()
            
            # Cleanup Docker resources
            if self._docker_manager:
                await self._docker_manager.shutdown()
            
            logger.info("Service manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during service manager shutdown: {e}", exc_info=True)
    
    def is_docker_enabled(self) -> bool:
        """Check if Docker integration is enabled and available."""
        return self._docker_enabled and self._docker_manager is not None and self._docker_manager.is_available()
