"""Azure-consistent error response formatting for LocalZure Gateway.

This module provides error response formatting that matches Azure's error
structure and format for compatibility with Azure SDKs.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, Any
from xml.etree import ElementTree as ET
import logging

logger = logging.getLogger(__name__)


class ErrorFormat(str, Enum):
    """Error response format."""

    JSON = "json"  # For most Azure services
    XML = "xml"  # For Storage services


class ServiceType(str, Enum):
    """Azure service types for error formatting."""

    STORAGE = "storage"  # Blob, Queue, Table, File
    SERVICE_BUS = "servicebus"
    KEY_VAULT = "keyvault"
    COSMOS_DB = "cosmosdb"
    GENERIC = "generic"


# Common Azure error codes with HTTP status mappings
ERROR_CODE_MAPPINGS: Dict[str, int] = {
    # Authentication errors (401)
    "AuthenticationFailed": 401,
    "InvalidAuthenticationInfo": 401,
    "MissingRequiredHeader": 401,
    # Authorization errors (403)
    "AuthorizationFailed": 403,
    "InsufficientAccountPermissions": 403,
    "AccountIsDisabled": 403,
    # Not found errors (404)
    "ResourceNotFound": 404,
    "BlobNotFound": 404,
    "ContainerNotFound": 404,
    "QueueNotFound": 404,
    "TableNotFound": 404,
    "EntityNotFound": 404,
    # Bad request errors (400)
    "InvalidResourceName": 400,
    "InvalidUri": 400,
    "InvalidInput": 400,
    "InvalidQueryParameter": 400,
    "InvalidHeaderValue": 400,
    "MissingRequiredQueryParameter": 400,
    "OutOfRangeInput": 400,
    # Conflict errors (409)
    "ResourceAlreadyExists": 409,
    "ContainerAlreadyExists": 409,
    "BlobAlreadyExists": 409,
    "QueueAlreadyExists": 409,
    "TableAlreadyExists": 409,
    "EntityAlreadyExists": 409,
    # Precondition errors (412)
    "ConditionNotMet": 412,
    "TargetConditionNotMet": 412,
    # Rate limiting (429)
    "TooManyRequests": 429,
    "OperationTimedOut": 408,
    # Server errors (500+)
    "InternalError": 500,
    "ServerBusy": 503,
    "ServiceUnavailable": 503,
}


@dataclass
class ErrorContext:
    """Context for error response generation."""

    error_code: str
    message: str
    service_type: ServiceType = ServiceType.GENERIC
    status_code: Optional[int] = None
    request_id: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Generate defaults."""
        if self.status_code is None:
            self.status_code = ERROR_CODE_MAPPINGS.get(self.error_code, 500)
        if self.request_id is None:
            self.request_id = generate_request_id()


@dataclass
class AzureError:
    """Represents an Azure-style error response."""

    error_code: str
    message: str
    status_code: int
    request_id: str
    headers: Dict[str, str]
    body: str
    content_type: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for FastAPI response."""
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "content_type": self.content_type,
        }


def generate_request_id() -> str:
    """Generate Azure-style request ID.

    Returns:
        Request ID in UUID format
    """
    return str(uuid.uuid4())


def generate_timestamp_request_id() -> str:
    """Generate Azure-style timestamp-based request ID.

    Returns:
        Request ID in timestamp format (e.g., "20251204T103045.123Z")
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%S.%f")[:-3] + "Z"


def determine_error_format(
    service_type: ServiceType, accept_header: Optional[str] = None
) -> ErrorFormat:
    """Determine error format based on service type and Accept header.

    Args:
        service_type: Type of Azure service
        accept_header: HTTP Accept header value

    Returns:
        Error format to use (JSON or XML)
    """
    # Storage services default to XML
    if service_type == ServiceType.STORAGE:
        # Check if client explicitly wants JSON
        if accept_header and "application/json" in accept_header.lower():
            return ErrorFormat.JSON
        return ErrorFormat.XML

    # All other services use JSON
    return ErrorFormat.JSON


def format_error_xml(context: ErrorContext) -> str:
    """Format error as XML for Storage services.

    Args:
        context: Error context

    Returns:
        XML-formatted error string
    """
    # Create XML structure matching Azure Storage format
    error = ET.Element("Error")

    code = ET.SubElement(error, "Code")
    code.text = context.error_code

    message = ET.SubElement(error, "Message")
    message.text = context.message

    # Add additional info if present
    if context.additional_info:
        for key, value in context.additional_info.items():
            elem = ET.SubElement(error, key)
            elem.text = str(value)

    # Convert to string with XML declaration
    xml_str = ET.tostring(error, encoding="utf-8", method="xml")
    return b'<?xml version="1.0" encoding="utf-8"?>\n' + xml_str


def format_error_json(context: ErrorContext) -> str:
    """Format error as JSON for non-Storage services.

    Args:
        context: Error context

    Returns:
        JSON-formatted error string
    """
    error_body: Dict[str, Any] = {
        "error": {"code": context.error_code, "message": context.message}
    }

    # Add additional info to error object
    if context.additional_info:
        error_body["error"].update(context.additional_info)

    return json.dumps(error_body, indent=2)


