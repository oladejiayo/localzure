"""Tests for protocol routing."""

import pytest

from localzure.gateway.protocol_router import (
    ProtocolType,
    ProtocolError,
    ConnectionState,
    ProtocolContext,
    ProtocolDetector,
    ProtocolRouter,
    format_protocol_error,
    http_handler_example,
    websocket_handler_example,
    amqp_handler_example,
)


class TestProtocolType:
    """Test protocol type enum."""

    def test_protocol_types_exist(self):
        """Test all expected protocol types are defined."""
        assert ProtocolType.HTTP == "http"
        assert ProtocolType.HTTP2 == "http2"
        assert ProtocolType.WEBSOCKET == "websocket"
        assert ProtocolType.AMQP == "amqp"
        assert ProtocolType.UNKNOWN == "unknown"


class TestProtocolError:
    """Test protocol error class."""

    def test_error_initialization(self):
        """Test protocol error initializes with all fields."""
        error = ProtocolError(
            "Test error", protocol=ProtocolType.HTTP, status_code=400
        )

        assert error.message == "Test error"
        assert error.protocol == ProtocolType.HTTP
        assert error.status_code == 400
        assert str(error) == "Test error"

    def test_error_default_status_code(self):
        """Test protocol error uses default status code."""
        error = ProtocolError("Test error", protocol=ProtocolType.HTTP)

        assert error.status_code == 400

    def test_error_different_protocols(self):
        """Test errors for different protocol types."""
        http_error = ProtocolError("HTTP error", protocol=ProtocolType.HTTP)
        ws_error = ProtocolError("WS error", protocol=ProtocolType.WEBSOCKET)
        amqp_error = ProtocolError("AMQP error", protocol=ProtocolType.AMQP)

        assert http_error.protocol == ProtocolType.HTTP
        assert ws_error.protocol == ProtocolType.WEBSOCKET
        assert amqp_error.protocol == ProtocolType.AMQP


class TestConnectionState:
    """Test connection state management."""

    def test_connection_state_initialization(self):
        """Test connection state initializes correctly."""
        state = ConnectionState(
            protocol=ProtocolType.WEBSOCKET,
            connection_id="ws-123",
            metadata={"key": "value"},
        )

        assert state.protocol == ProtocolType.WEBSOCKET
        assert state.connection_id == "ws-123"
        assert state.metadata == {"key": "value"}
        assert state.is_active is True

    def test_connection_state_default_metadata(self):
        """Test connection state initializes metadata if None."""
        state = ConnectionState(
            protocol=ProtocolType.HTTP,
            connection_id="http-1",
            metadata=None,
        )

        assert state.metadata == {}

    def test_connection_state_active_flag(self):
        """Test connection active flag can be modified."""
        state = ConnectionState(
            protocol=ProtocolType.AMQP,
            connection_id="amqp-1",
            metadata={},
        )

        assert state.is_active is True
        state.is_active = False
        assert state.is_active is False


class TestProtocolContext:
    """Test protocol context."""

    def test_context_initialization(self):
        """Test protocol context initializes correctly."""
        context = ProtocolContext(
            protocol=ProtocolType.HTTP,
            headers={"Content-Type": "application/json"},
            metadata={"source": "test"},
        )

        assert context.protocol == ProtocolType.HTTP
        assert context.headers == {"Content-Type": "application/json"}
        assert context.metadata == {"source": "test"}
        assert context.connection_state is None

    def test_context_with_connection_state(self):
        """Test protocol context with connection state."""
        state = ConnectionState(
            protocol=ProtocolType.WEBSOCKET,
            connection_id="ws-1",
            metadata={},
        )

        context = ProtocolContext(
            protocol=ProtocolType.WEBSOCKET,
            headers={},
            metadata={},
            connection_state=state,
        )

        assert context.connection_state == state
        assert context.connection_state.connection_id == "ws-1"

    def test_context_default_dicts(self):
        """Test context initializes empty dicts for None values."""
        context = ProtocolContext(
            protocol=ProtocolType.HTTP,
            headers=None,
            metadata=None,
        )

        assert context.headers == {}
        assert context.metadata == {}


