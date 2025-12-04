"""Tests for rate limiting functionality."""

import pytest
import asyncio
import time

from localzure.gateway.rate_limiter import (
    RateLimiter,
    RateLimitRule,
    RateLimitScope,
    TokenBucket,
)


class TestTokenBucket:
    """Tests for TokenBucket class."""

    def test_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(
            capacity=100.0,
            refill_rate=10.0,
        )

        assert bucket.capacity == 100.0
        assert bucket.refill_rate == 10.0
        assert bucket.tokens == 100.0
        assert bucket.last_refill is not None

    def test_refill_tokens(self):
        """Test token refilling."""
        bucket = TokenBucket(
            capacity=100.0,
            refill_rate=10.0,
            tokens=0.0,
        )

        # Sleep for 0.1 seconds (should refill 1 token)
        import time
        time.sleep(0.1)

        bucket.refill()
        assert bucket.tokens >= 0.9  # Allow some timing variance
        assert bucket.tokens <= 1.1

    def test_refill_does_not_exceed_capacity(self):
        """Test that refilling does not exceed capacity."""
        bucket = TokenBucket(
            capacity=10.0,
            refill_rate=100.0,
            tokens=5.0,
        )

        # Sleep to allow full refill
        import time
        time.sleep(0.1)

        bucket.refill()
        assert bucket.tokens <= bucket.capacity

    def test_consume_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(
            capacity=100.0,
            refill_rate=10.0,
            tokens=50.0,
        )

        result = bucket.consume(10.0)
        assert result is True
        assert bucket.tokens == pytest.approx(40.0, rel=0.01)

    def test_consume_failure(self):
        """Test failed token consumption."""
        bucket = TokenBucket(
            capacity=100.0,
            refill_rate=10.0,
            tokens=5.0,
        )

        result = bucket.consume(10.0)
        assert result is False
        assert bucket.tokens == pytest.approx(5.0, rel=0.01)  # Tokens unchanged

    def test_consume_exact_amount(self):
        """Test consuming exact token amount."""
        bucket = TokenBucket(
            capacity=100.0,
            refill_rate=10.0,
            tokens=10.0,
        )

        result = bucket.consume(10.0)
        assert result is True
        assert bucket.tokens == pytest.approx(0.0, abs=0.01)


