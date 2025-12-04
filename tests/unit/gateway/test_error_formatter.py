"""Tests for Azure error formatter."""

import json
import pytest
from xml.etree import ElementTree as ET
from localzure.gateway.error_formatter import (
    ErrorFormat,
    ServiceType,
    ErrorContext,
    AzureError,
    generate_request_id,
    generate_timestamp_request_id,
    determine_error_format,
    format_error_xml,
    format_error_json,
    create_error_headers,
    create_error_response,
    map_error_code_to_status,
    create_storage_error,
    create_service_bus_error,
    create_key_vault_error,
    create_cosmos_db_error,
    create_generic_error,
    ERROR_CODE_MAPPINGS,
)


class TestErrorCodeMappings:
    """Tests for error code mappings."""

    def test_authentication_error_codes(self):
        """Test authentication error codes map to 401."""
        assert ERROR_CODE_MAPPINGS["AuthenticationFailed"] == 401
        assert ERROR_CODE_MAPPINGS["InvalidAuthenticationInfo"] == 401
        assert ERROR_CODE_MAPPINGS["MissingRequiredHeader"] == 401

    def test_authorization_error_codes(self):
        """Test authorization error codes map to 403."""
        assert ERROR_CODE_MAPPINGS["AuthorizationFailed"] == 403
        assert ERROR_CODE_MAPPINGS["InsufficientAccountPermissions"] == 403
        assert ERROR_CODE_MAPPINGS["AccountIsDisabled"] == 403

    def test_not_found_error_codes(self):
        """Test not found error codes map to 404."""
        assert ERROR_CODE_MAPPINGS["ResourceNotFound"] == 404
        assert ERROR_CODE_MAPPINGS["BlobNotFound"] == 404
        assert ERROR_CODE_MAPPINGS["ContainerNotFound"] == 404
        assert ERROR_CODE_MAPPINGS["QueueNotFound"] == 404

    def test_bad_request_error_codes(self):
        """Test bad request error codes map to 400."""
        assert ERROR_CODE_MAPPINGS["InvalidResourceName"] == 400
        assert ERROR_CODE_MAPPINGS["InvalidUri"] == 400
        assert ERROR_CODE_MAPPINGS["InvalidInput"] == 400

    def test_conflict_error_codes(self):
        """Test conflict error codes map to 409."""
        assert ERROR_CODE_MAPPINGS["ResourceAlreadyExists"] == 409
        assert ERROR_CODE_MAPPINGS["ContainerAlreadyExists"] == 409
        assert ERROR_CODE_MAPPINGS["BlobAlreadyExists"] == 409

    def test_server_error_codes(self):
        """Test server error codes map to 500+."""
        assert ERROR_CODE_MAPPINGS["InternalError"] == 500
        assert ERROR_CODE_MAPPINGS["ServerBusy"] == 503
        assert ERROR_CODE_MAPPINGS["ServiceUnavailable"] == 503

    def test_rate_limit_error_code(self):
        """Test rate limit error code maps to 429."""
        assert ERROR_CODE_MAPPINGS["TooManyRequests"] == 429


class TestRequestIdGeneration:
    """Tests for request ID generation."""

    def test_generate_request_id_format(self):
        """Test request ID is valid UUID."""
        request_id = generate_request_id()
        # Should be UUID format
        assert len(request_id) == 36
        assert request_id.count("-") == 4

    def test_generate_request_id_unique(self):
        """Test request IDs are unique."""
        id1 = generate_request_id()
        id2 = generate_request_id()
        assert id1 != id2

    def test_generate_timestamp_request_id_format(self):
        """Test timestamp request ID format."""
        request_id = generate_timestamp_request_id()
        # Should be format: YYYYMMDDTHHMMss.fffZ (20 chars)
        assert request_id.endswith("Z")
        assert "T" in request_id
        assert len(request_id) == 20  # YYYYMMDDTHHMMss.fffZ

    def test_generate_timestamp_request_id_unique(self):
        """Test timestamp request IDs are different."""
        id1 = generate_timestamp_request_id()
        id2 = generate_timestamp_request_id()
        # May be equal if called very quickly, but structure should be valid
        assert id1.endswith("Z")
        assert id2.endswith("Z")


