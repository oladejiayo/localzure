"""Tests for SAS token validation."""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest

from localzure.gateway.sas_validator import (
    SASPermission,
    SASResourceType,
    SASService,
    SASToken,
    SASValidationError,
    SASValidator,
    get_permission_for_method,
)


@pytest.fixture
def account_key():
    """Generate a test account key."""
    return base64.b64encode(b"test-account-key-12345678901234567890").decode()


@pytest.fixture
def validator(account_key):
    """Create a SAS validator instance."""
    return SASValidator(account_name="testaccount", account_key=account_key)


def build_sas_url(
    base_url: str,
    account_name: str,
    account_key_bytes: bytes,
    permissions: str = "r",
    services: str = "b",
    resource_types: str = "o",
    expiry_offset: timedelta = timedelta(hours=1),
    start_offset: timedelta = None,
    version: str = "2021-06-08",
) -> str:
    """Build a valid SAS URL with signature.

    Args:
        base_url: Base URL without query parameters
        account_name: Storage account name
        account_key_bytes: Decoded account key bytes
        permissions: Permission string (rwdlacup)
        services: Service string (bqtf)
        resource_types: Resource type string (sco)
        expiry_offset: Time offset for expiry from now
        start_offset: Time offset for start from now (optional)
        version: SAS version

    Returns:
        Complete URL with SAS token
    """
    now = datetime.now(timezone.utc)
    expiry = (now + expiry_offset).strftime("%Y-%m-%dT%H:%M:%SZ")
    start = (
        (now + start_offset).strftime("%Y-%m-%dT%H:%M:%SZ")
        if start_offset
        else ""
    )

    # Build string to sign
    string_to_sign = "\n".join(
        [
            account_name,
            permissions,
            services,
            resource_types,
            start,
            expiry,
            "",  # IP
            "",  # Protocol
            version,
        ]
    )

    # Compute signature
    signature = base64.b64encode(
        hmac.new(
            account_key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256
        ).digest()
    ).decode()

    # Build query parameters
    params = {
        "sv": version,
        "ss": services,
        "srt": resource_types,
        "sp": permissions,
        "se": expiry,
        "sig": signature,
    }
    if start:
        params["st"] = start

    return f"{base_url}?{urlencode(params)}"


class TestSASTokenParsing:
    """Test SAS token parsing (AC1)."""

    def test_parse_valid_sas_token(self, validator):
        """Test parsing a valid SAS token from URL."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        assert token.signed_version == "2021-06-08"
        assert token.signed_services == "b"
        assert token.signed_resource_types == "o"
        assert token.signed_permissions == "r"
        assert token.signed_expiry == "2025-12-31T23:59:59Z"
        assert token.signature == "abc123"
        assert token.signed_start is None

    def test_parse_sas_token_with_start_time(self, validator):
        """Test parsing SAS token with start time."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&"
            "st=2025-01-01T00:00:00Z&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        assert token.signed_start == "2025-01-01T00:00:00Z"

    def test_parse_sas_token_with_protocol_and_ip(self, validator):
        """Test parsing SAS token with protocol and IP restrictions."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=2025-12-31T23:59:59Z&"
            "spr=https&sip=192.168.1.1&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        assert token.signed_protocol == "https"
        assert token.signed_ip == "192.168.1.1"

    def test_parse_missing_required_parameter(self, validator):
        """Test parsing SAS token with missing required parameter."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r"  # Missing se and sig
        )

        with pytest.raises(SASValidationError) as exc_info:
            validator.parse_sas_token(url)

        assert exc_info.value.error_code == "InvalidQueryParameterValue"

    def test_parse_multiple_services_permissions(self, validator):
        """Test parsing SAS token with multiple services and permissions."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=bqt&srt=sco&sp=rwdlacup&"
            "se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        assert token.signed_services == "bqt"
        assert token.signed_resource_types == "sco"
        assert token.signed_permissions == "rwdlacup"


class TestSASSignatureValidation:
    """Test SAS signature validation (AC2)."""

    def test_valid_signature(self, validator, account_key):
        """Test validation of correct signature."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
        )

        token = validator.parse_sas_token(url)
        # Should not raise
        validator.validate_signature(token, url)

    def test_invalid_signature(self, validator):
        """Test validation fails with incorrect signature."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=2025-12-31T23:59:59Z&sig=invalid"
        )

        token = validator.parse_sas_token(url)

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate_signature(token, url)

        assert exc_info.value.error_code == "AuthenticationFailed"
        assert "Signature mismatch" in exc_info.value.message

    def test_signature_with_url_encoding(self, validator, account_key):
        """Test signature validation handles URL encoding correctly."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
        )

        # URL encode the signature
        url_encoded = url.replace("+", "%2B").replace("/", "%2F")

        token = validator.parse_sas_token(url_encoded)
        # Should still validate correctly
        validator.validate_signature(token, url_encoded)


