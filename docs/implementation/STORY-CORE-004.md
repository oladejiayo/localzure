# STORY-CORE-004: Docker Integration Support

**Status:** ✅ COMPLETED

## Overview

Implemented Docker integration support for LocalZure, enabling service emulators to run in Docker containers with full lifecycle management, health monitoring, log integration, and volume mounting.

## Implementation Summary

### Components Created

1. **DockerManager** (`localzure/core/docker_manager.py`)
   - Container lifecycle management (start, stop, remove)
   - Docker availability detection
   - Health check monitoring
   - Log streaming integration
   - Volume mounting support
   - Automatic cleanup

2. **Service Interface Extension** (`localzure/core/service.py`)
   - Added `docker_config()` method to `LocalZureService`
   - Services can optionally return `DockerConfig` for container execution
   - Defaults to `None` for host-mode execution

3. **ServiceManager Integration** (`localzure/core/service_manager.py`)
   - Docker-aware service startup
   - Execution mode tracking (docker vs host)
   - Container cleanup on shutdown
   - Health checks include container status

4. **Runtime Integration** (`localzure/core/runtime.py`)
   - Passes `docker_enabled` configuration to ServiceManager
   - Graceful shutdown includes Docker cleanup

## Architecture

### Docker Manager Flow

```
┌─────────────────────────────────────────────────────┐
│                  ServiceManager                      │
│  ┌────────────────────────────────────────────────┐ │
│  │  Service Discovery & Dependency Resolution     │ │
│  └────────────────────────────────────────────────┘ │
│                       ↓                              │
│  ┌────────────────────────────────────────────────┐ │
│  │  Check service.docker_config()                 │ │
│  └────────────────────────────────────────────────┘ │
│                       ↓                              │
│           ┌───────────┴───────────┐                 │
│           ↓                       ↓                  │
│    Docker Config?           No Config                │
│           ↓                       ↓                  │
│  ┌─────────────────┐      ┌──────────────┐         │
│  │  DockerManager  │      │  Host Mode   │         │
│  │  - Start        │      │  - Direct    │         │
│  │  - Health       │      │    Start     │         │
│  │  - Logs         │      │              │         │
│  │  - Volumes      │      │              │         │
│  └─────────────────┘      └──────────────┘         │
└─────────────────────────────────────────────────────┘
```

### Container Lifecycle

```
┌──────────────┐
│ UNINITIALIZED│
└──────┬───────┘
       ↓
┌──────────────┐     ┌─────────────┐
│   CREATING   │────→│   RUNNING   │
└──────────────┘     └──────┬──────┘
                            ↓
                     ┌──────────────┐
                     │  STOPPING    │
                     └──────┬───────┘
                            ↓
                     ┌──────────────┐
                     │   STOPPED    │
                     └──────────────┘
```

## API Reference

### DockerConfig

```python
from localzure.core.docker_manager import DockerConfig

config = DockerConfig(
    image="mcr.microsoft.com/azure-storage/azurite",
    ports={"10000": "10000", "10001": "10001"},
    volumes={"/host/data": "/container/data"},
    environment={"AZURITE_ACCOUNTS": "devstoreaccount1:..."},
    command=["azurite-blob", "--blobHost", "0.0.0.0"],
    network_mode="bridge"
)
```

**Fields:**
- `image` (str, required): Docker image name
- `ports` (dict): Port mappings (container_port -> host_port)
- `volumes` (dict): Volume mounts (host_path -> container_path)
- `environment` (dict): Environment variables
- `command` (list): Override container command
- `healthcheck` (dict): Custom health check configuration
- `network_mode` (str): Network mode (default: "bridge")

### DockerManager

```python
from localzure.core.docker_manager import DockerManager

manager = DockerManager()

# Initialize and detect Docker
available = await manager.initialize()

# Start container
success = await manager.start_container("service-name", docker_config)

# Get health
health = await manager.get_container_health("service-name")

# Stop container
await manager.stop_container("service-name")

# Cleanup
await manager.shutdown()
```

**Key Methods:**

- `initialize()` → `bool`: Detect Docker availability
- `is_available()` → `bool`: Check if Docker is ready
- `start_container(name, config, instance_id=None)` → `bool`: Start container
- `stop_container(name, instance_id=None)` → `bool`: Stop container
- `remove_container(name, instance_id=None)` → `bool`: Remove container
- `get_container_health(name, instance_id=None)` → `dict`: Get health status
- `cleanup_all()`: Stop and remove all managed containers
- `shutdown()`: Clean up all resources

### Service Interface Extension

```python
from localzure.core import LocalZureService, ServiceMetadata
from localzure.core.docker_manager import DockerConfig

class MyService(LocalZureService):
    def get_metadata(self) -> ServiceMetadata:
        return ServiceMetadata(
            name="my-service",
            version="1.0.0",
            description="Example service"
        )
    
    # Optional: Return None for host mode
    def docker_config(self) -> Optional[DockerConfig]:
        return DockerConfig(
            image="myorg/service:latest",
            ports={"8080": "8080"},
            environment={"MODE": "emulator"}
        )
    
    async def start(self):
        # Only called in host mode
        # Docker containers are managed by DockerManager
        pass
    
    # ... other methods
```

