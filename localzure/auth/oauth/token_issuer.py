"""
JWT Token Issuer for Mock OAuth Authority.

Issues JWT tokens for testing Azure SDK authentication flows.

Author: LocalZure Team
Date: 2025-12-12
"""

import json
import logging
import secrets
from base64 import urlsafe_b64encode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from hashlib import sha256

import jwt

from localzure.auth.oauth.exceptions import (
    InvalidGrantError,
    InvalidClientError,
    InvalidScopeError,
)

logger = logging.getLogger(__name__)


@dataclass
class TokenRequest:
    """OAuth 2.0 token request."""
    
    grant_type: str
    scope: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    resource: Optional[str] = None


@dataclass
class TokenResponse:
    """OAuth 2.0 token response."""
    
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: Optional[str] = None


@dataclass
class JWK:
    """JSON Web Key."""
    
    kty: str  # Key type (RSA)
    use: str  # Public key use (sig)
    kid: str  # Key ID
    n: str  # Modulus
    e: str  # Exponent
    alg: str = "RS256"


@dataclass
class JWKSResponse:
    """JSON Web Key Set response."""
    
    keys: List[JWK]


@dataclass
class OpenIDConfiguration:
    """OpenID Connect configuration."""
    
    issuer: str
    token_endpoint: str
    jwks_uri: str
    response_types_supported: List[str]
    subject_types_supported: List[str]
    id_token_signing_alg_values_supported: List[str]