class TestSASExpiryValidation:
    """Test SAS expiry time validation (AC3)."""

    def test_valid_expiry(self, validator, account_key):
        """Test validation passes for non-expired token."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            expiry_offset=timedelta(hours=1),
        )

        token = validator.parse_sas_token(url)
        # Should not raise
        validator.validate_expiry(token)

    def test_expired_token(self, validator, account_key):
        """Test validation fails for expired token."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            expiry_offset=timedelta(hours=-1),  # Expired 1 hour ago
        )

        token = validator.parse_sas_token(url)

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate_expiry(token)

        assert exc_info.value.error_code == "AuthenticationFailed"
        assert "expired" in exc_info.value.message.lower()

    def test_invalid_expiry_format(self, validator):
        """Test validation fails for invalid expiry format."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=invalid-date&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate_expiry(token)

        assert exc_info.value.error_code == "InvalidQueryParameterValue"


class TestSASStartTimeValidation:
    """Test SAS start time validation (AC4)."""

    def test_valid_start_time(self, validator, account_key):
        """Test validation passes when current time is after start time."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            start_offset=timedelta(hours=-1),  # Started 1 hour ago
        )

        token = validator.parse_sas_token(url)
        # Should not raise
        validator.validate_start_time(token)

    def test_start_time_in_future(self, validator, account_key):
        """Test validation fails when current time is before start time."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            start_offset=timedelta(hours=1),  # Starts in 1 hour
        )

        token = validator.parse_sas_token(url)

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate_start_time(token)

        assert exc_info.value.error_code == "AuthenticationFailed"
        assert "not yet valid" in exc_info.value.message.lower()

    def test_no_start_time(self, validator, account_key):
        """Test validation passes when no start time is specified."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            start_offset=None,
        )

        token = validator.parse_sas_token(url)
        # Should not raise
        validator.validate_start_time(token)

    def test_invalid_start_time_format(self, validator):
        """Test validation fails for invalid start time format."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&st=invalid-date&"
            "se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate_start_time(token)

        assert exc_info.value.error_code == "InvalidQueryParameterValue"


class TestSASPermissionValidation:
    """Test SAS permission validation (AC5)."""

    def test_valid_permission(self, validator):
        """Test validation passes when required permission is granted."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)
        # Should not raise
        validator.validate_permissions(token, SASPermission.READ)

    def test_missing_permission(self, validator):
        """Test validation fails when required permission is not granted."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate_permissions(token, SASPermission.WRITE)

        assert exc_info.value.error_code == "AuthorizationPermissionMismatch"
        assert "lacks required permission" in exc_info.value.message

    def test_multiple_permissions(self, validator):
        """Test validation with multiple granted permissions."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=rwdl&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        # All these should pass
        validator.validate_permissions(token, SASPermission.READ)
        validator.validate_permissions(token, SASPermission.WRITE)
        validator.validate_permissions(token, SASPermission.DELETE)
        validator.validate_permissions(token, SASPermission.LIST)

        # This should fail
        with pytest.raises(SASValidationError):
            validator.validate_permissions(token, SASPermission.ADD)

    def test_all_permissions(self, validator):
        """Test validation with all permissions granted."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=rwdlacup&"
            "se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        # All permissions should pass
        for perm in SASPermission:
            validator.validate_permissions(token, perm)


class TestSASResourceTypeValidation:
    """Test SAS resource type validation (AC6)."""

    def test_valid_resource_type(self, validator):
        """Test validation passes when required resource type is allowed."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)
        # Should not raise
        validator.validate_resource_types(token, SASResourceType.OBJECT)

    def test_invalid_resource_type(self, validator):
        """Test validation fails when required resource type is not allowed."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate_resource_types(token, SASResourceType.CONTAINER)

        assert exc_info.value.error_code == "AuthorizationResourceTypeMismatch"
        assert "does not allow resource type" in exc_info.value.message

    def test_multiple_resource_types(self, validator):
        """Test validation with multiple allowed resource types."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=sco&sp=r&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        # All these should pass
        validator.validate_resource_types(token, SASResourceType.SERVICE)
        validator.validate_resource_types(token, SASResourceType.CONTAINER)
        validator.validate_resource_types(token, SASResourceType.OBJECT)


