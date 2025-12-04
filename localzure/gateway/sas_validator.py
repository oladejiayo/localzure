"""SAS (Shared Access Signature) token validation for Azure Storage services.

This module provides validation for SAS tokens used in Azure Storage API requests,
including signature verification, time-based validation, and permission checking.
"""

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Set
from urllib.parse import parse_qs, unquote, urlparse


class SASPermission(str, Enum):
    """SAS permission flags."""

    READ = "r"
    WRITE = "w"
    DELETE = "d"
    LIST = "l"
    ADD = "a"
    CREATE = "c"
    UPDATE = "u"
    PROCESS = "p"


class SASResourceType(str, Enum):
    """SAS resource type flags."""

    SERVICE = "s"
    CONTAINER = "c"
    OBJECT = "o"


class SASService(str, Enum):
    """SAS service type flags."""

    BLOB = "b"
    QUEUE = "q"
    TABLE = "t"
    FILE = "f"


class SASValidationError(Exception):
    """Base exception for SAS validation errors."""

    def __init__(self, message: str, error_code: str = "AuthenticationFailed"):
        """Initialize SAS validation error.

        Args:
            message: Human-readable error message
            error_code: Azure-compatible error code
        """
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass
class SASToken:
    """Parsed SAS token representation."""

    signed_version: str  # sv
    signed_services: str  # ss
    signed_resource_types: str  # srt
    signed_permissions: str  # sp
    signed_expiry: str  # se
    signed_start: Optional[str]  # st
    signature: str  # sig
    signed_protocol: Optional[str] = None  # spr
    signed_ip: Optional[str] = None  # sip
    raw_params: Dict[str, str] = None  # All query parameters

    def __post_init__(self):
        """Validate required fields are present."""
        if not all(
            [
                self.signed_version,
                self.signed_services,
                self.signed_resource_types,
                self.signed_permissions,
                self.signed_expiry,
                self.signature,
            ]
        ):
            raise SASValidationError(
                "Missing required SAS parameters", "InvalidQueryParameterValue"
            )


