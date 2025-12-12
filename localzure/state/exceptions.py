"""
State Backend Exceptions.

Custom exceptions for state backend operations.

Author: LocalZure Team
Date: 2025-12-11
"""


class StateBackendError(Exception):
    """Base exception for all state backend errors."""

    pass


class KeyNotFoundError(StateBackendError):
    """Raised when a requested key does not exist."""

    pass


class NamespaceError(StateBackendError):
    """Raised when namespace operations fail."""

    pass


class TransactionError(StateBackendError):
    """Raised when transaction operations fail."""

    pass


class SerializationError(StateBackendError):
    """Raised when value serialization/deserialization fails."""

    pass