class TestSASServiceValidation:
    """Test SAS service validation."""

    def test_valid_service(self, validator):
        """Test validation passes when required service is allowed."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)
        # Should not raise
        validator.validate_services(token, SASService.BLOB)

    def test_invalid_service(self, validator):
        """Test validation fails when required service is not allowed."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=b&srt=o&sp=r&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate_services(token, SASService.QUEUE)

        assert exc_info.value.error_code == "AuthorizationServiceMismatch"
        assert "does not allow service" in exc_info.value.message

    def test_multiple_services(self, validator):
        """Test validation with multiple allowed services."""
        url = (
            "https://testaccount.blob.core.windows.net/container/blob?"
            "sv=2021-06-08&ss=bqt&srt=o&sp=r&se=2025-12-31T23:59:59Z&sig=abc123"
        )

        token = validator.parse_sas_token(url)

        # These should pass
        validator.validate_services(token, SASService.BLOB)
        validator.validate_services(token, SASService.QUEUE)
        validator.validate_services(token, SASService.TABLE)

        # This should fail
        with pytest.raises(SASValidationError):
            validator.validate_services(token, SASService.FILE)


class TestSASCompleteValidation:
    """Test complete SAS validation workflow."""

    def test_complete_validation_success(self, validator, account_key):
        """Test complete validation with all checks passing."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            permissions="r",
            services="b",
            resource_types="o",
        )

        # Should not raise
        token = validator.validate(
            url,
            required_permission=SASPermission.READ,
            required_resource_type=SASResourceType.OBJECT,
            required_service=SASService.BLOB,
        )

        assert token is not None
        assert isinstance(token, SASToken)

    def test_complete_validation_with_write_permission(
        self, validator, account_key
    ):
        """Test complete validation with write permission."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            permissions="rw",
            services="b",
            resource_types="o",
        )

        token = validator.validate(
            url,
            required_permission=SASPermission.WRITE,
            required_resource_type=SASResourceType.OBJECT,
            required_service=SASService.BLOB,
        )

        assert token is not None

    def test_complete_validation_fails_on_expired(
        self, validator, account_key
    ):
        """Test complete validation fails when token is expired."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            expiry_offset=timedelta(hours=-1),
        )

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate(
                url,
                required_permission=SASPermission.READ,
                required_resource_type=SASResourceType.OBJECT,
                required_service=SASService.BLOB,
            )

        assert exc_info.value.error_code == "AuthenticationFailed"

    def test_complete_validation_fails_on_permission(
        self, validator, account_key
    ):
        """Test complete validation fails when permission is insufficient."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            permissions="r",  # Read only
        )

        with pytest.raises(SASValidationError) as exc_info:
            validator.validate(
                url,
                required_permission=SASPermission.WRITE,  # Requires write
                required_resource_type=SASResourceType.OBJECT,
                required_service=SASService.BLOB,
            )

        assert exc_info.value.error_code == "AuthorizationPermissionMismatch"

    def test_complete_validation_with_all_checks(
        self, validator, account_key
    ):
        """Test complete validation with start time, expiry, permissions, etc."""
        account_key_bytes = base64.b64decode(account_key)
        url = build_sas_url(
            "https://testaccount.blob.core.windows.net/container/blob",
            "testaccount",
            account_key_bytes,
            permissions="rwdl",
            services="bq",
            resource_types="sco",
            start_offset=timedelta(hours=-1),
            expiry_offset=timedelta(hours=1),
        )

        token = validator.validate(
            url,
            required_permission=SASPermission.DELETE,
            required_resource_type=SASResourceType.CONTAINER,
            required_service=SASService.BLOB,
        )

        assert token is not None
        assert token.signed_start is not None


