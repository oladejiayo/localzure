"""
Storage Backend Factory

Creates appropriate storage backend based on configuration.

Author: Ayodele Oladeji
Date: December 11, 2025
"""

from .interface import StorageBackend, StorageConfig, StorageType, StorageError
from .inmemory import InMemoryStorage
from .sqlite import SQLiteStorage
from .json_backend import JSONStorage


def create_storage_backend(config: StorageConfig) -> StorageBackend:
    """
    Factory function to create storage backend based on configuration.
    
    Args:
        config: Storage configuration
    
    Returns:
        Initialized storage backend instance
    
    Raises:
        StorageError: If storage type is unknown or unsupported
    
    Example:
        ```python
        config = StorageConfig(
            storage_type=StorageType.SQLITE,
            sqlite_path="./data/servicebus.db"
        )
        storage = create_storage_backend(config)
        await storage.initialize()
        ```
    """
    if config.storage_type == StorageType.IN_MEMORY:
        return InMemoryStorage(config)
    
    elif config.storage_type == StorageType.SQLITE:
        return SQLiteStorage(config)
    
    elif config.storage_type == StorageType.JSON:
        return JSONStorage(config)
    
    elif config.storage_type == StorageType.REDIS:
        # Redis backend not implemented in initial version
        raise StorageError(
            "Redis storage backend not yet implemented. "
            "Use 'sqlite' or 'json' for persistence."
        )
    
    else:
        raise StorageError(
            f"Unknown storage type: {config.storage_type}. "
            f"Supported types: {[t.value for t in StorageType]}"
        )
