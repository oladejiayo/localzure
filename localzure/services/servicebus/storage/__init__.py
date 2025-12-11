"""
Service Bus Storage Backend Module

Provides pluggable storage backends for persisting Service Bus entities and messages.

Author: Ayodele Oladeji
Date: December 11, 2025
"""

from .interface import StorageBackend, StorageConfig, StorageType, StorageError
from .inmemory import InMemoryStorage
from .sqlite import SQLiteStorage
from .json_backend import JSONStorage
from .wal import WriteAheadLog, WALOperation
from .factory import create_storage_backend

__all__ = [
    "StorageBackend",
    "StorageConfig",
    "StorageType",
    "StorageError",
    "InMemoryStorage",
    "SQLiteStorage",
    "JSONStorage",
    "WriteAheadLog",
    "WALOperation",
    "create_storage_backend",
]
