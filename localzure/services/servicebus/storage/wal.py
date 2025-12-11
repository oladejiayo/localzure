"""
Write-Ahead Log (WAL) for Crash Recovery

Logs operations before they're committed to enable crash recovery.

Author: Ayodele Oladeji
Date: December 11, 2025
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum


class WALOperation(str, Enum):
    """Types of WAL operations."""
    
    SAVE_ENTITY = "save_entity"
    DELETE_ENTITY = "delete_entity"
    SAVE_MESSAGE = "save_message"
    DELETE_MESSAGE = "delete_message"
    DELETE_ALL_MESSAGES = "delete_all_messages"
    SAVE_STATE = "save_state"


class WriteAheadLog:
    """
    Write-Ahead Log for crash recovery.
    
    **Purpose**:
    Log all mutating operations BEFORE they're committed to storage.
    On restart, replay WAL to recover uncommitted operations.
    
    **How It Works**:
    1. Before write: Append operation to WAL file
    2. Execute write: Update storage backend
    3. After snapshot: Truncate WAL (operations committed)
    
    **Recovery Process**:
    1. On startup, check if WAL exists
    2. If exists, replay all operations in order
    3. Truncate WAL after successful replay
    
    **WAL Entry Format** (JSON lines):
    ```json
    {
      "timestamp": "2025-12-11T10:30:00Z",
      "operation": "save_entity",
      "entity_type": "queue",
      "entity_name": "myqueue",
      "data": {...}
    }
    ```
    
    **Design Decisions**:
    - JSON lines format (one JSON object per line)
    - Append-only (never modify existing entries)
    - Simple fsync after each write (durability over performance)
    - Max size limit triggers forced snapshot
    
    **Trade-offs**:
    - ✅ Simple to implement and understand
    - ✅ Human-readable (debugging friendly)
    - ✅ Crash-safe (fsync each entry)
    - ❌ Sequential writes (not ideal for high throughput)
    - ❌ Replay can be slow for large logs
    """
    
    def __init__(self, wal_path: str, max_size_mb: int = 10):
        """
        Initialize Write-Ahead Log.
        
        Args:
            wal_path: Path to WAL file
            max_size_mb: Maximum WAL size before forcing snapshot
        """
        self._wal_path = Path(wal_path)
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._write_lock = asyncio.Lock()
        self._file_handle: Optional[object] = None
    
    async def initialize(self) -> None:
        """Initialize WAL (create file if needed)."""
        self._wal_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open file in append mode
        self._file_handle = open(self._wal_path, 'a', buffering=1)  # Line buffered
    
    async def close(self) -> None:
        """Close WAL file."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
    
    async def log_operation(
        self,
        operation: WALOperation,
        **kwargs
    ) -> None:
        """
        Log operation to WAL.
        
        Args:
            operation: Operation type
            **kwargs: Operation-specific data
        """
        async with self._write_lock:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": operation.value,
                **kwargs
            }
            
            # Write JSON line
            json_line = json.dumps(entry) + '\n'
            self._file_handle.write(json_line)
            self._file_handle.flush()
            
            # Force write to disk (durability)
            import os
            os.fsync(self._file_handle.fileno())
    
    async def replay(self, storage_backend) -> int:
        """
        Replay WAL operations to storage backend.
        
        Args:
            storage_backend: Storage backend to replay operations to
        
        Returns:
            Number of operations replayed
        """
        if not self._wal_path.exists():
            return 0
        
        operations_count = 0
        
        try:
            with open(self._wal_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    entry = json.loads(line)
                    operation = entry["operation"]
                    
                    # Replay operation based on type
                    if operation == WALOperation.SAVE_ENTITY.value:
                        await storage_backend.save_entity(
                            entry["entity_type"],
                            entry["entity_name"],
                            entry["data"]
                        )
                    
                    elif operation == WALOperation.DELETE_ENTITY.value:
                        await storage_backend.delete_entity(
                            entry["entity_type"],
                            entry["entity_name"]
                        )
                    
                    elif operation == WALOperation.SAVE_MESSAGE.value:
                        await storage_backend.save_message(
                            entry["entity_name"],
                            entry["message_id"],
                            entry["data"],
                            entry.get("state", "active")
                        )
                    
                    elif operation == WALOperation.DELETE_MESSAGE.value:
                        await storage_backend.delete_message(
                            entry["entity_name"],
                            entry["message_id"]
                        )
                    
                    elif operation == WALOperation.DELETE_ALL_MESSAGES.value:
                        await storage_backend.delete_all_messages(
                            entry["entity_name"]
                        )
                    
                    elif operation == WALOperation.SAVE_STATE.value:
                        await storage_backend.save_state(
                            entry["key"],
                            entry["value"]
                        )
                    
                    operations_count += 1
        
        except Exception as e:
            # Log error but don't fail - partial replay is better than nothing
            print(f"WAL replay error: {e}")
        
        return operations_count
    
    async def truncate(self) -> None:
        """Truncate WAL (after successful snapshot)."""
        async with self._write_lock:
            if self._file_handle:
                self._file_handle.close()
            
            # Truncate file
            with open(self._wal_path, 'w') as f:
                pass
            
            # Reopen for appending
            self._file_handle = open(self._wal_path, 'a', buffering=1)
    
    async def get_size(self) -> int:
        """Get WAL file size in bytes."""
        if self._wal_path.exists():
            return self._wal_path.stat().st_size
        return 0
    
    async def needs_snapshot(self) -> bool:
        """Check if WAL size exceeds threshold."""
        size = await self.get_size()
        return size >= self._max_size_bytes
    
    async def get_entry_count(self) -> int:
        """Count number of entries in WAL."""
        if not self._wal_path.exists():
            return 0
        
        count = 0
        with open(self._wal_path, 'r') as f:
            for line in f:
                if line.strip():
                    count += 1
        return count