class TestProtocolDetector:
    """Test protocol detection (AC1)."""

    def test_detect_http_from_headers(self):
        """Test detecting standard HTTP from headers."""
        headers = {
            "Host": "example.com",
            "User-Agent": "test-client",
        }

        protocol = ProtocolDetector.detect_from_headers(headers)
        assert protocol == ProtocolType.HTTP

    def test_detect_http2_from_headers(self):
        """Test detecting HTTP/2 from headers."""
        headers = {
            "Host": "example.com",
            "HTTP2-Settings": "AAMAAABkAAQAAP__",
        }

        protocol = ProtocolDetector.detect_from_headers(headers)
        assert protocol == ProtocolType.HTTP2

    def test_detect_websocket_from_headers(self):
        """Test detecting WebSocket from upgrade headers."""
        headers = {
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
        }

        protocol = ProtocolDetector.detect_from_headers(headers)
        assert protocol == ProtocolType.WEBSOCKET

    def test_detect_websocket_case_insensitive(self):
        """Test WebSocket detection is case-insensitive."""
        headers = {
            "upgrade": "WebSocket",
            "connection": "upgrade",
        }

        protocol = ProtocolDetector.detect_from_headers(headers)
        assert protocol == ProtocolType.WEBSOCKET

    def test_detect_websocket_connection_keep_alive_upgrade(self):
        """Test WebSocket with multiple connection values."""
        headers = {
            "Upgrade": "websocket",
            "Connection": "keep-alive, Upgrade",
        }

        protocol = ProtocolDetector.detect_from_headers(headers)
        assert protocol == ProtocolType.WEBSOCKET

    def test_detect_unknown_from_empty_headers(self):
        """Test unknown protocol from empty headers."""
        headers = {}

        protocol = ProtocolDetector.detect_from_headers(headers)
        assert protocol == ProtocolType.UNKNOWN

    @pytest.mark.asyncio
    async def test_detect_amqp_from_data(self):
        """Test detecting AMQP from connection preface."""
        data = b"AMQP\x00\x01\x00\x00"

        protocol = await ProtocolDetector.detect_from_data(data)
        assert protocol == ProtocolType.AMQP

    @pytest.mark.asyncio
    async def test_detect_http_from_data(self):
        """Test detecting HTTP from request line."""
        data = b"GET /path HTTP/1.1\r\n"

        protocol = await ProtocolDetector.detect_from_data(data)
        assert protocol == ProtocolType.HTTP

    @pytest.mark.asyncio
    async def test_detect_http_post_from_data(self):
        """Test detecting HTTP POST from request line."""
        data = b"POST /api/resource HTTP/1.1\r\n"

        protocol = await ProtocolDetector.detect_from_data(data)
        assert protocol == ProtocolType.HTTP

    @pytest.mark.asyncio
    async def test_detect_unknown_from_data(self):
        """Test unknown protocol from unrecognized data."""
        data = b"UNKNOWN_PROTOCOL"

        protocol = await ProtocolDetector.detect_from_data(data)
        assert protocol == ProtocolType.UNKNOWN


