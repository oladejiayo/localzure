"""
Blob Storage API Endpoints

FastAPI endpoints for Azure Blob Storage container and blob operations.

Author: Ayodele Oladeji
Date: 2025
"""

from fastapi import APIRouter, Body, Header, HTTPException, Query, Request, Response, status
from typing import Dict, List, Optional
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from .backend import (
    BlobAlreadyExistsError,
    BlobNotFoundError,
    ContainerAlreadyExistsError,
    ContainerBackend,
    ContainerNotFoundError,
    InvalidBlockIdError,
    InvalidContainerNameError,
    LeaseAlreadyPresentError,
    LeaseIdMismatchError,
    LeaseIdMissingError,
    LeaseNotFoundError,
    SnapshotNotFoundError,
)
from .models import (
    BlockListType,
    BlockReference,
    ConditionalHeaders,
    CreateContainerRequest,
    Lease,
    LeaseAction,
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
    summary="Create Container or Container Operations",
)
async def create_container_or_ops(
    account_name: str,
    container_name: str,
    request: Request,
    x_ms_blob_public_access: Optional[str] = Header(None),
    x_ms_meta_prefix: Optional[str] = Header(None, alias="x-ms-meta-*"),
    comp: Optional[str] = Query(None),
    restype: Optional[str] = Query(None),
    x_ms_lease_action: Optional[str] = Header(None, alias="x-ms-lease-action"),
    x_ms_lease_duration: Optional[int] = Header(None, alias="x-ms-lease-duration"),
    x_ms_lease_id: Optional[str] = Header(None, alias="x-ms-lease-id"),
    x_ms_proposed_lease_id: Optional[str] = Header(None, alias="x-ms-proposed-lease-id"),
    x_ms_lease_break_period: Optional[int] = Header(None, alias="x-ms-lease-break-period"),
) -> Response:
    """
    Create a container or perform container operations (lease).
    
    Azure REST API: 
    - PUT https://{account}.blob.core.windows.net/{container}?restype=container (create)
    - PUT https://{account}.blob.core.windows.net/{container}?comp=lease (lease operations)
    
    Args:
        account_name: Storage account name
        container_name: Container name
        request: FastAPI request
        x_ms_blob_public_access: Public access level (for create)
        x_ms_meta_prefix: Metadata headers (x-ms-meta-*) (for create)
        comp: Component parameter (lease)
        restype: Resource type parameter (container)
        x_ms_lease_action: Lease action (acquire, renew, release, break, change)
        x_ms_lease_duration: Lease duration in seconds
        x_ms_lease_id: Lease ID
        x_ms_proposed_lease_id: Proposed lease ID
        x_ms_lease_break_period: Break period in seconds
        
    Returns:
        201 Created with headers (create)
        201 Created with lease ID (acquire)
        200 OK (renew, release)
        202 Accepted (break)
        
    Raises:
        400 Bad Request: Invalid container name or parameters
        409 Conflict: Container already exists
    """
    # Handle lease operations
    if comp == "lease":
        if not x_ms_lease_action:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-action is required for lease operations"),
            )
        
        action = x_ms_lease_action.lower()
        
        try:
            if action == "acquire":
                if x_ms_lease_duration is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-duration is required for acquire"),
                    )
                
                lease = await backend.acquire_container_lease(
                    container_name=container_name,
                    duration=x_ms_lease_duration,
                    proposed_lease_id=x_ms_proposed_lease_id,
                )
                
                response = Response(status_code=status.HTTP_201_CREATED)
                response.headers["x-ms-lease-id"] = lease.lease_id
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            elif action == "renew":
                if x_ms_lease_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-id is required for renew"),
                    )
                
                lease = await backend.renew_container_lease(
                    container_name=container_name,
                    lease_id=x_ms_lease_id,
                )
                
                response = Response(status_code=status.HTTP_200_OK)
                response.headers["x-ms-lease-id"] = lease.lease_id
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            elif action == "release":
                if x_ms_lease_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-id is required for release"),
                    )
                
                await backend.release_container_lease(
                    container_name=container_name,
                    lease_id=x_ms_lease_id,
                )
                
                response = Response(status_code=status.HTTP_200_OK)
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            elif action == "break":
                remaining_time = await backend.break_container_lease(
                    container_name=container_name,
                    break_period=x_ms_lease_break_period,
                )
                
                response = Response(status_code=status.HTTP_202_ACCEPTED)
                response.headers["x-ms-lease-time"] = str(remaining_time)
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            elif action == "change":
                if x_ms_lease_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-id is required for change"),
                    )
                if x_ms_proposed_lease_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-proposed-lease-id is required for change"),
                    )
                
                lease = await backend.change_container_lease(
                    container_name=container_name,
                    lease_id=x_ms_lease_id,
                    proposed_lease_id=x_ms_proposed_lease_id,
                )
                
                response = Response(status_code=status.HTTP_200_OK)
                response.headers["x-ms-lease-id"] = lease.lease_id
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_format_error_response("InvalidHeaderValue", f"Invalid lease action: {action}"),
                )
        
        except (LeaseNotFoundError, ContainerNotFoundError) as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response(type(e).__name__.replace("Error", ""), str(e)),
            )
        except LeaseAlreadyPresentError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_format_error_response("LeaseAlreadyPresent", str(e)),
            )
        except LeaseIdMismatchError as e:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=_format_error_response("LeaseIdMismatchConditionNotMet", str(e)),
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_format_error_response("InvalidHeaderValue", str(e)),
            )
    
    # Handle container creation (default behavior if no comp parameter)
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
    summary="Get Container Properties or List Blobs",
)
async def get_container_or_list_blobs(
    account_name: str,
    container_name: str,
    restype: Optional[str] = Query(None),
    comp: Optional[str] = Query(None),
    prefix: Optional[str] = Query(None),
    delimiter: Optional[str] = Query(None),
    maxresults: Optional[int] = Query(None),
    marker: Optional[str] = Query(None),
    include: Optional[str] = Query(None),
) -> Response:
    """
    Get container properties and metadata, or list blobs if restype=container&comp=list.
    
    Azure REST API: GET https://{account}.blob.core.windows.net/{container}?restype=container
    
    Args:
        account_name: Storage account name
        container_name: Container name
        restype: Resource type (container for list blobs)
        comp: Component (list for blobs)
        prefix: Blob name prefix filter
        delimiter: Delimiter for hierarchical listing
        maxresults: Maximum results
        marker: Continuation marker
        include: Include options (snapshots, metadata, etc.)
        
    Returns:
        200 OK with container properties in headers or blob list XML
        
    Raises:
        404 Not Found: Container not found
    """
    # Handle List Blobs operation
    if restype == "container" and comp == "list":
        try:
            # Parse include parameter
            include_snapshots = False
            if include and "snapshots" in include.lower():
                include_snapshots = True
            
            blobs, next_marker = await backend.list_blobs(
                container_name,
                prefix=prefix,
                delimiter=delimiter,
                max_results=maxresults,
                marker=marker,
                include_snapshots=include_snapshots,
            )
            
            # Build XML response
            root = ET.Element("EnumerationResults")
            root.set("ServiceEndpoint", f"https://{account_name}.blob.core.windows.net/")
            root.set("ContainerName", container_name)
            
            if prefix:
                ET.SubElement(root, "Prefix").text = prefix
            if delimiter:
                ET.SubElement(root, "Delimiter").text = delimiter
            if marker:
                ET.SubElement(root, "Marker").text = marker
            if maxresults:
                ET.SubElement(root, "MaxResults").text = str(maxresults)
            
            blobs_element = ET.SubElement(root, "Blobs")
            for blob in blobs:
                blob_element = ET.SubElement(blobs_element, "Blob")
                ET.SubElement(blob_element, "Name").text = blob.name
                
                # Add snapshot information if this is a snapshot
                if blob.snapshot_id:
                    ET.SubElement(blob_element, "Snapshot").text = blob.snapshot_id
                
                props = ET.SubElement(blob_element, "Properties")
                ET.SubElement(props, "Content-Length").text = str(blob.properties.content_length)
                ET.SubElement(props, "Content-Type").text = blob.properties.content_type
                ET.SubElement(props, "Etag").text = blob.properties.etag
                ET.SubElement(props, "Last-Modified").text = blob.properties.last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
                ET.SubElement(props, "BlobType").text = blob.properties.blob_type.value
                
                if blob.metadata.metadata:
                    metadata_element = ET.SubElement(blob_element, "Metadata")
                    for key, value in blob.metadata.metadata.items():
                        ET.SubElement(metadata_element, key).text = value
            
            if next_marker:
                ET.SubElement(root, "NextMarker").text = next_marker
            
            xml_response = ET.tostring(root, encoding='utf-8', xml_declaration=True)
            
            return Response(
                content=xml_response,
                media_type="application/xml",
                headers={
                    'x-ms-request-id': 'localzure-request-id',
                    'x-ms-version': '2021-08-06',
                },
            )
            
        except ContainerNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response("ContainerNotFound", "Container not found"),
            )
    
    # Handle Get Container Properties operation
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


