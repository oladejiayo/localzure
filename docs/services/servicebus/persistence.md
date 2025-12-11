# Service Bus Persistence Guide

## Overview

LocalZure Service Bus now supports optional persistent storage, allowing entities (queues, topics, subscriptions) and messages to survive emulator restarts. This feature is essential for testing stateful applications and long-running scenarios.

## Quick Start

### Enable SQLite Persistence (Production)

```bash
# Using environment variables
export LOCALZURE_STORAGE_TYPE=sqlite
export LOCALZURE_SQLITE_PATH=./data/servicebus.db
localzure start
```

### Configure via YAML

Create `config.yaml`:

```yaml
storage:
  type: sqlite  # Options: in-memory, sqlite, json, redis
  sqlite:
    path: ./data/servicebus.db
    wal_enabled: true
  snapshot_interval_seconds: 60
  auto_compact: true
```

Then start LocalZure with the config:

```bash
localzure start --config config.yaml
```

### Using Python API

```python
from localzure.services.servicebus.backend import ServiceBusBackend
from localzure.services.servicebus.storage import StorageConfig, StorageType

# Create backend with persistence
config = StorageConfig(
    storage_type=StorageType.SQLITE,
    sqlite_path="./data/servicebus.db",
    snapshot_interval_seconds=60,
    wal_enabled=True,
)

backend = ServiceBusBackend(storage_config=config)
await backend.initialize_persistence()

try:
    # Use backend normally
    await backend.create_queue("my-queue", ...)
    # ... work with messages ...
finally:
    # Graceful shutdown persists state
    await backend.shutdown_persistence()
```

## Storage Backends

### In-Memory (Default)

**When to use**: Development, testing, maximum performance

**Characteristics**:
- ✅ No persistence (backward compatible)
- ✅ Zero overhead
- ✅ Fastest performance
- ❌ Data lost on restart

**Configuration**:
```yaml
storage:
  type: in-memory
```

### SQLite (Production)

**When to use**: Production, crash recovery required, single-node deployments

**Characteristics**:
- ✅ ACID compliant
- ✅ WAL mode for crash safety
- ✅ Battle-tested reliability
- ✅ Schema versioning for migrations
- ⚠️ ~5-10% slower than in-memory

**Configuration**:
```yaml
storage:
  type: sqlite
  sqlite:
    path: ./data/servicebus.db  # Database file path
    wal_enabled: true           # Enable write-ahead log
  snapshot_interval_seconds: 60  # Auto-snapshot every 60 seconds
  auto_compact: true             # Auto-compact on shutdown
```

**Features**:
- Write-Ahead Log (WAL) for crash recovery
- Automatic schema migrations
- Export/import to JSON
- VACUUM support for compaction

### JSON (Development/Debugging)

**When to use**: Development, debugging, manual state inspection

**Characteristics**:
- ✅ Human-readable files
- ✅ Easy manual editing
- ✅ No dependencies
- ✅ Version control friendly
- ❌ Slower for large datasets
- ❌ No ACID transactions

**Configuration**:
```yaml
storage:
  type: json
  json:
    path: ./data              # Directory for JSON files
    pretty_print: true        # Format JSON for readability
  snapshot_interval_seconds: 30
```

**File Structure**:
```
data/
  entities/
    queues.json           # All queue definitions
    topics.json           # All topic definitions
    subscriptions.json    # All subscription definitions
  messages/
    queue_myqueue.json    # Messages for specific queue
    subscription_mytopic_mysub.json  # Messages for subscription
  state.json              # Internal state (sequence counters, etc.)
```

### Redis (Future)

**When to use**: Distributed deployments, high availability

**Status**: Placeholder for future implementation

**Planned features**:
- Distributed storage
- High availability
- Shared state across instances

## Crash Recovery

### Write-Ahead Log (WAL)

The WAL ensures no data is lost even if LocalZure crashes unexpectedly.

**How it works**:
1. Every state-changing operation is logged to WAL before execution
2. On startup, LocalZure checks for an existing WAL file
3. If found, all operations are replayed in order
4. After successful replay, WAL is truncated
5. WAL is periodically truncated after snapshots

**WAL Operations Logged**:
- Entity creation/deletion (queues, topics, subscriptions)
- Message send/delete operations
- State updates

**Configuration**:
```yaml
storage:
  sqlite:
    wal_enabled: true  # Enable WAL (recommended for production)
```

**WAL File Location**:
- SQLite: `{sqlite_path}.wal` (e.g., `./data/servicebus.db.wal`)
- JSON: `{json_path}/operations.wal` (e.g., `./data/operations.wal`)

### Recovery Process

When LocalZure starts with WAL enabled:

```
1. Initialize storage backend
2. Check for WAL file
3. If WAL exists:
   a. Load last snapshot from storage
   b. Replay all WAL operations sequentially
   c. Log: "Replayed N operations from WAL"
4. Truncate WAL
5. Resume normal operation
```

