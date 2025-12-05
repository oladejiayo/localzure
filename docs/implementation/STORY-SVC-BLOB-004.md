# SVC-BLOB-004: Blob Snapshots

**Status:** ✅ Completed  
**Epic:** [EPIC-SVC-BLOB](../../docs/epics/EPIC-SVC-BLOB.md)  
**Assigned To:** GitHub Copilot  
**Sprint:** December 2025  
**Completed:** December 4, 2025

## Story Overview

Implement blob snapshot functionality for Azure Blob Storage, enabling point-in-time read-only copies of blobs. Snapshots provide version history, backup capabilities, and support for testing scenarios without modifying production data.

## Acceptance Criteria

All 7 acceptance criteria have been successfully implemented and tested:

### ✅ AC1: Create Read-only Snapshots
- Implemented `create_snapshot()` in backend - creates immutable point-in-time copy
- Snapshots freeze blob content and metadata at creation time
- Modifications to base blob do not affect existing snapshots
- HTTP PUT with `comp=snapshot` query parameter
- Returns 201 Created with `x-ms-snapshot` header containing timestamp ID
- **Test Coverage:** 5 unit tests, 4 integration tests

### ✅ AC2: Unique Timestamp Identifiers
- Snapshot IDs use RFC1123 DateTime format: `YYYY-MM-DDTHH:MM:SS.fffffffZ`
- Format: `2025-12-04T21:22:01.431235Z` with microsecond precision
- Each snapshot creation generates unique timestamp
- Timestamp-based sorting for chronological ordering
- **Test Coverage:** 3 unit tests verifying uniqueness and format

### ✅ AC3: Get Blob with Snapshot Parameter
- Extended `get_blob` API to accept optional `snapshot` query parameter
- Implemented `get_blob_snapshot()` in backend
- Retrieves specific snapshot by timestamp ID
- Returns snapshot content, metadata, and properties
- HTTP GET with URL: `{blob-url}?snapshot={timestamp}`
- Returns 404 if snapshot not found
- **Test Coverage:** 3 unit tests, 3 integration tests

### ✅ AC4: List Blobs with/without Snapshots
- Extended `list_blobs()` backend method with `include_snapshots` parameter
- Updated list blobs API to parse `include` query parameter
- Default behavior: lists only base blobs (snapshots excluded)
- With `include=snapshots`: returns base blobs + all snapshots
- Snapshots sorted by (blob_name, snapshot_id) for consistent ordering
- XML response includes `<Snapshot>` element for snapshot blobs
- **Test Coverage:** 4 unit tests, 2 integration tests

### ✅ AC5: Delete Specific Snapshots
- Implemented `delete_snapshot()` in backend
- HTTP DELETE with `snapshot` query parameter
- Deletes specific snapshot without affecting base blob or other snapshots
- Automatic cleanup of empty snapshot storage structures
- Returns 202 Accepted on success
- Returns 404 if snapshot not found
- **Test Coverage:** 4 unit tests, 3 integration tests

### ✅ AC6: Delete Base Blob Behavior
- Implemented `delete_blob_with_snapshots()` with flexible deletion options
- Deleting base blob without options orphans snapshots (snapshots remain accessible)
- Three deletion modes via `x-ms-delete-snapshots` header:
  - `None` (default): Deletes base blob only, snapshots orphaned
  - `include`: Deletes base blob AND all snapshots
  - `only`: Deletes all snapshots, keeps base blob
- **Test Coverage:** 4 unit tests, 3 integration tests

### ✅ AC7: Snapshot Metadata Copied
- Snapshot creation copies all metadata from base blob
- Metadata frozen at snapshot creation time
- Subsequent metadata changes to base blob don't affect snapshots
- Snapshot metadata returned in HTTP headers on retrieval
- **Test Coverage:** 2 unit tests, 2 integration tests

