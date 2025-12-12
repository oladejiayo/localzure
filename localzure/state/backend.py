"""
Abstract State Backend Interface.

Defines the contract that all state backend implementations must fulfill,
ensuring consistent behavior across Redis, SQLite, file-based, and in-memory backends.

Author: LocalZure Team
Date: 2025-12-11
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager


class StateBackend(ABC):
    """
    Abstract base class for state persistence backends.

    All backend implementations (Redis, SQLite, file-based, in-memory) must
    implement this interface to ensure consistent behavior across LocalZure.

    Supports:
    - Basic key-value operations (get, set, delete, list)
    - Namespacing for service isolation
    - TTL (time-to-live) for automatic key expiration
    - Batch operations for efficiency
    - Transactional operations with rollback support
    """

    @abstractmethod
    async def get(
        self, namespace: str, key: str, default: Optional[Any] = None
    ) -> Optional[Any]:
        """
        Retrieve a value from the backend.

        Args:
            namespace: Service namespace for isolation (e.g., "cosmosdb", "blob")
            key: Unique key within namespace
            default: Value to return if key doesn't exist

        Returns:
            The stored value or default if not found

        Raises:
            StateBackendError: If retrieval operation fails
            SerializationError: If stored value cannot be deserialized
        """
        pass

    @abstractmethod
    async def set(
        self, namespace: str, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """
        Store a value in the backend.

        Args:
            namespace: Service namespace for isolation
            key: Unique key within namespace
            value: Value to store (must be JSON-serializable)
            ttl: Time-to-live in seconds (None = no expiration)

        Raises:
            StateBackendError: If storage operation fails
            SerializationError: If value cannot be serialized
        """
        pass

    @abstractmethod
    async def delete(self, namespace: str, key: str) -> bool:
        """
        Delete a key from the backend.

        Args:
            namespace: Service namespace
            key: Key to delete

        Returns:
            True if key was deleted, False if key didn't exist

        Raises:
            StateBackendError: If deletion operation fails
        """
        pass

    @abstractmethod
    async def list(
        self, namespace: str, pattern: Optional[str] = None
    ) -> List[str]:
        """
        List all keys in a namespace matching optional pattern.

        Args:
            namespace: Service namespace
            pattern: Glob-style pattern (e.g., "user:*", "db:*:container")
                     None = list all keys in namespace

        Returns:
            List of matching keys

        Raises:
            StateBackendError: If list operation fails
        """
        pass

    @abstractmethod
    async def batch_get(
        self, namespace: str, keys: List[str]
    ) -> Dict[str, Any]:
        """
        Retrieve multiple values in a single operation.

        Args:
            namespace: Service namespace
            keys: List of keys to retrieve

        Returns:
            Dictionary mapping keys to values (missing keys are omitted)

        Raises:
            StateBackendError: If batch operation fails
            SerializationError: If any stored value cannot be deserialized
        """
        pass

    @abstractmethod
    async def batch_set(
        self, namespace: str, items: Dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """
        Store multiple key-value pairs in a single operation.

        Args:
            namespace: Service namespace
            items: Dictionary of key-value pairs to store
            ttl: Time-to-live in seconds for all items (None = no expiration)

        Raises:
            StateBackendError: If batch operation fails
            SerializationError: If any value cannot be serialized
        """
        pass

    @abstractmethod
    async def clear_namespace(self, namespace: str) -> int:
        """
        Delete all keys in a namespace.

        Args:
            namespace: Service namespace to clear

        Returns:
            Number of keys deleted

        Raises:
            StateBackendError: If clear operation fails
        """
        pass

    @asynccontextmanager
    async def transaction(self, namespace: str):
        """
        Context manager for transactional operations.

        Changes made within the transaction are committed on success
        or rolled back on exception.

        Usage:
            async with backend.transaction("cosmosdb") as txn:
                await txn.set("db1", {...})
                await txn.set("db2", {...})
                # Auto-commits on exit, auto-rollback on exception

        Args:
            namespace: Service namespace for transaction

        Yields:
            Transaction context with same interface as backend

        Raises:
            TransactionError: If transaction operations fail
        """
        # Default implementation: no-op transaction (immediate commit)
        # Backends can override for true transactional support
        yield self

    @abstractmethod
    async def exists(self, namespace: str, key: str) -> bool:
        """
        Check if a key exists in the backend.

        Args:
            namespace: Service namespace
            key: Key to check

        Returns:
            True if key exists, False otherwise

        Raises:
            StateBackendError: If existence check fails
        """
        pass

    @abstractmethod
    async def get_ttl(self, namespace: str, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.

        Args:
            namespace: Service namespace
            key: Key to check

        Returns:
            Remaining seconds until expiration, None if no TTL set,
            or raises KeyNotFoundError if key doesn't exist

        Raises:
            KeyNotFoundError: If key doesn't exist
            StateBackendError: If TTL retrieval fails
        """
        pass

    @abstractmethod
    async def set_ttl(self, namespace: str, key: str, ttl: int) -> bool:
        """
        Update TTL for an existing key.

        Args:
            namespace: Service namespace
            key: Key to update
            ttl: New time-to-live in seconds

        Returns:
            True if TTL was updated, False if key doesn't exist

        Raises:
            StateBackendError: If TTL update fails
        """
        pass
