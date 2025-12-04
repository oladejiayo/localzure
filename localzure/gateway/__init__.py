"""Gateway module for LocalZure.

This module provides URL rewriting, hostname mapping, and request routing
for Azure SDK traffic to local service endpoints.
"""

from localzure.gateway.hostname_mapper import (
    HostnameMapper,
    MappingResult,
    HostnamePattern,
)
from localzure.gateway.canonicalizer import (
    RequestCanonicalizer,
    CanonicalizedRequest,
    CanonicalVersion,
    ServiceType,
    parse_authorization_header,
)

__all__ = [
    "HostnameMapper",
    "MappingResult",
    "HostnamePattern",
    "RequestCanonicalizer",
    "CanonicalizedRequest",
    "CanonicalVersion",
    "ServiceType",
    "parse_authorization_header",
]