## Implementation Summary

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                           │
│  - PUT {blob}?comp=snapshot (create snapshot)               │
│  - GET {blob}?snapshot={id} (retrieve snapshot)             │
│  - DELETE {blob}?snapshot={id} (delete snapshot)            │
│  - DELETE {blob} (header: x-ms-delete-snapshots)            │
│  - GET {container}?include=snapshots (list with snapshots)  │
├─────────────────────────────────────────────────────────────┤
│                       Backend Layer                         │
│  - Three-level storage: container → blob → snapshot_id      │
│  - create_snapshot(): Copy + freeze metadata                │
│  - get_blob_snapshot(): Retrieve by ID                      │
│  - list_blob_snapshots(): List all for blob                 │
│  - delete_snapshot(): Delete specific snapshot              │
│  - delete_blob_with_snapshots(): Flexible deletion          │
│  - list_blobs(include_snapshots): Optional inclusion        │
├─────────────────────────────────────────────────────────────┤
│                        Models Layer                         │
│  - BlobProperties: is_snapshot, snapshot_time               │
│  - Blob: snapshot_id field                                  │
│  - to_headers(): x-ms-snapshot header                       │
│  - to_dict(): Snapshot element in response                  │
└─────────────────────────────────────────────────────────────┘
```

### Data Model

**Snapshot Storage Structure:**
```python
_snapshots: Dict[str, Dict[str, Dict[str, Blob]]]
# container_name → blob_name → snapshot_id → Blob object
```

**Blob Object Extensions:**
- `snapshot_id: Optional[str]` - RFC1123 timestamp identifier
- `properties.is_snapshot: bool` - True for snapshot blobs
- `properties.snapshot_time: Optional[datetime]` - Creation timestamp

### Key Design Decisions

1. **RFC1123 DateTime Format**: Matches Azure Blob Storage API specification with microsecond precision
2. **Immutability**: Snapshots are read-only copies; modifications create new snapshots
3. **Orphaned Snapshots**: Deleting base blob doesn't cascade to snapshots by default (AC6)
4. **Three-level Storage**: Efficient lookup and cleanup with nested dictionaries
5. **Sorted Listing**: Snapshots sorted by (blob_name, snapshot_id) for deterministic ordering

## Files Modified

### Core Implementation
- **localzure/services/blob/models.py** (+50 lines)
  - Added `is_snapshot`, `snapshot_time` to `BlobProperties`
  - Added `snapshot_id` to `Blob` model
  - Updated `to_headers()` and `to_dict()` methods

- **localzure/services/blob/backend.py** (+250 lines)
  - Added `_snapshots` storage dictionary
  - Implemented `create_snapshot()` method
  - Implemented `get_blob_snapshot()` method
  - Implemented `list_blob_snapshots()` method
  - Implemented `delete_snapshot()` method
  - Implemented `delete_blob_with_snapshots()` method
  - Updated `list_blobs()` with `include_snapshots` parameter
  - Added `SnapshotNotFoundError` exception class

- **localzure/services/blob/api.py** (+90 lines)
  - Extended `get_blob` endpoint with `snapshot` query parameter
  - Extended `delete_blob` endpoint with snapshot deletion logic
  - Added snapshot creation handler in `put_blob` (comp=snapshot)
  - Extended `list_blobs` endpoint with `include` parameter
  - Added `SnapshotNotFoundError` exception handling

### Test Files
- **tests/unit/services/blob/test_snapshot_backend.py** (NEW, 476 lines)
  - 36 comprehensive unit tests covering all backend operations
  - Tests for model fields, snapshot methods, edge cases
  - 100% pass rate

- **tests/integration/services/blob/test_snapshot_api.py** (NEW, 437 lines)
  - 17 integration tests covering all HTTP endpoints
  - Tests for create, get, list, delete operations
  - Error case validation
  - 100% pass rate

## Test Results

### Unit Tests (36 tests)
```
✅ TestSnapshotModels (4 tests)
   - blob_snapshot_fields
   - blob_properties_snapshot_fields
   - snapshot_to_headers
   - snapshot_to_dict

