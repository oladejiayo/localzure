"""
JWT Token Validator for Mock OAuth Authority.

Validates JWT tokens issued by the mock authority.

Author: LocalZure Team
Date: 2025-12-12
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import jwt
from jwt import PyJWKClient

from localzure.auth.oauth.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
    InvalidSignatureError,
)

logger = logging.getLogger(__name__)


@dataclass
class TokenClaims:
    """JWT token claims."""
    
    aud: str  # Audience
    iss: str  # Issuer
    sub: str  # Subject
    exp: int  # Expiration time
    iat: int  # Issued at
    scope: Optional[str] = None
    tid: Optional[str] = None  # Tenant ID
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenClaims":
        """Create TokenClaims from dictionary."""
        return cls(
            aud=data["aud"],
            iss=data["iss"],
            sub=data["sub"],
            exp=data["exp"],
            iat=data["iat"],
            scope=data.get("scope"),
            tid=data.get("tid"),
        )


@dataclass
class ValidationResult:
    """Token validation result."""
    
    valid: bool
    claims: Optional[TokenClaims] = None
    error: Optional[str] = None


class TokenValidator:
    """
    Validates JWT tokens issued by mock OAuth authority.
    
    Supports:
    - JWT signature verification using JWKS
    - Token expiration validation
    - Issuer validation
    - Audience validation
    """
    
    def __init__(
        self,
        issuer: str,
        jwks_uri: Optional[str] = None,
        public_key: Optional[bytes] = None,
        audience: Optional[str] = None,
    ):
        """
        Initialize token validator.
        
        Args:
            issuer: Expected token issuer
            jwks_uri: JWKS endpoint URL for fetching public keys
            public_key: RSA public key (PEM format) for validation
            audience: Expected audience (optional)
        """
        self.issuer = issuer
        self.audience = audience
        
        # Initialize JWKS client or use provided public key
        if jwks_uri:
            self.jwks_client = PyJWKClient(jwks_uri)
            self.public_key = None
        elif public_key:
            self.jwks_client = None
            self.public_key = public_key
        else:
            raise ValueError("Either jwks_uri or public_key must be provided")
        
        logger.info(f"TokenValidator initialized with issuer: {issuer}")
    
    def validate_token(self, token: str) -> ValidationResult:
        """
        Validate JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Validation result with claims if valid
        """
        try:
            # Decode and verify token
            claims_dict = self._decode_token(token)
            
            # Create claims object
            claims = TokenClaims.from_dict(claims_dict)
            
            # Additional validations
            self._validate_issuer(claims)
            self._validate_expiration(claims)
            
            if self.audience:
                self._validate_audience(claims)
            
            logger.info(f"Token validated successfully for sub={claims.sub}")
            return ValidationResult(valid=True, claims=claims)
        
        except TokenExpiredError as e:
            logger.warning(f"Token expired: {e}")
            return ValidationResult(valid=False, error=str(e))
        
        except InvalidSignatureError as e:
            logger.warning(f"Invalid signature: {e}")
            return ValidationResult(valid=False, error=str(e))
        
        except InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return ValidationResult(valid=False, error=str(e))
        
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return ValidationResult(valid=False, error=str(e))
    
    def _decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and verify JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded claims
        
        Raises:
            InvalidTokenError: If token cannot be decoded
            InvalidSignatureError: If signature is invalid
        """
        try:
            # Get signing key
            if self.jwks_client:
                # Fetch key from JWKS
                signing_key = self.jwks_client.get_signing_key_from_jwt(token)
                public_key = signing_key.key
            else:
                # Use provided public key
                public_key = self.public_key
            
            # Decode and verify
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={
                    "verify_exp": False,  # We validate expiration separately
                    "verify_aud": False,  # We validate audience separately
                }
            )
            
            return claims
        
        except jwt.InvalidSignatureError as e:
            raise InvalidSignatureError(f"Token signature verification failed: {e}")
        
        except jwt.DecodeError as e:
            raise InvalidTokenError(f"Token decode failed: {e}")
        
        except Exception as e:
            raise InvalidTokenError(f"Token validation failed: {e}")
    
    def _validate_issuer(self, claims: TokenClaims) -> None:
        """
        Validate token issuer.
        
        Args:
            claims: Token claims
        
        Raises:
            InvalidTokenError: If issuer doesn't match
        """
        if claims.iss != self.issuer:
            raise InvalidTokenError(
                f"Invalid issuer. Expected: {self.issuer}, Got: {claims.iss}"
            )
    
    def _validate_expiration(self, claims: TokenClaims) -> None:
        """
        Validate token expiration.
        
        Args:
            claims: Token claims
        
        Raises:
            TokenExpiredError: If token has expired
        """
        now = datetime.now(timezone.utc)
        exp_time = datetime.fromtimestamp(claims.exp, tz=timezone.utc)
        
        if now >= exp_time:
            raise TokenExpiredError(
                f"Token expired at {exp_time.isoformat()}. Current time: {now.isoformat()}"
            )
    
    def _validate_audience(self, claims: TokenClaims) -> None:
        """
        Validate token audience.
        
        Args:
            claims: Token claims
        
        Raises:
            InvalidTokenError: If audience doesn't match
        """
        if claims.aud != self.audience:
            raise InvalidTokenError(
                f"Invalid audience. Expected: {self.audience}, Got: {claims.aud}"
            )
