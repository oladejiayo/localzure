"""
SharedKey Authentication implementation for Azure-compatible services.

Implements the SharedKey authentication scheme according to Azure specifications:
- 2009-09-19 (legacy)
- 2015-04-05 (current)

Reference: https://docs.microsoft.com/en-us/rest/api/storageservices/authorize-with-shared-key

Author: LocalZure Team
Date: 2025-12-12
"""

import base64
import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from localzure.auth.exceptions import (
    AuthenticationFailedError,
    ClockSkewError,
    InvalidAuthorizationHeaderError,
    SignatureMismatchError,
)

logger = logging.getLogger(__name__)


@dataclass
class SharedKeyCredentials:
    """Credentials for SharedKey authentication."""
    
    account_name: str
    account_key: str  # Base64-encoded


class SharedKeyAuthenticator:
    """
    Validates SharedKey authentication for Azure-compatible requests.
    
    Supports both legacy (2009-09-19) and current (2015-04-05) canonicalization formats.
    """
    
    # Default clock skew tolerance (15 minutes)
    DEFAULT_CLOCK_SKEW_SECONDS = 15 * 60
    
    # Supported API versions and their canonicalization formats
    CANONICALIZATION_VERSIONS = {
        "2009-09-19": "legacy",
        "2015-04-05": "current",
        "2016-05-31": "current",
        "2017-04-17": "current",
        "2017-07-29": "current",
        "2017-11-09": "current",
        "2018-03-28": "current",
        "2018-11-09": "current",
        "2019-02-02": "current",
        "2019-07-07": "current",
        "2019-12-12": "current",
        "2020-02-10": "current",
        "2020-04-08": "current",
        "2020-06-12": "current",
        "2020-08-04": "current",
        "2020-10-02": "current",
        "2021-02-12": "current",
        "2021-04-10": "current",
        "2021-06-08": "current",
        "2021-08-06": "current",
    }
    
    def __init__(
        self,
        credentials_store: Dict[str, str],
        clock_skew_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS
    ):
        """
        Initialize SharedKey authenticator.
        
        Args:
            credentials_store: Map of account_name -> base64_encoded_key
            clock_skew_seconds: Allowed clock skew tolerance in seconds
        """
        self.credentials_store = credentials_store
        self.clock_skew_seconds = clock_skew_seconds
    
    def authenticate(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        api_version: Optional[str] = None
    ) -> SharedKeyCredentials:
        """
        Authenticate a request using SharedKey.
        
        Args:
            method: HTTP method (GET, PUT, etc.)
            url: Full request URL
            headers: Request headers (case-insensitive dict)
            api_version: API version (from x-ms-version header or query param)
        
        Returns:
            SharedKeyCredentials if authentication succeeds
        
        Raises:
            InvalidAuthorizationHeaderError: If Authorization header is malformed
            AuthenticationFailedError: If account not found
            SignatureMismatchError: If signature doesn't match
            ClockSkewError: If timestamp is outside allowed window
        """
        # Normalize headers to lowercase keys
        headers_lower = {k.lower(): v for k, v in headers.items()}
        
        # Extract Authorization header
        auth_header = headers_lower.get("authorization")
        if not auth_header:
            raise InvalidAuthorizationHeaderError("Authorization header is missing")
        
        # Parse authorization header
        account_name, provided_signature = parse_authorization_header(auth_header)
        
        # Get account key
        account_key = self.credentials_store.get(account_name)
        if not account_key:
            logger.warning(f"Account not found: {account_name}")
            raise AuthenticationFailedError(
                f"Server failed to authenticate the request. Account '{account_name}' not found."
            )
        
        # Validate timestamp (clock skew)
        self._validate_timestamp(headers_lower)
        
        # Determine canonicalization version
        if api_version is None:
            api_version = headers_lower.get("x-ms-version", "2015-04-05")
        
        canon_version = self.CANONICALIZATION_VERSIONS.get(api_version, "current")
        
        # Build canonical string
        canonical_string = build_canonical_string(
            method=method,
            url=url,
            headers=headers_lower,
            account_name=account_name,
            version=canon_version
        )
        
        # Compute expected signature
        expected_signature = compute_signature(canonical_string, account_key)
        
        # Compare signatures (constant-time comparison)
        if not self._constant_time_compare(provided_signature, expected_signature):
            logger.warning(
                f"Signature mismatch for account {account_name}. "
                f"Expected: {expected_signature[:20]}..., Got: {provided_signature[:20]}..."
            )
            raise SignatureMismatchError(
                "Server failed to authenticate the request. "
                "Signature mismatch."
            )
        
        logger.info(f"SharedKey authentication successful for account: {account_name}")
        return SharedKeyCredentials(account_name=account_name, account_key=account_key)
    
    def _validate_timestamp(self, headers: Dict[str, str]) -> None:
        """
        Validate request timestamp is within allowed clock skew.
        
        Args:
            headers: Request headers (lowercase keys)
        
        Raises:
            ClockSkewError: If timestamp is outside allowed window
        """
        # x-ms-date takes precedence over Date header
        date_str = headers.get("x-ms-date") or headers.get("date")
        
        if not date_str:
            # No date header - allow it (some requests may not require it)
            return
        
        try:
            # Parse date string (RFC 1123 format)
            request_time = datetime.strptime(
                date_str, "%a, %d %b %Y %H:%M:%S GMT"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            # Try ISO 8601 format
            try:
                request_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Invalid date format: {date_str}")
                raise ClockSkewError(f"Invalid date format: {date_str}")
        
        current_time = datetime.now(timezone.utc)
        time_diff = abs((current_time - request_time).total_seconds())
        
        if time_diff > self.clock_skew_seconds:
            raise ClockSkewError(
                f"Request timestamp is outside allowed clock skew window. "
                f"Diff: {time_diff:.0f}s, Allowed: {self.clock_skew_seconds}s"
            )
    
    @staticmethod
    def _constant_time_compare(a: str, b: str) -> bool:
        """
        Constant-time string comparison to prevent timing attacks.
        
        Args:
            a: First string
            b: Second string
        
        Returns:
            True if strings are equal
        """
        if len(a) != len(b):
            return False
        
        result = 0
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)
        
        return result == 0


