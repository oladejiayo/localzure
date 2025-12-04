"""
Blob Storage Models

Pydantic models for Azure Blob Storage containers, blobs, metadata, and properties.

Author: Ayodele Oladeji
Date: 2025
"""

import base64
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PublicAccessLevel(str, Enum):
    """Container public access levels."""
    PRIVATE = "private"
    BLOB = "blob"
    CONTAINER = "container"


class LeaseStatus(str, Enum):
    """Container lease status."""
    LOCKED = "locked"
    UNLOCKED = "unlocked"


class LeaseState(str, Enum):
    """Container lease state."""
    AVAILABLE = "available"
    LEASED = "leased"
    EXPIRED = "expired"
    BREAKING = "breaking"
    BROKEN = "broken"


class ContainerNameValidator:
    """
    Validates Azure Blob Storage container names.
    
    Rules:
    - 3-63 characters
    - Lowercase letters, numbers, hyphens only
    - Must start and end with letter or number
    - No consecutive hyphens
    """
    
    # Container name pattern
    PATTERN = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')
    MIN_LENGTH = 3
    MAX_LENGTH = 63
    
    @classmethod
    def validate(cls, name: str) -> tuple[bool, Optional[str]]:
        """
        Validate container name against Azure rules.
        
        Args:
            name: Container name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name:
            return False, "Container name cannot be empty"
        
        if len(name) < cls.MIN_LENGTH:
            return False, f"Container name must be at least {cls.MIN_LENGTH} characters"
        
        if len(name) > cls.MAX_LENGTH:
            return False, f"Container name must be at most {cls.MAX_LENGTH} characters"
        
        if not cls.PATTERN.match(name):
            return False, "Container name must contain only lowercase letters, numbers, and hyphens, and must start/end with letter or number"
        
        if '--' in name:
            return False, "Container name cannot contain consecutive hyphens"
        
        return True, None
    
    @classmethod
    def validate_raise(cls, name: str) -> None:
        """
        Validate container name and raise ValueError if invalid.
        
        Args:
            name: Container name to validate
            
        Raises:
            ValueError: If name is invalid
        """
        is_valid, error = cls.validate(name)
        if not is_valid:
            raise ValueError(error)


class ContainerMetadata(BaseModel):
    """
    Container metadata (x-ms-meta-* headers).
    
    Metadata keys are case-insensitive and stored in lowercase.
    """
    
    metadata: Dict[str, str] = Field(default_factory=dict)
    
    @field_validator('metadata')
    @classmethod
    def validate_metadata(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Ensure all keys are lowercase."""
        return {k.lower(): str(val) for k, val in v.items()}
    
    def to_headers(self) -> Dict[str, str]:
        """Convert metadata to HTTP headers."""
        return {f'x-ms-meta-{k}': v for k, v in self.metadata.items()}
    
    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> 'ContainerMetadata':
        """Extract metadata from HTTP headers."""
        metadata = {}
        for key, value in headers.items():
            if key.lower().startswith('x-ms-meta-'):
                meta_key = key[10:]  # Remove 'x-ms-meta-' prefix
                metadata[meta_key.lower()] = value
        return cls(metadata=metadata)


class ContainerProperties(BaseModel):
    """
    Container properties.
    
    Includes ETag, Last-Modified, lease status, and lease state.
    """
    
    etag: str = Field(description="Entity tag for the container")
    last_modified: datetime = Field(description="Last modified timestamp")
    lease_status: LeaseStatus = Field(default=LeaseStatus.UNLOCKED)
    lease_state: LeaseState = Field(default=LeaseState.AVAILABLE)
    lease_duration: Optional[str] = Field(default=None, description="Lease duration (infinite or seconds)")
    public_access: PublicAccessLevel = Field(default=PublicAccessLevel.PRIVATE)
    has_immutability_policy: bool = Field(default=False)
    has_legal_hold: bool = Field(default=False)
    
    def to_headers(self) -> Dict[str, str]:
        """Convert properties to HTTP headers."""
        headers = {
            'ETag': f'"{self.etag}"',
            'Last-Modified': self.last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'x-ms-lease-status': self.lease_status.value,
            'x-ms-lease-state': self.lease_state.value,
            'x-ms-blob-public-access': self.public_access.value,
            'x-ms-has-immutability-policy': str(self.has_immutability_policy).lower(),
            'x-ms-has-legal-hold': str(self.has_legal_hold).lower(),
        }
        if self.lease_duration:
            headers['x-ms-lease-duration'] = self.lease_duration
        return headers