class SASValidator:
    """Validator for SAS tokens in Azure Storage requests."""

    def __init__(self, account_name: str, account_key: str):
        """Initialize SAS validator.

        Args:
            account_name: Storage account name
            account_key: Storage account key (base64-encoded)
        """
        self.account_name = account_name
        self.account_key = account_key
        # Decode the base64 account key for HMAC operations
        try:
            self.account_key_bytes = base64.b64decode(account_key)
        except Exception as exc:
            raise ValueError("Invalid account key format") from exc

    def parse_sas_token(self, url: str) -> SASToken:
        """Parse SAS token from URL query parameters.

        Args:
            url: Full URL with SAS query parameters

        Returns:
            Parsed SASToken object

        Raises:
            SASValidationError: If required parameters are missing
        """
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Extract single values from query params
        def get_param(key: str, required: bool = True) -> Optional[str]:
            values = params.get(key, [])
            if not values:
                if required:
                    raise SASValidationError(
                        f"Missing required SAS parameter: {key}",
                        "InvalidQueryParameterValue",
                    )
                return None
            return values[0]

        # Build raw params dict for string-to-sign
        raw_params = {}
        for key, values in params.items():
            if values:
                raw_params[key] = values[0]

        return SASToken(
            signed_version=get_param("sv"),
            signed_services=get_param("ss"),
            signed_resource_types=get_param("srt"),
            signed_permissions=get_param("sp"),
            signed_expiry=get_param("se"),
            signed_start=get_param("st", required=False),
            signature=get_param("sig"),
            signed_protocol=get_param("spr", required=False),
            signed_ip=get_param("sip", required=False),
            raw_params=raw_params,
        )

    def validate_signature(
        self, sas_token: SASToken, url: str = None  # pylint: disable=unused-argument
    ) -> None:
        """Validate SAS signature using HMAC-SHA256.

        Args:
            sas_token: Parsed SAS token
            url: Original request URL (reserved for future service SAS validation)

        Raises:
            SASValidationError: If signature is invalid
        """
        # Build string to sign for account SAS
        string_to_sign = self._build_string_to_sign(sas_token)

        # Compute expected signature
        expected_sig = base64.b64encode(
            hmac.new(
                self.account_key_bytes,
                string_to_sign.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        # URL-decode the provided signature for comparison
        provided_sig = unquote(sas_token.signature)

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise SASValidationError(
                "Signature mismatch", "AuthenticationFailed"
            )

    def _build_string_to_sign(self, sas_token: SASToken) -> str:
        """Build the string to sign for account SAS validation.

        Format for account SAS (version 2015-04-05 and later):
        accountname\n
        signedpermissions\n
        signedservice\n
        signedresourcetype\n
        signedstart\n
        signedexpiry\n
        signedIP\n
        signedProtocol\n
        signedversion

        Args:
            sas_token: Parsed SAS token

        Returns:
            String to sign
        """
        # Account SAS string to sign format
        parts = [
            self.account_name,
            sas_token.signed_permissions,
            sas_token.signed_services,
            sas_token.signed_resource_types,
            sas_token.signed_start or "",
            sas_token.signed_expiry,
            sas_token.signed_ip or "",
            sas_token.signed_protocol or "",
            sas_token.signed_version,
        ]

        return "\n".join(parts)

    def validate_expiry(self, sas_token: SASToken) -> None:
        """Validate SAS token expiry time.

        Args:
            sas_token: Parsed SAS token

        Raises:
            SASValidationError: If token is expired
        """
        try:
            expiry = datetime.fromisoformat(
                sas_token.signed_expiry.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise SASValidationError(
                "Invalid expiry time format", "InvalidQueryParameterValue"
            ) from exc

        now = datetime.now(timezone.utc)
        if now >= expiry:
            raise SASValidationError(
                "SAS token has expired", "AuthenticationFailed"
            )

    def validate_start_time(self, sas_token: SASToken) -> None:
        """Validate SAS token start time if present.

        Args:
            sas_token: Parsed SAS token

        Raises:
            SASValidationError: If current time is before start time
        """
        if not sas_token.signed_start:
            return

        try:
            start = datetime.fromisoformat(
                sas_token.signed_start.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise SASValidationError(
                "Invalid start time format", "InvalidQueryParameterValue"
            ) from exc

        now = datetime.now(timezone.utc)
        if now < start:
            raise SASValidationError(
                "SAS token not yet valid", "AuthenticationFailed"
            )

    def validate_permissions(
        self, sas_token: SASToken, required_permission: SASPermission
    ) -> None:
        """Validate that SAS token has required permission.

        Args:
            sas_token: Parsed SAS token
            required_permission: Permission required for the operation

        Raises:
            SASValidationError: If required permission is not present
        """
        granted_permissions = set(sas_token.signed_permissions)
        if required_permission.value not in granted_permissions:
            raise SASValidationError(
                f"SAS token lacks required permission: {required_permission.value}",
                "AuthorizationPermissionMismatch",
            )

    def validate_resource_types(
        self, sas_token: SASToken, required_resource_type: SASResourceType
    ) -> None:
        """Validate that SAS token allows required resource type.

        Args:
            sas_token: Parsed SAS token
            required_resource_type: Resource type required for the operation

        Raises:
            SASValidationError: If required resource type is not allowed
        """
        allowed_types = set(sas_token.signed_resource_types)
        if required_resource_type.value not in allowed_types:
            raise SASValidationError(
                f"SAS token does not allow resource type: {required_resource_type.value}",
                "AuthorizationResourceTypeMismatch",
            )

    def validate_services(
        self, sas_token: SASToken, required_service: SASService
    ) -> None:
        """Validate that SAS token allows required service.

        Args:
            sas_token: Parsed SAS token
            required_service: Service type required for the operation

        Raises:
            SASValidationError: If required service is not allowed
        """
        allowed_services = set(sas_token.signed_services)
        if required_service.value not in allowed_services:
            raise SASValidationError(
                f"SAS token does not allow service: {required_service.value}",
                "AuthorizationServiceMismatch",
            )

    def validate(
        self,
        url: str,
        *,
        required_permission: SASPermission,
        required_resource_type: SASResourceType,
        required_service: SASService,
    ) -> SASToken:
        """Perform complete SAS token validation.

        Args:
            url: Full URL with SAS query parameters
            required_permission: Permission required for the operation
            required_resource_type: Resource type required for the operation
            required_service: Service type required for the operation

        Returns:
            Validated SASToken object

        Raises:
            SASValidationError: If any validation check fails
        """
        # AC1: Parse SAS token from query parameters
        sas_token = self.parse_sas_token(url)

        # AC2: Validate SAS signature using account key
        self.validate_signature(sas_token, url)

        # AC3: Check SAS expiration time
        self.validate_expiry(sas_token)

        # AC4: Check SAS start time if present
        self.validate_start_time(sas_token)

        # AC5: Check SAS permissions against request operation
        self.validate_permissions(sas_token, required_permission)

        # AC6: Validate allowed resource types
        self.validate_resource_types(sas_token, required_resource_type)

        # Validate allowed services
        self.validate_services(sas_token, required_service)

        return sas_token


def get_permission_for_method(http_method: str) -> SASPermission:
    """Map HTTP method to required SAS permission.

    Args:
        http_method: HTTP method (GET, PUT, POST, DELETE, HEAD)

    Returns:
        Required SAS permission

    Raises:
        ValueError: If method cannot be mapped
    """
    method_map = {
        "GET": SASPermission.READ,
        "HEAD": SASPermission.READ,
        "PUT": SASPermission.WRITE,
        "POST": SASPermission.ADD,
        "DELETE": SASPermission.DELETE,
    }

    method_upper = http_method.upper()
    if method_upper not in method_map:
        raise ValueError(f"Unsupported HTTP method: {http_method}")

    return method_map[method_upper]