def create_error_headers(
    error_code: str, request_id: str, content_type: str
) -> Dict[str, str]:
    """Create error response headers.

    Args:
        error_code: Azure error code
        request_id: Request ID
        content_type: Response content type

    Returns:
        Dictionary of headers
    """
    headers = {
        "x-ms-request-id": request_id,
        "x-ms-error-code": error_code,
        "Content-Type": content_type,
        "Date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
    }
    return headers


def create_error_response(
    context: ErrorContext,
    *,
    error_format: Optional[ErrorFormat] = None,
    accept_header: Optional[str] = None,
) -> AzureError:
    """Create Azure-consistent error response.

    Args:
        context: Error context with code, message, and metadata
        error_format: Override error format (defaults based on service type)
        accept_header: HTTP Accept header for content negotiation

    Returns:
        AzureError object with formatted response
    """
    # Determine format
    if error_format is None:
        error_format = determine_error_format(context.service_type, accept_header)

    # Format error body
    if error_format == ErrorFormat.XML:
        body_bytes = format_error_xml(context)
        body = body_bytes.decode("utf-8")
        content_type = "application/xml"
    else:
        body = format_error_json(context)
        content_type = "application/json"

    # Create headers
    headers = create_error_headers(context.error_code, context.request_id, content_type)

    logger.debug(
        f"Created error response: {context.error_code} "
        f"(status={context.status_code}, format={error_format.value})"
    )

    return AzureError(
        error_code=context.error_code,
        message=context.message,
        status_code=context.status_code,
        request_id=context.request_id,
        headers=headers,
        body=body,
        content_type=content_type,
    )


def map_error_code_to_status(error_code: str, default: int = 500) -> int:
    """Map Azure error code to HTTP status code.

    Args:
        error_code: Azure error code
        default: Default status code if not mapped

    Returns:
        HTTP status code
    """
    return ERROR_CODE_MAPPINGS.get(error_code, default)


def create_storage_error(
    error_code: str,
    message: str,
    *,
    request_id: Optional[str] = None,
    accept_header: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None,
) -> AzureError:
    """Create Storage service error response.

    Args:
        error_code: Azure Storage error code
        message: Error message
        request_id: Optional request ID (generated if not provided)
        accept_header: HTTP Accept header
        additional_info: Additional error details

    Returns:
        AzureError formatted for Storage
    """
    context = ErrorContext(
        error_code=error_code,
        message=message,
        service_type=ServiceType.STORAGE,
        request_id=request_id,
        additional_info=additional_info,
    )
    return create_error_response(context, accept_header=accept_header)


def create_service_bus_error(
    error_code: str,
    message: str,
    *,
    request_id: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None,
) -> AzureError:
    """Create Service Bus error response.

    Args:
        error_code: Azure Service Bus error code
        message: Error message
        request_id: Optional request ID (generated if not provided)
        additional_info: Additional error details

    Returns:
        AzureError formatted for Service Bus
    """
    context = ErrorContext(
        error_code=error_code,
        message=message,
        service_type=ServiceType.SERVICE_BUS,
        request_id=request_id,
        additional_info=additional_info,
    )
    return create_error_response(context)


def create_key_vault_error(
    error_code: str,
    message: str,
    *,
    request_id: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None,
) -> AzureError:
    """Create Key Vault error response.

    Args:
        error_code: Azure Key Vault error code
        message: Error message
        request_id: Optional request ID (generated if not provided)
        additional_info: Additional error details

    Returns:
        AzureError formatted for Key Vault
    """
    context = ErrorContext(
        error_code=error_code,
        message=message,
        service_type=ServiceType.KEY_VAULT,
        request_id=request_id,
        additional_info=additional_info,
    )
    return create_error_response(context)


def create_cosmos_db_error(
    error_code: str,
    message: str,
    *,
    request_id: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None,
) -> AzureError:
    """Create Cosmos DB error response.

    Args:
        error_code: Azure Cosmos DB error code
        message: Error message
        request_id: Optional request ID (generated if not provided)
        additional_info: Additional error details

    Returns:
        AzureError formatted for Cosmos DB
    """
    context = ErrorContext(
        error_code=error_code,
        message=message,
        service_type=ServiceType.COSMOS_DB,
        request_id=request_id,
        additional_info=additional_info,
    )
    return create_error_response(context)


def create_generic_error(
    error_code: str,
    message: str,
    status_code: int = 500,
    *,
    request_id: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None,
) -> AzureError:
    """Create generic Azure error response.

    Args:
        error_code: Error code
        message: Error message
        status_code: HTTP status code
        request_id: Optional request ID (generated if not provided)
        additional_info: Additional error details

    Returns:
        AzureError formatted generically
    """
    context = ErrorContext(
        error_code=error_code,
        message=message,
        service_type=ServiceType.GENERIC,
        status_code=status_code,
        request_id=request_id,
        additional_info=additional_info,
    )
    return create_error_response(context)
