# Service Bus Logging Guide

This guide explains the observability and logging features of the LocalZure Service Bus implementation.

## Overview

The Service Bus module provides comprehensive structured logging with correlation tracking to help trace message flows and diagnose issues. All logs are output in JSON format for easy parsing and integration with log aggregation tools.

## Features

### Structured JSON Logging

All log entries are formatted as JSON with consistent fields:

```json
{
  "timestamp": "2025-12-05T18:16:07.611757+00:00",
  "level": "INFO",
  "logger": "localzure.services.servicebus.backend",
  "message": "message_sent: queue/orders",
  "correlation_id": "1f8853fe-5221-4039-b7c9-a0d73e7fa9b5",
  "operation": "message_sent",
  "entity_type": "queue",
  "entity_name": "orders",
  "message_id": "122523e3-fc29-45cb-8a42-2a6921e4a19e",
  "sequence_number": 1
}
```

### Correlation ID Tracking

Correlation IDs enable tracing requests across the entire system:

- **Automatic Extraction**: The middleware extracts correlation IDs from incoming HTTP requests (`x-correlation-id` or `correlation-id` headers)
- **UUID Generation**: If no correlation ID is provided, a UUID is automatically generated
- **Context Propagation**: The correlation ID is stored in an async-safe context and automatically included in all log entries
- **Response Headers**: The correlation ID is added to HTTP response headers for client-side tracking

**Example Request:**
```bash
curl -H "x-correlation-id: my-trace-123" \
  -X POST http://localhost:8000/servicebus/test-ns/my-queue/messages \
  -d '{"body": "test message"}'
```

All logs for this request will include `"correlation_id": "my-trace-123"`.

### Operation Logging

Key operations are logged with relevant context:

#### Queue/Topic Operations
- `queue_created`, `queue_deleted`, `queue_updated`
- `topic_created`, `topic_deleted`, `topic_updated`
- `subscription_created`, `subscription_deleted`, `subscription_updated`
- `rule_added`, `rule_deleted`

#### Message Operations
- `message_sent` - Message sent to queue/topic
- `topic_fan_out` - Message distributed to matching subscriptions
- `message_received` - Message received from queue/subscription
- `message_completed` - Message processing completed
- `message_abandoned` - Message processing abandoned
- `message_deadlettered` - Message moved to dead-letter queue

#### Lock Operations
- `lock_acquired` - Message lock obtained
- `lock_renewed` - Message lock extended
- `lock_released` - Message lock released
- `lock_expired` - Message lock timed out

#### Filter Evaluation
- `filter_evaluated` - Subscription filter applied to message

## Configuration

### Setting Log Level

Configure the logging level using the `configure_logging` function:

```python
from localzure.services.servicebus.logging_utils import configure_logging

# Set to DEBUG for detailed operation tracing
configure_logging(level='DEBUG', json_format=True)

# Set to INFO for normal operations (default)
configure_logging(level='INFO', json_format=True)

# Set to ERROR for production (errors only)
configure_logging(level='ERROR', json_format=True)
```

### Using Plain Text Format

For local development, you can use plain text logging:

```python
from localzure.services.servicebus.logging_utils import configure_logging

configure_logging(level='DEBUG', json_format=False)
```

This outputs logs in standard format:
```
2025-12-05 18:16:07,611 - INFO - localzure.services.servicebus.backend - message_sent: queue/orders
```

### Adding Correlation Middleware

The correlation middleware is automatically included when using the Service Bus API. If you need to add it to a custom FastAPI application:

```python
from fastapi import FastAPI
from localzure.services.servicebus.middleware import CorrelationMiddleware
from localzure.services.servicebus.api import router

app = FastAPI()
app.add_middleware(CorrelationMiddleware)
app.include_router(router)
```

## Usage Examples

### Tracing a Message Flow

Send a message with a correlation ID and trace its path through the system:

```bash
# Send message with correlation ID
curl -H "x-correlation-id: trace-001" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8000/servicebus/test-ns/my-topic/messages \
  -d '{"body": "urgent order", "label": "order"}'
```

