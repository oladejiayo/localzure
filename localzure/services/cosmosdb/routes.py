"""
Cosmos DB Routes.

FastAPI routes for Azure Cosmos DB REST API endpoints.

Author: LocalZure Team
Date: 2025-12-11
"""

from fastapi import APIRouter, HTTPException, status, Header, Body
from typing import Optional, Dict, Any

from .backend import CosmosDBBackend
from .models import (
    Database,
    Container,
    CreateDatabaseRequest,
    CreateContainerRequest,
    DatabaseListResult,
    ContainerListResult,
    CreateDocumentRequest,
    ReplaceDocumentRequest,
    PatchDocumentRequest,
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


# Initialize backend
backend = CosmosDBBackend()

# Create router
router = APIRouter(prefix="/cosmosdb", tags=["cosmosdb"])


@router.post("/dbs", status_code=status.HTTP_201_CREATED, response_model=Database)
async def create_database(request: CreateDatabaseRequest) -> Database:
    """Create a new database.
    
    Args:
        request: Database creation request
        
    Returns:
        Created database
        
    Raises:
        HTTPException: If database creation fails
    """
    try:
        return await backend.create_database(request)
    except DatabaseAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/dbs", response_model=DatabaseListResult)
async def list_databases() -> DatabaseListResult:
    """List all databases.
    
    Returns:
        List of databases
    """
    return await backend.list_databases()


@router.get("/dbs/{database_id}", response_model=Database)
async def get_database(database_id: str) -> Database:
    """Get a database by ID.
    
    Args:
        database_id: Database identifier
        
    Returns:
        Database
        
    Raises:
        HTTPException: If database not found
    """
    try:
        return await backend.get_database(database_id)
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/dbs/{database_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_database(database_id: str) -> None:
    """Delete a database and all its containers.
    
    Args:
        database_id: Database identifier
        
    Raises:
        HTTPException: If database not found
    """
    try:
        await backend.delete_database(database_id)
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/dbs/{database_id}/colls",
    status_code=status.HTTP_201_CREATED,
    response_model=Container
)
async def create_container(
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
        HTTPException: If container creation fails
    """
    try:
        return await backend.create_container(database_id, request)
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except InvalidPartitionKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/dbs/{database_id}/colls", response_model=ContainerListResult)
async def list_containers(database_id: str) -> ContainerListResult:
    """List all containers in a database.
    
    Args:
        database_id: Database identifier
        
    Returns:
        List of containers
        
    Raises:
        HTTPException: If database not found
    """
    try:
        return await backend.list_containers(database_id)
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/dbs/{database_id}/colls/{container_id}", response_model=Container)
async def get_container(database_id: str, container_id: str) -> Container:
    """Get a container by ID.
    
    Args:
        database_id: Database identifier
        container_id: Container identifier
        
    Returns:
        Container
        
    Raises:
        HTTPException: If database or container not found
    """
    try:
        return await backend.get_container(database_id, container_id)
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete(
    "/dbs/{database_id}/colls/{container_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_container(database_id: str, container_id: str) -> None:
    """Delete a container from a database.
    
    Args:
        database_id: Database identifier
        container_id: Container identifier
        
    Raises:
        HTTPException: If database or container not found
    """
    try:
        await backend.delete_container(database_id, container_id)
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# Document operations

@router.post(
    "/dbs/{database_id}/colls/{container_id}/docs",
    status_code=status.HTTP_201_CREATED,
    response_model=Dict[str, Any]
)
async def create_document(
    database_id: str,
    container_id: str,
    document: Dict[str, Any] = Body(...),
    x_ms_documentdb_partitionkey: Optional[str] = Header(None, alias="x-ms-documentdb-partitionkey")
) -> Dict[str, Any]:
    """Create a new document in a container.
    
    Args:
        database_id: Database identifier
        container_id: Container identifier
        document: Document data
        x_ms_documentdb_partitionkey: Partition key value (header)
        
    Returns:
        Created document with system properties
        
    Raises:
        HTTPException: If document creation fails
    """
    try:
        # Parse partition key from header if provided (it comes as JSON array)
        partition_key_value = None
        if x_ms_documentdb_partitionkey:
            import json
            pk_array = json.loads(x_ms_documentdb_partitionkey)
            if pk_array:
                partition_key_value = str(pk_array[0])
        
        return await backend.create_document(
            database_id,
            container_id,
            document,
            partition_key_value
        )
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DocumentAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/dbs/{database_id}/colls/{container_id}/docs/{document_id}",
    response_model=Dict[str, Any]
)
async def get_document(
    database_id: str,
    container_id: str,
    document_id: str,
    x_ms_documentdb_partitionkey: str = Header(..., alias="x-ms-documentdb-partitionkey")
) -> Dict[str, Any]:
    """Get a document by ID and partition key.
    
    Args:
        database_id: Database identifier
        container_id: Container identifier
        document_id: Document identifier
        x_ms_documentdb_partitionkey: Partition key value (header)
        
    Returns:
        Document
        
    Raises:
        HTTPException: If document not found
    """
    try:
        # Parse partition key from header (it comes as JSON array)
        import json
        pk_array = json.loads(x_ms_documentdb_partitionkey)
        partition_key_value = str(pk_array[0]) if pk_array else ""
        
        return await backend.get_document(
            database_id,
            container_id,
            document_id,
            partition_key_value
        )
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put(
    "/dbs/{database_id}/colls/{container_id}/docs/{document_id}",
    response_model=Dict[str, Any]
)
async def replace_document(
    database_id: str,
    container_id: str,
    document_id: str,
    document: Dict[str, Any] = Body(...),
    x_ms_documentdb_partitionkey: str = Header(..., alias="x-ms-documentdb-partitionkey"),
    if_match: Optional[str] = Header(None, alias="If-Match")
) -> Dict[str, Any]:
    """Replace an entire document.
    
    Args:
        database_id: Database identifier
        container_id: Container identifier
        document_id: Document identifier
        document: New document data
        x_ms_documentdb_partitionkey: Partition key value (header)
        if_match: ETag for optimistic concurrency
        
    Returns:
        Replaced document
        
    Raises:
        HTTPException: If document replacement fails
    """
    try:
        # Parse partition key from header
        import json
        pk_array = json.loads(x_ms_documentdb_partitionkey)
        partition_key_value = str(pk_array[0]) if pk_array else ""
        
        return await backend.replace_document(
            database_id,
            container_id,
            document_id,
            document,
            partition_key_value,
            if_match
        )
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PreconditionFailedError as e:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(e)
        )


@router.patch(
    "/dbs/{database_id}/colls/{container_id}/docs/{document_id}",
    response_model=Dict[str, Any]
)
async def patch_document(
    database_id: str,
    container_id: str,
    document_id: str,
    patch_request: PatchDocumentRequest,
    x_ms_documentdb_partitionkey: str = Header(..., alias="x-ms-documentdb-partitionkey"),
    if_match: Optional[str] = Header(None, alias="If-Match")
) -> Dict[str, Any]:
    """Patch specific fields in a document.
    
    Args:
        database_id: Database identifier
        container_id: Container identifier
        document_id: Document identifier
        patch_request: Patch operations
        x_ms_documentdb_partitionkey: Partition key value (header)
        if_match: ETag for optimistic concurrency
        
    Returns:
        Patched document
        
    Raises:
        HTTPException: If document patching fails
    """
    try:
        # Parse partition key from header
        import json
        pk_array = json.loads(x_ms_documentdb_partitionkey)
        partition_key_value = str(pk_array[0]) if pk_array else ""
        
        return await backend.patch_document(
            database_id,
            container_id,
            document_id,
            patch_request.operations,
            partition_key_value,
            if_match
        )
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PreconditionFailedError as e:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/dbs/{database_id}/colls/{container_id}/docs/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_document(
    database_id: str,
    container_id: str,
    document_id: str,
    x_ms_documentdb_partitionkey: str = Header(..., alias="x-ms-documentdb-partitionkey")
) -> None:
    """Delete a document.
    
    Args:
        database_id: Database identifier
        container_id: Container identifier
        document_id: Document identifier
        x_ms_documentdb_partitionkey: Partition key value (header)
        
    Raises:
        HTTPException: If document deletion fails
    """
    try:
        # Parse partition key from header
        import json
        pk_array = json.loads(x_ms_documentdb_partitionkey)
        partition_key_value = str(pk_array[0]) if pk_array else ""
        
        await backend.delete_document(
            database_id,
            container_id,
            document_id,
            partition_key_value
        )
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/dbs/{database_id}/colls/{container_id}/docs",
    response_model=DocumentListResult
)
async def list_documents(
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
        HTTPException: If database or container not found
    """
    try:
        return await backend.list_documents(database_id, container_id)
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/dbs/{database_id}/colls/{container_id}/docs",
    response_model=QueryResult,
    summary="Query documents"
)
async def query_documents(
    database_id: str,
    container_id: str,
    query_request: QueryRequest = Body(...),
    x_ms_documentdb_partitionkey: Optional[str] = Header(None, alias="x-ms-documentdb-partitionkey"),
    x_ms_max_item_count: Optional[int] = Header(None, alias="x-ms-max-item-count"),
    x_ms_continuation: Optional[str] = Header(None, alias="x-ms-continuation"),
    x_ms_documentdb_query_enablecrosspartition: Optional[str] = Header(None, alias="x-ms-documentdb-query-enablecrosspartition"),
) -> QueryResult:
    """Query documents using SQL.
    
    Args:
        database_id: Database identifier
        container_id: Container identifier
        query_request: SQL query request with query string and parameters
        x_ms_documentdb_partitionkey: Partition key value (JSON array format)
        x_ms_max_item_count: Maximum items per page
        x_ms_continuation: Continuation token for pagination
        x_ms_documentdb_query_enablecrosspartition: Enable cross-partition query
        
    Returns:
        Query result with documents
        
    Raises:
        HTTPException: If database/container not found or query is invalid
    """
    # Parse partition key if provided
    partition_key_value = None
    if x_ms_documentdb_partitionkey:
        try:
            import json
            pk_array = json.loads(x_ms_documentdb_partitionkey)
            if pk_array and len(pk_array) > 0:
                partition_key_value = str(pk_array[0])
        except (json.JSONDecodeError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid partition key format"
            )
    
    # Parse cross-partition flag
    enable_cross_partition = False
    if x_ms_documentdb_query_enablecrosspartition:
        enable_cross_partition = x_ms_documentdb_query_enablecrosspartition.lower() == "true"
    
    try:
        return await backend.query_documents(
            database_id=database_id,
            container_id=container_id,
            query=query_request.query,
            parameters=query_request.parameters,
            partition_key_value=partition_key_value,
            max_item_count=x_ms_max_item_count,
            continuation_token=x_ms_continuation,
            enable_cross_partition=enable_cross_partition
        )
    except DatabaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ContainerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