✅ TestCreateSnapshot (7 tests)
   - create_snapshot_success
   - create_snapshot_copies_content
   - create_snapshot_copies_metadata (AC7)
   - create_snapshot_immutable (AC1)
   - create_snapshot_unique_timestamp (AC2)
   - create_snapshot_container_not_found
   - create_snapshot_blob_not_found

✅ TestGetBlobSnapshot (4 tests)
   - get_blob_snapshot_success (AC3)
   - get_blob_snapshot_not_found
   - get_blob_snapshot_container_not_found
   - get_blob_snapshot_blob_not_found

✅ TestListBlobSnapshots (4 tests)
   - list_blob_snapshots_empty
   - list_blob_snapshots_multiple
   - list_blob_snapshots_sorted_by_time
   - list_blob_snapshots_container_not_found
   - list_blob_snapshots_blob_not_found

✅ TestDeleteSnapshot (6 tests)
   - delete_snapshot_success (AC5)
   - delete_snapshot_base_blob_intact
   - delete_snapshot_cleanup
   - delete_snapshot_not_found
   - delete_snapshot_container_not_found
   - delete_snapshot_blob_not_found

✅ TestDeleteBlobWithSnapshots (4 tests)
   - delete_blob_with_snapshots_none (AC6)
   - delete_blob_with_snapshots_include
   - delete_blob_with_snapshots_only
   - delete_blob_with_snapshots_container_not_found
   - delete_blob_with_snapshots_blob_not_found

✅ TestListBlobsWithSnapshots (4 tests)
   - list_blobs_without_snapshots (AC4)
   - list_blobs_with_snapshots (AC4)
   - list_blobs_snapshots_sorted
   - list_blobs_snapshots_with_prefix

✅ TestSnapshotReset (1 test)
   - reset_clears_snapshots

Pass Rate: 36/36 (100%)
```

### Integration Tests (17 tests)
```
✅ TestCreateSnapshot (4 tests)
   - create_snapshot_success (AC1)
   - create_snapshot_container_not_found
   - create_snapshot_blob_not_found
   - create_multiple_snapshots (AC2)

✅ TestGetBlobSnapshot (3 tests)
   - get_blob_snapshot (AC3)
   - get_blob_snapshot_not_found
   - get_blob_snapshot_immutable (AC1)

✅ TestListBlobsWithSnapshots (2 tests)
   - list_blobs_without_snapshots_default
   - list_blobs_with_snapshots_included (AC4)

✅ TestDeleteSnapshot (3 tests)
   - delete_specific_snapshot (AC5)
   - delete_snapshot_base_blob_intact
   - delete_snapshot_not_found

✅ TestDeleteBlobWithSnapshots (3 tests)
   - delete_base_blob_snapshots_orphaned (AC6)
   - delete_blob_with_snapshots_include
   - delete_blob_with_snapshots_only

✅ TestSnapshotMetadata (2 tests)
   - snapshot_copies_metadata (AC7)
   - snapshot_metadata_immutable

Pass Rate: 17/17 (100%)
```

**Total Test Coverage:** 53 tests, 100% pass rate

## API Usage Examples

### Create Snapshot
```http
PUT /blob/myaccount/mycontainer/myblob.txt?comp=snapshot
Host: localhost:8000
x-ms-version: 2021-08-06

Response: 201 Created
x-ms-snapshot: 2025-12-04T21:22:01.431235Z
ETag: "0x8D9F8B7C6A5E4D3"
Last-Modified: Wed, 04 Dec 2025 21:22:01 GMT
```

### Get Snapshot
```http
GET /blob/myaccount/mycontainer/myblob.txt?snapshot=2025-12-04T21:22:01.431235Z
Host: localhost:8000

Response: 200 OK
x-ms-snapshot: 2025-12-04T21:22:01.431235Z
Content-Type: text/plain
Content-Length: 13

