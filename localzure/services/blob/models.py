"""
Blob Storage Container Models

Pydantic models for Azure Blob Storage containers, metadata, and properties.

Author: Ayodele Oladeji
Date: 2025
"""

import re
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator


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
