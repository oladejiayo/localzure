# Service Bus Performance Tuning Guide

Optimize LocalZure Service Bus for maximum throughput and minimal latency.

## Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Send latency (P50) | < 1ms | Single message |
| Send latency (P99) | < 5ms | Under load |
| Receive latency (P50) | < 1ms | Peek-lock mode |
| Throughput | 10,000 msg/s | Single queue |
| Filter evaluation | < 0.1ms | Simple SQL filter |
| Memory usage | < 500 MB | 10k active messages |

## Configuration Options

### Environment Variables

```bash
# Queue and Message Limits
export MAX_QUEUE_SIZE=10000              # Messages per queue
export MAX_MESSAGE_SIZE_KB=256           # Max message size
export MAX_ENTITY_COUNT=1000             # Max queues + topics

# Lock and TTL Settings
export LOCK_DURATION_SECONDS=60          # Message lock duration
export DEFAULT_MESSAGE_TTL_SECONDS=1209600  # 14 days
export MAX_DELIVERY_COUNT=10             # Before auto-DLQ

# Performance Tuning
export BACKGROUND_TASK_INTERVAL=10       # Lock cleanup interval (s)
export RATE_LIMIT_MSG_PER_SEC=1000       # Per-queue rate limit
export FILTER_CACHE_SIZE=100             # Parsed filter cache

# Resource Limits
export MAX_CONCURRENT_LOCKS=10000        # Active locks limit
export MAX_SUBSCRIPTIONS_PER_TOPIC=2000  # Subscription limit
```

### YAML Configuration

```yaml
# config.yaml
servicebus:
  performance:
    max_queue_size: 10000
    max_message_size_kb: 256
    lock_duration_seconds: 60
    background_task_interval: 10
    rate_limit_msg_per_sec: 1000
    filter_cache_size: 100
    
  limits:
    max_entity_count: 1000
    max_concurrent_locks: 10000
    max_subscriptions_per_topic: 2000
```

## Optimization Techniques

### 1. Use Correlation Filters

**Problem:** SQL filters are 10-100x slower than correlation filters.

**Solution:**
```python
# Slow (SQL filter)
await create_rule("priority-filter", "priority = 'high'")

# Fast (correlation filter - 10x faster)
await create_correlation_filter({
    "Properties": {"priority": "high"}
})
```

**Performance:**
- SQL filter: 0.1-1ms
- Correlation filter: < 0.01ms
- **Speedup: 10-100x**

### 2. Batch Operations

**Problem:** Sending messages one-by-one is inefficient.

**Solution:**
```python
# Slow (100 round trips)
for msg in messages:
    await sender.send_messages(msg)

# Fast (1-2 round trips)
batch = await sender.create_message_batch()
for msg in messages:
    batch.add_message(msg)
await sender.send_messages(batch)
```

**Performance:**
- Individual sends: ~100 msg/s
- Batch sends: ~10,000 msg/s
- **Speedup: 100x**

### 3. Adjust Lock Duration

**Problem:** Messages re-delivered too quickly or locks held too long.

**Solution:**
```bash
# For fast processing (< 10s)
export LOCK_DURATION_SECONDS=30

# For slow processing (> 60s)
export LOCK_DURATION_SECONDS=300  # 5 minutes
```

**Trade-offs:**
- Short duration: Faster redelivery, more retries
- Long duration: Slower redelivery, holds resources

### 4. Increase Background Task Interval

**Problem:** Lock cleanup runs too frequently, consuming CPU.

**Solution:**
```bash
# Default (every 10s)
export BACKGROUND_TASK_INTERVAL=10

# Optimized for throughput (every 30s)
export BACKGROUND_TASK_INTERVAL=30
```

**Impact:**
- Longer interval: Higher throughput, delayed lock cleanup
- Shorter interval: Lower throughput, faster cleanup

### 5. Simplify SQL Filters

**Problem:** Complex SQL filters slow down message routing.

**Solution:**
```sql
-- Slow (5+ conditions, pattern matching)
(priority = 'high' OR priority = 'urgent')
AND region IN ('us-west', 'us-east', 'eu-west')
AND sys.Label LIKE 'order-%'
AND quantity > 100

-- Fast (1-2 conditions)
priority = 'high' AND region = 'us-west'
```

**Performance by complexity:**
- 1-2 conditions: < 0.1ms
- 3-4 conditions: < 1ms
- 5+ conditions: < 5ms
- Pattern matching: +1-2ms

### 6. Reduce Subscription Count

**Problem:** Every subscription adds filter evaluation overhead.

**Solution:**
```python
# Slow (10 subscriptions, 10 filter evaluations per message)
for i in range(10):
    await create_subscription(f"sub-{i}", f"region = 'region-{i}'")

# Fast (1 subscription, client-side filtering)
await create_subscription("all-regions", "1=1")
# Filter on client side
if message.properties["region"] == "my-region":
    process(message)
```