# ============================================================================
# Blob Operations
# ============================================================================


@router.put(
    "/{account_name}/{container_name}/{blob_name:path}",
    status_code=status.HTTP_201_CREATED,
    summary="Put Blob",
)
async def put_blob(
    account_name: str,
    container_name: str,
    blob_name: str,
    request: Request,
    x_ms_blob_type: str = Header("BlockBlob"),
    content_type: Optional[str] = Header("application/octet-stream"),
    content_encoding: Optional[str] = Header(None),
    content_language: Optional[str] = Header(None),
    cache_control: Optional[str] = Header(None),
    content_disposition: Optional[str] = Header(None),
    if_match: Optional[str] = Header(None),
    if_none_match: Optional[str] = Header(None),
    x_ms_lease_id: Optional[str] = Header(None, alias="x-ms-lease-id"),
    x_ms_lease_action: Optional[str] = Header(None, alias="x-ms-lease-action"),
    x_ms_lease_duration: Optional[int] = Header(None, alias="x-ms-lease-duration"),
    x_ms_proposed_lease_id: Optional[str] = Header(None, alias="x-ms-proposed-lease-id"),
    x_ms_lease_break_period: Optional[int] = Header(None, alias="x-ms-lease-break-period"),
    comp: Optional[str] = Query(None),
    blockid: Optional[str] = Query(None),
) -> Response:
    """
    Upload a blob or stage a block or perform lease operations.
    
    Azure REST API: PUT https://{account}.blob.core.windows.net/{container}/{blob}
    
    Args:
        account_name: Storage account name
        container_name: Container name
        blob_name: Blob name
        request: FastAPI request
        x_ms_blob_type: Blob type (BlockBlob)
        content_type: Content type
        content_encoding: Content encoding
        content_language: Content language
        cache_control: Cache control
        content_disposition: Content disposition
        if_match: Conditional ETag match
        if_none_match: Conditional ETag non-match
        x_ms_lease_id: Lease ID
        x_ms_lease_action: Lease action (acquire, renew, release, break, change)
        x_ms_lease_duration: Lease duration in seconds
        x_ms_proposed_lease_id: Proposed lease ID
        x_ms_lease_break_period: Break period in seconds
        comp: Operation component (block, blocklist, metadata, lease)
        blockid: Block ID for Put Block operation
        
    Returns:
        201 Created for Put Blob, 201 Created for Put Block, various for lease
        
    Raises:
        404 Not Found: Container not found or blob not found
        400 Bad Request: Invalid block ID or parameters
    """
    # Handle lease operations
    if comp == "lease":
        if not x_ms_lease_action:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-action is required for lease operations"),
            )
        
        action = x_ms_lease_action.lower()
        
        try:
            if action == "acquire":
                if x_ms_lease_duration is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-duration is required for acquire"),
                    )
                
                lease = await backend.acquire_blob_lease(
                    container_name=container_name,
                    blob_name=blob_name,
                    duration=x_ms_lease_duration,
                    proposed_lease_id=x_ms_proposed_lease_id,
                )
                
                response = Response(status_code=status.HTTP_201_CREATED)
                response.headers["x-ms-lease-id"] = lease.lease_id
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            elif action == "renew":
                if x_ms_lease_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-id is required for renew"),
                    )
                
                lease = await backend.renew_blob_lease(
                    container_name=container_name,
                    blob_name=blob_name,
                    lease_id=x_ms_lease_id,
                )
                
                response = Response(status_code=status.HTTP_200_OK)
                response.headers["x-ms-lease-id"] = lease.lease_id
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            elif action == "release":
                if x_ms_lease_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-id is required for release"),
                    )
                
                await backend.release_blob_lease(
                    container_name=container_name,
                    blob_name=blob_name,
                    lease_id=x_ms_lease_id,
                )
                
                response = Response(status_code=status.HTTP_200_OK)
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            elif action == "break":
                remaining_time = await backend.break_blob_lease(
                    container_name=container_name,
                    blob_name=blob_name,
                    break_period=x_ms_lease_break_period,
                )
                
                response = Response(status_code=status.HTTP_202_ACCEPTED)
                response.headers["x-ms-lease-time"] = str(remaining_time)
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            elif action == "change":
                if x_ms_lease_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-lease-id is required for change"),
                    )
                if x_ms_proposed_lease_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_format_error_response("MissingRequiredHeader", "x-ms-proposed-lease-id is required for change"),
                    )
                
                lease = await backend.change_blob_lease(
                    container_name=container_name,
                    blob_name=blob_name,
                    lease_id=x_ms_lease_id,
                    proposed_lease_id=x_ms_proposed_lease_id,
                )
                
                response = Response(status_code=status.HTTP_200_OK)
                response.headers["x-ms-lease-id"] = lease.lease_id
                response.headers["x-ms-request-id"] = "localzure-request-id"
                response.headers["x-ms-version"] = "2021-08-06"
                response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                return response
            
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_format_error_response("InvalidHeaderValue", f"Invalid lease action: {action}"),
                )
        
        except (LeaseNotFoundError, ContainerNotFoundError, BlobNotFoundError) as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response(type(e).__name__.replace("Error", ""), str(e)),
            )
        except LeaseAlreadyPresentError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_format_error_response("LeaseAlreadyPresent", str(e)),
            )
        except LeaseIdMismatchError as e:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=_format_error_response("LeaseIdMismatchConditionNotMet", str(e)),
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_format_error_response("InvalidHeaderValue", str(e)),
            )
    
    # Handle snapshot operation
    if comp == "snapshot":
        try:
            snapshot = await backend.create_snapshot(container_name, blob_name)
            
            response = Response(status_code=status.HTTP_201_CREATED)
            response.headers["x-ms-snapshot"] = snapshot.snapshot_id if snapshot.snapshot_id else ""
            response.headers["x-ms-request-id"] = "localzure-request-id"
            response.headers["x-ms-version"] = "2021-08-06"
            response.headers["ETag"] = f'"{snapshot.properties.etag}"'
            response.headers["Last-Modified"] = snapshot.properties.last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
            response.headers["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
            return response
        
        except ContainerNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response("ContainerNotFound", "Container not found"),
            )
        except BlobNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response("BlobNotFound", "Blob not found"),
            )
    
    # Handle Put Block operation
    if comp == "block" and blockid:
        try:
            content = await request.body()
            await backend.put_block(container_name, blob_name, blockid, content)
            
            return Response(
                status_code=status.HTTP_201_CREATED,
                headers={
                    'x-ms-request-id': 'localzure-request-id',
                    'x-ms-version': '2021-08-06',
                    'Content-MD5': '',  # TODO: Calculate MD5
                },
            )
            
        except ContainerNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response("ContainerNotFound", "Container not found"),
            )
        except InvalidBlockIdError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_format_error_response("InvalidBlockId", str(e)),
            )
    
    # Handle Put Block List operation
    if comp == "blocklist":
        try:
            body = await request.body()
            block_list = _parse_block_list_xml(body)
            
            # Extract metadata from headers
            metadata = {}
            for key, value in request.headers.items():
                if key.lower().startswith('x-ms-meta-'):
                    meta_key = key[10:]
                    metadata[meta_key] = value
            
            blob = await backend.put_block_list(
                container_name,
                blob_name,
                block_list,
                content_type=content_type or "application/octet-stream",
                metadata=metadata if metadata else None,
                lease_id=x_ms_lease_id,
            )
            
            response_headers = blob.properties.to_headers()
            response_headers['x-ms-request-id'] = 'localzure-request-id'
            response_headers['x-ms-version'] = '2021-08-06'
            # Remove Content-Length from response to avoid mismatch
            response_headers.pop('Content-Length', None)
            
            return Response(
                status_code=status.HTTP_201_CREATED,
                headers=response_headers,
            )
            
        except ContainerNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response("ContainerNotFound", "Container not found"),
            )
        except BlobNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response("BlobNotFound", "Blob not found"),
            )
        except InvalidBlockIdError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_format_error_response("InvalidBlockId", str(e)),
            )
        except LeaseIdMissingError:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=_format_error_response("LeaseIdMissing", "There is currently a lease on the resource and no lease ID was specified in the request"),
            )
        except LeaseIdMismatchError:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=_format_error_response("LeaseIdMismatchWithBlobOperation", "The lease ID specified did not match the lease ID for the blob"),
            )
    
    # Handle Set Blob Metadata operation
    if comp == "metadata":
        try:
            # Extract metadata from headers
            metadata = {}
            for key, value in request.headers.items():
                if key.lower().startswith('x-ms-meta-'):
                    meta_key = key[10:]
                    metadata[meta_key] = value
            
            blob = await backend.set_blob_metadata(container_name, blob_name, metadata, lease_id=x_ms_lease_id)
            
            response_headers = blob.properties.to_headers()
            response_headers['x-ms-request-id'] = 'localzure-request-id'
            response_headers['x-ms-version'] = '2021-08-06'
            # Remove Content-Length from response to avoid mismatch
            response_headers.pop('Content-Length', None)
            
            return Response(
                status_code=status.HTTP_200_OK,
                headers=response_headers,
            )
            
        except ContainerNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response("ContainerNotFound", "Container not found"),
            )
        except BlobNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response("BlobNotFound", "Blob not found"),
            )
        except LeaseIdMissingError:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=_format_error_response("LeaseIdMissing", "There is currently a lease on the resource and no lease ID was specified in the request"),
            )
        except LeaseIdMismatchError:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=_format_error_response("LeaseIdMismatchWithBlobOperation", "The lease ID specified did not match the lease ID for the blob"),
            )
    
    # Handle regular Put Blob operation
    try:
        content = await request.body()
        
        # Extract metadata from headers
        metadata = {}
        for key, value in request.headers.items():
            if key.lower().startswith('x-ms-meta-'):
                meta_key = key[10:]
                metadata[meta_key] = value
        
        # Check conditional headers
        if if_match or if_none_match:
            try:
                existing_blob = await backend.get_blob(container_name, blob_name)
                cond = ConditionalHeaders(if_match=if_match, if_none_match=if_none_match)
                status_code = cond.check_conditions(existing_blob.properties.etag, existing_blob.properties.last_modified)
                if status_code == 412:
                    raise HTTPException(
                        status_code=status.HTTP_412_PRECONDITION_FAILED,
                        detail=_format_error_response("ConditionNotMet", "Condition not met"),
                    )
                elif status_code == 304:
                    return Response(status_code=status.HTTP_304_NOT_MODIFIED)
            except BlobNotFoundError:
                pass  # Blob doesn't exist, continue with creation
        
        blob = await backend.put_blob(
            container_name,
            blob_name,
            content,
            content_type=content_type or "application/octet-stream",
            metadata=metadata if metadata else None,
            content_encoding=content_encoding,
            content_language=content_language,
            cache_control=cache_control,
            content_disposition=content_disposition,
            lease_id=x_ms_lease_id,
        )
        
        response_headers = blob.properties.to_headers()
        response_headers['x-ms-request-id'] = 'localzure-request-id'
        response_headers['x-ms-version'] = '2021-08-06'
        # Remove Content-Length from PUT response to avoid mismatch
        response_headers.pop('Content-Length', None)
        
        return Response(
            status_code=status.HTTP_201_CREATED,
            headers=response_headers,
        )
        
    except ContainerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("ContainerNotFound", "Container not found"),
        )
    except LeaseIdMissingError:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=_format_error_response("LeaseIdMissing", "There is currently a lease on the resource and no lease ID was specified in the request"),
        )
    except LeaseIdMismatchError:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=_format_error_response("LeaseIdMismatchWithBlobOperation", "The lease ID specified did not match the lease ID for the blob"),
        )



