"""
Service Bus API Endpoints.

FastAPI endpoints for Azure Service Bus Management API.
Provides HTTP/REST endpoints for queue, topic, subscription, and message operations.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

from datetime import datetime, timezone
from typing import Optional
import xml.etree.ElementTree as ET

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from .constants import XML_DECLARATION, XML_MEDIA_TYPE
from .logging_utils import StructuredLogger
from .exceptions import (
    QueueAlreadyExistsError,
    QueueNotFoundError,
    InvalidQueueNameError,
    QuotaExceededError,
    MessageNotFoundError,
    MessageLockLostError,
    TopicAlreadyExistsError,
    TopicNotFoundError,
    SubscriptionAlreadyExistsError,
    SubscriptionNotFoundError,
    RuleAlreadyExistsError,
    RuleNotFoundError,
)
from .error_handlers import register_exception_handlers
from .backend import ServiceBusBackend
from .models import (
    CreateQueueRequest,
    UpdateQueueRequest,
    QueueProperties,
    ServiceBusMessage,
    SendMessageRequest,
    ReceiveMode,
    CreateTopicRequest,
    UpdateTopicRequest,
    TopicProperties,
    CreateSubscriptionRequest,
    UpdateSubscriptionRequest,
    SubscriptionProperties,
    SubscriptionFilter,
    FilterType,
)


# Initialize backend and logger
backend = ServiceBusBackend()
logger = StructuredLogger('localzure.services.servicebus.api')

# Create router
router = APIRouter(prefix="/servicebus", tags=["service-bus"])

# Note: Exception handlers must be registered at the FastAPI app level,
# not the router level. Call register_exception_handlers(app) when
# including this router in your FastAPI app.


def _parse_iso_duration(duration_str: str) -> int:
    """
    Parse ISO 8601 duration string to seconds.
    
    Supports formats like:
    - PT60S (60 seconds)
    - PT1M (60 seconds)
    - PT1H (3600 seconds)
    - P1D (86400 seconds)
    - P14D (1209600 seconds)
    
    Args:
        duration_str: ISO 8601 duration string
        
    Returns:
        Duration in seconds
    """
    import re
    
    # Remove 'P' prefix
    if not duration_str.startswith('P'):
        raise ValueError(f"Invalid ISO 8601 duration: {duration_str}")
    
    duration_str = duration_str[1:]
    
    # Split into date and time parts
    time_part = ""
    date_part = duration_str
    if 'T' in duration_str:
        parts = duration_str.split('T')
        date_part = parts[0]
        time_part = parts[1] if len(parts) > 1 else ""
    
    total_seconds = 0
    
    # Parse date part (days, months, years)
    if date_part:
        # Days
        days_match = re.search(r'(\d+)D', date_part)
        if days_match:
            total_seconds += int(days_match.group(1)) * 86400
        
        # Months (approximate as 30 days)
        months_match = re.search(r'(\d+)M', date_part)
        if months_match:
            total_seconds += int(months_match.group(1)) * 30 * 86400
        
        # Years (approximate as 365 days)
        years_match = re.search(r'(\d+)Y', date_part)
        if years_match:
            total_seconds += int(years_match.group(1)) * 365 * 86400
    
    # Parse time part (hours, minutes, seconds)
    if time_part:
        # Hours
        hours_match = re.search(r'(\d+)H', time_part)
        if hours_match:
            total_seconds += int(hours_match.group(1)) * 3600
        
        # Minutes
        minutes_match = re.search(r'(\d+)M', time_part)
        if minutes_match:
            total_seconds += int(minutes_match.group(1)) * 60
        
        # Seconds
        seconds_match = re.search(r'(\d+(?:\.\d+)?)S', time_part)
        if seconds_match:
            total_seconds += int(float(seconds_match.group(1)))
    
    return total_seconds


def _format_error_response(code: str, message: str) -> str:
    """
    Format error response as XML for Service Bus Management API.
    
    Args:
        code: Error code
        message: Error message
        
    Returns:
        XML error response string
    """
    root = ET.Element("Error")
    ET.SubElement(root, "Code").text = code
    ET.SubElement(root, "Detail").text = message
    
    return XML_DECLARATION + ET.tostring(root, encoding="unicode")


def _parse_queue_properties_from_xml(xml_content: str) -> QueueProperties:
    """
    Parse queue properties from XML request body.
    
    Args:
        xml_content: XML content
        
    Returns:
        QueueProperties object
    """
    try:
        root = ET.fromstring(xml_content)
        
        # Extract properties (handle both with and without namespace)
        def get_text(tag_name: str, default=None):
            """Get text from element, handling namespace."""
            elem = root.find(f".//{tag_name}")
            if elem is None:
                elem = root.find(f".//{{*}}{tag_name}")
            return elem.text if elem is not None else default
        
        # Parse duration strings (PT60S -> 60)
        def parse_duration(duration_str: str) -> int:
            """Parse ISO 8601 duration string to seconds."""
            if not duration_str:
                return 0
            # Simple parser for PT<seconds>S format
            if duration_str.startswith("PT") and duration_str.endswith("S"):
                return int(duration_str[2:-1])
            return 0
        
        # Parse boolean strings
        def parse_bool(value_str: str, default: bool = False) -> bool:
            """Parse boolean string."""
            if value_str is None:
                return default
            return value_str.lower() in ('true', '1', 'yes')
        
        # Build properties
        props_dict = {}
        
        max_size = get_text("MaxSizeInMegabytes")
        if max_size:
            props_dict["max_size_in_megabytes"] = int(max_size)
        
        ttl = get_text("DefaultMessageTimeToLive")
        if ttl:
            props_dict["default_message_time_to_live"] = parse_duration(ttl)
        
        lock_duration = get_text("LockDuration")
        if lock_duration:
            props_dict["lock_duration"] = parse_duration(lock_duration)
        
        requires_session = get_text("RequiresSession")
        if requires_session:
            props_dict["requires_session"] = parse_bool(requires_session)
        
        requires_dup_detection = get_text("RequiresDuplicateDetection")
        if requires_dup_detection:
            props_dict["requires_duplicate_detection"] = parse_bool(requires_dup_detection)
        
        enable_dead_letter = get_text("EnableDeadLetteringOnMessageExpiration")
        if enable_dead_letter:
            props_dict["enable_dead_lettering_on_message_expiration"] = parse_bool(enable_dead_letter)
        
        enable_batched = get_text("EnableBatchedOperations")
        if enable_batched:
            props_dict["enable_batched_operations"] = parse_bool(enable_batched)
        
        max_delivery = get_text("MaxDeliveryCount")
        if max_delivery:
            props_dict["max_delivery_count"] = int(max_delivery)
        
        return QueueProperties(**props_dict)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_format_error_response("InvalidRequest", f"Invalid XML body: {str(e)}"),
        )


def _queue_to_xml(queue) -> str:
    """
    Convert queue description to XML.
    
    Args:
        queue: QueueDescription object
        
    Returns:
        XML string
    """
    # Build XML response
    root = ET.Element("QueueDescription", {
        "xmlns": "http://schemas.microsoft.com/netservices/2010/10/servicebus/connect",
        "xmlns:i": "http://www.w3.org/2001/XMLSchema-instance",
    })
    
    # Add queue name
    ET.SubElement(root, "QueueName").text = queue.name
    
    # Add properties
    ET.SubElement(root, "MaxSizeInMegabytes").text = str(queue.properties.max_size_in_megabytes)
    ET.SubElement(root, "DefaultMessageTimeToLive").text = f"PT{queue.properties.default_message_time_to_live}S"
    ET.SubElement(root, "LockDuration").text = f"PT{queue.properties.lock_duration}S"
    ET.SubElement(root, "RequiresSession").text = str(queue.properties.requires_session).lower()
    ET.SubElement(root, "RequiresDuplicateDetection").text = str(queue.properties.requires_duplicate_detection).lower()
    ET.SubElement(root, "EnableDeadLetteringOnMessageExpiration").text = str(queue.properties.enable_dead_lettering_on_message_expiration).lower()
    ET.SubElement(root, "EnableBatchedOperations").text = str(queue.properties.enable_batched_operations).lower()
    ET.SubElement(root, "MaxDeliveryCount").text = str(queue.properties.max_delivery_count)
    
    # Add runtime info
    ET.SubElement(root, "MessageCount").text = str(queue.runtime_info.message_count)
    ET.SubElement(root, "ActiveMessageCount").text = str(queue.runtime_info.active_message_count)
    ET.SubElement(root, "DeadLetterMessageCount").text = str(queue.runtime_info.dead_letter_message_count)
    ET.SubElement(root, "ScheduledMessageCount").text = str(queue.runtime_info.scheduled_message_count)
    ET.SubElement(root, "SizeInBytes").text = str(queue.runtime_info.size_in_bytes)
    
    # Add timestamps
    ET.SubElement(root, "CreatedAt").text = queue.created_at.isoformat()
    ET.SubElement(root, "UpdatedAt").text = queue.updated_at.isoformat()
    
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode")


@router.put(
    "/{namespace}/{queue_name}",
    summary="Create or Update Service Bus Queue",
)
async def create_or_update_queue(
    namespace: str,
    queue_name: str,
    request: Request,
) -> Response:
    """
    Create a new Service Bus queue or update an existing one.
    
    Azure Management API: PUT https://{namespace}.servicebus.windows.net/{queue}
    
    Args:
        namespace: Service Bus namespace
        queue_name: Queue name
        request: FastAPI request containing XML body
        
    Returns:
        201 Created with queue description in XML (new queue)
        200 OK with queue description in XML (updated queue)
        
    Raises:
        400 Bad Request: Invalid queue name or properties
        507 Insufficient Storage: Quota exceeded
    """
    try:
        # Check if queue exists
        try:
            existing_queue = await backend.get_queue(queue_name)
            is_update = True
        except QueueNotFoundError:
            is_update = False
        
        # Parse request body if provided
        body = await request.body()
        properties = None
        
        if body:
            xml_content = body.decode('utf-8')
            properties = _parse_queue_properties_from_xml(xml_content)
        
        if is_update:
            # Update existing queue
            if properties:
                queue = await backend.update_queue(queue_name, properties)
            else:
                queue = existing_queue
            status_code = status.HTTP_200_OK
        else:
            # Create new queue
            queue = await backend.create_queue(queue_name, properties)
            status_code = status.HTTP_201_CREATED
        
        # Build XML response
        xml_content = _queue_to_xml(queue)
        
        return Response(
            content=xml_content,
            media_type="application/xml",
            status_code=status_code,
            headers={
                'Content-Type': 'application/xml',
            },
        )
        
    except InvalidQueueNameError:
        # Let exception handler convert to JSON error response  
        raise
    except QuotaExceededError:
        # Let exception handler convert to JSON error response
        raise
    except QueueAlreadyExistsError:
        # Let exception handler convert to JSON error response
        raise


@router.get(
    "/{namespace}/$Resources/Queues",
    status_code=status.HTTP_200_OK,
    summary="List Service Bus Queues",
)
async def list_queues(
    namespace: str,
    skip: int = Query(default=0, ge=0, alias="$skip"),
    top: int = Query(default=100, ge=1, le=1000, alias="$top"),
) -> Response:
    """
    List all Service Bus queues in the namespace.
    
    Azure Management API: GET https://{namespace}.servicebus.windows.net/$Resources/Queues
    
    Args:
        namespace: Service Bus namespace
        skip: Number of queues to skip (pagination)
        top: Maximum number of queues to return
        
    Returns:
        200 OK with queue list in XML
    """
    queues = await backend.list_queues(skip=skip, top=top)
    
    # Build XML response (ATOM feed format)
    root = ET.Element("feed", {
        "xmlns": "http://www.w3.org/2005/Atom",
    })
    
    ET.SubElement(root, "title", {"type": "text"}).text = "Queues"
    ET.SubElement(root, "id").text = f"https://{namespace}.servicebus.windows.net/$Resources/Queues"
    ET.SubElement(root, "updated").text = datetime.now(timezone.utc).isoformat()
    
    for queue in queues:
        entry = ET.SubElement(root, "entry")
        ET.SubElement(entry, "id").text = f"https://{namespace}.servicebus.windows.net/{queue.name}"
        ET.SubElement(entry, "title", {"type": "text"}).text = queue.name
        ET.SubElement(entry, "published").text = queue.created_at.isoformat()
        ET.SubElement(entry, "updated").text = queue.updated_at.isoformat()
        
        # Add content with queue description
        content = ET.SubElement(entry, "content", {"type": "application/xml"})
        # Parse queue XML and append to content
        queue_xml = _queue_to_xml(queue)
        queue_elem = ET.fromstring(queue_xml)
        content.append(queue_elem)
    
    xml_content = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode")
    
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={
            'Content-Type': 'application/xml',
        },
    )


@router.get(
    "/{namespace}/{queue_name}",
    status_code=status.HTTP_200_OK,
    summary="Get Service Bus Queue",
)
async def get_queue(
    namespace: str,
    queue_name: str,
) -> Response:
    """
    Get Service Bus queue description and runtime properties.
    
    Azure Management API: GET https://{namespace}.servicebus.windows.net/{queue}
    
    Args:
        namespace: Service Bus namespace
        queue_name: Queue name
        
    Returns:
        200 OK with queue description in XML
        
    Raises:
        404 Not Found: Queue not found
    """
    try:
        queue = await backend.get_queue(queue_name)
        
        # Build XML response
        xml_content = _queue_to_xml(queue)
        
        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={
                'Content-Type': 'application/xml',
            },
        )
        
    except QueueNotFoundError:
        # Let exception handler convert to JSON error response
        raise


@router.delete(
    "/{namespace}/{queue_name}",
    status_code=status.HTTP_200_OK,
    summary="Delete Service Bus Queue",
)
async def delete_queue(
    namespace: str,
    queue_name: str,
) -> Response:
    """
    Delete a Service Bus queue and all its messages.
    
    Azure Management API: DELETE https://{namespace}.servicebus.windows.net/{queue}
    
    Args:
        namespace: Service Bus namespace
        queue_name: Queue name
        
    Returns:
        200 OK on success
        
    Raises:
        404 Not Found: Queue not found
    """
    try:
        await backend.delete_queue(queue_name)
        
        return Response(
            status_code=status.HTTP_200_OK,
            headers={
                'Content-Type': 'application/xml',
            },
        )
        
    except QueueNotFoundError:
        # Let exception handler convert to JSON error response
        raise


# Message Operations

@router.post("/{namespace}/{queue_name}/messages")
async def send_message(
    namespace: str,
    queue_name: str,
    request: SendMessageRequest,
) -> dict:
    """
    Send a message to a Service Bus queue.
    
    Args:
        namespace: Service Bus namespace
        queue_name: Queue name
        request: Message send request
        
    Returns:
        Message details with MessageId
        
    Raises:
        404 Not Found: Queue not found
    """
    try:
        message = await backend.send_message(queue_name, request)
        
        return message.model_dump(mode="json", by_alias=True)
        
    except QueueNotFoundError:
        # Let exception handler convert to JSON error response
        raise


@router.post("/{namespace}/{queue_name}/messages/head")
async def receive_message(
    queue_name: str,
    mode: str = Query(default=ReceiveMode.PEEK_LOCK, description="Receive mode: PeekLock or ReceiveAndDelete"),
) -> Optional[dict]:
    """
    Receive a message from a Service Bus queue.
    
    Args:
        queue_name: Queue name
        mode: Receive mode (PeekLock or ReceiveAndDelete)
        
    Returns:
        Message if available, None otherwise
        
    Raises:
        QueueNotFoundError: If queue not found
    """
    try:
        message = await backend.receive_message(queue_name, mode)
        
        if message is None:
            return None
        
        return message.model_dump(mode="json", by_alias=True)
        
    except QueueNotFoundError:
        raise


@router.delete("/{namespace}/{queue_name}/messages/{message_id}/{lock_token}")
async def complete_message(
    namespace: str,
    queue_name: str,
    message_id: str,
    lock_token: str,
):
    """
    Complete a message and remove it from the queue.
    
    Args:
        namespace: Service Bus namespace
        queue_name: Queue name
        message_id: Message ID
        lock_token: Lock token
        
    Returns:
        200 OK on success
        
    Raises:
        404 Not Found: Queue or message not found
        410 Gone: Message lock lost
    """
    try:
        await backend.complete_message(queue_name, message_id, lock_token)
        
        return Response(status_code=status.HTTP_200_OK)
        
    except QueueNotFoundError:
        # Let exception handler convert to JSON error response
        raise
    except MessageNotFoundError:
        # Let exception handler convert to JSON error response
        raise
    except MessageLockLostError:
        # Let exception handler convert to JSON error response
        raise


@router.put("/{namespace}/{queue_name}/messages/{message_id}/{lock_token}/abandon")
async def abandon_message(
    namespace: str,
    queue_name: str,
    message_id: str,
    lock_token: str,
):
    """
    Abandon a message and return it to the queue.
    
    Args:
        namespace: Service Bus namespace
        queue_name: Queue name
        message_id: Message ID
        lock_token: Lock token
        
    Returns:
        200 OK on success
        
    Raises:
        404 Not Found: Queue or message not found
        410 Gone: Message lock lost
    """
    try:
        await backend.abandon_message(queue_name, message_id, lock_token)
        
        return Response(status_code=status.HTTP_200_OK)
        
    except QueueNotFoundError:
        # Let exception handler convert to JSON error response
        raise
    except MessageNotFoundError:
        # Let exception handler convert to JSON error response
        raise
    except MessageLockLostError:
        # Let exception handler convert to JSON error response
        raise


@router.put("/{namespace}/{queue_name}/messages/{message_id}/{lock_token}/deadletter")
async def dead_letter_message(
    namespace: str,
    queue_name: str,
    message_id: str,
    lock_token: str,
    reason: Optional[str] = Query(default=None, description="Reason for dead-lettering"),
    description: Optional[str] = Query(default=None, description="Description"),
):
    """
    Move a message to the dead-letter queue.
    
    Args:
        namespace: Service Bus namespace
        queue_name: Queue name
        message_id: Message ID
        lock_token: Lock token
        reason: Reason for dead-lettering
        description: Description
        
    Returns:
        200 OK on success
        
    Raises:
        404 Not Found: Queue or message not found
        410 Gone: Message lock lost
    """
    try:
        await backend.dead_letter_message(queue_name, message_id, lock_token, reason, description)
        
        return Response(status_code=status.HTTP_200_OK)
        
    except QueueNotFoundError:
        # Let exception handler convert to JSON error response
        raise
    except MessageNotFoundError:
        # Let exception handler convert to JSON error response
        raise
    except MessageLockLostError:
        # Let exception handler convert to JSON error response
        raise


@router.post("/{namespace}/{queue_name}/messages/{message_id}/{lock_token}/renewlock")
async def renew_lock(
    namespace: str,
    queue_name: str,
    message_id: str,
    lock_token: str,
):
    """
    Renew the lock on a message.
    
    Args:
        namespace: Service Bus namespace
        queue_name: Queue name
        message_id: Message ID
        lock_token: Lock token
        
    Returns:
        New LockedUntilUtc timestamp
        
    Raises:
        404 Not Found: Queue or message not found
        410 Gone: Message lock lost
    """
    try:
        locked_until = await backend.renew_lock(queue_name, message_id, lock_token)
        
        return {
            "LockedUntilUtc": locked_until.isoformat(),
        }
        
    except QueueNotFoundError:
        # Let exception handler convert to JSON error response
        raise
    except MessageNotFoundError:
        # Let exception handler convert to JSON error response
        raise
    except MessageLockLostError:
        # Let exception handler convert to JSON error response
        raise


# ========== Topic Management Endpoints ==========

@router.put("/{namespace}/topics/{topic_name}")
async def create_or_update_topic(
    namespace: str,
    topic_name: str,
    request: Request,
):
    """Create or update a Service Bus topic."""
    try:
        body = await request.body()
        root = ET.fromstring(body.decode("utf-8"))
        
        properties_dict = {}
        ns = {"": "http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"}
        desc_elem = root.find(".//TopicDescription", ns)
        if desc_elem is None:
            desc_elem = root
        
        # Map PascalCase XML properties to snake_case model properties
        property_map = {
            "MaxSizeInMegabytes": "max_size_in_megabytes",
            "DefaultMessageTimeToLive": "default_message_time_to_live",
            "RequiresDuplicateDetection": "requires_duplicate_detection",
            "EnableBatchedOperations": "enable_batched_operations",
            "SupportOrdering": "support_ordering",
        }
        
        for xml_name, model_name in property_map.items():
            elem = desc_elem.find(xml_name, ns)
            if elem is not None and elem.text:
                value = elem.text
                # Convert types
                if model_name == "max_size_in_megabytes":
                    properties_dict[model_name] = int(value)
                elif model_name == "default_message_time_to_live":
                    # Parse ISO 8601 duration to seconds
                    if value.startswith("P"):
                        properties_dict[model_name] = _parse_iso_duration(value)
                    else:
                        properties_dict[model_name] = int(value)
                elif model_name in ["requires_duplicate_detection", "enable_batched_operations", "support_ordering"]:
                    properties_dict[model_name] = value.lower() == "true"
                else:
                    properties_dict[model_name] = value
        
        properties = TopicProperties(**properties_dict) if properties_dict else TopicProperties()
        
        try:
            await backend.get_topic(topic_name)
            topic = await backend.update_topic(topic_name, properties)
            status_code = status.HTTP_200_OK
        except TopicNotFoundError:
            topic = await backend.create_topic(topic_name, properties)
            status_code = status.HTTP_201_CREATED
        
        response_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <id>https://{namespace}.servicebus.windows.net/topics/{topic_name}</id>
    <title type="text">{topic_name}</title>
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>{topic.properties.max_size_in_megabytes}</MaxSizeInMegabytes>
            <SubscriptionCount>{topic.runtime_info.subscription_count}</SubscriptionCount>
        </TopicDescription>
    </content>
</entry>"""
        
        return Response(content=response_xml, media_type="application/xml", status_code=status_code)
        
    except TopicAlreadyExistsError:
        # Let exception handler convert to JSON error response
        raise
    except QuotaExceededError:
        # Let exception handler convert to JSON error response
        raise


