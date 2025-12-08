"""
Service Bus Rate Limiter

Token bucket algorithm for per-entity rate limiting to prevent resource exhaustion.

Author: Ayodele Oladeji
Date: 2025-12-08
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import dataclass, field

from .exceptions import QuotaExceededError


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.
    
    Implements the token bucket algorithm for smooth rate limiting
    with burst capacity.
    """
    capacity: int  # Maximum tokens (burst capacity)
    rate: float  # Tokens added per second
    tokens: float = field(init=False)  # Current available tokens
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        """Initialize with full bucket."""
        self.tokens = float(self.capacity)
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens consumed successfully, False if insufficient
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_update).total_seconds()
        
        # Add tokens based on rate and elapsed time
        tokens_to_add = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_update = now
    
    def get_retry_after(self, tokens: int = 1) -> float:
        """
        Calculate seconds until enough tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Seconds to wait (0 if tokens available now)
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        needed_tokens = tokens - self.tokens
        return needed_tokens / self.rate


class ServiceBusRateLimiter:
    """
    Rate limiter for Service Bus entities.
    
    Provides per-entity rate limiting using token bucket algorithm.
    Default limits:
    - Queues: 100 messages/second
    - Topics: 1000 messages/second
    """
    
    # Default rate limits (messages per second)
    DEFAULT_QUEUE_RATE = 100
    DEFAULT_TOPIC_RATE = 1000
    DEFAULT_SUBSCRIPTION_RATE = 100
    
    # Burst capacity (multiplier of rate)
    BURST_MULTIPLIER = 2
    
    def __init__(self):
        """Initialize rate limiter with empty buckets."""
        self._queue_buckets: Dict[str, TokenBucket] = {}
        self._topic_buckets: Dict[str, TokenBucket] = {}
        self._subscription_buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
    
    async def check_queue_rate(self, queue_name: str, count: int = 1) -> None:
        """
        Check if queue operation is within rate limit.
        
        Args:
            queue_name: Name of the queue
            count: Number of messages (default: 1)
            
        Raises:
            QuotaExceededError: If rate limit exceeded
        """
        async with self._lock:
            bucket = self._get_queue_bucket(queue_name)
            
            if not bucket.consume(count):
                retry_after = bucket.get_retry_after(count)
                raise QuotaExceededError(
                    quota_type="rate_limit",
                    current_value=0,  # No tokens available
                    max_value=bucket.capacity,
                    entity_name=queue_name,
                    message=f"Rate limit exceeded for queue '{queue_name}'. Retry after {retry_after:.2f} seconds"
                )
    
    async def check_topic_rate(self, topic_name: str, count: int = 1) -> None:
        """
        Check if topic operation is within rate limit.
        
        Args:
            topic_name: Name of the topic
            count: Number of messages (default: 1)
            
        Raises:
            QuotaExceededError: If rate limit exceeded
        """
        async with self._lock:
            bucket = self._get_topic_bucket(topic_name)
            
            if not bucket.consume(count):
                retry_after = bucket.get_retry_after(count)
                raise QuotaExceededError(
                    quota_type="rate_limit",
                    current_value=0,
                    max_value=bucket.capacity,
                    entity_name=topic_name,
                    message=f"Rate limit exceeded for topic '{topic_name}'. Retry after {retry_after:.2f} seconds"
                )
    
    async def check_subscription_rate(
        self,
        topic_name: str,
        subscription_name: str,
        count: int = 1
    ) -> None:
        """
        Check if subscription operation is within rate limit.
        
        Args:
            topic_name: Name of the topic
            subscription_name: Name of the subscription
            count: Number of messages (default: 1)
            
        Raises:
            QuotaExceededError: If rate limit exceeded
        """
        async with self._lock:
            key = f"{topic_name}/{subscription_name}"
            bucket = self._get_subscription_bucket(key)
            
            if not bucket.consume(count):
                retry_after = bucket.get_retry_after(count)
                raise QuotaExceededError(
                    quota_type="rate_limit",
                    current_value=0,
                    max_value=bucket.capacity,
                    entity_name=key,
                    message=f"Rate limit exceeded for subscription '{subscription_name}'. Retry after {retry_after:.2f} seconds"
                )
    
    def set_queue_rate(self, queue_name: str, rate: int) -> None:
        """
        Set custom rate limit for a queue.
        
        Args:
            queue_name: Name of the queue
            rate: Messages per second
        """
        capacity = rate * self.BURST_MULTIPLIER
        self._queue_buckets[queue_name] = TokenBucket(capacity=capacity, rate=float(rate))
    
    def set_topic_rate(self, topic_name: str, rate: int) -> None:
        """
        Set custom rate limit for a topic.
        
        Args:
            topic_name: Name of the topic
            rate: Messages per second
        """
        capacity = rate * self.BURST_MULTIPLIER
        self._topic_buckets[topic_name] = TokenBucket(capacity=capacity, rate=float(rate))
    
    def _get_queue_bucket(self, queue_name: str) -> TokenBucket:
        """Get or create token bucket for queue."""
        if queue_name not in self._queue_buckets:
            capacity = self.DEFAULT_QUEUE_RATE * self.BURST_MULTIPLIER
            self._queue_buckets[queue_name] = TokenBucket(
                capacity=capacity,
                rate=float(self.DEFAULT_QUEUE_RATE)
            )
        return self._queue_buckets[queue_name]
    
    def _get_topic_bucket(self, topic_name: str) -> TokenBucket:
        """Get or create token bucket for topic."""
        if topic_name not in self._topic_buckets:
            capacity = self.DEFAULT_TOPIC_RATE * self.BURST_MULTIPLIER
            self._topic_buckets[topic_name] = TokenBucket(
                capacity=capacity,
                rate=float(self.DEFAULT_TOPIC_RATE)
            )
        return self._topic_buckets[topic_name]
    
    def _get_subscription_bucket(self, key: str) -> TokenBucket:
        """Get or create token bucket for subscription."""
        if key not in self._subscription_buckets:
            capacity = self.DEFAULT_SUBSCRIPTION_RATE * self.BURST_MULTIPLIER
            self._subscription_buckets[key] = TokenBucket(
                capacity=capacity,
                rate=float(self.DEFAULT_SUBSCRIPTION_RATE)
            )
        return self._subscription_buckets[key]
    
    def reset(self) -> None:
        """Reset all rate limiters (for testing)."""
        self._queue_buckets.clear()
        self._topic_buckets.clear()
        self._subscription_buckets.clear()
