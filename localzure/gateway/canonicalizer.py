"""Request canonicalization engine for Azure SharedKey authentication.

This module implements Azure's canonicalization algorithms for building
canonical strings used in SharedKey signature validation. Supports multiple
Azure Storage versions and service types (Blob, Queue, Table).

Reference: https://docs.microsoft.com/azure/storage/common/storage-auth-aad
"""

import hmac
import hashlib
import base64
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from enum import Enum


class CanonicalVersion(str, Enum):
    """Supported Azure canonicalization versions."""
    VERSION_2009_09_19 = "2009-09-19"
    VERSION_2015_04_05 = "2015-04-05"
    VERSION_2019_02_02 = "2019-02-02"


class ServiceType(str, Enum):
    """Azure service types with different canonicalization rules."""
    BLOB = "blob"
    QUEUE = "queue"
    TABLE = "table"
    FILE = "file"


@dataclass
class CanonicalizedRequest:
    """Result of request canonicalization."""
    
    string_to_sign: str
    canonical_headers: str
    canonical_resource: str
    version: CanonicalVersion


class RequestCanonicalizer:
    """Canonicalize HTTP requests for Azure SharedKey authentication.
    
    Implements Azure Storage canonicalization algorithms for building
    the string-to-sign used in HMAC-SHA256 signature validation.
    
    Supports multiple versions:
    - 2009-09-19: Original Azure Storage version
    - 2015-04-05: Updated with additional headers
    - 2019-02-02: Latest version with full header support
    
    Example:
        canonicalizer = RequestCanonicalizer()
        result = canonicalizer.canonicalize(
            method="GET",
            url="https://myaccount.blob.core.windows.net/container/blob",
            headers={
                "x-ms-version": "2021-08-06",
                "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT"
            },
            account_name="myaccount"
        )
        # result.string_to_sign contains full canonical string
    """
    
    def __init__(self, version: CanonicalVersion = CanonicalVersion.VERSION_2019_02_02):
        """Initialize canonicalizer with specific version.
        
        Args:
            version: Azure canonicalization version to use (default: 2019-02-02)
        """
        self.version = version
    
    def canonicalize(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        account_name: str,
        *,
        service_type: ServiceType = ServiceType.BLOB
    ) -> CanonicalizedRequest:
        """Canonicalize an HTTP request for SharedKey authentication.
        
        Builds the string-to-sign according to Azure's canonicalization rules.
        The format varies by version and service type.
        
        Args:
            method: HTTP method (GET, PUT, POST, etc.)
            url: Full request URL
            headers: HTTP headers dictionary
            account_name: Azure storage account name
            service_type: Type of Azure service (blob, queue, table, file)
        
        Returns:
            CanonicalizedRequest with string-to-sign and components
            
        Example:
            >>> result = canonicalizer.canonicalize(
            ...     method="GET",
            ...     url="https://myaccount.blob.core.windows.net/container/blob",
            ...     headers={"x-ms-version": "2021-08-06"},
            ...     account_name="myaccount"
            ... )
            >>> print(result.string_to_sign)
        """
        # Normalize method to uppercase
        method = method.upper()
        
        # Build canonical headers
        canonical_headers = self._build_canonical_headers(headers)
        
        # Build canonical resource
        canonical_resource = self._build_canonical_resource(
            url, account_name, service_type
        )
        
        # Build string to sign based on version
        if service_type == ServiceType.TABLE:
            string_to_sign = self._build_table_string_to_sign(
                method, url, headers, canonical_resource
            )
        else:
            string_to_sign = self._build_storage_string_to_sign(
                method, headers, canonical_headers, canonical_resource
            )
        
        return CanonicalizedRequest(
            string_to_sign=string_to_sign,
            canonical_headers=canonical_headers,
            canonical_resource=canonical_resource,
            version=self.version
        )
    
    def _build_canonical_headers(self, headers: Dict[str, str]) -> str:
        """Build canonicalized headers string.
        
        Azure canonicalization rules:
        1. Include all headers starting with "x-ms-"
        2. Convert header names to lowercase
        3. Sort headers lexicographically by name
        4. Trim whitespace from values
        5. Replace multiple spaces with single space
        6. Format as "name:value\n"
        
        Args:
            headers: HTTP headers dictionary
        
        Returns:
            Canonicalized headers string
            
        Example:
            >>> headers = {
            ...     "X-MS-Version": "2021-08-06",
            ...     "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT",
            ...     "Content-Type": "application/json"
            ... }
            >>> result = self._build_canonical_headers(headers)
            >>> print(result)
            x-ms-date:Tue, 04 Dec 2025 10:30:00 GMT
            x-ms-version:2021-08-06
        """
        # Filter and normalize x-ms-* headers
        ms_headers: List[Tuple[str, str]] = []
        
        for name, value in headers.items():
            name_lower = name.lower()
            if name_lower.startswith("x-ms-"):
                # Normalize value: strip whitespace and collapse multiple spaces
                normalized_value = " ".join(str(value).split())
                ms_headers.append((name_lower, normalized_value))
        
        # Sort by header name
        ms_headers.sort(key=lambda x: x[0])
        
        # Build canonical string
        if not ms_headers:
            return ""
        
        return "\n".join(f"{name}:{value}" for name, value in ms_headers)
    
    def _build_canonical_resource(
        self,
        url: str,
        account_name: str,
        service_type: ServiceType  # pylint: disable=unused-argument
    ) -> str:
        """Build canonicalized resource string.
        
        Azure canonicalization rules:
        1. Start with "/<account-name>/<resource-path>"
        2. Include query parameters in sorted order
        3. Format query params as "name:value1,value2,..."
        4. Special handling for comp, etc.
        
        Args:
            url: Full request URL
            account_name: Azure storage account name
            service_type: Type of Azure service
        
        Returns:
            Canonicalized resource string
            
        Example:
            >>> url = "https://myaccount.blob.core.windows.net/container/blob?comp=metadata&timeout=30"
            >>> result = self._build_canonical_resource(url, "myaccount", ServiceType.BLOB)
            >>> print(result)
            /myaccount/container/blob
            comp:metadata
            timeout:30
        """
        parsed = urlparse(url)
        
        # Start with /<account-name><path>
        path = parsed.path or "/"
        canonical_resource = f"/{account_name}{path}"
        
        # Add query parameters for versions that support them
        if self.version in [CanonicalVersion.VERSION_2015_04_05, CanonicalVersion.VERSION_2019_02_02]:
            query_params = parse_qs(parsed.query, keep_blank_values=True)
            
            if query_params:
                # Sort parameters by name
                sorted_params = sorted(query_params.items())
                
                # Format each parameter
                param_lines = []
                for name, values in sorted_params:
                    # Convert name to lowercase
                    name_lower = name.lower()
                    # Join multiple values with comma
                    value_str = ",".join(str(v) for v in values)
                    param_lines.append(f"{name_lower}:{value_str}")
                
                # Append parameters to canonical resource
                if param_lines:
                    canonical_resource += "\n" + "\n".join(param_lines)
        
        return canonical_resource
    
    def _build_storage_string_to_sign(
        self,
        method: str,
        headers: Dict[str, str],
        canonical_headers: str,
        canonical_resource: str
    ) -> str:
        """Build string-to-sign for Blob, Queue, and File storage.
        
        Format (2015-04-05 and later):
        ```
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
        ```
        
        Args:
            method: HTTP method
            headers: HTTP headers dictionary
            canonical_headers: Pre-built canonical headers string
            canonical_resource: Pre-built canonical resource string
        
        Returns:
            String to sign
        """
        # Helper to get header value or empty string
        def get_header(name: str) -> str:
            # Check case-insensitive
            for key, value in headers.items():
                if key.lower() == name.lower():
                    return str(value) if value else ""
            return ""
        
        parts = [
            method,
            get_header("Content-Encoding"),
            get_header("Content-Language"),
            get_header("Content-Length"),
            get_header("Content-MD5"),
            get_header("Content-Type"),
            get_header("Date"),
            get_header("If-Modified-Since"),
            get_header("If-Match"),
            get_header("If-None-Match"),
            get_header("If-Unmodified-Since"),
            get_header("Range"),
            canonical_headers,
            canonical_resource
        ]
        
        return "\n".join(parts)
    
    def _build_table_string_to_sign(
        self,
        method: str,
        url: str,  # pylint: disable=unused-argument
        headers: Dict[str, str],
        canonical_resource: str
    ) -> str:
        """Build string-to-sign for Table storage.
        
        Table storage uses a simpler format:
        ```
        VERB\n
        Content-MD5\n
        Content-Type\n
        Date\n
        CanonicalizedResource
        ```
        
        Args:
            method: HTTP method
            url: Full request URL
            headers: HTTP headers dictionary
            canonical_resource: Pre-built canonical resource string
        
        Returns:
            String to sign for Table storage
        """
        # Helper to get header value or empty string
        def get_header(name: str) -> str:
            for key, value in headers.items():
                if key.lower() == name.lower():
                    return str(value) if value else ""
            return ""
        
        # Get x-ms-date if Date is not present
        date_value = get_header("Date")
        if not date_value:
            date_value = get_header("x-ms-date")
        
        parts = [
            method,
            get_header("Content-MD5"),
            get_header("Content-Type"),
            date_value,
            canonical_resource
        ]
        
        return "\n".join(parts)
    
    def compute_signature(
        self,
        string_to_sign: str,
        account_key: str
    ) -> str:
        """Compute HMAC-SHA256 signature for authentication.
        
        Args:
            string_to_sign: Canonical string to sign
            account_key: Base64-encoded storage account key
        
        Returns:
            Base64-encoded signature
            
        Example:
            >>> string_to_sign = "GET\\n\\n\\n...\\n/myaccount/container"
            >>> account_key = "YmFzZTY0a2V5"  # Base64-encoded key
            >>> signature = canonicalizer.compute_signature(string_to_sign, account_key)
        """
        # Decode the account key from base64
        decoded_key = base64.b64decode(account_key)
        
        # Compute HMAC-SHA256
        signature_bytes = hmac.new(
            decoded_key,
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Encode result as base64
        return base64.b64encode(signature_bytes).decode('utf-8')
    
    def validate_signature(
        self,
        *,
        method: str,
        url: str,
        headers: Dict[str, str],
        account_name: str,
        account_key: str,
        provided_signature: str,
        service_type: ServiceType = ServiceType.BLOB
    ) -> bool:
        """Validate a SharedKey signature.
        
        Args:
            method: HTTP method
            url: Full request URL
            headers: HTTP headers dictionary
            account_name: Azure storage account name
            account_key: Base64-encoded account key
            provided_signature: Signature from Authorization header
            service_type: Type of Azure service
        
        Returns:
            True if signature is valid, False otherwise
            
        Example:
            >>> valid = canonicalizer.validate_signature(
            ...     method="GET",
            ...     url="https://myaccount.blob.core.windows.net/container",
            ...     headers={"x-ms-version": "2021-08-06"},
            ...     account_name="myaccount",
            ...     account_key="YmFzZTY0a2V5",
            ...     provided_signature="expected_signature"
            ... )
        """
        # Canonicalize the request
        canonical_request = self.canonicalize(
            method=method,
            url=url,
            headers=headers,
            account_name=account_name,
            service_type=service_type
        )
        
        # Compute expected signature
        expected_signature = self.compute_signature(
            canonical_request.string_to_sign,
            account_key
        )
        
        # Compare signatures (constant-time comparison)
        return hmac.compare_digest(expected_signature, provided_signature)


def parse_authorization_header(auth_header: str) -> Optional[Dict[str, str]]:
    """Parse Azure SharedKey authorization header.
    
    Format: "SharedKey <account>:<signature>" or "SharedKeyLite <account>:<signature>"
    
    Args:
        auth_header: Authorization header value
    
    Returns:
        Dictionary with 'scheme', 'account', and 'signature', or None if invalid
        
    Example:
        >>> header = "SharedKey myaccount:xyz123=="
        >>> result = parse_authorization_header(header)
        >>> result['account']
        'myaccount'
        >>> result['signature']
        'xyz123=='
    """
    if not auth_header:
        return None
    
    parts = auth_header.split(' ', 1)
    if len(parts) != 2:
        return None
    
    scheme = parts[0]
    if scheme not in ['SharedKey', 'SharedKeyLite']:
        return None
    
    credentials = parts[1].split(':', 1)
    if len(credentials) != 2:
        return None
    
    return {
        'scheme': scheme,
        'account': credentials[0],
        'signature': credentials[1]
    }
