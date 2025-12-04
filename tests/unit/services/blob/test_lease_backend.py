"""
Unit tests for Blob Storage lease backend operations.

Tests lease acquisition, renewal, release, break, and change operations
for both containers and blobs.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from datetime import datetime, timedelta, timezone

from localzure.services.blob.backend import (
    ContainerBackend,
    ContainerNotFoundError,
    BlobNotFoundError,
    LeaseAlreadyPresentError,
    LeaseIdMissingError,
    LeaseIdMismatchError,
    LeaseNotFoundError,
)
from localzure.services.blob.models import (
    LeaseState,
    LeaseStatus,
)


@pytest.fixture
async def backend():
    """Create a container backend for testing."""
    backend = ContainerBackend()
    # Create test container
    await backend.create_container("test-container")
    # Create test blob
    await backend.put_blob("test-container", "test-blob", b"test content")
    return backend


class TestContainerLeaseAcquire:
    """Test container lease acquisition."""
    
    @pytest.mark.asyncio
    async def test_acquire_container_lease_finite_duration(self, backend):
        """Test acquiring a finite duration container lease."""
        lease = await backend.acquire_container_lease("test-container", 30)
        
        assert lease.lease_id is not None
        assert lease.duration == 30
        assert lease.state == LeaseState.LEASED
        assert lease.expiration_time is not None
        assert not lease.is_expired()
        
        # Check container properties
        container = await backend.get_container("test-container")
        assert container.properties.lease_status == LeaseStatus.LOCKED
        assert container.properties.lease_state == LeaseState.LEASED
    
    @pytest.mark.asyncio
    async def test_acquire_container_lease_infinite_duration(self, backend):
        """Test acquiring an infinite duration container lease."""
        lease = await backend.acquire_container_lease("test-container", -1)
        
        assert lease.lease_id is not None
        assert lease.duration == -1
        assert lease.state == LeaseState.LEASED
        assert lease.expiration_time is None
        assert not lease.is_expired()
    
    @pytest.mark.asyncio
    async def test_acquire_container_lease_with_proposed_id(self, backend):
        """Test acquiring a container lease with proposed lease ID."""
        proposed_id = "my-custom-lease-id"
        lease = await backend.acquire_container_lease("test-container", 30, proposed_id)
        
        assert lease.lease_id == proposed_id
    
    @pytest.mark.asyncio
    async def test_acquire_container_lease_invalid_duration_too_short(self, backend):
        """Test acquiring a container lease with duration too short."""
        with pytest.raises(ValueError, match="15-60 seconds"):
            await backend.acquire_container_lease("test-container", 10)
    
    @pytest.mark.asyncio
    async def test_acquire_container_lease_invalid_duration_too_long(self, backend):
        """Test acquiring a container lease with duration too long."""
        with pytest.raises(ValueError, match="15-60 seconds"):
            await backend.acquire_container_lease("test-container", 70)
    
    @pytest.mark.asyncio
    async def test_acquire_container_lease_nonexistent_container(self, backend):
        """Test acquiring a lease on nonexistent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.acquire_container_lease("nonexistent", 30)
    
    @pytest.mark.asyncio
    async def test_acquire_container_lease_already_leased(self, backend):
        """Test acquiring a lease on already leased container."""
        await backend.acquire_container_lease("test-container", 30)
        
        with pytest.raises(LeaseAlreadyPresentError):
            await backend.acquire_container_lease("test-container", 30)


