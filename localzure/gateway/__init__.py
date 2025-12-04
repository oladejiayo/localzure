"""Gateway module for LocalZure.

This module provides URL rewriting, hostname mapping, request routing,
authentication validation, and protocol routing for Azure SDK traffic
to local service endpoints.
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
from localzure.gateway.sas_validator import (
    SASValidator,
    SASToken,
    SASPermission,
    SASResourceType,
    SASService,
    SASValidationError,
    get_permission_for_method,
)
from localzure.gateway.protocol_router import (
    ProtocolRouter,
    ProtocolType,
    ProtocolError,
    ProtocolDetector,
    ProtocolContext,
    ConnectionState,
    format_protocol_error,
)
from localzure.gateway.retry_simulator import (
    RetrySimulator,
    TestModeConfig,
    FailurePattern,
    RetryAfterFormat,
    FailureInjectionResult,
    create_error_response,
    parse_test_mode_config,
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
    "SASValidator",
    "SASToken",
    "SASPermission",
    "SASResourceType",
    "SASService",
    "SASValidationError",
    "get_permission_for_method",
    "ProtocolRouter",
    "ProtocolType",
    "ProtocolError",
    "ProtocolDetector",
    "ProtocolContext",
    "ConnectionState",
    "format_protocol_error",
    "RetrySimulator",
    "TestModeConfig",
    "FailurePattern",
    "RetryAfterFormat",
    "FailureInjectionResult",
    "create_error_response",
    "parse_test_mode_config",
]