**Example**:
```
[2025-12-11 10:15:23] INFO: Persistence initialized (storage_type=sqlite, wal_enabled=true)
[2025-12-11 10:15:23] INFO: Replayed 47 operations from WAL
[2025-12-11 10:15:23] INFO: Service Bus backend started
```

## Periodic Snapshots

LocalZure automatically persists state at regular intervals.

**Configuration**:
```yaml
storage:
  snapshot_interval_seconds: 60  # Snapshot every 60 seconds
```

**What happens during snapshot**:
1. Acquire backend lock (brief pause)
2. Serialize all entities and messages
3. Write to storage backend
4. Truncate WAL
5. Release lock

**Disabling auto-snapshots**:
```yaml
storage:
  snapshot_interval_seconds: 0  # Disable automatic snapshots
```

**Manual snapshots** (via CLI):
```bash
localzure storage snapshot
```

## Configuration Reference

### Environment Variables

All settings can be configured via environment variables (takes precedence over YAML):

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOCALZURE_STORAGE_TYPE` | string | `in-memory` | Storage backend: `in-memory`, `sqlite`, `json`, `redis` |
| `LOCALZURE_SQLITE_PATH` | string | `./data/servicebus.db` | SQLite database file path |
| `LOCALZURE_JSON_PATH` | string | `./data` | JSON storage directory |
| `LOCALZURE_REDIS_HOST` | string | `localhost` | Redis server host |
| `LOCALZURE_REDIS_PORT` | int | `6379` | Redis server port |
| `LOCALZURE_SNAPSHOT_INTERVAL` | int | `60` | Seconds between auto-snapshots (0=disabled) |
| `LOCALZURE_WAL_ENABLED` | bool | `true` | Enable write-ahead log |
| `LOCALZURE_AUTO_COMPACT` | bool | `true` | Auto-compact storage on shutdown |

### YAML Configuration

Create `config.yaml` with full settings:

```yaml
storage:
  # Storage backend type
  type: sqlite  # in-memory | sqlite | json | redis
  
  # SQLite-specific settings
  sqlite:
    path: ./data/servicebus.db
    wal_enabled: true
  
  # JSON-specific settings
  json:
    path: ./data
    pretty_print: true
  
  # Redis-specific settings (future)
  redis:
    host: localhost
    port: 6379
    password: null
    db: 0
  
  # General settings
  snapshot_interval_seconds: 60
  auto_compact: true
```

## Management Commands

### View Storage Statistics

```bash
localzure storage stats
```

**Output**:
```
Storage Statistics
==================
Backend:     SQLite
Database:    ./data/servicebus.db
Size:        2.4 MB
Entities:    15 (5 queues, 3 topics, 7 subscriptions)
Messages:    1,247 active, 23 deadletter
Last Snapshot: 2025-12-11 10:30:15
WAL Size:    45 KB
```

### Export Data to JSON

Backup all data to a portable JSON file:

```bash
localzure storage export backup.json
```

**Use cases**:
- Creating backups before upgrades
- Migrating between storage backends
- Debugging state issues
- Version control of test data

### Import Data from JSON

Restore data from a previous export:

```bash
localzure storage import backup.json
```

**Warning**: This overwrites existing data. Use with caution.

### Compact Storage

Reclaim disk space by removing deleted data:

```bash
localzure storage compact
```

**When to use**:
- After deleting many entities/messages
- Database file has grown large
- Running low on disk space

**What it does**:
- SQLite: Runs `VACUUM` to rebuild database
- JSON: Removes orphaned files
- Redis: No-op (Redis handles compaction automatically)

### Purge All Data

Delete everything and start fresh:

```bash
localzure storage purge
```

**Warning**: This is irreversible! All entities and messages will be permanently deleted.

**Confirmation required**:
```
Are you sure you want to purge ALL data? Type 'yes' to confirm: yes
Purging all data from storage...
Done. All entities and messages have been deleted.
```

## Migration Between Storage Backends

### In-Memory → SQLite

```bash
# 1. Export current state (if you have data to preserve)
localzure storage export backup.json

# 2. Stop LocalZure
localzure stop

# 3. Change configuration
export LOCALZURE_STORAGE_TYPE=sqlite
export LOCALZURE_SQLITE_PATH=./data/servicebus.db

# 4. Start LocalZure
localzure start

# 5. Import previous data (if needed)
localzure storage import backup.json
```

### SQLite → JSON

```bash
# 1. Export from SQLite
localzure storage export backup.json

# 2. Stop LocalZure
localzure stop

# 3. Change configuration
export LOCALZURE_STORAGE_TYPE=json
export LOCALZURE_JSON_PATH=./data

# 4. Start LocalZure
localzure start

