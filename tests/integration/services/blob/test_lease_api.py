"""
Integration tests for Blob Storage lease API endpoints.

Tests lease operations: acquire, renew, release, break, change for containers
and blobs, including lease validation on blob operations.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
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
    await backend.put_blob("test-container", "test-blob", b"test content")


class TestContainerLeaseAcquire:
    """Test container lease acquisition via API."""
    
    def test_acquire_container_lease_finite(self, client):
        """Test acquiring a finite duration container lease."""
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        assert response.status_code == 201
        assert "x-ms-lease-id" in response.headers
        lease_id = response.headers["x-ms-lease-id"]
        assert len(lease_id) == 36  # UUID format
    
    def test_acquire_container_lease_infinite(self, client):
        """Test acquiring an infinite duration container lease."""
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "-1",
            }
        )
        
        assert response.status_code == 201
        assert "x-ms-lease-id" in response.headers
    
    def test_acquire_container_lease_with_proposed_id(self, client):
        """Test acquiring a container lease with proposed ID."""
        proposed_id = "my-custom-lease-id-123"
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
                "x-ms-proposed-lease-id": proposed_id,
            }
        )
        
        assert response.status_code == 201
        assert response.headers["x-ms-lease-id"] == proposed_id
    
    def test_acquire_container_lease_already_leased(self, client):
        """Test acquiring a lease on already leased container."""
        # Acquire first lease
        client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Try to acquire second lease
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        assert response.status_code == 409
        assert "LeaseAlreadyPresent" in response.text
    
    def test_acquire_container_lease_invalid_duration(self, client):
        """Test acquiring a lease with invalid duration."""
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "10",  # Too short
            }
        )
        
        assert response.status_code == 400
        assert "15-60 seconds" in response.text
    
    def test_acquire_container_lease_missing_duration(self, client):
        """Test acquiring a lease without duration header."""
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
            }
        )
        
        assert response.status_code == 400
        assert "x-ms-lease-duration is required" in response.text


class TestBlobLeaseAcquire:
    """Test blob lease acquisition via API."""
    
    def test_acquire_blob_lease_finite(self, client):
        """Test acquiring a finite duration blob lease."""
        response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        assert response.status_code == 201
        assert "x-ms-lease-id" in response.headers
    
    def test_acquire_blob_lease_infinite(self, client):
        """Test acquiring an infinite duration blob lease."""
        response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "-1",
            }
        )
        
        assert response.status_code == 201
        assert "x-ms-lease-id" in response.headers
    
    def test_acquire_blob_lease_nonexistent_blob(self, client):
        """Test acquiring a lease on nonexistent blob."""
        response = client.put(
            "/blob/testaccount/test-container/nonexistent?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        assert response.status_code == 404
        assert "BlobNotFound" in response.text


class TestContainerLeaseRenew:
    """Test container lease renewal via API."""
    
    def test_renew_container_lease(self, client):
        """Test renewing a container lease."""
        # Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        lease_id = acquire_response.headers["x-ms-lease-id"]
        
        # Renew lease
        renew_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "renew",
                "x-ms-lease-id": lease_id,
            }
        )
        
        assert renew_response.status_code == 200
        assert renew_response.headers["x-ms-lease-id"] == lease_id
    
    def test_renew_container_lease_wrong_id(self, client):
        """Test renewing a container lease with wrong ID."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Try to renew with wrong ID
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "renew",
                "x-ms-lease-id": "wrong-id",
            }
        )
        
        assert response.status_code == 412
        assert "LeaseIdMismatch" in response.text
    
    def test_renew_container_lease_missing_id(self, client):
        """Test renewing a lease without lease ID."""
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "renew",
            }
        )
        
        assert response.status_code == 400
        assert "x-ms-lease-id is required" in response.text


class TestBlobLeaseRenew:
    """Test blob lease renewal via API."""
    
    def test_renew_blob_lease(self, client):
        """Test renewing a blob lease."""
        # Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        lease_id = acquire_response.headers["x-ms-lease-id"]
        
        # Renew lease
        renew_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "renew",
                "x-ms-lease-id": lease_id,
            }
        )
        
        assert renew_response.status_code == 200
        assert renew_response.headers["x-ms-lease-id"] == lease_id


