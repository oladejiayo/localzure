"""
Integration tests for Blob Storage snapshot API endpoints.

Tests snapshot creation, retrieval, listing, deletion via HTTP API.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from localzure.services.blob.api import router, backend


@pytest.fixture
def client():
    """Create test client."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
async def reset_backend():
    """Reset backend before each test."""
    await backend.reset()
    await backend.create_container("test-container")


@pytest.fixture
async def uploaded_blob(client):
    """Upload a test blob."""
    client.put(
        "/blob/testaccount/test-container/test.txt",
        content=b"Hello, World!",
        headers={"x-ms-blob-type": "BlockBlob", "Content-Type": "text/plain"},
    )
    return "test.txt"


class TestCreateSnapshot:
    """Test snapshot creation via API (AC1)."""
    
    def test_create_snapshot_success(self, client, uploaded_blob):
        """Test creating a snapshot via PUT with comp=snapshot."""
        response = client.put(
            "/blob/testaccount/test-container/test.txt?comp=snapshot",
        )
        
        assert response.status_code == 201
        assert "x-ms-snapshot" in response.headers
        assert "ETag" in response.headers
        assert "Last-Modified" in response.headers
        
        # Verify snapshot ID is RFC1123 format (AC2)
        snapshot_id = response.headers["x-ms-snapshot"]
        assert "T" in snapshot_id
        assert "Z" in snapshot_id
    
    def test_create_snapshot_container_not_found(self, client, uploaded_blob):
        """Test creating snapshot in non-existent container."""
        response = client.put(
            "/blob/testaccount/nonexistent/test.txt?comp=snapshot",
        )
        
        assert response.status_code == 404
    
    def test_create_snapshot_blob_not_found(self, client):
        """Test creating snapshot of non-existent blob."""
        response = client.put(
            "/blob/testaccount/test-container/nonexistent.txt?comp=snapshot",
        )
        
        assert response.status_code == 404
    
    def test_create_multiple_snapshots(self, client, uploaded_blob):
        """Test creating multiple snapshots with unique IDs (AC2)."""
        response1 = client.put(
            "/blob/testaccount/test-container/test.txt?comp=snapshot",
        )
        response2 = client.put(
            "/blob/testaccount/test-container/test.txt?comp=snapshot",
        )
        
        snapshot_id1 = response1.headers["x-ms-snapshot"]
        snapshot_id2 = response2.headers["x-ms-snapshot"]
        
        assert snapshot_id1 != snapshot_id2


class TestGetBlobSnapshot:
    """Test retrieving blob snapshots via API (AC3)."""
    
    def test_get_blob_snapshot(self, client, uploaded_blob):
        """Test retrieving a specific snapshot."""
        # Create snapshot
        create_response = client.put(
            "/blob/testaccount/test-container/test.txt?comp=snapshot",
        )
        snapshot_id = create_response.headers["x-ms-snapshot"]
        
        # Get snapshot
        response = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id}",
        )
        
        assert response.status_code == 200
        assert response.content == b"Hello, World!"
        assert response.headers["x-ms-snapshot"] == snapshot_id
    
    def test_get_blob_snapshot_not_found(self, client, uploaded_blob):
        """Test retrieving non-existent snapshot."""
        response = client.get(
            "/blob/testaccount/test-container/test.txt?snapshot=2025-01-01T00:00:00.0000000Z",
        )
        
        assert response.status_code == 404
    
    def test_get_blob_snapshot_immutable(self, client, uploaded_blob):
        """Test that snapshots are immutable (AC1)."""
        # Create snapshot
        create_response = client.put(
            "/blob/testaccount/test-container/test.txt?comp=snapshot",
        )
        snapshot_id = create_response.headers["x-ms-snapshot"]
        
        # Modify base blob
        client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"Modified content",
            headers={"x-ms-blob-type": "BlockBlob"},
        )
        
        # Verify snapshot unchanged
        response = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id}",
        )
        assert response.content == b"Hello, World!"


