"""Rate limiting for LocalZure Gateway.

This module provides token bucket rate limiting with per-client limits
and configurable rules for production-grade request throttling.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple
import logging
import asyncio

logger = logging.getLogger(__name__)


class RateLimitScope(str, Enum):
    """Scope for rate limiting."""

    GLOBAL = "global"  # All requests
    PER_CLIENT = "per_client"  # Per client IP
    PER_SERVICE = "per_service"  # Per Azure service
    PER_ACCOUNT = "per_account"  # Per storage account


@dataclass
class RateLimitRule:
    """Rate limit rule configuration."""

    requests_per_second: float
    burst_size: int
    scope: RateLimitScope = RateLimitScope.PER_CLIENT
    enabled: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if self.burst_size < 1:
            raise ValueError("burst_size must be at least 1")


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: float  # Maximum tokens (burst size)
    refill_rate: float  # Tokens per second
    tokens: Optional[float] = None  # Current tokens (defaults to capacity)
    last_refill: float = field(default_factory=time.time)

    def __post_init__(self):
        """Initialize tokens to capacity if not specified."""
        if self.tokens is None:
            self.tokens = self.capacity

    def refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """Attempt to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient
        """
        self.refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_retry_after(self) -> float:
        """Calculate seconds until tokens available.

        Returns:
            Seconds to wait for tokens
        """
        self.refill()
        if self.tokens >= 1.0:
            return 0.0
        tokens_needed = 1.0 - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """Production-grade rate limiter using token bucket algorithm."""

    def __init__(
        self,
        global_rule: Optional[RateLimitRule] = None,
        default_rule: Optional[RateLimitRule] = None,
    ):
        """Initialize rate limiter.

        Args:
            global_rule: Global rate limit (applies to all requests)
            default_rule: Default per-client rate limit
        """
        self.global_rule = global_rule
        self.default_rule = default_rule or RateLimitRule(
            requests_per_second=100.0, burst_size=200
        )

        # Bucket storage
        self._buckets: Dict[str, TokenBucket] = {}
        self._global_bucket: Optional[TokenBucket] = None
        self._service_rules: Dict[str, RateLimitRule] = {}
        self._lock = asyncio.Lock()

        # Initialize global bucket
        if self.global_rule and self.global_rule.enabled:
            self._global_bucket = TokenBucket(
                capacity=float(self.global_rule.burst_size),
                tokens=float(self.global_rule.burst_size),
                refill_rate=self.global_rule.requests_per_second,
            )

    def register_service_rule(self, service_name: str, rule: RateLimitRule) -> None:
        """Register service-specific rate limit rule.

        Args:
            service_name: Name of the service
            rule: Rate limit rule for the service
        """
        self._service_rules[service_name] = rule
        logger.info(
            f"Registered rate limit for {service_name}: "
            f"{rule.requests_per_second} req/s, burst {rule.burst_size}"
        )

    def get_rule(self, service_name: Optional[str] = None) -> RateLimitRule:
        """Get applicable rate limit rule.

        Args:
            service_name: Service name to check for specific rule

        Returns:
            Rate limit rule (service-specific or default)
        """
        if service_name and service_name in self._service_rules:
            return self._service_rules[service_name]
        return self.default_rule

    def _get_bucket_key(
        self, rule: RateLimitRule, client_id: str, service_name: Optional[str] = None
    ) -> str:
        """Generate bucket key based on scope.

        Args:
            rule: Rate limit rule
            client_id: Client identifier
            service_name: Service name

        Returns:
            Bucket key
        """
        if rule.scope == RateLimitScope.GLOBAL:
            return "global"
        elif rule.scope == RateLimitScope.PER_CLIENT:
            return f"client:{client_id}"
        elif rule.scope == RateLimitScope.PER_SERVICE and service_name:
            return f"service:{service_name}:{client_id}"
        elif rule.scope == RateLimitScope.PER_ACCOUNT:
            return f"account:{client_id}"
        return f"client:{client_id}"

    def _get_or_create_bucket(self, key: str, rule: RateLimitRule) -> TokenBucket:
        """Get or create token bucket.

        Args:
            key: Bucket key
            rule: Rate limit rule

        Returns:
            Token bucket
        """
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                capacity=float(rule.burst_size),
                tokens=float(rule.burst_size),
                refill_rate=rule.requests_per_second,
            )
        return self._buckets[key]

    async def check_rate_limit(
        self,
        client_id: str,
        *,
        service_name: Optional[str] = None,
        tokens: float = 1.0,
    ) -> Tuple[bool, Optional[float]]:
        """Check if request is within rate limit.

        Args:
            client_id: Client identifier (e.g., IP address)
            service_name: Optional service name for service-specific limits
            tokens: Number of tokens to consume (default: 1.0)

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        async with self._lock:
            # Check global limit first
            if self._global_bucket:
                if not self._global_bucket.consume(tokens):
                    retry_after = self._global_bucket.get_retry_after()
                    logger.warning(
                        f"Global rate limit exceeded for client {client_id}, "
                        f"retry after {retry_after:.2f}s"
                    )
                    return False, retry_after

            # Check service/client-specific limit
            rule = self.get_rule(service_name)
            if not rule.enabled:
                return True, None

            bucket_key = self._get_bucket_key(rule, client_id, service_name)
            bucket = self._get_or_create_bucket(bucket_key, rule)

            if not bucket.consume(tokens):
                retry_after = bucket.get_retry_after()
                logger.warning(
                    f"Rate limit exceeded for {bucket_key}, "
                    f"retry after {retry_after:.2f}s"
                )
                return False, retry_after

            return True, None

    async def reset_client(self, client_id: str) -> None:
        """Reset rate limit for a client.

        Args:
            client_id: Client identifier
        """
        async with self._lock:
            # Remove all buckets for this client
            keys_to_remove = [
                key for key in self._buckets if f":{client_id}" in key or key == f"client:{client_id}"
            ]
            for key in keys_to_remove:
                del self._buckets[key]
            logger.info(f"Reset rate limit for client {client_id}")

    async def cleanup_expired_buckets(self, max_age_seconds: float = 300.0) -> int:
        """Remove expired buckets to prevent memory growth.

        Args:
            max_age_seconds: Maximum age for inactive buckets

        Returns:
            Number of buckets removed
        """
        async with self._lock:
            now = time.time()
            keys_to_remove = []

            for key, bucket in self._buckets.items():
                age = now - bucket.last_refill
                if age > max_age_seconds:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._buckets[key]

            if keys_to_remove:
                logger.info(f"Cleaned up {len(keys_to_remove)} expired rate limit buckets")

            return len(keys_to_remove)

    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_buckets": len(self._buckets),
            "global_enabled": self._global_bucket is not None,
            "global_tokens": self._global_bucket.tokens if self._global_bucket else None,
            "service_rules": len(self._service_rules),
            "default_rule": {
                "requests_per_second": self.default_rule.requests_per_second,
                "burst_size": self.default_rule.burst_size,
                "scope": self.default_rule.scope.value,
            },
        }
