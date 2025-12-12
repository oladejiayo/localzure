"""
Mock OAuth 2.0 / OIDC Authority for LocalZure.

Provides JWT token generation and validation for testing Azure SDK authentication flows.

Author: LocalZure Team
Date: 2025-12-12
"""

from localzure.auth.oauth.token_issuer import (
    TokenIssuer,
    TokenRequest,
    TokenResponse,
    JWKSResponse,
    OpenIDConfiguration,
)
from localzure.auth.oauth.token_validator import (
    TokenValidator,
    TokenClaims,
    ValidationResult,
)
from localzure.auth.oauth.exceptions import (
    OAuthError,
    InvalidGrantError,
    InvalidClientError,
    InvalidScopeError,
    InvalidTokenError,
    TokenExpiredError,
    InvalidSignatureError,
)

__all__ = [
    # Token Issuer
    "TokenIssuer",
    "TokenRequest",
    "TokenResponse",
    "JWKSResponse",
    "OpenIDConfiguration",
    # Token Validator
    "TokenValidator",
    "TokenClaims",
    "ValidationResult",
    # Exceptions
    "OAuthError",
    "InvalidGrantError",
    "InvalidClientError",
    "InvalidScopeError",
    "InvalidTokenError",
    "TokenExpiredError",
    "InvalidSignatureError",
]
