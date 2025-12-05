"""
Pydantic models for Azure Table Storage emulator.

Defines data structures for tables, entities, and validation rules.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict


class TableNameValidator:
    """Validates Azure Table Storage table naming rules."""
    
    @staticmethod
    def validate(name: str) -> tuple[bool, Optional[str]]:
        """
        Validate table name against Azure rules.
        
        Rules:
        - 3-63 characters
        - Alphanumeric only
        - Must start with a letter
        - Case-insensitive (stored as-is but compared case-insensitively)
        
        Args:
            name: Table name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name:
            return False, "Table name cannot be empty"
        
        if len(name) < 3 or len(name) > 63:
            return False, f"Table name must be between 3 and 63 characters, got {len(name)}"
        
        if not re.match(r"^[A-Za-z][A-Za-z0-9]*$", name):
            return False, "Table name must start with a letter and contain only alphanumeric characters"
        
        return True, None


class Table(BaseModel):
    """Azure Table Storage table model."""
    model_config = ConfigDict(extra='forbid')
    
    table_name: str = Field(..., min_length=3, max_length=63)
    
    @field_validator('table_name')
    @classmethod
    def validate_table_name(cls, v: str) -> str:
        """Validate table name."""
        is_valid, error = TableNameValidator.validate(v)
        if not is_valid:
            raise ValueError(error)
        return v


class Entity(BaseModel):
    """
    Azure Table Storage entity model.
    
    Entities must have PartitionKey and RowKey (system properties).
    Timestamp and ETag are managed by the service.
    Custom properties support various types.
    """
    model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True, populate_by_name=True)
    
    # System properties (required)
    PartitionKey: str = Field(..., description="Partition key for the entity")
    RowKey: str = Field(..., description="Row key for the entity")
    Timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last modification timestamp"
    )
    etag: str = Field(
        default="",
        description="ETag for optimistic concurrency",
        alias="odata.etag"
    )
    
    # Custom properties stored in model_extra
    
    @field_validator('PartitionKey', 'RowKey')
    @classmethod
    def validate_keys_not_empty(cls, v: str) -> str:
        """Validate that keys are not empty."""
        if not v or not v.strip():
            raise ValueError("PartitionKey and RowKey cannot be empty")
        return v
    
    def get_custom_properties(self) -> Dict[str, Any]:
        """Get all custom properties (non-system properties)."""
        system_props = {'PartitionKey', 'RowKey', 'Timestamp', 'etag', 'odata.etag'}
        if not hasattr(self, 'model_extra') or self.model_extra is None:
            return {}
        return {k: v for k, v in self.model_extra.items() if k not in system_props}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert entity to dictionary for JSON serialization.
        
        Returns:
            Dictionary with all properties
        """
        result = {
            "PartitionKey": self.PartitionKey,
            "RowKey": self.RowKey,
            "Timestamp": self.Timestamp.isoformat().replace('+00:00', 'Z'),
        }
        
        # Add ETag if present
        if self.etag:
            result["odata.etag"] = self.etag
        
        # Add custom properties
        result.update(self.get_custom_properties())
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        """
        Create entity from dictionary.
        
        Args:
            data: Dictionary with entity data
            
        Returns:
            Entity instance
        """
        # Extract system properties
        partition_key = data.get("PartitionKey", "")
        row_key = data.get("RowKey", "")
        timestamp = data.get("Timestamp")
        etag = data.get("odata.etag", data.get("etag", ""))
        
        # Parse timestamp if string
        if isinstance(timestamp, str):
            # Handle various ISO formats
            timestamp = timestamp.replace('Z', '+00:00')
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Get custom properties
        system_props = {'PartitionKey', 'RowKey', 'Timestamp', 'etag', 'odata.etag'}
        custom_props = {k: v for k, v in data.items() if k not in system_props}
        
        # Create entity
        return cls(
            PartitionKey=partition_key,
            RowKey=row_key,
            Timestamp=timestamp,
            etag=etag,
            **custom_props
        )
    
    @staticmethod
    def generate_etag(timestamp: Optional[datetime] = None) -> str:
        """
        Generate ETag for entity.
        
        Args:
            timestamp: Optional timestamp to use
            
        Returns:
            ETag string in Azure format
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Azure format: W/"datetime'2025-12-04T10%3A30%3A00.123456Z'"
        # Use microseconds for better uniqueness
        ts_str = timestamp.isoformat(timespec='microseconds').replace('+00:00', 'Z')
        # URL-encode the colons
        ts_str = ts_str.replace(':', '%3A')
        return f'W/"datetime\'{ts_str}\'"'


class InsertEntityRequest(BaseModel):
    """Request model for inserting an entity."""
    model_config = ConfigDict(extra='allow')
    
    PartitionKey: str
    RowKey: str
    
    def to_entity(self) -> Entity:
        """Convert request to Entity."""
        data = self.model_dump()
        return Entity.from_dict(data)


class UpdateEntityRequest(BaseModel):
    """Request model for updating an entity (replace all properties)."""
    model_config = ConfigDict(extra='allow')
    
    PartitionKey: str
    RowKey: str
    
    def to_entity(self) -> Entity:
        """Convert request to Entity."""
        data = self.model_dump()
        return Entity.from_dict(data)


class MergeEntityRequest(BaseModel):
    """Request model for merging an entity (update only specified properties)."""
    model_config = ConfigDict(extra='allow')
    
    # PartitionKey and RowKey may not be in body (from URL)
    PartitionKey: Optional[str] = None
    RowKey: Optional[str] = None
    
    def get_properties_to_merge(self) -> Dict[str, Any]:
        """Get properties to merge (excluding None keys)."""
        data = self.model_dump(exclude_none=True)
        # Remove keys if they're None
        return {k: v for k, v in data.items() if k not in ['PartitionKey', 'RowKey'] or v is not None}