**Log Output:**
```json
{"timestamp": "...", "level": "INFO", "operation": "request_started", 
 "correlation_id": "trace-001", "method": "POST", "path": "/servicebus/test-ns/my-topic/messages"}

{"timestamp": "...", "level": "INFO", "operation": "message_sent", 
 "correlation_id": "trace-001", "entity_type": "topic", "entity_name": "my-topic",
 "message_id": "a1b2c3d4-...", "sequence_number": 0}

{"timestamp": "...", "level": "INFO", "operation": "filter_evaluated",
 "correlation_id": "trace-001", "subscription_name": "sub-1", 
 "filter_expression": "TrueFilter", "filter_result": true}

{"timestamp": "...", "level": "INFO", "operation": "topic_fan_out",
 "correlation_id": "trace-001", "entity_name": "my-topic",
 "matched_subscriptions": 3, "total_subscriptions": 5}

{"timestamp": "...", "level": "INFO", "operation": "request_completed",
 "correlation_id": "trace-001", "duration_ms": 2.45}
```

### Filtering Logs by Operation

Parse JSON logs to filter specific operations:

```bash
# Get all filter evaluation logs
cat logs/servicebus.log | jq 'select(.operation == "filter_evaluated")'

# Get all messages sent to a specific topic
cat logs/servicebus.log | jq 'select(.operation == "message_sent" and .entity_name == "orders")'

# Get all errors for a correlation ID
cat logs/servicebus.log | jq 'select(.correlation_id == "trace-001" and .level == "ERROR")'
```

### Debugging Lock Timeouts

Track lock operations for a specific message:

```bash
# Find all lock-related logs for a message
cat logs/servicebus.log | jq 'select(.message_id == "a1b2c3d4-...")'
```

**Example Output:**
```json
{"operation": "lock_acquired", "message_id": "a1b2c3d4-...", "lock_duration_seconds": 60}
{"operation": "lock_renewed", "message_id": "a1b2c3d4-...", "new_lock_duration_seconds": 60}
{"operation": "lock_expired", "message_id": "a1b2c3d4-...", "lock_duration_seconds": 60}
```

## Log Fields Reference

### Common Fields (All Logs)
- `timestamp` (ISO 8601): When the log entry was created
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logger`: Logger name (usually module path)
- `message`: Human-readable description
- `correlation_id` (UUID): Request correlation identifier

### Operation-Specific Fields

#### Entity Operations
- `operation`: Operation type (e.g., `queue_created`)
- `entity_type`: Entity type (`queue`, `topic`, `subscription`)
- `entity_name`: Entity name

#### Message Operations
- `message_id` (UUID): Unique message identifier
- `sequence_number` (int): Message sequence number
- `delivery_count` (int): Number of delivery attempts
- `message_size_bytes` (int): Message body size

#### Filter Operations
- `filter_expression` (string): SQL or correlation filter expression
- `filter_result` (boolean): Whether message matched filter
- `subscription_name` (string): Target subscription

#### Lock Operations
- `lock_duration_seconds` (int): Lock duration
- `locked_until` (ISO 8601): Lock expiration time

#### Request Operations
- `method`: HTTP method (GET, POST, PUT, DELETE)
- `path`: Request path
- `status_code` (int): HTTP response status
- `duration_ms` (float): Request processing time

#### Error Operations
- `error_type`: Exception class name
- `error_message`: Error description
- `stack_trace`: Full exception traceback

## Performance Considerations

- **Lazy Evaluation**: Log message formatting is deferred until the log is actually output
- **Minimal Overhead**: Logging adds < 1ms per operation on average
- **Async-Safe**: Uses `contextvars` for thread-safe correlation tracking in async operations
- **Configurable**: Set log level to ERROR in production to minimize overhead

## Integration with Monitoring Tools

### Elastic Stack (ELK)

Configure Filebeat to ship JSON logs:

```yaml
filebeat.inputs:
  - type: log
    paths:
      - /var/log/localzure/servicebus.log
    json.keys_under_root: true
    json.add_error_key: true