class TestBlobLeaseAcquire:
    """Test blob lease acquisition."""
    
    @pytest.mark.asyncio
    async def test_acquire_blob_lease_finite_duration(self, backend):
        """Test acquiring a finite duration blob lease."""
        lease = await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        assert lease.lease_id is not None
        assert lease.duration == 30
        assert lease.state == LeaseState.LEASED
        assert lease.expiration_time is not None
        
        # Check blob properties
        blob = await backend.get_blob("test-container", "test-blob")
        assert blob.properties.lease_status == LeaseStatus.LOCKED
        assert blob.properties.lease_state == LeaseState.LEASED
    
    @pytest.mark.asyncio
    async def test_acquire_blob_lease_infinite_duration(self, backend):
        """Test acquiring an infinite duration blob lease."""
        lease = await backend.acquire_blob_lease("test-container", "test-blob", -1)
        
        assert lease.duration == -1
        assert lease.expiration_time is None
    
    @pytest.mark.asyncio
    async def test_acquire_blob_lease_nonexistent_blob(self, backend):
        """Test acquiring a lease on nonexistent blob."""
        with pytest.raises(BlobNotFoundError):
            await backend.acquire_blob_lease("test-container", "nonexistent", 30)
    
    @pytest.mark.asyncio
    async def test_acquire_blob_lease_already_leased(self, backend):
        """Test acquiring a lease on already leased blob."""
        await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        with pytest.raises(LeaseAlreadyPresentError):
            await backend.acquire_blob_lease("test-container", "test-blob", 30)


class TestContainerLeaseRenew:
    """Test container lease renewal."""
    
    @pytest.mark.asyncio
    async def test_renew_container_lease(self, backend):
        """Test renewing a container lease."""
        lease1 = await backend.acquire_container_lease("test-container", 30)
        original_acquired = lease1.acquired_time
        
        # Wait a bit and renew
        import asyncio
        await asyncio.sleep(0.1)
        
        lease2 = await backend.renew_container_lease("test-container", lease1.lease_id)
        
        assert lease2.lease_id == lease1.lease_id
        assert lease2.duration == 30
        assert lease2.acquired_time > original_acquired
    
    @pytest.mark.asyncio
    async def test_renew_container_lease_wrong_id(self, backend):
        """Test renewing a container lease with wrong ID."""
        await backend.acquire_container_lease("test-container", 30)
        
        with pytest.raises(LeaseIdMismatchError):
            await backend.renew_container_lease("test-container", "wrong-id")
    
    @pytest.mark.asyncio
    async def test_renew_container_lease_no_lease(self, backend):
        """Test renewing a container lease when no lease exists."""
        with pytest.raises(LeaseNotFoundError):
            await backend.renew_container_lease("test-container", "some-id")


class TestBlobLeaseRenew:
    """Test blob lease renewal."""
    
    @pytest.mark.asyncio
    async def test_renew_blob_lease(self, backend):
        """Test renewing a blob lease."""
        lease1 = await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        # Wait and renew
        import asyncio
        await asyncio.sleep(0.1)
        
        lease2 = await backend.renew_blob_lease("test-container", "test-blob", lease1.lease_id)
        
        assert lease2.lease_id == lease1.lease_id
        assert lease2.acquired_time >= lease1.acquired_time
    
    @pytest.mark.asyncio
    async def test_renew_blob_lease_wrong_id(self, backend):
        """Test renewing a blob lease with wrong ID."""
        await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        with pytest.raises(LeaseIdMismatchError):
            await backend.renew_blob_lease("test-container", "test-blob", "wrong-id")


class TestContainerLeaseRelease:
    """Test container lease release."""
    
    @pytest.mark.asyncio
    async def test_release_container_lease(self, backend):
        """Test releasing a container lease."""
        lease = await backend.acquire_container_lease("test-container", 30)
        
        await backend.release_container_lease("test-container", lease.lease_id)
        
        # Check container properties
        container = await backend.get_container("test-container")
        assert container.properties.lease_status == LeaseStatus.UNLOCKED
        assert container.properties.lease_state == LeaseState.AVAILABLE
        
        # Should be able to acquire new lease
        new_lease = await backend.acquire_container_lease("test-container", 30)
        assert new_lease.lease_id != lease.lease_id
    
    @pytest.mark.asyncio
    async def test_release_container_lease_wrong_id(self, backend):
        """Test releasing a container lease with wrong ID."""
        await backend.acquire_container_lease("test-container", 30)
        
        with pytest.raises(LeaseIdMismatchError):
            await backend.release_container_lease("test-container", "wrong-id")