**Performance:**
- 1 subscription: ~10,000 msg/s
- 10 subscriptions: ~5,000 msg/s
- 100 subscriptions: ~1,000 msg/s

### 7. Use Async Patterns

**Problem:** Blocking I/O reduces throughput.

**Solution:**
```python
# Slow (synchronous, blocking)
for msg in messages:
    result = sender.send_messages(msg)  # Blocks
    process(result)

# Fast (asynchronous, non-blocking)
tasks = [sender.send_messages(msg) for msg in messages]
results = await asyncio.gather(*tasks)
```

**Performance:**
- Sync: 1,000 msg/s
- Async: 10,000 msg/s
- **Speedup: 10x**

### 8. Optimize Message Size

**Problem:** Large messages consume more memory and bandwidth.

**Solution:**
```python
# Large message (256 KB)
message = ServiceBusMessage(large_payload)  # Slow

# Optimized (< 64 KB)
compressed_payload = gzip.compress(large_payload)
message = ServiceBusMessage(compressed_payload)  # Faster

# Or store in blob, send reference
blob_url = upload_to_blob(large_payload)
message = ServiceBusMessage(json.dumps({"blob_url": blob_url}))
```

**Performance by size:**
- < 1 KB: ~15,000 msg/s
- 1-64 KB: ~10,000 msg/s
- 64-256 KB: ~5,000 msg/s

### 9. Session Batching

**Problem:** Processing session messages one-by-one is slow.

**Solution:**
```python
# Slow (1 message at a time)
receiver = await client.accept_session(queue, session_id)
msg = await receiver.receive_messages(max_message_count=1)
process(msg)

# Fast (batch of messages)
receiver = await client.accept_session(queue, session_id)
messages = await receiver.receive_messages(max_message_count=20)
for msg in messages:
    process(msg)
```

**Performance:**
- Single message: ~1,000 msg/s
- Batch (20): ~5,000 msg/s
- **Speedup: 5x**

### 10. Adjust Rate Limits

**Problem:** Default rate limits are too conservative or too aggressive.

**Solution:**
```bash
# Conservative (low throughput, stable)
export RATE_LIMIT_MSG_PER_SEC=100

# Aggressive (high throughput, may spike CPU)
export RATE_LIMIT_MSG_PER_SEC=5000

# Disabled (maximum throughput, no protection)
export RATE_LIMIT_MSG_PER_SEC=0
```

## Benchmarking

### Measure Latency

```python
import time
from azure.servicebus import ServiceBusClient, ServiceBusMessage

client = ServiceBusClient.from_connection_string(CONNECTION_STRING)
sender = client.get_queue_sender("bench-queue")

# Measure send latency
times = []
for i in range(1000):
    start = time.perf_counter()
    sender.send_messages(ServiceBusMessage(f"msg-{i}"))
    elapsed = time.perf_counter() - start
    times.append(elapsed)

import statistics
print(f"P50: {statistics.median(times)*1000:.2f}ms")
print(f"P95: {statistics.quantiles(times, n=20)[18]*1000:.2f}ms")
print(f"P99: {statistics.quantiles(times, n=100)[98]*1000:.2f}ms")
```

### Measure Throughput

```python
import time
from azure.servicebus import ServiceBusClient, ServiceBusMessage

client = ServiceBusClient.from_connection_string(CONNECTION_STRING)
sender = client.get_queue_sender("bench-queue")

# Measure throughput
start = time.time()
batch = sender.create_message_batch()
for i in range(10000):
    batch.add_message(ServiceBusMessage(f"msg-{i}"))
    if i % 1000 == 999:  # Send every 1000
        sender.send_messages(batch)
        batch = sender.create_message_batch()

elapsed = time.time() - start
print(f"Throughput: {10000/elapsed:.0f} msg/s")
```

### Monitor with Prometheus

```promql
# Average send latency (last 5m)
rate(servicebus_send_duration_seconds_sum[5m]) / rate(servicebus_send_duration_seconds_count[5m])

# P95 send latency
histogram_quantile(0.95, rate(servicebus_send_duration_seconds_bucket[5m]))

# Throughput (messages per second)
rate(servicebus_messages_sent_total[1m])

# Error rate
rate(servicebus_errors_total[5m]) / rate(servicebus_messages_sent_total[5m])
```

## Performance Comparison

### LocalZure vs Azure

| Operation | LocalZure | Azure Standard | Azure Premium |
|-----------|-----------|----------------|---------------|
| Send (P50) | < 1ms | 5-20ms | 2-10ms |
| Receive (P50) | < 1ms | 5-20ms | 2-10ms |
| Throughput (queue) | 10k msg/s | 2k msg/s | 4k msg/s |
| Throughput (topic) | 5k msg/s | 500 msg/s | 1k msg/s |
| SQL filter | < 0.1ms | 1-5ms | 0.5-2ms |
| Correlation filter | < 0.01ms | 0.5-2ms | 0.2-1ms |

