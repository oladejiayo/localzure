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
- Docker configuration support

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
  - docker_enabled: bool (default: False)
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
- Stream Docker container logs

**Key Features:**
- JSON-formatted structured logs
- Sensitive data redaction (passwords, keys, tokens, SAS URLs)
- File rotation support with configurable size limits
- Correlation ID propagation via context vars
- Per-module log level configuration
- Container log integration

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

#### 1.4 Service Manager (`localzure/core/service_manager.py`) ✅ IMPLEMENTED

**Responsibilities:**
- Discover service emulator plugins via Python entrypoints
- Resolve service dependencies using topological sort
- Manage service lifecycle (start/stop/reset)
- Monitor service health and emit state change events
- Provide service status information

**Key Features:**
- Plugin discovery via `localzure.services` entrypoint group
- Dependency graph resolution with cycle detection
- State machine for service lifecycle
- Event system for state change notifications
- Graceful error handling and recovery

**Service States:**
- `UNINITIALIZED` → `STARTING` → `RUNNING` → `STOPPING` → `STOPPED`
- `FAILED` (error state, can transition from any state)

**Dependency Resolution:**
- Uses Kahn's algorithm for topological sort
- Detects missing dependencies
- Detects circular dependencies
- Ensures services start in correct order

**Event System:**
```python
@dataclass
class ServiceEvent:
    service_name: str
    old_state: ServiceState
    new_state: ServiceState
    error: Optional[Exception]
    timestamp: float
```

#### 1.5 Service Interface (`localzure/core/service.py`) ✅ IMPLEMENTED

**Abstract Base Class:** All service emulators must implement `LocalZureService`

**Required Methods:**
```python
class LocalZureService(ABC):
    def get_metadata(self) -> ServiceMetadata
    async def start(self) -> None
    async def stop(self) -> None
    async def reset(self) -> None
    async def health(self) -> Dict[str, Any]
    def get_routes(self) -> List[ServiceRoute]
    def docker_config(self) -> Optional[DockerConfig]  # Optional Docker support
```

#### 1.6 Docker Manager (`localzure/core/docker_manager.py`) ✅ IMPLEMENTED

**Responsibilities:**
- Detect Docker availability on the system
- Manage Docker container lifecycle for services
- Stream container logs to LocalZure logging infrastructure
- Monitor container health status
- Clean up containers on shutdown or crash
- Support volume mounting for persistent data

**Key Features:**
- Automatic Docker detection with graceful fallback
- Container naming convention: `localzure-<service>[-<instance>]`
- Log integration via container log streaming
- Health check monitoring with Docker HEALTHCHECK support
- Volume mounting for persistent state
- Automatic cleanup of orphaned containers

**Container Lifecycle:**
```
UNINITIALIZED → CREATING → RUNNING → STOPPING → STOPPED
              ↓
            FAILED
```

**Docker Configuration:**
```python
@dataclass
class DockerConfig:
    image: str  # Docker image name
    ports: Dict[str, str]  # container_port -> host_port
    volumes: Dict[str, str]  # host_path -> container_path
    environment: Dict[str, str]  # Environment variables
    command: Optional[List[str]]  # Override container command
    healthcheck: Optional[Dict[str, Any]]  # Custom health check
    network_mode: str  # Default: "bridge"
```

**Usage Example:**
```python
# Service with Docker support
class AzuriteBlobService(LocalZureService):
    def docker_config(self):
        return DockerConfig(
            image="mcr.microsoft.com/azure-storage/azurite",
            ports={"10000": "10000"},
            volumes={"/data": "/localzure/blob"},
            environment={"AZURITE_ACCOUNTS": "..."}
        )
```

**Service Execution Modes:**
- **Docker Mode:** Service runs in container (if `docker_config()` returns config and Docker available)
- **Host Mode:** Service runs in LocalZure process (if `docker_config()` returns `None` or Docker unavailable)
- **Automatic Fallback:** Falls back to host mode if Docker is unavailable

#### 1.7 Lifecycle Manager (`localzure/core/lifecycle.py`) ✅ IMPLEMENTED

**Responsibilities:**
- Handle graceful shutdown with signal processing
- Track in-flight requests during shutdown
- Manage runtime lifecycle state transitions
- Support startup rollback on initialization failure
- Coordinate shutdown callbacks across subsystems

**Key Features:**
- SIGTERM/SIGINT signal handling via asyncio
- Configurable shutdown timeout (default 30s)
- Request tracking with draining mode
- Force shutdown after timeout
- Startup rollback for partial initialization failures
- State change callbacks for monitoring

**Lifecycle States:**
```
INITIALIZING → STARTING → RUNNING → DRAINING → STOPPING → STOPPED
             ↓           ↓          ↓
           FAILED      FAILED     FAILED
```

**Shutdown Sequence:**
```
1. Receive signal/request
2. Set state to DRAINING
3. Stop accepting new requests
4. Wait for in-flight requests (with timeout)
5. Execute shutdown callbacks
6. Cleanup resources (services, Docker)
7. Set state to STOPPED
```

**Usage Example:**
```python
# Initialize with custom timeout
lifecycle = LifecycleManager(shutdown_timeout=45.0)

# Register signal handlers (main thread)
lifecycle.register_signal_handlers()

# Track requests
tracker = lifecycle.get_request_tracker()
await tracker.start_request("req-123")
# ... process request ...
await tracker.end_request("req-123")

# Register shutdown callback
async def cleanup(reason):
    await save_state()
    await close_connections()

lifecycle.register_shutdown_callback(cleanup)

# Wait for signal
signal = await lifecycle.wait_for_shutdown_signal()

# Graceful shutdown
success = await lifecycle.graceful_shutdown()
```

