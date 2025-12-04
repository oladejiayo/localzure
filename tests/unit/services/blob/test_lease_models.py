"""
Unit tests for Blob Storage lease models.

Tests Lease model and LeaseAction enum.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from datetime import datetime, timedelta, timezone

from localzure.services.blob.models import (
    Lease,
    LeaseAction,
    LeaseState,
)


class TestLeaseAction:
    """Test LeaseAction enum."""
    
    def test_lease_actions(self):
        """Test all lease actions are defined."""
        assert LeaseAction.ACQUIRE == "acquire"
        assert LeaseAction.RENEW == "renew"
        assert LeaseAction.RELEASE == "release"
        assert LeaseAction.BREAK == "break"
        assert LeaseAction.CHANGE == "change"


class TestLeaseModel:
    """Test Lease model."""
    
    def test_create_finite_lease(self):
        """Test creating a finite duration lease."""
        now = datetime.now(timezone.utc)
        expiration = now + timedelta(seconds=30)
        
        lease = Lease(
            lease_id="test-lease-123",
            duration=30,
            acquired_time=now,
            expiration_time=expiration,
            state=LeaseState.LEASED,
        )
        
        assert lease.lease_id == "test-lease-123"
        assert lease.duration == 30
        assert lease.acquired_time == now
        assert lease.expiration_time == expiration
        assert lease.break_time is None
        assert lease.state == LeaseState.LEASED
    
    def test_create_infinite_lease(self):
        """Test creating an infinite duration lease."""
        now = datetime.now(timezone.utc)
        
        lease = Lease(
            lease_id="infinite-lease",
            duration=-1,
            acquired_time=now,
            expiration_time=None,
            state=LeaseState.LEASED,
        )
        
        assert lease.lease_id == "infinite-lease"
        assert lease.duration == -1
        assert lease.expiration_time is None
        assert lease.state == LeaseState.LEASED
    
    def test_is_expired_not_expired(self):
        """Test is_expired returns False for non-expired lease."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(seconds=30)
        
        lease = Lease(
            lease_id="test-lease",
            duration=30,
            acquired_time=now,
            expiration_time=future,
            state=LeaseState.LEASED,
        )
        
        assert not lease.is_expired()
    
    def test_is_expired_expired(self):
        """Test is_expired returns True for expired lease."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=10)
        
        lease = Lease(
            lease_id="test-lease",
            duration=30,
            acquired_time=past - timedelta(seconds=30),
            expiration_time=past,
            state=LeaseState.LEASED,
        )
        
        assert lease.is_expired()
    
    def test_is_expired_infinite_lease(self):
        """Test is_expired returns False for infinite lease."""
        now = datetime.now(timezone.utc)
        
        lease = Lease(
            lease_id="test-lease",
            duration=-1,
            acquired_time=now,
            expiration_time=None,
            state=LeaseState.LEASED,
        )
        
        assert not lease.is_expired()
    
    def test_is_breaking(self):
        """Test is_breaking identifies BREAKING state."""
        now = datetime.now(timezone.utc)
        
        lease = Lease(
            lease_id="test-lease",
            duration=30,
            acquired_time=now,
            expiration_time=None,
            break_time=now + timedelta(seconds=10),
            state=LeaseState.BREAKING,
        )
        
        assert lease.is_breaking()
    
    def test_is_not_breaking(self):
        """Test is_breaking returns False for non-BREAKING state."""
        now = datetime.now(timezone.utc)
        
        lease = Lease(
            lease_id="test-lease",
            duration=30,
            acquired_time=now,
            expiration_time=now + timedelta(seconds=30),
            state=LeaseState.LEASED,
        )
        
        assert not lease.is_breaking()
    
    def test_is_broken_no_break_time(self):
        """Test is_broken returns False when no break_time set."""
        now = datetime.now(timezone.utc)
        
        lease = Lease(
            lease_id="test-lease",
            duration=30,
            acquired_time=now,
            expiration_time=now + timedelta(seconds=30),
            state=LeaseState.LEASED,
        )
        
        assert not lease.is_broken()
    
    def test_is_broken_future_break_time(self):
        """Test is_broken returns False when break_time is in the future."""
        now = datetime.now(timezone.utc)
        
        lease = Lease(
            lease_id="test-lease",
            duration=30,
            acquired_time=now,
            expiration_time=None,
            break_time=now + timedelta(seconds=30),
            state=LeaseState.BREAKING,
        )
        
        assert not lease.is_broken()
    
    def test_is_broken_past_break_time(self):
        """Test is_broken returns True when break_time has passed."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=10)
        
        lease = Lease(
            lease_id="test-lease",
            duration=30,
            acquired_time=now - timedelta(seconds=40),
            expiration_time=None,
            break_time=past,
            state=LeaseState.BREAKING,
        )
        
        assert lease.is_broken()
    
    def test_lease_lifecycle(self):
        """Test complete lease lifecycle states."""
        now = datetime.now(timezone.utc)
        
        # Acquired
        lease = Lease(
            lease_id="test-lease",
            duration=30,
            acquired_time=now,
            expiration_time=now + timedelta(seconds=30),
            state=LeaseState.LEASED,
        )
        assert not lease.is_expired()
        assert not lease.is_breaking()
        assert not lease.is_broken()
        
        # Breaking
        lease.state = LeaseState.BREAKING
        lease.break_time = now + timedelta(seconds=10)
        assert not lease.is_expired()
        assert lease.is_breaking()
        assert not lease.is_broken()
        
        # Broken (simulate time passing)
        lease.break_time = now - timedelta(seconds=1)
        assert not lease.is_expired()
        assert lease.is_breaking()
        assert lease.is_broken()
