# LocalZure Integration Guide

## Using LocalZure Like LocalStack

LocalZure works exactly like LocalStack but for Azure services. Here's how to use it in your development workflow.

## Installation & Setup

### Method 1: PyPI (Recommended)

```bash
pip install localzure
```

### Method 2: Docker

```bash
docker run -d -p 7071:7071 localzure/localzure:latest
```

### Method 3: From Source

```bash
git clone https://github.com/yourusername/localzure.git
cd localzure
pip install -e .
```

## Starting LocalZure

### CLI (Like LocalStack)

```bash
# Basic start
localzure start

# Development mode with auto-reload
localzure start --reload --log-level DEBUG

# Custom port
localzure start --port 8080

# Check status
localzure status

# View configuration
localzure config

# Check version
localzure version
```

### Docker

```bash
# Using docker run
docker run -d \
  --name localzure \
  -p 7071:7071 \
  localzure/localzure:latest

# Using docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Makefile Commands

```bash
make dev          # Start in development mode
make start        # Start normally
make docker-run   # Run in Docker
make test         # Run tests
make coverage     # Run tests with coverage
```

## Configuring Your Application

### Service Bus

#### Using Azure SDK (Recommended)

```python
from azure.servicebus import ServiceBusClient

# Point to LocalZure instead of Azure
connection_string = "Endpoint=sb://127.0.0.1:7071/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=dummy"

client = ServiceBusClient.from_connection_string(connection_string)

# Use normally
with client:
    sender = client.get_queue_sender(queue_name="myqueue")
    sender.send_messages(ServiceBusMessage("Hello LocalZure!"))
```

#### Using REST API

```python
import requests

base_url = "http://127.0.0.1:7071"

# Create queue
response = requests.put(f"{base_url}/myqueue")

# Send message
response = requests.post(
    f"{base_url}/myqueue/messages",
    json={"body": "Hello World", "user_properties": {"sender": "app1"}}
)

# Receive message
response = requests.post(f"{base_url}/myqueue/messages/head")
message = response.json()

# Complete message
lock_token = message["lock_token"]
requests.delete(f"{base_url}/myqueue/messages/{lock_token}")
```

### Environment Variables

Set these in your `.env` file:

```bash
# Service Bus
AZURE_SERVICEBUS_ENDPOINT=http://127.0.0.1:7071
AZURE_SERVICEBUS_CONNECTION_STRING=Endpoint=sb://127.0.0.1:7071/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=dummy

# Storage (when implemented)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:7071/devstoreaccount1
```

### Configuration File

Create `config.yaml` in your project:

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

Load config:

```bash
localzure start --config config.yaml
```

## Development Workflow

### 1. Start LocalZure

```bash
# Terminal 1: Start LocalZure
localzure start --reload

# Or with Docker
docker-compose up
```

### 2. Develop Your Application

```bash
# Terminal 2: Run your app
python your_app.py

# Or run tests
pytest tests/
```

### 3. Verify Services

```bash
# Health check
curl http://127.0.0.1:7071/health

# API documentation
open http://127.0.0.1:7071/docs
```

## Testing Integration

### pytest Example

```python
import pytest
import requests

@pytest.fixture(scope="session")
def localzure_url():
    """LocalZure endpoint"""
    return "http://127.0.0.1:7071"

@pytest.fixture(scope="session", autouse=True)
def ensure_localzure_running(localzure_url):
    """Ensure LocalZure is running before tests"""
    response = requests.get(f"{localzure_url}/health")
    assert response.status_code == 200

def test_queue_operations(localzure_url):
    queue_name = "test-queue"
    
    # Create queue
    response = requests.put(f"{localzure_url}/{queue_name}")
    assert response.status_code in [201, 200]
    
    # Send message
    response = requests.post(
        f"{localzure_url}/{queue_name}/messages",
        json={"body": "test message"}
    )
    assert response.status_code == 200
    
    # Receive message
    response = requests.post(f"{localzure_url}/{queue_name}/messages/head")
    assert response.status_code == 200
    message = response.json()
    assert message["body"] == "test message"
```

### unittest Example

```python
import unittest
import requests

class TestServiceBus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_url = "http://127.0.0.1:7071"
        
    def test_create_queue(self):
        response = requests.put(f"{self.base_url}/test-queue")
        self.assertIn(response.status_code, [200, 201])
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Test with LocalZure

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest
      
      - name: Start LocalZure
        run: |
          localzure start &
          sleep 5
          curl -f http://127.0.0.1:7071/health
      
      - name: Run tests
        run: pytest tests/
```

### Docker-based CI

```yaml
name: Test with LocalZure Docker

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      localzure:
        image: localzure/localzure:latest
        ports:
          - 7071:7071
        options: >-
          --health-cmd "curl -f http://localhost:7071/health"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Run tests
        run: pytest tests/
        env:
          SERVICEBUS_ENDPOINT: http://localhost:7071