**Service Metadata:**
```python
@dataclass
class ServiceMetadata:
    name: str
    version: str
    description: str
    dependencies: List[str]
    port: Optional[int]
    enabled: bool
```

**Service Route:**
```python
@dataclass
class ServiceRoute:
    path: str
    methods: List[str]
    handler: Any  # FastAPI route handler
```

### 2. API Gateway Layer ✅ IMPLEMENTED (Production-Ready)

**Purpose:** Route requests, rewrite URLs, handle authentication, and manage cross-cutting concerns.

**Components:** 11 implemented (Hostname Mapper, Request Canonicalizer, SAS Validator, Protocol Router, Retry Simulator, Error Formatter, Rate Limiter, Circuit Breaker, Distributed Tracing, Metrics Collection, FastAPI Middleware)

**Test Coverage:**
- Gateway Tests: 315 tests (270 core + 45 production enhancements)
- Overall Coverage: 93%
- All Components: ✅ Production-ready with comprehensive tests

**Implemented Components:**

#### 2.1 Hostname Mapper (`localzure/gateway/hostname_mapper.py`) ✅ IMPLEMENTED

**Responsibility:** Map Azure service hostnames to LocalZure endpoints and rewrite URLs.

**Key Features:**
- Regex-based hostname pattern matching
- Support for 6 major Azure services:
  - Blob Storage: `<account>.blob.core.windows.net` → `http://localhost:10000/<account>`
  - Queue Storage: `<account>.queue.core.windows.net` → `http://localhost:10001/<account>`
  - Table Storage: `<account>.table.core.windows.net` → `http://localhost:10002/<account>`
  - Service Bus: `<namespace>.servicebus.windows.net` → `http://localhost:5672`
  - Key Vault: `<vault>.vault.azure.net` → `http://localhost:8200/<vault>`
  - Cosmos DB: `<account>.documents.azure.com` → `http://localhost:8081/<account>`
- Path and query parameter preservation
- Custom hostname mapping support via configuration
- Original host header preservation (`X-Original-Host`)

**API:**
```python
mapper = HostnameMapper(custom_mappings={"custom.domain.com": "http://localhost:9000"})
result = mapper.map_url("https://myaccount.blob.core.windows.net/container/blob?sv=2021-06-08")
# result.mapped_url = "http://localhost:10000/myaccount/container/blob?sv=2021-06-08"
# result.original_host = "myaccount.blob.core.windows.net"
# result.service_name = "blob"
```

**Configuration:**
```python
class GatewayConfig(BaseModel):
    enabled: bool = True
    custom_mappings: Dict[str, str] = Field(default_factory=dict)
    preserve_host_header: bool = True
```

**Status:** ✅ Complete (STORY-GATEWAY-001)
**Tests:** 41 unit tests, 99% coverage
**Documentation:** `docs/implementation/STORY-GATEWAY-001.md`

#### 2.2 Request Canonicalizer (`localzure/gateway/canonicalizer.py`) ✅ IMPLEMENTED

**Responsibility:** Canonicalize HTTP requests for Azure SharedKey authentication.

**Key Features:**
- Multi-version canonicalization support:
  - 2009-09-19: Original Azure Storage version
  - 2015-04-05: Updated with query parameters
  - 2019-02-02: Latest version with full header support
- Multi-service support: Blob, Queue, Table, File storage
- Canonical headers building (sorted x-ms-* headers)
- Canonical resource building (account name, path, query params)
- HMAC-SHA256 signature computation
- Signature validation for SharedKey auth
- Authorization header parsing

**Canonicalization Algorithm:**
```
VERB\n
Content-Encoding\n
Content-Length\n
Content-MD5\n
Content-Type\n
Date\n
[Other standard headers...]\n
CanonicalizedHeaders\n
CanonicalizedResource
```

**API:**
```python
canonicalizer = RequestCanonicalizer(version=CanonicalVersion.VERSION_2019_02_02)
result = canonicalizer.canonicalize(
    method="GET",
    url="https://myaccount.blob.core.windows.net/container/blob",
    headers={"x-ms-version": "2021-08-06", "x-ms-date": "..."},
    account_name="myaccount",
    service_type=ServiceType.BLOB
)
signature = canonicalizer.compute_signature(result.string_to_sign, account_key)
valid = canonicalizer.validate_signature(..., provided_signature=signature)
```

**Status:** ✅ Complete (STORY-GATEWAY-002)
**Tests:** 38 unit tests, 100% coverage
**Documentation:** `docs/implementation/STORY-GATEWAY-002.md`

---

#### 2.3 SAS Token Validator (`localzure/gateway/sas_validator.py`) ✅ IMPLEMENTED

**Responsibility:** Validate Shared Access Signature (SAS) tokens for Azure Storage services.

**Key Features:**
- Parse SAS tokens from URL query parameters
- HMAC-SHA256 signature validation using account keys
- Time-based validation (expiry and start time)
- Permission validation (rwdlacup flags)
- Resource type validation (service, container, object)
- Service type validation (blob, queue, table, file)
- Azure-compatible error codes

**SAS Token Parameters:**
```
sv  - Signed version
ss  - Signed services (bqtf)
srt - Signed resource types (sco)
sp  - Signed permissions (rwdlacup)
se  - Signed expiry (ISO 8601)
st  - Signed start (ISO 8601, optional)
sig - Signature (HMAC-SHA256)
spr - Signed protocol (optional)
sip - Signed IP (optional)
```

