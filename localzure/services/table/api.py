"""
FastAPI endpoints for Azure Table Storage emulator.

Implements OData-style REST API for table and entity operations.
"""

import json
from typing import Optional
from fastapi import APIRouter, Response, Request, status, Header
from fastapi.responses import JSONResponse

from localzure.services.table.backend import (
    backend,
    TableAlreadyExistsError,
    TableNotFoundError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ETagMismatchError,
)
from localzure.services.table.models import (
    Table,
    Entity,
    InsertEntityRequest,
    UpdateEntityRequest,
    MergeEntityRequest,
)

router = APIRouter(prefix="/table", tags=["table-storage"])


def create_error_response(error_code: str, message: str, status_code: int) -> JSONResponse:
    """
    Create Azure-compatible error response.
    
    Args:
        error_code: Azure error code
        message: Error message
        status_code: HTTP status code
        
    Returns:
        JSON error response
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "odata.error": {
                "code": error_code,
                "message": {"lang": "en-US", "value": message}
            }
        }
    )


@router.post(
    "/{account_name}/Tables",
    status_code=status.HTTP_201_CREATED,
    summary="Create Table",
)
async def create_table(
    account_name: str,
    request: Request,
) -> JSONResponse:
    """
    Create a new table.
    
    Azure REST API: POST https://{account}.table.core.windows.net/Tables
    
    Args:
        account_name: Storage account name
        request: FastAPI request with JSON body containing TableName
        
    Returns:
        201 Created with table metadata
        
    Raises:
        400 Bad Request: Invalid table name
        409 Conflict: Table already exists
    """
    try:
        body = await request.json()
        table_name = body.get("TableName", "")
        
        if not table_name:
            return create_error_response(
                "InvalidInput",
                "TableName is required",
                status.HTTP_400_BAD_REQUEST
            )
        
        table = await backend.create_table(table_name)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "odata.metadata": f"https://{account_name}.table.core.windows.net/$metadata#Tables/@Element",
                "TableName": table.table_name
            },
            headers={
                "Content-Type": "application/json;odata=minimalmetadata",
                "Location": f"https://{account_name}.table.core.windows.net/Tables('{table.table_name}')",
                "x-ms-request-id": "localzure-request-id",
                "x-ms-version": "2021-08-06",
            }
        )
    
    except TableAlreadyExistsError as e:
        return create_error_response(
            "TableAlreadyExists",
            str(e),
            status.HTTP_409_CONFLICT
        )
    except ValueError as e:
        return create_error_response(
            "InvalidInput",
            str(e),
            status.HTTP_400_BAD_REQUEST
        )


@router.get(
    "/{account_name}/Tables",
    status_code=status.HTTP_200_OK,
    summary="List Tables",
)
async def list_tables(account_name: str) -> JSONResponse:
    """
    List all tables.
    
    Azure REST API: GET https://{account}.table.core.windows.net/Tables
    
    Args:
        account_name: Storage account name
        
    Returns:
        200 OK with list of tables
    """
    tables = await backend.list_tables()
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "odata.metadata": f"https://{account_name}.table.core.windows.net/$metadata#Tables",
            "value": [{"TableName": t.table_name} for t in tables]
        },
        headers={
            "Content-Type": "application/json;odata=minimalmetadata",
            "x-ms-request-id": "localzure-request-id",
            "x-ms-version": "2021-08-06",
        }
    )


@router.delete(
    "/{account_name}/Tables('{table_name}')",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Table",
)
async def delete_table(
    account_name: str,
    table_name: str,
) -> Response:
    """
    Delete a table.
    
    Azure REST API: DELETE https://{account}.table.core.windows.net/Tables('{table}')
    
    Args:
        account_name: Storage account name
        table_name: Table name
        
    Returns:
        204 No Content
        
    Raises:
        404 Not Found: Table not found
    """
    try:
        await backend.delete_table(table_name)
        
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={
                "x-ms-request-id": "localzure-request-id",
                "x-ms-version": "2021-08-06",
            }
        )
    
    except TableNotFoundError as e:
        return create_error_response(
            "TableNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )


@router.post(
    "/{account_name}/{table_name}",
    status_code=status.HTTP_201_CREATED,
    summary="Insert Entity",
)
async def insert_entity(
    account_name: str,
    table_name: str,
    request: Request,
) -> JSONResponse:
    """
    Insert a new entity into a table.
    
    Azure REST API: POST https://{account}.table.core.windows.net/{table}
    
    Args:
        account_name: Storage account name
        table_name: Table name
        request: FastAPI request with JSON body containing entity data
        
    Returns:
        201 Created with entity data
        
    Raises:
        404 Not Found: Table not found
        409 Conflict: Entity already exists
    """
    try:
        body = await request.json()
        
        # Create entity from request
        entity_req = InsertEntityRequest(**body)
        entity = entity_req.to_entity()
        
        # Insert entity
        inserted = await backend.insert_entity(table_name, entity)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "odata.metadata": f"https://{account_name}.table.core.windows.net/$metadata#{table_name}/@Element",
                **inserted.to_dict()
            },
            headers={
                "Content-Type": "application/json;odata=minimalmetadata",
                "Location": f"https://{account_name}.table.core.windows.net/{table_name}(PartitionKey='{inserted.PartitionKey}',RowKey='{inserted.RowKey}')",
                "ETag": inserted.etag,
                "x-ms-request-id": "localzure-request-id",
                "x-ms-version": "2021-08-06",
            }
        )
    
    except TableNotFoundError as e:
        return create_error_response(
            "TableNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )
    except EntityAlreadyExistsError as e:
        return create_error_response(
            "EntityAlreadyExists",
            str(e),
            status.HTTP_409_CONFLICT
        )
    except ValueError as e:
        return create_error_response(
            "InvalidInput",
            str(e),
            status.HTTP_400_BAD_REQUEST
        )


@router.get(
    "/{account_name}/{table_name}(PartitionKey='{partition_key}',RowKey='{row_key}')",
    status_code=status.HTTP_200_OK,
    summary="Get Entity",
)
async def get_entity(
    account_name: str,
    table_name: str,
    partition_key: str,
    row_key: str,
) -> JSONResponse:
    """
    Get an entity by partition and row keys.
    
    Azure REST API: GET https://{account}.table.core.windows.net/{table}(PartitionKey='{pk}',RowKey='{rk}')
    
    Args:
        account_name: Storage account name
        table_name: Table name
        partition_key: Partition key
        row_key: Row key
        
    Returns:
        200 OK with entity data
        
    Raises:
        404 Not Found: Table or entity not found
    """
    try:
        entity = await backend.get_entity(table_name, partition_key, row_key)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "odata.metadata": f"https://{account_name}.table.core.windows.net/$metadata#{table_name}/@Element",
                **entity.to_dict()
            },
            headers={
                "Content-Type": "application/json;odata=minimalmetadata",
                "ETag": entity.etag,
                "x-ms-request-id": "localzure-request-id",
                "x-ms-version": "2021-08-06",
            }
        )
    
    except TableNotFoundError as e:
        return create_error_response(
            "TableNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )
    except EntityNotFoundError as e:
        return create_error_response(
            "ResourceNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )


@router.put(
    "/{account_name}/{table_name}(PartitionKey='{partition_key}',RowKey='{row_key}')",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update Entity",
)
async def update_entity(
    account_name: str,
    table_name: str,
    partition_key: str,
    row_key: str,
    request: Request,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
) -> Response:
    """
    Update (replace) an entity.
    
    Azure REST API: PUT https://{account}.table.core.windows.net/{table}(PartitionKey='{pk}',RowKey='{rk}')
    
    Args:
        account_name: Storage account name
        table_name: Table name
        partition_key: Partition key
        row_key: Row key
        request: FastAPI request with JSON body containing new entity data
        if_match: Optional ETag for optimistic concurrency
        
    Returns:
        204 No Content with new ETag
        
    Raises:
        404 Not Found: Table or entity not found
        412 Precondition Failed: ETag mismatch
    """
    try:
        body = await request.json()
        
        # Create entity from request
        entity_req = UpdateEntityRequest(**body)
        entity = entity_req.to_entity()
        
        # Update entity
        updated = await backend.update_entity(
            table_name,
            partition_key,
            row_key,
            entity,
            if_match
        )
        
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={
                "ETag": updated.etag,
                "x-ms-request-id": "localzure-request-id",
                "x-ms-version": "2021-08-06",
            }
        )
    
    except TableNotFoundError as e:
        return create_error_response(
            "TableNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )
    except EntityNotFoundError as e:
        return create_error_response(
            "ResourceNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )
    except ETagMismatchError as e:
        return create_error_response(
            "UpdateConditionNotSatisfied",
            str(e),
            status.HTTP_412_PRECONDITION_FAILED
        )
    except ValueError as e:
        return create_error_response(
            "InvalidInput",
            str(e),
            status.HTTP_400_BAD_REQUEST
        )


@router.patch(
    "/{account_name}/{table_name}(PartitionKey='{partition_key}',RowKey='{row_key}')",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Merge Entity",
)
@router.api_route(
    "/{account_name}/{table_name}(PartitionKey='{partition_key}',RowKey='{row_key}')",
    methods=["MERGE"],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def merge_entity(
    account_name: str,
    table_name: str,
    partition_key: str,
    row_key: str,
    request: Request,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
) -> Response:
    """
    Merge (update) an entity with specified properties.
    
    Azure REST API: MERGE/PATCH https://{account}.table.core.windows.net/{table}(PartitionKey='{pk}',RowKey='{rk}')
    
    Args:
        account_name: Storage account name
        table_name: Table name
        partition_key: Partition key
        row_key: Row key
        request: FastAPI request with JSON body containing properties to merge
        if_match: Optional ETag for optimistic concurrency
        
    Returns:
        204 No Content with new ETag
        
    Raises:
        404 Not Found: Table or entity not found
        412 Precondition Failed: ETag mismatch
    """
    try:
        body = await request.json()
        
        # Get properties to merge
        merge_req = MergeEntityRequest(**body)
        properties = merge_req.get_properties_to_merge()
        
        # Merge entity
        merged = await backend.merge_entity(
            table_name,
            partition_key,
            row_key,
            properties,
            if_match
        )
        
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={
                "ETag": merged.etag,
                "x-ms-request-id": "localzure-request-id",
                "x-ms-version": "2021-08-06",
            }
        )
    
    except TableNotFoundError as e:
        return create_error_response(
            "TableNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )
    except EntityNotFoundError as e:
        return create_error_response(
            "ResourceNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )
    except ETagMismatchError as e:
        return create_error_response(
            "UpdateConditionNotSatisfied",
            str(e),
            status.HTTP_412_PRECONDITION_FAILED
        )
    except ValueError as e:
        return create_error_response(
            "InvalidInput",
            str(e),
            status.HTTP_400_BAD_REQUEST
        )


@router.delete(
    "/{account_name}/{table_name}(PartitionKey='{partition_key}',RowKey='{row_key}')",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Entity",
)
async def delete_entity(
    account_name: str,
    table_name: str,
    partition_key: str,
    row_key: str,
    if_match: Optional[str] = Header(default="*", alias="If-Match"),
) -> Response:
    """
    Delete an entity.
    
    Azure REST API: DELETE https://{account}.table.core.windows.net/{table}(PartitionKey='{pk}',RowKey='{rk}')
    
    Args:
        account_name: Storage account name
        table_name: Table name
        partition_key: Partition key
        row_key: Row key
        if_match: ETag for optimistic concurrency (default: "*" = skip check)
        
    Returns:
        204 No Content
        
    Raises:
        404 Not Found: Table or entity not found
        412 Precondition Failed: ETag mismatch
    """
    try:
        await backend.delete_entity(
            table_name,
            partition_key,
            row_key,
            if_match
        )
        
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={
                "x-ms-request-id": "localzure-request-id",
                "x-ms-version": "2021-08-06",
            }
        )
    
    except TableNotFoundError as e:
        return create_error_response(
            "TableNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )
    except EntityNotFoundError as e:
        return create_error_response(
            "ResourceNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )
    except ETagMismatchError as e:
        return create_error_response(
            "UpdateConditionNotSatisfied",
            str(e),
            status.HTTP_412_PRECONDITION_FAILED
        )


@router.get(
    "/{account_name}/{table_name}()",
    status_code=status.HTTP_200_OK,
    summary="Query Entities",
)
async def query_entities(
    account_name: str,
    table_name: str,
    filter: Optional[str] = None,
    select: Optional[str] = None,
    top: Optional[int] = None,
    NextPartitionKey: Optional[str] = None,
    NextRowKey: Optional[str] = None,
) -> JSONResponse:
    """
    Query entities with OData parameters.
    
    Azure REST API: GET https://{account}.table.core.windows.net/{table}()?$filter=...&$select=...&$top=...
    
    Args:
        account_name: Storage account name
        table_name: Table name
        filter: $filter OData expression
        select: $select comma-separated properties
        top: $top result limit
        NextPartitionKey: Continuation token partition key
        NextRowKey: Continuation token row key
        
    Returns:
        200 OK with entity list and optional continuation token
        
    Raises:
        404 Not Found: Table not found
    """
    try:
        # Query entities
        entities, continuation_token = await backend.query_entities(
            table_name=table_name,
            filter_expr=filter,
            select=select,
            top=top,
            next_partition_key=NextPartitionKey,
            next_row_key=NextRowKey,
        )
        
        # Build response
        response_data = {
            "odata.metadata": f"https://{account_name}.table.core.windows.net/$metadata#{table_name}",
            "value": [entity.to_dict() for entity in entities]
        }
        
        # Add headers
        response_headers = {
            "Content-Type": "application/json;odata=minimalmetadata",
            "x-ms-request-id": "localzure-request-id",
            "x-ms-version": "2021-08-06",
        }
        
        # Add continuation token if present
        if continuation_token:
            response_headers["x-ms-continuation-NextPartitionKey"] = continuation_token
            response_headers["x-ms-continuation-NextRowKey"] = continuation_token
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_data,
            headers=response_headers
        )
    
    except TableNotFoundError as e:
        return create_error_response(
            "TableNotFound",
            str(e),
            status.HTTP_404_NOT_FOUND
        )

