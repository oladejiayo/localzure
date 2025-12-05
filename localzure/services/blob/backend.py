"""
Blob Storage Backend

In-memory storage backend for container and blob operations.

Author: Ayodele Oladeji
Date: 2025
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
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
    Lease,
    LeaseAction,
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


class LeaseAlreadyPresentError(Exception):
    """Raised when attempting to acquire a lease on an already leased resource."""
    pass


class LeaseIdMissingError(Exception):
    """Raised when lease ID is required but not provided."""
    pass


class LeaseIdMismatchError(Exception):
    """Raised when provided lease ID doesn't match the active lease."""
    pass


class LeaseNotFoundError(Exception):
    """Raised when lease ID is not found."""
    pass


class SnapshotNotFoundError(Exception):
    """Raised when snapshot is not found."""
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
        self._snapshots: Dict[str, Dict[str, Dict[str, Blob]]] = {}  # container_name -> {blob_name -> {snapshot_id -> Blob}}
        self._container_leases: Dict[str, Lease] = {}  # container_name -> Lease
        self._blob_leases: Dict[str, Dict[str, Lease]] = {}  # container_name -> {blob_name -> Lease}
        self._lock = asyncio.Lock()
        self._expiration_task: Optional[asyncio.Task] = None
        self._stop_expiration = False
    
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
        """Reset the backend, removing all containers, blobs, snapshots, and leases."""
        async with self._lock:
            self._containers.clear()
            self._blobs.clear()
            self._snapshots.clear()
            self._container_leases.clear()
            self._blob_leases.clear()
    
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
        lease_id: Optional[str] = None,
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
            lease_id: Lease ID if blob is leased
            
        Returns:
            Created or updated blob
            
        Raises:
            ContainerNotFoundError: If container not found
            LeaseIdMissingError: If lease ID required but not provided
            LeaseIdMismatchError: If lease ID doesn't match
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            # Validate lease if blob exists and is leased
            if container_name in self._blobs and blob_name in self._blobs[container_name]:
                self._validate_blob_lease(container_name, blob_name, lease_id)
            
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
        lease_id: Optional[str] = None,
    ) -> Blob:
        """
        Set blob metadata.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            metadata: Metadata key-value pairs
            lease_id: Lease ID if blob is leased
            
        Returns:
            Updated blob
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            LeaseIdMissingError: If lease ID required but not provided
            LeaseIdMismatchError: If lease ID doesn't match
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            # Validate lease
            self._validate_blob_lease(container_name, blob_name, lease_id)
            
            blob = self._blobs[container_name][blob_name]
            
            # Update metadata
            blob.metadata = ContainerMetadata(metadata=metadata)
            
            # Update properties
            blob.properties.etag = self._generate_etag()
            blob.properties.last_modified = datetime.now(timezone.utc)
            
            return blob
    
    async def delete_blob(
        self,
        container_name: str,
        blob_name: str,
        lease_id: Optional[str] = None,
    ) -> None:
        """
        Delete a blob.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            lease_id: Lease ID if blob is leased
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            LeaseIdMissingError: If lease ID required but not provided
            LeaseIdMismatchError: If lease ID doesn't match
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            # Validate lease
            self._validate_blob_lease(container_name, blob_name, lease_id)
            
            del self._blobs[container_name][blob_name]
    
    async def list_blobs(
        self,
        container_name: str,
        prefix: Optional[str] = None,
        delimiter: Optional[str] = None,
        max_results: Optional[int] = None,
        marker: Optional[str] = None,
        include_snapshots: bool = False,
    ) -> tuple[List[Blob], Optional[str]]:
        """
        List blobs in a container.
        
        Args:
            container_name: Container name
            prefix: Optional prefix filter
            delimiter: Optional delimiter for hierarchical listing
            max_results: Optional maximum number of results
            marker: Optional continuation marker
            include_snapshots: Whether to include snapshots in the listing
            
        Returns:
            Tuple of (list of blobs, next_marker)
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs:
                blobs = []
            else:
                blobs = list(self._blobs[container_name].values())
            
            # Add snapshots if requested
            if include_snapshots and container_name in self._snapshots:
                for blob_name in self._snapshots[container_name]:
                    for snapshot in self._snapshots[container_name][blob_name].values():
                        blobs.append(snapshot)
            
            # Apply prefix filter
            if prefix:
                blobs = [b for b in blobs if b.name.startswith(prefix)]
            
            # Sort by name, then by snapshot_id (base blob first, then snapshots in order)
            blobs.sort(key=lambda b: (b.name, b.snapshot_id if b.snapshot_id else ""))
            
            # Apply marker (continue from this blob name)
            if marker:
                blobs = [b for b in blobs if b.name > marker or (b.name == marker and b.snapshot_id and b.snapshot_id > marker)]
            
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
    # Blob Snapshot Operations
    # ============================================================================
    
    async def create_snapshot(
        self,
        container_name: str,
        blob_name: str,
    ) -> Blob:
        """
        Create a snapshot of a blob.
        
        Creates a read-only point-in-time copy of the blob with a unique
        snapshot timestamp identifier.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            
        Returns:
            Snapshot blob with snapshot_id set
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            # Get the base blob
            base_blob = self._blobs[container_name][blob_name]
            
            # Create snapshot timestamp (RFC1123 format with microseconds)
            snapshot_time = datetime.now(timezone.utc)
            snapshot_id = snapshot_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            
            # Create a copy of the blob as a snapshot
            snapshot_blob = Blob(
                name=blob_name,
                container_name=container_name,
                content=base_blob.content,
                metadata=ContainerMetadata(metadata=dict(base_blob.metadata.metadata)),  # Deep copy metadata
                properties=BlobProperties(
                    etag=self._generate_etag(),
                    last_modified=snapshot_time,
                    content_length=base_blob.properties.content_length,
                    content_type=base_blob.properties.content_type,
                    content_encoding=base_blob.properties.content_encoding,
                    content_language=base_blob.properties.content_language,
                    content_md5=base_blob.properties.content_md5,
                    cache_control=base_blob.properties.cache_control,
                    content_disposition=base_blob.properties.content_disposition,
                    blob_type=base_blob.properties.blob_type,
                    blob_tier=base_blob.properties.blob_tier,
                    creation_time=base_blob.properties.creation_time,
                    is_snapshot=True,
                    snapshot_time=snapshot_time,
                ),
                snapshot_id=snapshot_id,
            )
            
            # Store snapshot
            if container_name not in self._snapshots:
                self._snapshots[container_name] = {}
            if blob_name not in self._snapshots[container_name]:
                self._snapshots[container_name][blob_name] = {}
            
            self._snapshots[container_name][blob_name][snapshot_id] = snapshot_blob
            
            return snapshot_blob
    
    async def get_blob_snapshot(
        self,
        container_name: str,
        blob_name: str,
        snapshot_id: str,
    ) -> Blob:
        """
        Get a specific blob snapshot.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            snapshot_id: Snapshot identifier
            
        Returns:
            Snapshot blob
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If snapshot not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if (container_name not in self._snapshots or
                blob_name not in self._snapshots[container_name] or
                snapshot_id not in self._snapshots[container_name][blob_name]):
                raise SnapshotNotFoundError(f"Snapshot '{snapshot_id}' for blob '{blob_name}' not found")
            
            return self._snapshots[container_name][blob_name][snapshot_id]
    
    async def list_blob_snapshots(
        self,
        container_name: str,
        blob_name: str,
    ) -> List[Blob]:
        """
        List all snapshots for a blob.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            
        Returns:
            List of snapshot blobs (sorted by snapshot time)
            
        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            if (container_name not in self._snapshots or
                blob_name not in self._snapshots[container_name]):
                return []
            
            snapshots = list(self._snapshots[container_name][blob_name].values())
            # Sort by snapshot time (oldest first)
            snapshots.sort(key=lambda s: s.snapshot_id if s.snapshot_id else "")
            return snapshots
    
    async def delete_snapshot(
        self,
        container_name: str,
        blob_name: str,
        snapshot_id: str,
    ) -> None:
        """
        Delete a specific blob snapshot.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            snapshot_id: Snapshot identifier
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If snapshot not found
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            if (container_name not in self._snapshots or
                blob_name not in self._snapshots[container_name] or
                snapshot_id not in self._snapshots[container_name][blob_name]):
                raise SnapshotNotFoundError(f"Snapshot '{snapshot_id}' for blob '{blob_name}' not found")
            
            del self._snapshots[container_name][blob_name][snapshot_id]
            
            # Clean up empty dictionaries
            if not self._snapshots[container_name][blob_name]:
                del self._snapshots[container_name][blob_name]
            if not self._snapshots[container_name]:
                del self._snapshots[container_name]
    
    async def delete_blob_with_snapshots(
        self,
        container_name: str,
        blob_name: str,
        delete_snapshots: str = "include",
        lease_id: Optional[str] = None,
    ) -> None:
        """
        Delete a blob and optionally its snapshots.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            delete_snapshots: How to handle snapshots ("include", "only", or None)
            lease_id: Lease ID if blob is leased
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            ValueError: If snapshots exist but delete_snapshots not specified
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            # Check if blob exists
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            # Check if snapshots exist
            has_snapshots = (container_name in self._snapshots and
                           blob_name in self._snapshots[container_name] and
                           len(self._snapshots[container_name][blob_name]) > 0)
            
            if delete_snapshots == "only":
                # Delete only snapshots, keep base blob
                if has_snapshots:
                    del self._snapshots[container_name][blob_name]
                    if not self._snapshots[container_name]:
                        del self._snapshots[container_name]
            elif delete_snapshots == "include":
                # Delete both base blob and snapshots
                if has_snapshots:
                    del self._snapshots[container_name][blob_name]
                    if not self._snapshots[container_name]:
                        del self._snapshots[container_name]
                
                # Validate lease and delete base blob
                self._validate_blob_lease(container_name, blob_name, lease_id)
                del self._blobs[container_name][blob_name]
            else:
                # delete_snapshots is None - delete base blob only (snapshots are orphaned per AC6)
                self._validate_blob_lease(container_name, blob_name, lease_id)
                del self._blobs[container_name][blob_name]
    
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
        lease_id: Optional[str] = None,
    ) -> Blob:
        """
        Commit blocks to create or update a block blob.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            block_list: List of (block_id, block_type) tuples
            content_type: Content type
            metadata: Optional metadata
            lease_id: Optional lease ID for leased blob
            
        Returns:
            Updated blob
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            InvalidBlockIdError: If block ID not found
            LeaseIdMissingError: If blob is leased and lease_id not provided
            LeaseIdMismatchError: If lease_id doesn't match active lease
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            blob = self._blobs[container_name][blob_name]
            
            # Validate lease if blob exists
            self._validate_blob_lease(container_name, blob_name, lease_id)
            
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
    
    # Lease Operations
    
    async def acquire_container_lease(
        self,
        container_name: str,
        duration: int,
        proposed_lease_id: Optional[str] = None,
    ) -> Lease:
        """
        Acquire a lease on a container.
        
        Args:
            container_name: Container name
            duration: Lease duration in seconds (15-60 or -1 for infinite)
            proposed_lease_id: Optional proposed lease ID
            
        Returns:
            New lease
            
        Raises:
            ContainerNotFoundError: If container not found
            LeaseAlreadyPresentError: If container already leased
        """
        # Ensure lease expiration task is running
        self._ensure_expiration_task_running()
        
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            # Check if already leased
            if container_name in self._container_leases:
                existing_lease = self._container_leases[container_name]
                if not existing_lease.is_expired() and not existing_lease.is_broken():
                    raise LeaseAlreadyPresentError(f"Container '{container_name}' is already leased")
            
            # Validate duration
            if duration != -1 and (duration < 15 or duration > 60):
                raise ValueError("Lease duration must be 15-60 seconds or -1 for infinite")
            
            # Create lease
            lease_id = proposed_lease_id or str(uuid.uuid4())
            acquired_time = datetime.now(timezone.utc)
            expiration_time = None if duration == -1 else acquired_time + timedelta(seconds=duration)
            
            lease = Lease(
                lease_id=lease_id,
                duration=duration,
                acquired_time=acquired_time,
                expiration_time=expiration_time,
                state=LeaseState.LEASED,
            )
            
            self._container_leases[container_name] = lease
            
            # Update container lease status
            container = self._containers[container_name]
            container.properties.lease_status = LeaseStatus.LOCKED
            container.properties.lease_state = LeaseState.LEASED
            
            return lease
    
    async def acquire_blob_lease(
        self,
        container_name: str,
        blob_name: str,
        duration: int,
        proposed_lease_id: Optional[str] = None,
    ) -> Lease:
        """
        Acquire a lease on a blob.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            duration: Lease duration in seconds (15-60 or -1 for infinite)
            proposed_lease_id: Optional proposed lease ID
            
        Returns:
            New lease
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            LeaseAlreadyPresentError: If blob already leased
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            # Initialize blob leases dict if needed
            if container_name not in self._blob_leases:
                self._blob_leases[container_name] = {}
            
            # Check if already leased
            if blob_name in self._blob_leases[container_name]:
                existing_lease = self._blob_leases[container_name][blob_name]
                if not existing_lease.is_expired() and not existing_lease.is_broken():
                    raise LeaseAlreadyPresentError(f"Blob '{blob_name}' is already leased")
            
            # Validate duration
            if duration != -1 and (duration < 15 or duration > 60):
                raise ValueError("Lease duration must be 15-60 seconds or -1 for infinite")
            
            # Create lease
            lease_id = proposed_lease_id or str(uuid.uuid4())
            acquired_time = datetime.now(timezone.utc)
            expiration_time = None if duration == -1 else acquired_time + timedelta(seconds=duration)
            
            lease = Lease(
                lease_id=lease_id,
                duration=duration,
                acquired_time=acquired_time,
                expiration_time=expiration_time,
                state=LeaseState.LEASED,
            )
            
            self._blob_leases[container_name][blob_name] = lease
            
            # Update blob lease status
            blob = self._blobs[container_name][blob_name]
            blob.properties.lease_status = LeaseStatus.LOCKED
            blob.properties.lease_state = LeaseState.LEASED
            
            return lease
    
    async def renew_container_lease(
        self,
        container_name: str,
        lease_id: str,
    ) -> Lease:
        """
        Renew a container lease.
        
        Args:
            container_name: Container name
            lease_id: Lease ID to renew
            
        Returns:
            Renewed lease
            
        Raises:
            ContainerNotFoundError: If container not found
            LeaseNotFoundError: If lease not found
            LeaseIdMismatchError: If lease ID doesn't match
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._container_leases:
                raise LeaseNotFoundError(f"No lease found for container '{container_name}'")
            
            lease = self._container_leases[container_name]
            
            if lease.lease_id != lease_id:
                raise LeaseIdMismatchError("Provided lease ID doesn't match active lease")
            
            if lease.is_expired():
                raise LeaseNotFoundError("Lease has expired")
            
            # Renew lease
            acquired_time = datetime.now(timezone.utc)
            if lease.duration == -1:
                lease.expiration_time = None
            else:
                lease.expiration_time = acquired_time + timedelta(seconds=lease.duration)
            
            lease.acquired_time = acquired_time
            lease.state = LeaseState.LEASED
            
            return lease
    
    async def renew_blob_lease(
        self,
        container_name: str,
        blob_name: str,
        lease_id: str,
    ) -> Lease:
        """
        Renew a blob lease.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            lease_id: Lease ID to renew
            
        Returns:
            Renewed lease
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            LeaseNotFoundError: If lease not found
            LeaseIdMismatchError: If lease ID doesn't match
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            if container_name not in self._blob_leases or blob_name not in self._blob_leases[container_name]:
                raise LeaseNotFoundError(f"No lease found for blob '{blob_name}'")
            
            lease = self._blob_leases[container_name][blob_name]
            
            if lease.lease_id != lease_id:
                raise LeaseIdMismatchError("Provided lease ID doesn't match active lease")
            
            if lease.is_expired():
                raise LeaseNotFoundError("Lease has expired")
            
            # Renew lease
            acquired_time = datetime.now(timezone.utc)
            if lease.duration == -1:
                lease.expiration_time = None
            else:
                lease.expiration_time = acquired_time + timedelta(seconds=lease.duration)
            
            lease.acquired_time = acquired_time
            lease.state = LeaseState.LEASED
            
            return lease
    
    async def release_container_lease(
        self,
        container_name: str,
        lease_id: str,
    ) -> None:
        """
        Release a container lease.
        
        Args:
            container_name: Container name
            lease_id: Lease ID to release
            
        Raises:
            ContainerNotFoundError: If container not found
            LeaseNotFoundError: If lease not found
            LeaseIdMismatchError: If lease ID doesn't match
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._container_leases:
                raise LeaseNotFoundError(f"No lease found for container '{container_name}'")
            
            lease = self._container_leases[container_name]
            
            if lease.lease_id != lease_id:
                raise LeaseIdMismatchError("Provided lease ID doesn't match active lease")
            
            # Release lease
            del self._container_leases[container_name]
            
            # Update container lease status
            container = self._containers[container_name]
            container.properties.lease_status = LeaseStatus.UNLOCKED
            container.properties.lease_state = LeaseState.AVAILABLE
    
    async def release_blob_lease(
        self,
        container_name: str,
        blob_name: str,
        lease_id: str,
    ) -> None:
        """
        Release a blob lease.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            lease_id: Lease ID to release
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            LeaseNotFoundError: If lease not found
            LeaseIdMismatchError: If lease ID doesn't match
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            if container_name not in self._blob_leases or blob_name not in self._blob_leases[container_name]:
                raise LeaseNotFoundError(f"No lease found for blob '{blob_name}'")
            
            lease = self._blob_leases[container_name][blob_name]
            
            if lease.lease_id != lease_id:
                raise LeaseIdMismatchError("Provided lease ID doesn't match active lease")
            
            # Release lease
            del self._blob_leases[container_name][blob_name]
            
            # Update blob lease status
            blob = self._blobs[container_name][blob_name]
            blob.properties.lease_status = LeaseStatus.UNLOCKED
            blob.properties.lease_state = LeaseState.AVAILABLE
    
    async def break_container_lease(
        self,
        container_name: str,
        break_period: Optional[int] = None,
    ) -> int:
        """
        Break a container lease.
        
        Args:
            container_name: Container name
            break_period: Break period in seconds (0-60, None for immediate)
            
        Returns:
            Remaining break time in seconds
            
        Raises:
            ContainerNotFoundError: If container not found
            LeaseNotFoundError: If no active lease
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._container_leases:
                raise LeaseNotFoundError(f"No lease found for container '{container_name}'")
            
            lease = self._container_leases[container_name]
            
            # Validate break period
            if break_period is not None and (break_period < 0 or break_period > 60):
                raise ValueError("Break period must be 0-60 seconds")
            
            # Calculate break time
            now = datetime.now(timezone.utc)
            if break_period is None or break_period == 0:
                # Immediate break
                lease.break_time = now
                lease.state = LeaseState.BROKEN
                
                # Release lease
                del self._container_leases[container_name]
                
                # Update container lease status
                container = self._containers[container_name]
                container.properties.lease_status = LeaseStatus.UNLOCKED
                container.properties.lease_state = LeaseState.BROKEN
                
                return 0
            else:
                # Delayed break
                lease.break_time = now + timedelta(seconds=break_period)
                lease.state = LeaseState.BREAKING
                
                # Update container lease status
                container = self._containers[container_name]
                container.properties.lease_state = LeaseState.BREAKING
                
                return break_period
    
    async def break_blob_lease(
        self,
        container_name: str,
        blob_name: str,
        break_period: Optional[int] = None,
    ) -> int:
        """
        Break a blob lease.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            break_period: Break period in seconds (0-60, None for immediate)
            
        Returns:
            Remaining break time in seconds
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            LeaseNotFoundError: If no active lease
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            if container_name not in self._blob_leases or blob_name not in self._blob_leases[container_name]:
                raise LeaseNotFoundError(f"No lease found for blob '{blob_name}'")
            
            lease = self._blob_leases[container_name][blob_name]
            
            # Validate break period
            if break_period is not None and (break_period < 0 or break_period > 60):
                raise ValueError("Break period must be 0-60 seconds")
            
            # Calculate break time
            now = datetime.now(timezone.utc)
            if break_period is None or break_period == 0:
                # Immediate break
                lease.break_time = now
                lease.state = LeaseState.BROKEN
                
                # Release lease
                del self._blob_leases[container_name][blob_name]
                
                # Update blob lease status
                blob = self._blobs[container_name][blob_name]
                blob.properties.lease_status = LeaseStatus.UNLOCKED
                blob.properties.lease_state = LeaseState.BROKEN
                
                return 0
            else:
                # Delayed break
                lease.break_time = now + timedelta(seconds=break_period)
                lease.state = LeaseState.BREAKING
                
                # Update blob lease status
                blob = self._blobs[container_name][blob_name]
                blob.properties.lease_state = LeaseState.BREAKING
                
                return break_period
    
    async def change_container_lease(
        self,
        container_name: str,
        lease_id: str,
        proposed_lease_id: str,
    ) -> Lease:
        """
        Change a container lease ID.
        
        Args:
            container_name: Container name
            lease_id: Current lease ID
            proposed_lease_id: New lease ID
            
        Returns:
            Updated lease
            
        Raises:
            ContainerNotFoundError: If container not found
            LeaseNotFoundError: If lease not found
            LeaseIdMismatchError: If lease ID doesn't match
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._container_leases:
                raise LeaseNotFoundError(f"No lease found for container '{container_name}'")
            
            lease = self._container_leases[container_name]
            
            if lease.lease_id != lease_id:
                raise LeaseIdMismatchError("Provided lease ID doesn't match active lease")
            
            if lease.is_expired():
                raise LeaseNotFoundError("Lease has expired")
            
            # Change lease ID
            lease.lease_id = proposed_lease_id
            
            return lease
    
    async def change_blob_lease(
        self,
        container_name: str,
        blob_name: str,
        lease_id: str,
        proposed_lease_id: str,
    ) -> Lease:
        """
        Change a blob lease ID.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            lease_id: Current lease ID
            proposed_lease_id: New lease ID
            
        Returns:
            Updated lease
            
        Raises:
            ContainerNotFoundError: If container not found
            BlobNotFoundError: If blob not found
            LeaseNotFoundError: If lease not found
            LeaseIdMismatchError: If lease ID doesn't match
        """
        async with self._lock:
            if container_name not in self._containers:
                raise ContainerNotFoundError(f"Container '{container_name}' not found")
            
            if container_name not in self._blobs or blob_name not in self._blobs[container_name]:
                raise BlobNotFoundError(f"Blob '{blob_name}' not found")
            
            if container_name not in self._blob_leases or blob_name not in self._blob_leases[container_name]:
                raise LeaseNotFoundError(f"No lease found for blob '{blob_name}'")
            
            lease = self._blob_leases[container_name][blob_name]
            
            if lease.lease_id != lease_id:
                raise LeaseIdMismatchError("Provided lease ID doesn't match active lease")
            
            if lease.is_expired():
                raise LeaseNotFoundError("Lease has expired")
            
            # Change lease ID
            lease.lease_id = proposed_lease_id
            
            return lease
    
    def _validate_blob_lease(self, container_name: str, blob_name: str, lease_id: Optional[str]) -> None:
        """
        Validate lease ID for blob operations.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            lease_id: Provided lease ID
            
        Raises:
            LeaseIdMissingError: If lease ID required but not provided
            LeaseIdMismatchError: If lease ID doesn't match
        """
        # Check if blob is leased
        if container_name in self._blob_leases and blob_name in self._blob_leases[container_name]:
            active_lease = self._blob_leases[container_name][blob_name]
            
            # Skip validation if lease is expired or broken
            if active_lease.is_expired() or active_lease.is_broken():
                return
            
            # Require lease ID
            if not lease_id:
                raise LeaseIdMissingError("A lease ID must be specified to complete this operation")
            
            # Validate lease ID matches
            if lease_id != active_lease.lease_id:
                raise LeaseIdMismatchError("The lease ID specified did not match the lease ID for the blob")
    
    async def expire_leases(self) -> None:
        """
        Expire all leases that have passed their expiration time.
        
        This should be called periodically as a background task.
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            
            # Expire container leases
            expired_containers = []
            for container_name, lease in list(self._container_leases.items()):
                if lease.is_expired() or (lease.is_breaking() and lease.is_broken()):
                    expired_containers.append(container_name)
            
            for container_name in expired_containers:
                del self._container_leases[container_name]
                container = self._containers[container_name]
                container.properties.lease_status = LeaseStatus.UNLOCKED
                container.properties.lease_state = LeaseState.EXPIRED
            
            # Expire blob leases
            for container_name, blobs in list(self._blob_leases.items()):
                expired_blobs = []
                for blob_name, lease in list(blobs.items()):
                    if lease.is_expired() or (lease.is_breaking() and lease.is_broken()):
                        expired_blobs.append(blob_name)
                
                for blob_name in expired_blobs:
                    del self._blob_leases[container_name][blob_name]
                    blob = self._blobs[container_name][blob_name]
                    blob.properties.lease_status = LeaseStatus.UNLOCKED
                    blob.properties.lease_state = LeaseState.EXPIRED
    
    async def _expiration_loop(self) -> None:
        """
        Background task that periodically expires leases.
        
        Runs every 5 seconds to check for expired leases.
        """
        while not self._stop_expiration:
            try:
                await self.expire_leases()
            except Exception:
                pass  # Ignore errors in background task
            
            # Sleep for 5 seconds between checks
            await asyncio.sleep(5)
    
    def _ensure_expiration_task_running(self) -> None:
        """
        Ensure the lease expiration background task is running.
        
        Called internally by lease operations to lazy-start the background task.
        """
        if self._expiration_task is None or self._expiration_task.done():
            self._stop_expiration = False
            try:
                loop = asyncio.get_running_loop()
                self._expiration_task = loop.create_task(self._expiration_loop())
            except RuntimeError:
                # No running event loop yet
                pass
    
    def start_lease_expiration(self) -> None:
        """
        Start the background lease expiration task.
        
        This should be called when the backend is initialized or the service starts.
        Must be called from within a running event loop.
        """
        if self._expiration_task is None or self._expiration_task.done():
            self._stop_expiration = False
            try:
                loop = asyncio.get_running_loop()
                self._expiration_task = loop.create_task(self._expiration_loop())
            except RuntimeError:
                # No running event loop, will start when first endpoint is called
                pass
    
    async def stop_lease_expiration(self) -> None:
        """
        Stop the background lease expiration task.
        
        This should be called when the backend is shut down or the service stops.
        """
        self._stop_expiration = True
        if self._expiration_task and not self._expiration_task.done():
            await self._expiration_task