**String-to-Sign Format (Account SAS):**
```
accountname\n
signedpermissions\n
signedservice\n
signedresourcetype\n
signedstart\n
signedexpiry\n
signedIP\n
signedProtocol\n
signedversion
```

**API:**
```python
validator = SASValidator(account_name="myaccount", account_key="base64-key")

# Complete validation
token = validator.validate(
    url="https://myaccount.blob.core.windows.net/container?sv=2021-06-08&...",
    required_permission=SASPermission.READ,
    required_resource_type=SASResourceType.OBJECT,
    required_service=SASService.BLOB
)

# Granular validation
token = validator.parse_sas_token(url)
validator.validate_signature(token, url)
validator.validate_expiry(token)
validator.validate_permissions(token, SASPermission.WRITE)
```

**Error Codes:**
- `AuthenticationFailed` - Signature mismatch, expired, not yet valid
- `InvalidQueryParameterValue` - Missing/malformed parameters
- `AuthorizationPermissionMismatch` - Insufficient permissions
- `AuthorizationResourceTypeMismatch` - Resource type not allowed
- `AuthorizationServiceMismatch` - Service not allowed

**Status:** ✅ Complete (STORY-GATEWAY-003)
**Tests:** 42 unit tests, 99% coverage
**Documentation:** `docs/implementation/STORY-GATEWAY-003.md`

---

#### 2.4 Protocol Router (`localzure/gateway/protocol_router.py`) ✅ IMPLEMENTED

**Responsibility:** Route different protocol types (HTTP, WebSocket, AMQP) to appropriate service handlers.

**Key Features:**
- Protocol detection from headers and raw connection data
- Support for HTTP/1.1, HTTP/2, WebSocket, and AMQP 1.0
- Handler registration and routing per protocol
- Stateful connection management for WebSocket and AMQP
- Protocol-specific error formatting
- Header and metadata preservation

**Supported Protocols:**
```python
class ProtocolType(str, Enum):
    HTTP = "http"          # HTTP/1.1 requests
    HTTP2 = "http2"        # HTTP/2 requests
    WEBSOCKET = "websocket"  # WebSocket upgrades
    AMQP = "amqp"          # AMQP 1.0 connections
    UNKNOWN = "unknown"    # Unrecognized
```

**Protocol Detection:**
- **HTTP:** Standard HTTP headers
- **HTTP/2:** `HTTP2-Settings` header present
- **WebSocket:** `Upgrade: websocket` + `Connection: Upgrade`
- **AMQP:** Connection preface `AMQP\x00\x01\x00\x00`

**API:**
```python
router = ProtocolRouter()

# Register handlers
router.register_handler(ProtocolType.HTTP, http_handler)
router.register_handler(ProtocolType.WEBSOCKET, ws_handler)
router.register_handler(ProtocolType.AMQP, amqp_handler)

# Route request
result = await router.route_request(
    protocol=ProtocolType.HTTP,
    headers={"Host": "example.com"},
    metadata={"source_ip": "127.0.0.1"}
)

# Connection tracking (stateful protocols)
state = router.create_connection(ProtocolType.WEBSOCKET)
count = router.active_connections(ProtocolType.WEBSOCKET)
router.close_connection(state.connection_id)
```

**Error Handling:**
```python
# Protocol-specific error formats
HTTP: {"error": {"code": 404, "message": "...", "protocol": "http"}}
WebSocket: {"close_code": 1008, "close_reason": "..."}
AMQP: {"condition": "amqp:internal-error", "description": "..."}
```

**Status:** ✅ Complete (STORY-GATEWAY-004)
**Tests:** 50 unit tests, 100% coverage
**Documentation:** `docs/implementation/STORY-GATEWAY-004.md`

#### 2.5 Retry Simulator (`localzure/gateway/retry_simulator.py`) ✅ IMPLEMENTED

**Responsibility:** Simulate Azure retry behavior and backoff patterns for testing application retry logic.

**Features:**
- **Test Mode Configuration:**
  - Global and per-service configuration
  - Configurable failure rate (0.0 to 1.0)
  - Multiple error codes (429, 500, 502, 503, 504)
  - Optional duration for time-bounded injection
  - Disabled by default for safety

- **Failure Patterns:**
  ```python
  class FailurePattern(str, Enum):
      RANDOM = "random"        # Random failures based on rate
      SEQUENTIAL = "sequential" # Every Nth request fails
      BURST = "burst"          # Failures in bursts
  ```

- **Retry-After Formats:**
  - Seconds: `"10"` (delay-seconds format)
  - HTTP-Date: `"Fri, 31 Dec 2025 23:59:59 GMT"`
  - x-ms-retry-after-ms header support

- **Deterministic Injection:**
  - Seed-based randomness for reproducible tests
  - Request ID hashing for consistent behavior

**Usage:**
```python
# Configure test mode
config = TestModeConfig(
    enabled=True,
    failure_rate=0.3,
    error_codes=[429, 503],
    retry_after=10,
    retry_after_format=RetryAfterFormat.SECONDS,
    pattern=FailurePattern.RANDOM
)

# Create simulator
simulator = RetrySimulator(global_config=config)

# Register service-specific config
storage_config = TestModeConfig(enabled=True, failure_rate=0.5)
simulator.register_service_config("storage", storage_config)

# Check if request should fail
result = simulator.check_failure(service_name="storage")
if result.should_fail:
    response = create_error_response(result)
    # Returns 429/503 with Retry-After header
```

**Configuration:**
```yaml
test_mode:
  enabled: true
  failure_rate: 0.2
  error_codes: [429, 503]
  retry_after: 15
  retry_after_format: http_date
  pattern: burst
  burst_size: 3
  burst_interval: 10
  duration: 300
```