class TestListBlobsWithSnapshots:
    """Test listing blobs with snapshots (AC4)."""
    
    def test_list_blobs_without_snapshots_default(self, client, uploaded_blob):
        """Test listing blobs without snapshots (default)."""
        # Create snapshots
        client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        
        # List blobs
        response = client.get(
            "/blob/testaccount/test-container?restype=container&comp=list",
        )
        
        assert response.status_code == 200
        
        # Parse XML and count blobs (should only be base blob)
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)
        blobs = root.findall(".//Blob")
        assert len(blobs) == 1
        
        # Verify no Snapshot element in base blob
        snapshot_elements = root.findall(".//Snapshot")
        assert len(snapshot_elements) == 0
    
    def test_list_blobs_with_snapshots_included(self, client, uploaded_blob):
        """Test listing blobs with snapshots included (AC4)."""
        # Create snapshots
        create1 = client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        create2 = client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        snapshot_id1 = create1.headers["x-ms-snapshot"]
        snapshot_id2 = create2.headers["x-ms-snapshot"]
        
        # List blobs with snapshots
        response = client.get(
            "/blob/testaccount/test-container?restype=container&comp=list&include=snapshots",
        )
        
        assert response.status_code == 200
        
        # Parse XML and count blobs (base + 2 snapshots = 3)
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)
        blobs = root.findall(".//Blob")
        assert len(blobs) == 3
        
        # Verify snapshot IDs present
        snapshot_elements = root.findall(".//Snapshot")
        assert len(snapshot_elements) == 2
        snapshot_ids = [elem.text for elem in snapshot_elements]
        assert snapshot_id1 in snapshot_ids
        assert snapshot_id2 in snapshot_ids


class TestDeleteSnapshot:
    """Test deleting snapshots via API (AC5)."""
    
    def test_delete_specific_snapshot(self, client, uploaded_blob):
        """Test deleting a specific snapshot (AC5)."""
        # Create snapshot
        create_response = client.put(
            "/blob/testaccount/test-container/test.txt?comp=snapshot",
        )
        snapshot_id = create_response.headers["x-ms-snapshot"]
        
        # Delete snapshot
        response = client.delete(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id}",
        )
        
        assert response.status_code == 202
        
        # Verify snapshot deleted
        get_response = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id}",
        )
        assert get_response.status_code == 404
    
    def test_delete_snapshot_base_blob_intact(self, client, uploaded_blob):
        """Test that deleting snapshot doesn't affect base blob."""
        # Create snapshot
        create_response = client.put(
            "/blob/testaccount/test-container/test.txt?comp=snapshot",
        )
        snapshot_id = create_response.headers["x-ms-snapshot"]
        
        # Delete snapshot
        client.delete(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id}",
        )
        
        # Verify base blob still exists
        response = client.get("/blob/testaccount/test-container/test.txt")
        assert response.status_code == 200
        assert response.content == b"Hello, World!"
    
    def test_delete_snapshot_not_found(self, client, uploaded_blob):
        """Test deleting non-existent snapshot."""
        response = client.delete(
            "/blob/testaccount/test-container/test.txt?snapshot=2025-01-01T00:00:00.0000000Z",
        )
        
        assert response.status_code == 404