class TestProtocolRouter:
    """Test protocol router functionality."""

    def test_router_initialization(self):
        """Test router initializes correctly."""
        router = ProtocolRouter()

        assert router.active_connections() == 0

    def test_register_handler(self):
        """Test registering protocol handlers."""
        router = ProtocolRouter()

        async def handler(context, **kwargs):
            return {"status": "ok"}

        router.register_handler(ProtocolType.HTTP, handler)

        assert router.get_handler(ProtocolType.HTTP) == handler

    def test_get_handler_not_registered(self):
        """Test getting unregistered handler returns None."""
        router = ProtocolRouter()

        handler = router.get_handler(ProtocolType.WEBSOCKET)
        assert handler is None

    def test_create_connection(self):
        """Test creating connection state (AC6)."""
        router = ProtocolRouter()

        state = router.create_connection(
            ProtocolType.WEBSOCKET, metadata={"user": "test"}
        )

        assert state.protocol == ProtocolType.WEBSOCKET
        assert state.connection_id.startswith("websocket-")
        assert state.metadata == {"user": "test"}
        assert state.is_active is True
        assert router.active_connections() == 1

    def test_create_multiple_connections(self):
        """Test creating multiple connections with unique IDs."""
        router = ProtocolRouter()

        state1 = router.create_connection(ProtocolType.WEBSOCKET)
        state2 = router.create_connection(ProtocolType.WEBSOCKET)

        assert state1.connection_id != state2.connection_id
        assert router.active_connections() == 2

    def test_get_connection(self):
        """Test retrieving connection by ID."""
        router = ProtocolRouter()

        state = router.create_connection(ProtocolType.AMQP)
        connection_id = state.connection_id

        retrieved = router.get_connection(connection_id)
        assert retrieved == state

    def test_get_nonexistent_connection(self):
        """Test getting nonexistent connection returns None."""
        router = ProtocolRouter()

        retrieved = router.get_connection("nonexistent")
        assert retrieved is None

    def test_close_connection(self):
        """Test closing connection."""
        router = ProtocolRouter()

        state = router.create_connection(ProtocolType.WEBSOCKET)
        connection_id = state.connection_id

        assert router.active_connections() == 1

        closed = router.close_connection(connection_id)
        assert closed is True
        assert router.active_connections() == 0

    def test_close_nonexistent_connection(self):
        """Test closing nonexistent connection returns False."""
        router = ProtocolRouter()

        closed = router.close_connection("nonexistent")
        assert closed is False

    def test_active_connections_by_protocol(self):
        """Test counting active connections by protocol."""
        router = ProtocolRouter()

        router.create_connection(ProtocolType.WEBSOCKET)
        router.create_connection(ProtocolType.WEBSOCKET)
        router.create_connection(ProtocolType.AMQP)

        assert router.active_connections() == 3
        assert router.active_connections(ProtocolType.WEBSOCKET) == 2
        assert router.active_connections(ProtocolType.AMQP) == 1
        assert router.active_connections(ProtocolType.HTTP) == 0

    @pytest.mark.asyncio
    async def test_route_http_request(self):
        """Test routing HTTP request (AC2)."""
        router = ProtocolRouter()

        async def http_handler(context, **kwargs):
            return {
                "status": 200,
                "protocol": context.protocol.value,
            }

        router.register_handler(ProtocolType.HTTP, http_handler)

        result = await router.route_request(
            protocol=ProtocolType.HTTP,
            headers={"Host": "example.com"},
        )

        assert result["status"] == 200
        assert result["protocol"] == "http"

    @pytest.mark.asyncio
    async def test_route_http2_request(self):
        """Test routing HTTP/2 request (AC2)."""
        router = ProtocolRouter()

        async def http2_handler(context, **kwargs):
            return {
                "status": 200,
                "protocol": context.protocol.value,
            }

        router.register_handler(ProtocolType.HTTP2, http2_handler)

        result = await router.route_request(
            protocol=ProtocolType.HTTP2,
            headers={"HTTP2-Settings": "value"},
        )

        assert result["status"] == 200
        assert result["protocol"] == "http2"

    @pytest.mark.asyncio
    async def test_route_websocket_request(self):
        """Test routing WebSocket upgrade request (AC3)."""
        router = ProtocolRouter()

        async def ws_handler(context, **kwargs):
            return {
                "status": "upgrade",
                "connection_id": context.connection_state.connection_id,
            }

        router.register_handler(ProtocolType.WEBSOCKET, ws_handler)

        result = await router.route_request(
            protocol=ProtocolType.WEBSOCKET,
            headers={"Upgrade": "websocket"},
        )

        assert result["status"] == "upgrade"
        assert "connection_id" in result
        assert router.active_connections(ProtocolType.WEBSOCKET) == 1

    @pytest.mark.asyncio
    async def test_route_amqp_request(self):
        """Test routing AMQP connection (AC4)."""
        router = ProtocolRouter()

        async def amqp_handler(context, **kwargs):
            return {
                "status": "connected",
                "connection_id": context.connection_state.connection_id,
            }

        router.register_handler(ProtocolType.AMQP, amqp_handler)

        result = await router.route_request(
            protocol=ProtocolType.AMQP,
            headers={},
        )

        assert result["status"] == "connected"
        assert "connection_id" in result
        assert router.active_connections(ProtocolType.AMQP) == 1

    @pytest.mark.asyncio
    async def test_route_preserves_headers(self):
        """Test routing preserves protocol headers (AC5)."""
        router = ProtocolRouter()

        captured_context = None

        async def handler(context, **kwargs):
            nonlocal captured_context
            captured_context = context
            return {"status": "ok"}

        router.register_handler(ProtocolType.HTTP, handler)

        headers = {
            "Content-Type": "application/json",
            "X-Custom-Header": "value",
        }

        await router.route_request(
            protocol=ProtocolType.HTTP,
            headers=headers,
        )

        assert captured_context is not None
        assert captured_context.headers == headers

    @pytest.mark.asyncio
    async def test_route_preserves_metadata(self):
        """Test routing preserves metadata (AC5)."""
        router = ProtocolRouter()

        captured_context = None

        async def handler(context, **kwargs):
            nonlocal captured_context
            captured_context = context
            return {"status": "ok"}

        router.register_handler(ProtocolType.HTTP, handler)

        metadata = {"source_ip": "127.0.0.1", "auth": "bearer token"}

        await router.route_request(
            protocol=ProtocolType.HTTP,
            headers={},
            metadata=metadata,
        )

        assert captured_context is not None
        assert captured_context.metadata == metadata

    @pytest.mark.asyncio
    async def test_route_unregistered_protocol(self):
        """Test routing unregistered protocol raises error (AC7)."""
        router = ProtocolRouter()

        with pytest.raises(ProtocolError) as exc_info:
            await router.route_request(
                protocol=ProtocolType.WEBSOCKET,
                headers={},
            )

        assert exc_info.value.protocol == ProtocolType.WEBSOCKET
        assert exc_info.value.status_code == 501
        assert "No handler registered" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_route_handler_error(self):
        """Test routing handles handler errors (AC7)."""
        router = ProtocolRouter()

        async def failing_handler(context, **kwargs):
            raise ValueError("Handler failed")

        router.register_handler(ProtocolType.HTTP, failing_handler)

        with pytest.raises(ProtocolError) as exc_info:
            await router.route_request(
                protocol=ProtocolType.HTTP,
                headers={},
            )

        assert exc_info.value.protocol == ProtocolType.HTTP
        assert exc_info.value.status_code == 500
        assert "Protocol handler error" in exc_info.value.message


