"""
Unit tests for Blob Storage snapshot backend operations.

Tests snapshot creation, retrieval, listing, deletion, and edge cases.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from datetime import datetime

from localzure.services.blob.backend import (
    BlobNotFoundError,
    ContainerBackend,
    ContainerNotFoundError,
    SnapshotNotFoundError,
)
from localzure.services.blob.models import BlobType


@pytest.fixture
def backend():
    """Create a fresh backend for each test."""
    return ContainerBackend()


@pytest.fixture
async def backend_with_blob(backend):
    """Create a backend with a test container and blob."""
    await backend.create_container("test-container")
    await backend.put_blob(
        "test-container",
        "test.txt",
        b"Hello, World!",
        content_type="text/plain",
        metadata={"key1": "value1", "key2": "value2"},
    )
    return backend


class TestSnapshotModels:
    """Test snapshot model fields and methods."""
    
    @pytest.mark.asyncio
    async def test_blob_snapshot_fields(self, backend_with_blob):
        """Test that Blob model has snapshot_id field."""
        blob = await backend_with_blob.get_blob("test-container", "test.txt")
        assert hasattr(blob, "snapshot_id")
        assert blob.snapshot_id is None  # Base blob has no snapshot_id
    
    @pytest.mark.asyncio
    async def test_blob_properties_snapshot_fields(self, backend_with_blob):
        """Test that BlobProperties has snapshot fields."""
        blob = await backend_with_blob.get_blob("test-container", "test.txt")
        assert hasattr(blob.properties, "is_snapshot")
        assert hasattr(blob.properties, "snapshot_time")
        assert blob.properties.is_snapshot is False
        assert blob.properties.snapshot_time is None
    
    @pytest.mark.asyncio
    async def test_snapshot_to_headers(self, backend_with_blob):
        """Test that snapshot headers are included in to_headers()."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        headers = snapshot.properties.to_headers()
        assert "x-ms-snapshot" in headers
        assert headers["x-ms-snapshot"] == snapshot.snapshot_id
    
    @pytest.mark.asyncio
    async def test_snapshot_to_dict(self, backend_with_blob):
        """Test that snapshot info is included in to_dict()."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        blob_dict = snapshot.to_dict()
        assert "Snapshot" in blob_dict
        assert blob_dict["Snapshot"] == snapshot.snapshot_id


class TestCreateSnapshot:
    """Test snapshot creation operations."""
    
    @pytest.mark.asyncio
    async def test_create_snapshot_success(self, backend_with_blob):
        """Test creating a snapshot successfully."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        # Verify snapshot properties
        assert snapshot.snapshot_id is not None
        assert snapshot.properties.is_snapshot is True
        assert snapshot.properties.snapshot_time is not None
        assert isinstance(snapshot.properties.snapshot_time, datetime)
        
        # Verify snapshot ID is RFC1123 format
        assert "T" in snapshot.snapshot_id
        assert "Z" in snapshot.snapshot_id
    
    @pytest.mark.asyncio
    async def test_create_snapshot_copies_content(self, backend_with_blob):
        """Test that snapshot copies blob content."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        assert snapshot.name == "test.txt"
        assert snapshot.content == b"Hello, World!"
        assert snapshot.properties.content_type == "text/plain"
        assert snapshot.properties.content_length == 13
    
    @pytest.mark.asyncio
    async def test_create_snapshot_copies_metadata(self, backend_with_blob):
        """Test that snapshot copies blob metadata (AC7)."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        assert snapshot.metadata.metadata == {"key1": "value1", "key2": "value2"}
    
    @pytest.mark.asyncio
    async def test_create_snapshot_immutable(self, backend_with_blob):
        """Test that snapshots are immutable (AC1)."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        # Modify base blob
        await backend_with_blob.put_blob(
            "test-container",
            "test.txt",
            b"Modified content",
        )
        
        # Verify snapshot content unchanged
        retrieved_snapshot = await backend_with_blob.get_blob_snapshot(
            "test-container", "test.txt", snapshot.snapshot_id
        )
        assert retrieved_snapshot.content == b"Hello, World!"
    
    @pytest.mark.asyncio
    async def test_create_snapshot_unique_timestamp(self, backend_with_blob):
        """Test that snapshots have unique timestamp identifiers (AC2)."""
        snapshot1 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        snapshot2 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        assert snapshot1.snapshot_id != snapshot2.snapshot_id
        assert snapshot1.properties.snapshot_time != snapshot2.properties.snapshot_time
    
    @pytest.mark.asyncio
    async def test_create_snapshot_container_not_found(self, backend):
        """Test creating snapshot in non-existent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.create_snapshot("nonexistent", "test.txt")
    
    @pytest.mark.asyncio
    async def test_create_snapshot_blob_not_found(self, backend_with_blob):
        """Test creating snapshot of non-existent blob."""
        with pytest.raises(BlobNotFoundError):
            await backend_with_blob.create_snapshot("test-container", "nonexistent.txt")