class TestDeleteBlobWithSnapshots:
    """Test deleting blobs with snapshot options (AC6)."""
    
    def test_delete_base_blob_snapshots_orphaned(self, client, uploaded_blob):
        """Test that deleting base blob doesn't delete snapshots (AC6)."""
        # Create snapshots
        create1 = client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        create2 = client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        snapshot_id1 = create1.headers["x-ms-snapshot"]
        snapshot_id2 = create2.headers["x-ms-snapshot"]
        
        # Delete base blob only
        response = client.delete("/blob/testaccount/test-container/test.txt")
        assert response.status_code == 202
        
        # Verify base blob deleted
        get_base = client.get("/blob/testaccount/test-container/test.txt")
        assert get_base.status_code == 404
        
        # Verify snapshots still exist
        get_snap1 = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id1}"
        )
        get_snap2 = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id2}"
        )
        assert get_snap1.status_code == 200
        assert get_snap2.status_code == 200
    
    def test_delete_blob_with_snapshots_include(self, client, uploaded_blob):
        """Test deleting blob and all snapshots with x-ms-delete-snapshots: include."""
        # Create snapshots
        create1 = client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        create2 = client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        snapshot_id1 = create1.headers["x-ms-snapshot"]
        snapshot_id2 = create2.headers["x-ms-snapshot"]
        
        # Delete blob and snapshots
        response = client.delete(
            "/blob/testaccount/test-container/test.txt",
            headers={"x-ms-delete-snapshots": "include"},
        )
        assert response.status_code == 202
        
        # Verify base blob deleted
        get_base = client.get("/blob/testaccount/test-container/test.txt")
        assert get_base.status_code == 404
        
        # Verify snapshots deleted
        get_snap1 = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id1}"
        )
        get_snap2 = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id2}"
        )
        assert get_snap1.status_code == 404
        assert get_snap2.status_code == 404
    
    def test_delete_blob_with_snapshots_only(self, client, uploaded_blob):
        """Test deleting only snapshots with x-ms-delete-snapshots: only."""
        # Create snapshots
        create1 = client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        create2 = client.put("/blob/testaccount/test-container/test.txt?comp=snapshot")
        snapshot_id1 = create1.headers["x-ms-snapshot"]
        snapshot_id2 = create2.headers["x-ms-snapshot"]
        
        # Delete only snapshots
        response = client.delete(
            "/blob/testaccount/test-container/test.txt",
            headers={"x-ms-delete-snapshots": "only"},
        )
        assert response.status_code == 202
        
        # Verify base blob still exists
        get_base = client.get("/blob/testaccount/test-container/test.txt")
        assert get_base.status_code == 200
        
        # Verify snapshots deleted
        get_snap1 = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id1}"
        )
        get_snap2 = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id2}"
        )
        assert get_snap1.status_code == 404
        assert get_snap2.status_code == 404


class TestSnapshotMetadata:
    """Test snapshot metadata handling (AC7)."""
    
    def test_snapshot_copies_metadata(self, client):
        """Test that snapshot copies metadata from base blob (AC7)."""
        # Upload blob with metadata
        client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"Hello, World!",
            headers={
                "x-ms-blob-type": "BlockBlob",
                "x-ms-meta-key1": "value1",
                "x-ms-meta-key2": "value2",
            },
        )
        
        # Create snapshot
        create_response = client.put(
            "/blob/testaccount/test-container/test.txt?comp=snapshot",
        )
        snapshot_id = create_response.headers["x-ms-snapshot"]
        
        # Get snapshot metadata
        response = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id}",
        )
        
        assert response.status_code == 200
        assert response.headers.get("x-ms-meta-key1") == "value1"
        assert response.headers.get("x-ms-meta-key2") == "value2"
    
    def test_snapshot_metadata_immutable(self, client):
        """Test that snapshot metadata is immutable."""
        # Upload blob with metadata
        client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"Hello, World!",
            headers={
                "x-ms-blob-type": "BlockBlob",
                "x-ms-meta-original": "value",
            },
        )
        
        # Create snapshot
        create_response = client.put(
            "/blob/testaccount/test-container/test.txt?comp=snapshot",
        )
        snapshot_id = create_response.headers["x-ms-snapshot"]
        
        # Modify base blob metadata
        client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"Hello, World!",
            headers={
                "x-ms-blob-type": "BlockBlob",
                "x-ms-meta-modified": "new_value",
            },
        )
        
        # Verify snapshot metadata unchanged
        response = client.get(
            f"/blob/testaccount/test-container/test.txt?snapshot={snapshot_id}",
        )
        assert response.headers.get("x-ms-meta-original") == "value"
        assert "x-ms-meta-modified" not in response.headers