## Configuration

### Enable Docker in Config

```yaml
# config.yaml
version: "0.1.0"

docker_enabled: true  # Enable Docker integration

services:
  blob:
    enabled: true
    port: 10000
  
  queue:
    enabled: true
    port: 10001
```

### Service-Specific Docker Settings

Services that provide `docker_config()` will automatically run in Docker when:
1. `docker_enabled: true` in configuration
2. Docker is available on the system
3. Service returns non-None `DockerConfig`

Fallback to host mode if:
- Docker is not available
- Service returns `None` from `docker_config()`
- `docker_enabled: false` in configuration

## Container Naming Convention

All LocalZure containers follow this naming pattern:
```
localzure-<service-name>[-<instance-id>]
```

Examples:
- `localzure-blob`
- `localzure-queue-instance-1`
- `localzure-cosmos`

## Log Integration

Container logs are automatically streamed to LocalZure's logging infrastructure:

```python
# Container logs appear as:
logger = logging.getLogger("localzure.container.localzure-blob")
# All container stdout/stderr is logged with this logger
```

## Health Checks

Health checks integrate Docker container status with service health:

```python
health = await service_manager.get_service_health("blob")
# Returns:
{
    "status": "healthy",
    "details": {...},
    "container": {  # Only present for Docker services
        "status": "running",
        "running": True,
        "health_status": "healthy",
        "exit_code": None,
        "started_at": "2025-12-04T10:00:00Z"
    }
}
```

## Volume Mounting

Services can specify volume mounts for persistent data:

```python
def docker_config(self):
    return DockerConfig(
        image="service:latest",
        volumes={
            "/var/lib/localzure/blob": "/data",  # Persistent storage
            "/tmp/logs": "/app/logs"              # Log directory
        }
    )
```

## Error Handling

### Docker Unavailable

If Docker is requested but unavailable:
1. `DockerManager.initialize()` returns `False`
2. ServiceManager logs warning and disables Docker
3. All services fall back to host mode
4. System continues to operate normally

### Container Failures

If a container fails to start:
1. `start_container()` returns `False`
2. Service state transitions to `FAILED`
3. Service startup raises `RuntimeError`
4. Error details available in service status

### Cleanup Failures

DockerManager ensures cleanup even on errors:
- Orphaned containers are removed on initialization
- `cleanup_all()` continues even if individual removals fail
- `shutdown()` attempts full cleanup with error logging

## Testing

### Unit Tests

Created 21 unit tests for DockerManager:
- Initialization (with/without Docker)
- Container lifecycle (start, stop, remove)
- Health checks
- Log streaming setup
- Cleanup operations
- Naming conventions

### Integration Tests

Added 7 integration tests for ServiceManager:
- Docker-enabled initialization
- Service startup in Docker
- Service startup in host mode
- Docker service shutdown
- Execution mode tracking
- Manager shutdown with Docker

### Test Coverage

- **DockerManager**: 76% coverage (47 uncovered lines mostly in log streaming and error paths)
- **ServiceManager**: 87% coverage (includes Docker integration)
- **Overall Core**: 88% coverage

### Running Tests

```powershell
# All Docker tests
pytest tests/unit/core/test_docker_manager.py -v

# Integration tests
pytest tests/unit/core/test_service_manager.py::TestDockerIntegration -v

# Full suite with coverage
pytest tests/unit/core/ --cov=localzure.core --cov-report=term-missing
```

## Acceptance Criteria Validation

✅ **AC1: Core runtime detects if Docker is available on the system**
- `DockerManager.initialize()` attempts to import and connect to Docker
- Returns `True` if available, `False` otherwise
- Logs warning if unavailable
- Tests: `test_initialize_with_docker_available`, `test_initialize_with_docker_unavailable`

✅ **AC2: Service emulators can specify Docker container requirements**
- Added `docker_config()` method to `LocalZureService`
- Services return `DockerConfig` with image, ports, volumes, environment
- Returns `None` for host-mode services
- Tests: `test_service_with_docker_config`, `test_service_without_docker_config`

✅ **AC3: Core runtime can start, stop, and manage Docker containers for services**
- `DockerManager` provides full lifecycle management
- ServiceManager integrates Docker operations
- Containers follow `localzure-<service>` naming convention
- Tests: `test_start_container_success`, `test_stop_container_success`, `test_remove_container_success`

✅ **AC4: Container logs are integrated into LocalZure logging infrastructure**
- `_stream_logs()` method streams container output
- Uses logger: `localzure.container.<container-name>`
- Log streaming starts/stops with container lifecycle
- Tests: `test_start_container_success` verifies log streaming setup

✅ **AC5: Container health checks are monitored and reported**
- `get_container_health()` queries Docker container status
- ServiceManager includes container health in service health
- Health status includes running state, health checks, exit codes
- Tests: `test_get_container_health_running`, `test_service_health_includes_container`

