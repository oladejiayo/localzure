"""
Queue Storage API Endpoints

FastAPI endpoints for Azure Queue Storage operations.

Author: Ayodele Oladeji
Date: 2025
"""

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from typing import Dict, Optional
import xml.etree.ElementTree as ET

from .backend import (
    QueueAlreadyExistsError,
    QueueBackend,
    QueueNotFoundError,
    InvalidQueueNameError,
    MessageNotFoundError,
    InvalidPopReceiptError,
)
from .models import CreateQueueRequest, SetQueueMetadataRequest, PutMessageRequest, UpdateMessageRequest


# Initialize backend
backend = QueueBackend()

# Create router
router = APIRouter(prefix="/queue", tags=["queue-storage"])


def _format_error_response(code: str, message: str) -> str:
    """Format error response as XML."""
    root = ET.Element("Error")
    ET.SubElement(root, "Code").text = code
    ET.SubElement(root, "Message").text = message
    return ET.tostring(root, encoding="unicode")


def _parse_metadata_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Extract metadata from x-ms-meta-* headers."""
    metadata = {}
    for key, value in headers.items():
        if key.lower().startswith("x-ms-meta-"):
            meta_key = key[10:]  # Remove 'x-ms-meta-' prefix
            metadata[meta_key] = value
    return metadata


@router.put(
    "/{account_name}/{queue_name}",
    summary="Create Queue or Set Metadata",
)
async def queue_operations(
    account_name: str,
    queue_name: str,
    request: Request,
    comp: Optional[str] = Query(None),
) -> Response:
    """
    Handle queue PUT operations - create queue or set metadata.
    
    Azure REST API:
    - PUT https://{account}.queue.core.windows.net/{queue} - Create queue
    - PUT https://{account}.queue.core.windows.net/{queue}?comp=metadata - Set metadata
    
    Args:
        account_name: Storage account name
        queue_name: Queue name
        request: FastAPI request to access headers
        comp: Optional "metadata" for set metadata operation
        
    Returns:
        201 Created for new queue
        204 No Content for metadata update
        
    Raises:
        400 Bad Request: Invalid queue name or comp parameter
        404 Not Found: Queue not found (for metadata operation)
        409 Conflict: Queue already exists (for create)
    """
    # Parse metadata from headers
    metadata = _parse_metadata_headers(dict(request.headers))
    
    # If comp=metadata, set metadata
    if comp == "metadata":
        try:
            # Set metadata
            await backend.set_queue_metadata(queue_name, metadata)
            
            # Build response
            return Response(
                status_code=status.HTTP_204_NO_CONTENT,
                headers={
                    'x-ms-request-id': 'localzure-request-id',
                    'x-ms-version': '2021-08-06',
                },
            )
            
        except QueueNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_format_error_response("QueueNotFound", f"Queue '{queue_name}' not found"),
            )
    
    elif comp is None:
        # Create queue
        try:
            # Create queue
            queue = await backend.create_queue(queue_name, metadata)
            
            # Build response
            return Response(
                status_code=status.HTTP_201_CREATED,
                headers={
                    'x-ms-request-id': 'localzure-request-id',
                    'x-ms-version': '2021-08-06',
                },
            )
            
        except InvalidQueueNameError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_format_error_response("InvalidQueueName", str(e)),
            )
        except QueueAlreadyExistsError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_format_error_response("QueueAlreadyExists", f"Queue '{queue_name}' already exists"),
            )
    
    else:
        # Invalid comp parameter
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_format_error_response("InvalidQueryParameter", f"Invalid comp parameter: {comp}"),
        )


@router.get(
    "/{account_name}",
    status_code=status.HTTP_200_OK,
    summary="List Queues",
)
async def list_queues(
    account_name: str,
    comp: str = Query(...),
    prefix: Optional[str] = Query(None),
    marker: Optional[str] = Query(None),
    maxresults: Optional[int] = Query(None),
    include: Optional[str] = Query(None),
) -> Response:
    """
    List queues in the storage account.
    
    Azure REST API: GET https://{account}.queue.core.windows.net/?comp=list
    
    Args:
        account_name: Storage account name
        comp: Must be "list"
        prefix: Optional prefix filter
        marker: Continuation token
        maxresults: Maximum results to return
        include: Optional include options (metadata)
        
    Returns:
        200 OK with XML list of queues
    """
    if comp != "list":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_format_error_response("InvalidQueryParameter", "comp must be 'list'"),
        )
    
    # Determine if metadata should be included
    include_metadata = include and "metadata" in include.lower()
    
    # List queues
    queues, next_marker = await backend.list_queues(
        prefix=prefix,
        max_results=maxresults,
        marker=marker,
        include_metadata=include_metadata,
    )
    
    # Build XML response
    root = ET.Element("EnumerationResults")
    root.set("ServiceEndpoint", f"https://{account_name}.queue.core.windows.net/")
    
    if prefix:
        ET.SubElement(root, "Prefix").text = prefix
    if marker:
        ET.SubElement(root, "Marker").text = marker
    if maxresults:
        ET.SubElement(root, "MaxResults").text = str(maxresults)
    
    queues_element = ET.SubElement(root, "Queues")
    
    for queue in queues:
        queue_element = ET.SubElement(queues_element, "Queue")
        ET.SubElement(queue_element, "Name").text = queue.name
        
        if include_metadata:
            metadata_element = ET.SubElement(queue_element, "Metadata")
            if queue.metadata.metadata:
                for key, value in queue.metadata.metadata.items():
                    ET.SubElement(metadata_element, key).text = value
    
    if next_marker:
        ET.SubElement(root, "NextMarker").text = next_marker
    
    # Convert to XML string
    xml_content = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode")
    
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={
            'x-ms-request-id': 'localzure-request-id',
            'x-ms-version': '2021-08-06',
        },
    )


@router.get(
    "/{account_name}/{queue_name}",
    status_code=status.HTTP_200_OK,
    summary="Get Queue Metadata",
)
async def get_queue_metadata(
    account_name: str,
    queue_name: str,
    comp: str = Query(...),
) -> Response:
    """
    Get queue metadata and properties.
    
    Azure REST API: GET https://{account}.queue.core.windows.net/{queue}?comp=metadata
    
    Args:
        account_name: Storage account name
        queue_name: Queue name
        comp: Must be "metadata"
        
    Returns:
        200 OK with metadata in headers
        
    Raises:
        404 Not Found: Queue not found
    """
    if comp != "metadata":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_format_error_response("InvalidQueryParameter", "comp must be 'metadata'"),
        )
    
    try:
        metadata, properties = await backend.get_queue_metadata(queue_name)
        
        # Build response with metadata and properties in headers
        headers_dict = {
            'x-ms-request-id': 'localzure-request-id',
            'x-ms-version': '2021-08-06',
        }
        headers_dict.update(metadata.to_headers())
        headers_dict.update(properties.to_headers())
        
        return Response(
            status_code=status.HTTP_200_OK,
            headers=headers_dict,
        )
        
    except QueueNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("QueueNotFound", f"Queue '{queue_name}' not found"),
        )

@router.delete(
    "/{account_name}/{queue_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Queue",
)
async def delete_queue(
    account_name: str,
    queue_name: str,
) -> Response:
    """
    Delete a queue and all its messages.
    
    Azure REST API: DELETE https://{account}.queue.core.windows.net/{queue}
    
    Args:
        account_name: Storage account name
        queue_name: Queue name
        
    Returns:
        204 No Content on success
        
    Raises:
        404 Not Found: Queue not found
    """
    try:
        await backend.delete_queue(queue_name)
        
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={
                'x-ms-request-id': 'localzure-request-id',
                'x-ms-version': '2021-08-06',
            },
        )
        
    except QueueNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("QueueNotFound", f"Queue '{queue_name}' not found"),
        )


# Message Operations


@router.post(
    "/{account_name}/{queue_name}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Put Message",
)
async def put_message(
    account_name: str,
    queue_name: str,
    request: Request,
    visibilitytimeout: Optional[int] = Query(default=0, alias="visibilitytimeout"),
    messagettl: Optional[int] = Query(default=604800, alias="messagettl"),
) -> Response:
    """
    Put a message into the queue.
    
    Azure REST API: POST https://{account}.queue.core.windows.net/{queue}/messages
    
    Args:
        account_name: Storage account name
        queue_name: Queue name
        request: FastAPI request containing XML body
        visibilitytimeout: Initial visibility timeout in seconds (0-604800)
        messagettl: Message time-to-live in seconds (1-604800)
        
    Returns:
        201 Created with message details in XML
        
    Raises:
        400 Bad Request: Invalid parameters
        404 Not Found: Queue not found
    """
    try:
        # Parse XML body to get message text
        body = await request.body()
        root = ET.fromstring(body)
        message_text_elem = root.find("MessageText")
        
        if message_text_elem is None or not message_text_elem.text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_format_error_response("InvalidMessageContent", "Message text is required"),
            )
        
        message_text = message_text_elem.text
        
        # Put message
        message = await backend.put_message(
            queue_name,
            message_text,
            visibility_timeout=visibilitytimeout or 0,
            message_ttl=messagettl or 604800,
        )
        
        # Build XML response
        root = ET.Element("QueueMessagesList")
        msg_elem = ET.SubElement(root, "QueueMessage")
        ET.SubElement(msg_elem, "MessageId").text = message.message_id
        ET.SubElement(msg_elem, "InsertionTime").text = message.insertion_time.strftime('%a, %d %b %Y %H:%M:%S GMT')
        ET.SubElement(msg_elem, "ExpirationTime").text = message.expiration_time.strftime('%a, %d %b %Y %H:%M:%S GMT')
        ET.SubElement(msg_elem, "PopReceipt").text = message.pop_receipt
        ET.SubElement(msg_elem, "TimeNextVisible").text = message.time_next_visible.strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        xml_content = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode")
        
        return Response(
            content=xml_content,
            media_type="application/xml",
            status_code=status.HTTP_201_CREATED,
            headers={
                'x-ms-request-id': 'localzure-request-id',
                'x-ms-version': '2021-08-06',
            },
        )
        
    except QueueNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("QueueNotFound", f"Queue '{queue_name}' not found"),
        )


@router.get(
    "/{account_name}/{queue_name}/messages",
    status_code=status.HTTP_200_OK,
    summary="Get Messages",
)
async def get_messages_endpoint(
    account_name: str,
    queue_name: str,
    numofmessages: Optional[int] = Query(default=1, alias="numofmessages", ge=1, le=32),
    visibilitytimeout: Optional[int] = Query(default=30, alias="visibilitytimeout", ge=0, le=604800),
    peekonly: Optional[bool] = Query(default=False, alias="peekonly"),
) -> Response:
    """
    Get messages from the queue or peek messages.
    
    Azure REST API: GET https://{account}.queue.core.windows.net/{queue}/messages
    
    Args:
        account_name: Storage account name
        queue_name: Queue name
        numofmessages: Number of messages to retrieve (1-32)
        visibilitytimeout: Visibility timeout in seconds (0-604800)
        peekonly: If True, peek messages without changing visibility
        
    Returns:
        200 OK with messages in XML
        
    Raises:
        404 Not Found: Queue not found
    """
    try:
        # Get or peek messages based on parameter
        if peekonly:
            messages = await backend.peek_messages(queue_name, numofmessages or 1)
        else:
            # Use 30 as default only if visibilitytimeout is None (not passed)
            visibility = 30 if visibilitytimeout is None else visibilitytimeout
            messages = await backend.get_messages(
                queue_name,
                numofmessages or 1,
                visibility,
            )
        
        # Build XML response
        root = ET.Element("QueueMessagesList")
        for message in messages:
            msg_elem = ET.SubElement(root, "QueueMessage")
            msg_dict = message.to_dict(include_pop_receipt=not peekonly)
            
            ET.SubElement(msg_elem, "MessageId").text = msg_dict["MessageId"]
            ET.SubElement(msg_elem, "InsertionTime").text = msg_dict["InsertionTime"]
            ET.SubElement(msg_elem, "ExpirationTime").text = msg_dict["ExpirationTime"]
            
            if not peekonly:
                ET.SubElement(msg_elem, "PopReceipt").text = msg_dict["PopReceipt"]
                ET.SubElement(msg_elem, "TimeNextVisible").text = msg_dict["TimeNextVisible"]
            
            ET.SubElement(msg_elem, "DequeueCount").text = msg_dict["DequeueCount"]
            ET.SubElement(msg_elem, "MessageText").text = msg_dict["MessageText"]
        
        xml_content = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode")
        
        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={
                'x-ms-request-id': 'localzure-request-id',
                'x-ms-version': '2021-08-06',
            },
        )
        
    except QueueNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("QueueNotFound", f"Queue '{queue_name}' not found"),
        )


@router.put(
    "/{account_name}/{queue_name}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update Message",
)
async def update_message_endpoint(
    account_name: str,
    queue_name: str,
    message_id: str,
    request: Request,
    popreceipt: str = Query(..., alias="popreceipt"),
    visibilitytimeout: int = Query(..., alias="visibilitytimeout", ge=0, le=604800),
) -> Response:
    """
    Update a message's visibility timeout and optionally its content.
    
    Azure REST API: PUT https://{account}.queue.core.windows.net/{queue}/messages/{messageid}
    
    Args:
        account_name: Storage account name
        queue_name: Queue name
        message_id: Message ID
        request: FastAPI request containing optional XML body
        popreceipt: Pop receipt from get_messages
        visibilitytimeout: New visibility timeout in seconds (0-604800)
        
    Returns:
        204 No Content with new pop receipt in headers
        
    Raises:
        400 Bad Request: Invalid pop receipt
        404 Not Found: Queue or message not found
    """
    try:
        # Parse XML body for optional new message text
        new_text = None
        body = await request.body()
        if body:
            try:
                root = ET.fromstring(body)
                message_text_elem = root.find("MessageText")
                if message_text_elem is not None and message_text_elem.text:
                    new_text = message_text_elem.text
            except ET.ParseError:
                pass  # No body or invalid XML, just update visibility
        
        # Update message
        new_pop_receipt = await backend.update_message(
            queue_name,
            message_id,
            popreceipt,
            visibilitytimeout,
            new_text,
        )
        
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={
                'x-ms-request-id': 'localzure-request-id',
                'x-ms-version': '2021-08-06',
                'x-ms-popreceipt': new_pop_receipt,
                'x-ms-time-next-visible': 'localzure-time',  # Simplified
            },
        )
        
    except QueueNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("QueueNotFound", f"Queue '{queue_name}' not found"),
        )
    except MessageNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("MessageNotFound", f"Message '{message_id}' not found"),
        )
    except InvalidPopReceiptError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_format_error_response("InvalidPopReceipt", "The specified pop receipt is invalid"),
        )


@router.delete(
    "/{account_name}/{queue_name}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Message",
)
async def delete_message_endpoint(
    account_name: str,
    queue_name: str,
    message_id: str,
    popreceipt: str = Query(..., alias="popreceipt"),
) -> Response:
    """
    Delete a message from the queue.
    
    Azure REST API: DELETE https://{account}.queue.core.windows.net/{queue}/messages/{messageid}
    
    Args:
        account_name: Storage account name
        queue_name: Queue name
        message_id: Message ID
        popreceipt: Pop receipt from get_messages
        
    Returns:
        204 No Content on success
        
    Raises:
        400 Bad Request: Invalid pop receipt
        404 Not Found: Queue or message not found
    """
    try:
        await backend.delete_message(queue_name, message_id, popreceipt)
        
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={
                'x-ms-request-id': 'localzure-request-id',
                'x-ms-version': '2021-08-06',
            },
        )
        
    except QueueNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("QueueNotFound", f"Queue '{queue_name}' not found"),
        )
    except MessageNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_format_error_response("MessageNotFound", f"Message '{message_id}' not found"),
        )
    except InvalidPopReceiptError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_format_error_response("InvalidPopReceipt", "The specified pop receipt is invalid"),
        )

