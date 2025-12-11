"""
In-Memory Storage Backend

No-op implementation for backward compatibility. All data stored in ServiceBusBackend
memory structures. Data lost on restart.

Author: Ayodele Oladeji
Date: December 11, 2025
"""

from typing import Any, Dict, List, Optional

from .interface import StorageBackend, StorageConfig


class InMemoryStorage(StorageBackend):
    """
    In-memory storage backend (no persistence).
    
    This is the default storage backend for backward compatibility.
    All methods are no-ops since ServiceBusBackend manages state in memory.
    
    **When to Use**:
    - Development/testing when persistence not needed
    - Maximum performance (no I/O overhead)
    - Simple scenarios without restart requirements
    
    **Trade-offs**:
    - ✅ Fastest (no disk I/O)
    - ✅ Simple (no configuration needed)
    - ❌ Data lost on restart
    - ❌ No crash recovery
    """
    
    def __init__(self, config: StorageConfig):
        """Initialize in-memory storage (no-op)."""
        super().__init__(config)
        self._state: Dict[str, Any] = {}
    
    async def initialize(self) -> None:
        """Initialize in-memory storage (no-op)."""
        pass
    
    async def close(self) -> None:
        """Close in-memory storage (no-op)."""
        pass
    
    # ========== Entity Operations (No-ops) ==========
    
    async def save_entity(
        self,
        entity_type: str,
        entity_name: str,
        data: Dict[str, Any]
    ) -> None:
        """Save entity (no-op, data in memory)."""
        pass
    
    async def load_entities(self, entity_type: str) -> Dict[str, Dict[str, Any]]:
        """Load entities (no-op, returns empty)."""
        return {}
    
    async def delete_entity(self, entity_type: str, entity_name: str) -> None:
        """Delete entity (no-op)."""
        pass
    
    # ========== Message Operations (No-ops) ==========
    
    async def save_message(
        self,
        entity_name: str,
        message_id: str,
        data: Dict[str, Any],
        state: str = "active"
    ) -> None:
        """Save message (no-op, data in memory)."""
        pass
    
    async def load_messages(
        self,
        entity_name: str,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load messages (no-op, returns empty)."""
        return []
    
    async def delete_message(self, entity_name: str, message_id: str) -> None:
        """Delete message (no-op)."""
        pass
    
    async def delete_all_messages(self, entity_name: str) -> None:
        """Delete all messages (no-op)."""
        pass
    
    # ========== Snapshot Operations (No-ops) ==========
    
    async def snapshot(self) -> None:
        """Take snapshot (no-op)."""
        pass
    
    # ========== State Operations ==========
    
    async def save_state(self, key: str, value: Any) -> None:
        """Save state in memory (for testing)."""
        self._state[key] = value
    
    async def load_state(self, key: str) -> Optional[Any]:
        """Load state from memory."""
        return self._state.get(key)
    
    # ========== Maintenance Operations (No-ops) ==========
    
    async def compact(self) -> None:
        """Compact storage (no-op)."""
        pass
    
    async def purge(self) -> None:
        """Purge all data (no-op)."""
        self._state.clear()
    
    async def export_data(self, path: str) -> None:
        """Export data (no-op)."""
        pass
    
    async def import_data(self, path: str) -> None:
        """Import data (no-op)."""
        pass
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage stats (returns minimal info)."""
        return {
            "storage_type": "in-memory",
            "entity_count": 0,
            "message_count": 0,
            "storage_size_bytes": 0,
            "persistent": False
        }
