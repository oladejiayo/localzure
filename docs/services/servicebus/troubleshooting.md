# Service Bus Troubleshooting Guide

Common issues and solutions for LocalZure Service Bus emulator.

## Quick Diagnostics

### Health Check

```bash
# Check if service is running
curl http://localhost:8000/servicebus/health

# Check readiness
curl http://localhost:8000/servicebus/health/ready

# Check liveness
curl http://localhost:8000/servicebus/health/live
```

### View Metrics

```bash
# Prometheus metrics
curl http://localhost:8000/servicebus/metrics | grep servicebus_
```

### Check Logs

```bash
# Follow logs
tail -f localzure.log

# Search for errors
grep "ERROR" localzure.log

# Filter by correlation ID
grep "correlation_id.*abc-123" localzure.log
```

## Common Issues

### 1. "Queue Not Found" Error

**Symptom:**
```
QueueNotFoundError: Queue 'myqueue' does not exist
```

**Causes:**
- Queue not created
- Typo in queue name (case-sensitive)
- Queue was deleted

**Solutions:**

1. **List all queues:**
   ```bash
   curl http://localhost:8000/servicebus/queues
   ```

2. **Create the queue:**
   ```bash
   curl -X PUT http://localhost:8000/servicebus/queues/myqueue \
     -H "Content-Type: application/xml" \
     -d '<entry xmlns="http://www.w3.org/2005/Atom"><content type="application/xml"><QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"></QueueDescription></content></entry>'
   ```

3. **Check queue name** - names are case-sensitive

### 2. Message Stuck in Active State

**Symptom:**
- Messages received but never completed
- ActiveMessageCount keeps growing
- Messages reappear after lock expires

**Causes:**
- `complete_message()` not called
- Lock expired before completion
- Exception in message processing

**Solutions:**

1. **Always complete or abandon messages:**
   ```python
   with client.get_queue_receiver("myqueue") as receiver:
       for msg in receiver:
           try:
               # Process message
               process(msg)
               receiver.complete_message(msg)
           except Exception as e:
               print(f"Error: {e}")
               receiver.abandon_message(msg)
   ```

2. **Increase lock duration:**
   ```bash
   # Update queue properties
   curl -X PUT http://localhost:8000/servicebus/queues/myqueue \
     -H "Content-Type: application/xml" \
     -d '<entry xmlns="http://www.w3.org/2005/Atom"><content type="application/xml"><QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"><LockDuration>PT300S</LockDuration></QueueDescription></content></entry>'
   ```

3. **Renew lock for long processing:**
   ```python
   message = receiver.receive_messages(max_wait_time=5)
   receiver.renew_message_lock(message)  # Extend lock
   process(message)
   receiver.complete_message(message)
   ```

### 3. No Messages Received from Subscription

**Symptom:**
- Messages sent to topic
- Subscription receives nothing
- Other subscriptions work fine

**Causes:**
- Filter doesn't match message properties
- No default rule and no matching rules
- Typo in property names

**Solutions:**

1. **Check subscription rules:**
   ```bash
   curl http://localhost:8000/servicebus/topics/mytopic/subscriptions/mysub/rules
   ```

2. **Verify message properties:**
   ```python
   # Send with required properties
   message = ServiceBusMessage(
       "test",
       application_properties={"priority": "high", "region": "us-west"}
   )
   sender.send_messages(message)
   ```

3. **Test with match-all filter:**
   ```bash
   # Delete existing rules
   curl -X DELETE http://localhost:8000/servicebus/topics/mytopic/subscriptions/mysub/rules/myfilter
   
   # Add default rule (matches everything)
   curl -X PUT http://localhost:8000/servicebus/topics/mytopic/subscriptions/mysub/rules/$Default \
     -H "Content-Type: application/xml" \
     -d '<entry xmlns="http://www.w3.org/2005/Atom"><content type="application/xml"><RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"><Filter><TrueFilter/></Filter></RuleDescription></content></entry>'
   ```

4. **Check property names (case-sensitive):**
   ```python
   # Wrong - won't match filter "Priority = 'high'"
   {"priority": "high"}
   
   # Correct
   {"Priority": "high"}
   ```

### 4. High Latency / Slow Performance

**Symptom:**
- Send/receive operations take > 100ms
- Grafana shows high P95/P99 latency
- System feels sluggish

**Causes:**
- Complex SQL filters
- Too many subscriptions with filters
- Lock expiration background task overhead
- Memory pressure

**Solutions:**

1. **Simplify SQL filters:**
   ```sql
   -- Slow (5+ conditions)
   (a = 1 AND b = 2) OR (c = 3 AND d = 4) OR (e = 5 AND f = 6)
   
   -- Fast (< 3 conditions)
   priority = 'high' AND region = 'us-west'
   ```

2. **Use correlation filters:**
   ```json
   // 10x faster than SQL
   {
     "Properties": {
       "priority": "high",
       "region": "us-west"
     }
   }
   ```