@router.get(
    "/{account_name}/{container_name}/{blob_name:path}",
    status_code=status.HTTP_200_OK,
    summary="Get Blob",
)
async def get_blob(
    account_name: str,
    container_name: str,
    blob_name: str,
    comp: Optional[str] = Query(None),
    snapshot: Optional[str] = Query(None),
    if_match: Optional[str] = Header(None),
    if_none_match: Optional[str] = Header(None),
    if_modified_since: Optional[str] = Header(None),
    if_unmodified_since: Optional[str] = Header(None),
) -> Response:
    """
    Download blob content or get blob properties.
    
    Azure REST API: GET https://{account}.blob.core.windows.net/{container}/{blob}
    
    Args:
        account_name: Storage account name
        container_name: Container name
        blob_name: Blob name
        comp: Operation component (metadata for properties only)
        snapshot: Snapshot identifier (datetime string)
        if_match: Conditional ETag match
        if_none_match: Conditional ETag non-match
        if_modified_since: Conditional modified since
        if_unmodified_since: Conditional unmodified since
        
    Returns:
        200 OK with blob content or 304 Not Modified
        
    Raises:
        404 Not Found: Container or blob not found
        412 Precondition Failed: Conditions not met
    """
    try:
        # Get blob or snapshot
        if snapshot:
            blob = await backend.get_blob_snapshot(container_name, blob_name, snapshot)
        else:
            blob = await backend.get_blob(container_name, blob_name)
        
        # Parse conditional headers
        if_modified_dt = None
        if_unmodified_dt = None
        if if_modified_since:
            try:
                if_modified_dt = datetime.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S GMT').replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if if_unmodified_since:
            try:
                if_unmodified_dt = datetime.strptime(if_unmodified_since, '%a, %d %b %Y %H:%M:%S GMT').replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        
        # Check conditional headers
        cond = ConditionalHeaders(
            if_match=if_match,
            if_none_match=if_none_match,
            if_modified_since=if_modified_dt,
            if_unmodified_since=if_unmodified_dt,
        )
        status_code = cond.check_conditions(blob.properties.etag, blob.properties.last_modified)
        if status_code == 412:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=_format_error_response("ConditionNotMet", "Condition not met"),
            )
        elif status_code == 304:
            return Response(status_code=status.HTTP_304_NOT_MODIFIED)
        
        # Handle metadata-only request
        if comp == "metadata":
            response_headers = blob.properties.to_headers()
            response_headers.update(blob.metadata.to_headers())
            response_headers['x-ms-request-id'] = 'localzure-request-id'
            response_headers['x-ms-version'] = '2021-08-06'
            
            return Response(
                status_code=status.HTTP_200_OK,
                headers=response_headers,
            )
        
        # Return blob content
        response_headers = blob.properties.to_headers()
        response_headers.update(blob.metadata.to_headers())
        response_headers['x-ms-request-id'] = 'localzure-request-id'
        response_headers['x-ms-version'] = '2021-08-06'
        
        return Response(
            content=blob.content,
            status_code=status.HTTP_200_OK,
            headers=response_headers,
            media_type=blob.properties.content_type,
        )
        
    except ContainerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("ContainerNotFound", "Container not found"),
        )
    except BlobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("BlobNotFound", "Blob not found"),
        )
    except SnapshotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("BlobNotFound", "Snapshot not found"),
        )