class TestHelperFunctions:
    """Test helper functions."""

    def test_get_permission_for_method_get(self):
        """Test mapping GET to READ permission."""
        assert get_permission_for_method("GET") == SASPermission.READ

    def test_get_permission_for_method_head(self):
        """Test mapping HEAD to READ permission."""
        assert get_permission_for_method("HEAD") == SASPermission.READ

    def test_get_permission_for_method_put(self):
        """Test mapping PUT to WRITE permission."""
        assert get_permission_for_method("PUT") == SASPermission.WRITE

    def test_get_permission_for_method_post(self):
        """Test mapping POST to ADD permission."""
        assert get_permission_for_method("POST") == SASPermission.ADD

    def test_get_permission_for_method_delete(self):
        """Test mapping DELETE to DELETE permission."""
        assert get_permission_for_method("DELETE") == SASPermission.DELETE

    def test_get_permission_for_method_case_insensitive(self):
        """Test method mapping is case-insensitive."""
        assert get_permission_for_method("get") == SASPermission.READ
        assert get_permission_for_method("Get") == SASPermission.READ

    def test_get_permission_for_method_unsupported(self):
        """Test unsupported HTTP method raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_permission_for_method("PATCH")

        assert "Unsupported HTTP method" in str(exc_info.value)


class TestSASValidationError:
    """Test SAS validation error class (AC7)."""

    def test_error_has_code_and_message(self):
        """Test SASValidationError contains error code and message."""
        error = SASValidationError(
            "Test error message", "TestErrorCode"
        )

        assert error.error_code == "TestErrorCode"
        assert error.message == "Test error message"
        assert str(error) == "Test error message"

    def test_error_default_code(self):
        """Test SASValidationError uses default error code."""
        error = SASValidationError("Test error message")

        assert error.error_code == "AuthenticationFailed"

    def test_different_error_codes(self):
        """Test various error codes used throughout validation."""
        # From parsing
        error1 = SASValidationError(
            "Missing parameter", "InvalidQueryParameterValue"
        )
        assert error1.error_code == "InvalidQueryParameterValue"

        # From signature validation
        error2 = SASValidationError("Bad signature", "AuthenticationFailed")
        assert error2.error_code == "AuthenticationFailed"

        # From permission validation
        error3 = SASValidationError(
            "No permission", "AuthorizationPermissionMismatch"
        )
        assert error3.error_code == "AuthorizationPermissionMismatch"

        # From resource type validation
        error4 = SASValidationError(
            "Wrong resource", "AuthorizationResourceTypeMismatch"
        )
        assert error4.error_code == "AuthorizationResourceTypeMismatch"


class TestSASValidatorInitialization:
    """Test SAS validator initialization."""

    def test_validator_initialization(self, account_key):
        """Test validator initializes with account name and key."""
        validator = SASValidator(
            account_name="testaccount", account_key=account_key
        )

        assert validator.account_name == "testaccount"
        assert validator.account_key == account_key
        assert validator.account_key_bytes is not None

    def test_validator_invalid_key_format(self):
        """Test validator rejects invalid account key format."""
        with pytest.raises(ValueError) as exc_info:
            SASValidator(
                account_name="testaccount", account_key="not-base64!@#$"
            )

        assert "Invalid account key format" in str(exc_info.value)