class TestRateLimitRule:
    """Tests for RateLimitRule class."""

    def test_initialization(self):
        """Test rate limit rule initialization."""
        rule = RateLimitRule(
            requests_per_second=100,
            burst_size=50,
            scope=RateLimitScope.PER_CLIENT,
        )

        assert rule.requests_per_second == 100
        assert rule.burst_size == 50
        assert rule.scope == RateLimitScope.PER_CLIENT


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing."""
        default_rule = RateLimitRule(
            requests_per_second=10,
            burst_size=5,
            scope=RateLimitScope.GLOBAL,
        )
        return RateLimiter(default_rule=default_rule)

    @pytest.mark.asyncio
    async def test_initialization(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter.default_rule.requests_per_second == 10
        assert rate_limiter.default_rule.burst_size == 5
        assert rate_limiter.default_rule.scope == RateLimitScope.GLOBAL

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter):
        """Test rate limit check when allowed."""
        allowed, retry_after = await rate_limiter.check_rate_limit(
            client_id="client1",
            service_name="blob",
        )

        assert allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, rate_limiter):
        """Test rate limit check when exceeded."""
        # Configure low rate limit
        rate_limiter.register_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=1,
                burst_size=1,
                scope=RateLimitScope.GLOBAL,
            ),
        )

        # First request should succeed
        allowed1, _ = await rate_limiter.check_rate_limit(
            client_id="client1",
            service_name="blob",
        )
        assert allowed1 is True

        # Second request should fail (burst exhausted)
        allowed2, retry_after = await rate_limiter.check_rate_limit(
            client_id="client1",
            service_name="blob",
        )
        assert allowed2 is False
        assert retry_after is not None
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_per_client_scope(self, rate_limiter):
        """Test per-client rate limiting."""
        rate_limiter.register_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=1,
                burst_size=1,
                scope=RateLimitScope.PER_CLIENT,
            ),
        )

        # Client 1 uses their limit
        allowed1, _ = await rate_limiter.check_rate_limit(
            client_id="client1",
            service_name="blob",
        )
        assert allowed1 is True

        # Client 1 exceeds limit
        allowed2, _ = await rate_limiter.check_rate_limit(
            client_id="client1",
            service_name="blob",
        )
        assert allowed2 is False

        # Client 2 should still have their limit
        allowed3, _ = await rate_limiter.check_rate_limit(
            client_id="client2",
            service_name="blob",
        )
        assert allowed3 is True

    @pytest.mark.asyncio
    async def test_per_service_scope(self, rate_limiter):
        """Test per-service rate limiting."""
        rate_limiter.register_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=1,
                burst_size=1,
                scope=RateLimitScope.PER_SERVICE,
            ),
        )

        # Use limit for blob service
        allowed1, _ = await rate_limiter.check_rate_limit(
            client_id="client1",
            service_name="blob",
        )
        assert allowed1 is True

        # Exceed limit for blob service
        allowed2, _ = await rate_limiter.check_rate_limit(
            client_id="client1",
            service_name="blob",
        )
        assert allowed2 is False

        # Different service should still work
        allowed3, _ = await rate_limiter.check_rate_limit(
            client_id="client1",
            service_name="queue",
        )
        assert allowed3 is True

    @pytest.mark.asyncio
    async def test_per_account_scope(self, rate_limiter):
        """Test per-account rate limiting."""
        rate_limiter.register_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=1,
                burst_size=1,
                scope=RateLimitScope.PER_ACCOUNT,
            ),
        )

        # Use limit for account1
        allowed1, _ = await rate_limiter.check_rate_limit(
            client_id="account1",
            service_name="blob",
        )
        assert allowed1 is True

        # Exceed limit for account1
        allowed2, _ = await rate_limiter.check_rate_limit(
            client_id="account1",
            service_name="blob",
        )
        assert allowed2 is False

        # Different account should still work
        allowed3, _ = await rate_limiter.check_rate_limit(
            client_id="account2",
            service_name="blob",
        )
        assert allowed3 is True

    @pytest.mark.asyncio
    async def test_global_scope(self, rate_limiter):
        """Test global rate limiting."""
        rate_limiter.register_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=1,
                burst_size=1,
                scope=RateLimitScope.GLOBAL,
            ),
        )

        # Use global limit
        allowed1, _ = await rate_limiter.check_rate_limit(
            client_id="client1",
            service_name="blob",
        )
        assert allowed1 is True

        # Exceed global limit (different client)
        allowed2, _ = await rate_limiter.check_rate_limit(
            client_id="client2",
            service_name="blob",
        )
        assert allowed2 is False

    @pytest.mark.asyncio
    async def test_token_refill_over_time(self, rate_limiter):
        """Test that tokens refill over time."""
        rate_limiter.register_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=10,
                burst_size=2,
                scope=RateLimitScope.GLOBAL,
            ),
        )

        # Exhaust burst
        await rate_limiter.check_rate_limit(client_id="client1", service_name="blob")
        await rate_limiter.check_rate_limit(client_id="client1", service_name="blob")

        # Should fail immediately
        allowed, _ = await rate_limiter.check_rate_limit(
            client_id="client1", service_name="blob"
        )
        assert allowed is False

        # Wait for refill (0.2 seconds should refill 2 tokens)
        await asyncio.sleep(0.2)

        # Should succeed after refill
        allowed, _ = await rate_limiter.check_rate_limit(
            client_id="client1", service_name="blob"
        )
        assert allowed is True

    @pytest.mark.asyncio
    async def test_register_service_rule(self, rate_limiter):
        """Test adding service-specific rules."""
        rule = RateLimitRule(
            requests_per_second=100,
            burst_size=50,
            scope=RateLimitScope.PER_SERVICE,
        )

        rate_limiter.register_service_rule("blob", rule)

        assert "blob" in rate_limiter._service_rules
        assert rate_limiter._service_rules["blob"] == rule

    @pytest.mark.asyncio
    async def test_reset_client(self, rate_limiter):
        """Test resetting client rate limits."""
        rate_limiter.register_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=1,
                burst_size=1,
                scope=RateLimitScope.PER_CLIENT,
            ),
        )

        # Exhaust limit
        await rate_limiter.check_rate_limit(client_id="client1", service_name="blob")

        # Should fail
        allowed1, _ = await rate_limiter.check_rate_limit(
            client_id="client1", service_name="blob"
        )
        assert allowed1 is False

        # Reset client
        await rate_limiter.reset_client("client1")

        # Should succeed after reset
        allowed2, _ = await rate_limiter.check_rate_limit(
            client_id="client1", service_name="blob"
        )
        assert allowed2 is True

    @pytest.mark.asyncio
    async def test_get_stats(self, rate_limiter):
        """Test getting rate limiter statistics."""
        rate_limiter.register_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=10,
                burst_size=5,
                scope=RateLimitScope.GLOBAL,
            ),
        )

        # Make some requests
        await rate_limiter.check_rate_limit(client_id="client1", service_name="blob")
        await rate_limiter.check_rate_limit(client_id="client2", service_name="blob")

        stats = rate_limiter.get_stats()

        assert "total_buckets" in stats
        assert "service_rules" in stats
        assert stats["total_buckets"] >= 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_buckets(self, rate_limiter):
        """Test cleanup of expired buckets."""
        # Create some buckets
        await rate_limiter.check_rate_limit(client_id="client1", service_name="blob")

        initial_count = len(rate_limiter._buckets)
        assert initial_count > 0

        # Cleanup should not remove recently used buckets
        removed = await rate_limiter.cleanup_expired_buckets(max_age_seconds=1)

        assert removed == 0
        assert len(rate_limiter._buckets) == initial_count

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, rate_limiter):
        """Test concurrent request handling."""
        rate_limiter.register_service_rule(
            "blob",
            RateLimitRule(
                requests_per_second=10,
                burst_size=5,
                scope=RateLimitScope.GLOBAL,
            ),
        )

        # Make concurrent requests
        tasks = [
            rate_limiter.check_rate_limit(
                client_id=f"client{i}",
                service_name="blob",
            )
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)
        allowed_count = sum(1 for allowed, _ in results if allowed)

        # First 5 should succeed (burst size)
        assert allowed_count == 5

    @pytest.mark.asyncio
    async def test_different_services_independent(self, rate_limiter):
        """Test that different services have independent limits."""
        # Add rules for different services
        for service in ["blob", "queue", "table"]:
            rate_limiter.register_service_rule(
                service,
                RateLimitRule(
                    requests_per_second=1,
                    burst_size=1,
                    scope=RateLimitScope.PER_SERVICE,
                ),
            )

        # Each service should allow one request
        result_blob, _ = await rate_limiter.check_rate_limit(
            client_id="client1", service_name="blob"
        )
        result_queue, _ = await rate_limiter.check_rate_limit(
            client_id="client1", service_name="queue"
        )
        result_table, _ = await rate_limiter.check_rate_limit(
            client_id="client1", service_name="table"
        )

        assert result_blob is True
        assert result_queue is True
        assert result_table is True