# 5. Import data
localzure storage import backup.json
```

## Performance Considerations

### Overhead

Persistence adds minimal overhead:

- **In-Memory**: 0% (baseline)
- **SQLite**: ~5-10% slower
- **JSON**: ~15-25% slower (depends on data size)

### Optimization Tips

1. **Use appropriate snapshot intervals**:
   - High-frequency: 10-30 seconds (more overhead, better crash recovery)
   - Low-frequency: 60-300 seconds (less overhead, longer recovery time)
   - Manual only: 0 (no overhead, requires explicit snapshots)

2. **Enable WAL for SQLite** (default):
   ```yaml
   sqlite:
     wal_enabled: true  # Reduces write locks
   ```

3. **Compact regularly** for large datasets:
   ```bash
   # Weekly cron job
   0 2 * * 0 localzure storage compact
   ```

4. **Use in-memory for performance testing**:
   ```yaml
   storage:
     type: in-memory  # Maximum throughput
   ```

## Troubleshooting

### Issue: "Failed to initialize persistence"

**Symptoms**:
```
ERROR: Failed to initialize persistence (error=...).
Falling back to in-memory mode
```

**Causes**:
- Database file permissions
- Disk full
- Corrupt database file
- Invalid configuration

**Solutions**:
```bash
# Check disk space
df -h

# Check file permissions
ls -la ./data/

# Test database integrity (SQLite)
sqlite3 ./data/servicebus.db "PRAGMA integrity_check;"

# Reset database (WARNING: deletes all data)
rm -f ./data/servicebus.db
```

### Issue: "WAL replay failed"

**Symptoms**:
```
ERROR: WAL replay failed (error=...).
State may be inconsistent.
```

**Causes**:
- Corrupt WAL file
- Incompatible WAL version
- Disk full during write

**Solutions**:
```bash
# Remove WAL file (loses uncommitted operations)
rm -f ./data/servicebus.db.wal

# Restore from backup
localzure storage import backup.json
```

### Issue: Slow performance

**Symptoms**:
- High latency on message operations
- Timeouts in client applications

**Diagnostics**:
```bash
# Check storage stats
localzure storage stats

# Monitor snapshot duration
tail -f logs/localzure.log | grep snapshot
```

**Solutions**:
```yaml
# Increase snapshot interval
storage:
  snapshot_interval_seconds: 300  # 5 minutes

# Or disable auto-snapshots
storage:
  snapshot_interval_seconds: 0
```

## Best Practices

### Development

- Use **in-memory** for unit tests (fast, isolated)
- Use **JSON** for integration tests (inspectable, debuggable)
- Export test fixtures: `localzure storage export tests/fixtures/scenario1.json`

### Production

- Use **SQLite** for single-instance deployments
- Enable **WAL** for crash safety
- Set **snapshot_interval** to 60-120 seconds
- Enable **auto_compact** to manage disk space
- **Export backups** before upgrades

### Testing

```python
# Unit test with in-memory
backend = ServiceBusBackend()  # No config = in-memory

# Integration test with isolated SQLite
config = StorageConfig(
    storage_type=StorageType.SQLITE,
    sqlite_path=f"/tmp/test-{uuid.uuid4()}.db",
)
backend = ServiceBusBackend(storage_config=config)
```

## Backward Compatibility

Persistence is **completely optional**. Existing code works unchanged:

```python
# Old code (still works)
backend = ServiceBusBackend()

# New code (with persistence)
backend = ServiceBusBackend(storage_config=config)
```

**Default behavior**: In-memory storage (no persistence)

## Schema Versioning

LocalZure automatically manages storage schema versions:

```sql
-- Schema version tracking
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Current version**: 1

**Future migrations**: Automatic on startup

## API Reference

### StorageConfig

```python
@dataclass
class StorageConfig:
    storage_type: StorageType = StorageType.IN_MEMORY
    sqlite_path: str = "./data/servicebus.db"
    json_path: str = "./data"
    redis_host: str = "localhost"
    redis_port: int = 6379
    snapshot_interval_seconds: int = 60
    wal_enabled: bool = True
    auto_compact: bool = True
```

### ServiceBusBackend

```python
class ServiceBusBackend:
    def __init__(
        self,
        storage_config: Optional[StorageConfig] = None
    ):
        """
        Create backend with optional persistence.
        
        Args:
            storage_config: Storage configuration.
                           If None, uses in-memory (default).
        """
    
    async def initialize_persistence(self):
        """Initialize storage and recover state."""
    
    async def shutdown_persistence(self):
        """Gracefully shutdown with final snapshot."""
```

## Support

For issues or questions:

- GitHub Issues: https://github.com/oladejiayo/localzure/issues
- Documentation: https://github.com/oladejiayo/localzure/docs
- Story: SVC-SB-010 (Persistence Layer and State Management)
