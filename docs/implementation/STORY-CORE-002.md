# STORY-CORE-002 Implementation Documentation

**Story:** Service Manager Implementation  
**Status:** ✅ COMPLETED  
**Date:** December 4, 2025  
**Developer:** LocalZure Team

---

## Overview

Implemented a comprehensive service management system that enables dynamic discovery, lifecycle management, and dependency resolution for LocalZure service emulators. The system uses a plugin architecture based on Python entrypoints and provides robust state management with event notifications.

## Implementation Summary

### Core Components

1. **LocalZureService Abstract Interface** (`localzure/core/service.py`)
   - Abstract base class defining the contract for all service emulators
   - State machine with 6 states: UNINITIALIZED, STARTING, RUNNING, STOPPING, STOPPED, FAILED
   - Safe lifecycle methods with automatic state transitions
   - Service metadata including name, version, dependencies, and configuration

2. **ServiceManager** (`localzure/core/service_manager.py`)
   - Plugin discovery via Python entrypoints (`localzure.services`)
   - Dependency resolution using Kahn's topological sort algorithm
   - Lifecycle management (start/stop/reset) with proper ordering
   - Health monitoring and status reporting
   - Event system for state change notifications

3. **Runtime Integration** (`localzure/core/runtime.py`)
   - ServiceManager integrated into LocalZureRuntime initialization
   - Service statuses included in `/health` endpoint
   - Overall health considers service states (degraded if any services failed)

## Architecture

### Service State Machine

```
┌─────────────┐
│UNINITIALIZED│
└──────┬──────┘
       │
       ▼
   ┌────────┐
   │STARTING│◄─────┐
   └───┬────┘      │
       │           │
       ▼           │
   ┌───────┐    Retry
   │RUNNING│      │
   └───┬───┘      │
       │          │
       ▼          │
   ┌────────┐    │
   │STOPPING│────┘
   └───┬────┘
       │
       ▼
   ┌───────┐
   │STOPPED│
   └───────┘
       
   Any state can transition to:
   ┌──────┐
   │FAILED│
   └──────┘
```

### Dependency Resolution

The ServiceManager uses topological sorting to determine startup order:

1. Build dependency graph from service metadata
2. Calculate in-degree for each service
3. Use Kahn's algorithm for topological sort
4. Detect missing dependencies
5. Detect circular dependencies
6. Return ordered list for sequential startup

**Example:**
- Services: A, B (depends on A), C (depends on B)
- Startup order: A → B → C
- Shutdown order: C → B → A

### Event System

ServiceManager emits events on state changes:
```python
ServiceEvent(
    service_name="blob-storage",
    old_state=ServiceState.STARTING,
    new_state=ServiceState.RUNNING,
    error=None,
    timestamp=1234567890.123
)
```

Event listeners can be registered to track service state changes for monitoring, logging, or alerting.

## API Reference

### LocalZureService

**Abstract Methods:**
```python
def get_metadata(self) -> ServiceMetadata
async def start(self) -> None
async def stop(self) -> None  
async def reset(self) -> None
async def health(self) -> Dict[str, Any]
def get_routes(self) -> List[ServiceRoute]
```

**Properties:**
- `state`: Current ServiceState
- `error`: Last exception if in FAILED state
- `uptime`: Seconds running (None if not running)

### ServiceManager

**Key Methods:**
```python
def discover_services(self) -> None
def register_service(self, service: LocalZureService) -> None
async def initialize(self) -> None
async def start_service(self, name: str) -> None
async def stop_service(self, name: str) -> None
async def start_all(self) -> None
async def stop_all(self) -> None
async def reset_service(self, name: str) -> None
def get_service_status(self, name: str) -> Dict[str, Any]
def get_all_status(self) -> Dict[str, Dict[str, Any]]
async def get_service_health(self, name: str) -> Dict[str, Any]
async def get_all_health(self) -> Dict[str, Dict[str, Any]]
def add_event_listener(self, listener: Callable) -> None
```

**Properties:**
- `service_count`: Total registered services
- `running_services`: List of running service names
- `failed_services`: List of failed service names

## Usage Examples

### Implementing a Service

```python
from localzure.core import LocalZureService, ServiceMetadata, ServiceRoute

class BlobStorageService(LocalZureService):
    def get_metadata(self) -> ServiceMetadata:
        return ServiceMetadata(
            name="blob-storage",
            version="1.0.0",
            description="Azure Blob Storage Emulator",
            dependencies=[],
            port=10000,
            enabled=True
        )
    
    async def start(self) -> None:
        logger.info("Starting blob storage service")
        # Initialize storage backend
        self.storage = StorageBackend()
        await self.storage.initialize()
    
    async def stop(self) -> None:
        logger.info("Stopping blob storage service")
        await self.storage.cleanup()
    
    async def reset(self) -> None:
        logger.info("Resetting blob storage")
        await self.storage.clear_all()
    
    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "details": {
                "containers": await self.storage.count_containers(),
                "blobs": await self.storage.count_blobs()
            }
        }
    
    def get_routes(self) -> List[ServiceRoute]:
        return [
            ServiceRoute("/:account/:container", ["GET", "PUT", "DELETE"], self.handle_container),
            ServiceRoute("/:account/:container/:blob", ["GET", "PUT", "DELETE"], self.handle_blob)
        ]
```

### Registering via Entrypoint

**pyproject.toml:**
```toml
[project.entry-points."localzure.services"]
blob = "localzure.services.blob:BlobStorageService"
queue = "localzure.services.queue:QueueStorageService"
```

