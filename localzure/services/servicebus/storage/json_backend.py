"""
JSON File Storage Backend

Human-readable file-based storage for debugging and simple deployments.

Author: Ayodele Oladeji
Date: December 11, 2025
"""

import asyncio
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .interface import (
    StorageBackend,
    StorageConfig,
    StorageError,
    StorageInitializationError,
    StorageIOError,
)


class JSONStorage(StorageBackend):
    """
    JSON file-based persistent storage backend.
    
    **Features**:
    - Human-readable JSON files
    - Simple file structure (one file per entity type)
    - Atomic writes using temp files
    - Easy debugging and inspection
    
    **File Structure**:
    ```
    data/
      entities/
        queues.json
        topics.json
        subscriptions.json
      messages/
        queue_myqueue.json
        subscription_mytopic_mysub.json
      state.json
    ```
    
    **When to Use**:
    - Development and debugging (inspect files manually)
    - Simple deployments without database dependencies
    - Testing and demos
    - When you need to edit state manually
    
    **Trade-offs**:
    - ✅ Human-readable (easy debugging)
    - ✅ No dependencies (just filesystem)
    - ✅ Simple to understand
    - ❌ Slower than SQLite for large datasets
    - ❌ No transactions (write entire file each time)
    - ❌ File locking can be problematic on Windows
    """
    
    def __init__(self, config: StorageConfig):
        """Initialize JSON storage with configuration."""
        super().__init__(config)
        self._data_dir = Path(config.json_path)
        self._entities_dir = self._data_dir / "entities"
        self._messages_dir = self._data_dir / "messages"
        self._state_file = self._data_dir / "state.json"
        self._write_lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize JSON storage (create directories)."""
        if self._initialized:
            return
        
        try:
            # Create directory structure
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._entities_dir.mkdir(parents=True, exist_ok=True)
            self._messages_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize state file if it doesn't exist
            if not self._state_file.exists():
                await self._write_json(self._state_file, {})
            
            self._initialized = True
        
        except Exception as e:
            raise StorageInitializationError(
                f"Failed to initialize JSON storage: {e}"
            ) from e
    
    async def close(self) -> None:
        """Close JSON storage (no-op, files already flushed)."""
        self._initialized = False
    
    async def _write_json(self, path: Path, data: Any) -> None:
        """
        Write JSON to file atomically.
        
        Uses temp file + rename pattern for atomic writes:
        1. Write to temp file
        2. Flush to disk
        3. Rename temp to target (atomic on POSIX, near-atomic on Windows)
        
        Args:
            path: Target file path
            data: Data to write (must be JSON-serializable)
        """
        temp_path = path.with_suffix('.tmp')
        
        try:
            # Write to temp file
            with open(temp_path, 'w') as f:
                json.dump(
                    data,
                    f,
                    indent=2 if self.config.pretty_json else None,
                    default=str  # Handle datetime objects
                )
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            # Atomic rename (or near-atomic on Windows)
            temp_path.replace(path)
        
        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise StorageIOError(f"Failed to write JSON file: {e}") from e
    
    async def _read_json(self, path: Path, default: Any = None) -> Any:
        """
        Read JSON from file.
        
        Args:
            path: File path to read
            default: Default value if file doesn't exist
        
        Returns:
            Parsed JSON data or default value
        """
        try:
            if not path.exists():
                return default
            
            with open(path, 'r') as f:
                return json.load(f)
        
        except Exception as e:
            raise StorageIOError(f"Failed to read JSON file: {e}") from e
    
    def _entity_file_path(self, entity_type: str) -> Path:
        """Get file path for entity type."""
        return self._entities_dir / f"{entity_type}.json"
    
    def _message_file_path(self, entity_name: str) -> Path:
        """Get file path for entity messages."""
        # Sanitize entity name for filename
        safe_name = entity_name.replace('/', '_')
        return self._messages_dir / f"{safe_name}.json"
    
    # ========== Entity Operations ==========
    
    async def save_entity(
        self,
        entity_type: str,
        entity_name: str,
        data: Dict[str, Any]
    ) -> None:
        """Save entity to JSON file."""
        try:
            async with self._write_lock:
                file_path = self._entity_file_path(entity_type)
                
                # Load existing entities
                entities = await self._read_json(file_path, default={})
                
                # Update entity with timestamp
                entities[entity_name] = {
                    **data,
                    "_updated_at": datetime.now(timezone.utc).isoformat()
                }
                
                # Write back
                await self._write_json(file_path, entities)
        
        except Exception as e:
            raise StorageIOError(f"Failed to save entity: {e}") from e
    
    async def load_entities(self, entity_type: str) -> Dict[str, Dict[str, Any]]:
        """Load all entities of given type from JSON."""
        try:
            file_path = self._entity_file_path(entity_type)
            entities = await self._read_json(file_path, default={})
            
            # Remove internal timestamp fields
            return {
                name: {k: v for k, v in data.items() if not k.startswith('_')}
                for name, data in entities.items()
            }
        
        except Exception as e:
            raise StorageIOError(f"Failed to load entities: {e}") from e
    
    async def delete_entity(self, entity_type: str, entity_name: str) -> None:
        """Delete entity from JSON file."""
        try:
            async with self._write_lock:
                file_path = self._entity_file_path(entity_type)
                
                # Load existing entities
                entities = await self._read_json(file_path, default={})
                
                # Remove entity
                entities.pop(entity_name, None)
                
                # Write back
                await self._write_json(file_path, entities)
        
        except Exception as e:
            raise StorageIOError(f"Failed to delete entity: {e}") from e
    
    # ========== Message Operations ==========
    
    async def save_message(
        self,
        entity_name: str,
        message_id: str,
        data: Dict[str, Any],
        state: str = "active"
    ) -> None:
        """Save message to JSON file."""
        try:
            async with self._write_lock:
                file_path = self._message_file_path(entity_name)
                
                # Load existing messages
                messages = await self._read_json(file_path, default={})
                
                # Save message with metadata
                messages[message_id] = {
                    "data": data,
                    "state": state,
                    "enqueued_at": datetime.now(timezone.utc).isoformat()
                }
                
                # Write back
                await self._write_json(file_path, messages)
        
        except Exception as e:
            raise StorageIOError(f"Failed to save message: {e}") from e
    
    async def load_messages(
        self,
        entity_name: str,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load messages for entity from JSON."""
        try:
            file_path = self._message_file_path(entity_name)
            messages = await self._read_json(file_path, default={})
            
            result = []
            for message_id, message_data in messages.items():
                if state is None or message_data.get("state") == state:
                    result.append(message_data["data"])
            
            return result
        
        except Exception as e:
            raise StorageIOError(f"Failed to load messages: {e}") from e
    
    async def delete_message(self, entity_name: str, message_id: str) -> None:
        """Delete message from JSON file."""
        try:
            async with self._write_lock:
                file_path = self._message_file_path(entity_name)
                
                # Load existing messages
                messages = await self._read_json(file_path, default={})
                
                # Remove message
                messages.pop(message_id, None)
                
                # Write back
                await self._write_json(file_path, messages)
        
        except Exception as e:
            raise StorageIOError(f"Failed to delete message: {e}") from e
    
    async def delete_all_messages(self, entity_name: str) -> None:
        """Delete all messages for an entity."""
        try:
            file_path = self._message_file_path(entity_name)
            if file_path.exists():
                file_path.unlink()
        
        except Exception as e:
            raise StorageIOError(f"Failed to delete all messages: {e}") from e
    
    # ========== Snapshot Operations ==========
    
    async def snapshot(self) -> None:
        """Take snapshot (JSON files are always up-to-date, no-op)."""
        pass
    
    # ========== State Operations ==========
    
    async def save_state(self, key: str, value: Any) -> None:
        """Save state to JSON file."""
        try:
            async with self._write_lock:
                state = await self._read_json(self._state_file, default={})
                state[key] = value
                await self._write_json(self._state_file, state)
        
        except Exception as e:
            raise StorageIOError(f"Failed to save state: {e}") from e
    
    async def load_state(self, key: str) -> Optional[Any]:
        """Load state from JSON file."""
        try:
            state = await self._read_json(self._state_file, default={})
            return state.get(key)
        
        except Exception as e:
            raise StorageIOError(f"Failed to load state: {e}") from e
    
    # ========== Maintenance Operations ==========
    
    async def compact(self) -> None:
        """Compact storage (remove empty files)."""
        try:
            # Remove empty entity files
            for file_path in self._entities_dir.glob("*.json"):
                data = await self._read_json(file_path, default={})
                if not data:
                    file_path.unlink()
            
            # Remove empty message files
            for file_path in self._messages_dir.glob("*.json"):
                data = await self._read_json(file_path, default={})
                if not data:
                    file_path.unlink()
        
        except Exception as e:
            raise StorageIOError(f"Failed to compact storage: {e}") from e
    
    async def purge(self) -> None:
        """Delete all data."""
        try:
            # Remove all entity files
            for file_path in self._entities_dir.glob("*.json"):
                file_path.unlink()
            
            # Remove all message files
            for file_path in self._messages_dir.glob("*.json"):
                file_path.unlink()
            
            # Clear state
            await self._write_json(self._state_file, {})
        
        except Exception as e:
            raise StorageIOError(f"Failed to purge storage: {e}") from e
    
    async def export_data(self, path: str) -> None:
        """Export all data to single JSON file."""
        try:
            export_data = {
                "version": 1,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "entities": {},
                "messages": {},
                "state": await self._read_json(self._state_file, default={})
            }
            
            # Export entities
            for file_path in self._entities_dir.glob("*.json"):
                entity_type = file_path.stem
                export_data["entities"][entity_type] = await self._read_json(file_path, default={})
            
            # Export messages
            for file_path in self._messages_dir.glob("*.json"):
                entity_name = file_path.stem.replace('_', '/')
                export_data["messages"][entity_name] = await self._read_json(file_path, default={})
            
            # Write export file
            export_path = Path(path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            await self._write_json(export_path, export_data)
        
        except Exception as e:
            raise StorageIOError(f"Failed to export data: {e}") from e
    
    async def import_data(self, path: str) -> None:
        """Import data from JSON file."""
        try:
            # Load export file
            import_data = await self._read_json(Path(path))
            
            # Clear existing data
            await self.purge()
            
            # Import entities
            for entity_type, entities in import_data.get("entities", {}).items():
                file_path = self._entity_file_path(entity_type)
                await self._write_json(file_path, entities)
            
            # Import messages
            for entity_name, messages in import_data.get("messages", {}).items():
                file_path = self._message_file_path(entity_name)
                await self._write_json(file_path, messages)
            
            # Import state
            state = import_data.get("state", {})
            await self._write_json(self._state_file, state)
        
        except Exception as e:
            raise StorageIOError(f"Failed to import data: {e}") from e
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get JSON storage statistics."""
        try:
            total_size = 0
            entity_count = 0
            message_count = 0
            
            # Count entities
            for file_path in self._entities_dir.glob("*.json"):
                total_size += file_path.stat().st_size
                entities = await self._read_json(file_path, default={})
                entity_count += len(entities)
            
            # Count messages
            for file_path in self._messages_dir.glob("*.json"):
                total_size += file_path.stat().st_size
                messages = await self._read_json(file_path, default={})
                message_count += len(messages)
            
            # State file size
            if self._state_file.exists():
                total_size += self._state_file.stat().st_size
            
            return {
                "storage_type": "json",
                "entity_count": entity_count,
                "message_count": message_count,
                "storage_size_bytes": total_size,
                "persistent": True,
                "data_path": str(self._data_dir),
                "entity_files": len(list(self._entities_dir.glob("*.json"))),
                "message_files": len(list(self._messages_dir.glob("*.json")))
            }
        
        except Exception as e:
            raise StorageIOError(f"Failed to get storage stats: {e}") from e
