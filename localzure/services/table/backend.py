"""
Azure Table Storage backend implementation.

Provides in-memory storage for tables and entities with async operations.
"""

import asyncio
import base64
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from localzure.services.table.models import Table, Entity
from localzure.services.table.query import ODataQuery


class TableAlreadyExistsError(Exception):
    """Raised when attempting to create a table that already exists."""
    pass


class TableNotFoundError(Exception):
    """Raised when a table is not found."""
    pass


class EntityAlreadyExistsError(Exception):
    """Raised when attempting to insert an entity that already exists."""
    pass


class EntityNotFoundError(Exception):
    """Raised when an entity is not found."""
    pass


class ETagMismatchError(Exception):
    """Raised when ETag doesn't match for optimistic concurrency."""
    pass


class TableBackend:
    """
    In-memory backend for Azure Table Storage emulation.
    
    Stores tables and their entities in memory with async-safe operations.
    """
    
    def __init__(self):
        """Initialize the backend with empty storage."""
        self._tables: Dict[str, Table] = {}
        # Store entities: table_name -> {(partition_key, row_key): Entity}
        self._entities: Dict[str, Dict[tuple[str, str], Entity]] = defaultdict(dict)
        self._lock = asyncio.Lock()
    
    async def reset(self) -> None:
        """Reset all tables and entities."""
        async with self._lock:
            self._tables.clear()
            self._entities.clear()
    
    async def create_table(self, table_name: str) -> Table:
        """
        Create a new table.
        
        Args:
            table_name: Name of the table to create
            
        Returns:
            Created Table object
            
        Raises:
            TableAlreadyExistsError: If table already exists
        """
        async with self._lock:
            # Case-insensitive comparison for table names
            existing_key = self._find_table_key(table_name)
            if existing_key is not None:
                raise TableAlreadyExistsError(f"Table '{table_name}' already exists")
            
            table = Table(table_name=table_name)
            self._tables[table_name] = table
            self._entities[table_name] = {}
            
            return table
    
    async def delete_table(self, table_name: str) -> None:
        """
        Delete a table and all its entities.
        
        Args:
            table_name: Name of the table to delete
            
        Raises:
            TableNotFoundError: If table not found
        """
        async with self._lock:
            existing_key = self._find_table_key(table_name)
            if existing_key is None:
                raise TableNotFoundError(f"Table '{table_name}' not found")
            
            del self._tables[existing_key]
            del self._entities[existing_key]
    
    async def list_tables(self) -> List[Table]:
        """
        List all tables.
        
        Returns:
            List of all tables
        """
        async with self._lock:
            return list(self._tables.values())
    
    async def insert_entity(
        self,
        table_name: str,
        entity: Entity
    ) -> Entity:
        """
        Insert a new entity into a table.
        
        Args:
            table_name: Name of the table
            entity: Entity to insert
            
        Returns:
            Inserted entity with generated Timestamp and ETag
            
        Raises:
            TableNotFoundError: If table not found
            EntityAlreadyExistsError: If entity already exists
        """
        async with self._lock:
            existing_key = self._find_table_key(table_name)
            if existing_key is None:
                raise TableNotFoundError(f"Table '{table_name}' not found")
            
            key = (entity.PartitionKey, entity.RowKey)
            if key in self._entities[existing_key]:
                raise EntityAlreadyExistsError(
                    f"Entity with PartitionKey '{entity.PartitionKey}' "
                    f"and RowKey '{entity.RowKey}' already exists"
                )
            
            # Set system properties
            entity.Timestamp = datetime.now(timezone.utc)
            entity.etag = Entity.generate_etag(entity.Timestamp)
            
            self._entities[existing_key][key] = entity
            return entity
    
    async def get_entity(
        self,
        table_name: str,
        partition_key: str,
        row_key: str
    ) -> Entity:
        """
        Get an entity by partition and row keys.
        
        Args:
            table_name: Name of the table
            partition_key: Partition key
            row_key: Row key
            
        Returns:
            Entity
            
        Raises:
            TableNotFoundError: If table not found
            EntityNotFoundError: If entity not found
        """
        async with self._lock:
            existing_key = self._find_table_key(table_name)
            if existing_key is None:
                raise TableNotFoundError(f"Table '{table_name}' not found")
            
            key = (partition_key, row_key)
            if key not in self._entities[existing_key]:
                raise EntityNotFoundError(
                    f"Entity with PartitionKey '{partition_key}' "
                    f"and RowKey '{row_key}' not found"
                )
            
            return self._entities[existing_key][key]
    
    async def update_entity(
        self,
        table_name: str,
        partition_key: str,
        row_key: str,
        entity: Entity,
        if_match: Optional[str] = None
    ) -> Entity:
        """
        Update (replace) an entity.
        
        Args:
            table_name: Name of the table
            partition_key: Partition key
            row_key: Row key
            entity: New entity data
            if_match: Optional ETag for optimistic concurrency
            
        Returns:
            Updated entity
            
        Raises:
            TableNotFoundError: If table not found
            EntityNotFoundError: If entity not found
            ETagMismatchError: If ETag doesn't match
        """
        async with self._lock:
            existing_key = self._find_table_key(table_name)
            if existing_key is None:
                raise TableNotFoundError(f"Table '{table_name}' not found")
            
            key = (partition_key, row_key)
            if key not in self._entities[existing_key]:
                raise EntityNotFoundError(
                    f"Entity with PartitionKey '{partition_key}' "
                    f"and RowKey '{row_key}' not found"
                )
            
            existing_entity = self._entities[existing_key][key]
            
            # Check ETag if provided
            if if_match and if_match != "*":
                if existing_entity.etag != if_match:
                    raise ETagMismatchError(
                        f"ETag mismatch: expected '{if_match}', got '{existing_entity.etag}'"
                    )
            
            # Update entity (replace all properties)
            entity.PartitionKey = partition_key
            entity.RowKey = row_key
            entity.Timestamp = datetime.now(timezone.utc)
            entity.etag = Entity.generate_etag(entity.Timestamp)
            
            self._entities[existing_key][key] = entity
            return entity
    
    async def merge_entity(
        self,
        table_name: str,
        partition_key: str,
        row_key: str,
        properties: Dict[str, any],
        if_match: Optional[str] = None
    ) -> Entity:
        """
        Merge (update) an entity with specified properties.
        
        Args:
            table_name: Name of the table
            partition_key: Partition key
            row_key: Row key
            properties: Properties to merge
            if_match: Optional ETag for optimistic concurrency
            
        Returns:
            Merged entity
            
        Raises:
            TableNotFoundError: If table not found
            EntityNotFoundError: If entity not found
            ETagMismatchError: If ETag doesn't match
        """
        async with self._lock:
            existing_key = self._find_table_key(table_name)
            if existing_key is None:
                raise TableNotFoundError(f"Table '{table_name}' not found")
            
            key = (partition_key, row_key)
            if key not in self._entities[existing_key]:
                raise EntityNotFoundError(
                    f"Entity with PartitionKey '{partition_key}' "
                    f"and RowKey '{row_key}' not found"
                )
            
            existing_entity = self._entities[existing_key][key]
            
            # Check ETag if provided
            if if_match and if_match != "*":
                if existing_entity.etag != if_match:
                    raise ETagMismatchError(
                        f"ETag mismatch: expected '{if_match}', got '{existing_entity.etag}'"
                    )
            
            # Merge properties
            entity_dict = existing_entity.to_dict()
            entity_dict.update(properties)
            
            # Create updated entity
            merged_entity = Entity.from_dict(entity_dict)
            merged_entity.Timestamp = datetime.now(timezone.utc)
            merged_entity.etag = Entity.generate_etag(merged_entity.Timestamp)
            
            self._entities[existing_key][key] = merged_entity
            return merged_entity
    
    async def delete_entity(
        self,
        table_name: str,
        partition_key: str,
        row_key: str,
        if_match: Optional[str] = None
    ) -> None:
        """
        Delete an entity.
        
        Args:
            table_name: Name of the table
            partition_key: Partition key
            row_key: Row key
            if_match: Optional ETag for optimistic concurrency
            
        Raises:
            TableNotFoundError: If table not found
            EntityNotFoundError: If entity not found
            ETagMismatchError: If ETag doesn't match
        """
        async with self._lock:
            existing_key = self._find_table_key(table_name)
            if existing_key is None:
                raise TableNotFoundError(f"Table '{table_name}' not found")
            
            key = (partition_key, row_key)
            if key not in self._entities[existing_key]:
                raise EntityNotFoundError(
                    f"Entity with PartitionKey '{partition_key}' "
                    f"and RowKey '{row_key}' not found"
                )
            
            existing_entity = self._entities[existing_key][key]
            
            # Check ETag if provided
            if if_match and if_match != "*":
                if existing_entity.etag != if_match:
                    raise ETagMismatchError(
                        f"ETag mismatch: expected '{if_match}', got '{existing_entity.etag}'"
                    )
            
            del self._entities[existing_key][key]
    
    async def query_entities(
        self,
        table_name: str,
        filter_expr: Optional[str] = None,
        select: Optional[str] = None,
        top: Optional[int] = None,
        next_partition_key: Optional[str] = None,
        next_row_key: Optional[str] = None,
    ) -> Tuple[List[Entity], Optional[str]]:
        """
        Query entities with OData filter expression.
        
        Args:
            table_name: Name of the table
            filter_expr: OData $filter expression
            select: $select comma-separated properties
            top: $top result limit (default 1000)
            next_partition_key: Continuation token partition key
            next_row_key: Continuation token row key
            
        Returns:
            Tuple of (entity list, continuation_token)
            
        Raises:
            TableNotFoundError: If table not found
        """
        async with self._lock:
            existing_key = self._find_table_key(table_name)
            if existing_key is None:
                raise TableNotFoundError(f"Table '{table_name}' not found")
            
            # Get all entities for this table
            all_entities = self._entities.get(existing_key, {})
            
            # Create OData query
            query = ODataQuery(filter_expr=filter_expr, select=select, top=top)
            
            # Determine actual limit (default 1000)
            limit = top if top is not None else 1000
            
            # Sort entities by PartitionKey, then RowKey for consistent pagination
            sorted_keys = sorted(all_entities.keys())
            
            # Find starting position if continuation token provided
            start_idx = 0
            if next_partition_key and next_row_key:
                for idx, (pk, rk) in enumerate(sorted_keys):
                    if pk == next_partition_key and rk == next_row_key:
                        start_idx = idx  # Start FROM the continuation key (which points to next entity)
                        break
            
            # Filter and collect results
            results = []
            last_key = None
            
            for pk, rk in sorted_keys[start_idx:]:
                entity = all_entities[(pk, rk)]
                entity_dict = entity.to_dict()
                
                # Check if matches filter
                if query.matches(entity_dict):
                    # Project properties
                    projected = query.project(entity_dict)
                    
                    # Create entity from projected dict (preserve original entity for metadata)
                    result_entity = Entity.from_dict(projected)
                    results.append(result_entity)
                    last_key = (pk, rk)
                    
                    if len(results) >= limit:
                        break
            
            # Generate continuation token if more results exist
            continuation_token = None
            if last_key and len(results) >= limit:
                # Check if there are more entities after this one
                last_idx = sorted_keys.index(last_key)
                if last_idx + 1 < len(sorted_keys):
                    next_pk, next_rk = sorted_keys[last_idx + 1]
                    token_data = {
                        "NextPartitionKey": next_pk,
                        "NextRowKey": next_rk
                    }
                    continuation_token = base64.b64encode(
                        json.dumps(token_data).encode()
                    ).decode()
            
            return results, continuation_token
    
    def _find_table_key(self, table_name: str) -> Optional[str]:
        """
        Find table key with case-insensitive comparison.
        
        Args:
            table_name: Table name to find
            
        Returns:
            Actual key in storage, or None if not found
        """
        table_name_lower = table_name.lower()
        for key in self._tables.keys():
            if key.lower() == table_name_lower:
                return key
        return None


# Global backend instance
backend = TableBackend()
