"""
OAuth 2.0 exceptions for LocalZure.

Author: LocalZure Team
Date: 2025-12-12
"""


class OAuthError(Exception):
    """Base exception for OAuth errors."""
    
    def __init__(self, error: str, error_description: str = None):
        self.error = error
        self.error_description = error_description
        super().__init__(error_description or error)


class InvalidGrantError(OAuthError):
    """Raised when grant type is invalid or unsupported."""
    
    def __init__(self, description: str = "Invalid or unsupported grant type"):
        super().__init__("invalid_grant", description)


class InvalidClientError(OAuthError):
    """Raised when client authentication fails."""
    
    def __init__(self, description: str = "Client authentication failed"):
        super().__init__("invalid_client", description)


class InvalidScopeError(OAuthError):
    """Raised when requested scope is invalid."""
    
    def __init__(self, description: str = "Invalid scope"):
        super().__init__("invalid_scope", description)


class InvalidTokenError(OAuthError):
    """Raised when token validation fails."""
    
    def __init__(self, description: str = "Invalid token"):
        super().__init__("invalid_token", description)


class TokenExpiredError(InvalidTokenError):
    """Raised when token has expired."""
    
    def __init__(self, description: str = "Token has expired"):
        super().__init__(description)


class InvalidSignatureError(InvalidTokenError):
    """Raised when token signature is invalid."""
    
    def __init__(self, description: str = "Invalid token signature"):
        super().__init__(description)
