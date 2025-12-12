"""
Cosmos DB Models.

Pydantic models for Azure Cosmos DB databases and containers,
matching Azure Cosmos DB SDK data structures.

Author: LocalZure Team
Date: 2025-12-11
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PartitionKeyPath(BaseModel):
    """Partition key path configuration.
    
    Attributes:
        paths: List of partition key paths (e.g., ["/userId"])
        kind: Partition key kind (Hash or Range)
        version: Partition key version (1 or 2)
    """
    
    paths: List[str]
    kind: str = "Hash"
    version: int = Field(default=2, alias="Version")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator("paths", mode="before")
    @classmethod
    def validate_paths(cls, v: List[str]) -> List[str]:
        """Validate partition key paths.
        
        Args:
            v: Partition key paths
            
        Returns:
            Validated paths
            
        Raises:
            ValueError: If paths are invalid
        """
        if not v:
            raise ValueError("Partition key paths cannot be empty")
        
        for path in v:
            if not path.startswith("/"):
                raise ValueError(f"Partition key path must start with '/': {path}")
        
        return v
    
    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        """Validate partition key kind.
        
        Args:
            v: Partition key kind
            
        Returns:
            Validated kind
            
        Raises:
            ValueError: If kind is invalid
        """
        if v not in ["Hash", "Range"]:
            raise ValueError(f"Partition key kind must be 'Hash' or 'Range': {v}")
        return v


class PartitionKeyDefinition(BaseModel):
    """Partition key definition for container.
    
    Attributes:
        paths: List of partition key paths
        kind: Partition key kind
        version: Partition key version
    """
    
    paths: List[str]
    kind: str = "Hash"
    version: int = Field(default=2, alias="Version")
    
    model_config = ConfigDict(populate_by_name=True)


class IndexingPolicy(BaseModel):
    """Simplified indexing policy.
    
    Attributes:
        automatic: Whether indexing is automatic
        indexing_mode: Indexing mode (consistent, lazy, none)
    """
    
    automatic: bool = True
    indexing_mode: str = Field(default="consistent", alias="indexingMode")
    
    model_config = ConfigDict(populate_by_name=True)


class Database(BaseModel):
    """Cosmos DB database.
    
    Attributes:
        id: Database identifier
        _rid: Resource ID (internal)
        _ts: Timestamp
        _self: Self link
        _etag: ETag
        _colls: Collections link
        _users: Users link
    """
    
    id: str
    rid: str = Field(default="", alias="_rid")
    ts: int = Field(default=0, alias="_ts")
    self_link: str = Field(default="", alias="_self")
    etag: str = Field(default="", alias="_etag")
    colls: str = Field(default="", alias="_colls")
    users: str = Field(default="", alias="_users")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate database ID.
        
        Args:
            v: Database ID
            
        Returns:
            Validated ID
            
        Raises:
            ValueError: If ID is invalid
        """
        if not v:
            raise ValueError("Database ID cannot be empty")
        
        if len(v) > 255:
            raise ValueError("Database ID must be 255 characters or less")
        
        # Azure Cosmos DB allows alphanumeric, underscore, and hyphen
        if not all(c.isalnum() or c in ['_', '-'] for c in v):
            raise ValueError("Database ID can only contain alphanumeric characters, underscores, and hyphens")
        
        return v


class Container(BaseModel):
    """Cosmos DB container.
    
    Attributes:
        id: Container identifier
        partition_key: Partition key definition
        indexing_policy: Indexing policy
        throughput: Throughput in RU/s
        _rid: Resource ID (internal)
        _ts: Timestamp
        _self: Self link
        _etag: ETag
        _docs: Documents link
        _sprocs: Stored procedures link
        _triggers: Triggers link
        _udfs: User-defined functions link
        _conflicts: Conflicts link
    """
    
    id: str
    partition_key: PartitionKeyDefinition = Field(alias="partitionKey")
    indexing_policy: Optional[IndexingPolicy] = Field(default=None, alias="indexingPolicy")
    throughput: Optional[int] = None
    rid: str = Field(default="", alias="_rid")
    ts: int = Field(default=0, alias="_ts")
    self_link: str = Field(default="", alias="_self")
    etag: str = Field(default="", alias="_etag")
    docs: str = Field(default="", alias="_docs")
    sprocs: str = Field(default="", alias="_sprocs")
    triggers: str = Field(default="", alias="_triggers")
    udfs: str = Field(default="", alias="_udfs")
    conflicts: str = Field(default="", alias="_conflicts")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate container ID.
        
        Args:
            v: Container ID
            
        Returns:
            Validated ID
            
        Raises:
            ValueError: If ID is invalid
        """
        if not v:
            raise ValueError("Container ID cannot be empty")
        
        if len(v) > 255:
            raise ValueError("Container ID must be 255 characters or less")
        
        return v


class CreateDatabaseRequest(BaseModel):
    """Request to create a database.
    
    Attributes:
        id: Database identifier
        throughput: Throughput in RU/s (optional)
    """
    
    id: str
    throughput: Optional[int] = None
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate database ID.
        
        Args:
            v: Database ID
            
        Returns:
            Validated ID
            
        Raises:
            ValueError: If ID is invalid
        """
        if not v:
            raise ValueError("Database ID cannot be empty")
        
        if len(v) > 255:
            raise ValueError("Database ID must be 255 characters or less")
        
        # Azure Cosmos DB allows alphanumeric, underscore, and hyphen
        if not all(c.isalnum() or c in ['_', '-'] for c in v):
            raise ValueError("Database ID can only contain alphanumeric characters, underscores, and hyphens")
        
        return v