def parse_authorization_header(auth_header: str) -> Tuple[str, str]:
    """
    Parse SharedKey Authorization header.
    
    Expected format: "SharedKey account:signature"
    
    Args:
        auth_header: Authorization header value
    
    Returns:
        Tuple of (account_name, signature)
    
    Raises:
        InvalidAuthorizationHeaderError: If header is malformed
    """
    parts = auth_header.strip().split(maxsplit=1)
    
    if len(parts) != 2:
        raise InvalidAuthorizationHeaderError(
            "Authorization header must be in format: SharedKey account:signature"
        )
    
    scheme, credentials = parts
    
    if scheme.lower() != "sharedkey":
        raise InvalidAuthorizationHeaderError(
            f"Expected SharedKey scheme, got: {scheme}"
        )
    
    if ":" not in credentials:
        raise InvalidAuthorizationHeaderError(
            "Credentials must be in format: account:signature"
        )
    
    account_name, signature = credentials.split(":", 1)
    
    if not account_name or not signature:
        raise InvalidAuthorizationHeaderError(
            "Account name and signature cannot be empty"
        )
    
    return account_name, signature


def build_canonical_string(
    method: str,
    url: str,
    headers: Dict[str, str],
    account_name: str,
    version: str = "current"
) -> str:
    """
    Build canonical string for SharedKey signature computation.
    
    Args:
        method: HTTP method (uppercase)
        url: Full request URL
        headers: Request headers (lowercase keys)
        account_name: Storage account name
        version: Canonicalization version ("legacy" or "current")
    
    Returns:
        Canonical string for signing
    """
    if version == "legacy":
        return _build_canonical_string_legacy(method, url, headers, account_name)
    else:
        return _build_canonical_string_current(method, url, headers, account_name)


def _build_canonical_string_current(
    method: str,
    url: str,
    headers: Dict[str, str],
    account_name: str
) -> str:
    """
    Build canonical string using 2015-04-05 format.
    
    Format:
        VERB\n
        Content-Encoding\n
        Content-Language\n
        Content-Length\n
        Content-MD5\n
        Content-Type\n
        Date\n
        If-Modified-Since\n
        If-Match\n
        If-None-Match\n
        If-Unmodified-Since\n
        Range\n
        CanonicalizedHeaders\n
        CanonicalizedResource
    """
    parts = [
        method.upper(),
        headers.get("content-encoding", ""),
        headers.get("content-language", ""),
        _get_content_length(headers),
        headers.get("content-md5", ""),
        headers.get("content-type", ""),
        "",  # Date - left empty if x-ms-date is present
        headers.get("if-modified-since", ""),
        headers.get("if-match", ""),
        headers.get("if-none-match", ""),
        headers.get("if-unmodified-since", ""),
        headers.get("range", ""),
    ]
    
    # Add CanonicalizedHeaders
    canonicalized_headers = _build_canonicalized_headers(headers)
    parts.append(canonicalized_headers)
    
    # Add CanonicalizedResource
    canonicalized_resource = _build_canonicalized_resource(url, account_name)
    parts.append(canonicalized_resource)
    
    return "\n".join(parts)