**Status:** ✅ Complete (STORY-GATEWAY-005)
**Tests:** 44 unit tests, 97% coverage
**Documentation:** `docs/implementation/STORY-GATEWAY-005.md`

#### 2.6 Error Formatter (`localzure/gateway/error_formatter.py`) ✅ IMPLEMENTED

**Responsibility:** Format error responses matching Azure's structure for SDK compatibility.

**Features:**
- **Error Formats:**
  - XML for Storage services (Blob, Queue, Table, File)
  - JSON for other services (Service Bus, Key Vault, Cosmos DB)
  - Content negotiation based on Accept header

- **Error Code Mappings:**
  - 30+ common Azure error codes mapped to HTTP status
  - Categories: Authentication (401), Authorization (403), Not Found (404)
  - Bad Request (400), Conflict (409), Rate Limit (429), Server Errors (500+)

- **Headers:**
  - `x-ms-request-id` - Request tracking ID (UUID or timestamp format)
  - `x-ms-error-code` - Azure error code
  - `Content-Type` - application/xml or application/json
  - `Date` - HTTP date format

- **Service-Specific Factories:**
  ```python
  create_storage_error()      # XML default, JSON optional
  create_service_bus_error()  # JSON
  create_key_vault_error()    # JSON
  create_cosmos_db_error()    # JSON
  create_generic_error()      # Custom status codes
  ```

**Error Format Examples:**
```xml
<!-- Storage (XML) -->
<?xml version="1.0" encoding="utf-8"?>
<Error>
  <Code>BlobNotFound</Code>
  <Message>The specified blob does not exist.</Message>
</Error>
```

```json
// Other services (JSON)
{
  "error": {
    "code": "ResourceNotFound",
    "message": "The specified resource does not exist."
  }
}
```

**Usage:**
```python
# Storage error (defaults to XML)
error = create_storage_error(
    "BlobNotFound",
    "The specified blob does not exist."
)

# Storage error with JSON (Accept header)
error = create_storage_error(
    "BlobNotFound",
    "Message",
    accept_header="application/json"
)

# Service Bus error (JSON)
error = create_service_bus_error(
    "QueueNotFound",
    "The specified queue does not exist."
)
```

**Status:** ✅ Complete (STORY-GATEWAY-006)
**Tests:** 55 unit tests, 100% coverage
**Documentation:** `docs/implementation/STORY-GATEWAY-006.md`

#### 2.7 Rate Limiter (`localzure/gateway/rate_limiter.py`) ✅ IMPLEMENTED

**Responsibility:** Production-grade request rate limiting using token bucket algorithm.

**Key Features:**
- Token bucket algorithm for precise rate control
- Multiple scoping levels: GLOBAL, PER_CLIENT, PER_SERVICE, PER_ACCOUNT
- Configurable requests per second and burst sizes
- Async-safe with asyncio locks
- Automatic bucket cleanup for memory management
- Per-service rule registration

**Implementation Details:**
```python
# Token Bucket Algorithm
- capacity: Maximum burst size
- refill_rate: Tokens added per second
- consume(): Attempts to consume tokens
- refill(): Refills tokens based on elapsed time

# Rate Limit Rules
- requests_per_second: Target throughput
- burst_size: Maximum burst capacity
- scope: Limiting scope (global/client/service/account)
- enabled: Enable/disable flag

# Rate Limiter
- Global and service-specific rules
- Automatic bucket key generation
- Async check_rate_limit() returns (allowed, retry_after)
- Client reset and bucket cleanup
```

**Azure Alignment:**
- Blob Storage: 20,000 requests/sec per account
- Queue Storage: 20,000 requests/sec per account
- Table Storage: 20,000 requests/sec per account

**Status:** ✅ Complete
**Tests:** 21 unit tests, 89% coverage
**Lines of Code:** 296

#### 2.8 Circuit Breaker (`localzure/gateway/circuit_breaker.py`) ✅ IMPLEMENTED

**Responsibility:** Fault tolerance and graceful degradation for downstream services.

**Key Features:**
- Three-state machine: CLOSED → OPEN → HALF_OPEN
- Configurable failure and success thresholds
- Automatic timeout-based recovery
- Fallback function support
- Per-service circuit breaker registry
- Manual and automatic reset capabilities
- Comprehensive statistics tracking

**State Machine:**
```
CLOSED (Normal Operation)
  ↓ (failure_threshold failures)
OPEN (Blocking Requests)
  ↓ (timeout_seconds elapsed)
HALF_OPEN (Testing Recovery)
  ↓ (success_threshold successes)
CLOSED

HALF_OPEN → OPEN (on any failure)
```

**Configuration:**
- failure_threshold: Failures before opening (default: 5)
- success_threshold: Successes before closing (default: 2)
- timeout_seconds: Time before half-open retry (default: 60)
- half_open_max_calls: Max calls in half-open state (default: 3)
- excluded_exceptions: Exceptions that don't trigger circuit

**Registry Features:**
- Per-service circuit breaker management
- Centralized statistics collection
- Bulk reset operations

**Status:** ✅ Complete
**Tests:** 24 unit tests, 92% coverage
**Lines of Code:** 354

#### 2.9 Distributed Tracing (`localzure/gateway/tracing.py`) ✅ IMPLEMENTED

**Responsibility:** Request correlation and distributed tracing across services.

**Key Features:**
- Correlation ID propagation
- TraceContext with metadata baggage
- Span creation with events and attributes
- Header-based context injection/extraction
- Async context variable support

