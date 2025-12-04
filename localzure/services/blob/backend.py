"""
Blob Storage Backend

In-memory storage backend for container and blob operations.

Author: Ayodele Oladeji
Date: 2025
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .models import (
    Blob,
    BlobProperties,
    BlobTier,
    BlobType,
    Block,
    BlockListType,
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


class BlobNotFoundError(Exception):
    """Raised when a blob is not found."""
    pass


class BlobAlreadyExistsError(Exception):
    """Raised when attempting to create a blob that already exists."""
    pass


class InvalidBlockIdError(Exception):
    """Raised when a block ID is invalid."""
    pass


class ContainerBackend:
    """
    In-memory storage backend for containers and blobs.
    
    Manages container and blob lifecycle, metadata, and properties.
    Thread-safe using asyncio locks.
    """
    
    def __init__(self):
        """Initialize the container backend."""
        self._containers: Dict[str, Container] = {}
        self._blobs: Dict[str, Dict[str, Blob]] = {}  # container_name -> {blob_name -> Blob}
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
        Delete a container and all its blobs.
        
        Args:
            name: Container name
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            if name not in self._containers:
                raise ContainerNotFoundError(f"Container '{name}' not found")
            del self._containers[name]
            # Delete all blobs in the container
            if name in self._blobs:
                del self._blobs[name]
    
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
        """Reset the backend, removing all containers and blobs."""
        async with self._lock:
            self._containers.clear()
            self._blobs.clear()
    
    def _generate_etag(self) -> str:
        """Generate a unique ETag."""
        return hashlib.md5(uuid.uuid4().bytes).hexdigest()
    
    # ============================================================================
    # Blob Operations
    # ============================================================================
    
    async def put_blob(
        self,
        container_name: str,
        blob_name: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
        content_encoding: Optional[str] = None,
        content_language: Optional[str] = None,
        cache_control: Optional[str] = None,
        content_disposition: Optional[str] = None,
    ) -> Blob:
        """
        Upload a blob with content.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            content: Blob content bytes
            content_type: Content type
            metadata: Optional metadata
            content_encoding: Content encoding header
            content_language: Content language header
            cache_control: Cache control header
            content_disposition: Content disposition header
            
        Returns:
            Created or updated blob
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            # Ensure blob container exists in storage
            if container_name not in self._blobs:
                self._blobs[container_name] = {}
            
            # Create blob properties
            now = datetime.now(timezone.utc)
            properties = BlobProperties(
                etag=self._generate_etag(),
                last_modified=now,
                creation_time=now,
                content_length=len(content),
                content_type=content_type,
                content_encoding=content_encoding,
                content_language=content_language,
                cache_control=cache_control,
                content_disposition=content_disposition,
                blob_type=BlobType.BLOCK_BLOB,
            )
            
            # Create blob
            blob = Blob(
                name=blob_name,
                container_name=container_name,
                content=content,
                metadata=ContainerMetadata(metadata=metadata or {}),
                properties=properties,
            )
            
            self._blobs[container_name][blob_name] = blob
            return blob
    
    async def get_blob(self, container_name: str, blob_name: str) -> Blob:
        """
        Get blob by name.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            
        Returns:
            Blob
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found in container '{container_name}'")
            
            return self._blobs[container_name][blob_name]
    
    async def get_blob_properties(self, container_name: str, blob_name: str) -> BlobProperties:
        """
        Get blob properties.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            
        Returns:
            Blob properties
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
        """
        blob = await self.get_blob(container_name, blob_name)
        return blob.properties
    
    async def set_blob_metadata(
        self,
        container_name: str,
        blob_name: str,
        metadata: Dict[str, str],
    ) -> Blob:
        """
        Set blob metadata.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            metadata: Metadata key-value pairs
            
        Returns:
            Updated blob
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            blob = self._blobs[container_name][blob_name]
            
            # Update metadata
            blob.metadata = ContainerMetadata(metadata=metadata)
            
            # Update properties
            blob.properties.etag = self._generate_etag()
            blob.properties.last_modified = datetime.now(timezone.utc)
            
            return blob
    
    async def delete_blob(self, container_name: str, blob_name: str) -> None:
        """
        Delete a blob.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            del self._blobs[container_name][blob_name]
    
    async def list_blobs(
        self,
        container_name: str,
        prefix: Optional[str] = None,
        delimiter: Optional[str] = None,
        max_results: Optional[int] = None,
        marker: Optional[str] = None,
    ) -> tuple[List[Blob], Optional[str]]:
        """
        List blobs in a container.
        
        Args:
            container_name: Container name
            prefix: Optional prefix filter
            delimiter: Optional delimiter for hierarchical listing
            max_results: Optional maximum number of results
            marker: Optional continuation marker
            
        Returns:
            Tuple of (list of blobs, next_marker)
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs:
                return [], None
            
            blobs = list(self._blobs[container_name].values())
            
            # Apply prefix filter
            if prefix:
                blobs = [b for b in blobs if b.name.startswith(prefix)]
            
            # Sort by name
            blobs.sort(key=lambda b: b.name)
            
            # Apply marker (continue from this blob name)
            if marker:
                blobs = [b for b in blobs if b.name > marker]
            
            # Apply max results
            next_marker = None
            if max_results and len(blobs) > max_results:
                next_marker = blobs[max_results - 1].name
                blobs = blobs[:max_results]
            
            return blobs, next_marker
    
    async def blob_exists(self, container_name: str, blob_name: str) -> bool:
        """
        Check if blob exists.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            
        Returns:
            True if blob exists
        """
        async with self._lock:
            if container_name not in self._blobs:
                return False
            return blob_name in self._blobs[container_name]
    
    # ============================================================================
    # Block Blob Operations
    # ============================================================================
    
    async def put_block(
        self,
        container_name: str,
        blob_name: str,
        block_id: str,
        content: bytes,
    ) -> None:
        """
        Stage a block for a block blob.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            block_id: Base64-encoded block ID
            content: Block content
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            # Ensure container blob storage exists
            if container_name not in self._blobs:
                self._blobs[container_name] = {}
            
            # Get or create blob
            if blob_name not in self._blobs[container_name]:
                # Create blob with empty content for block staging
                now = datetime.now(timezone.utc)
                properties = BlobProperties(
                    etag=self._generate_etag(),
                    last_modified=now,
                    creation_time=now,
                    content_length=0,
                    blob_type=BlobType.BLOCK_BLOB,
                )
                blob = Blob(
                    name=blob_name,
                    container_name=container_name,
                    content=b"",
                    properties=properties,
                )
                self._blobs[container_name][blob_name] = blob
            else:
                blob = self._blobs[container_name][blob_name]
            
            # Stage the block
            block = Block(
                block_id=block_id,
                size=len(content),
                content=content,
                committed=False,
            )
            blob.uncommitted_blocks[block_id] = block
    
    async def put_block_list(
        self,
        container_name: str,
        blob_name: str,
        block_list: List[tuple[str, BlockListType]],
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Blob:
        """
        Commit blocks to create or update a block blob.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            block_list: List of (block_id, block_type) tuples
            content_type: Content type
            metadata: Optional metadata
            
        Returns:
            Updated blob
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            InvalidBlockIdError: If block ID not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            blob = self._blobs[container_name][blob_name]
            
            # Collect blocks based on block list
            final_blocks: List[Block] = []
            for block_id, block_type in block_list:
                block = None
                
                if block_type == BlockListType.UNCOMMITTED:
                    if block_id in blob.uncommitted_blocks:
                        block = blob.uncommitted_blocks[block_id]
                elif block_type == BlockListType.COMMITTED:
                    # Find in committed blocks
                    if block_id in blob.uncommitted_blocks:
                        block = blob.uncommitted_blocks[block_id]
                elif block_type == BlockListType.LATEST:
                    # Prefer uncommitted, fall back to committed
                    if block_id in blob.uncommitted_blocks:
                        block = blob.uncommitted_blocks[block_id]
                
                if block is None:
                    raise InvalidBlockIdError(f"Block '{block_id}' not found")
                
                final_blocks.append(block)
            
            # Assemble final content
            content = b"".join(block.content for block in final_blocks)
            
            # Update blob
            blob.content = content
            blob.properties.content_length = len(content)
            blob.properties.content_type = content_type
            blob.properties.etag = self._generate_etag()
            blob.properties.last_modified = datetime.now(timezone.utc)
            
            if metadata:
                blob.metadata = ContainerMetadata(metadata=metadata)
            
            # Update committed blocks list
            blob.committed_blocks = [block.block_id for block in final_blocks]
            
            # Clear uncommitted blocks
            blob.uncommitted_blocks.clear()
            
            return blob