✅ **AC6: Containers are properly cleaned up on shutdown or crash**
- `cleanup_all()` removes all managed containers
- `cleanup_service_containers()` removes orphaned containers
- ServiceManager calls Docker cleanup on shutdown
- Crash recovery: Removes containers with `localzure.managed=true` label
- Tests: `test_cleanup_all`, `test_cleanup_service_containers`, `test_manager_shutdown_with_docker`

✅ **AC7: Volume mounting for persistent state is supported**
- `DockerConfig.volumes` dict maps host paths to container paths
- Volumes passed to `docker.containers.run()` with proper mount config
- Mode set to 'rw' for read-write access
- Tests: `test_start_container_success` verifies volume configuration

## Example Usage

### Basic Service with Docker

```python
from localzure.core import LocalZureService, ServiceMetadata, ServiceRoute
from localzure.core.docker_manager import DockerConfig

class AzuriteBlobService(LocalZureService):
    """Blob Storage using Azurite container."""
    
    def get_metadata(self):
        return ServiceMetadata(
            name="blob",
            version="1.0.0",
            description="Azure Blob Storage Emulator (Azurite)",
            port=10000
        )
    
    def docker_config(self):
        return DockerConfig(
            image="mcr.microsoft.com/azure-storage/azurite",
            ports={
                "10000": "10000",  # Blob
                "10001": "10001",  # Queue
                "10002": "10002"   # Table
            },
            volumes={
                "/var/lib/localzure/azurite": "/data"
            },
            environment={
                "AZURITE_ACCOUNTS": "devstoreaccount1:Eby8vdM2..."
            },
            command=[
                "azurite-blob",
                "--blobHost", "0.0.0.0",
                "--blobPort", "10000",
                "--location", "/data",
                "--loose"
            ]
        )
    
    async def start(self):
        # Not called when running in Docker
        # DockerManager handles container startup
        pass
    
    async def stop(self):
        # Not called when running in Docker
        pass
    
    async def reset(self):
        # Could be implemented to clear /data volume
        pass
    
    async def health(self):
        # Check if container is responding
        return {"status": "healthy", "mode": "docker"}
    
    def get_routes(self):
        return [
            ServiceRoute(
                path="/devstoreaccount1",
                methods=["GET", "PUT", "DELETE"],
                handler=self.handle_blob_request
            )
        ]
```

### Host-Mode Service (No Docker)

```python
class SimpleQueueService(LocalZureService):
    """In-memory queue service running in host process."""
    
    def get_metadata(self):
        return ServiceMetadata(
            name="queue",
            version="1.0.0",
            description="Simple Queue Service"
        )
    
    # No docker_config() method = host mode
    
    async def start(self):
        self._queue = []
        # Initialize in-process resources
    
    async def stop(self):
        self._queue = None
    
    # ... other methods
```

## Known Limitations

1. **Docker SDK Required**: Docker Python SDK must be installed (`pip install docker`)
2. **Platform-Specific**: Docker must be running on the host system
3. **Windows Containers**: Only Linux containers are tested
4. **Network Isolation**: Containers use bridge mode by default
5. **Resource Limits**: No automatic resource (CPU/memory) limits applied
6. **Multi-Instance**: Instance IDs supported but not fully tested

## Future Enhancements

- [ ] Resource limits (CPU, memory) configuration
- [ ] Custom network creation for service isolation
- [ ] Docker Compose integration for complex services
- [ ] Health check DSL for custom container health checks
- [ ] Container image pre-pulling
- [ ] Registry authentication support
- [ ] Windows container support
- [ ] Kubernetes deployment option

## Dependencies

- `docker>=7.0.0` (optional but recommended)
- Python 3.10+ with asyncio

## Files Changed

- `localzure/core/docker_manager.py` (NEW, 388 lines)
- `localzure/core/service.py` (modified, +23 lines)
- `localzure/core/service_manager.py` (modified, +89 lines)
- `localzure/core/runtime.py` (modified, +8 lines)
- `localzure/core/__init__.py` (modified, +3 exports)
- `requirements.txt` (modified, +1 dependency)
- `tests/unit/core/test_docker_manager.py` (NEW, 485 lines, 21 tests)
- `tests/unit/core/test_service_manager.py` (modified, +155 lines, 7 tests)

## Test Summary

- **Total Tests**: 149 (121 existing + 28 new)
- **All Passing**: ✅ 149/149
- **Coverage**: 88% overall, 76% DockerManager, 87% ServiceManager
- **New Tests**: 28 (21 DockerManager + 7 ServiceManager integration)

## References

- [Docker SDK Documentation](https://docker-py.readthedocs.io/)
- [Azurite Docker Image](https://hub.docker.com/_/microsoft-azure-storage-azurite)
- STORY-CORE-002: Service Manager Implementation
- STORY-CORE-003: Centralized Logging Infrastructure

**Implementation Date**: December 4, 2025
**Story Status**: ✅ COMPLETED