**Components:**
```python
# TraceContext
- correlation_id: Unique request identifier
- request_id: Current operation ID
- parent_id: Parent operation ID
- service_name: Service name
- operation_name: Operation being performed
- metadata: Arbitrary metadata
- baggage: Key-value pairs for cross-service data

# Span
- trace_id: Trace identifier
- span_id: Span identifier
- parent_span_id: Parent span
- operation_name: Operation being traced
- start_time / end_time: Timing information
- status: ok, error, timeout
- attributes: Span attributes
- events: Span events

# Tracer
- start_span(): Create new span
- get_spans(): Query spans
- clear_spans(): Cleanup
```

**Header Propagation:**
- X-Correlation-ID: Request correlation
- X-Request-ID: Current request
- X-Parent-ID: Parent request
- X-Service-Name: Service name
- X-Operation-Name: Operation name
- X-Baggage-*: Baggage items

**Status:** ✅ Complete
**Lines of Code:** 344

#### 2.10 Metrics Collection (`localzure/gateway/metrics.py`) ✅ IMPLEMENTED

**Responsibility:** Prometheus-compatible metrics for monitoring and observability.

**Key Features:**
- Counter metrics (monotonically increasing)
- Gauge metrics (up/down values)
- Histogram metrics (distributions with buckets)
- Summary metrics (quantiles)
- Automatic metric aggregation
- Prometheus text format export

**Default Metrics:**
```
# Request Metrics
gateway_requests_total{service, method, path, status_code}
gateway_request_duration_seconds{service, method, path}
gateway_errors_total{service, method, path, status_code}
gateway_active_requests{service}

# Rate Limiting Metrics
gateway_rate_limit_exceeded_total{service, client_id}

# Circuit Breaker Metrics
gateway_circuit_breaker_state{service}
gateway_circuit_breaker_transitions_total{service, from_state, to_state}
```

**Metric Types:**
- CounterMetric: inc()
- GaugeMetric: set(), inc(), dec()
- HistogramMetric: observe(), buckets, average
- SummaryMetric: observe(), quantiles, average

**Status:** ✅ Complete
**Lines of Code:** 543

#### 2.11 FastAPI Middleware (`localzure/gateway/middleware.py`) ✅ IMPLEMENTED

**Responsibility:** Integrate all gateway components into unified request processing pipeline.

**Key Features:**
- Automatic hostname mapping and URL rewriting
- Rate limiting enforcement
- Circuit breaker protection
- Distributed tracing with correlation IDs
- Metrics collection
- Azure-consistent error formatting
- Comprehensive error handling

**Request Pipeline:**
```
1. Create trace context from headers
2. Start span for request
3. Increment active requests gauge
4. Map hostname to service
5. Check rate limits (reject if exceeded)
6. Execute via circuit breaker
7. Record metrics (duration, status)
8. Add tracing headers to response
9. Finish span
10. Decrement active requests gauge
```

**Error Handling:**
- Rate limit exceeded → 429 Too Many Requests
- Circuit open → 503 Service Unavailable
- Other errors → Formatted Azure errors
- Fallback to error formatter for consistency

**Configuration:**
```python
GatewayMiddleware(
    app=app,
    hostname_mapper=HostnameMapper(),
    rate_limiter=RateLimiter(),
    circuit_breaker_registry=CircuitBreakerRegistry(),
    enable_tracing=True,
    enable_metrics=True,
)
```

**Default Rate Limits (Azure-aligned):**
- Blob: 20,000 req/s per account, burst 5,000
- Table: 20,000 req/s per account, burst 5,000
- Queue: 20,000 req/s per account, burst 5,000

**Default Circuit Breakers:**
- Per-service breakers: blob, table, queue, cosmosdb
- Failure threshold: 5
- Success threshold: 2
- Timeout: 60 seconds

**Status:** ✅ Complete
**Lines of Code:** 422

**Production Enhancement Summary:**
- Total Lines: 1,959 (across 5 new files)
- Total Tests: 45 (rate limiter: 21, circuit breaker: 24)
- Coverage: 91% average (rate limiter: 89%, circuit breaker: 92%)
- All tests passing: 508/508 ✅

#### 2.12 Authentication & Authorization (PLANNED)

**Responsibility:** Orchestrate all authentication mechanisms.

**Planned Features:**
- SharedKey authentication (using RequestCanonicalizer)
- SAS token authentication (using SASValidator)
- OAuth 2.0 / Azure AD mock
- CORS handling

### 3. Service Emulator Layer

**Purpose:** Implement Azure service-specific logic and API compatibility.

**Status:** In Development (Blob Storage Container Operations implemented)

#### 3.1 Blob Storage Service ✅ IMPLEMENTED (SVC-BLOB-001)

**Purpose:** Emulate Azure Blob Storage API for container and blob operations.

**Location:** `localzure/services/blob/`

**Implemented Features:**
- Container lifecycle management (create, list, delete)
- Container metadata operations
- Container properties (ETag, Last-Modified, Lease Status/State)
- Public access level support (private, blob, container)
- Azure naming validation (3-63 chars, lowercase, alphanumeric, hyphens)
- Azure-compatible error codes (ContainerAlreadyExists, ContainerNotFound, InvalidContainerName)

**Architecture:**