### Using ServiceManager

```python
from localzure.core import ServiceManager

# Create and initialize
manager = ServiceManager(config={"blob": {"port": 10000}})
manager.discover_services()
await manager.initialize()

# Start all services
await manager.start_all()

# Check status
status = manager.get_all_status()
print(f"Running services: {manager.running_services}")

# Listen to events
def on_state_change(event):
    print(f"{event.service_name}: {event.old_state} → {event.new_state}")

manager.add_event_listener(on_state_change)

# Stop all services
await manager.stop_all()
```

## Testing

### Test Coverage

**119 total tests** with **91% code coverage** across core modules:

**Service Tests (22 tests):**
- State machine transitions
- Lifecycle methods (start/stop/reset)
- Error handling and recovery
- Health checks and uptime tracking
- Metadata and route definitions

**Service Manager Tests (38 tests):**
- Service registration and discovery
- Dependency resolution (simple, diamond, chains)
- Circular dependency detection
- Missing dependency detection
- Lifecycle management (individual and bulk operations)
- Status and health reporting
- Event system
- Error handling and fault tolerance

### Key Test Scenarios

1. **Dependency Resolution:**
   - No dependencies (any order valid)
   - Simple chains (A → B → C)
   - Diamond dependencies (D → B,C → A)
   - Missing dependencies (fails with clear error)
   - Circular dependencies (detected and rejected)

2. **Lifecycle Management:**
   - Start service checks dependencies are running
   - Services start in dependency order
   - Services stop in reverse dependency order
   - Start/stop operations are idempotent
   - Failures don't block other services

3. **State Transitions:**
   - Valid transitions work correctly
   - State preserved across operations
   - Errors transition to FAILED state
   - Recovery from FAILED state possible

4. **Event System:**
   - Events emitted on state changes
   - Multiple listeners supported
   - Listener errors don't break system
   - Events include error information

## Files Created/Modified

### New Files
1. `localzure/core/service.py` (222 lines) - Abstract service interface
2. `localzure/core/service_manager.py` (443 lines) - Service manager implementation
3. `tests/unit/core/test_service.py` (282 lines) - Service tests
4. `tests/unit/core/test_service_manager.py` (638 lines) - Service manager tests
5. `docs/implementation/STORY-CORE-002.md` (this file)

### Modified Files
1. `localzure/core/__init__.py` - Added exports for service and service_manager
2. `localzure/core/runtime.py` - Integrated ServiceManager
3. `docs/architecture.md` - Updated with service management documentation

## Acceptance Criteria Validation

✅ **AC1:** Service manager discovers available service plugins via entrypoints  
- Implemented `discover_services()` using `importlib.metadata.entry_points()`
- Supports both Python 3.9 and 3.10+ APIs

✅ **AC2:** Each service implements the `LocalZureService` abstract interface  
- Created abstract base class with required methods
- Type hints and docstrings for all methods

✅ **AC3:** Service manager checks dependencies before starting services  
- Dependency validation in `start_service()`
- Raises `ServiceStateError` if dependencies not running

✅ **AC4:** Services can be started individually or all at once  
- `start_service(name)` for individual starts
- `start_all()` for bulk startup in correct order

✅ **AC5:** Service manager handles service crashes and reports failures  
- Services transition to FAILED state on exceptions
- Error information preserved in `service.error`
- Failed services listed in `failed_services` property

✅ **AC6:** Service manager provides status information for each registered service  
- `get_service_status(name)` returns detailed status
- `get_all_status()` returns status for all services
- Includes state, uptime, error, and dependencies

✅ **AC7:** Service manager supports graceful shutdown of all services  
- `stop_all()` stops services in reverse dependency order
- Continues even if some services fail to stop cleanly
- Reports failures without breaking shutdown process

## Technical Notes

### Entrypoint Group

Services register via the `localzure.services` entrypoint group:
```toml
[project.entry-points."localzure.services"]
service-name = "module.path:ServiceClass"
```

### Topological Sort Algorithm

Uses Kahn's algorithm for dependency resolution:
1. O(V + E) time complexity
2. O(V) space complexity
3. Detects cycles reliably
4. Deterministic ordering

### Error Handling

- Service start failures don't prevent other services from starting
- Service stop failures don't prevent graceful shutdown
- All errors logged with context
- Original exceptions preserved and re-raised with context

### State Safety

- State transitions validated before execution
- `_safe_start()` and `_safe_stop()` wrappers manage state
- Idempotent operations (safe to call multiple times)
- Thread-safe for async operations

## Future Enhancements

1. **Service Hot-Reload:** Reload services without full restart
2. **Service Metrics:** Built-in metrics collection per service
3. **Service Limits:** CPU/memory limits per service
4. **Service Isolation:** Run services in separate processes/containers
5. **Service Versioning:** Support multiple versions simultaneously
6. **Service Dependencies:** Runtime dependency injection
7. **Service Discovery:** Dynamic discovery without restart

## References

- PRD Section 4.3: Core Submodules
- PRD Section 6.1: Standard Service Interface
- [Python Packaging - Entry Points](https://packaging.python.org/en/latest/specifications/entry-points/)
- [Kahn's Algorithm](https://en.wikipedia.org/wiki/Topological_sorting#Kahn's_algorithm)

---

**Implementation Complete:** December 4, 2025  
**Tests:** 119 passed, 91% coverage  
**Next Story:** STORY-CORE-003 (Centralized Logging Infrastructure)