class TestContainerLeaseRelease:
    """Test container lease release via API."""
    
    def test_release_container_lease(self, client):
        """Test releasing a container lease."""
        # Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        lease_id = acquire_response.headers["x-ms-lease-id"]
        
        # Release lease
        release_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "release",
                "x-ms-lease-id": lease_id,
            }
        )
        
        assert release_response.status_code == 200
        
        # Should be able to acquire new lease after release
        new_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        assert new_response.status_code == 201
    
    def test_release_container_lease_wrong_id(self, client):
        """Test releasing a container lease with wrong ID."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Try to release with wrong ID
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "release",
                "x-ms-lease-id": "wrong-id",
            }
        )
        
        assert response.status_code == 412
        assert "LeaseIdMismatch" in response.text


class TestBlobLeaseRelease:
    """Test blob lease release via API."""
    
    def test_release_blob_lease(self, client):
        """Test releasing a blob lease."""
        # Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        lease_id = acquire_response.headers["x-ms-lease-id"]
        
        # Release lease
        release_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "release",
                "x-ms-lease-id": lease_id,
            }
        )
        
        assert release_response.status_code == 200


class TestContainerLeaseBreak:
    """Test container lease break via API."""
    
    def test_break_container_lease_immediate(self, client):
        """Test breaking a container lease immediately."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Break lease immediately
        break_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "break",
                "x-ms-lease-break-period": "0",
            }
        )
        
        assert break_response.status_code == 202
        assert "x-ms-lease-time" in break_response.headers
        assert break_response.headers["x-ms-lease-time"] == "0"
    
    def test_break_container_lease_delayed(self, client):
        """Test breaking a container lease with delay."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Break lease with 15 second delay
        break_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "break",
                "x-ms-lease-break-period": "15",
            }
        )
        
        assert break_response.status_code == 202
        assert break_response.headers["x-ms-lease-time"] == "15"
    
    def test_break_container_lease_without_period(self, client):
        """Test breaking a lease without specifying break period."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Break lease (defaults to immediate)
        break_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "break",
            }
        )
        
        assert break_response.status_code == 202


class TestBlobLeaseBreak:
    """Test blob lease break via API."""
    
    def test_break_blob_lease_immediate(self, client):
        """Test breaking a blob lease immediately."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Break lease immediately
        break_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "break",
                "x-ms-lease-break-period": "0",
            }
        )
        
        assert break_response.status_code == 202
        assert break_response.headers["x-ms-lease-time"] == "0"
    
    def test_break_blob_lease_delayed(self, client):
        """Test breaking a blob lease with delay."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Break lease with delay
        break_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "break",
                "x-ms-lease-break-period": "30",
            }
        )
        
        assert break_response.status_code == 202
        assert break_response.headers["x-ms-lease-time"] == "30"


class TestContainerLeaseChange:
    """Test container lease change via API."""
    
    def test_change_container_lease(self, client):
        """Test changing a container lease ID."""
        # Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        old_lease_id = acquire_response.headers["x-ms-lease-id"]
        new_lease_id = "new-lease-id-456"
        
        # Change lease ID
        change_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "change",
                "x-ms-lease-id": old_lease_id,
                "x-ms-proposed-lease-id": new_lease_id,
            }
        )
        
        assert change_response.status_code == 200
        assert change_response.headers["x-ms-lease-id"] == new_lease_id
    
    def test_change_container_lease_missing_proposed_id(self, client):
        """Test changing a lease without proposed ID."""
        # Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        lease_id = acquire_response.headers["x-ms-lease-id"]
        
        # Try to change without proposed ID
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "change",
                "x-ms-lease-id": lease_id,
            }
        )
        
        assert response.status_code == 400
        assert "x-ms-proposed-lease-id is required" in response.text


class TestBlobLeaseChange:
    """Test blob lease change via API."""
    
    def test_change_blob_lease(self, client):
        """Test changing a blob lease ID."""
        # Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        old_lease_id = acquire_response.headers["x-ms-lease-id"]
        new_lease_id = "new-blob-lease-789"
        
        # Change lease ID
        change_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "change",
                "x-ms-lease-id": old_lease_id,
                "x-ms-proposed-lease-id": new_lease_id,
            }
        )
        
        assert change_response.status_code == 200
        assert change_response.headers["x-ms-lease-id"] == new_lease_id