**Why LocalZure is faster:**
- No network latency (runs locally)
- No TLS overhead
- In-memory storage
- Optimized for development, not durability

### Configuration Presets

**Development (default):**
```bash
MAX_QUEUE_SIZE=10000
LOCK_DURATION_SECONDS=60
BACKGROUND_TASK_INTERVAL=10
RATE_LIMIT_MSG_PER_SEC=1000
```
- Balanced performance
- Good for typical development

**High Throughput:**
```bash
MAX_QUEUE_SIZE=50000
LOCK_DURATION_SECONDS=30
BACKGROUND_TASK_INTERVAL=30
RATE_LIMIT_MSG_PER_SEC=10000
```
- Maximum throughput
- Use for load testing
- Higher memory usage

**Low Latency:**
```bash
MAX_QUEUE_SIZE=1000
LOCK_DURATION_SECONDS=60
BACKGROUND_TASK_INTERVAL=5
RATE_LIMIT_MSG_PER_SEC=1000
```
- Minimal latency
- Fast lock cleanup
- Lower throughput

**Resource Constrained:**
```bash
MAX_QUEUE_SIZE=1000
MAX_ENTITY_COUNT=100
MAX_CONCURRENT_LOCKS=1000
BACKGROUND_TASK_INTERVAL=30
RATE_LIMIT_MSG_PER_SEC=100
```
- Low memory usage
- Suitable for CI/CD
- Limited throughput

## Monitoring Performance

### Key Metrics

```bash
# View all metrics
curl http://localhost:8000/servicebus/metrics | grep servicebus_

# Send duration histogram
servicebus_send_duration_seconds_bucket

# Active messages (queue depth)
servicebus_active_messages

# Throughput
servicebus_messages_sent_total
servicebus_messages_received_total

# Error rate
servicebus_errors_total
```

### Grafana Dashboard

Import `grafana-dashboard.json` for:
- Message latency (P50, P95, P99)
- Throughput (msg/s)
- Queue depths
- Error rates
- Lock counts
- Filter performance

### Performance Alerts

```yaml
# Prometheus alerting rules
groups:
  - name: servicebus-performance
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(servicebus_send_duration_seconds_bucket[5m])) > 0.1
        annotations:
          summary: "P95 latency > 100ms"
          
      - alert: LowThroughput
        expr: rate(servicebus_messages_sent_total[5m]) < 100
        annotations:
          summary: "Throughput < 100 msg/s"
          
      - alert: QueueBacklog
        expr: servicebus_active_messages > 5000
        annotations:
          summary: "Queue has > 5000 messages"
```

## Troubleshooting Performance Issues

### High Latency

**Symptoms:**
- P95 latency > 100ms
- Slow send/receive operations

**Causes & Solutions:**
1. **Complex SQL filters** → Use correlation filters
2. **Too many subscriptions** → Reduce count or simplify filters
3. **Large messages** → Compress or split messages
4. **Frequent background tasks** → Increase `BACKGROUND_TASK_INTERVAL`

### Low Throughput

**Symptoms:**
- < 1,000 msg/s on single queue
- Grafana shows low message rate

**Causes & Solutions:**
1. **Individual sends** → Use batch operations
2. **Synchronous code** → Use async patterns
3. **Rate limits** → Increase `RATE_LIMIT_MSG_PER_SEC`
4. **Many subscriptions** → Reduce fan-out

### High Memory Usage

**Symptoms:**
- Process memory > 1 GB
- System becomes unresponsive

**Causes & Solutions:**
1. **Too many messages** → Reduce `MAX_QUEUE_SIZE`
2. **Large message size** → Compress or reduce size
3. **Not completing messages** → Complete/abandon messages promptly
4. **Too many entities** → Delete unused queues/topics

### High CPU Usage

**Symptoms:**
- CPU > 80%
- System lag

**Causes & Solutions:**
1. **Frequent background tasks** → Increase interval
2. **Complex filters** → Simplify SQL expressions
3. **High message rate** → Add rate limiting
4. **Too many subscriptions** → Reduce count

## Best Practices Summary

1. **Use correlation filters** instead of SQL when possible (10x faster)
2. **Batch operations** for high throughput (100x faster)
3. **Keep messages small** (< 64 KB recommended)
4. **Simplify SQL filters** (< 3 conditions ideal)
5. **Use async patterns** for concurrency
6. **Monitor key metrics** (latency, throughput, errors)
7. **Adjust lock duration** to match processing time
8. **Limit subscriptions** to reduce filter overhead
9. **Complete messages promptly** to avoid memory buildup
10. **Benchmark regularly** to detect regressions

## Related Documentation

- [README](servicebus-README.md)
- [Architecture](servicebus-architecture.md)
- [Troubleshooting](servicebus-troubleshooting.md)
- [Operations Runbook](servicebus-operations.md)