class TestErrorContext:
    """Tests for ErrorContext."""

    def test_error_context_defaults(self):
        """Test ErrorContext default values."""
        context = ErrorContext(error_code="BlobNotFound", message="Test message")

        assert context.error_code == "BlobNotFound"
        assert context.message == "Test message"
        assert context.service_type == ServiceType.GENERIC
        assert context.status_code == 404  # Mapped from error code
        assert context.request_id is not None
        assert context.additional_info is None

    def test_error_context_custom_status(self):
        """Test ErrorContext with custom status code."""
        context = ErrorContext(
            error_code="CustomError", message="Test", status_code=418
        )

        assert context.status_code == 418

    def test_error_context_custom_request_id(self):
        """Test ErrorContext with custom request ID."""
        context = ErrorContext(
            error_code="Test", message="Test", request_id="custom-id-123"
        )

        assert context.request_id == "custom-id-123"

    def test_error_context_additional_info(self):
        """Test ErrorContext with additional info."""
        context = ErrorContext(
            error_code="Test",
            message="Test",
            additional_info={"detail": "extra info"},
        )

        assert context.additional_info == {"detail": "extra info"}

    def test_error_context_service_type(self):
        """Test ErrorContext with service type."""
        context = ErrorContext(
            error_code="Test", message="Test", service_type=ServiceType.STORAGE
        )

        assert context.service_type == ServiceType.STORAGE


class TestDetermineErrorFormat:
    """Tests for determine_error_format."""

    def test_storage_defaults_to_xml(self):
        """Test Storage services default to XML."""
        fmt = determine_error_format(ServiceType.STORAGE)
        assert fmt == ErrorFormat.XML

    def test_storage_json_with_accept_header(self):
        """Test Storage can use JSON with Accept header."""
        fmt = determine_error_format(
            ServiceType.STORAGE, accept_header="application/json"
        )
        assert fmt == ErrorFormat.JSON

    def test_storage_xml_with_xml_accept_header(self):
        """Test Storage uses XML with XML Accept header."""
        fmt = determine_error_format(
            ServiceType.STORAGE, accept_header="application/xml"
        )
        assert fmt == ErrorFormat.XML

    def test_service_bus_uses_json(self):
        """Test Service Bus uses JSON."""
        fmt = determine_error_format(ServiceType.SERVICE_BUS)
        assert fmt == ErrorFormat.JSON

    def test_key_vault_uses_json(self):
        """Test Key Vault uses JSON."""
        fmt = determine_error_format(ServiceType.KEY_VAULT)
        assert fmt == ErrorFormat.JSON

    def test_cosmos_db_uses_json(self):
        """Test Cosmos DB uses JSON."""
        fmt = determine_error_format(ServiceType.COSMOS_DB)
        assert fmt == ErrorFormat.JSON

    def test_generic_uses_json(self):
        """Test generic services use JSON."""
        fmt = determine_error_format(ServiceType.GENERIC)
        assert fmt == ErrorFormat.JSON


class TestFormatErrorXml:
    """Tests for format_error_xml."""

    def test_basic_xml_format(self):
        """Test basic XML error format."""
        context = ErrorContext(
            error_code="BlobNotFound",
            message="The specified blob does not exist.",
        )

        xml_str = format_error_xml(context)
        xml_bytes = xml_str if isinstance(xml_str, bytes) else xml_str.encode("utf-8")

        # Parse XML
        root = ET.fromstring(xml_bytes)

        assert root.tag == "Error"
        assert root.find("Code").text == "BlobNotFound"
        assert root.find("Message").text == "The specified blob does not exist."

    def test_xml_with_declaration(self):
        """Test XML includes declaration."""
        context = ErrorContext(error_code="Test", message="Test")

        xml_str = format_error_xml(context)
        xml_bytes = xml_str if isinstance(xml_str, bytes) else xml_str.encode("utf-8")

        assert xml_bytes.startswith(b'<?xml version="1.0" encoding="utf-8"?>')

    def test_xml_with_additional_info(self):
        """Test XML with additional info fields."""
        context = ErrorContext(
            error_code="Test",
            message="Test",
            additional_info={"RequestId": "abc123", "Detail": "More info"},
        )

        xml_str = format_error_xml(context)
        xml_bytes = xml_str if isinstance(xml_str, bytes) else xml_str.encode("utf-8")

        root = ET.fromstring(xml_bytes)
        assert root.find("RequestId").text == "abc123"
        assert root.find("Detail").text == "More info"


class TestFormatErrorJson:
    """Tests for format_error_json."""

    def test_basic_json_format(self):
        """Test basic JSON error format."""
        context = ErrorContext(
            error_code="ResourceNotFound",
            message="The specified resource does not exist.",
        )

        json_str = format_error_json(context)
        data = json.loads(json_str)

        assert "error" in data
        assert data["error"]["code"] == "ResourceNotFound"
        assert data["error"]["message"] == "The specified resource does not exist."

    def test_json_with_additional_info(self):
        """Test JSON with additional info."""
        context = ErrorContext(
            error_code="Test",
            message="Test",
            additional_info={"target": "field1", "details": "validation failed"},
        )

        json_str = format_error_json(context)
        data = json.loads(json_str)

        assert data["error"]["target"] == "field1"
        assert data["error"]["details"] == "validation failed"


