# LocalZure Architecture

**Version:** 0.1.0  
**Last Updated:** December 4, 2025  
**Status:** In Development

## Overview

LocalZure is a local Azure cloud platform emulator that enables developers to test Azure services offline. The architecture is modular and layered, providing isolation between concerns and supporting extensibility through a plugin-based service system.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Applications                      │
│              (Azure SDKs, REST Clients, CLI)                │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                       │
│        (FastAPI, Request Routing, Auth, CORS)               │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Service Emulator Layer                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │  Blob    │ │  Queue   │ │  Table   │ │ Service  │ ...  │
│  │ Storage  │ │ Storage  │ │ Storage  │ │   Bus    │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Runtime Layer                        │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐             │
│  │   Config   │ │  Logging   │ │  Service   │             │
│  │  Manager   │ │   System   │ │  Manager   │             │
│  └────────────┘ └────────────┘ └────────────┘             │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    State Backend Layer                       │
│        (File System, In-Memory, SQLite, Redis)              │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Core Runtime Layer ✅ IMPLEMENTED

**Purpose:** Provides foundational infrastructure for system initialization, configuration, and lifecycle management.

#### 1.1 Configuration Manager (`localzure/core/config_manager.py`)

**Responsibilities:**
- Load configuration from multiple sources (files, environment variables, CLI arguments)
- Validate configuration using Pydantic models
- Provide configuration access to all subsystems
- Support hot-reloading of configuration

**Key Features:**
- Multi-source loading with precedence: CLI > ENV > File > Defaults
- Supports YAML and JSON formats
- Pydantic-based schema validation
- Sensitive data redaction in logs

**Configuration Schema:**
```python
LocalZureConfig:
  - version: str (semver format)
  - host: str (default: "127.0.0.1")
  - port: int (default: 8080)
  - log_level: str (default: "INFO")
  - log_format: str (default: "json")
  - services: dict[str, ServiceConfig]
  - state_backend: StateBackendConfig
```

**Usage:**
```python
config_manager = ConfigManager(config_path="config.yaml")
config_manager.load()
config = config_manager.get_config()
```

#### 1.2 Logging Infrastructure (`localzure/core/logging_config.py`)

**Responsibilities:**
- Provide structured logging across all components
- Filter sensitive data from logs
- Support multiple output formats (JSON, text)
- Enable correlation ID tracking for distributed tracing

**Key Features:**
- JSON-formatted structured logs
- Sensitive data redaction (passwords, keys, tokens, SAS URLs)
- File rotation support with configurable size limits
- Correlation ID propagation via context vars

**Log Format:**
```json
{
  "timestamp": "2025-12-04T10:30:45.123Z",
  "level": "INFO",
  "logger": "localzure.core.runtime",
  "message": "Runtime initialized successfully",
  "correlation_id": "abc123",
  "extras": {...}
}
```

**Redaction Patterns:**
- Authorization headers (including Bearer tokens)
- Password fields
- API keys and secrets
- SAS tokens and signatures
- Connection strings

#### 1.3 Runtime Manager (`localzure/core/runtime.py`)

**Responsibilities:**
- Orchestrate system startup and shutdown
- Manage service lifecycle
- Expose health check endpoints
- Handle graceful degradation

**Key Features:**
- Idempotent initialization
- Async lifecycle management
- FastAPI integration for health endpoints
- Uptime tracking

**Lifecycle States:**
- `UNINITIALIZED` → `INITIALIZED` → `RUNNING` → `STOPPED`

