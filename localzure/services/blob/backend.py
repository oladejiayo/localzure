"""
Blob Storage Container Backend

In-memory storage backend for container operations.

Author: Ayodele Oladeji
Date: 2025
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .models import (
    Container,
    ContainerMetadata,
    ContainerNameValidator,
    ContainerProperties,
    LeaseState,
    LeaseStatus,
    PublicAccessLevel,
)


class ContainerAlreadyExistsError(Exception):
    """Raised when attempting to create a container that already exists."""
    pass


class ContainerNotFoundError(Exception):
    """Raised when a container is not found."""
    pass


class InvalidContainerNameError(Exception):
    """Raised when a container name is invalid."""
    pass


class ContainerBackend:
    """
    In-memory storage backend for containers.
    
    Manages container lifecycle, metadata, and properties.
    Thread-safe using asyncio locks.
    """
    
    def __init__(self):
        """Initialize the container backend."""
        self._containers: Dict[str, Container] = {}
        self._lock = asyncio.Lock()
    
    async def create_container(
        self,
        name: str,
        metadata: Optional[Dict[str, str]] = None,
        public_access: PublicAccessLevel = PublicAccessLevel.PRIVATE,
    ) -> Container:
        """
        Create a new container.
        
        Args:
            name: Container name
            metadata: Optional metadata key-value pairs
            public_access: Public access level
            
        Returns:
            Created container
            
        Raises:
            InvalidContainerNameError: If name is invalid
            ContainerAlreadyExistsError: If container already exists
        """
        # Validate name
        is_valid, error = ContainerNameValidator.validate(name)
        if not is_valid:
            raise InvalidContainerNameError(error)
        
        async with self._lock:
            if name in self._containers:
                raise ContainerAlreadyExistsError(f"Container '{name}' already exists")
            
            # Create container
            container_metadata = ContainerMetadata(metadata=metadata or {})
            properties = ContainerProperties(
                etag=self._generate_etag(),
                last_modified=datetime.now(timezone.utc),
                lease_status=LeaseStatus.UNLOCKED,
                lease_state=LeaseState.AVAILABLE,
                public_access=public_access,
            )
            
            container = Container(
                name=name,
                metadata=container_metadata,
                properties=properties,
            )
            
            self._containers[name] = container
            return container
    
    async def list_containers(
        self,
        prefix: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[Container]:
        """
        List all containers.
        
        Args:
            prefix: Optional prefix filter
            max_results: Optional maximum number of results
            
        Returns:
            List of containers
        """
        async with self._lock:
            containers = list(self._containers.values())
        
        # Apply prefix filter
        if prefix:
            containers = [c for c in containers if c.name.startswith(prefix)]
        
        # Sort by name
        containers.sort(key=lambda c: c.name)
        
        # Apply max results
        if max_results:
            containers = containers[:max_results]
        
        return containers
    
    async def get_container(self, name: str) -> Container:
        """
        Get container by name.
        
        Args:
            name: Container name
            
        Returns:
            Container
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            if name not in self._containers:
                raise ContainerNotFoundError(f"Container '{name}' not found")
            return self._containers[name]
    
    async def get_container_properties(self, name: str) -> ContainerProperties:
        """
        Get container properties.
        
        Args:
            name: Container name
            
        Returns:
            Container properties
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        container = await self.get_container(name)
        return container.properties
    
    async def set_container_metadata(
        self,
        name: str,
        metadata: Dict[str, str],
    ) -> Container:
        """
        Set container metadata.
        
        Args:
            name: Container name
            metadata: Metadata key-value pairs
            
        Returns:
            Updated container
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            if name not in self._containers:
                raise ContainerNotFoundError(f"Container '{name}' not found")
            
            container = self._containers[name]
            
            # Update metadata
            container.metadata = ContainerMetadata(metadata=metadata)
            
            # Update properties
            container.properties.etag = self._generate_etag()
            container.properties.last_modified = datetime.now(timezone.utc)
            
            return container
    
    async def delete_container(self, name: str) -> None:
        """
        Delete a container.
        
        Args:
            name: Container name
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            if name not in self._containers:
                raise ContainerNotFoundError(f"Container '{name}' not found")
            del self._containers[name]
    
    async def container_exists(self, name: str) -> bool:
        """
        Check if container exists.
        
        Args:
            name: Container name
            
        Returns:
            True if container exists
        """
        async with self._lock:
            return name in self._containers
    
    async def reset(self) -> None:
        """Reset the backend, removing all containers."""
        async with self._lock:
            self._containers.clear()
    
    def _generate_etag(self) -> str:
        """Generate a unique ETag."""
        return hashlib.md5(uuid.uuid4().bytes).hexdigest()
