"""
LocalZure Service Abstract Interface.

Defines the base contract that all service emulators must implement.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

if TYPE_CHECKING:
    from localzure.core.docker_manager import DockerConfig


class ServiceState(str, Enum):
    """Service lifecycle states."""
    UNINITIALIZED = "uninitialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ServiceMetadata:
    """Metadata for a service emulator."""
    name: str
    version: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    port: Optional[int] = None
    enabled: bool = True


@dataclass
class ServiceRoute:
    """Route definition for a service."""
    path: str
    methods: List[str]
    handler: Any  # Callable or FastAPI route
    
    def __post_init__(self):
        """Validate route definition."""
        if not self.path.startswith("/"):
            self.path = f"/{self.path}"


class LocalZureService(ABC):
    """
    Abstract base class for all LocalZure service emulators.
    
    Each service must implement this interface to be managed by the ServiceManager.
    Services follow a strict state machine and lifecycle.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the service.
        
        Args:
            config: Service-specific configuration
        """
        self._config = config or {}
        self._state = ServiceState.UNINITIALIZED
        self._error: Optional[Exception] = None
        self._start_time: Optional[datetime] = None
    
    @property
    def state(self) -> ServiceState:
        """Get current service state."""
        return self._state
    
    @property
    def error(self) -> Optional[Exception]:
        """Get last error if service is in FAILED state."""
        return self._error
    
    @property
    def uptime(self) -> Optional[float]:
        """Get service uptime in seconds if running."""
        if self._start_time and self._state == ServiceState.RUNNING:
            return (datetime.now() - self._start_time).total_seconds()
        return None
    
    @abstractmethod
    def get_metadata(self) -> ServiceMetadata:
        """
        Get service metadata.
        
        Returns:
            ServiceMetadata containing name, version, dependencies, etc.
        """
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """
        Start the service.
        
        This method should:
        1. Initialize service resources
        2. Start any background tasks
        3. Verify service is ready
        
        Raises:
            RuntimeError: If service cannot start
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the service gracefully.
        
        This method should:
        1. Stop accepting new requests
        2. Complete in-flight operations
        3. Release resources
        
        Raises:
            RuntimeError: If service cannot stop cleanly
        """
        pass
    
    @abstractmethod
    async def reset(self) -> None:
        """
        Reset service to initial state.
        
        This method should:
        1. Clear all service data
        2. Reset internal state
        3. Keep service running if it was running
        
        Raises:
            RuntimeError: If reset fails
        """
        pass
    
    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        """
        Get service health status.
        
        Returns:
            Dictionary with health information:
            {
                "status": "healthy|degraded|unhealthy",
                "details": {...}
            }
        """
        pass
    
    @abstractmethod
    def get_routes(self) -> List[ServiceRoute]:
        """
        Get API routes provided by this service.
        
        Returns:
            List of ServiceRoute objects
        """
        pass
    
    def docker_config(self) -> Optional['DockerConfig']:
        """
        Get Docker configuration for this service.
        
        Returns:
            DockerConfig if service should run in Docker, None for host mode
            
        Example:
            from localzure.core.docker_manager import DockerConfig
            
            return DockerConfig(
                image="mcr.microsoft.com/azure-storage/azurite",
                ports={"10000": "10000", "10001": "10001"},
                volumes={"/tmp/azurite": "/data"},
                environment={"AZURITE_ACCOUNTS": "devstoreaccount1:..."}
            )
        """
        return None
    
    def _transition_state(self, new_state: ServiceState, error: Optional[Exception] = None) -> None:
        """
        Transition to a new state.
        
        Args:
            new_state: Target state
            error: Optional error if transitioning to FAILED
        """
        old_state = self._state
        self._state = new_state
        
        if new_state == ServiceState.RUNNING:
            self._start_time = datetime.now()
            self._error = None
        elif new_state == ServiceState.FAILED:
            self._error = error
        elif new_state in (ServiceState.STOPPED, ServiceState.UNINITIALIZED):
            self._start_time = None
            self._error = None
    
    async def _safe_start(self) -> None:
        """
        Safely start the service with state management.
        
        Internal wrapper that manages state transitions.
        """
        if self._state == ServiceState.RUNNING:
            return
        
        try:
            self._transition_state(ServiceState.STARTING)
            await self.start()
            self._transition_state(ServiceState.RUNNING)
        except Exception as e:
            self._transition_state(ServiceState.FAILED, e)
            raise
    
    async def _safe_stop(self) -> None:
        """
        Safely stop the service with state management.
        
        Internal wrapper that manages state transitions.
        """
        if self._state in (ServiceState.STOPPED, ServiceState.UNINITIALIZED):
            return
        
        try:
            self._transition_state(ServiceState.STOPPING)
            await self.stop()
            self._transition_state(ServiceState.STOPPED)
        except Exception as e:
            self._transition_state(ServiceState.FAILED, e)
            raise