class TestFormatProtocolError:
    """Test protocol error formatting (AC7)."""

    def test_format_http_error(self):
        """Test formatting HTTP error."""
        error = ProtocolError(
            "Not found", protocol=ProtocolType.HTTP, status_code=404
        )

        formatted = format_protocol_error(error)

        assert formatted == {
            "error": {
                "code": 404,
                "message": "Not found",
                "protocol": "http",
            }
        }

    def test_format_http2_error(self):
        """Test formatting HTTP/2 error."""
        error = ProtocolError(
            "Server error", protocol=ProtocolType.HTTP2, status_code=500
        )

        formatted = format_protocol_error(error)

        assert formatted["error"]["code"] == 500
        assert formatted["error"]["protocol"] == "http2"

    def test_format_websocket_error(self):
        """Test formatting WebSocket error."""
        error = ProtocolError(
            "Invalid frame", protocol=ProtocolType.WEBSOCKET
        )

        formatted = format_protocol_error(error)

        assert formatted["close_code"] == 1008
        assert formatted["close_reason"] == "Invalid frame"

    def test_format_amqp_error(self):
        """Test formatting AMQP error."""
        error = ProtocolError(
            "Connection failed", protocol=ProtocolType.AMQP
        )

        formatted = format_protocol_error(error)

        assert formatted["condition"] == "amqp:internal-error"
        assert formatted["description"] == "Connection failed"

    def test_format_unknown_error(self):
        """Test formatting unknown protocol error."""
        error = ProtocolError(
            "Generic error", protocol=ProtocolType.UNKNOWN
        )

        formatted = format_protocol_error(error)

        assert formatted == {"error": "Generic error"}