class TestBlobLeaseRelease:
    """Test blob lease release."""
    
    @pytest.mark.asyncio
    async def test_release_blob_lease(self, backend):
        """Test releasing a blob lease."""
        lease = await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        await backend.release_blob_lease("test-container", "test-blob", lease.lease_id)
        
        # Check blob properties
        blob = await backend.get_blob("test-container", "test-blob")
        assert blob.properties.lease_status == LeaseStatus.UNLOCKED
        assert blob.properties.lease_state == LeaseState.AVAILABLE
        
        # Should be able to acquire new lease
        new_lease = await backend.acquire_blob_lease("test-container", "test-blob", 30)
        assert new_lease.lease_id != lease.lease_id


class TestContainerLeaseBreak:
    """Test container lease break."""
    
    @pytest.mark.asyncio
    async def test_break_container_lease_immediate(self, backend):
        """Test breaking a container lease immediately."""
        await backend.acquire_container_lease("test-container", 30)
        
        remaining_time = await backend.break_container_lease("test-container", 0)
        
        assert remaining_time == 0
        
        # Lease should be broken
        container = await backend.get_container("test-container")
        assert container.properties.lease_state == LeaseState.BROKEN
    
    @pytest.mark.asyncio
    async def test_break_container_lease_delayed(self, backend):
        """Test breaking a container lease with delay."""
        await backend.acquire_container_lease("test-container", 30)
        
        remaining_time = await backend.break_container_lease("test-container", 15)
        
        assert remaining_time == 15
        
        # Lease should be breaking
        container = await backend.get_container("test-container")
        assert container.properties.lease_state == LeaseState.BREAKING
    
    @pytest.mark.asyncio
    async def test_break_container_lease_no_lease(self, backend):
        """Test breaking a container lease when no lease exists."""
        # Should raise LeaseNotFoundError
        with pytest.raises(LeaseNotFoundError):
            await backend.break_container_lease("test-container", 0)


class TestBlobLeaseBreak:
    """Test blob lease break."""
    
    @pytest.mark.asyncio
    async def test_break_blob_lease_immediate(self, backend):
        """Test breaking a blob lease immediately."""
        await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        remaining_time = await backend.break_blob_lease("test-container", "test-blob", 0)
        
        assert remaining_time == 0
        
        # Lease should be broken
        blob = await backend.get_blob("test-container", "test-blob")
        assert blob.properties.lease_state == LeaseState.BROKEN
    
    @pytest.mark.asyncio
    async def test_break_blob_lease_delayed(self, backend):
        """Test breaking a blob lease with delay."""
        await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        remaining_time = await backend.break_blob_lease("test-container", "test-blob", 30)
        
        assert remaining_time == 30
        
        # Lease should be breaking
        blob = await backend.get_blob("test-container", "test-blob")
        assert blob.properties.lease_state == LeaseState.BREAKING


class TestContainerLeaseChange:
    """Test container lease change."""
    
    @pytest.mark.asyncio
    async def test_change_container_lease(self, backend):
        """Test changing a container lease ID."""
        lease = await backend.acquire_container_lease("test-container", 30)
        new_id = "new-lease-id"
        
        changed_lease = await backend.change_container_lease("test-container", lease.lease_id, new_id)
        
        assert changed_lease.lease_id == new_id
        assert changed_lease.duration == lease.duration
    
    @pytest.mark.asyncio
    async def test_change_container_lease_wrong_id(self, backend):
        """Test changing a container lease with wrong ID."""
        await backend.acquire_container_lease("test-container", 30)
        
        with pytest.raises(LeaseIdMismatchError):
            await backend.change_container_lease("test-container", "wrong-id", "new-id")


class TestBlobLeaseChange:
    """Test blob lease change."""
    
    @pytest.mark.asyncio
    async def test_change_blob_lease(self, backend):
        """Test changing a blob lease ID."""
        lease = await backend.acquire_blob_lease("test-container", "test-blob", 30)
        new_id = "new-lease-id"
        
        changed_lease = await backend.change_blob_lease("test-container", "test-blob", lease.lease_id, new_id)
        
        assert changed_lease.lease_id == new_id
        assert changed_lease.duration == lease.duration