class TestGetBlobSnapshot:
    """Test snapshot retrieval operations."""
    
    @pytest.mark.asyncio
    async def test_get_blob_snapshot_success(self, backend_with_blob):
        """Test retrieving a snapshot by ID (AC3)."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        retrieved = await backend_with_blob.get_blob_snapshot(
            "test-container", "test.txt", snapshot.snapshot_id
        )
        
        assert retrieved.snapshot_id == snapshot.snapshot_id
        assert retrieved.content == b"Hello, World!"
        assert retrieved.properties.is_snapshot is True
    
    @pytest.mark.asyncio
    async def test_get_blob_snapshot_not_found(self, backend_with_blob):
        """Test retrieving non-existent snapshot."""
        with pytest.raises(SnapshotNotFoundError):
            await backend_with_blob.get_blob_snapshot(
                "test-container", "test.txt", "2025-01-01T00:00:00.0000000Z"
            )
    
    @pytest.mark.asyncio
    async def test_get_blob_snapshot_container_not_found(self, backend):
        """Test retrieving snapshot from non-existent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.get_blob_snapshot("nonexistent", "test.txt", "2025-01-01T00:00:00.0000000Z")
    
    @pytest.mark.asyncio
    async def test_get_blob_snapshot_blob_not_found(self, backend_with_blob):
        """Test retrieving snapshot of non-existent blob."""
        with pytest.raises(SnapshotNotFoundError):
            await backend_with_blob.get_blob_snapshot(
                "test-container", "nonexistent.txt", "2025-01-01T00:00:00.0000000Z"
            )


class TestListBlobSnapshots:
    """Test listing snapshots for a blob."""
    
    @pytest.mark.asyncio
    async def test_list_blob_snapshots_empty(self, backend_with_blob):
        """Test listing snapshots when none exist."""
        snapshots = await backend_with_blob.list_blob_snapshots("test-container", "test.txt")
        assert snapshots == []
    
    @pytest.mark.asyncio
    async def test_list_blob_snapshots_multiple(self, backend_with_blob):
        """Test listing multiple snapshots."""
        snapshot1 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        snapshot2 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        snapshot3 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        snapshots = await backend_with_blob.list_blob_snapshots("test-container", "test.txt")
        
        assert len(snapshots) == 3
        assert all(s.properties.is_snapshot for s in snapshots)
        assert snapshot1.snapshot_id in [s.snapshot_id for s in snapshots]
        assert snapshot2.snapshot_id in [s.snapshot_id for s in snapshots]
        assert snapshot3.snapshot_id in [s.snapshot_id for s in snapshots]
    
    @pytest.mark.asyncio
    async def test_list_blob_snapshots_sorted_by_time(self, backend_with_blob):
        """Test that snapshots are sorted by snapshot_time."""
        await backend_with_blob.create_snapshot("test-container", "test.txt")
        await backend_with_blob.create_snapshot("test-container", "test.txt")
        await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        snapshots = await backend_with_blob.list_blob_snapshots("test-container", "test.txt")
        
        # Verify sorted order
        for i in range(len(snapshots) - 1):
            assert snapshots[i].properties.snapshot_time <= snapshots[i + 1].properties.snapshot_time
    
    @pytest.mark.asyncio
    async def test_list_blob_snapshots_container_not_found(self, backend):
        """Test listing snapshots in non-existent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.list_blob_snapshots("nonexistent", "test.txt")
    
    @pytest.mark.asyncio
    async def test_list_blob_snapshots_blob_not_found(self, backend_with_blob):
        """Test listing snapshots of non-existent blob."""
        with pytest.raises(BlobNotFoundError):
            await backend_with_blob.list_blob_snapshots("test-container", "nonexistent.txt")


class TestDeleteSnapshot:
    """Test snapshot deletion operations."""
    
    @pytest.mark.asyncio
    async def test_delete_snapshot_success(self, backend_with_blob):
        """Test deleting a specific snapshot (AC5)."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        await backend_with_blob.delete_snapshot("test-container", "test.txt", snapshot.snapshot_id)
        
        # Verify snapshot deleted
        with pytest.raises(SnapshotNotFoundError):
            await backend_with_blob.get_blob_snapshot(
                "test-container", "test.txt", snapshot.snapshot_id
            )
    
    @pytest.mark.asyncio
    async def test_delete_snapshot_base_blob_intact(self, backend_with_blob):
        """Test that deleting snapshot doesn't affect base blob."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        await backend_with_blob.delete_snapshot("test-container", "test.txt", snapshot.snapshot_id)
        
        # Verify base blob still exists
        blob = await backend_with_blob.get_blob("test-container", "test.txt")
        assert blob.content == b"Hello, World!"
    
    @pytest.mark.asyncio
    async def test_delete_snapshot_cleanup(self, backend_with_blob):
        """Test that deleting last snapshot cleans up storage."""
        snapshot = await backend_with_blob.create_snapshot("test-container", "test.txt")
        await backend_with_blob.delete_snapshot("test-container", "test.txt", snapshot.snapshot_id)
        
        # Verify cleanup (no snapshots dict entry)
        assert "test-container" not in backend_with_blob._snapshots or \
               "test.txt" not in backend_with_blob._snapshots.get("test-container", {})
    
    @pytest.mark.asyncio
    async def test_delete_snapshot_not_found(self, backend_with_blob):
        """Test deleting non-existent snapshot."""
        with pytest.raises(SnapshotNotFoundError):
            await backend_with_blob.delete_snapshot(
                "test-container", "test.txt", "2025-01-01T00:00:00.0000000Z"
            )
    
    @pytest.mark.asyncio
    async def test_delete_snapshot_container_not_found(self, backend):
        """Test deleting snapshot from non-existent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.delete_snapshot("nonexistent", "test.txt", "2025-01-01T00:00:00.0000000Z")
    
    @pytest.mark.asyncio
    async def test_delete_snapshot_blob_not_found(self, backend_with_blob):
        """Test deleting snapshot of non-existent blob."""
        with pytest.raises(BlobNotFoundError):
            await backend_with_blob.delete_snapshot(
                "test-container", "nonexistent.txt", "2025-01-01T00:00:00.0000000Z"
            )


