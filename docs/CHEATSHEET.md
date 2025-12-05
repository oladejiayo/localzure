# LocalZure Quick Reference Card

## 🚀 Installation

```bash
# Install from source
pip install -e .

# Verify
localzure version
```

## 🎮 Commands

```bash
# Start LocalZure
localzure start

# Development mode
localzure start --reload --log-level DEBUG

# Custom port
localzure start --port 8080

# Check status
localzure status

# View config
localzure config

# Show version
localzure version
```

## 🐳 Docker

```bash
# Build
docker build -t localzure/localzure:latest .

# Run
docker run -d -p 7071:7071 localzure/localzure:latest

# Compose
docker-compose up -d

# Logs
docker-compose logs -f

# Stop
docker-compose down
```

## 📡 Endpoints

```
Health:    GET  http://localhost:7071/health
API Docs:       http://localhost:7071/docs
OpenAPI:        http://localhost:7071/openapi.json
```

## 🔧 Service Bus API

```bash
# Create queue
PUT http://localhost:7071/{queue}

# Send message
POST http://localhost:7071/{queue}/messages
Body: {"body": "Hello", "user_properties": {...}}

# Receive message
POST http://localhost:7071/{queue}/messages/head

# Complete message
DELETE http://localhost:7071/{queue}/messages/{lock_token}

# List queues
GET http://localhost:7071/$Resources/Queues

# Create topic
PUT http://localhost:7071/{topic}

# Create subscription
PUT http://localhost:7071/{topic}/subscriptions/{sub}

# Publish
POST http://localhost:7071/{topic}/messages
```

## 💻 Code Examples

### Python

```python
from azure.servicebus import ServiceBusClient, ServiceBusMessage

connection_string = "Endpoint=sb://127.0.0.1:7071/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=dummy"
client = ServiceBusClient.from_connection_string(connection_string)

with client:
    sender = client.get_queue_sender("myqueue")
    sender.send_messages(ServiceBusMessage("Hello!"))
```

### REST

```python
import requests

url = "http://127.0.0.1:7071"
requests.put(f"{url}/myqueue")
requests.post(f"{url}/myqueue/messages", json={"body": "Hello"})
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=localzure

# Specific test
pytest tests/unit/test_servicebus_api.py

# Demo app
python examples/test_servicebus.py
```

## ⚙️ Configuration

### Environment Variables

```bash
LOCALZURE_HOST=127.0.0.1
LOCALZURE_PORT=7071
LOCALZURE_LOG_LEVEL=INFO
```

### config.yaml

```yaml
server:
  host: "127.0.0.1"
  port: 7071
  log_level: "INFO"

servicebus:
  enabled: true
  default_message_ttl: 1209600
  max_delivery_count: 10
```

## 🔍 Troubleshooting

### Port in use
```bash
localzure start --port 8080
```

### Check if running
```bash
curl http://127.0.0.1:7071/health
```

### View debug logs
```bash
localzure start --log-level DEBUG
```

### Reset state
```bash
# Stop and restart
# (In-memory backend clears on restart)
```

## 📚 Documentation

- **README.md** - Main overview
- **QUICKSTART.md** - Getting started
- **INTEGRATION.md** - Usage guide
- **DOCKER.md** - Container guide
- **CONTRIBUTING.md** - Development guide
- **COMPLETE.md** - Full feature list

## 🆘 Support

- GitHub Issues: Report bugs
- GitHub Discussions: Ask questions
- API Docs: http://localhost:7071/docs

---

**Quick Test:**
```bash
localzure start &
sleep 3
curl http://127.0.0.1:7071/health
python examples/test_servicebus.py
```
