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
)
from .models import (
    BlockListType,
    BlockReference,
    ConditionalHeaders,
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
        
    Returns:
        200 OK with container properties in headers or blob list XML
        
    Raises:
        404 Not Found: Container not found
    """
    # Handle List Blobs operation
    if restype == "container" and comp == "list":
        try:
            blobs, next_marker = await backend.list_blobs(
                container_name,
                prefix=prefix,
                delimiter=delimiter,
                max_results=maxresults,
                marker=marker,
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
    comp: Optional[str] = Query(None),
    blockid: Optional[str] = Query(None),
) -> Response:
    """
    Upload a blob or stage a block.
    
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
        comp: Operation component (block, blocklist, metadata)
        blockid: Block ID for Put Block operation
        
    Returns:
        201 Created for Put Blob, 201 Created for Put Block
        
    Raises:
        404 Not Found: Container not found
        400 Bad Request: Invalid block ID
    """
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
            )
            
            response_headers = blob.properties.to_headers()
            response_headers['x-ms-request-id'] = 'localzure-request-id'
            response_headers['x-ms-version'] = '2021-08-06'
            
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
    
    # Handle Set Blob Metadata operation
    if comp == "metadata":
        try:
            # Extract metadata from headers
            metadata = {}
            for key, value in request.headers.items():
                if key.lower().startswith('x-ms-meta-'):
                    meta_key = key[10:]
                    metadata[meta_key] = value
            
            blob = await backend.set_blob_metadata(container_name, blob_name, metadata)
            
            response_headers = blob.properties.to_headers()
            response_headers['x-ms-request-id'] = 'localzure-request-id'
            response_headers['x-ms-version'] = '2021-08-06'
            
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
        )
        
        response_headers = blob.properties.to_headers()
        response_headers['x-ms-request-id'] = 'localzure-request-id'
        response_headers['x-ms-version'] = '2021-08-06'
        
        return Response(
            status_code=status.HTTP_201_CREATED,
            headers=response_headers,
        )
        
    except ContainerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("ContainerNotFound", "Container not found"),
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


@router.delete(
    "/{account_name}/{container_name}/{blob_name:path}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete Blob",
)
async def delete_blob(
    account_name: str,
    container_name: str,
    blob_name: str,
) -> Response:
    """
    Delete a blob.
    
    Azure REST API: DELETE https://{account}.blob.core.windows.net/{container}/{blob}
    
    Args:
        account_name: Storage account name
        container_name: Container name
        blob_name: Blob name
        
    Returns:
        202 Accepted
        
    Raises:
        404 Not Found: Container or blob not found
    """
    try:
        await backend.delete_blob(container_name, blob_name)
        
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
    Reset the backend, removing all containers and blobs.
    
    This is a testing endpoint not present in Azure.
    """
    await backend.reset()
    return {"message": "Backend reset successfully"}