3. **Reduce subscription count:**
   - Combine similar subscriptions
   - Use broader filters with client-side filtering

4. **Check metrics:**
   ```bash
   # View filter evaluation time
   curl http://localhost:8000/servicebus/metrics | grep filter_evaluation
   ```

5. **Increase background task interval:**
   ```bash
   export SERVICEBUS_BACKGROUND_TASK_INTERVAL=30  # 30 seconds instead of 10
   ```

### 5. Memory Usage Growing

**Symptom:**
- Process memory keeps increasing
- System becomes unresponsive
- Out of memory errors

**Causes:**
- Messages not being completed (accumulating in memory)
- Large dead-letter queue
- Too many queues/topics created
- Message size too large

**Solutions:**

1. **Complete messages:**
   ```python
   # Always complete or abandon
   receiver.complete_message(msg)
   ```

2. **Check message counts:**
   ```bash
   curl http://localhost:8000/servicebus/metrics | grep active_messages
   curl http://localhost:8000/servicebus/metrics | grep deadletter_messages
   ```

3. **Purge dead-letter queue:**
   ```python
   # Receive and complete all DLQ messages
   dlq_receiver = client.get_queue_receiver("myqueue", sub_queue=ServiceBusSubQueue.DEAD_LETTER)
   for msg in dlq_receiver:
       dlq_receiver.complete_message(msg)
   ```

4. **Delete unused entities:**
   ```bash
   curl -X DELETE http://localhost:8000/servicebus/queues/unused-queue
   ```

5. **Set message size limits:**
   ```python
   # Keep messages small (< 64 KB recommended)
   message = ServiceBusMessage(json.dumps(data)[:65536])
   ```

### 6. "Message Lock Lost" Error

**Symptom:**
```
MessageLockLostError: The lock supplied is invalid
```

**Causes:**
- Lock expired (default 60s)
- Message already completed/abandoned
- Lock token mismatch

**Solutions:**

1. **Process messages faster:**
   ```python
   # Complete within lock duration
   for msg in receiver:
       quick_process(msg)  # < 60 seconds
       receiver.complete_message(msg)
   ```

2. **Renew lock:**
   ```python
   for msg in receiver:
       # Renew every 30 seconds for long processing
       while processing:
           receiver.renew_message_lock(msg)
           time.sleep(30)
   ```

3. **Increase lock duration:**
   ```bash
   # Set to 5 minutes
   curl -X PUT http://localhost:8000/servicebus/queues/myqueue \
     -H "Content-Type: application/xml" \
     -d '<entry xmlns="http://www.w3.org/2005/Atom"><content type="application/xml"><QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"><LockDuration>PT300S</LockDuration></QueueDescription></content></entry>'
   ```

### 7. SQL Filter Syntax Error

**Symptom:**
```
InvalidOperationError: Invalid SQL expression
```

**Common Mistakes:**

1. **Using double quotes instead of single:**
   ```sql
   -- Wrong
   priority = "high"
   
   -- Correct
   priority = 'high'
   ```

2. **Wrong operator spelling:**
   ```sql
   -- Wrong
   priority = 'high' and region = 'us-west'
   
   -- Correct (uppercase)
   priority = 'high' AND region = 'us-west'
   ```

3. **Unmatched parentheses:**
   ```sql
   -- Wrong
   (a = 1 AND (b = 2)
   
   -- Correct
   (a = 1 AND (b = 2))
   ```

4. **Invalid property names:**
   ```sql
   -- Wrong (special characters)
   sys.my-property = 'value'
   
   -- Correct (underscores only)
   sys.my_property = 'value'
   ```

**Solution:** Validate filter syntax before creating rule.

### 8. Connection Refused

**Symptom:**
```
ConnectionError: Connection refused to localhost:8000
```

**Causes:**
- Service not running
- Wrong port
- Firewall blocking

**Solutions:**

1. **Check if service is running:**
   ```bash
   # Linux/Mac
   ps aux | grep localzure
   
   # Windows
   tasklist | findstr localzure
   ```

2. **Start the service:**
   ```bash
   localzure start
   ```

3. **Check port:**
   ```bash
   # See what's listening on port 8000
   netstat -an | grep 8000
   ```

4. **Try different port:**
   ```bash
   localzure start --port 9000
   ```

### 9. Rate Limit Exceeded

**Symptom:**
```
QuotaExceededError: Rate limit exceeded
```

**Causes:**
- Sending too many messages too fast
- Rate limit configured too low

**Solutions:**

1. **Add delays:**
   ```python
   for msg in messages:
       sender.send_messages(msg)
       time.sleep(0.01)  # 100 msg/s
   ```

2. **Increase rate limit:**
   ```bash
   export RATE_LIMIT_QUEUE_MSG_PER_SEC=500
   localzure start
   ```