```

### Splunk

Configure Splunk to parse JSON logs:

```conf
[localzure_servicebus]
INDEXED_EXTRACTIONS = json
KV_MODE = json
TIME_PREFIX = "timestamp":"
TIME_FORMAT = %Y-%m-%dT%H:%M:%S.%6N%z
```

### CloudWatch

Use AWS CloudWatch Logs agent with JSON parsing:

```json
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/localzure/servicebus.log",
            "log_group_name": "/localzure/servicebus",
            "log_stream_name": "{instance_id}",
            "timestamp_format": "%Y-%m-%dT%H:%M:%S.%fZ"
          }
        ]
      }
    }
  }
}
```

## Troubleshooting

### Missing Correlation IDs

If correlation IDs are not appearing in logs:

1. Verify middleware is registered:
   ```python
   app.add_middleware(CorrelationMiddleware)
   ```

2. Check that middleware is added before the router:
   ```python
   app.add_middleware(CorrelationMiddleware)  # Add middleware first
   app.include_router(router)                  # Then add router
   ```

### Logs Not in JSON Format

Ensure JSON formatting is enabled:

```python
from localzure.services.servicebus.logging_utils import configure_logging

configure_logging(level='INFO', json_format=True)  # json_format=True
```

### Performance Issues

If logging is causing performance degradation:

1. Increase log level to reduce volume:
   ```python
   configure_logging(level='WARNING')  # Only warnings and errors
   ```

2. Disable verbose filter evaluation logging:
   ```python
   # In backend.py, comment out filter_evaluated log calls
   ```

3. Use async file handlers to avoid blocking I/O

## Best Practices

1. **Always use correlation IDs** for multi-step operations
2. **Set appropriate log levels** (DEBUG for dev, INFO for staging, ERROR for production)
3. **Parse logs with jq or similar tools** for analysis
4. **Archive logs regularly** to prevent disk space issues
5. **Monitor log volume** to detect abnormal activity
6. **Use structured queries** when searching logs (don't grep plain text)
7. **Configure log rotation** (logrotate on Linux, Windows Event Log rotation)

## Example: Complete Debugging Workflow

**Scenario**: A message is not being delivered to a subscription.

**Step 1**: Send message with correlation ID
```bash
curl -H "x-correlation-id: debug-123" \
  -X POST http://localhost:8000/servicebus/test-ns/events/messages \
  -d '{"body": "test", "label": "important"}'
```

**Step 2**: Find all logs for this request
```bash
cat logs/servicebus.log | jq 'select(.correlation_id == "debug-123")'
```

**Step 3**: Check filter evaluation
```bash
cat logs/servicebus.log | jq 'select(.correlation_id == "debug-123" and .operation == "filter_evaluated")'
```

**Output shows**:
```json
{"operation": "filter_evaluated", "subscription_name": "sub-1", 
 "filter_expression": "priority = 'high'", "filter_result": false}
```

**Step 4**: Identify root cause
The message doesn't have a `priority` property set to `'high'`, so it's being filtered out.

**Step 5**: Fix and verify
Update message properties and resend with same correlation ID to confirm fix.

## API Reference

For programmatic logging:

```python
from localzure.services.servicebus.logging_utils import (
    StructuredLogger,
    CorrelationContext,
    configure_logging,
    track_operation_time
)

# Create logger
logger = StructuredLogger('my.module')

# Log operations
logger.log_operation('custom_operation', entity_type='queue', entity_name='test')

# Log messages
logger.log_message_operation('message_sent', 'msg-id-123', sequence_number=1)

# Log filters
logger.log_filter_evaluation('priority = "high"', True, 'msg-id-123', 'sub-1')

# Log locks
logger.log_lock_operation('lock_acquired', 'msg-id-123', lock_duration_seconds=60)

# Get/set correlation ID
from localzure.services.servicebus.logging_utils import CorrelationContext

correlation_id = CorrelationContext.get()
CorrelationContext.set('my-custom-id')
CorrelationContext.clear()

# Track operation timing
@track_operation_time('my_operation')
async def my_function():
    await some_async_work()
```