class TestExampleHandlers:
    """Test example handler implementations."""

    @pytest.mark.asyncio
    async def test_http_handler_example(self):
        """Test HTTP handler example."""
        context = ProtocolContext(
            protocol=ProtocolType.HTTP,
            headers={"Host": "example.com"},
            metadata={},
        )

        result = await http_handler_example(context)

        assert result["status"] == 200
        assert result["body"]["protocol"] == "http"
        assert result["headers"] == context.headers

    @pytest.mark.asyncio
    async def test_websocket_handler_example(self):
        """Test WebSocket handler example."""
        state = ConnectionState(
            protocol=ProtocolType.WEBSOCKET,
            connection_id="ws-test",
            metadata={},
        )

        context = ProtocolContext(
            protocol=ProtocolType.WEBSOCKET,
            headers={},
            metadata={},
            connection_state=state,
        )

        result = await websocket_handler_example(context)

        assert result["status"] == "upgrade"
        assert result["connection_id"] == "ws-test"
        assert result["protocol"] == "websocket"

    @pytest.mark.asyncio
    async def test_websocket_handler_no_connection(self):
        """Test WebSocket handler fails without connection state."""
        context = ProtocolContext(
            protocol=ProtocolType.WEBSOCKET,
            headers={},
            metadata={},
        )

        with pytest.raises(ProtocolError) as exc_info:
            await websocket_handler_example(context)

        assert exc_info.value.protocol == ProtocolType.WEBSOCKET

    @pytest.mark.asyncio
    async def test_amqp_handler_example(self):
        """Test AMQP handler example."""
        state = ConnectionState(
            protocol=ProtocolType.AMQP,
            connection_id="amqp-test",
            metadata={},
        )

        context = ProtocolContext(
            protocol=ProtocolType.AMQP,
            headers={},
            metadata={},
            connection_state=state,
        )

        result = await amqp_handler_example(context)

        assert result["status"] == "connected"
        assert result["connection_id"] == "amqp-test"
        assert result["protocol"] == "amqp"

    @pytest.mark.asyncio
    async def test_amqp_handler_no_connection(self):
        """Test AMQP handler fails without connection state."""
        context = ProtocolContext(
            protocol=ProtocolType.AMQP,
            headers={},
            metadata={},
        )

        with pytest.raises(ProtocolError) as exc_info:
            await amqp_handler_example(context)

        assert exc_info.value.protocol == ProtocolType.AMQP


class TestConnectionStateTracking:
    """Test connection state tracking for stateful protocols (AC6)."""

    def test_track_multiple_websocket_connections(self):
        """Test tracking multiple WebSocket connections."""
        router = ProtocolRouter()

        ws1 = router.create_connection(ProtocolType.WEBSOCKET)
        ws2 = router.create_connection(ProtocolType.WEBSOCKET)
        amqp1 = router.create_connection(ProtocolType.AMQP)

        assert router.active_connections(ProtocolType.WEBSOCKET) == 2
        assert router.active_connections(ProtocolType.AMQP) == 1

        # Close one WebSocket
        router.close_connection(ws1.connection_id)

        assert router.active_connections(ProtocolType.WEBSOCKET) == 1
        assert router.active_connections(ProtocolType.AMQP) == 1

    def test_connection_metadata_persistence(self):
        """Test connection metadata persists across retrievals."""
        router = ProtocolRouter()

        metadata = {"client_id": "test-123", "auth": "token"}
        state = router.create_connection(ProtocolType.WEBSOCKET, metadata)

        retrieved = router.get_connection(state.connection_id)

        assert retrieved.metadata == metadata
        assert retrieved.metadata["client_id"] == "test-123"
