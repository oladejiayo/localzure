"""Protocol routing for LocalZure Gateway.

This module provides protocol detection and routing for different Azure
communication protocols including HTTP, WebSocket, and AMQP.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)


class ProtocolType(str, Enum):
    """Supported protocol types."""

    HTTP = "http"
    HTTP2 = "http2"
    WEBSOCKET = "websocket"
    AMQP = "amqp"
    UNKNOWN = "unknown"


class ProtocolError(Exception):
    """Base exception for protocol-related errors."""

    def __init__(
        self, message: str, protocol: ProtocolType, status_code: int = 400
    ):
        """Initialize protocol error.

        Args:
            message: Human-readable error message
            protocol: Protocol type that generated the error
            status_code: HTTP-style status code (for compatibility)
        """
        super().__init__(message)
        self.message = message
        self.protocol = protocol
        self.status_code = status_code


@dataclass
class ConnectionState:
    """State information for a protocol connection."""

    protocol: ProtocolType
    connection_id: str
    metadata: Dict[str, Any]
    is_active: bool = True

    def __post_init__(self):
        """Ensure metadata is initialized."""
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ProtocolContext:
    """Context for protocol request handling."""

    protocol: ProtocolType
    headers: Dict[str, str]
    metadata: Dict[str, Any]
    connection_state: Optional[ConnectionState] = None

    def __post_init__(self):
        """Ensure dictionaries are initialized."""
        if self.headers is None:
            self.headers = {}
        if self.metadata is None:
            self.metadata = {}


class ProtocolDetector:
    """Detects protocol type from connection data."""

    AMQP_PREFACE = b"AMQP\x00\x01\x00\x00"

    @staticmethod
    def detect_from_headers(headers: Dict[str, str]) -> ProtocolType:
        """Detect protocol from HTTP headers.

        Args:
            headers: Request headers (case-insensitive keys)

        Returns:
            Detected protocol type
        """
        # Normalize header keys to lowercase for case-insensitive comparison
        normalized_headers = {k.lower(): v for k, v in headers.items()}

        # Check for WebSocket upgrade
        upgrade = normalized_headers.get("upgrade", "").lower()
        connection = normalized_headers.get("connection", "").lower()

        if upgrade == "websocket" and "upgrade" in connection:
            return ProtocolType.WEBSOCKET

        # Check HTTP version
        # HTTP/2 is indicated by the protocol negotiation (ALPN)
        # For now, we default to HTTP/1.1 unless explicitly marked
        if "http2-settings" in normalized_headers:
            return ProtocolType.HTTP2

        # Default to HTTP for standard headers
        if normalized_headers:
            return ProtocolType.HTTP

        return ProtocolType.UNKNOWN

    @staticmethod
    async def detect_from_data(
        data: bytes, timeout: float = 1.0  # pylint: disable=unused-argument
    ) -> ProtocolType:
        """Detect protocol from initial connection data.

        Args:
            data: Initial bytes from connection
            timeout: Detection timeout in seconds (reserved for future use)

        Returns:
            Detected protocol type
        """
        # Check for AMQP preface
        if data.startswith(ProtocolDetector.AMQP_PREFACE):
            return ProtocolType.AMQP

        # Check for HTTP request line
        if data.startswith((b"GET ", b"POST ", b"PUT ", b"DELETE ", b"HEAD ", b"PATCH ", b"OPTIONS ")):
            return ProtocolType.HTTP

        return ProtocolType.UNKNOWN


class ProtocolRouter:
    """Routes requests to appropriate handlers based on protocol."""

    def __init__(self):
        """Initialize protocol router."""
        self._handlers: Dict[ProtocolType, Callable] = {}
        self._connections: Dict[str, ConnectionState] = {}
        self._connection_counter = 0

    def register_handler(
        self, protocol: ProtocolType, handler: Callable
    ) -> None:
        """Register a handler for a specific protocol.

        Args:
            protocol: Protocol type to handle
            handler: Async callable that handles requests for this protocol
        """
        self._handlers[protocol] = handler
        logger.info(f"Registered handler for protocol: {protocol}")

    def get_handler(self, protocol: ProtocolType) -> Optional[Callable]:
        """Get handler for a specific protocol.

        Args:
            protocol: Protocol type

        Returns:
            Handler callable or None if not registered
        """
        return self._handlers.get(protocol)

    def create_connection(
        self, protocol: ProtocolType, metadata: Optional[Dict[str, Any]] = None
    ) -> ConnectionState:
        """Create and track a new connection.

        Args:
            protocol: Protocol type for the connection
            metadata: Optional metadata to associate with connection

        Returns:
            ConnectionState object
        """
        self._connection_counter += 1
        connection_id = f"{protocol.value}-{self._connection_counter}"

        state = ConnectionState(
            protocol=protocol,
            connection_id=connection_id,
            metadata=metadata or {},
            is_active=True,
        )

        self._connections[connection_id] = state
        logger.debug(f"Created connection: {connection_id}")
        return state

    def get_connection(self, connection_id: str) -> Optional[ConnectionState]:
        """Get connection state by ID.

        Args:
            connection_id: Connection identifier

        Returns:
            ConnectionState or None if not found
        """
        return self._connections.get(connection_id)

    def close_connection(self, connection_id: str) -> bool:
        """Close and remove a connection.

        Args:
            connection_id: Connection identifier

        Returns:
            True if connection was closed, False if not found
        """
        state = self._connections.get(connection_id)
        if state:
            state.is_active = False
            del self._connections[connection_id]
            logger.debug(f"Closed connection: {connection_id}")
            return True
        return False

    def active_connections(self, protocol: Optional[ProtocolType] = None) -> int:
        """Get count of active connections.

        Args:
            protocol: Optional protocol filter

        Returns:
            Number of active connections
        """
        if protocol:
            return sum(
                1
                for conn in self._connections.values()
                if conn.protocol == protocol and conn.is_active
            )
        return len(self._connections)

    async def route_request(
        self,
        *,
        protocol: ProtocolType,
        headers: Dict[str, str],
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """Route a request to the appropriate protocol handler.

        Args:
            protocol: Detected protocol type
            headers: Request headers
            metadata: Additional protocol metadata
            **kwargs: Protocol-specific arguments

        Returns:
            Handler response

        Raises:
            ProtocolError: If no handler registered or handler fails
        """
        handler = self.get_handler(protocol)
        if not handler:
            raise ProtocolError(
                f"No handler registered for protocol: {protocol}",
                protocol=protocol,
                status_code=501,
            )

        # Create protocol context
        context = ProtocolContext(
            protocol=protocol,
            headers=headers,
            metadata=metadata or {},
        )

        try:
            # For stateful protocols, create connection tracking
            if protocol in (ProtocolType.WEBSOCKET, ProtocolType.AMQP):
                connection = self.create_connection(protocol, metadata)
                context.connection_state = connection

            # Call the handler
            result = await handler(context, **kwargs)

            return result

        except Exception as exc:
            logger.error(
                f"Error routing {protocol} request: {exc}", exc_info=True
            )
            raise ProtocolError(
                f"Protocol handler error: {str(exc)}",
                protocol=protocol,
                status_code=500,
            ) from exc


def format_protocol_error(error: ProtocolError) -> Dict[str, Any]:
    """Format protocol error for appropriate response.

    Args:
        error: Protocol error to format

    Returns:
        Error response dict with protocol-specific format
    """
    if error.protocol in (ProtocolType.HTTP, ProtocolType.HTTP2):
        # HTTP JSON error format
        return {
            "error": {
                "code": error.status_code,
                "message": error.message,
                "protocol": error.protocol.value,
            }
        }
    elif error.protocol == ProtocolType.WEBSOCKET:
        # WebSocket close frame data
        return {
            "close_code": 1008,  # Policy Violation
            "close_reason": error.message,
        }
    elif error.protocol == ProtocolType.AMQP:
        # AMQP error format
        return {
            "condition": "amqp:internal-error",
            "description": error.message,
        }
    else:
        # Generic error format
        return {"error": error.message}


async def http_handler_example(
    context: ProtocolContext, **kwargs  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    """Example HTTP request handler.

    This is a placeholder showing the handler interface.
    Real implementations would process HTTP requests appropriately.

    Args:
        context: Protocol context with headers and metadata
        **kwargs: Additional request data (method, path, body, etc.)

    Returns:
        Response dict
    """
    return {
        "status": 200,
        "body": {
            "message": "HTTP handler",
            "protocol": context.protocol.value,
        },
        "headers": context.headers,
    }


async def websocket_handler_example(
    context: ProtocolContext, **kwargs  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    """Example WebSocket upgrade handler.

    Args:
        context: Protocol context with connection state
        **kwargs: WebSocket-specific data

    Returns:
        Upgrade response or error
    """
    if context.connection_state:
        return {
            "status": "upgrade",
            "connection_id": context.connection_state.connection_id,
            "protocol": "websocket",
        }
    raise ProtocolError(
        "Failed to establish WebSocket connection",
        protocol=ProtocolType.WEBSOCKET,
        status_code=400,
    )


async def amqp_handler_example(
    context: ProtocolContext, **kwargs  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    """Example AMQP connection handler.

    Args:
        context: Protocol context with connection state
        **kwargs: AMQP-specific data

    Returns:
        Connection response
    """
    if context.connection_state:
        return {
            "status": "connected",
            "connection_id": context.connection_state.connection_id,
            "protocol": "amqp",
        }
    raise ProtocolError(
        "Failed to establish AMQP connection",
        protocol=ProtocolType.AMQP,
        status_code=400,
    )