class TokenIssuer:
    """
    Issues JWT tokens for mock OAuth authority.
    
    Supports:
    - Client credentials flow
    - JWT token generation with RSA signature
    - JWKS endpoint for public key distribution
    - OpenID configuration discovery
    """
    
    SUPPORTED_GRANT_TYPES = ["client_credentials"]
    DEFAULT_TOKEN_LIFETIME = 3600  # 1 hour
    DEFAULT_ISSUER = "https://localzure.local"
    
    # Common Azure resource scopes
    DEFAULT_SCOPES = {
        "https://storage.azure.com/.default": "https://storage.azure.com",
        "https://vault.azure.net/.default": "https://vault.azure.net",
        "https://management.azure.com/.default": "https://management.azure.com",
        "https://graph.microsoft.com/.default": "https://graph.microsoft.com",
    }
    
    def __init__(
        self,
        issuer: str = DEFAULT_ISSUER,
        token_lifetime: int = DEFAULT_TOKEN_LIFETIME,
        private_key: Optional[bytes] = None,
        public_key: Optional[bytes] = None,
        key_id: Optional[str] = None,
    ):
        """
        Initialize token issuer.
        
        Args:
            issuer: Token issuer URL
            token_lifetime: Token lifetime in seconds
            private_key: RSA private key (PEM format), generates if None
            public_key: RSA public key (PEM format), generates if None
            key_id: Key ID for JWKS, generates if None
        """
        self.issuer = issuer
        self.token_lifetime = token_lifetime
        
        # Generate or load RSA keys
        if private_key is None or public_key is None:
            self._private_key, self._public_key = self._generate_rsa_keypair()
        else:
            self._private_key = serialization.load_pem_private_key(
                private_key, password=None, backend=default_backend()
            )
            self._public_key = serialization.load_pem_public_key(
                public_key, backend=default_backend()
            )
        
        # Generate or use provided key ID
        self.key_id = key_id or self._generate_key_id()
        
        logger.info(f"TokenIssuer initialized with issuer: {issuer}, key_id: {self.key_id}")
    
    def issue_token(self, request: TokenRequest) -> TokenResponse:
        """
        Issue JWT token for token request.
        
        Args:
            request: Token request
        
        Returns:
            Token response with JWT access token
        
        Raises:
            InvalidGrantError: If grant type is not supported
            InvalidScopeError: If scope is invalid
        """
        # Validate grant type
        if request.grant_type not in self.SUPPORTED_GRANT_TYPES:
            raise InvalidGrantError(
                f"Unsupported grant type: {request.grant_type}. "
                f"Supported: {', '.join(self.SUPPORTED_GRANT_TYPES)}"
            )
        
        # Validate and normalize scope
        scope = request.scope or request.resource
        if scope:
            audience = self._resolve_audience(scope)
        else:
            # Default to storage scope
            audience = "https://storage.azure.com"
            scope = "https://storage.azure.com/.default"
        
        # Create JWT claims
        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=self.token_lifetime)
        
        claims = {
            "aud": audience,
            "iss": self.issuer,
            "sub": request.client_id or "local-user",
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "scope": scope,
            "ver": "1.0",
            "tid": "localzure-tenant",
        }
        
        # Sign JWT with RSA private key
        token = jwt.encode(
            claims,
            self._get_private_key_pem(),
            algorithm="RS256",
            headers={"kid": self.key_id}
        )
        
        logger.info(
            f"Issued token for scope={scope}, "
            f"sub={claims['sub']}, exp={exp.isoformat()}"
        )
        
        return TokenResponse(
            access_token=token,
            token_type="Bearer",
            expires_in=self.token_lifetime,
            scope=scope,
        )
    
    def get_jwks(self) -> JWKSResponse:
        """
        Get JSON Web Key Set for token verification.
        
        Returns:
            JWKS response with public key
        """
        public_numbers = self._public_key.public_numbers()
        
        # Convert modulus and exponent to base64url
        n = self._int_to_base64url(public_numbers.n)
        e = self._int_to_base64url(public_numbers.e)
        
        jwk = JWK(
            kty="RSA",
            use="sig",
            kid=self.key_id,
            n=n,
            e=e,
            alg="RS256",
        )
        
        return JWKSResponse(keys=[jwk])
    
    def get_openid_configuration(
        self,
        base_url: str = "http://localhost:8000"
    ) -> OpenIDConfiguration:
        """
        Get OpenID Connect configuration.
        
        Args:
            base_url: Base URL for endpoints
        
        Returns:
            OpenID configuration
        """
        return OpenIDConfiguration(
            issuer=self.issuer,
            token_endpoint=f"{base_url}/.localzure/oauth/token",
            jwks_uri=f"{base_url}/.localzure/oauth/keys",
            response_types_supported=["token"],
            subject_types_supported=["public"],
            id_token_signing_alg_values_supported=["RS256"],
        )
    
    def _resolve_audience(self, scope: str) -> str:
        """
        Resolve audience from scope.
        
        Args:
            scope: Requested scope
        
        Returns:
            Audience URL
        
        Raises:
            InvalidScopeError: If scope is invalid
        """
        # Check if scope is in default scopes
        if scope in self.DEFAULT_SCOPES:
            return self.DEFAULT_SCOPES[scope]
        
        # Try to extract audience from scope
        # Format: https://resource.azure.com/.default
        if scope.endswith("/.default"):
            return scope[:-10]  # Remove /.default
        
        # If scope looks like a URL, use it as audience
        if scope.startswith("https://") or scope.startswith("http://"):
            return scope
        
        # Invalid scope
        raise InvalidScopeError(f"Invalid or unsupported scope: {scope}")
    
    def _generate_rsa_keypair(self) -> tuple:
        """
        Generate RSA key pair.
        
        Returns:
            Tuple of (private_key, public_key)
        """
        logger.info("Generating RSA key pair for JWT signing")
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        return private_key, public_key
    
    def _generate_key_id(self) -> str:
        """
        Generate unique key ID.
        
        Returns:
            Key ID (hex string)
        """
        # Use public key thumbprint as key ID
        public_pem = self._get_public_key_pem()
        thumbprint = sha256(public_pem).hexdigest()
        return thumbprint[:16]  # Use first 16 chars
    
    def _get_private_key_pem(self) -> bytes:
        """Get private key in PEM format."""
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    def _get_public_key_pem(self) -> bytes:
        """Get public key in PEM format."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    @staticmethod
    def _int_to_base64url(value: int) -> str:
        """
        Convert integer to base64url string.
        
        Args:
            value: Integer value
        
        Returns:
            Base64url encoded string
        """
        # Convert to bytes (big-endian)
        value_bytes = value.to_bytes((value.bit_length() + 7) // 8, byteorder='big')
        
        # Encode as base64url (no padding)
        return urlsafe_b64encode(value_bytes).decode('utf-8').rstrip('=')