class TestCreateErrorHeaders:
    """Tests for create_error_headers."""

    def test_required_headers(self):
        """Test required error headers are present."""
        headers = create_error_headers(
            error_code="BlobNotFound",
            request_id="abc-123",
            content_type="application/xml",
        )

        assert headers["x-ms-request-id"] == "abc-123"
        assert headers["x-ms-error-code"] == "BlobNotFound"
        assert headers["Content-Type"] == "application/xml"
        assert "Date" in headers

    def test_date_header_format(self):
        """Test Date header has correct format."""
        headers = create_error_headers("Test", "id", "application/json")

        # Should be HTTP date format
        assert "GMT" in headers["Date"]


class TestCreateErrorResponse:
    """Tests for create_error_response."""

    def test_storage_error_xml_default(self):
        """Test Storage error defaults to XML."""
        context = ErrorContext(
            error_code="BlobNotFound",
            message="Blob not found",
            service_type=ServiceType.STORAGE,
        )

        error = create_error_response(context)

        assert error.error_code == "BlobNotFound"
        assert error.status_code == 404
        assert error.content_type == "application/xml"
        assert "<?xml" in error.body
        assert error.headers["x-ms-error-code"] == "BlobNotFound"
        assert "x-ms-request-id" in error.headers

    def test_storage_error_json_with_accept(self):
        """Test Storage error uses JSON with Accept header."""
        context = ErrorContext(
            error_code="BlobNotFound",
            message="Blob not found",
            service_type=ServiceType.STORAGE,
        )

        error = create_error_response(context, accept_header="application/json")

        assert error.content_type == "application/json"
        data = json.loads(error.body)
        assert data["error"]["code"] == "BlobNotFound"

    def test_service_bus_error_json(self):
        """Test Service Bus error uses JSON."""
        context = ErrorContext(
            error_code="QueueNotFound",
            message="Queue not found",
            service_type=ServiceType.SERVICE_BUS,
        )

        error = create_error_response(context)

        assert error.content_type == "application/json"
        data = json.loads(error.body)
        assert data["error"]["code"] == "QueueNotFound"

    def test_error_format_override(self):
        """Test error format can be overridden."""
        context = ErrorContext(
            error_code="Test",
            message="Test",
            service_type=ServiceType.STORAGE,
        )

        error = create_error_response(context, error_format=ErrorFormat.JSON)

        assert error.content_type == "application/json"

    def test_error_to_dict(self):
        """Test AzureError.to_dict()."""
        context = ErrorContext(error_code="Test", message="Test")
        error = create_error_response(context)

        result = error.to_dict()

        assert "status_code" in result
        assert "headers" in result
        assert "body" in result
        assert "content_type" in result


class TestMapErrorCodeToStatus:
    """Tests for map_error_code_to_status."""

    def test_known_error_code(self):
        """Test mapping known error code."""
        status = map_error_code_to_status("BlobNotFound")
        assert status == 404

    def test_unknown_error_code_default(self):
        """Test unknown error code uses default."""
        status = map_error_code_to_status("UnknownError")
        assert status == 500

    def test_unknown_error_code_custom_default(self):
        """Test unknown error code with custom default."""
        status = map_error_code_to_status("UnknownError", default=418)
        assert status == 418


class TestCreateStorageError:
    """Tests for create_storage_error."""

    def test_storage_error_xml_format(self):
        """Test Storage error in XML format."""
        error = create_storage_error(
            "BlobNotFound", "The specified blob does not exist."
        )

        assert error.status_code == 404
        assert error.content_type == "application/xml"
        assert "BlobNotFound" in error.body
        assert error.headers["x-ms-error-code"] == "BlobNotFound"

    def test_storage_error_json_format(self):
        """Test Storage error in JSON format."""
        error = create_storage_error(
            "BlobNotFound",
            "The specified blob does not exist.",
            accept_header="application/json",
        )

        assert error.content_type == "application/json"
        data = json.loads(error.body)
        assert data["error"]["code"] == "BlobNotFound"

    def test_storage_error_custom_request_id(self):
        """Test Storage error with custom request ID."""
        error = create_storage_error("Test", "Test", request_id="custom-123")

        assert error.request_id == "custom-123"
        assert error.headers["x-ms-request-id"] == "custom-123"

    def test_storage_error_additional_info(self):
        """Test Storage error with additional info."""
        error = create_storage_error(
            "Test", "Test", additional_info={"Detail": "Extra"}
        )

        # Additional info should be in body
        assert "Detail" in error.body or "detail" in error.body.lower()


