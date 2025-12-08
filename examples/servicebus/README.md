# Service Bus Examples

Complete, runnable examples demonstrating LocalZure Service Bus usage in Python, .NET, and Java.

## Prerequisites

1. **LocalZure running:**
   ```bash
   localzure start
   ```

2. **Create entities** (run once):
   ```bash
   cd examples/servicebus
   python create_entities.py
   ```

## Python Example

**Requirements:**
```bash
pip install azure-servicebus aiohttp
```

**Run:**
```bash
python python_example.py
```

**Features demonstrated:**
- Queue send/receive with peek-lock
- Complete and dead-letter operations
- Topic/subscription with SQL filters
- Session-enabled queues
- Batch operations
- Error handling and retries

## .NET C# Example

**Requirements:**
```bash
dotnet new console -n ServiceBusExample
cd ServiceBusExample
dotnet add package Azure.Messaging.ServiceBus
```

**Copy code:**
```bash
cp ../dotnet_example.cs Program.cs
```

**Run:**
```bash
dotnet run
```

## Java Example

**Requirements (Maven pom.xml):**
```xml
<dependency>
    <groupId>com.azure</groupId>
    <artifactId>azure-messaging-servicebus</artifactId>
    <version>7.13.0</version>
</dependency>
```

**Run:**
```bash
mvn compile exec:java -Dexec.mainClass="JavaExample"
```

## Example Scenarios

### 1. Queue Operations
- Send messages with properties
- Receive with automatic lock
- Complete successful messages
- Dead-letter failed messages
- Read from DLQ

### 2. Topic/Subscription
- Publish to topic
- Multiple subscriptions with filters
- SQL filter evaluation
- Fan-out pattern

### 3. Session Queues
- Session-based ordering
- Accept specific session
- Session state management
- FIFO per session

### 4. Batch Operations
- Create message batch
- Efficient bulk send
- Bulk receive
- Performance optimization

### 5. Error Handling
- Retry with abandon
- Max delivery count
- Automatic DLQ
- Graceful degradation

## Connection String

All examples use:
```
Endpoint=sb://localhost:8000/servicebus/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=fake-key
```

Change endpoint for remote LocalZure instance.

## Expected Output

Each example prints:
- Operation being performed
- Messages sent/received
- Properties and metadata
- Success/failure indicators
- Performance metrics

## Troubleshooting

**"Queue not found":**
```bash
# Create entities first
python create_entities.py
```

**"Connection refused":**
```bash
# Start LocalZure
localzure start
```

**No messages received:**
- Check filter syntax
- Verify message properties
- See [Troubleshooting Guide](../docs/servicebus-troubleshooting.md)

## Related Documentation

- [README](../docs/servicebus-README.md)
- [Filter Syntax](../docs/servicebus-filters.md)
- [Troubleshooting](../docs/servicebus-troubleshooting.md)
- [Architecture](../docs/servicebus-architecture.md)
