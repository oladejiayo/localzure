# Persistence Quick Reference

## Enable Persistence (Choose One Method)

### Method 1: Environment Variables
```bash
export LOCALZURE_STORAGE_TYPE=sqlite
export LOCALZURE_SQLITE_PATH=./data/servicebus.db
python -m localzure start
```

### Method 2: YAML Configuration
```yaml
# config.yaml
storage:
  type: sqlite
  sqlite:
    path: ./data/servicebus.db
    wal_enabled: true
  snapshot_interval_seconds: 60
```
```bash
python -m localzure start --config config.yaml
```

### Method 3: Python API
```python
from localzure.services.servicebus.backend import ServiceBusBackend
from localzure.services.servicebus.storage import StorageConfig, StorageType

config = StorageConfig(
    storage_type=StorageType.SQLITE,
    sqlite_path="./data/servicebus.db",
)

backend = ServiceBusBackend(storage_config=config)
await backend.initialize_persistence()
# ... use backend ...
await backend.shutdown_persistence()
```

## Storage Backend Comparison

| Feature | In-Memory | SQLite | JSON |
|---------|-----------|--------|------|
| **Persistence** | ❌ | ✅ | ✅ |
| **ACID** | N/A | ✅ | ❌ |
| **Performance** | ⚡ Fastest | ~5-10% slower | ~15-25% slower |
| **Use Case** | Testing | Production | Development |
| **Human Readable** | N/A | ❌ | ✅ |

## Environment Variables

```bash
# Backend type
LOCALZURE_STORAGE_TYPE=sqlite        # in-memory|sqlite|json|redis

# SQLite settings
LOCALZURE_SQLITE_PATH=./data/servicebus.db
LOCALZURE_WAL_ENABLED=true

# JSON settings
LOCALZURE_JSON_PATH=./data

# General settings
LOCALZURE_SNAPSHOT_INTERVAL=60       # seconds (0=disabled)
LOCALZURE_AUTO_COMPACT=true
```

## CLI Commands

```bash
# View storage info
localzure storage stats

# Backup data
localzure storage export backup.json

# Restore data
localzure storage import-data backup.json

# Reclaim space
localzure storage compact

# Delete everything (requires confirmation)
localzure storage purge
```

## Common Tasks

### Backup Before Upgrade
```bash
localzure storage export backup-$(date +%Y%m%d).json
```

### Switch from In-Memory to SQLite
```bash
# No data to preserve (in-memory doesn't persist)
export LOCALZURE_STORAGE_TYPE=sqlite
localzure start
```

### Switch from SQLite to JSON
```bash
# Export first
localzure storage export backup.json

# Stop LocalZure
# Change config
export LOCALZURE_STORAGE_TYPE=json

# Restart
localzure start

# Import
localzure storage import-data backup.json
```

### Development Workflow
```bash
# Use JSON for easy inspection
export LOCALZURE_STORAGE_TYPE=json
export LOCALZURE_JSON_PATH=./dev-data

# Start LocalZure
localzure start

# Inspect state
cat ./dev-data/entities/queues.json
cat ./dev-data/messages/queue_myqueue.json
```

### Production Setup
```bash
# Use SQLite with WAL
export LOCALZURE_STORAGE_TYPE=sqlite
export LOCALZURE_SQLITE_PATH=/var/lib/localzure/servicebus.db
export LOCALZURE_WAL_ENABLED=true
export LOCALZURE_SNAPSHOT_INTERVAL=60
export LOCALZURE_AUTO_COMPACT=true

# Start LocalZure
localzure start

# Set up backup cron
echo "0 2 * * * localzure storage export /backups/servicebus-\$(date +\%Y\%m\%d).json" | crontab -
```

## Testing Scenarios

### Unit Tests (Fast, Isolated)
```python
# Use in-memory (default)
backend = ServiceBusBackend()  # No persistence
```

### Integration Tests (Realistic)
```python
# Use SQLite with temp file
import tempfile
config = StorageConfig(
    storage_type=StorageType.SQLITE,
    sqlite_path=f"{tempfile.gettempdir()}/test-{uuid.uuid4()}.db",
)
backend = ServiceBusBackend(storage_config=config)
await backend.initialize_persistence()
```

### Manual Testing (Inspectable)
```python
# Use JSON for visibility
config = StorageConfig(
    storage_type=StorageType.JSON,
    json_path="./test-data",
)
backend = ServiceBusBackend(storage_config=config)
await backend.initialize_persistence()
# Check ./test-data/ directory
```

## Troubleshooting

### "Failed to initialize persistence"
```bash
# Check disk space
df -h

# Check permissions
ls -la ./data/

# Check database integrity (SQLite)
sqlite3 ./data/servicebus.db "PRAGMA integrity_check;"

# Reset (WARNING: deletes data)
rm -rf ./data/
```

### Slow Performance
```bash
# Increase snapshot interval
export LOCALZURE_SNAPSHOT_INTERVAL=300  # 5 minutes

# Or disable auto-snapshots
export LOCALZURE_SNAPSHOT_INTERVAL=0
```

### WAL Replay Failed
```bash
# Remove WAL (loses uncommitted operations)
rm -f ./data/servicebus.db.wal

# Or restore from backup
localzure storage import-data backup.json
```

## File Locations

### SQLite
```
./data/servicebus.db          # Main database
./data/servicebus.db-wal      # Write-ahead log
./data/servicebus.db-shm      # Shared memory
```

### JSON
```
./data/
  entities/
    queues.json
    topics.json
    subscriptions.json
  messages/
    queue_{queue_name}.json
    subscription_{topic}_{sub}.json
  state.json
  operations.wal              # WAL file (if enabled)
```

## Performance Tips

1. **Use appropriate backend**
   - Development: JSON (inspectable)
   - Testing: In-memory (fast)
   - Production: SQLite (durable)

2. **Tune snapshot interval**
   - High-frequency: 10-30s (more overhead, faster recovery)
   - Low-frequency: 60-300s (less overhead, slower recovery)
   - Manual: 0 (no overhead, requires explicit snapshots)

3. **Enable WAL for SQLite**
   - Better concurrency
   - Less lock contention
   - Default: enabled

4. **Compact regularly**
   - Reclaims disk space
   - Improves performance
   - Run weekly or after large deletes

## Documentation Links

- **Full Guide**: `docs/servicebus-persistence.md`
- **Architecture**: `docs/servicebus-architecture.md`
- **Implementation**: `docs/SVC-SB-010-SUMMARY.md`
- **API Reference**: See docstrings in code

## Support

- GitHub Issues: https://github.com/oladejiayo/localzure/issues
- Label: `persistence`
- Story: SVC-SB-010
