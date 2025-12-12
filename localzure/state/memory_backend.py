"""
In-Memory State Backend Implementation.

Fastest backend implementation using Python dictionaries.
Ideal for development, testing, and scenarios where persistence isn't required.

Author: LocalZure Team
Date: 2025-12-11
"""

import asyncio
import fnmatch
import json
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from .backend import StateBackend
from .exceptions import (
    KeyNotFoundError,
    SerializationError,
    StateBackendError,
    TransactionError,
)


class InMemoryBackend(StateBackend):
    """
    In-memory state backend using nested dictionaries.

    Storage structure:
        {namespace: {key: (value, expiry_timestamp)}}

    Features:
    - Fastest performance (no I/O overhead)
    - Namespace isolation
    - TTL support with automatic expiration
    - Batch operations
    - Transactional operations with rollback
    - JSON serialization for value consistency

    Limitations:
    - Data lost on process restart
    - No persistence across restarts
    - Memory usage scales with data size
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._storage: Dict[str, Dict[str, tuple[Any, Optional[float]]]] = {}
        self._lock = asyncio.Lock()

    def _is_expired(self, expiry: Optional[float]) -> bool:
        """Check if a key has expired."""
        if expiry is None:
            return False
        return time.time() > expiry

    def _serialize(self, value: Any) -> Any:
        """
        Serialize value for storage consistency.

        Ensures values behave consistently across all backends by
        converting to JSON and back (same as Redis/SQLite).
        """
        try:
            # Round-trip through JSON for consistency
            json_str = json.dumps(value)
            return json.loads(json_str)
        except (TypeError, ValueError) as e:
            raise SerializationError(f"Cannot serialize value: {e}")

    def _deserialize(self, value: Any) -> Any:
        """
        Deserialize value from storage.

        Since we already store JSON-compatible values, this is a no-op,
        but kept for consistency with other backends.
        """
        return value

    async def get(
        self, namespace: str, key: str, default: Optional[Any] = None
    ) -> Optional[Any]:
        """Retrieve a value from the backend."""
        async with self._lock:
            if namespace not in self._storage:
                return default

            if key not in self._storage[namespace]:
                return default

            value, expiry = self._storage[namespace][key]

            # Check expiration
            if self._is_expired(expiry):
                del self._storage[namespace][key]
                return default

            return self._deserialize(value)

    async def set(
        self, namespace: str, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """Store a value in the backend."""
        try:
            serialized_value = self._serialize(value)
        except SerializationError:
            raise

        expiry = time.time() + ttl if ttl is not None else None

        async with self._lock:
            if namespace not in self._storage:
                self._storage[namespace] = {}

            self._storage[namespace][key] = (serialized_value, expiry)

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete a key from the backend."""
        async with self._lock:
            if namespace not in self._storage:
                return False

            if key not in self._storage[namespace]:
                return False

            del self._storage[namespace][key]
            return True

    async def list(
        self, namespace: str, pattern: Optional[str] = None
    ) -> List[str]:
        """List all keys in a namespace matching optional pattern."""
        async with self._lock:
            if namespace not in self._storage:
                return []

            # Clean up expired keys first
            current_time = time.time()
            expired_keys = [
                k
                for k, (_, expiry) in self._storage[namespace].items()
                if expiry is not None and current_time > expiry
            ]
            for k in expired_keys:
                del self._storage[namespace][k]

            keys = list(self._storage[namespace].keys())

            # Apply pattern filter if provided
            if pattern is not None:
                keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]

            return keys

    async def batch_get(
        self, namespace: str, keys: List[str]
    ) -> Dict[str, Any]:
        """Retrieve multiple values in a single operation."""
        result = {}
        async with self._lock:
            if namespace not in self._storage:
                return result

            for key in keys:
                if key in self._storage[namespace]:
                    value, expiry = self._storage[namespace][key]

                    # Skip expired keys
                    if not self._is_expired(expiry):
                        result[key] = self._deserialize(value)

        return result

    async def batch_set(
        self, namespace: str, items: Dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """Store multiple key-value pairs in a single operation."""
        # Serialize all values first (fail fast if any can't be serialized)
        try:
            serialized_items = {
                k: self._serialize(v) for k, v in items.items()
            }
        except SerializationError:
            raise

        expiry = time.time() + ttl if ttl is not None else None

        async with self._lock:
            if namespace not in self._storage:
                self._storage[namespace] = {}

            for key, value in serialized_items.items():
                self._storage[namespace][key] = (value, expiry)

    async def clear_namespace(self, namespace: str) -> int:
        """Delete all keys in a namespace."""
        async with self._lock:
            if namespace not in self._storage:
                return 0

            count = len(self._storage[namespace])
            del self._storage[namespace]
            return count

    async def exists(self, namespace: str, key: str) -> bool:
        """Check if a key exists in the backend."""
        async with self._lock:
            if namespace not in self._storage:
                return False

            if key not in self._storage[namespace]:
                return False

            _, expiry = self._storage[namespace][key]

            # Check expiration
            if self._is_expired(expiry):
                del self._storage[namespace][key]
                return False

            return True

    async def get_ttl(self, namespace: str, key: str) -> Optional[int]:
        """Get remaining TTL for a key."""
        async with self._lock:
            if namespace not in self._storage:
                raise KeyNotFoundError(f"Key '{key}' not found in namespace '{namespace}'")

            if key not in self._storage[namespace]:
                raise KeyNotFoundError(f"Key '{key}' not found in namespace '{namespace}'")

            _, expiry = self._storage[namespace][key]

            if expiry is None:
                return None

            remaining = expiry - time.time()
            if remaining <= 0:
                # Key expired, clean it up
                del self._storage[namespace][key]
                raise KeyNotFoundError(f"Key '{key}' not found in namespace '{namespace}'")

            return int(remaining)

    async def set_ttl(self, namespace: str, key: str, ttl: int) -> bool:
        """Update TTL for an existing key."""
        async with self._lock:
            if namespace not in self._storage:
                return False

            if key not in self._storage[namespace]:
                return False

            value, old_expiry = self._storage[namespace][key]

            # Check if key expired
            if self._is_expired(old_expiry):
                del self._storage[namespace][key]
                return False

            # Update with new TTL
            new_expiry = time.time() + ttl
            self._storage[namespace][key] = (value, new_expiry)
            return True

    @asynccontextmanager
    async def transaction(self, namespace: str):
        """
        Context manager for transactional operations.

        Implementation:
        - Creates a snapshot of namespace state on entry
        - Yields a transaction proxy that records operations
        - Commits changes on success, rolls back on exception
        """
        # Create transaction proxy
        transaction = _InMemoryTransaction(self, namespace)

        try:
            yield transaction
            # Commit on successful exit
            await transaction._commit()
        except Exception:
            # Rollback on exception
            await transaction._rollback()
            raise


class _InMemoryTransaction:
    """
    Transaction proxy for in-memory backend.

    Records all operations and applies them atomically on commit,
    or discards them on rollback.
    """

    def __init__(self, backend: InMemoryBackend, namespace: str):
        self._backend = backend
        self._namespace = namespace
        self._operations: List[tuple] = []
        self._snapshot: Optional[Dict[str, tuple]] = None
        self._committed = False

    async def __aenter__(self):
        """Create snapshot on transaction start."""
        async with self._backend._lock:
            # Snapshot current namespace state
            if self._namespace in self._backend._storage:
                self._snapshot = dict(self._backend._storage[self._namespace])
            else:
                self._snapshot = {}
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Handle transaction completion."""
        if exc_type is None:
            await self._commit()
        else:
            await self._rollback()
        return False

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """Record set operation."""
        if self._committed:
            raise TransactionError("Transaction already committed")
        self._operations.append(("set", key, value, ttl))

    async def delete(self, key: str) -> bool:
        """Record delete operation."""
        if self._committed:
            raise TransactionError("Transaction already committed")
        self._operations.append(("delete", key))
        return True

    async def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """Read from backend (reads are not transactional)."""
        return await self._backend.get(self._namespace, key, default)

    async def _commit(self) -> None:
        """Apply all recorded operations atomically."""
        if self._committed:
            return

        async with self._backend._lock:
            for op in self._operations:
                if op[0] == "set":
                    _, key, value, ttl = op
                    serialized_value = self._backend._serialize(value)
                    expiry = time.time() + ttl if ttl is not None else None

                    if self._namespace not in self._backend._storage:
                        self._backend._storage[self._namespace] = {}

                    self._backend._storage[self._namespace][key] = (
                        serialized_value,
                        expiry,
                    )

                elif op[0] == "delete":
                    _, key = op
                    if self._namespace in self._backend._storage:
                        self._backend._storage[self._namespace].pop(key, None)

        self._committed = True

    async def _rollback(self) -> None:
        """Restore snapshot, discarding all recorded operations."""
        if self._committed:
            return

        async with self._backend._lock:
            # Restore snapshot
            if self._snapshot is not None:
                if self._snapshot:
                    self._backend._storage[self._namespace] = self._snapshot
                elif self._namespace in self._backend._storage:
                    del self._backend._storage[self._namespace]

        self._committed = True


# Add get_namespaces method to InMemoryBackend for snapshot support
async def _get_namespaces(self: InMemoryBackend) -> List[str]:
    """Get list of all namespaces in backend."""
    async with self._lock:
        return list(self._storage.keys())


InMemoryBackend.get_namespaces = _get_namespaces
