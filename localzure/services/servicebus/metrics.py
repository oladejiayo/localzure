"""
Service Bus Metrics Collection

Prometheus metrics for monitoring Service Bus operations,
message throughput, latency, and system health.

Author: Ayodele Oladeji
Date: 2025-12-08
"""

from typing import Optional, Callable, Any
from functools import wraps
import time
import asyncio

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


class ServiceBusMetrics:
    """
    Prometheus metrics collector for Service Bus operations.
    
    Tracks message operations, entity management, errors, and performance.
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collectors.
        
        Args:
            registry: Prometheus registry (uses default if None)
        """
        self.registry = registry
        
        # Message operation counters
        self.messages_sent_total = Counter(
            'servicebus_messages_sent_total',
            'Total messages sent',
            ['entity_type', 'entity_name'],
            registry=registry
        )
        
        self.messages_received_total = Counter(
            'servicebus_messages_received_total',
            'Total messages received',
            ['entity_type', 'entity_name'],
            registry=registry
        )
        
        self.messages_completed_total = Counter(
            'servicebus_messages_completed_total',
            'Total messages completed',
            ['entity_type', 'entity_name'],
            registry=registry
        )
        
        self.messages_abandoned_total = Counter(
            'servicebus_messages_abandoned_total',
            'Total messages abandoned',
            ['entity_type', 'entity_name'],
            registry=registry
        )
        
        self.messages_deadlettered_total = Counter(
            'servicebus_messages_deadlettered_total',
            'Total messages dead-lettered',
            ['entity_type', 'entity_name', 'reason'],
            registry=registry
        )
        
        # Error counters
        self.errors_total = Counter(
            'servicebus_errors_total',
            'Total errors',
            ['operation', 'error_type'],
            registry=registry
        )
        
        # Entity gauges (current state)
        self.active_messages = Gauge(
            'servicebus_active_messages',
            'Current active messages',
            ['entity_type', 'entity_name'],
            registry=registry
        )
        
        self.deadletter_messages = Gauge(
            'servicebus_deadletter_messages',
            'Current dead-letter messages',
            ['entity_type', 'entity_name'],
            registry=registry
        )
        
        self.scheduled_messages = Gauge(
            'servicebus_scheduled_messages',
            'Current scheduled messages',
            ['entity_type', 'entity_name'],
            registry=registry
        )
        
        self.active_locks = Gauge(
            'servicebus_active_locks',
            'Current active message locks',
            ['entity_type', 'entity_name'],
            registry=registry
        )
        
        self.entity_count = Gauge(
            'servicebus_entity_count',
            'Total entities',
            ['entity_type'],
            registry=registry
        )
        
        # Performance histograms
        self.send_duration_seconds = Histogram(
            'servicebus_send_duration_seconds',
            'Message send duration',
            ['entity_type', 'entity_name'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=registry
        )
        
        self.receive_duration_seconds = Histogram(
            'servicebus_receive_duration_seconds',
            'Message receive duration',
            ['entity_type', 'entity_name'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=registry
        )
        
        self.lock_wait_seconds = Histogram(
            'servicebus_lock_wait_seconds',
            'Time waiting for lock',
            ['entity_type', 'entity_name'],
            buckets=[0.0, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
            registry=registry
        )
        
        self.message_size_bytes = Histogram(
            'servicebus_message_size_bytes',
            'Message size in bytes',
            ['entity_type', 'entity_name'],
            buckets=[100, 1000, 10000, 50000, 100000, 250000],
            registry=registry
        )
        
        self.filter_evaluation_seconds = Histogram(
            'servicebus_filter_evaluation_seconds',
            'Filter evaluation duration',
            buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1],
            registry=registry
        )
    
    def track_message_sent(self, entity_type: str, entity_name: str, size_bytes: int, duration: float) -> None:
        """
        Track message sent operation.
        
        Args:
            entity_type: Type of entity (queue/topic)
            entity_name: Name of entity
            size_bytes: Message size in bytes
            duration: Operation duration in seconds
        """
        self.messages_sent_total.labels(entity_type=entity_type, entity_name=entity_name).inc()
        self.send_duration_seconds.labels(entity_type=entity_type, entity_name=entity_name).observe(duration)
        self.message_size_bytes.labels(entity_type=entity_type, entity_name=entity_name).observe(size_bytes)
    
    def track_message_received(self, entity_type: str, entity_name: str, duration: float) -> None:
        """
        Track message received operation.
        
        Args:
            entity_type: Type of entity (queue/subscription)
            entity_name: Name of entity
            duration: Operation duration in seconds
        """
        self.messages_received_total.labels(entity_type=entity_type, entity_name=entity_name).inc()
        self.receive_duration_seconds.labels(entity_type=entity_type, entity_name=entity_name).observe(duration)
    
    def track_message_completed(self, entity_type: str, entity_name: str) -> None:
        """
        Track message completed operation.
        
        Args:
            entity_type: Type of entity (queue/subscription)
            entity_name: Name of entity
        """
        self.messages_completed_total.labels(entity_type=entity_type, entity_name=entity_name).inc()
    
    def track_message_abandoned(self, entity_type: str, entity_name: str) -> None:
        """
        Track message abandoned operation.
        
        Args:
            entity_type: Type of entity (queue/subscription)
            entity_name: Name of entity
        """
        self.messages_abandoned_total.labels(entity_type=entity_type, entity_name=entity_name).inc()
    
    def track_message_deadlettered(self, entity_type: str, entity_name: str, reason: str) -> None:
        """
        Track message dead-lettered operation.
        
        Args:
            entity_type: Type of entity (queue/subscription)
            entity_name: Name of entity
            reason: Dead-letter reason
        """
        self.messages_deadlettered_total.labels(
            entity_type=entity_type,
            entity_name=entity_name,
            reason=reason
        ).inc()
    
    def track_error(self, operation: str, error_type: str) -> None:
        """
        Track error occurrence.
        
        Args:
            operation: Operation that failed (send_message, create_queue, etc.)
            error_type: Type of error (QueueNotFoundError, TimeoutError, etc.)
        """
        self.errors_total.labels(operation=operation, error_type=error_type).inc()
    
    def update_active_messages(self, entity_type: str, entity_name: str, count: int) -> None:
        """
        Update active message count gauge.
        
        Args:
            entity_type: Type of entity (queue/subscription)
            entity_name: Name of entity
            count: Current active message count
        """
        self.active_messages.labels(entity_type=entity_type, entity_name=entity_name).set(count)
    
    def update_deadletter_messages(self, entity_type: str, entity_name: str, count: int) -> None:
        """
        Update dead-letter message count gauge.
        
        Args:
            entity_type: Type of entity (queue/subscription)
            entity_name: Name of entity
            count: Current dead-letter message count
        """
        self.deadletter_messages.labels(entity_type=entity_type, entity_name=entity_name).set(count)
    
    def update_scheduled_messages(self, entity_type: str, entity_name: str, count: int) -> None:
        """
        Update scheduled message count gauge.
        
        Args:
            entity_type: Type of entity (queue/subscription)
            entity_name: Name of entity
            count: Current scheduled message count
        """
        self.scheduled_messages.labels(entity_type=entity_type, entity_name=entity_name).set(count)
    
    def update_active_locks(self, entity_type: str, entity_name: str, count: int) -> None:
        """
        Update active lock count gauge.
        
        Args:
            entity_type: Type of entity (queue/subscription)
            entity_name: Name of entity
            count: Current active lock count
        """
        self.active_locks.labels(entity_type=entity_type, entity_name=entity_name).set(count)
    
    def update_entity_count(self, entity_type: str, count: int) -> None:
        """
        Update entity count gauge.
        
        Args:
            entity_type: Type of entity (queue/topic/subscription)
            count: Total entity count
        """
        self.entity_count.labels(entity_type=entity_type).set(count)
    
    def track_filter_evaluation(self, duration: float) -> None:
        """
        Track filter evaluation duration.
        
        Args:
            duration: Evaluation duration in seconds
        """
        self.filter_evaluation_seconds.observe(duration)
    
    def generate_metrics(self) -> bytes:
        """
        Generate Prometheus metrics output.
        
        Returns:
            Metrics in Prometheus text format
        """
        from prometheus_client import generate_latest, REGISTRY
        registry = self.registry if self.registry is not None else REGISTRY
        return generate_latest(registry)
    
    def get_content_type(self) -> str:
        """
        Get Prometheus metrics content type.
        
        Returns:
            Content type string
        """
        return CONTENT_TYPE_LATEST


def track_duration(histogram: Histogram):
    """
    Decorator to automatically track operation duration.
    
    Args:
        histogram: Prometheus histogram to record duration
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.perf_counter() - start
                    # Extract labels from function arguments if available
                    # This assumes entity_type and entity_name are in kwargs or args
                    entity_type = kwargs.get('entity_type', 'unknown')
                    entity_name = kwargs.get('entity_name', 'unknown')
                    if len(args) >= 2:
                        if hasattr(args[0], '__class__'):
                            # Skip self/cls argument
                            if len(args) >= 2 and isinstance(args[1], str):
                                entity_name = args[1]
                    histogram.labels(entity_type=entity_type, entity_name=entity_name).observe(duration)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.perf_counter() - start
                    entity_type = kwargs.get('entity_type', 'unknown')
                    entity_name = kwargs.get('entity_name', 'unknown')
                    if len(args) >= 2:
                        if hasattr(args[0], '__class__'):
                            if len(args) >= 2 and isinstance(args[1], str):
                                entity_name = args[1]
                    histogram.labels(entity_type=entity_type, entity_name=entity_name).observe(duration)
            return sync_wrapper
    return decorator


# Global metrics instance
_metrics: Optional[ServiceBusMetrics] = None


def get_metrics() -> ServiceBusMetrics:
    """
    Get global metrics instance (singleton).
    
    Returns:
        ServiceBusMetrics instance
    """
    global _metrics
    if _metrics is None:
        _metrics = ServiceBusMetrics()
    return _metrics


def reset_metrics() -> None:
    """Reset global metrics instance (for testing)."""
    global _metrics
    _metrics = None
