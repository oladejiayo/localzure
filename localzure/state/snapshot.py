"""
State Snapshot and Restore Module.

Provides functionality to snapshot entire state backend to compressed files
and restore from snapshots for reproducible test environments.

Author: LocalZure Team
Date: 2025-12-12
"""

import gzip
import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict

from .backend import StateBackend
from .exceptions import StateBackendError

logger = logging.getLogger(__name__)


SNAPSHOT_VERSION = "1.0"


@dataclass
class SnapshotMetadata:
    """Metadata for state snapshot."""
    
    version: str
    timestamp: str
    backend_type: str
    namespaces: List[str]
    total_keys: int
    checksum: Optional[str] = None
    partial: bool = False
    services: Optional[List[str]] = None


class StateSnapshot:
    """
    State snapshot and restore functionality.
    
    Features:
    - Export entire state to gzipped JSON file
    - Include all namespaces or specific services
    - Compressed storage to save disk space
    - Metadata with timestamp, backend type, checksum
    - Validation before restore
    - Backup current state before restore
    
    Snapshot file format:
    {
        "metadata": {
            "version": "1.0",
            "timestamp": "2025-12-12T10:30:00Z",
            "backend_type": "memory",
            "namespaces": ["cosmosdb", "blob"],
            "total_keys": 150,
            "checksum": "sha256:...",
            "partial": false,
            "services": null
        },
        "data": {
            "cosmosdb": {
                "db:my-database": {...},
                "container:users": {...}
            },
            "blob": {
                "container:images": {...}
            }
        }
    }
    """
    
    def __init__(self, backend: StateBackend):
        """
        Initialize snapshot manager.
        
        Args:
            backend: State backend to snapshot/restore
        """
        self.backend = backend
    
    async def create_snapshot(
        self,
        output_path: str,
        namespaces: Optional[List[str]] = None,
        services: Optional[List[str]] = None,
    ) -> SnapshotMetadata:
        """
        Create a snapshot of current state.
        
        Args:
            output_path: Path to write snapshot file
            namespaces: Specific namespaces to include (None = all)
            services: Service names for partial snapshot (e.g., ['blob', 'queue'])
        
        Returns:
            Snapshot metadata
        
        Raises:
            StateBackendError: If snapshot creation fails
        """
        logger.info(f"Creating snapshot to {output_path}")
        
        try:
            # Determine namespaces to snapshot
            if services:
                # Partial snapshot for specific services
                target_namespaces = []
                all_namespaces = await self._get_all_namespaces()
                
                for service in services:
                    # Match namespaces that start with service name
                    # e.g., service='blob' matches 'blob', 'service:blob', etc.
                    matching = [
                        ns for ns in all_namespaces
                        if ns == service or ns.startswith(f"{service}:") or ns.startswith(f"service:{service}")
                    ]
                    target_namespaces.extend(matching)
                
                target_namespaces = list(set(target_namespaces))  # Remove duplicates
                is_partial = True
            elif namespaces:
                target_namespaces = namespaces
                is_partial = True
            else:
                # Full snapshot
                target_namespaces = await self._get_all_namespaces()
                is_partial = False
            
            logger.debug(f"Snapshotting {len(target_namespaces)} namespaces: {target_namespaces}")
            
            # Collect data from all target namespaces
            data: Dict[str, Dict[str, Any]] = {}
            total_keys = 0
            
            for namespace in target_namespaces:
                keys = await self.backend.list(namespace)
                
                if keys:
                    namespace_data = {}
                    
                    for key in keys:
                        value = await self.backend.get(namespace, key)
                        if value is not None:
                            namespace_data[key] = value
                            total_keys += 1
                    
                    if namespace_data:
                        data[namespace] = namespace_data
            
            # Create metadata (without checksum first)
            backend_type = type(self.backend).__name__.replace("Backend", "").lower()
            
            metadata_dict = {
                "version": SNAPSHOT_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "backend_type": backend_type,
                "namespaces": list(data.keys()),
                "total_keys": total_keys,
                "partial": is_partial,
                "services": services,
            }
            
            # Create snapshot structure WITHOUT checksum for calculation
            snapshot = {
                "metadata": metadata_dict,
                "data": data
            }
            
            # Calculate checksum on snapshot WITHOUT checksum field
            snapshot_json = json.dumps(snapshot, sort_keys=True, separators=(',', ':'))
            checksum = f"sha256:{hashlib.sha256(snapshot_json.encode('utf-8')).hexdigest()}"
            
            # Now add checksum to snapshot
            metadata_dict["checksum"] = checksum
            snapshot["metadata"]["checksum"] = checksum
            
            # Create metadata dataclass with checksum
            metadata = SnapshotMetadata(**metadata_dict)
            
            # Write compressed snapshot
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with gzip.open(output_file, 'wt', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2)
            
            file_size = output_file.stat().st_size
            logger.info(
                f"Snapshot created: {total_keys} keys from {len(data)} namespaces, "
                f"size: {file_size} bytes, checksum: {checksum[:16]}..."
            )
            
            return metadata
        
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise StateBackendError(f"Snapshot creation failed: {e}")
    
    async def restore_snapshot(
        self,
        input_path: str,
        validate: bool = True,
        backup: bool = True,
        clear_existing: bool = True,
    ) -> SnapshotMetadata:
        """
        Restore state from snapshot.
        
        Args:
            input_path: Path to snapshot file
            validate: Validate checksum before restore
            backup: Create backup of current state before restore
            clear_existing: Clear existing state before restore
        
        Returns:
            Snapshot metadata
        
        Raises:
            StateBackendError: If restore fails
            ValueError: If snapshot validation fails
        """
        logger.info(f"Restoring snapshot from {input_path}")
        
        try:
            # Load snapshot
            snapshot = self._load_snapshot(input_path)
            metadata_dict = snapshot["metadata"]
            data = snapshot["data"]
            
            # Validate version
            if metadata_dict["version"] != SNAPSHOT_VERSION:
                raise ValueError(
                    f"Unsupported snapshot version: {metadata_dict['version']} "
                    f"(expected {SNAPSHOT_VERSION})"
                )
            
            # Validate checksum
            if validate and metadata_dict.get("checksum"):
                stored_checksum = metadata_dict["checksum"]
                
                # Recalculate checksum (remove checksum field first)
                temp_snapshot = snapshot.copy()
                temp_metadata = temp_snapshot["metadata"].copy()
                temp_metadata.pop("checksum", None)
                temp_snapshot["metadata"] = temp_metadata
                
                snapshot_json = json.dumps(temp_snapshot, sort_keys=True, separators=(',', ':'))
                calculated_checksum = f"sha256:{hashlib.sha256(snapshot_json.encode('utf-8')).hexdigest()}"
                
                if stored_checksum != calculated_checksum:
                    raise ValueError(
                        f"Checksum mismatch! Stored: {stored_checksum[:32]}..., "
                        f"Calculated: {calculated_checksum[:32]}..."
                    )
                
                logger.debug("Checksum validation passed")
            
            # Create backup if requested
            if backup:
                backup_path = f"{input_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.gz"
                logger.info(f"Creating backup before restore: {backup_path}")
                
                try:
                    await self.create_snapshot(backup_path)
                except Exception as e:
                    logger.warning(f"Backup creation failed: {e}")
            
            # Clear existing state if requested
            if clear_existing:
                logger.info("Clearing existing state")
                
                existing_namespaces = await self._get_all_namespaces()
                for namespace in existing_namespaces:
                    await self.backend.clear_namespace(namespace)
            
            # Restore data
            total_keys = 0
            
            for namespace, namespace_data in data.items():
                logger.debug(f"Restoring namespace: {namespace} ({len(namespace_data)} keys)")
                
                # Use batch_set for efficiency
                await self.backend.batch_set(namespace, namespace_data)
                total_keys += len(namespace_data)
            
            logger.info(
                f"Snapshot restored: {total_keys} keys in {len(data)} namespaces "
                f"from {metadata_dict['timestamp']}"
            )
            
            # Return metadata
            metadata = SnapshotMetadata(**metadata_dict)
            return metadata
        
        except Exception as e:
            logger.error(f"Failed to restore snapshot: {e}")
            raise StateBackendError(f"Snapshot restore failed: {e}")
    
    async def validate_snapshot(self, input_path: str) -> Dict[str, Any]:
        """
        Validate a snapshot file without restoring.
        
        Args:
            input_path: Path to snapshot file
        
        Returns:
            Validation result with metadata and status
        
        Raises:
            StateBackendError: If validation fails
        """
        try:
            snapshot = self._load_snapshot(input_path)
            metadata = snapshot["metadata"]
            data = snapshot["data"]
            
            # Check version
            version_valid = metadata["version"] == SNAPSHOT_VERSION
            
            # Check checksum
            checksum_valid = True
            checksum_message = "No checksum"
            
            if metadata.get("checksum"):
                stored_checksum = metadata["checksum"]
                
                temp_snapshot = snapshot.copy()
                temp_metadata = temp_snapshot["metadata"].copy()
                temp_metadata.pop("checksum", None)
                temp_snapshot["metadata"] = temp_metadata
                
                snapshot_json = json.dumps(temp_snapshot, sort_keys=True, separators=(',', ':'))
                calculated_checksum = f"sha256:{hashlib.sha256(snapshot_json.encode('utf-8')).hexdigest()}"
                
                checksum_valid = stored_checksum == calculated_checksum
                checksum_message = "Valid" if checksum_valid else "Invalid"
            
            # Count keys
            total_keys = sum(len(ns_data) for ns_data in data.values())
            
            return {
                "valid": version_valid and checksum_valid,
                "version_valid": version_valid,
                "checksum_valid": checksum_valid,
                "checksum_message": checksum_message,
                "metadata": metadata,
                "namespaces_count": len(data),
                "total_keys": total_keys,
                "file_size": Path(input_path).stat().st_size,
            }
        
        except Exception as e:
            logger.error(f"Failed to validate snapshot: {e}")
            raise StateBackendError(f"Snapshot validation failed: {e}")
    
    async def list_namespaces(self, input_path: str) -> List[str]:
        """
        List namespaces in a snapshot file.
        
        Args:
            input_path: Path to snapshot file
        
        Returns:
            List of namespace names
        """
        snapshot = self._load_snapshot(input_path)
        return snapshot["metadata"]["namespaces"]
    
    def _load_snapshot(self, input_path: str) -> Dict[str, Any]:
        """
        Load snapshot from compressed file.
        
        Args:
            input_path: Path to snapshot file
        
        Returns:
            Snapshot dict
        
        Raises:
            FileNotFoundError: If file doesn't exist
            StateBackendError: If file cannot be read
        """
        input_file = Path(input_path)
        
        if not input_file.exists():
            raise FileNotFoundError(f"Snapshot file not found: {input_path}")
        
        try:
            with gzip.open(input_file, 'rt', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise StateBackendError(f"Failed to load snapshot: {e}")
    
    async def _get_all_namespaces(self) -> List[str]:
        """
        Get all namespaces from backend.
        
        This is a backend-specific operation. We need to determine
        namespaces by examining keys.
        
        Returns:
            List of unique namespace names
        """
        # For most backends, we need to introspect the data structure
        # This is implementation-specific
        
        # Try to get namespaces from backend if it has a method
        if hasattr(self.backend, 'get_namespaces'):
            return await self.backend.get_namespaces()
        
        # Otherwise, we need a different approach
        # For InMemoryBackend, we can access _data directly
        if hasattr(self.backend, '_data'):
            return list(self.backend._data.keys())
        
        # For Redis, we need to scan keys and extract namespace prefixes
        # This is a fallback and may not work for all backends
        logger.warning(
            "Backend doesn't provide namespace enumeration. "
            "Attempting to discover namespaces."
        )
        
        # Try common namespace patterns
        common_services = [
            "blob", "queue", "table", "cosmosdb", "servicebus",
            "keyvault", "service:blob", "service:queue", "service:table",
            "service:cosmosdb", "service:servicebus", "service:keyvault"
        ]
        
        namespaces = []
        for ns in common_services:
            keys = await self.backend.list(ns)
            if keys:
                namespaces.append(ns)
        
        return namespaces


async def create_snapshot_from_backend(
    backend: StateBackend,
    output_path: str,
    namespaces: Optional[List[str]] = None,
    services: Optional[List[str]] = None,
) -> SnapshotMetadata:
    """
    Convenience function to create a snapshot.
    
    Args:
        backend: State backend to snapshot
        output_path: Path to write snapshot file
        namespaces: Specific namespaces to include (None = all)
        services: Service names for partial snapshot
    
    Returns:
        Snapshot metadata
    """
    snapshot = StateSnapshot(backend)
    return await snapshot.create_snapshot(output_path, namespaces, services)


async def restore_snapshot_to_backend(
    backend: StateBackend,
    input_path: str,
    validate: bool = True,
    backup: bool = True,
    clear_existing: bool = True,
) -> SnapshotMetadata:
    """
    Convenience function to restore a snapshot.
    
    Args:
        backend: State backend to restore to
        input_path: Path to snapshot file
        validate: Validate checksum before restore
        backup: Create backup of current state before restore
        clear_existing: Clear existing state before restore
    
    Returns:
        Snapshot metadata
    """
    snapshot = StateSnapshot(backend)
    return await snapshot.restore_snapshot(input_path, validate, backup, clear_existing)