@router.get("/{namespace}/topics")
async def list_topics(namespace: str):
    """List all Service Bus topics."""
    topics = await backend.list_topics()
    
    feed = '<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title type="text">Topics</title>'
    
    for topic in topics:
        feed += f'<entry><id>https://{namespace}.servicebus.windows.net/topics/{topic.name}</id><title type="text">{topic.name}</title></entry>'
    
    feed += '</feed>'
    return Response(content=feed, media_type="application/xml")


@router.get("/{namespace}/topics/{topic_name}")
async def get_topic(namespace: str, topic_name: str):
    """Get details of a specific topic."""
    try:
        topic = await backend.get_topic(topic_name)
        
        response_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>{topic.properties.max_size_in_megabytes}</MaxSizeInMegabytes>
            <SubscriptionCount>{topic.runtime_info.subscription_count}</SubscriptionCount>
        </TopicDescription>
    </content>
</entry>"""
        
        return Response(content=response_xml, media_type="application/xml")
        
    except TopicNotFoundError:
        # Let exception handler convert to JSON error response
        raise


@router.delete("/{namespace}/topics/{topic_name}")
async def delete_topic(namespace: str, topic_name: str):
    """Delete a Service Bus topic."""
    try:
        await backend.delete_topic(topic_name)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except TopicNotFoundError:
        # Let exception handler convert to JSON error response
        raise


# ========== Subscription Management Endpoints ==========

@router.put("/{namespace}/topics/{topic_name}/subscriptions/{subscription_name}")
async def create_or_update_subscription(namespace: str, topic_name: str, subscription_name: str, request: Request):
    """Create or update a subscription."""
    try:
        body = await request.body()
        root = ET.fromstring(body.decode("utf-8"))
        
        properties_dict = {}
        ns = {"": "http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"}
        desc_elem = root.find(".//SubscriptionDescription", ns) or root
        
        # Map PascalCase XML properties to snake_case model properties
        property_map = {
            "LockDuration": "lock_duration",
            "MaxDeliveryCount": "max_delivery_count",
            "RequiresSession": "requires_session",
            "DefaultMessageTimeToLive": "default_message_time_to_live",
            "DeadLetteringOnMessageExpiration": "dead_lettering_on_message_expiration",
        }
        
        for xml_name, model_name in property_map.items():
            elem = desc_elem.find(xml_name, ns)
            if elem is not None and elem.text:
                value = elem.text
                # Convert types
                if model_name == "lock_duration":
                    # Parse ISO 8601 duration to seconds
                    if value.startswith("PT"):
                        properties_dict[model_name] = _parse_iso_duration(value)
                    else:
                        properties_dict[model_name] = int(value)
                elif model_name == "max_delivery_count":
                    properties_dict[model_name] = int(value)
                elif model_name == "default_message_time_to_live":
                    # Parse ISO 8601 duration to seconds
                    if value.startswith("P"):
                        properties_dict[model_name] = _parse_iso_duration(value)
                    else:
                        properties_dict[model_name] = int(value)
                elif model_name in ["requires_session", "dead_lettering_on_message_expiration"]:
                    properties_dict[model_name] = value.lower() == "true"
                else:
                    properties_dict[model_name] = value
        
        properties = SubscriptionProperties(**properties_dict) if properties_dict else SubscriptionProperties()
        
        try:
            await backend.get_subscription(topic_name, subscription_name)
            subscription = await backend.update_subscription(topic_name, subscription_name, properties)
            status_code = status.HTTP_200_OK
        except SubscriptionNotFoundError:
            subscription = await backend.create_subscription(topic_name, subscription_name, properties)
            status_code = status.HTTP_201_CREATED
        
        response_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>{subscription.properties.lock_duration}</LockDuration>
            <MessageCount>{subscription.runtime_info.message_count}</MessageCount>
        </SubscriptionDescription>
    </content>
</entry>"""
        
        return Response(content=response_xml, media_type="application/xml", status_code=status_code)
        
    except TopicNotFoundError:
        # Let exception handler convert to JSON error response
        raise