class Container(BaseModel):
    """
    Azure Blob Storage container.
    
    Represents a container with metadata and properties.
    """
    
    name: str = Field(description="Container name")
    metadata: ContainerMetadata = Field(default_factory=ContainerMetadata)
    properties: ContainerProperties
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate container name."""
        ContainerNameValidator.validate_raise(v)
        return v
    
    def to_dict(self) -> Dict:
        """Convert container to dictionary for API responses."""
        return {
            'Name': self.name,
            'Properties': {
                'Etag': self.properties.etag,
                'Last-Modified': self.properties.last_modified.isoformat(),
                'LeaseStatus': self.properties.lease_status.value,
                'LeaseState': self.properties.lease_state.value,
                'PublicAccess': self.properties.public_access.value,
            },
            'Metadata': self.metadata.metadata,
        }


class CreateContainerRequest(BaseModel):
    """Request model for creating a container."""
    
    metadata: Optional[Dict[str, str]] = Field(default=None)
    public_access: PublicAccessLevel = Field(default=PublicAccessLevel.PRIVATE)


class SetContainerMetadataRequest(BaseModel):
    """Request model for setting container metadata."""
    
    metadata: Dict[str, str] = Field(default_factory=dict)


# ============================================================================
# Blob Models
# ============================================================================


class BlobType(str, Enum):
    """Blob type."""
    BLOCK_BLOB = "BlockBlob"
    APPEND_BLOB = "AppendBlob"
    PAGE_BLOB = "PageBlob"


class BlobTier(str, Enum):
    """Blob access tier."""
    HOT = "Hot"
    COOL = "Cool"
    ARCHIVE = "Archive"


class Block(BaseModel):
    """
    Block in a block blob.
    
    Represents a staged or committed block with its ID and content.
    """
    
    block_id: str = Field(description="Base64-encoded block ID")
    size: int = Field(description="Block size in bytes")
    content: bytes = Field(description="Block content")
    committed: bool = Field(default=False, description="Whether block is committed")
    
    @field_validator('block_id')
    @classmethod
    def validate_block_id(cls, v: str) -> str:
        """Validate block ID is valid base64 and not too long."""
        try:
            decoded = base64.b64decode(v)
            if len(decoded) > 64:
                raise ValueError("Block ID must be at most 64 bytes before encoding")
        except Exception as e:
            raise ValueError(f"Invalid base64 block ID: {e}")
        return v
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class BlobProperties(BaseModel):
    """
    Blob properties.
    
    Includes content properties, ETag, timestamps, and blob-specific metadata.
    """
    
    etag: str = Field(description="Entity tag for the blob")
    last_modified: datetime = Field(description="Last modified timestamp")
    content_length: int = Field(description="Blob size in bytes")
    content_type: str = Field(default="application/octet-stream")
    content_encoding: Optional[str] = Field(default=None)
    content_language: Optional[str] = Field(default=None)
    content_md5: Optional[str] = Field(default=None)
    cache_control: Optional[str] = Field(default=None)
    content_disposition: Optional[str] = Field(default=None)
    blob_type: BlobType = Field(default=BlobType.BLOCK_BLOB)
    lease_status: LeaseStatus = Field(default=LeaseStatus.UNLOCKED)
    lease_state: LeaseState = Field(default=LeaseState.AVAILABLE)
    blob_tier: BlobTier = Field(default=BlobTier.HOT)
    creation_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Blob creation timestamp")
    
    def to_headers(self) -> Dict[str, str]:
        """Convert properties to HTTP headers."""
        headers = {
            'ETag': f'"{self.etag}"',
            'Last-Modified': self.last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'Content-Length': str(self.content_length),
            'Content-Type': self.content_type,
            'x-ms-blob-type': self.blob_type.value,
            'x-ms-lease-status': self.lease_status.value,
            'x-ms-lease-state': self.lease_state.value,
            'x-ms-access-tier': self.blob_tier.value,
            'x-ms-creation-time': self.creation_time.strftime('%a, %d %b %Y %H:%M:%S GMT'),
        }
        
        if self.content_encoding:
            headers['Content-Encoding'] = self.content_encoding
        if self.content_language:
            headers['Content-Language'] = self.content_language
        if self.content_md5:
            headers['Content-MD5'] = self.content_md5
        if self.cache_control:
            headers['Cache-Control'] = self.cache_control
        if self.content_disposition:
            headers['Content-Disposition'] = self.content_disposition
        
        return headers


class Blob(BaseModel):
    """
    Azure Blob Storage blob.
    
    Represents a blob with content, metadata, and properties.
    """
    
    name: str = Field(description="Blob name")
    container_name: str = Field(description="Parent container name")
    content: bytes = Field(description="Blob content")
    metadata: ContainerMetadata = Field(default_factory=ContainerMetadata)
    properties: BlobProperties
    uncommitted_blocks: Dict[str, Block] = Field(default_factory=dict)
    committed_blocks: List[str] = Field(default_factory=list)  # Ordered list of block IDs
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def to_dict(self) -> Dict:
        """Convert blob to dictionary for API responses."""
        return {
            'Name': self.name,
            'Properties': {
                'Content-Length': self.properties.content_length,
                'Content-Type': self.properties.content_type,
                'Etag': self.properties.etag,
                'Last-Modified': self.properties.last_modified.isoformat(),
                'BlobType': self.properties.blob_type.value,
                'LeaseStatus': self.properties.lease_status.value,
                'LeaseState': self.properties.lease_state.value,
                'AccessTier': self.properties.blob_tier.value,
            },
            'Metadata': self.metadata.metadata,
        }


class BlockListType(str, Enum):
    """Block list type for Put Block List."""
    COMMITTED = "Committed"
    UNCOMMITTED = "Uncommitted"
    LATEST = "Latest"


class BlockReference(BaseModel):
    """Reference to a block in Put Block List."""
    block_id: str = Field(description="Base64-encoded block ID")
    block_type: BlockListType = Field(description="Block type (Committed/Uncommitted/Latest)")


class PutBlockListRequest(BaseModel):
    """Request model for Put Block List operation."""
    blocks: List[BlockReference] = Field(description="List of blocks to commit")


class ConditionalHeaders(BaseModel):
    """Conditional request headers."""
    if_match: Optional[str] = Field(default=None, description="ETag to match")
    if_none_match: Optional[str] = Field(default=None, description="ETag to not match")
    if_modified_since: Optional[datetime] = Field(default=None, description="Modified since timestamp")
    if_unmodified_since: Optional[datetime] = Field(default=None, description="Unmodified since timestamp")
    
    def check_conditions(self, etag: str, last_modified: datetime) -> Optional[int]:
        """
        Check conditional headers against blob properties.
        
        Args:
            etag: Current blob ETag
            last_modified: Current blob last modified time
            
        Returns:
            None if conditions pass, HTTP status code if they fail
        """
        # If-Match: return 412 if ETag doesn't match
        if self.if_match and self.if_match != f'"{etag}"' and self.if_match != etag:
            return 412
        
        # If-None-Match: return 304 if ETag matches
        if self.if_none_match and (self.if_none_match == f'"{etag}"' or self.if_none_match == etag):
            return 304
        
        # If-Modified-Since: return 304 if not modified
        if self.if_modified_since and last_modified <= self.if_modified_since:
            return 304
        
        # If-Unmodified-Since: return 412 if modified
        if self.if_unmodified_since and last_modified > self.if_unmodified_since:
            return 412
        
        return None

