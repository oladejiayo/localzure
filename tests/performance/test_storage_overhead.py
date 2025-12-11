"""
Performance tests for Service Bus persistence layer.

Validates that persistence overhead stays within acceptable limits:
- SQLite: < 10% overhead vs in-memory
- JSON: < 25% overhead vs in-memory
- Snapshot operations: < 100ms for typical workload

Author: LocalZure Contributors
Date: 2025-12-11
"""

import asyncio
import time
import tempfile
from pathlib import Path
from typing import List, Dict, Any

import pytest

from localzure.services.servicebus.backend import ServiceBusBackend
from localzure.services.servicebus.storage import StorageConfig, StorageType
from localzure.services.servicebus.models import (
    QueueProperties,
    SendMessageRequest,
)


class PerformanceMetrics:
    """Container for performance measurements."""
    
    def __init__(self, name: str):
        self.name = name
        self.operations = 0
        self.total_time = 0.0
        self.latencies: List[float] = []
    
    def record(self, duration: float):
        """Record a single operation duration."""
        self.operations += 1
        self.total_time += duration
        self.latencies.append(duration)
    
    @property
    def throughput(self) -> float:
        """Operations per second."""
        return self.operations / self.total_time if self.total_time > 0 else 0
    
    @property
    def avg_latency(self) -> float:
        """Average latency in milliseconds."""
        return (sum(self.latencies) / len(self.latencies) * 1000) if self.latencies else 0
    
    @property
    def p50_latency(self) -> float:
        """P50 latency in milliseconds."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.5)
        return sorted_latencies[idx] * 1000
    
    @property
    def p95_latency(self) -> float:
        """P95 latency in milliseconds."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx] * 1000
    
    @property
    def p99_latency(self) -> float:
        """P99 latency in milliseconds."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx] * 1000
    
    def overhead_vs(self, baseline: 'PerformanceMetrics') -> float:
        """Calculate overhead percentage vs baseline."""
        if baseline.throughput == 0:
            return 0
        return ((baseline.throughput - self.throughput) / baseline.throughput) * 100
    
    def __str__(self) -> str:
        return (
            f"{self.name}:\n"
            f"  Operations:  {self.operations}\n"
            f"  Total Time:  {self.total_time:.2f}s\n"
            f"  Throughput:  {self.throughput:.0f} ops/s\n"
            f"  Avg Latency: {self.avg_latency:.2f}ms\n"
            f"  P50 Latency: {self.p50_latency:.2f}ms\n"
            f"  P95 Latency: {self.p95_latency:.2f}ms\n"
            f"  P99 Latency: {self.p99_latency:.2f}ms"
        )


@pytest.fixture
async def temp_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


async def benchmark_send_operations(
    backend: ServiceBusBackend,
    queue_name: str,
    num_operations: int = 1000
) -> PerformanceMetrics:
    """
    Benchmark message send operations.
    
    Args:
        backend: Service Bus backend to test
        queue_name: Queue to send messages to
        num_operations: Number of messages to send
        
    Returns:
        Performance metrics
    """
    metrics = PerformanceMetrics(f"send_{num_operations}_messages")
    
    for i in range(num_operations):
        start = time.perf_counter()
        
        request = SendMessageRequest(
            body={"test": f"message_{i}", "index": i},
            user_properties={"seq": str(i)},
        )
        await backend.send_message(queue_name, request)
        
        duration = time.perf_counter() - start
        metrics.record(duration)
    
    return metrics


async def benchmark_receive_operations(
    backend: ServiceBusBackend,
    queue_name: str,
    num_operations: int = 1000
) -> PerformanceMetrics:
    """
    Benchmark message receive operations.
    
    Args:
        backend: Service Bus backend to test
        queue_name: Queue to receive messages from
        num_operations: Number of messages to receive
        
    Returns:
        Performance metrics
    """
    metrics = PerformanceMetrics(f"receive_{num_operations}_messages")
    
    for i in range(num_operations):
        start = time.perf_counter()
        
        msg = await backend.receive_message(queue_name, timeout_seconds=1)
        if msg:
            await backend.complete_message(queue_name, msg.lock_token)
        
        duration = time.perf_counter() - start
        metrics.record(duration)
    
    return metrics


async def benchmark_snapshot(backend: ServiceBusBackend) -> float:
    """
    Benchmark snapshot operation duration.
    
    Args:
        backend: Service Bus backend to test
        
    Returns:
        Snapshot duration in milliseconds
    """
    if not backend._persistence_enabled or not backend._storage:
        return 0
    
    start = time.perf_counter()
    await backend._persist_current_state()
    duration = time.perf_counter() - start
    
    return duration * 1000  # Convert to ms


@pytest.mark.asyncio
@pytest.mark.performance
async def test_sqlite_overhead_within_limits(temp_dir):
    """
    Test that SQLite persistence overhead is < 10% vs in-memory.
    
    This is a critical performance requirement for production use.
    """
    num_operations = 500  # Reduced for faster tests
    
    # Benchmark 1: In-memory (baseline)
    backend_mem = ServiceBusBackend()
    queue_name = "perf-test-queue"
    
    await backend_mem.create_queue(
        name=queue_name,
        properties=QueueProperties(),
    )
    
    metrics_mem_send = await benchmark_send_operations(backend_mem, queue_name, num_operations)
    metrics_mem_recv = await benchmark_receive_operations(backend_mem, queue_name, num_operations)
    
    # Benchmark 2: SQLite
    config_sqlite = StorageConfig(
        storage_type=StorageType.SQLITE,
        sqlite_path=str(temp_dir / "perf.db"),
        snapshot_interval_seconds=0,  # Disable auto-snapshots
        wal_enabled=True,
    )
    
    backend_sqlite = ServiceBusBackend(storage_config=config_sqlite)
    await backend_sqlite.initialize_persistence()
    
    try:
        await backend_sqlite.create_queue(
            name=queue_name,
            properties=QueueProperties(),
        )
        
        metrics_sqlite_send = await benchmark_send_operations(backend_sqlite, queue_name, num_operations)
        metrics_sqlite_recv = await benchmark_receive_operations(backend_sqlite, queue_name, num_operations)
        
        # Calculate overhead
        send_overhead = metrics_sqlite_send.overhead_vs(metrics_mem_send)
        recv_overhead = metrics_sqlite_recv.overhead_vs(metrics_mem_recv)
        
        # Print results
        print("\n" + "=" * 60)
        print("PERFORMANCE COMPARISON: SQLite vs In-Memory")
        print("=" * 60)
        print("\n[BASELINE] In-Memory:")
        print(f"  Send:    {metrics_mem_send.throughput:.0f} ops/s")
        print(f"  Receive: {metrics_mem_recv.throughput:.0f} ops/s")
        print("\n[TEST] SQLite:")
        print(f"  Send:    {metrics_sqlite_send.throughput:.0f} ops/s (overhead: {send_overhead:.1f}%)")
        print(f"  Receive: {metrics_sqlite_recv.throughput:.0f} ops/s (overhead: {recv_overhead:.1f}%)")
        print("\n" + "=" * 60)
        
        # Assertions
        assert send_overhead < 10, f"SQLite send overhead ({send_overhead:.1f}%) exceeds 10% limit"
        assert recv_overhead < 10, f"SQLite receive overhead ({recv_overhead:.1f}%) exceeds 10% limit"
    
    finally:
        await backend_sqlite.shutdown_persistence()


@pytest.mark.asyncio
@pytest.mark.performance
async def test_json_overhead_within_limits(temp_dir):
    """
    Test that JSON persistence overhead is < 25% vs in-memory.
    
    JSON is expected to be slower but still acceptable for development use.
    """
    num_operations = 200  # Reduced for JSON (slower)
    
    # Benchmark 1: In-memory (baseline)
    backend_mem = ServiceBusBackend()
    queue_name = "perf-test-queue"
    
    await backend_mem.create_queue(
        name=queue_name,
        properties=QueueProperties(),
    )
    
    metrics_mem = await benchmark_send_operations(backend_mem, queue_name, num_operations)
    
    # Benchmark 2: JSON
    config_json = StorageConfig(
        storage_type=StorageType.JSON,
        json_path=str(temp_dir),
        snapshot_interval_seconds=0,  # Disable auto-snapshots
        wal_enabled=False,
    )
    
    backend_json = ServiceBusBackend(storage_config=config_json)
    await backend_json.initialize_persistence()
    
    try:
        await backend_json.create_queue(
            name=queue_name,
            properties=QueueProperties(),
        )
        
        metrics_json = await benchmark_send_operations(backend_json, queue_name, num_operations)
        
        # Calculate overhead
        overhead = metrics_json.overhead_vs(metrics_mem)
        
        # Print results
        print("\n" + "=" * 60)
        print("PERFORMANCE COMPARISON: JSON vs In-Memory")
        print("=" * 60)
        print(f"\n[BASELINE] In-Memory: {metrics_mem.throughput:.0f} ops/s")
        print(f"[TEST] JSON:          {metrics_json.throughput:.0f} ops/s (overhead: {overhead:.1f}%)")
        print("=" * 60)
        
        # Assertion
        assert overhead < 25, f"JSON overhead ({overhead:.1f}%) exceeds 25% limit"
    
    finally:
        await backend_json.shutdown_persistence()


@pytest.mark.asyncio
@pytest.mark.performance
async def test_snapshot_performance(temp_dir):
    """
    Test that snapshot operations complete quickly (< 100ms for typical workload).
    
    Snapshots should not cause noticeable pauses in message processing.
    """
    config = StorageConfig(
        storage_type=StorageType.SQLITE,
        sqlite_path=str(temp_dir / "snapshot.db"),
        snapshot_interval_seconds=0,  # Manual snapshots only
        wal_enabled=True,
    )
    
    backend = ServiceBusBackend(storage_config=config)
    await backend.initialize_persistence()
    
    try:
        # Create typical workload: 3 queues, 1 topic, 2 subscriptions
        for i in range(3):
            await backend.create_queue(
                name=f"queue-{i}",
                properties=QueueProperties(),
            )
            
            # Send 50 messages to each queue
            for j in range(50):
                request = SendMessageRequest(
                    body={"queue": i, "msg": j},
                )
                await backend.send_message(f"queue-{i}", request)
        
        # Create topic and subscriptions
        await backend.create_topic(
            name="test-topic",
            properties=None,
        )
        
        for i in range(2):
            await backend.create_subscription(
                topic_name="test-topic",
                subscription_name=f"sub-{i}",
                properties=None,
            )
        
        # Benchmark snapshot
        snapshot_duration = await benchmark_snapshot(backend)
        
        print("\n" + "=" * 60)
        print("SNAPSHOT PERFORMANCE")
        print("=" * 60)
        print(f"Workload:   3 queues, 150 messages, 1 topic, 2 subscriptions")
        print(f"Duration:   {snapshot_duration:.2f}ms")
        print(f"Limit:      100ms")
        print("=" * 60)
        
        # Assertion
        assert snapshot_duration < 100, f"Snapshot took {snapshot_duration:.2f}ms (limit: 100ms)"
    
    finally:
        await backend.shutdown_persistence()


@pytest.mark.asyncio
@pytest.mark.performance
async def test_concurrent_operations_scaling(temp_dir):
    """
    Test that persistence maintains performance under concurrent load.
    
    Validates that locking doesn't create bottlenecks.
    """
    config = StorageConfig(
        storage_type=StorageType.SQLITE,
        sqlite_path=str(temp_dir / "concurrent.db"),
        snapshot_interval_seconds=0,
        wal_enabled=True,
    )
    
    backend = ServiceBusBackend(storage_config=config)
    await backend.initialize_persistence()
    
    try:
        # Create 5 queues
        num_queues = 5
        for i in range(num_queues):
            await backend.create_queue(
                name=f"queue-{i}",
                properties=QueueProperties(),
            )
        
        # Concurrent sends to different queues
        async def send_batch(queue_idx: int, num_msgs: int):
            for i in range(num_msgs):
                request = SendMessageRequest(
                    body={"queue": queue_idx, "msg": i},
                )
                await backend.send_message(f"queue-{queue_idx}", request)
        
        start = time.perf_counter()
        
        # Run 5 concurrent senders, each sending 50 messages
        tasks = [send_batch(i, 50) for i in range(num_queues)]
        await asyncio.gather(*tasks)
        
        duration = time.perf_counter() - start
        total_ops = num_queues * 50
        throughput = total_ops / duration
        
        print("\n" + "=" * 60)
        print("CONCURRENT OPERATIONS PERFORMANCE")
        print("=" * 60)
        print(f"Concurrent tasks:  {num_queues}")
        print(f"Total operations:  {total_ops}")
        print(f"Duration:          {duration:.2f}s")
        print(f"Throughput:        {throughput:.0f} ops/s")
        print("=" * 60)
        
        # Expect at least 200 ops/s with concurrency
        assert throughput > 200, f"Concurrent throughput ({throughput:.0f} ops/s) too low"
    
    finally:
        await backend.shutdown_persistence()


@pytest.mark.asyncio
@pytest.mark.performance
async def test_large_message_performance(temp_dir):
    """
    Test performance with larger messages (close to size limit).
    
    Validates that persistence scales with message size.
    """
    config = StorageConfig(
        storage_type=StorageType.SQLITE,
        sqlite_path=str(temp_dir / "large.db"),
        snapshot_interval_seconds=0,
        wal_enabled=True,
    )
    
    backend = ServiceBusBackend(storage_config=config)
    await backend.initialize_persistence()
    
    try:
        queue_name = "large-msg-queue"
        await backend.create_queue(
            name=queue_name,
            properties=QueueProperties(),
        )
        
        # Create large message (200 KB)
        large_body = {"data": "x" * (200 * 1024)}
        
        metrics = PerformanceMetrics("large_messages")
        num_messages = 20  # Fewer operations for large messages
        
        for i in range(num_messages):
            start = time.perf_counter()
            
            request = SendMessageRequest(
                body=large_body,
                user_properties={"index": str(i)},
            )
            await backend.send_message(queue_name, request)
            
            duration = time.perf_counter() - start
            metrics.record(duration)
        
        print("\n" + "=" * 60)
        print("LARGE MESSAGE PERFORMANCE")
        print("=" * 60)
        print(f"Message size:  200 KB")
        print(f"Operations:    {metrics.operations}")
        print(f"Avg latency:   {metrics.avg_latency:.2f}ms")
        print(f"P95 latency:   {metrics.p95_latency:.2f}ms")
        print("=" * 60)
        
        # Large messages should complete within reasonable time (< 50ms avg)
        assert metrics.avg_latency < 50, f"Large message latency ({metrics.avg_latency:.2f}ms) too high"
    
    finally:
        await backend.shutdown_persistence()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance"])