class TestDeleteBlobWithSnapshots:
    """Test deleting blobs with snapshot options."""
    
    @pytest.mark.asyncio
    async def test_delete_blob_with_snapshots_none(self, backend_with_blob):
        """Test that deleting base blob doesn't delete snapshots (AC6)."""
        snapshot1 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        snapshot2 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        # Delete base blob only
        await backend_with_blob.delete_blob_with_snapshots(
            "test-container", "test.txt", delete_snapshots=None
        )
        
        # Verify base blob deleted
        with pytest.raises(BlobNotFoundError):
            await backend_with_blob.get_blob("test-container", "test.txt")
        
        # Verify snapshots still exist
        retrieved1 = await backend_with_blob.get_blob_snapshot(
            "test-container", "test.txt", snapshot1.snapshot_id
        )
        retrieved2 = await backend_with_blob.get_blob_snapshot(
            "test-container", "test.txt", snapshot2.snapshot_id
        )
        assert retrieved1.snapshot_id == snapshot1.snapshot_id
        assert retrieved2.snapshot_id == snapshot2.snapshot_id
    
    @pytest.mark.asyncio
    async def test_delete_blob_with_snapshots_include(self, backend_with_blob):
        """Test deleting blob and all snapshots with delete_snapshots='include'."""
        snapshot1 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        snapshot2 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        # Delete blob and snapshots
        await backend_with_blob.delete_blob_with_snapshots(
            "test-container", "test.txt", delete_snapshots="include"
        )
        
        # Verify base blob deleted
        with pytest.raises(BlobNotFoundError):
            await backend_with_blob.get_blob("test-container", "test.txt")
        
        # Verify all snapshots deleted
        with pytest.raises(SnapshotNotFoundError):
            await backend_with_blob.get_blob_snapshot(
                "test-container", "test.txt", snapshot1.snapshot_id
            )
        with pytest.raises(SnapshotNotFoundError):
            await backend_with_blob.get_blob_snapshot(
                "test-container", "test.txt", snapshot2.snapshot_id
            )
    
    @pytest.mark.asyncio
    async def test_delete_blob_with_snapshots_only(self, backend_with_blob):
        """Test deleting only snapshots with delete_snapshots='only'."""
        snapshot1 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        snapshot2 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        # Delete snapshots only
        await backend_with_blob.delete_blob_with_snapshots(
            "test-container", "test.txt", delete_snapshots="only"
        )
        
        # Verify base blob still exists
        blob = await backend_with_blob.get_blob("test-container", "test.txt")
        assert blob.content == b"Hello, World!"
        
        # Verify all snapshots deleted
        with pytest.raises(SnapshotNotFoundError):
            await backend_with_blob.get_blob_snapshot(
                "test-container", "test.txt", snapshot1.snapshot_id
            )
        with pytest.raises(SnapshotNotFoundError):
            await backend_with_blob.get_blob_snapshot(
                "test-container", "test.txt", snapshot2.snapshot_id
            )
    
    @pytest.mark.asyncio
    async def test_delete_blob_with_snapshots_container_not_found(self, backend):
        """Test deleting blob with snapshots from non-existent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.delete_blob_with_snapshots("nonexistent", "test.txt")
    
    @pytest.mark.asyncio
    async def test_delete_blob_with_snapshots_blob_not_found(self, backend_with_blob):
        """Test deleting non-existent blob with snapshots."""
        with pytest.raises(BlobNotFoundError):
            await backend_with_blob.delete_blob_with_snapshots("test-container", "nonexistent.txt")


class TestListBlobsWithSnapshots:
    """Test listing blobs with snapshot inclusion (AC4)."""
    
    @pytest.mark.asyncio
    async def test_list_blobs_without_snapshots(self, backend_with_blob):
        """Test listing blobs without snapshots (default behavior)."""
        await backend_with_blob.create_snapshot("test-container", "test.txt")
        await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        blobs, _ = await backend_with_blob.list_blobs("test-container", include_snapshots=False)
        
        # Should only return base blob
        assert len(blobs) == 1
        assert blobs[0].name == "test.txt"
        assert blobs[0].snapshot_id is None
    
    @pytest.mark.asyncio
    async def test_list_blobs_with_snapshots(self, backend_with_blob):
        """Test listing blobs with snapshots included (AC4)."""
        snapshot1 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        snapshot2 = await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        blobs, _ = await backend_with_blob.list_blobs("test-container", include_snapshots=True)
        
        # Should return base blob + 2 snapshots
        assert len(blobs) == 3
        
        # Verify base blob is included
        base_blobs = [b for b in blobs if b.snapshot_id is None]
        assert len(base_blobs) == 1
        assert base_blobs[0].name == "test.txt"
        
        # Verify snapshots are included
        snapshot_blobs = [b for b in blobs if b.snapshot_id is not None]
        assert len(snapshot_blobs) == 2
        assert snapshot1.snapshot_id in [s.snapshot_id for s in snapshot_blobs]
        assert snapshot2.snapshot_id in [s.snapshot_id for s in snapshot_blobs]
    
    @pytest.mark.asyncio
    async def test_list_blobs_snapshots_sorted(self, backend_with_blob):
        """Test that blobs with snapshots are sorted by (name, snapshot_id)."""
        # Create another blob
        await backend_with_blob.put_blob("test-container", "another.txt", b"Another")
        
        # Create snapshots for both blobs
        await backend_with_blob.create_snapshot("test-container", "test.txt")
        await backend_with_blob.create_snapshot("test-container", "another.txt")
        
        blobs, _ = await backend_with_blob.list_blobs("test-container", include_snapshots=True)
        
        # Should be sorted: another.txt (base), another.txt (snapshot), test.txt (base), test.txt (snapshot)
        assert blobs[0].name == "another.txt" and blobs[0].snapshot_id is None
        assert blobs[1].name == "another.txt" and blobs[1].snapshot_id is not None
        assert blobs[2].name == "test.txt" and blobs[2].snapshot_id is None
        assert blobs[3].name == "test.txt" and blobs[3].snapshot_id is not None
    
    @pytest.mark.asyncio
    async def test_list_blobs_snapshots_with_prefix(self, backend_with_blob):
        """Test listing blobs with snapshots and prefix filter."""
        await backend_with_blob.put_blob("test-container", "prefix/test.txt", b"Prefixed")
        await backend_with_blob.create_snapshot("test-container", "prefix/test.txt")
        
        blobs, _ = await backend_with_blob.list_blobs(
            "test-container", prefix="prefix/", include_snapshots=True
        )
        
        # Should return base blob + 1 snapshot with prefix
        assert len(blobs) == 2
        assert all(b.name.startswith("prefix/") for b in blobs)


class TestSnapshotReset:
    """Test snapshot storage reset."""
    
    @pytest.mark.asyncio
    async def test_reset_clears_snapshots(self, backend_with_blob):
        """Test that reset() clears all snapshots."""
        await backend_with_blob.create_snapshot("test-container", "test.txt")
        await backend_with_blob.create_snapshot("test-container", "test.txt")
        
        await backend_with_blob.reset()
        
        # Verify snapshots cleared
        assert len(backend_with_blob._snapshots) == 0
