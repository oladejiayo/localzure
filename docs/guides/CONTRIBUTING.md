# Contributing to LocalZure

Thank you for your interest in contributing to LocalZure! This document provides guidelines for contributing.

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## Getting Started

1. **Fork the repository**
   ```bash
   git clone https://github.com/yourusername/localzure.git
   cd localzure
   ```

2. **Set up development environment**
   ```bash
   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   
   # Install in development mode
   pip install -e ".[dev]"
   ```

3. **Run tests**
   ```bash
   pytest tests/
   ```

## Development Workflow

### 1. Create a branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make changes

- Write clear, documented code
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation

### 3. Run tests and linting

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=localzure --cov-report=html

# Format code
black localzure/ tests/

# Lint code
ruff check localzure/

# Type check
mypy localzure/
```

### 4. Commit changes

```bash
git add .
git commit -m "feat: add new feature"
```

Use conventional commit format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance

### 5. Push and create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Adding New Azure Services

To add a new Azure service emulator:

### 1. Create service module

```
localzure/services/your_service/
├── __init__.py
├── api.py        # FastAPI endpoints
├── models.py     # Pydantic models
├── storage.py    # In-memory backend
└── exceptions.py # Service-specific errors
```

### 2. Implement REST API

```python
# api.py
from fastapi import APIRouter, Request

router = APIRouter(prefix="/your-service")

@router.get("/resource")
async def get_resource():
    return {"status": "ok"}
```

### 3. Add to main app

```python
# localzure/cli.py
from localzure.services.your_service.api import router as your_service_router

app.include_router(your_service_router)
```

### 4. Write tests

```python
# tests/unit/test_your_service.py
def test_resource_creation():
    # Test your service
    pass

# tests/integration/test_your_service_integration.py
def test_end_to_end():
    # Integration test
    pass
```

### 5. Update documentation

- Add to README.md
- Create service-specific guide
- Update STATUS.md

## Testing Guidelines

### Unit Tests

```python
# tests/unit/test_models.py
from localzure.services.servicebus.models import ServiceBusMessage

def test_message_creation():
    msg = ServiceBusMessage(body="test")
    assert msg.body == "test"
    assert msg.message_id is not None
```

### Integration Tests

```python
# tests/integration/test_api.py
import requests

def test_queue_operations(base_url):
    # Create queue
    response = requests.put(f"{base_url}/myqueue")
    assert response.status_code in [200, 201]
    
    # Use queue
    # ...
```

### Test Fixtures

```python
# tests/conftest.py
import pytest

@pytest.fixture
def base_url():
    return "http://127.0.0.1:7071"

@pytest.fixture
def reset_backend():
    # Reset state before each test
    pass
```

## Documentation

### Code Documentation

```python
def send_message(queue_name: str, message: ServiceBusMessage) -> dict:
    """
    Send a message to a queue.
    
    Args:
        queue_name: Name of the queue
        message: Message to send
    
    Returns:
        Dictionary with message details
    
    Raises:
        EntityNotFoundException: Queue not found
    """
    pass
```

### API Documentation

Use FastAPI's automatic documentation:

```python
@router.post(
    "/messages",
    summary="Send message",
    description="Send a message to the queue",
    response_model=MessageResponse
)
async def send_message(message: MessageRequest):
    pass
```

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create git tag
4. Push to GitHub
5. GitHub Actions builds and publishes

## Areas We Need Help

### High Priority

- [ ] Blob Storage implementation
- [ ] Queue Storage implementation
- [ ] Key Vault implementation
- [ ] Persistent storage backend
- [ ] Docker multi-arch builds

### Medium Priority

- [ ] Table Storage implementation
- [ ] Event Grid implementation
- [ ] Azure Functions support
- [ ] Cosmos DB emulator
- [ ] Kubernetes deployment

### Low Priority

- [ ] Web dashboard UI
- [ ] Performance benchmarks
- [ ] Load testing
- [ ] Additional SDKs examples
- [ ] Video tutorials

## Questions?

- Open an issue for bugs
- Start a discussion for questions
- Join our Discord (coming soon)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Every contribution helps make LocalZure better for the Azure development community. Thank you for your support! 🙏
