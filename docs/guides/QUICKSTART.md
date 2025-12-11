# LocalZure Quick Start Guide

## Installation

Install LocalZure in development mode:

```bash
cd localzure
pip install -e .
```

## Starting LocalZure

Start the local Azure emulator:

```bash
localzure start
```

The server will start on `http://127.0.0.1:7071` by default.

### Custom Port and Options

```bash
# Start on a different port
localzure start --port 8080

# Enable debug logging
localzure start --log-level DEBUG

# Enable auto-reload for development
localzure start --reload
```

## Testing Service Bus

Once LocalZure is running, you can interact with the Service Bus emulator:

### Using Python Azure SDK

```python
from azure.servicebus import ServiceBusClient

# Point to LocalZure endpoint
connection_string = "Endpoint=sb://127.0.0.1:7071/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=dummy"

# Or use environment variable
import os
os.environ["SERVICEBUS_CONNECTION_STRING"] = connection_string

# Create client
client = ServiceBusClient.from_connection_string(connection_string)

# Create queue (via REST API)
import requests
queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""

response = requests.put(
    "http://127.0.0.1:7071/servicebus/test-ns/myqueue",
    data=queue_xml,
    headers={"Content-Type": "application/xml"}
)
print(f"Queue created: {response.status_code}")

# Send message
response = requests.post(
    "http://127.0.0.1:7071/servicebus/test-ns/myqueue/messages",
    json={
        "body": "Hello from LocalZure!",
        "properties": {"priority": "high"}
    }
)
print(f"Message sent: {response.status_code}")

# Receive message
response = requests.post(
    "http://127.0.0.1:7071/servicebus/test-ns/myqueue/messages/head?timeout=5"
)
if response.status_code == 200:
    message = response.json()
    print(f"Received message: {message}")
```

### Using cURL

```bash
# Create a queue
curl -X PUT http://127.0.0.1:7071/servicebus/test-ns/myqueue \
  -H "Content-Type: application/xml" \
  -d '<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>'

# Send a message
curl -X POST http://127.0.0.1:7071/servicebus/test-ns/myqueue/messages \
  -H "Content-Type: application/json" \
  -d '{"body": "Hello LocalZure!", "properties": {"sender": "demo"}}'

# Receive a message
curl -X POST "http://127.0.0.1:7071/servicebus/test-ns/myqueue/messages/head?timeout=5"

# List queues
curl http://127.0.0.1:7071/servicebus/test-ns/queues
```

## API Documentation

Once running, visit:

- **Interactive API Docs**: http://127.0.0.1:7071/docs
- **ReDoc**: http://127.0.0.1:7071/redoc
- **Health Check**: http://127.0.0.1:7071/health

## Available Commands

```bash
# Show status
localzure status

# Show configuration
localzure config

# Show version
localzure version

# Stop services (not yet implemented)
localzure stop

# View logs (not yet implemented)
localzure logs
```

## What's Supported

### Service Bus ✅
- Queues (create, delete, list, get)
- Topics & Subscriptions
- Send & Receive messages
- Message operations (complete, abandon, dead-letter)
- Lock management
- Error handling with proper HTTP status codes
- Correlation ID propagation

### Coming Soon 🚧
- Blob Storage
- Queue Storage  
- Table Storage
- Key Vault
- Event Grid
- Cosmos DB

## Development Mode

For development with auto-reload:

```bash
localzure start --reload --log-level DEBUG
```

This will automatically restart the server when you make code changes.

## Environment Variables

```bash
# Set LocalZure endpoint for Azure SDKs
export AZURE_SERVICEBUS_ENDPOINT=http://127.0.0.1:7071
export SERVICEBUS_CONNECTION_STRING="Endpoint=sb://127.0.0.1:7071/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=dummy"
```

## Next Steps

1. Start LocalZure: `localzure start`
2. Visit API docs: http://127.0.0.1:7071/docs
3. Try the examples above
4. Integrate with your application by pointing Azure SDKs to LocalZure

## Troubleshooting

### Port already in use

If port 7071 is in use, specify a different port:

```bash
localzure start --port 8080
```

### Import errors

Make sure LocalZure is installed in editable mode:

```bash
pip install -e .
```

### Enable debug logging

```bash
localzure start --log-level DEBUG
```

This will show detailed request/response information and help diagnose issues.
