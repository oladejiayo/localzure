"""
Blob Storage API Endpoints

FastAPI endpoints for Azure Blob Storage container operations.

Author: Ayodele Oladeji
Date: 2025
"""

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from typing import Dict, Optional

from .backend import (
    ContainerAlreadyExistsError,
    ContainerBackend,
    ContainerNotFoundError,
    InvalidContainerNameError,
)
from .models import (
    CreateContainerRequest,
    PublicAccessLevel,
    SetContainerMetadataRequest,
)


# Initialize backend
backend = ContainerBackend()

# Create router
router = APIRouter(prefix="/blob", tags=["blob-storage"])


def _format_error_response(code: str, message: str) -> Dict:
    """
    Format Azure-style error response.
    
    Args:
        code: Error code
        message: Error message
        
    Returns:
        Error response dictionary
    """
    return {
        "error": {
            "code": code,
            "message": message,
        }
    }


@router.put(
    "/{account_name}/{container_name}",
    status_code=status.HTTP_201_CREATED,
    summary="Create Container",
)
async def create_container(
    account_name: str,
    container_name: str,
    request: Request,
    x_ms_blob_public_access: Optional[str] = Header(None),
    x_ms_meta_prefix: Optional[str] = Header(None, alias="x-ms-meta-*"),
) -> Response:
    """
    Create a new container.
    
    Azure REST API: PUT https://{account}.blob.core.windows.net/{container}?restype=container
    
    Args:
        account_name: Storage account name
        container_name: Container name
        request: FastAPI request
        x_ms_blob_public_access: Public access level
        x_ms_meta_prefix: Metadata headers (x-ms-meta-*)
        
    Returns:
        201 Created with headers
        
    Raises:
        400 Bad Request: Invalid container name
        409 Conflict: Container already exists
    """
    try:
        # Extract metadata from headers
        metadata = {}
        for key, value in request.headers.items():
            if key.lower().startswith('x-ms-meta-'):
                meta_key = key[10:]  # Remove 'x-ms-meta-' prefix
                metadata[meta_key] = value
        
        # Determine public access level
        public_access = PublicAccessLevel.PRIVATE
        if x_ms_blob_public_access:
            try:
                public_access = PublicAccessLevel(x_ms_blob_public_access.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_format_error_response(
                        "InvalidHeaderValue",
                        f"Invalid public access level: {x_ms_blob_public_access}"
                    ),
                )
        
        # Create container
        container = await backend.create_container(
            name=container_name,
            metadata=metadata,
            public_access=public_access,
        )
        
        # Build response headers
        response_headers = container.properties.to_headers()
        response_headers['x-ms-request-id'] = 'localzure-request-id'
        response_headers['x-ms-version'] = '2021-08-06'
        
        return Response(
            status_code=status.HTTP_201_CREATED,
            headers=response_headers,
        )
        
    except InvalidContainerNameError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_format_error_response("InvalidContainerName", str(e)),
        )
    except ContainerAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_format_error_response(
                "ContainerAlreadyExists",
                f"The specified container already exists."
            ),
        )


@router.get(
    "/{account_name}",
    status_code=status.HTTP_200_OK,
    summary="List Containers",
)
async def list_containers(
    account_name: str,
    prefix: Optional[str] = Query(None),
    maxresults: Optional[int] = Query(None, alias="maxresults"),
) -> Dict:
    """
    List containers in the storage account.
    
    Azure REST API: GET https://{account}.blob.core.windows.net/?comp=list
    
    Args:
        account_name: Storage account name
        prefix: Filter by prefix
        maxresults: Maximum number of results
        
    Returns:
        List of containers with metadata
    """
    containers = await backend.list_containers(prefix=prefix, max_results=maxresults)
    
    return {
        "Containers": [c.to_dict() for c in containers],
        "ServiceEndpoint": f"https://{account_name}.blob.core.windows.net/",
        "Prefix": prefix or "",
        "MaxResults": maxresults,
    }


@router.get(
    "/{account_name}/{container_name}",
    status_code=status.HTTP_200_OK,
    summary="Get Container Properties",
)
async def get_container_properties(
    account_name: str,
    container_name: str,
) -> Response:
    """
    Get container properties and metadata.
    
    Azure REST API: GET https://{account}.blob.core.windows.net/{container}?restype=container
    
    Args:
        account_name: Storage account name
        container_name: Container name
        
    Returns:
        200 OK with container properties in headers
        
    Raises:
        404 Not Found: Container not found
    """
    try:
        container = await backend.get_container(container_name)
        
        # Build response headers
        response_headers = container.properties.to_headers()
        response_headers.update(container.metadata.to_headers())
        response_headers['x-ms-request-id'] = 'localzure-request-id'
        response_headers['x-ms-version'] = '2021-08-06'
        
        return Response(
            status_code=status.HTTP_200_OK,
            headers=response_headers,
        )
        
    except ContainerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response(
                "ContainerNotFound",
                f"The specified container does not exist."
            ),
        )


@router.put(
    "/{account_name}/{container_name}/metadata",
    status_code=status.HTTP_200_OK,
    summary="Set Container Metadata",
)
async def set_container_metadata(
    account_name: str,
    container_name: str,
    request: Request,
) -> Response:
    """
    Set container metadata.
    
    Azure REST API: PUT https://{account}.blob.core.windows.net/{container}?restype=container&comp=metadata
    
    Args:
        account_name: Storage account name
        container_name: Container name
        request: FastAPI request with metadata headers
        
    Returns:
        200 OK with updated properties
        
    Raises:
        404 Not Found: Container not found
    """
    try:
        # Extract metadata from headers
        metadata = {}
        for key, value in request.headers.items():
            if key.lower().startswith('x-ms-meta-'):
                meta_key = key[10:]  # Remove 'x-ms-meta-' prefix
                metadata[meta_key] = value
        
        # Update metadata
        container = await backend.set_container_metadata(container_name, metadata)
        
        # Build response headers
        response_headers = container.properties.to_headers()
        response_headers['x-ms-request-id'] = 'localzure-request-id'
        response_headers['x-ms-version'] = '2021-08-06'
        
        return Response(
            status_code=status.HTTP_200_OK,
            headers=response_headers,
        )
        
    except ContainerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response(
                "ContainerNotFound",
                f"The specified container does not exist."
            ),
        )


@router.delete(
    "/{account_name}/{container_name}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete Container",
)
async def delete_container(
    account_name: str,
    container_name: str,
) -> Response:
    """
    Delete a container.
    
    Azure REST API: DELETE https://{account}.blob.core.windows.net/{container}?restype=container
    
    Args:
        account_name: Storage account name
        container_name: Container name
        
    Returns:
        202 Accepted
        
    Raises:
        404 Not Found: Container not found
    """
    try:
        await backend.delete_container(container_name)
        
        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            headers={
                'x-ms-request-id': 'localzure-request-id',
                'x-ms-version': '2021-08-06',
            },
        )
        
    except ContainerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response(
                "ContainerNotFound",
                f"The specified container does not exist."
            ),
        )


@router.post("/reset", status_code=status.HTTP_200_OK, summary="Reset Backend")
async def reset_backend() -> Dict:
    """
    Reset the backend, removing all containers.
    
    This is a testing endpoint not present in Azure.
    """
    await backend.reset()
    return {"message": "Backend reset successfully"}