class TestLeaseValidation:
    """Test lease validation for blob operations."""
    
    @pytest.mark.asyncio
    async def test_put_blob_with_valid_lease(self, backend):
        """Test putting blob with valid lease ID."""
        lease = await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        # Should succeed with valid lease ID
        await backend.put_blob("test-container", "test-blob", b"new content", lease_id=lease.lease_id)
    
    @pytest.mark.asyncio
    async def test_put_blob_with_invalid_lease(self, backend):
        """Test putting blob with invalid lease ID."""
        await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        # Should fail with wrong lease ID
        with pytest.raises(LeaseIdMismatchError):
            await backend.put_blob("test-container", "test-blob", b"new content", lease_id="wrong-id")
    
    @pytest.mark.asyncio
    async def test_put_blob_leased_without_lease_id(self, backend):
        """Test putting leased blob without providing lease ID."""
        await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        # Should fail without lease ID
        with pytest.raises(LeaseIdMissingError):
            await backend.put_blob("test-container", "test-blob", b"new content")
    
    @pytest.mark.asyncio
    async def test_delete_blob_with_valid_lease(self, backend):
        """Test deleting blob with valid lease ID."""
        lease = await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        # Should succeed with valid lease ID
        await backend.delete_blob("test-container", "test-blob", lease_id=lease.lease_id)
    
    @pytest.mark.asyncio
    async def test_delete_blob_leased_without_lease_id(self, backend):
        """Test deleting leased blob without providing lease ID."""
        await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        # Should fail without lease ID
        with pytest.raises(LeaseIdMissingError):
            await backend.delete_blob("test-container", "test-blob")
    
    @pytest.mark.asyncio
    async def test_set_metadata_with_valid_lease(self, backend):
        """Test setting blob metadata with valid lease ID."""
        lease = await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        # Should succeed with valid lease ID
        await backend.set_blob_metadata("test-container", "test-blob", {"key": "value"}, lease_id=lease.lease_id)


class TestLeaseExpiration:
    """Test lease expiration."""
    
    @pytest.mark.asyncio
    async def test_expire_leases_container(self, backend):
        """Test expiring container leases."""
        # Acquire a lease that's already expired
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=10)
        
        await backend.acquire_container_lease("test-container", 30)
        
        # Manually set expiration to the past
        lease = backend._container_leases["test-container"]
        lease.expiration_time = past
        
        # Run expiration
        await backend.expire_leases()
        
        # Lease should be removed
        assert "test-container" not in backend._container_leases
        
        # Container should be unlocked
        container = await backend.get_container("test-container")
        assert container.properties.lease_status == LeaseStatus.UNLOCKED
        assert container.properties.lease_state == LeaseState.EXPIRED
    
    @pytest.mark.asyncio
    async def test_expire_leases_blob(self, backend):
        """Test expiring blob leases."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=10)
        
        await backend.acquire_blob_lease("test-container", "test-blob", 30)
        
        # Manually set expiration to the past
        lease = backend._blob_leases["test-container"]["test-blob"]
        lease.expiration_time = past
        
        # Run expiration
        await backend.expire_leases()
        
        # Lease should be removed
        assert "test-blob" not in backend._blob_leases["test-container"]
        
        # Blob should be unlocked
        blob = await backend.get_blob("test-container", "test-blob")
        assert blob.properties.lease_status == LeaseStatus.UNLOCKED
        assert blob.properties.lease_state == LeaseState.EXPIRED
    
    @pytest.mark.asyncio
    async def test_expire_leases_breaking(self, backend):
        """Test expiring breaking leases after break period."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=1)
        
        await backend.acquire_container_lease("test-container", 30)
        await backend.break_container_lease("test-container", 15)
        
        # Manually set break_time to the past
        lease = backend._container_leases["test-container"]
        lease.break_time = past
        
        # Run expiration
        await backend.expire_leases()
        
        # Lease should be removed
        assert "test-container" not in backend._container_leases