class TestLeaseValidationOnBlobOperations:
    """Test lease validation on blob operations."""
    
    def test_put_blob_with_valid_lease(self, client):
        """Test putting blob with valid lease ID."""
        # Acquire lease
        lease_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        lease_id = lease_response.headers["x-ms-lease-id"]
        
        # Put blob with lease ID
        put_response = client.put(
            "/blob/testaccount/test-container/test-blob",
            content=b"new content",
            headers={
                "x-ms-lease-id": lease_id,
            }
        )
        
        assert put_response.status_code == 201
    
    def test_put_blob_with_invalid_lease(self, client):
        """Test putting blob with invalid lease ID."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Try to put blob with wrong lease ID
        put_response = client.put(
            "/blob/testaccount/test-container/test-blob",
            content=b"new content",
            headers={
                "x-ms-lease-id": "wrong-id",
            }
        )
        
        assert put_response.status_code == 412
        assert "LeaseIdMismatch" in put_response.text
    
    def test_put_blob_leased_without_lease_id(self, client):
        """Test putting leased blob without providing lease ID."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Try to put blob without lease ID
        put_response = client.put(
            "/blob/testaccount/test-container/test-blob",
            content=b"new content",
        )
        
        assert put_response.status_code == 412
        assert "LeaseIdMissing" in put_response.text
    
    def test_delete_blob_with_valid_lease(self, client):
        """Test deleting blob with valid lease ID."""
        # Acquire lease
        lease_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        lease_id = lease_response.headers["x-ms-lease-id"]
        
        # Delete blob with lease ID
        delete_response = client.delete(
            "/blob/testaccount/test-container/test-blob",
            headers={
                "x-ms-lease-id": lease_id,
            }
        )
        
        assert delete_response.status_code == 202
    
    def test_delete_blob_leased_without_lease_id(self, client):
        """Test deleting leased blob without providing lease ID."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Try to delete blob without lease ID
        delete_response = client.delete(
            "/blob/testaccount/test-container/test-blob",
        )
        
        assert delete_response.status_code == 412
        assert "LeaseIdMissing" in delete_response.text
    
    def test_set_metadata_with_valid_lease(self, client):
        """Test setting blob metadata with valid lease ID."""
        # Acquire lease
        lease_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        lease_id = lease_response.headers["x-ms-lease-id"]
        
        # Set metadata with lease ID
        metadata_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=metadata",
            headers={
                "x-ms-lease-id": lease_id,
                "x-ms-meta-key1": "value1",
            }
        )
        
        assert metadata_response.status_code == 200
    
    def test_set_metadata_leased_without_lease_id(self, client):
        """Test setting metadata on leased blob without lease ID."""
        # Acquire lease
        client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # Try to set metadata without lease ID
        metadata_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=metadata",
            headers={
                "x-ms-meta-key1": "value1",
            }
        )
        
        assert metadata_response.status_code == 412
        assert "LeaseIdMissing" in metadata_response.text


class TestLeaseWorkflows:
    """Test complete lease workflows."""
    
    def test_full_lease_lifecycle(self, client):
        """Test complete lease lifecycle: acquire, renew, release."""
        # 1. Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        assert acquire_response.status_code == 201
        lease_id = acquire_response.headers["x-ms-lease-id"]
        
        # 2. Renew lease
        renew_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "renew",
                "x-ms-lease-id": lease_id,
            }
        )
        assert renew_response.status_code == 200
        
        # 3. Use lease for operation
        put_response = client.put(
            "/blob/testaccount/test-container/test-blob",
            content=b"updated content",
            headers={
                "x-ms-lease-id": lease_id,
            }
        )
        assert put_response.status_code == 201
        
        # 4. Release lease
        release_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "release",
                "x-ms-lease-id": lease_id,
            }
        )
        assert release_response.status_code == 200
        
        # 5. Can now operate without lease
        final_put = client.put(
            "/blob/testaccount/test-container/test-blob",
            content=b"final content",
        )
        assert final_put.status_code == 201
    
    def test_lease_break_workflow(self, client):
        """Test lease break workflow."""
        # 1. Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        assert acquire_response.status_code == 201
        
        # 2. Break lease immediately
        break_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "break",
                "x-ms-lease-break-period": "0",
            }
        )
        assert break_response.status_code == 202
        
        # 3. Can now acquire new lease
        new_acquire = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        assert new_acquire.status_code == 201
    
    def test_lease_change_workflow(self, client):
        """Test lease change workflow."""
        # 1. Acquire lease
        acquire_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        old_id = acquire_response.headers["x-ms-lease-id"]
        new_id = "changed-lease-id"
        
        # 2. Change lease ID
        change_response = client.put(
            "/blob/testaccount/test-container/test-blob?comp=lease",
            headers={
                "x-ms-lease-action": "change",
                "x-ms-lease-id": old_id,
                "x-ms-proposed-lease-id": new_id,
            }
        )
        assert change_response.status_code == 200
        
        # 3. Old ID no longer works
        put_old = client.put(
            "/blob/testaccount/test-container/test-blob",
            content=b"test",
            headers={
                "x-ms-lease-id": old_id,
            }
        )
        assert put_old.status_code == 412
        
        # 4. New ID works
        put_new = client.put(
            "/blob/testaccount/test-container/test-blob",
            content=b"test",
            headers={
                "x-ms-lease-id": new_id,
            }
        )
        assert put_new.status_code == 201


class TestLeaseErrorCases:
    """Test lease error handling."""
    
    def test_invalid_lease_action(self, client):
        """Test invalid lease action."""
        response = client.put(
            "/blob/testaccount/test-container?comp=lease",
            headers={
                "x-ms-lease-action": "invalid-action",
                "x-ms-lease-duration": "30",
            }
        )
        
        assert response.status_code == 400
        assert "Invalid lease action" in response.text
    
    def test_invalid_comp_parameter(self, client):
        """Test invalid comp parameter."""
        response = client.put(
            "/blob/testaccount/test-container?comp=invalid",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        # With invalid comp, it tries to create container (409) or returns error
        assert response.status_code in [400, 404, 409]
    
    def test_lease_on_nonexistent_container(self, client):
        """Test lease operation on nonexistent container."""
        response = client.put(
            "/blob/testaccount/nonexistent-container?comp=lease",
            headers={
                "x-ms-lease-action": "acquire",
                "x-ms-lease-duration": "30",
            }
        )
        
        assert response.status_code == 404
        assert "ContainerNotFound" in response.text