def _build_canonical_string_legacy(
    method: str,
    url: str,
    headers: Dict[str, str],
    account_name: str
) -> str:
    """
    Build canonical string using legacy 2009-09-19 format.
    
    Format:
        VERB\n
        Content-Encoding\n
        Content-Language\n
        Content-Length\n
        Content-MD5\n
        Content-Type\n
        Date\n
        If-Modified-Since\n
        If-Match\n
        If-None-Match\n
        If-Unmodified-Since\n
        Range\n
        CanonicalizedHeaders\n
        CanonicalizedResource
    """
    # Legacy format is same as current for most cases
    return _build_canonical_string_current(method, url, headers, account_name)


def _get_content_length(headers: Dict[str, str]) -> str:
    """
    Get Content-Length header value, handling special cases.
    
    Args:
        headers: Request headers
    
    Returns:
        Content-Length value or empty string
    """
    content_length = headers.get("content-length", "")
    
    # Empty Content-Length should be represented as empty string
    if content_length == "0":
        return ""
    
    return content_length


def _build_canonicalized_headers(headers: Dict[str, str]) -> str:
    """
    Build CanonicalizedHeaders string.
    
    Rules:
    1. Include all headers starting with "x-ms-"
    2. Sort headers alphabetically by name
    3. Format: "header-name:value\n"
    4. Trim whitespace from values
    5. Unfold multi-line headers
    
    Args:
        headers: Request headers (lowercase keys)
    
    Returns:
        Canonicalized headers string
    """
    # Filter x-ms- headers
    ms_headers = {k: v for k, v in headers.items() if k.startswith("x-ms-")}
    
    # Sort by header name
    sorted_headers = sorted(ms_headers.items())
    
    # Build canonical string
    lines = []
    for name, value in sorted_headers:
        # Trim whitespace and unfold
        value = " ".join(value.split())
        lines.append(f"{name}:{value}")
    
    return "\n".join(lines)


def _build_canonicalized_resource(url: str, account_name: str) -> str:
    """
    Build CanonicalizedResource string.
    
    Format:
        /account-name/resource-path
        param1:value1
        param2:value2
    
    Rules:
    1. Start with /account-name
    2. Append URL path (decoded)
    3. Append query parameters (sorted, lowercase names, decoded values)
    
    Args:
        url: Full request URL
        account_name: Storage account name
    
    Returns:
        Canonicalized resource string
    """
    parsed = urlparse(url)
    
    # Start with /account-name/path
    resource = f"/{account_name}{parsed.path}"
    
    # Parse and sort query parameters
    if parsed.query:
        params = _parse_query_string(parsed.query)
        sorted_params = sorted(params.items())
        
        # Append parameters
        param_lines = [f"{name}:{value}" for name, value in sorted_params]
        if param_lines:
            resource += "\n" + "\n".join(param_lines)
    
    return resource


def _parse_query_string(query: str) -> Dict[str, str]:
    """
    Parse query string into dict with special Azure rules.
    
    Rules:
    1. Parameter names are lowercase
    2. Values are URL-decoded
    3. Multiple values are comma-separated
    
    Args:
        query: Query string
    
    Returns:
        Dict of parameter name -> value
    """
    params: Dict[str, List[str]] = {}
    
    for param in query.split("&"):
        if "=" not in param:
            continue
        
        name, value = param.split("=", 1)
        name = unquote(name).lower()
        value = unquote(value)
        
        if name not in params:
            params[name] = []
        params[name].append(value)
    
    # Join multiple values with comma
    return {name: ",".join(values) for name, values in params.items()}


def compute_signature(canonical_string: str, account_key: str) -> str:
    """
    Compute HMAC-SHA256 signature.
    
    Signature = Base64(HMAC-SHA256(UTF8(StringToSign), Base64Decode(AccountKey)))
    
    Args:
        canonical_string: Canonical string to sign
        account_key: Base64-encoded account key
    
    Returns:
        Base64-encoded signature
    """
    # Decode account key
    key_bytes = base64.b64decode(account_key)
    
    # Compute HMAC-SHA256
    signature_bytes = hmac.new(
        key_bytes,
        canonical_string.encode("utf-8"),
        hashlib.sha256
    ).digest()
    
    # Encode as Base64
    signature = base64.b64encode(signature_bytes).decode("utf-8")
    
    return signature