3. **Use batch sends:**
   ```python
   # Send multiple messages at once
   batch = [ServiceBusMessage(f"msg{i}") for i in range(10)]
   sender.send_messages(batch)
   ```

### 10. Entity Name Invalid

**Symptom:**
```
InvalidQueueNameError: Queue name contains invalid characters
```

**Rules:**
- 1-260 characters
- Letters, numbers, hyphens, underscores, periods, forward slashes
- Cannot start/end with hyphen or period
- No consecutive hyphens
- Case-sensitive
- No reserved words (e.g., "default", "null")

**Solutions:**

1. **Use valid characters:**
   ```python
   # Wrong
   queue_name = "my queue!"
   
   # Correct
   queue_name = "my-queue"
   ```

2. **Check reserved words:**
   ```python
   # Wrong
   queue_name = "default"
   
   # Correct
   queue_name = "default-queue"
   ```

## Debugging Tips

### Enable Debug Logging

```bash
# Environment variable
export LOG_LEVEL=DEBUG
localzure start

# Or in Python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Trace Message Flow

```python
# Add correlation IDs
message = ServiceBusMessage(
    "test",
    correlation_id="trace-12345"
)
sender.send_messages(message)

# Search logs
grep "trace-12345" localzure.log
```

### Use Metrics for Diagnostics

```bash
# Check error rates
curl http://localhost:8000/servicebus/metrics | grep errors_total

# Check message counts
curl http://localhost:8000/servicebus/metrics | grep active_messages

# Check latency
curl http://localhost:8000/servicebus/metrics | grep duration_seconds
```

### Monitor with Grafana

1. Import dashboard: `grafana-dashboard.json`
2. Check panels:
   - Error Rate
   - Dead-Letter Messages
   - Message Latency
   - Active Locks

## Getting Help

### Check Documentation

- [README](servicebus-README.md)
- [Filter Syntax](servicebus-filters.md)
- [Compatibility Matrix](servicebus-compatibility.md)
- [Performance Guide](servicebus-performance.md)

### Report Issues

1. **Gather information:**
   - LocalZure version
   - Python version
   - Error messages
   - Minimal reproduction code

2. **File issue:** https://github.com/yourusername/localzure/issues/new

3. **Include logs:**
   ```bash
   # Export recent logs
   tail -n 100 localzure.log > debug.log
   ```

### Community Support

- GitHub Discussions: https://github.com/yourusername/localzure/discussions
- Stack Overflow: Tag `localzure`

## Preventive Measures

### Best Practices

1. **Always complete/abandon messages**
2. **Set appropriate lock durations**
3. **Use correlation filters when possible**
4. **Monitor metrics regularly**
5. **Test filters before production**
6. **Keep messages small (< 64 KB)**
7. **Use sessions for ordered processing**
8. **Handle errors gracefully**
9. **Enable audit logging**
10. **Review dead-letter queues regularly**

### Health Checks in Production

```yaml
# Kubernetes liveness probe
livenessProbe:
  httpGet:
    path: /servicebus/health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

# Kubernetes readiness probe
readinessProbe:
  httpGet:
    path: /servicebus/health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Monitoring Alerts

```yaml
# Prometheus alerting rules
groups:
  - name: servicebus
    rules:
      - alert: HighErrorRate
        expr: rate(servicebus_errors_total[5m]) > 0.05
        annotations:
          summary: "High error rate"
          
      - alert: DeadLetterThreshold
        expr: servicebus_deadletter_messages > 10
        annotations:
          summary: "Dead-letter queue has messages"
          
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(servicebus_send_duration_seconds_bucket[5m])) > 1.0
        annotations:
          summary: "P95 latency > 1 second"
```

## Quick Reference

### Diagnostic Commands

```bash
# Health
curl http://localhost:8000/servicebus/health

# List queues
curl http://localhost:8000/servicebus/queues

# Queue properties
curl http://localhost:8000/servicebus/queues/myqueue

# Subscription rules
curl http://localhost:8000/servicebus/topics/mytopic/subscriptions/mysub/rules

# Metrics
curl http://localhost:8000/servicebus/metrics
```

### Common Fixes

| Problem | Quick Fix |
|---------|-----------|
| Queue not found | Create queue with PUT request |
| Message stuck | Call complete_message() |
| No subscription messages | Check filter, add default rule |
| High latency | Use correlation filter |
| Memory growth | Complete messages, purge DLQ |
| Lock lost | Increase lock duration or renew |
| Filter error | Check SQL syntax (single quotes, uppercase AND/OR) |
| Connection refused | Start service with `localzure start` |
| Rate limit | Increase limit or add delays |
| Invalid name | Use only valid characters, avoid reserved words |

## Related Documentation

- [Architecture Guide](servicebus-architecture.md)
- [Filter Syntax](servicebus-filters.md)
- [Performance Tuning](servicebus-performance.md)
- [Operations Runbook](servicebus-operations.md)