Hello, World!
```

### List Blobs with Snapshots
```http
GET /blob/myaccount/mycontainer?restype=container&comp=list&include=snapshots
Host: localhost:8000

Response: 200 OK
<EnumerationResults>
  <Blobs>
    <Blob>
      <Name>myblob.txt</Name>
      <Properties>...</Properties>
    </Blob>
    <Blob>
      <Name>myblob.txt</Name>
      <Snapshot>2025-12-04T21:22:01.431235Z</Snapshot>
      <Properties>...</Properties>
    </Blob>
  </Blobs>
</EnumerationResults>
```

### Delete Specific Snapshot
```http
DELETE /blob/myaccount/mycontainer/myblob.txt?snapshot=2025-12-04T21:22:01.431235Z
Host: localhost:8000

Response: 202 Accepted
```

### Delete Blob with All Snapshots
```http
DELETE /blob/myaccount/mycontainer/myblob.txt
Host: localhost:8000
x-ms-delete-snapshots: include

Response: 202 Accepted
```

### Delete Only Snapshots
```http
DELETE /blob/myaccount/mycontainer/myblob.txt
Host: localhost:8000
x-ms-delete-snapshots: only

Response: 202 Accepted
```

## Technical Highlights

### Snapshot ID Generation
Uses Python's `datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')` for RFC1123 format with microsecond precision.

### Immutability Enforcement
Snapshots are stored as separate `Blob` objects with frozen properties. No modification APIs accept snapshot parameters except GET and DELETE.

### Storage Efficiency
Three-level nested dictionary enables O(1) lookup and efficient cleanup:
```python
snapshot = self._snapshots[container_name][blob_name][snapshot_id]
```

### Error Handling
- `SnapshotNotFoundError`: Specific exception for missing snapshots (HTTP 404)
- `BlobNotFoundError`: Base blob not found (HTTP 404)
- `ContainerNotFoundError`: Container not found (HTTP 404)

### Azure API Compliance
Follows Azure Blob Storage REST API v2021-08-06 specification for:
- Snapshot URL format
- Response headers
- Error codes
- Query parameters
- XML list format

## Future Enhancements

1. **Snapshot Metadata Update**: Allow metadata modification on snapshots (currently immutable)
2. **Snapshot Copy**: Copy blob from snapshot source
3. **Snapshot Versioning**: Track snapshot relationships and lineage
4. **Snapshot Expiration**: Automatic cleanup of old snapshots
5. **Snapshot Tags**: User-defined labels for snapshot categorization
6. **Incremental Snapshots**: Store only changes since previous snapshot

## Related Documentation

- [EPIC-SVC-BLOB.md](../../docs/epics/EPIC-SVC-BLOB.md) - Parent epic
- [Azure Blob Snapshots Documentation](https://learn.microsoft.com/en-us/rest/api/storageservices/snapshot-blob)
- [STORY-SVC-BLOB-003.md](STORY-SVC-BLOB-003.md) - Blob Lease Management (previous story)

## Lessons Learned

1. **Orphaned Snapshots Design**: The decision to keep snapshots when base blob is deleted (AC6) required careful consideration. This matches Azure's behavior and provides flexibility.

2. **Exception Hierarchy**: Adding `SnapshotNotFoundError` as a separate exception (not a subclass of `BlobNotFoundError`) provides clear error semantics.

3. **Storage Structure**: The three-level nested dictionary proved efficient for both lookup and cleanup operations.

4. **Test Coverage**: Writing comprehensive tests (53 total) before final implementation helped catch edge cases like snapshot retrieval when base blob is deleted.

5. **RFC1123 Format**: Python's `strftime` with `%f` (microseconds) provides sufficient precision for unique snapshot IDs in high-frequency scenarios.

---

**Implementation completed successfully on December 4, 2025**  
**All acceptance criteria validated**  
**53 tests passing (100%)**
