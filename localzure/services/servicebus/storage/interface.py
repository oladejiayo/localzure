"""
Storage Backend Interface

Defines the abstract interface all storage backends must implement.

Author: Ayodele Oladeji
Date: December 11, 2025
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StorageType(str, Enum):
    """Supported storage backend types."""
    
    IN_MEMORY = "in-memory"
    SQLITE = "sqlite"
    JSON = "json"
    REDIS = "redis"


@dataclass
class StorageConfig:
    """
    Configuration for storage backends.
    
    Attributes:
        storage_type: Type of storage backend to use
        sqlite_path: Path to SQLite database file
        json_path: Path to JSON storage directory
        redis_host: Redis server hostname
        redis_port: Redis server port
        redis_db: Redis database number
        redis_password: Redis authentication password
        snapshot_interval_seconds: How often to snapshot (0 = disabled)
        wal_enabled: Enable Write-Ahead Log for crash recovery
        auto_compact: Automatically compact storage on shutdown
    """
    
    storage_type: StorageType = StorageType.IN_MEMORY
    sqlite_path: str = "./data/servicebus.db"
    json_path: str = "./data"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    snapshot_interval_seconds: int = 60
    wal_enabled: bool = True
    auto_compact: bool = True
    pretty_json: bool = False


class StorageBackend(ABC):
    """
    Abstract base class for Service Bus storage backends.
    
    All storage implementations must inherit from this class and implement
    all abstract methods. This enables pluggable persistence strategies.
    
    **Design Pattern**: Strategy Pattern
    - ServiceBusBackend delegates persistence to StorageBackend
    - Different strategies (SQLite, JSON, Redis) implement same interface
    - Runtime selection via configuration
    
    **Lifecycle**:
    1. __init__(config) - Initialize storage with configuration
    2. initialize() - Setup storage (create tables, open files, etc.)
    3. [Runtime operations: save_entity, load_entities, save_message, etc.]
    4. snapshot() - Periodic full state dump
    5. close() - Graceful shutdown (flush, cleanup)
    
    **Thread Safety**:
    All methods are async and must be thread-safe (use locks if needed).
    ServiceBusBackend will call these methods from multiple async tasks.
    
    **Error Handling**:
    - Raise StorageError for storage-specific failures
    - Log errors internally but let caller decide how to handle
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize storage backend with configuration.
        
        Args:
            config: Storage configuration settings
        """
        self.config = config
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize storage backend (create tables, open files, connect to DB).
        
        Called once during ServiceBusBackend startup, before any operations.
        Must be idempotent (safe to call multiple times).
        
        Raises:
            StorageError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """
        Close storage backend gracefully (flush buffers, close connections).
        
        Called during ServiceBusBackend shutdown. Should ensure all pending
        writes are flushed to persistent storage.
        
        Raises:
            StorageError: If close fails
        """
        pass
    
    # ========== Entity Operations ==========
    
    @abstractmethod
    async def save_entity(
        self,
        entity_type: str,
        entity_name: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Save entity (queue, topic, subscription) to storage.
        
        Entity types:
        - "queue": QueueDescription
        - "topic": TopicDescription  
        - "subscription": SubscriptionDescription (key: "topic/subscription")
        
        Args:
            entity_type: Type of entity ("queue", "topic", "subscription")
            entity_name: Name of entity (or "topic/subscription" for subscriptions)
            data: Entity data as dictionary (JSON-serializable)
        
        Raises:
            StorageError: If save fails
        """
        pass
    
    @abstractmethod
    async def load_entities(self, entity_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Load all entities of a given type from storage.
        
        Args:
            entity_type: Type of entity to load ("queue", "topic", "subscription")
        
        Returns:
            Dictionary mapping entity names to entity data dictionaries
        
        Raises:
            StorageError: If load fails
        """
        pass
    
    @abstractmethod
    async def delete_entity(self, entity_type: str, entity_name: str) -> None:
        """
        Delete entity from storage.
        
        Args:
            entity_type: Type of entity ("queue", "topic", "subscription")
            entity_name: Name of entity to delete
        
        Raises:
            StorageError: If delete fails
        """
        pass
    
    # ========== Message Operations ==========
    
    @abstractmethod
    async def save_message(
        self,
        entity_name: str,
        message_id: str,
        data: Dict[str, Any],
        state: str = "active"
    ) -> None:
        """
        Save message to storage.
        
        Message states:
        - "active": Normal message in queue/subscription
        - "scheduled": Scheduled for future delivery
        - "deadletter": Moved to dead-letter queue
        
        Args:
            entity_name: Queue name or "topic/subscription"
            message_id: Unique message identifier
            data: Message data as dictionary (JSON-serializable)
            state: Message state ("active", "scheduled", "deadletter")
        
        Raises:
            StorageError: If save fails
        """
        pass
    
    @abstractmethod
    async def load_messages(
        self,
        entity_name: str,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Load messages for an entity from storage.
        
        Args:
            entity_name: Queue name or "topic/subscription"
            state: Filter by message state (None = all states)
        
        Returns:
            List of message data dictionaries
        
        Raises:
            StorageError: If load fails
        """
        pass
    
    @abstractmethod
    async def delete_message(self, entity_name: str, message_id: str) -> None:
        """
        Delete message from storage.
        
        Args:
            entity_name: Queue name or "topic/subscription"
            message_id: Message identifier to delete
        
        Raises:
            StorageError: If delete fails
        """
        pass
    
    @abstractmethod
    async def delete_all_messages(self, entity_name: str) -> None:
        """
        Delete all messages for an entity (used when deleting queue/subscription).
        
        Args:
            entity_name: Queue name or "topic/subscription"
        
        Raises:
            StorageError: If delete fails
        """
        pass
    
    # ========== Snapshot Operations ==========
    
    @abstractmethod
    async def snapshot(self) -> None:
        """
        Take a full snapshot of all entities and messages.
        
        Called periodically (based on snapshot_interval_seconds config).
        Should be efficient and not block other operations for long.
        
        Raises:
            StorageError: If snapshot fails
        """
        pass
    
    # ========== State Operations ==========
    
    @abstractmethod
    async def save_state(self, key: str, value: Any) -> None:
        """
        Save arbitrary state (e.g., sequence counters, locks).
        
        Args:
            key: State key
            value: State value (must be JSON-serializable)
        
        Raises:
            StorageError: If save fails
        """
        pass
    
    @abstractmethod
    async def load_state(self, key: str) -> Optional[Any]:
        """
        Load arbitrary state.
        
        Args:
            key: State key
        
        Returns:
            State value or None if not found
        
        Raises:
            StorageError: If load fails
        """
        pass
    
    # ========== Maintenance Operations ==========
    
    @abstractmethod
    async def compact(self) -> None:
        """
        Compact storage (remove deleted records, reclaim space).
        
        May be slow; typically called during shutdown if auto_compact enabled.
        
        Raises:
            StorageError: If compact fails
        """
        pass
    
    @abstractmethod
    async def purge(self) -> None:
        """
        Delete all data (entities, messages, state).
        
        Used for testing and cleanup. Irreversible.
        
        Raises:
            StorageError: If purge fails
        """
        pass
    
    @abstractmethod
    async def export_data(self, path: str) -> None:
        """
        Export all data to JSON file (backup).
        
        Args:
            path: Path to JSON export file
        
        Raises:
            StorageError: If export fails
        """
        pass
    
    @abstractmethod
    async def import_data(self, path: str) -> None:
        """
        Import data from JSON file (restore).
        
        Args:
            path: Path to JSON import file
        
        Raises:
            StorageError: If import fails
        """
        pass
    
    @abstractmethod
    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics (size, entity counts, message counts).
        
        Returns:
            Dictionary with storage statistics
        
        Raises:
            StorageError: If stats retrieval fails
        """
        pass


class StorageError(Exception):
    """Base exception for storage-related errors."""
    pass


class StorageInitializationError(StorageError):
    """Raised when storage initialization fails."""
    pass


class StorageIOError(StorageError):
    """Raised when storage I/O operation fails."""
    pass


class StorageCorruptionError(StorageError):
    """Raised when storage data is corrupted."""
    pass