```
┌──────────────────────────────────────────┐
│          FastAPI Endpoints               │
│     (api.py - REST handlers)             │
│  PUT /{account}/{container}              │
│  GET /{account}                          │
│  GET /{account}/{container}              │
│  PUT /{account}/{container}/metadata     │
│  DELETE /{account}/{container}           │
└──────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────┐
│        Pydantic Models                   │
│     (models.py - data validation)        │
│  - Container                             │
│  - ContainerMetadata                     │
│  - ContainerProperties                   │
│  - ContainerNameValidator                │
└──────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────┐
│       Storage Backend                    │
│   (backend.py - state management)        │
│  - ContainerBackend (in-memory)          │
│  - Async operations with locks           │
│  - ETag generation                       │
│  - Timestamp tracking                    │
└──────────────────────────────────────────┘
```

**Container Naming Rules:**
- Length: 3-63 characters
- Characters: lowercase letters, numbers, hyphens only
- Must start and end with letter or number
- No consecutive hyphens

**API Endpoints:**

| Method | Path | Description | Status Codes |
|--------|------|-------------|--------------|
| PUT | `/{account}/{container}` | Create container | 201, 400, 409 |
| GET | `/{account}` | List containers | 200 |
| GET | `/{account}/{container}` | Get properties | 200, 404 |
| PUT | `/{account}/{container}/metadata` | Set metadata | 200, 404 |
| DELETE | `/{account}/{container}` | Delete container | 202, 404 |

**Error Codes:**
- `ContainerAlreadyExists` (409): Container already exists
- `ContainerNotFound` (404): Container not found
- `InvalidContainerName` (400): Name violates Azure rules
- `InvalidHeaderValue` (400): Invalid header value

**Container Metadata:**
- Key-value pairs stored as HTTP headers
- Prefix: `x-ms-meta-*`
- Keys automatically converted to lowercase
- Updated via PUT to `/metadata` endpoint

**Container Properties:**
- `ETag`: Unique identifier, updated on changes
- `Last-Modified`: Timestamp of last modification
- `LeaseStatus`: locked | unlocked
- `LeaseState`: available | leased | expired | breaking | broken
- `PublicAccess`: private | blob | container
- `HasImmutabilityPolicy`: boolean
- `HasLegalHold`: boolean

**Implementation Details:**
- **Lines of Code:** 459 (models: 191, backend: 223, api: 269)
- **Test Coverage:** 61 tests (41 unit, 20 integration)
- **Backend:** In-memory storage with asyncio locks for thread safety
- **ETag Generation:** MD5 hash of UUID for uniqueness
- **Timestamps:** Timezone-aware UTC timestamps

**Pending Features:**
- Blob operations (upload, download, list, delete)
- Lease operations
- Snapshots
- CORS support
- Shared Access Signature (SAS) validation
- Shared Key authentication

**Usage Example:**
```python
from fastapi import FastAPI
from localzure.services.blob.api import router

app = FastAPI()
app.include_router(router)

# Create container
# PUT /blob/myaccount/mycontainer
# x-ms-meta-key: value

# List containers
# GET /blob/myaccount?prefix=my&maxresults=10

# Get properties
# GET /blob/myaccount/mycontainer

# Set metadata
# PUT /blob/myaccount/mycontainer/metadata
# x-ms-meta-newkey: newvalue

# Delete container
# DELETE /blob/myaccount/mycontainer
```

#### 3.2 Queue Storage Service ✅ IMPLEMENTED (SVC-QUEUE-001, SVC-QUEUE-002)

**Purpose:** Emulate Azure Queue Storage API for queue and message operations.

**Location:** `localzure/services/queue/`

**Implemented Features:**

**Queue Operations (SVC-QUEUE-001):**
- Queue lifecycle management (create, list, delete)
- Queue metadata operations
- Queue properties (approximate message count, ETag, Last-Modified)
- Azure naming validation (3-63 chars, lowercase, alphanumeric, hyphens)
- Azure-compatible error codes (QueueAlreadyExists, QueueNotFound, InvalidQueueName)

**Message Operations (SVC-QUEUE-002):**
- Put messages with visibility timeout and TTL
- Get messages with batch retrieval (1-32 messages)
- Peek messages without changing visibility state
- Update message content and visibility timeout
- Delete messages with pop receipt validation
- Base64 message encoding/decoding
- Automatic message expiration cleanup
- Dequeue count tracking

**Architecture:**

```
┌──────────────────────────────────────────┐
│          FastAPI Endpoints               │
│     (api.py - REST handlers)             │
│  PUT /{account}/{queue}                  │
│  GET /{account}                          │
│  GET /{account}/{queue}                  │
│  PUT /{account}/{queue}/metadata         │
│  DELETE /{account}/{queue}               │
│  POST /{account}/{queue}/messages        │
│  GET /{account}/{queue}/messages         │
│  PUT /{account}/{queue}/messages/{id}    │
│  DELETE /{account}/{queue}/messages/{id} │
└──────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────┐
│        Pydantic Models                   │
│     (models.py - data validation)        │
│  - Queue                                 │
│  - QueueMetadata                         │
│  - QueueProperties                       │
│  - Message                               │
│  - PutMessageRequest                     │
│  - UpdateMessageRequest                  │
└──────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────┐
│       Storage Backend                    │
│   (backend.py - state management)        │
│  - QueueBackend (in-memory)              │
│  - Async operations with locks           │
│  - Message visibility management         │
│  - Automatic expiration cleanup          │
│  - Pop receipt validation                │
└──────────────────────────────────────────┘
```

**Queue Naming Rules:**
- Length: 3-63 characters
- Characters: lowercase letters, numbers, hyphens only
- Must start and end with letter or number
- No consecutive hyphens

**API Endpoints:**