**Health Endpoint:** `GET /health`
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {},
  "uptime": 12345,
  "timestamp": "2025-12-04T10:30:45.123Z"
}
```

### 2. API Gateway Layer (PENDING)

**Purpose:** Route incoming requests to appropriate service emulators, handle authentication, and enforce rate limits.

**Planned Components:**
- Request router
- Authentication/authorization middleware
- CORS handling
- Rate limiting
- Request/response logging

### 3. Service Emulator Layer (PENDING)

**Purpose:** Implement Azure service-specific logic and API compatibility.

**Planned Services:**
- Blob Storage (Azure Storage Blobs)
- Queue Storage (Azure Storage Queues)
- Table Storage (Azure Storage Tables)
- Service Bus (Topics & Queues)
- Key Vault (Secrets, Keys, Certificates)
- Cosmos DB (NoSQL database)
- Functions (Serverless compute)

### 4. State Backend Layer (PENDING)

**Purpose:** Persist service data and state across restarts.

**Planned Backends:**
- File System (default, for development)
- In-Memory (fast, non-persistent)
- SQLite (embedded, persistent)
- Redis (distributed, high-performance)

## Design Principles

### 1. Modularity
- Each service emulator is independently loadable
- Core runtime has no knowledge of specific services
- Plugin-based architecture for extensibility

### 2. Azure API Compatibility
- Maintain API compatibility with Azure SDKs
- Support standard authentication mechanisms
- Return Azure-compatible error responses

### 3. Developer Experience
- Simple configuration with sensible defaults
- Clear error messages with actionable feedback
- Comprehensive logging for troubleshooting
- Hot-reload support for rapid iteration

### 4. Performance
- Async/await for I/O operations
- Connection pooling for state backends
- Lazy loading of service emulators
- Efficient memory management

### 5. Testing
- Unit tests for all core components (target: >90% coverage)
- Integration tests for service interactions
- Contract tests for Azure API compatibility
- Performance benchmarks for critical paths

## Configuration Management

### Configuration Sources (in precedence order)

1. **CLI Arguments** (highest priority)
   ```bash
   localzure --port 8080 --log-level DEBUG
   ```

2. **Environment Variables**
   ```bash
   LOCALZURE_PORT=8080
   LOCALZURE_LOG_LEVEL=DEBUG
   ```

3. **Configuration File** (YAML/JSON)
   ```yaml
   version: "0.1.0"
   host: "127.0.0.1"
   port: 8080
   log_level: "INFO"
   ```

4. **Defaults** (lowest priority)

### Configuration Validation

- All configuration validated using Pydantic models
- Type checking and constraint validation
- Clear error messages for invalid values
- Fail-fast on startup if configuration is invalid

## Logging Strategy

### Log Levels
- **DEBUG:** Detailed diagnostic information
- **INFO:** General informational messages
- **WARNING:** Warning messages for non-critical issues
- **ERROR:** Error messages for recoverable failures
- **CRITICAL:** Critical failures requiring immediate attention

### Sensitive Data Protection
All logs automatically redact:
- Authorization headers
- Passwords and secrets
- API keys
- SAS tokens
- Connection strings

### Correlation IDs
- Each request receives a unique correlation ID
- IDs propagate through all log messages
- Enables distributed tracing and debugging

## Security Considerations

### Current Implementation
- ✅ Sensitive data redaction in logs
- ✅ Configuration validation prevents injection
- ✅ No hardcoded credentials

### Planned Features
- Authentication middleware
- Authorization per service
- TLS/SSL support for production use
- Audit logging for security events
- Secrets management integration

## Performance Characteristics

### Current Benchmarks
- Runtime initialization: <100ms
- Configuration loading: <50ms
- Health check response: <10ms

### Targets
- Request latency: <100ms (p95)
- Throughput: >1000 req/s
- Memory usage: <500MB (with 5 services)
- Startup time: <5s (full system)

## Testing Strategy

### Unit Tests ✅
- **59 tests** covering core runtime components
- **93% code coverage** achieved
- Fast execution (<5s full suite)
- Isolated test fixtures

### Integration Tests (PLANNED)
- Service-to-service communication
- End-to-end request flows
- State backend persistence
- Error handling and recovery

### Contract Tests (PLANNED)
- Azure SDK compatibility
- API response format validation
- Error response matching

## Deployment Model

### Standalone Mode (Primary)
```bash
localzure start --config config.yaml
```

### Docker Container (PLANNED)
```bash
docker run -p 8080:8080 localzure/localzure
```

### Desktop Application (PLANNED)
- Native GUI for Windows/Mac/Linux
- Visual service management
- Built-in configuration editor

## Extension Points

### Service Plugins
Services can be added by implementing the `ServiceEmulator` interface:
```python
class ServiceEmulator(ABC):
    @abstractmethod
    async def initialize(self, config: dict) -> None: ...
    
    @abstractmethod
    async def start(self) -> None: ...
    
    @abstractmethod
    async def stop(self) -> None: ...
    
    @abstractmethod
    def get_routes(self) -> list[APIRoute]: ...
```

### State Backends
Custom backends can be added by implementing the `StateBackend` interface (PLANNED).

### Middleware
Custom middleware can be registered for request/response processing (PLANNED).

## Future Enhancements

### Short Term (Next 3 stories)
- Service Manager with plugin loading
- Centralized logging aggregation
- Docker integration

### Medium Term (Next quarter)
- Blob Storage emulator
- Queue Storage emulator
- Table Storage emulator

### Long Term (6+ months)
- Full Azure SDK compatibility
- Production-ready state backends
- Desktop application
- Cloud-based testing integration

## References

- [PRD.md](../PRD.md) - Product Requirements Document
- [STORY-CORE-001.md](../user-stories/EPIC-01-CORE-Runtime/STORY-CORE-001.md) - Core Runtime Implementation
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Azure REST API Reference](https://learn.microsoft.com/en-us/rest/api/azure/)

---

**Document Ownership:** LocalZure Development Team  
**Review Frequency:** Updated after each major feature implementation  
**Next Review:** After STORY-CORE-002 (Service Manager) completion
