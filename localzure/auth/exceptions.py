"""
Authentication exceptions for LocalZure.

Author: LocalZure Team
Date: 2025-12-12
"""


class AuthenticationError(Exception):
    """Base exception for authentication errors."""
    
    def __init__(self, message: str, error_code: str = "AuthenticationFailed"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class AuthenticationFailedError(AuthenticationError):
    """Raised when authentication fails (403 Forbidden)."""
    
    def __init__(self, message: str = "Server failed to authenticate the request"):
        super().__init__(message, "AuthenticationFailed")


class InvalidAuthorizationHeaderError(AuthenticationError):
    """Raised when Authorization header is malformed."""
    
    def __init__(self, message: str = "Invalid Authorization header format"):
        super().__init__(message, "InvalidAuthorizationHeader")


class SignatureMismatchError(AuthenticationFailedError):
    """Raised when computed signature doesn't match provided signature."""
    
    def __init__(self, message: str = "Signature mismatch"):
        super().__init__(message)


class ClockSkewError(AuthenticationFailedError):
    """Raised when request timestamp is outside allowed window."""
    
    def __init__(self, message: str = "Request timestamp is outside allowed clock skew"):
        super().__init__(message)


class MissingAuthorizationHeaderError(AuthenticationError):
    """Raised when Authorization header is missing."""
    
    def __init__(self, message: str = "Authorization header is missing"):
        super().__init__(message, "MissingAuthorizationHeader")


class UnsupportedAuthSchemeError(AuthenticationError):
    """Raised when authentication scheme is not supported."""
    
    def __init__(self, scheme: str):
        super().__init__(
            f"Unsupported authentication scheme: {scheme}",
            "UnsupportedAuthScheme"
        )