@router.delete(
    "/{account_name}/{container_name}/{blob_name:path}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete Blob",
)
async def delete_blob(
    account_name: str,
    container_name: str,
    blob_name: str,
    x_ms_lease_id: Optional[str] = Header(None, alias="x-ms-lease-id"),
    x_ms_delete_snapshots: Optional[str] = Header(None, alias="x-ms-delete-snapshots"),
    snapshot: Optional[str] = Query(None),
) -> Response:
    """
    Delete a blob or snapshot.
    
    Azure REST API: DELETE https://{account}.blob.core.windows.net/{container}/{blob}
    
    Args:
        account_name: Storage account name
        container_name: Container name
        blob_name: Blob name
        x_ms_lease_id: Lease ID if blob is leased
        x_ms_delete_snapshots: How to handle snapshots ("include" or "only")
        snapshot: Specific snapshot to delete
        
    Returns:
        202 Accepted
        
    Raises:
        404 Not Found: Container or blob not found
        400 Bad Request: Snapshots exist but delete_snapshots not specified
    """
    try:
        # Delete specific snapshot
        if snapshot:
            await backend.delete_snapshot(container_name, blob_name, snapshot)
        # Delete blob with snapshot handling
        elif x_ms_delete_snapshots:
            await backend.delete_blob_with_snapshots(
                container_name,
                blob_name,
                delete_snapshots=x_ms_delete_snapshots,
                lease_id=x_ms_lease_id
            )
        # Simple delete (error if snapshots exist)
        else:
            await backend.delete_blob_with_snapshots(
                container_name,
                blob_name,
                delete_snapshots=None,
                lease_id=x_ms_lease_id
            )
        
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
            detail=_format_error_response("ContainerNotFound", "Container not found"),
        )
    except BlobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("BlobNotFound", "Blob not found"),
        )
    except SnapshotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("BlobNotFound", "Snapshot not found"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_format_error_response("SnapshotsPresent", str(e)),
        )
    except LeaseIdMissingError:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=_format_error_response("LeaseIdMissing", "There is currently a lease on the resource and no lease ID was specified in the request"),
        )
    except LeaseIdMismatchError:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=_format_error_response("LeaseIdMismatchWithBlobOperation", "The lease ID specified did not match the lease ID for the blob"),
        )


def _parse_block_list_xml(xml_data: bytes) -> List[tuple[str, BlockListType]]:
    """
    Parse block list XML from Put Block List request.
    
    Args:
        xml_data: XML request body
        
    Returns:
        List of (block_id, block_type) tuples
    """
    root = ET.fromstring(xml_data)
    blocks = []
    
    for block_element in root:
        block_id = block_element.text
        block_type_str = block_element.tag
        
        if block_type_str == "Committed":
            block_type = BlockListType.COMMITTED
        elif block_type_str == "Uncommitted":
            block_type = BlockListType.UNCOMMITTED
        elif block_type_str == "Latest":
            block_type = BlockListType.LATEST
        else:
            continue
        
        blocks.append((block_id, block_type))
    
    return blocks


@router.post("/reset", status_code=status.HTTP_200_OK, summary="Reset Backend")
async def reset_backend() -> Dict:
    """
    Reset the backend, removing all containers, blobs, and leases.
    
    This is a testing endpoint not present in Azure.
    """
    await backend.reset()
    return {"message": "Backend reset successfully"}