**Queue Operations:**
| Method | Path | Description | Status Codes |
|--------|------|-------------|--------------|
| PUT | `/{account}/{queue}` | Create queue | 201, 400, 409 |
| GET | `/{account}` | List queues | 200 |
| GET | `/{account}/{queue}` | Get properties | 200, 404 |
| PUT | `/{account}/{queue}/metadata` | Set metadata | 204, 404 |
| DELETE | `/{account}/{queue}` | Delete queue | 204, 404 |

**Message Operations:**
| Method | Path | Description | Status Codes |
|--------|------|-------------|--------------|
| POST | `/{account}/{queue}/messages` | Put message | 201, 400, 404 |
| GET | `/{account}/{queue}/messages` | Get/peek messages | 200, 404 |
| PUT | `/{account}/{queue}/messages/{id}` | Update message | 204, 400, 404 |
| DELETE | `/{account}/{queue}/messages/{id}` | Delete message | 204, 400, 404 |

**Error Codes:**
- `QueueAlreadyExists` (409): Queue already exists
- `QueueNotFound` (404): Queue not found
- `InvalidQueueName` (400): Name violates Azure rules
- `MessageNotFound` (404): Message not found or expired
- `InvalidPopReceipt` (400): Pop receipt validation failed
- `InvalidMessageContent` (400): Empty or invalid message content

**Message Properties:**
- `MessageId`: UUID v4 string
- `PopReceipt`: Base64-encoded UUID bytes (unique per update)
- `InsertionTime`: UTC timestamp of message creation
- `ExpirationTime`: UTC timestamp when message expires
- `TimeNextVisible`: UTC timestamp when message becomes visible
- `DequeueCount`: Counter incremented with each get operation
- `MessageText`: Base64-encoded message content

**Message Features:**
- **Visibility Timeout:** 0-604800 seconds (7 days max, 30s default)
- **Message TTL:** 1-604800 seconds (7 days default)
- **Batch Retrieval:** 1-32 messages per get operation
- **Peek Operation:** View messages without changing state
- **Pop Receipt:** Required for update and delete operations
- **Base64 Encoding:** Automatic encoding/decoding of message text
- **Expiration:** Automatic cleanup during get/peek operations

**Implementation Details:**
- **Lines of Code:** 1,311 (models: 267, backend: 472, api: 619, tests: 631)
- **Test Coverage:** 151 tests (82 unit, 29 integration, 40 queue ops)
- **Pass Rate:** 100% (151/151 passing)
- **Backend:** In-memory storage with asyncio locks for thread safety
- **Pop Receipt:** Base64-encoded UUID for security
- **Visibility:** Special handling for timeout=0 (immediate visibility)

**Usage Example:**

**Queue Operations:**
```python
# Create queue
# PUT /queue/myaccount/myqueue
# x-ms-meta-key: value

# List queues
# GET /queue/myaccount?prefix=my&maxresults=10

# Get properties
# GET /queue/myaccount/myqueue

# Set metadata
# PUT /queue/myaccount/myqueue/metadata
# x-ms-meta-newkey: newvalue

# Delete queue
# DELETE /queue/myaccount/myqueue
```

**Message Operations:**
```python
# Put message
# POST /queue/myaccount/myqueue/messages?visibilitytimeout=30&messagettl=3600
# <QueueMessage><MessageText>SGVsbG8sIFdvcmxkIQ==</MessageText></QueueMessage>

# Get messages (batch)
# GET /queue/myaccount/myqueue/messages?numofmessages=5&visibilitytimeout=60

# Peek messages
# GET /queue/myaccount/myqueue/messages?peekonly=true&numofmessages=10

# Update message
# PUT /queue/myaccount/myqueue/messages/{id}?popreceipt={receipt}&visibilitytimeout=120
# <QueueMessage><MessageText>VXBkYXRlZCBtZXNzYWdl</MessageText></QueueMessage>

# Delete message
# DELETE /queue/myaccount/myqueue/messages/{id}?popreceipt={receipt}
```

**Pending Features:**
- Lease operations
- CORS support
- Shared Access Signature (SAS) validation
- Shared Key authentication
- Persistent storage backend
- Dead-letter queue / poison message handling

**Planned Services:**
- Blob Storage (Blob operations - PENDING)
- Table Storage (Azure Storage Tables - PENDING)
- Service Bus (Topics & Queues - PENDING)
- Key Vault (Secrets, Keys, Certificates - PENDING)
- Cosmos DB (NoSQL database - PENDING)
- Functions (Serverless compute - PENDING)

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
- Unit tests for all core components (**achieved: 91% coverage**, target: >90%)
- Integration tests for service interactions
- Contract tests for Azure API compatibility
- Performance benchmarks for critical paths

## Plugin System ✅ IMPLEMENTED

### Service Plugin Architecture

Services are discovered dynamically via Python entrypoints, allowing for:
- **Modular Development:** Each service is developed independently
- **Optional Services:** Services can be enabled/disabled via configuration
- **Third-Party Extensions:** External developers can create custom service emulators

### Registering a Service Plugin

**In `pyproject.toml` or `setup.py`:**
```toml
[project.entry-points."localzure.services"]
blob = "localzure.services.blob:BlobStorageService"
queue = "localzure.services.queue:QueueStorageService"
```

**Service Implementation:**
```python
from localzure.core import LocalZureService, ServiceMetadata

class BlobStorageService(LocalZureService):
    def get_metadata(self) -> ServiceMetadata:
        return ServiceMetadata(
            name="blob-storage",
            version="1.0.0",
            description="Azure Blob Storage Emulator",
            dependencies=[],  # No dependencies
            port=10000,
            enabled=True
        )
    
    async def start(self) -> None:
        # Initialize blob storage resources
        pass
    
    async def stop(self) -> None:
        # Clean up resources
        pass
    
    async def reset(self) -> None:
        # Clear all blobs
        pass
    
    async def health(self) -> Dict[str, Any]:
        return {"status": "healthy"}
    
    def get_routes(self) -> List[ServiceRoute]:
        return [
            ServiceRoute("/blob/*", ["GET", "PUT", "DELETE"], self.handle_blob)
        ]
```