@router.get("/{namespace}/topics/{topic_name}/subscriptions")
async def list_subscriptions(namespace: str, topic_name: str):
    """List all subscriptions for a topic."""
    try:
        subscriptions = await backend.list_subscriptions(topic_name)
        
        feed = '<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title type="text">Subscriptions</title>'
        for sub in subscriptions:
            feed += f'<entry><id>https://{namespace}.servicebus.windows.net/topics/{topic_name}/subscriptions/{sub.subscription_name}</id><title type="text">{sub.subscription_name}</title></entry>'
        feed += '</feed>'
        
        return Response(content=feed, media_type="application/xml")
    except TopicNotFoundError:
        # Let exception handler convert to JSON error response
        raise


@router.get("/{namespace}/topics/{topic_name}/subscriptions/{subscription_name}")
async def get_subscription(namespace: str, topic_name: str, subscription_name: str):
    """Get details of a specific subscription."""
    try:
        subscription = await backend.get_subscription(topic_name, subscription_name)
        
        response_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MessageCount>{subscription.runtime_info.message_count}</MessageCount>
        </SubscriptionDescription>
    </content>
</entry>"""
        
        return Response(content=response_xml, media_type="application/xml")
    except SubscriptionNotFoundError:
        # Let exception handler convert to JSON error response
        raise


@router.delete("/{namespace}/topics/{topic_name}/subscriptions/{subscription_name}")
async def delete_subscription(namespace: str, topic_name: str, subscription_name: str):
    """Delete a subscription."""
    try:
        await backend.delete_subscription(topic_name, subscription_name)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SubscriptionNotFoundError:
        # Let exception handler convert to JSON error response
        raise


# ========== Topic Message Endpoints ==========

@router.post("/{namespace}/topics/{topic_name}/messages")
async def send_to_topic(namespace: str, topic_name: str, request: SendMessageRequest):
    """Send a message to a topic (fan-out to matching subscriptions)."""
    try:
        message = await backend.send_to_topic(topic_name, request)
        return Response(status_code=status.HTTP_201_CREATED, headers={"BrokerProperties": f'{{"MessageId":"{message.message_id}"}}'})
    except TopicNotFoundError:
        # Let exception handler convert to JSON error response
        raise


@router.post("/{namespace}/topics/{topic_name}/subscriptions/{subscription_name}/messages/head")
async def receive_from_subscription(
    topic_name: str, 
    subscription_name: str,
    num_of_messages: int = Query(default=1, alias="numofmessages"),
    timeout: int = Query(default=60),
    mode: str = Query(default="peeklock"),
):
    """
    Receive messages from a subscription.
    
    Args:
        topic_name: Name of the topic
        subscription_name: Name of the subscription
        num_of_messages: Maximum number of messages to receive
        timeout: Receive timeout in seconds
        mode: Receive mode ('peeklock' or 'receiveanddelete')
        
    Returns:
        List of messages or 204 No Content if no messages available
        
    Raises:
        SubscriptionNotFoundError: If subscription doesn't exist
    """
    try:
        receive_mode = (
            ReceiveMode.PEEK_LOCK 
            if mode.lower() == "peeklock" 
            else ReceiveMode.RECEIVE_AND_DELETE
        )
        
        messages = await backend.receive_from_subscription(
            topic_name, 
            subscription_name, 
            receive_mode, 
            num_of_messages
        )
        
        if not messages:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        
        return [msg.model_dump(mode="json", by_alias=True) for msg in messages]
    except SubscriptionNotFoundError:
        raise


@router.delete("/{namespace}/topics/{topic_name}/subscriptions/{subscription_name}/messages/{message_id}/{lock_token}")
async def complete_subscription_message(
    topic_name: str, 
    subscription_name: str, 
    lock_token: str
):
    """
    Complete a subscription message (remove from queue).
    
    Args:
        topic_name: Name of the topic
        subscription_name: Name of the subscription
        lock_token: Lock token for the message
        
    Returns:
        200 OK response
        
    Raises:
        SubscriptionNotFoundError: If subscription doesn't exist
        MessageLockLostError: If message lock has expired
    """
    try:
        await backend.complete_subscription_message(
            topic_name, 
            subscription_name, 
            lock_token
        )
        return Response(status_code=status.HTTP_200_OK)
    except (SubscriptionNotFoundError, MessageLockLostError):
        raise