class CreateContainerRequest(BaseModel):
    """Request to create a container.
    
    Attributes:
        id: Container identifier
        partition_key: Partition key definition
        indexing_policy: Indexing policy (optional)
        throughput: Throughput in RU/s (optional)
    """
    
    id: str
    partition_key: PartitionKeyDefinition = Field(alias="partitionKey")
    indexing_policy: Optional[IndexingPolicy] = Field(default=None, alias="indexingPolicy")
    throughput: Optional[int] = None
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator("partition_key", mode="before")
    @classmethod
    def validate_partition_key(cls, v):
        """Validate partition key definition.
        
        Args:
            v: Partition key definition or dict
            
        Returns:
            PartitionKeyDefinition
            
        Raises:
            ValueError: If partition key is invalid
        """
        # If it's already a PartitionKeyDefinition, validate its paths
        if isinstance(v, PartitionKeyDefinition):
            for path in v.paths:
                if not path.startswith("/"):
                    raise ValueError(f"Partition key path must start with '/': {path}")
        # If it's a dict, validate paths before model creation
        elif isinstance(v, dict):
            paths = v.get("paths", [])
            for path in paths:
                if not path.startswith("/"):
                    raise ValueError(f"Partition key path must start with '/': {path}")
        
        return v


class DatabaseListResult(BaseModel):
    """List of databases.
    
    Attributes:
        _rid: Resource ID
        databases: List of databases
        _count: Count of databases
    """
    
    rid: str = Field(default="", alias="_rid")
    databases: List[Database] = Field(default_factory=list, alias="Databases")
    count: int = Field(default=0, alias="_count")
    
    model_config = ConfigDict(populate_by_name=True)


class ContainerListResult(BaseModel):
    """List of containers.
    
    Attributes:
        _rid: Resource ID
        document_collections: List of containers
        _count: Count of containers
    """
    
    rid: str = Field(default="", alias="_rid")
    document_collections: List[Container] = Field(default_factory=list, alias="DocumentCollections")
    count: int = Field(default=0, alias="_count")
    
    model_config = ConfigDict(populate_by_name=True)


class Document(BaseModel):
    """Cosmos DB document.
    
    Represents a document with user data and system-generated properties.
    
    Attributes:
        id: Document identifier
        User fields: Any additional fields provided by user
        _rid: Resource ID (system-generated)
        _ts: Timestamp (system-generated)
        _self: Self link (system-generated)
        _etag: ETag for optimistic concurrency (system-generated)
        _attachments: Attachments link (system-generated)
    """
    
    # Allow extra fields for user data
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow"  # Allow any additional fields
    )
    
    # Required user field
    id: str
    
    # System-generated fields
    rid: str = Field(default="", alias="_rid")
    ts: int = Field(default=0, alias="_ts")
    self_link: str = Field(default="", alias="_self")
    etag: str = Field(default="", alias="_etag")
    attachments: str = Field(default="", alias="_attachments")


class CreateDocumentRequest(BaseModel):
    """Request to create a document.
    
    Allows any fields in the document body.
    """
    
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow"  # Allow any fields
    )
    
    # id is optional - will be auto-generated if not provided
    id: Optional[str] = None


class ReplaceDocumentRequest(BaseModel):
    """Request to replace a document.
    
    Replaces entire document with new content.
    """
    
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow"  # Allow any fields
    )
    
    id: str


class PatchOperation(BaseModel):
    """JSON Patch operation.
    
    Attributes:
        op: Operation type (add, remove, replace, set)
        path: JSON path to field
        value: New value (for add/replace/set)
    """
    
    op: str
    path: str
    value: Optional[Any] = None
    
    @field_validator("op", mode="before")
    @classmethod
    def validate_op(cls, v: str) -> str:
        """Validate operation type.
        
        Args:
            v: Operation type
            
        Returns:
            Validated operation
            
        Raises:
            ValueError: If operation is invalid
        """
        valid_ops = ["add", "remove", "replace", "set"]
        if v not in valid_ops:
            raise ValueError(f"Invalid patch operation: {v}. Must be one of {valid_ops}")
        return v


class PatchDocumentRequest(BaseModel):
    """Request to patch a document.
    
    Applies JSON Patch operations to update specific fields.
    
    Attributes:
        operations: List of patch operations
    """
    
    operations: List[PatchOperation]
    
    model_config = ConfigDict(populate_by_name=True)


class DocumentListResult(BaseModel):
    """List of documents.
    
    Attributes:
        _rid: Resource ID
        documents: List of documents
        _count: Count of documents
    """
    
    rid: str = Field(default="", alias="_rid")
    documents: List[Dict[str, Any]] = Field(default_factory=list, alias="Documents")
    count: int = Field(default=0, alias="_count")
    
    model_config = ConfigDict(populate_by_name=True)


class QueryRequest(BaseModel):
    """SQL query request.
    
    Attributes:
        query: SQL query string
        parameters: Query parameters for parameterized queries
    """
    
    query: str
    parameters: Optional[List[Dict[str, Any]]] = None
    
    model_config = ConfigDict(populate_by_name=True)


class QueryResult(BaseModel):
    """SQL query result.
    
    Attributes:
        _rid: Resource ID of container
        documents: Query result documents
        _count: Count of documents in this page
        _continuation: Continuation token for pagination
    """
    
    rid: str = Field(default="", alias="_rid")
    documents: List[Dict[str, Any]] = Field(default_factory=list, alias="Documents")
    count: int = Field(default=0, alias="_count")
    continuation: Optional[str] = Field(default=None, alias="_continuation")
    
    model_config = ConfigDict(populate_by_name=True)