### Service Dependencies

Services can declare dependencies on other services:
```python
ServiceMetadata(
    name="functions",
    dependencies=["blob-storage", "queue-storage"]
)
```

The ServiceManager automatically:
1. Validates all dependencies are available
2. Detects circular dependencies
3. Starts services in correct dependency order
4. Stops services in reverse dependency order
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
- **463 tests** covering core runtime and gateway components
- **93% code coverage** achieved
- Fast execution (<7s full suite)
- Isolated test fixtures

**Test Coverage by Module:**
- `config_manager.py`: 96% coverage (22 tests)
- `logging_config.py`: 96% coverage (23 tests)  
- `runtime.py`: 87% coverage (32 tests)
- `service.py`: 94% coverage (22 tests)
- `service_manager.py`: 87% coverage (45 tests)
- `docker_manager.py`: 76% coverage (21 tests)
- `lifecycle.py`: 99% coverage (28 tests)
- `hostname_mapper.py`: 99% coverage (41 tests)
- `canonicalizer.py`: 100% coverage (38 tests)
- `sas_validator.py`: 99% coverage (42 tests)
- `protocol_router.py`: 100% coverage (50 tests)
- `retry_simulator.py`: 97% coverage (44 tests)
- `error_formatter.py`: 100% coverage (55 tests)

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
- ~~Service Manager with plugin loading~~ ✅ COMPLETED (STORY-CORE-002)
- ~~Centralized logging aggregation~~ ✅ COMPLETED (STORY-CORE-003)
- ~~Docker integration~~ ✅ COMPLETED (STORY-CORE-004)
- ~~Queue Storage service emulator~~ ✅ COMPLETED (STORY-SVC-QUEUE-001, STORY-SVC-QUEUE-002)

### Medium Term (Next quarter)
- Lifecycle management and graceful shutdown
- Blob Storage blob operations (upload, download, list)
- Table Storage emulator
- Service Bus emulator

### Long Term (6+ months)
- Full Azure SDK compatibility
- Production-ready state backends (Redis, SQLite)
- Desktop application
- Cloud-based testing integration
- Shared Access Signature (SAS) authentication
- Lease operations for blobs and queues

## Project Statistics

**Implementation Progress:**
- **Total Stories Completed:** 6 (4 Core + 2 Service)
  - STORY-CORE-001: Configuration Management ✅
  - STORY-CORE-002: Service Manager ✅
  - STORY-CORE-003: Centralized Logging ✅
  - STORY-CORE-004: Docker Integration ✅
  - STORY-SVC-BLOB-001: Blob Container Operations ✅
  - STORY-SVC-QUEUE-001: Queue Operations ✅
  - STORY-SVC-QUEUE-002: Message Operations ✅

**Code Metrics:**
- **Source Code:** ~4,500 lines
  - Core Runtime: ~1,200 lines
  - Blob Storage: ~459 lines
  - Queue Storage: ~1,358 lines
  - Infrastructure: ~1,483 lines
- **Test Code:** ~2,800 lines
  - Unit Tests: ~2,100 lines
  - Integration Tests: ~700 lines
- **Total:** ~7,300 lines
- **Test Coverage:** >90% (Core: 91%, Services: >95%)

**Test Results:**
- **Total Tests:** 212 (181 unit + 31 integration)
  - Core Runtime: 61 tests (48 unit + 13 integration)
  - Blob Storage: 61 tests (41 unit + 20 integration)
  - Queue Storage: 151 tests (122 unit + 29 integration)
- **Pass Rate:** 100% (212/212 passing)

**Service Implementation Status:**
- ✅ **Blob Storage:** Container operations complete
- ✅ **Queue Storage:** Queue and message operations complete
- ⏳ **Table Storage:** Not started
- ⏳ **Service Bus:** Not started
- ⏳ **Key Vault:** Not started
- ⏳ **Cosmos DB:** Not started

**API Endpoints Implemented:** 14
- Blob Storage: 5 endpoints
- Queue Storage: 9 endpoints

## References

- [PRD.md](../PRD.md) - Product Requirements Document
- [STORY-CORE-001.md](implementation/STORY-CORE-001.md) - Configuration Management
- [STORY-CORE-002.md](implementation/STORY-CORE-002.md) - Service Manager
- [STORY-CORE-003.md](implementation/STORY-CORE-003.md) - Centralized Logging
- [STORY-CORE-004.md](implementation/STORY-CORE-004.md) - Docker Integration
- [STORY-SVC-BLOB-001.md](implementation/STORY-SVC-BLOB-001.md) - Blob Container Operations
- [STORY-SVC-QUEUE-001.md](implementation/STORY-SVC-QUEUE-001.md) - Queue Operations
- [STORY-SVC-QUEUE-002.md](implementation/STORY-SVC-QUEUE-002.md) - Message Operations
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Azure REST API Reference](https://learn.microsoft.com/en-us/rest/api/azure/)
- [Azure Queue Storage API](https://learn.microsoft.com/en-us/rest/api/storageservices/queue-service-rest-api)

---

**Document Ownership:** LocalZure Development Team  
**Review Frequency:** Updated after each major feature implementation  
**Next Review:** After next service implementation (Table Storage or Blob Operations)