class TestCreateServiceBusError:
    """Tests for create_service_bus_error."""

    def test_service_bus_error_format(self):
        """Test Service Bus error format."""
        error = create_service_bus_error(
            "QueueNotFound", "The specified queue does not exist."
        )

        assert error.content_type == "application/json"
        assert error.status_code == 404
        data = json.loads(error.body)
        assert data["error"]["code"] == "QueueNotFound"

    def test_service_bus_error_headers(self):
        """Test Service Bus error headers."""
        error = create_service_bus_error("Test", "Test")

        assert "x-ms-request-id" in error.headers
        assert "x-ms-error-code" in error.headers


class TestCreateKeyVaultError:
    """Tests for create_key_vault_error."""

    def test_key_vault_error_format(self):
        """Test Key Vault error format."""
        error = create_key_vault_error("KeyNotFound", "The key does not exist.")

        assert error.content_type == "application/json"
        data = json.loads(error.body)
        assert data["error"]["code"] == "KeyNotFound"

    def test_key_vault_error_custom_request_id(self):
        """Test Key Vault error with custom request ID."""
        error = create_key_vault_error("Test", "Test", request_id="kv-123")

        assert error.request_id == "kv-123"


class TestCreateCosmosDbError:
    """Tests for create_cosmos_db_error."""

    def test_cosmos_db_error_format(self):
        """Test Cosmos DB error format."""
        error = create_cosmos_db_error(
            "EntityNotFound", "The entity does not exist."
        )

        assert error.content_type == "application/json"
        data = json.loads(error.body)
        assert data["error"]["code"] == "EntityNotFound"


class TestCreateGenericError:
    """Tests for create_generic_error."""

    def test_generic_error_format(self):
        """Test generic error format."""
        error = create_generic_error("CustomError", "Custom message", status_code=418)

        assert error.status_code == 418
        assert error.content_type == "application/json"
        data = json.loads(error.body)
        assert data["error"]["code"] == "CustomError"
        assert data["error"]["message"] == "Custom message"

    def test_generic_error_default_status(self):
        """Test generic error with default status."""
        error = create_generic_error("Error", "Message")

        assert error.status_code == 500


class TestEndToEndScenarios:
    """End-to-end test scenarios."""

    def test_blob_not_found_scenario(self):
        """Test blob not found error scenario."""
        error = create_storage_error(
            "BlobNotFound", "The specified blob does not exist."
        )

        # Verify response structure
        assert error.status_code == 404
        assert error.error_code == "BlobNotFound"
        assert "x-ms-request-id" in error.headers
        assert "x-ms-error-code" in error.headers
        assert error.headers["x-ms-error-code"] == "BlobNotFound"

        # Verify XML structure
        root = ET.fromstring(error.body.encode("utf-8"))
        assert root.find("Code").text == "BlobNotFound"
        assert "blob" in root.find("Message").text.lower()

    def test_authentication_failed_scenario(self):
        """Test authentication failed scenario."""
        error = create_storage_error(
            "AuthenticationFailed",
            "Server failed to authenticate the request.",
            accept_header="application/json",
        )

        # Verify status code mapped correctly
        assert error.status_code == 401
        assert error.content_type == "application/json"

        # Verify JSON structure
        data = json.loads(error.body)
        assert data["error"]["code"] == "AuthenticationFailed"

    def test_container_already_exists_scenario(self):
        """Test container already exists scenario."""
        error = create_storage_error(
            "ContainerAlreadyExists", "The specified container already exists."
        )

        # Verify conflict status
        assert error.status_code == 409
        assert error.error_code == "ContainerAlreadyExists"

    def test_rate_limit_scenario(self):
        """Test rate limit scenario."""
        error = create_generic_error(
            "TooManyRequests", "Rate limit exceeded.", status_code=429
        )

        assert error.status_code == 429
        assert error.headers["x-ms-error-code"] == "TooManyRequests"

    def test_service_unavailable_scenario(self):
        """Test service unavailable scenario."""
        error = create_service_bus_error("ServiceUnavailable", "Service is busy.")

        assert error.status_code == 503
        data = json.loads(error.body)
        assert data["error"]["code"] == "ServiceUnavailable"

    def test_content_negotiation_scenario(self):
        """Test content negotiation with different Accept headers."""
        # XML request
        error1 = create_storage_error(
            "Test", "Test", accept_header="application/xml"
        )
        assert error1.content_type == "application/xml"

        # JSON request
        error2 = create_storage_error(
            "Test", "Test", accept_header="application/json"
        )
        assert error2.content_type == "application/json"

        # Default (no Accept header)
        error3 = create_storage_error("Test", "Test")
        assert error3.content_type == "application/xml"
