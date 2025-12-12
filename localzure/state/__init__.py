"""
State Backend Module.

Provides unified state backend interface for LocalZure services,
supporting multiple storage implementations (in-memory, Redis, SQLite, file-based).

Author: LocalZure Team
Date: 2025-12-11
"""

from .backend import StateBackend
from .memory_backend import InMemoryBackend
from .exceptions import (
    StateBackendError,
    KeyNotFoundError,
    NamespaceError,
    TransactionError,
    SerializationError,
)
from .snapshot import (
    StateSnapshot,
    SnapshotMetadata,
    create_snapshot_from_backend,
    restore_snapshot_to_backend,
)

# Optional Redis backend (requires redis package)
try:
    from .redis_backend import RedisBackend
    _REDIS_AVAILABLE = True
except ImportError:
    RedisBackend = None  # type: ignore
    _REDIS_AVAILABLE = False

__all__ = [
    # Abstract interface
    "StateBackend",
    # Implementations
    "InMemoryBackend",
    "RedisBackend",
    # Snapshot functionality
    "StateSnapshot",
    "SnapshotMetadata",
    "create_snapshot_from_backend",
    "restore_snapshot_to_backend",
    # Exceptions
    "StateBackendError",
    "KeyNotFoundError",
    "NamespaceError",
    "TransactionError",
    "SerializationError",
]
