"""Hostname mapping and URL rewriting for Azure service endpoints.

This module provides hostname-to-localhost mapping for Azure SDKs,
rewriting Azure service URLs to LocalZure endpoints while preserving
paths, query parameters, and original host information.
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional, Pattern
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


@dataclass
class HostnamePattern:
    """Azure hostname pattern with corresponding local endpoint."""

    pattern: Pattern[str]
    local_base: str
    service_name: str


@dataclass
class MappingResult:
    """Result of hostname mapping and URL rewriting."""

    mapped_url: str
    original_host: str
    service_name: str
    account_or_namespace: Optional[str] = None


class HostnameMapper:
    """Maps Azure service hostnames to LocalZure endpoints and rewrites URLs.

    Handles hostname mapping for all major Azure services, preserving path
    and query parameters while rewriting the base URL to localhost endpoints.

    Example:
        mapper = HostnameMapper()
        result = mapper.map_url("https://myaccount.blob.core.windows.net/container/blob?sv=2021-06-08")
        # result.mapped_url = "http://localhost:10000/myaccount/container/blob?sv=2021-06-08"
        # result.original_host = "myaccount.blob.core.windows.net"
        # result.service_name = "blob"
        # result.account_or_namespace = "myaccount"
    """

    def __init__(self, custom_mappings: Optional[Dict[str, str]] = None):
        """Initialize hostname mapper with default and custom patterns.

        Args:
            custom_mappings: Optional dictionary of custom hostname patterns
                            to local endpoints (e.g., {"custom.domain.com": "http://localhost:9000"})
        """
        self._patterns: list[HostnamePattern] = []
        self._custom_mappings = custom_mappings or {}

        # Initialize default Azure service patterns
        self._init_default_patterns()

    def _init_default_patterns(self) -> None:
        """Initialize default Azure service hostname patterns."""
        # Blob Storage: <account>.blob.core.windows.net -> localhost:10000/<account>
        self._patterns.append(
            HostnamePattern(
                pattern=re.compile(r"^(?P<account>[\w\-]+)\.blob\.core\.windows\.net$", re.IGNORECASE),
                local_base="http://localhost:10000",
                service_name="blob",
            )
        )

        # Queue Storage: <account>.queue.core.windows.net -> localhost:10001/<account>
        self._patterns.append(
            HostnamePattern(
                pattern=re.compile(r"^(?P<account>[\w\-]+)\.queue\.core\.windows\.net$", re.IGNORECASE),
                local_base="http://localhost:10001",
                service_name="queue",
            )
        )

        # Table Storage: <account>.table.core.windows.net -> localhost:10002/<account>
        self._patterns.append(
            HostnamePattern(
                pattern=re.compile(r"^(?P<account>[\w\-]+)\.table\.core\.windows\.net$", re.IGNORECASE),
                local_base="http://localhost:10002",
                service_name="table",
            )
        )

        # Service Bus: <namespace>.servicebus.windows.net -> localhost:5672
        self._patterns.append(
            HostnamePattern(
                pattern=re.compile(r"^(?P<namespace>[\w\-]+)\.servicebus\.windows\.net$", re.IGNORECASE),
                local_base="http://localhost:5672",
                service_name="servicebus",
            )
        )

        # Key Vault: <vault>.vault.azure.net -> localhost:8200/<vault>
        self._patterns.append(
            HostnamePattern(
                pattern=re.compile(r"^(?P<vault>[\w\-]+)\.vault\.azure\.net$", re.IGNORECASE),
                local_base="http://localhost:8200",
                service_name="keyvault",
            )
        )

        # Cosmos DB: <account>.documents.azure.com -> localhost:8081/<account>
        self._patterns.append(
            HostnamePattern(
                pattern=re.compile(r"^(?P<account>[\w\-]+)\.documents\.azure\.com$", re.IGNORECASE),
                local_base="http://localhost:8081",
                service_name="cosmosdb",
            )
        )

    def map_url(self, url: str) -> Optional[MappingResult]:
        """Map Azure service URL to LocalZure endpoint.

        Rewrites the hostname and base URL while preserving:
        - Path components
        - Query parameters
        - URL fragments

        The original host is stored in the result for header preservation.

        Args:
            url: Full Azure service URL (e.g., "https://account.blob.core.windows.net/container")

        Returns:
            MappingResult with mapped URL and metadata, or None if no pattern matches

        Example:
            >>> mapper = HostnameMapper()
            >>> result = mapper.map_url("https://test.blob.core.windows.net/container/blob?sv=2021-06-08")
            >>> result.mapped_url
            'http://localhost:10000/test/container/blob?sv=2021-06-08'
            >>> result.original_host
            'test.blob.core.windows.net'
            >>> result.service_name
            'blob'
        """
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return None

        # Check custom mappings first (exact match)
        if hostname in self._custom_mappings:
            mapped_base = self._custom_mappings[hostname]
            mapped_url = self._build_mapped_url(mapped_base, parsed)
            return MappingResult(
                mapped_url=mapped_url,
                original_host=hostname,
                service_name="custom",
                account_or_namespace=None,
            )

        # Check default Azure patterns
        for pattern_info in self._patterns:
            match = pattern_info.pattern.match(hostname)
            if match:
                # Extract account/namespace/vault name from hostname
                groups = match.groupdict()
                identifier = next(iter(groups.values())) if groups else None

                # Build mapped URL with account/namespace in path
                if identifier and pattern_info.service_name != "servicebus":
                    # Most services: include account in path (e.g., /myaccount/container/blob)
                    base_with_account = f"{pattern_info.local_base}/{identifier}"
                    mapped_url = self._build_mapped_url(base_with_account, parsed)
                else:
                    # Service Bus: no account in path (single namespace per port)
                    mapped_url = self._build_mapped_url(pattern_info.local_base, parsed)

                return MappingResult(
                    mapped_url=mapped_url,
                    original_host=hostname,
                    service_name=pattern_info.service_name,
                    account_or_namespace=identifier,
                )

        # No pattern matched
        return None

    def _build_mapped_url(self, base_url: str, parsed_original: urlparse) -> str:
        """Build mapped URL by combining local base with original path and query.

        Args:
            base_url: Local base URL (e.g., "http://localhost:10000/myaccount")
            parsed_original: Parsed original URL

        Returns:
            Complete mapped URL with path, query, and fragment preserved
        """
        # Parse the base URL
        parsed_base = urlparse(base_url)

        # Combine paths: base path + original path
        if parsed_base.path and parsed_base.path != "/":
            combined_path = parsed_base.path.rstrip("/") + "/" + parsed_original.path.lstrip("/")
        else:
            combined_path = parsed_original.path

        # Normalize path (remove double slashes)
        combined_path = re.sub(r"//+", "/", combined_path)

        # Build new URL with preserved query and fragment
        mapped = urlunparse(
            (
                parsed_base.scheme,  # http
                parsed_base.netloc,  # localhost:10000
                combined_path,  # /myaccount/container/blob
                parsed_original.params,  # URL params (rarely used)
                parsed_original.query,  # sv=2021-06-08&...
                parsed_original.fragment,  # URL fragment
            )
        )

        return mapped

    def get_original_host_header(self, original_host: str) -> Dict[str, str]:
        """Generate header preserving original Azure hostname.

        Azure SDKs may validate the Host header for signature verification.
        This method generates the X-Original-Host header for middleware to use.

        Args:
            original_host: Original Azure hostname (e.g., "myaccount.blob.core.windows.net")

        Returns:
            Dictionary with X-Original-Host header

        Example:
            >>> mapper = HostnameMapper()
            >>> headers = mapper.get_original_host_header("test.blob.core.windows.net")
            >>> headers
            {'X-Original-Host': 'test.blob.core.windows.net'}
        """
        return {"X-Original-Host": original_host}

    def add_custom_mapping(self, hostname: str, local_endpoint: str) -> None:
        """Add a custom hostname mapping.

        Allows configuration of custom domains or non-standard Azure endpoints.

        Args:
            hostname: Custom hostname to map (e.g., "custom.domain.com")
            local_endpoint: Local endpoint to map to (e.g., "http://localhost:9000")

        Example:
            >>> mapper = HostnameMapper()
            >>> mapper.add_custom_mapping("custom.blob.example.com", "http://localhost:11000")
        """
        self._custom_mappings[hostname] = local_endpoint

    def remove_custom_mapping(self, hostname: str) -> bool:
        """Remove a custom hostname mapping.

        Args:
            hostname: Custom hostname to remove

        Returns:
            True if mapping was removed, False if it didn't exist
        """
        if hostname in self._custom_mappings:
            del self._custom_mappings[hostname]
            return True
        return False

    def list_supported_services(self) -> list[str]:
        """List all supported Azure service names.

        Returns:
            List of service names (e.g., ["blob", "queue", "table", ...])
        """
        return [pattern.service_name for pattern in self._patterns]

    def get_service_info(self, service_name: str) -> Optional[Dict[str, str]]:
        """Get mapping information for a specific service.

        Args:
            service_name: Name of the service (e.g., "blob", "queue")

        Returns:
            Dictionary with pattern and local_base, or None if service not found
        """
        for pattern in self._patterns:
            if pattern.service_name == service_name:
                return {
                    "service_name": pattern.service_name,
                    "pattern": pattern.pattern.pattern,
                    "local_base": pattern.local_base,
                }
        return None
