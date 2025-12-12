"""
LocalZure Authentication Module.

Provides authentication and authorization mechanisms for Azure-compatible services.
Supports SharedKey, SAS tokens, and OAuth/OIDC.

Author: LocalZure Team
Date: 2025-12-12
"""

from localzure.auth.exceptions import (
    AuthenticationError,
    AuthenticationFailedError,
    InvalidAuthorizationHeaderError,
    SignatureMismatchError,
    ClockSkewError,
)
from localzure.auth.sharedkey import (
    SharedKeyAuthenticator,
    SharedKeyCredentials,
    parse_authorization_header,
    build_canonical_string,
    compute_signature,
)

__all__ = [
    # Exceptions
    "AuthenticationError",
    "AuthenticationFailedError",
    "InvalidAuthorizationHeaderError",
    "SignatureMismatchError",
    "ClockSkewError",
    # SharedKey Auth
    "SharedKeyAuthenticator",
    "SharedKeyCredentials",
    "parse_authorization_header",
    "build_canonical_string",
    "compute_signature",
]
