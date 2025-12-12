"""
Cosmos DB Backend.

Backend implementation for Azure Cosmos DB database and container management,
using in-memory storage with async locking.

Author: LocalZure Team
Date: 2025-12-11
"""

import asyncio
import time
import hashlib
import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any

from .models import (
    Database,
    Container,
    CreateDatabaseRequest,
    CreateContainerRequest,
    DatabaseListResult,
    ContainerListResult,
    PartitionKeyDefinition,
    CreateDocumentRequest,
    ReplaceDocumentRequest,
    PatchDocumentRequest,
    PatchOperation,
    DocumentListResult,
    QueryRequest,
    QueryResult,
)
from .exceptions import (
    DatabaseNotFoundError,
    DatabaseAlreadyExistsError,
    ContainerNotFoundError,
    ContainerAlreadyExistsError,
    InvalidPartitionKeyError,
    DocumentNotFoundError,
    DocumentAlreadyExistsError,
    PreconditionFailedError,
)


class CosmosDBBackend:
    """Backend for Cosmos DB operations.
    
    Provides database and container management with in-memory storage.
    Thread-safe with async locking for concurrent operations.
    
    Attributes:
        _databases: Dictionary of databases by ID
        _containers: Dictionary of containers by database ID and container ID
        _lock: Async lock for thread safety
    """
    
    def __init__(self) -> None:
        """Initialize Cosmos DB backend."""
        self._databases: Dict[str, Database] = {}
        self._containers: Dict[str, Dict[str, Container]] = {}
        # Documents storage: {database_id: {container_id: {partition_key: {doc_id: doc}}}}
        self._documents: Dict[str, Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]] = {}
        self._lock = asyncio.Lock()
    
    def _generate_resource_id(self, resource_type: str, identifier: str) -> str:
        """Generate a unique resource ID.
        
        Args:
            resource_type: Type of resource (db, coll, etc.)
            identifier: Resource identifier
            
        Returns:
            Generated resource ID
        """
        hash_input = f"{resource_type}:{identifier}:{time.time()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:8]
    
    def _generate_timestamp(self) -> int:
        """Generate current timestamp.
        
        Returns:
            Current Unix timestamp
        """
        return int(datetime.now(timezone.utc).timestamp())
    
    async def create_database(self, request: CreateDatabaseRequest) -> Database:
        """Create a new database.
        
        Args:
            request: Database creation request
            
        Returns:
            Created database
            
        Raises:
            DatabaseAlreadyExistsError: If database already exists
        """
        async with self._lock:
            if request.id in self._databases:
                raise DatabaseAlreadyExistsError(
                    f"Database with id '{request.id}' already exists",
                    database_id=request.id
                )
            
            # Generate resource metadata
            rid = self._generate_resource_id("db", request.id)
            ts = self._generate_timestamp()
            
            # Create database
            database = Database(
                id=request.id,
                _rid=rid,
                _ts=ts,
                _self=f"dbs/{rid}",
                _etag=f'"{rid}"',
                _colls=f"dbs/{rid}/colls/",
                _users=f"dbs/{rid}/users/"
            )
            
            self._databases[request.id] = database
            self._containers[request.id] = {}
            
            return database
    
    async def list_databases(self) -> DatabaseListResult:
        """List all databases.
        
        Returns:
            List of databases
        """
        async with self._lock:
            databases = list(self._databases.values())
            return DatabaseListResult(
                _rid="",
                Databases=databases,
                _count=len(databases)
            )
    
    async def get_database(self, database_id: str) -> Database:
        """Get a database by ID.
        
        Args:
            database_id: Database identifier
            
        Returns:
            Database
            
        Raises:
            DatabaseNotFoundError: If database not found
        """
        async with self._lock:
            if database_id not in self._databases:
                raise DatabaseNotFoundError(
                    f"Database with id '{database_id}' not found",
                    database_id=database_id
                )
            return self._databases[database_id]
    
    async def delete_database(self, database_id: str) -> None:
        """Delete a database and all its containers.
        
        Args:
            database_id: Database identifier
            
        Raises:
            DatabaseNotFoundError: If database not found
        """
        async with self._lock:
            if database_id not in self._databases:
                raise DatabaseNotFoundError(
                    f"Database with id '{database_id}' not found",
                    database_id=database_id
                )
            
            # Cascade delete: Remove all containers in the database
            if database_id in self._containers:
                del self._containers[database_id]
            
            # Remove database
            del self._databases[database_id]
    
    async def create_container(
        self,
        database_id: str,
        request: CreateContainerRequest
    ) -> Container:
        """Create a new container in a database.
        
        Args:
            database_id: Database identifier
            request: Container creation request
            
        Returns:
            Created container
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerAlreadyExistsError: If container already exists
            InvalidPartitionKeyError: If partition key is invalid
        """
        async with self._lock:
            # Verify database exists
            if database_id not in self._databases:
                raise DatabaseNotFoundError(
                    f"Database with id '{database_id}' not found",
                    database_id=database_id
                )
            
            # Verify container doesn't exist
            if request.id in self._containers[database_id]:
                raise ContainerAlreadyExistsError(
                    f"Container with id '{request.id}' already exists in database '{database_id}'",
                    database_id=database_id,
                    container_id=request.id
                )
            
            # Validate partition key paths
            for path in request.partition_key.paths:
                if not path.startswith("/"):
                    raise InvalidPartitionKeyError(
                        f"Partition key path must start with '/': {path}",
                        partition_key_path=path
                    )
            
            # Generate resource metadata
            rid = self._generate_resource_id("coll", request.id)
            ts = self._generate_timestamp()
            db = self._databases[database_id]
            
            # Create container
            container = Container(
                id=request.id,
                partitionKey=request.partition_key,
                indexingPolicy=request.indexing_policy,
                throughput=request.throughput,
                _rid=rid,
                _ts=ts,
                _self=f"{db.self_link}/colls/{rid}",
                _etag=f'"{rid}"',
                _docs=f"{db.self_link}/colls/{rid}/docs/",
                _sprocs=f"{db.self_link}/colls/{rid}/sprocs/",
                _triggers=f"{db.self_link}/colls/{rid}/triggers/",
                _udfs=f"{db.self_link}/colls/{rid}/udfs/",
                _conflicts=f"{db.self_link}/colls/{rid}/conflicts/"
            )
            
            self._containers[database_id][request.id] = container
            
            return container
    
    async def list_containers(self, database_id: str) -> ContainerListResult:
        """List all containers in a database.
        
        Args:
            database_id: Database identifier
            
        Returns:
            List of containers
            
        Raises:
            DatabaseNotFoundError: If database not found
        """
        async with self._lock:
            # Verify database exists
            if database_id not in self._databases:
                raise DatabaseNotFoundError(
                    f"Database with id '{database_id}' not found",
                    database_id=database_id
                )
            
            containers = list(self._containers[database_id].values())
            return ContainerListResult(
                _rid=self._databases[database_id].rid,
                DocumentCollections=containers,
                _count=len(containers)
            )
    
    async def get_container(self, database_id: str, container_id: str) -> Container:
        """Get a container by ID.
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            
        Returns:
            Container
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            # Verify database exists
            if database_id not in self._databases:
                raise DatabaseNotFoundError(
                    f"Database with id '{database_id}' not found",
                    database_id=database_id
                )
            
            # Verify container exists
            if container_id not in self._containers[database_id]:
                raise ContainerNotFoundError(
                    f"Container with id '{container_id}' not found in database '{database_id}'",
                    database_id=database_id,
                    container_id=container_id
                )
            
            return self._containers[database_id][container_id]
    
    async def delete_container(self, database_id: str, container_id: str) -> None:
        """Delete a container from a database.
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            # Verify database exists
            if database_id not in self._databases:
                raise DatabaseNotFoundError(
                    f"Database with id '{database_id}' not found",
                    database_id=database_id
                )
            
            # Verify container exists
            if container_id not in self._containers[database_id]:
                raise ContainerNotFoundError(
                    f"Container with id '{container_id}' not found in database '{database_id}'",
                    database_id=database_id,
                    container_id=container_id
                )
            
            # Remove container
            del self._containers[database_id][container_id]
    
    def _extract_partition_key_value(self, document: Dict[str, Any], partition_key_path: str) -> str:
        """Extract partition key value from document.
        
        Args:
            document: Document data
            partition_key_path: Partition key path (e.g., "/userId")
            
        Returns:
            Partition key value
            
        Raises:
            ValueError: If partition key not found in document
        """
        # Remove leading slash
        key_name = partition_key_path.lstrip("/")
        
        if key_name not in document:
            raise ValueError(f"Partition key '{key_name}' not found in document")
        
        return str(document[key_name])
    
    def _generate_etag(self) -> str:
        """Generate an ETag value.
        
        Returns:
            ETag string
        """
        return f'"{uuid.uuid4().hex[:16]}"'
    
    def _apply_patch_operations(self, document: Dict[str, Any], operations: List[PatchOperation]) -> Dict[str, Any]:
        """Apply JSON Patch operations to document.
        
        Args:
            document: Document to patch
            operations: List of patch operations
            
        Returns:
            Patched document
            
        Raises:
            ValueError: If operation is invalid
        """
        doc = copy.deepcopy(document)
        
        for op in operations:
            path = op.path.lstrip("/")
            
            if op.op == "add" or op.op == "set" or op.op == "replace":
                doc[path] = op.value
            elif op.op == "remove":
                if path in doc:
                    del doc[path]
        
        return doc
    
    async def create_document(
        self,
        database_id: str,
        container_id: str,
        document_data: Dict[str, Any],
        partition_key_value: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new document in a container.
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            document_data: Document data
            partition_key_value: Partition key value (optional if in document)
            
        Returns:
            Created document with system properties
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
            DocumentAlreadyExistsError: If document already exists
            ValueError: If partition key not provided
        """
        async with self._lock:
            # Verify container exists
            container = await self._get_container_unlocked(database_id, container_id)
            
            # Generate ID if not provided
            if "id" not in document_data or not document_data["id"]:
                document_data["id"] = str(uuid.uuid4())
            
            doc_id = document_data["id"]
            
            # Extract partition key value
            partition_key_path = container.partition_key.paths[0]
            if partition_key_value is None:
                partition_key_value = self._extract_partition_key_value(document_data, partition_key_path)
            
            # Initialize storage if needed
            if database_id not in self._documents:
                self._documents[database_id] = {}
            if container_id not in self._documents[database_id]:
                self._documents[database_id][container_id] = {}
            if partition_key_value not in self._documents[database_id][container_id]:
                self._documents[database_id][container_id][partition_key_value] = {}
            
            # Check if document exists
            if doc_id in self._documents[database_id][container_id][partition_key_value]:
                raise DocumentAlreadyExistsError(
                    f"Document with id '{doc_id}' already exists",
                    document_id=doc_id,
                    partition_key=partition_key_value
                )
            
            # Add system properties
            rid = self._generate_resource_id("doc", doc_id)
            ts = self._generate_timestamp()
            etag = self._generate_etag()
            
            document = {
                **document_data,
                "_rid": rid,
                "_ts": ts,
                "_self": f"{container.self_link}/docs/{rid}",
                "_etag": etag,
                "_attachments": f"{container.self_link}/docs/{rid}/attachments/"
            }
            
            # Store document
            self._documents[database_id][container_id][partition_key_value][doc_id] = document
            
            return document
    
    async def get_document(
        self,
        database_id: str,
        container_id: str,
        document_id: str,
        partition_key_value: str
    ) -> Dict[str, Any]:
        """Get a document by ID and partition key.
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            document_id: Document identifier
            partition_key_value: Partition key value
            
        Returns:
            Document
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
            DocumentNotFoundError: If document not found
        """
        async with self._lock:
            # Verify container exists
            await self._get_container_unlocked(database_id, container_id)
            
            # Check document exists
            if (database_id not in self._documents or
                container_id not in self._documents[database_id] or
                partition_key_value not in self._documents[database_id][container_id] or
                document_id not in self._documents[database_id][container_id][partition_key_value]):
                raise DocumentNotFoundError(
                    f"Document with id '{document_id}' and partition key '{partition_key_value}' not found",
                    document_id=document_id,
                    partition_key=partition_key_value
                )
            
            return copy.deepcopy(self._documents[database_id][container_id][partition_key_value][document_id])
    
    async def replace_document(
        self,
        database_id: str,
        container_id: str,
        document_id: str,
        document_data: Dict[str, Any],
        partition_key_value: str,
        if_match_etag: Optional[str] = None
    ) -> Dict[str, Any]:
        """Replace an entire document.
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            document_id: Document identifier
            document_data: New document data
            partition_key_value: Partition key value
            if_match_etag: Expected ETag for optimistic concurrency
            
        Returns:
            Replaced document with updated system properties
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
            DocumentNotFoundError: If document not found
            PreconditionFailedError: If ETag doesn't match
        """
        async with self._lock:
            # Verify container exists
            container = await self._get_container_unlocked(database_id, container_id)
            
            # Get existing document
            existing_doc = await self._get_document_unlocked(
                database_id, container_id, document_id, partition_key_value
            )
            
            # Check ETag if provided
            if if_match_etag and existing_doc["_etag"] != if_match_etag:
                raise PreconditionFailedError(
                    f"ETag mismatch. Expected '{if_match_etag}', got '{existing_doc['_etag']}'",
                    etag=if_match_etag
                )
            
            # Update document data
            document_data["id"] = document_id
            
            # Preserve _rid, update other system properties
            ts = self._generate_timestamp()
            etag = self._generate_etag()
            
            document = {
                **document_data,
                "_rid": existing_doc["_rid"],
                "_ts": ts,
                "_self": existing_doc["_self"],
                "_etag": etag,
                "_attachments": existing_doc["_attachments"]
            }
            
            # Store updated document
            self._documents[database_id][container_id][partition_key_value][document_id] = document
            
            return document
    
    async def patch_document(
        self,
        database_id: str,
        container_id: str,
        document_id: str,
        operations: List[PatchOperation],
        partition_key_value: str,
        if_match_etag: Optional[str] = None
    ) -> Dict[str, Any]:
        """Patch specific fields in a document.
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            document_id: Document identifier
            operations: List of patch operations
            partition_key_value: Partition key value
            if_match_etag: Expected ETag for optimistic concurrency
            
        Returns:
            Patched document with updated system properties
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
            DocumentNotFoundError: If document not found
            PreconditionFailedError: If ETag doesn't match
        """
        async with self._lock:
            # Verify container exists
            await self._get_container_unlocked(database_id, container_id)
            
            # Get existing document
            existing_doc = await self._get_document_unlocked(
                database_id, container_id, document_id, partition_key_value
            )
            
            # Check ETag if provided
            if if_match_etag and existing_doc["_etag"] != if_match_etag:
                raise PreconditionFailedError(
                    f"ETag mismatch. Expected '{if_match_etag}', got '{existing_doc['_etag']}'",
                    etag=if_match_etag
                )
            
            # Apply patch operations
            patched_doc = self._apply_patch_operations(existing_doc, operations)
            
            # Update system properties
            ts = self._generate_timestamp()
            etag = self._generate_etag()
            patched_doc["_ts"] = ts
            patched_doc["_etag"] = etag
            
            # Store patched document
            self._documents[database_id][container_id][partition_key_value][document_id] = patched_doc
            
            return patched_doc
    
    async def delete_document(
        self,
        database_id: str,
        container_id: str,
        document_id: str,
        partition_key_value: str
    ) -> None:
        """Delete a document.
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            document_id: Document identifier
            partition_key_value: Partition key value
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
            DocumentNotFoundError: If document not found
        """
        async with self._lock:
            # Verify container exists
            await self._get_container_unlocked(database_id, container_id)
            
            # Check document exists
            if (database_id not in self._documents or
                container_id not in self._documents[database_id] or
                partition_key_value not in self._documents[database_id][container_id] or
                document_id not in self._documents[database_id][container_id][partition_key_value]):
                raise DocumentNotFoundError(
                    f"Document with id '{document_id}' and partition key '{partition_key_value}' not found",
                    document_id=document_id,
                    partition_key=partition_key_value
                )
            
            # Delete document
            del self._documents[database_id][container_id][partition_key_value][document_id]
    
    async def list_documents(
        self,
        database_id: str,
        container_id: str
    ) -> DocumentListResult:
        """List all documents in a container.
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            
        Returns:
            List of documents
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
        """
        async with self._lock:
            # Verify container exists
            container = await self._get_container_unlocked(database_id, container_id)
            
            documents = []
            if database_id in self._documents and container_id in self._documents[database_id]:
                for partition_docs in self._documents[database_id][container_id].values():
                    documents.extend(partition_docs.values())
            
            return DocumentListResult(
                _rid=container.rid,
                Documents=[copy.deepcopy(doc) for doc in documents],
                _count=len(documents)
            )
    
    async def _get_container_unlocked(self, database_id: str, container_id: str) -> Container:
        """Get container without acquiring lock (internal use).
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            
        Returns:
            Container
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
        """
        if database_id not in self._databases:
            raise DatabaseNotFoundError(
                f"Database with id '{database_id}' not found",
                database_id=database_id
            )
        
        if container_id not in self._containers[database_id]:
            raise ContainerNotFoundError(
                f"Container with id '{container_id}' not found in database '{database_id}'",
                container_id=container_id,
                database_id=database_id
            )
        
        return self._containers[database_id][container_id]
    
    async def _get_document_unlocked(
        self,
        database_id: str,
        container_id: str,
        document_id: str,
        partition_key_value: str
    ) -> Dict[str, Any]:
        """Get document without acquiring lock (internal use).
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            document_id: Document identifier
            partition_key_value: Partition key value
            
        Returns:
            Document
            
        Raises:
            DocumentNotFoundError: If document not found
        """
        if (database_id not in self._documents or
            container_id not in self._documents[database_id] or
            partition_key_value not in self._documents[database_id][container_id] or
            document_id not in self._documents[database_id][container_id][partition_key_value]):
            raise DocumentNotFoundError(
                f"Document with id '{document_id}' and partition key '{partition_key_value}' not found",
                document_id=document_id,
                partition_key=partition_key_value
            )
        
        return self._documents[database_id][container_id][partition_key_value][document_id]
    
    async def query_documents(
        self,
        database_id: str,
        container_id: str,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
        partition_key_value: Optional[str] = None,
        max_item_count: Optional[int] = None,
        continuation_token: Optional[str] = None,
        enable_cross_partition: bool = False
    ) -> QueryResult:
        """Execute SQL query on documents.
        
        Args:
            database_id: Database identifier
            container_id: Container identifier
            query: SQL query string
            parameters: Query parameters (not implemented yet)
            partition_key_value: Specific partition key (None for cross-partition)
            max_item_count: Maximum items per page
            continuation_token: Continuation token for pagination
            enable_cross_partition: Enable cross-partition queries
            
        Returns:
            Query result with documents and continuation token
            
        Raises:
            DatabaseNotFoundError: If database not found
            ContainerNotFoundError: If container not found
            ValueError: If query is invalid or cross-partition not enabled
        """
        async with self._lock:
            # Verify container exists
            container = await self._get_container_unlocked(database_id, container_id)
            
            # Get all documents from specified partition(s)
            documents = []
            if partition_key_value is not None:
                # Single partition query
                if (database_id in self._documents and
                    container_id in self._documents[database_id] and
                    partition_key_value in self._documents[database_id][container_id]):
                    documents = list(self._documents[database_id][container_id][partition_key_value].values())
            else:
                # Cross-partition query
                if not enable_cross_partition:
                    raise ValueError("Cross-partition queries require x-ms-documentdb-query-enablecrosspartition header")
                
                if database_id in self._documents and container_id in self._documents[database_id]:
                    for partition_docs in self._documents[database_id][container_id].values():
                        documents.extend(partition_docs.values())
            
            # Parse and execute query
            parsed_query = self._parse_sql_query(query)
            filtered_docs = self._execute_query(documents, parsed_query)
            
            # Handle pagination
            start_index = 0
            if continuation_token:
                try:
                    start_index = int(continuation_token)
                except ValueError:
                    start_index = 0
            
            # Apply max item count
            if max_item_count is None:
                max_item_count = 100  # Default page size
            
            end_index = start_index + max_item_count
            page_docs = filtered_docs[start_index:end_index]
            
            # Generate continuation token if more results exist
            next_token = None
            if end_index < len(filtered_docs):
                next_token = str(end_index)
            
            return QueryResult(
                _rid=container.rid,
                Documents=[copy.deepcopy(doc) for doc in page_docs],
                _count=len(page_docs),
                _continuation=next_token
            )
    
    def _parse_sql_query(self, query: str) -> Dict[str, Any]:
        """Parse SQL query into structured format.
        
        Args:
            query: SQL query string
            
        Returns:
            Parsed query structure
        """
        query = query.strip()
        query_upper = query.upper()
        
        parsed = {
            "select": [],
            "where": None,
            "order_by": [],
            "top": None,
        }
        
        # Extract TOP clause
        if "TOP" in query_upper:
            top_start = query_upper.find("TOP")
            select_start = query_upper.find("SELECT")
            if top_start > select_start:
                # TOP after SELECT (e.g., "SELECT TOP 5 * FROM c")
                from_start_temp = query_upper.find("FROM", top_start)
                if from_start_temp == -1:
                    from_start_temp = len(query)
                    
                # Extract just the TOP number part
                top_section = query[top_start + 3:from_start_temp].strip()
                # Find where the field list starts (after the number)
                parts = top_section.split(None, 1)  # Split on first whitespace
                if parts:
                    try:
                        parsed["top"] = int(parts[0])
                    except (ValueError, IndexError):
                        pass
        
        # Extract SELECT clause
        select_start = query_upper.find("SELECT")
        from_start = query_upper.find("FROM")
        
        if select_start != -1 and from_start != -1:
            select_clause = query[select_start + 6:from_start].strip()
            
            # Remove TOP N if present in select clause
            if select_clause.upper().startswith("TOP "):
                # Find where the field list actually starts
                parts = select_clause.split(None, 2)  # Split: ['TOP', 'N', 'field list']
                if len(parts) >= 3:
                    select_clause = parts[2]
                elif len(parts) == 2:
                    # Just "SELECT TOP N" with no fields - treat as SELECT *
                    select_clause = "*"
            
            if select_clause.strip() == "*":
                parsed["select"] = ["*"]
            else:
                # Parse selected fields (e.g., "c.id, c.name" or "c.id as userId")
                fields = [f.strip() for f in select_clause.split(",")]
                parsed["select"] = fields
        
        # Extract WHERE clause
        where_start = query_upper.find("WHERE")
        if where_start != -1:
            order_by_start = query_upper.find("ORDER BY", where_start)
            where_end = order_by_start if order_by_start != -1 else len(query)
            where_clause = query[where_start + 5:where_end].strip()
            parsed["where"] = where_clause
        
        # Extract ORDER BY clause
        order_by_start = query_upper.find("ORDER BY")
        if order_by_start != -1:
            order_by_clause = query[order_by_start + 8:].strip()
            # Parse field and direction (e.g., "c.name DESC")
            order_parts = order_by_clause.split()
            if order_parts:
                field = order_parts[0].strip()
                direction = "ASC"
                if len(order_parts) > 1 and order_parts[1].upper() in ["ASC", "DESC"]:
                    direction = order_parts[1].upper()
                parsed["order_by"] = [(field, direction)]
        
        return parsed
    
    def _execute_query(self, documents: List[Dict[str, Any]], parsed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute parsed query on documents.
        
        Args:
            documents: List of documents to query
            parsed_query: Parsed query structure
            
        Returns:
            Filtered and sorted documents
        """
        results = documents[:]
        
        # Apply WHERE filter
        if parsed_query["where"]:
            results = [doc for doc in results if self._evaluate_where_clause(doc, parsed_query["where"])]
        
        # Apply ORDER BY
        if parsed_query["order_by"]:
            for field, direction in reversed(parsed_query["order_by"]):
                field_name = field.replace("c.", "")
                results.sort(
                    key=lambda doc: self._get_nested_value(doc, field_name),
                    reverse=(direction == "DESC")
                )
        
        # Apply TOP limit
        if parsed_query["top"]:
            results = results[:parsed_query["top"]]
        
        # Apply SELECT projection (case-preserving for aliases)
        if parsed_query["select"] and parsed_query["select"] != ["*"]:
            projected_results = []
            for doc in results:
                projected_doc = {}
                for field in parsed_query["select"]:
                    # Handle "c.field as alias" (case-insensitive "as", but preserve alias case)
                    lower_field = field.lower()
                    if " as " in lower_field:
                        as_pos = lower_field.find(" as ")
                        source_part = field[:as_pos].strip()
                        alias_part = field[as_pos + 4:].strip()
                        
                        source_field = source_part.replace("c.", "").replace("C.", "")
                        alias = alias_part
                        if source_field in doc:
                            projected_doc[alias] = doc[source_field]
                    else:
                        field_name = field.replace("c.", "").replace("C.", "").strip()
                        if field_name in doc:
                            projected_doc[field_name] = doc[field_name]
                
                projected_results.append(projected_doc)
            results = projected_results
        
        return results
    
    def _evaluate_where_clause(self, document: Dict[str, Any], where_clause: str) -> bool:
        """Evaluate WHERE clause for a document.
        
        Args:
            document: Document to evaluate
            where_clause: WHERE clause string
            
        Returns:
            True if document matches the WHERE clause
        """
        # Simple evaluation - handle basic operators
        where_clause = where_clause.strip()
        
        # Handle BETWEEN operator FIRST (before AND/OR) to avoid conflicts
        if " BETWEEN " in where_clause.upper():
            upper_clause = where_clause.upper()
            between_pos = upper_clause.find(" BETWEEN ")
            and_pos = upper_clause.find(" AND ", between_pos + 10)
            
            if and_pos != -1:
                field = where_clause[:between_pos].strip().replace("c.", "").replace("C.", "")
                lower_str = where_clause[between_pos + 10:and_pos].strip()
                upper_str = where_clause[and_pos + 5:].strip()
                
                try:
                    lower = float(lower_str)
                    upper = float(upper_str)
                    doc_value = float(self._get_nested_value(document, field))
                    return lower <= doc_value <= upper
                except (ValueError, TypeError):
                    return False
        
        # Handle IN operator
        if " IN " in where_clause.upper():
            parts = where_clause.split(" IN ")
            if len(parts) == 2:
                field = parts[0].strip().replace("c.", "")
                values_str = parts[1].strip().strip("()")
                values = [v.strip().strip("\"'") for v in values_str.split(",")]
                doc_value = str(self._get_nested_value(document, field))
                return doc_value in values
        
        # Handle AND operator
        if " AND " in where_clause.upper():
            clauses = where_clause.split(" AND ")
            return all(self._evaluate_where_clause(document, clause.strip()) for clause in clauses)
        
        # Handle OR operator
        if " OR " in where_clause.upper():
            clauses = where_clause.split(" OR ")
            return any(self._evaluate_where_clause(document, clause.strip()) for clause in clauses)
        
        # Handle NOT operator
        if where_clause.upper().startswith("NOT "):
            return not self._evaluate_where_clause(document, where_clause[4:].strip())
        
        # Handle comparison operators
        for op in ["!=", ">=", "<=", "=", ">", "<"]:
            if f" {op} " in where_clause:
                parts = where_clause.split(f" {op} ")
                if len(parts) == 2:
                    field = parts[0].strip().replace("c.", "")
                    value_str = parts[1].strip().strip("\"'")
                    
                    doc_value = self._get_nested_value(document, field)
                    
                    # Handle boolean values
                    if value_str.lower() in ["true", "false"]:
                        compare_bool = value_str.lower() == "true"
                        doc_bool = doc_value if isinstance(doc_value, bool) else str(doc_value).lower() == "true"
                        
                        if op == "=":
                            return doc_bool == compare_bool
                        elif op == "!=":
                            return doc_bool != compare_bool
                        else:
                            return False  # Boolean can only use = or !=
                    
                    # Try to parse as number
                    try:
                        compare_value = float(value_str)
                        doc_value_num = float(doc_value)
                        
                        if op == "=":
                            return doc_value_num == compare_value
                        elif op == "!=":
                            return doc_value_num != compare_value
                        elif op == ">":
                            return doc_value_num > compare_value
                        elif op == "<":
                            return doc_value_num < compare_value
                        elif op == ">=":
                            return doc_value_num >= compare_value
                        elif op == "<=":
                            return doc_value_num <= compare_value
                    except (ValueError, TypeError):
                        # String comparison
                        doc_value_str = str(doc_value)
                        
                        if op == "=":
                            return doc_value_str == value_str
                        elif op == "!=":
                            return doc_value_str != value_str
                        elif op == ">":
                            return doc_value_str > value_str
                        elif op == "<":
                            return doc_value_str < value_str
                        elif op == ">=":
                            return doc_value_str >= value_str
                        elif op == "<=":
                            return doc_value_str <= value_str
                
                break
        
        return True
    
    def _get_nested_value(self, document: Dict[str, Any], field_path: str) -> Any:
        """Get nested value from document.
        
        Args:
            document: Document
            field_path: Field path (supports dot notation)
            
        Returns:
            Field value or None if not found
        """
        if "." in field_path:
            parts = field_path.split(".")
            value = document
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return None
            return value
        else:
            return document.get(field_path)
    
    async def clear(self) -> None:
        """Clear all databases, containers, and documents.
        
        Used for testing purposes.
        """
        async with self._lock:
            self._databases.clear()
            self._containers.clear()
            self._documents.clear()