```

### GitLab CI

```yaml
test:
  image: python:3.11
  services:
    - name: localzure/localzure:latest
      alias: localzure
  variables:
    SERVICEBUS_ENDPOINT: http://localzure:7071
  script:
    - pip install -e .
    - pytest tests/
```

## Production vs Development

### Development

```bash
# Use LocalZure
export SERVICEBUS_ENDPOINT=http://127.0.0.1:7071
python app.py
```

### Production

```bash
# Use real Azure
export SERVICEBUS_ENDPOINT=https://mynamespace.servicebus.windows.net
export SERVICEBUS_CONNECTION_STRING="Endpoint=sb://mynamespace.servicebus.windows.net/;..."
python app.py
```

### Smart Configuration

```python
import os
from azure.servicebus import ServiceBusClient

# Automatically use LocalZure in development
is_dev = os.getenv("ENVIRONMENT", "development") == "development"

if is_dev:
    connection_string = "Endpoint=sb://127.0.0.1:7071/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=dummy"
else:
    connection_string = os.getenv("AZURE_SERVICEBUS_CONNECTION_STRING")

client = ServiceBusClient.from_connection_string(connection_string)
```

## Common Use Cases

### 1. Local Development

```bash
# Start LocalZure
localzure start --reload

# Develop without Azure costs
python app.py
```

### 2. Integration Testing

```python
# tests/conftest.py
import pytest
import subprocess

@pytest.fixture(scope="session")
def localzure():
    # Start LocalZure for tests
    proc = subprocess.Popen(["localzure", "start"])
    yield "http://127.0.0.1:7071"
    proc.terminate()
```

### 3. Offline Development

```bash
# Work without internet
localzure start
# Your app runs completely offline
```

### 4. Team Collaboration

```yaml
# docker-compose.yml for team
version: '3.8'
services:
  localzure:
    image: localzure/localzure:latest
    ports:
      - "7071:7071"
  
  app:
    build: .
    environment:
      - SERVICEBUS_ENDPOINT=http://localzure:7071
    depends_on:
      - localzure
```

### 5. Demo/Prototype

```bash
# Quick demo without Azure account
docker run -d -p 7071:7071 localzure/localzure:latest
python demo.py
```

## API Compatibility

LocalZure implements Azure Service Bus REST API:

| Operation | LocalZure | Azure |
|-----------|-----------|-------|
| Create Queue | ✅ | ✅ |
| Delete Queue | ✅ | ✅ |
| List Queues | ✅ | ✅ |
| Send Message | ✅ | ✅ |
| Receive Message | ✅ | ✅ |
| Complete Message | ✅ | ✅ |
| Abandon Message | ✅ | ✅ |
| Dead Letter | ✅ | ✅ |
| Create Topic | ✅ | ✅ |
| Create Subscription | ✅ | ✅ |
| Publish Message | ✅ | ✅ |

## Troubleshooting

### Port Already in Use

```bash
# Use different port
localzure start --port 8080

# Update your app
SERVICEBUS_ENDPOINT=http://127.0.0.1:8080
```

### Connection Refused

```bash
# Check if LocalZure is running
curl http://127.0.0.1:7071/health

# Check status
localzure status

# View logs
localzure logs
```

### Test Failures

```bash
# Enable debug logging
localzure start --log-level DEBUG

# Check API docs
open http://127.0.0.1:7071/docs
```

## Migration from LocalStack

If you're familiar with LocalStack:

| LocalStack | LocalZure |
|------------|-----------|
| `localstack start` | `localzure start` |
| `localstack status` | `localzure status` |
| `localstack config` | `localzure config` |
| Port 4566 | Port 7071 |
| AWS services | Azure services |
| boto3 SDK | azure-sdk |

## Best Practices

1. **Use environment variables** for endpoint configuration
2. **Start LocalZure in CI/CD** before running tests
3. **Use Docker** for consistent team environments
4. **Enable auto-reload** during development
5. **Check health endpoint** before tests
6. **Use configuration files** for complex setups
7. **Keep LocalZure updated** with `pip install --upgrade localzure`

## Examples

See complete examples in [examples/](examples/):

- **Python Service Bus**: [examples/test_servicebus.py](examples/test_servicebus.py)
- **Docker Setup**: [examples/docker/](examples/docker/)
- **CI/CD**: [examples/ci/](examples/ci/)
- **.NET Integration**: [examples/dotnet/](examples/dotnet/)
- **Node.js Integration**: [examples/nodejs/](examples/nodejs/)

## Next Steps

1. ✅ **Start using**: `localzure start`
2. 📚 **Read docs**: Check [QUICKSTART.md](QUICKSTART.md)
3. 🐳 **Use Docker**: See [DOCKER.md](DOCKER.md)
4. 🧪 **Write tests**: Integrate with your test suite
5. 🚀 **Deploy**: Use in CI/CD pipelines
6. 🤝 **Contribute**: Help add more Azure services

## Support

- **Documentation**: [README.md](README.md)
- **Issues**: [GitHub Issues](https://github.com/yourusername/localzure/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/localzure/discussions)
