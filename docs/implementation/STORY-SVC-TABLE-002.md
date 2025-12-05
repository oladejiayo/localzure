# STORY-SVC-TABLE-002: OData Query Support

**Status:** ✅ Complete  
**Story ID:** SVC-TABLE-002  
**Epic:** Table Storage Service  
**Created:** 2025-01-XX  
**Completed:** 2025-01-XX

## Overview

Implemented OData query capabilities for Azure Table Storage service, enabling filtering, projection, and pagination of table entities via query parameters. The implementation includes a custom OData parser, backend query engine, and REST API endpoint with full continuation token support.

## Acceptance Criteria

All acceptance criteria have been validated:

### ✅ AC1: Filter Parameter Support
- **Criteria:** Support `$filter` parameter for filtering entities
- **Implementation:** 
  - Custom OData query parser with tokenizer and recursive descent parsing
  - Supports comparison operators: `eq`, `ne`, `gt`, `ge`, `lt`, `le`
  - Supports logical operators: `and`, `or`, `not` with proper precedence
  - Supports string functions: `startswith`, `endswith`, `contains`
  - Filter expressions evaluated against entity properties
- **Tests:** 
  - `test_query.py::TestODataFilterComparison` (8 tests)
  - `test_query.py::TestODataFilterLogical` (5 tests)
  - `test_query_api.py::TestQueryFilter` (7 tests)
- **Examples:**
  ```
  GET /table/testaccount/Products()?$filter=Price gt 50
  GET /table/testaccount/Products()?$filter=Active eq true
  GET /table/testaccount/Products()?$filter=Name startswith 'Azure'
  ```

### ✅ AC2: Comparison Operators
- **Criteria:** Support `eq`, `ne`, `gt`, `lt`, `ge`, `le` operators
- **Implementation:** 
  - All operators implemented in parser with proper type handling
  - Supports string, numeric, and boolean comparisons
  - Case-insensitive string matching for `eq` and `ne`
- **Tests:**
  - `test_query.py::test_filter_eq_string`
  - `test_query.py::test_filter_gt_number`
  - `test_query.py::test_filter_le_number`
  - `test_query_backend.py::test_query_filter_eq`
  - `test_query_backend.py::test_query_filter_gt`
- **Examples:**
  ```
  $filter=Stock gt 100
  $filter=Price le 50.00
  $filter=Active ne false
  ```

### ✅ AC3: Logical Operators
- **Criteria:** Support `and`, `or`, `not` logical operators
- **Implementation:**
  - Recursive descent parser handles operator precedence correctly
  - `and` has higher precedence than `or`
  - `not` is unary operator with highest precedence
  - Parentheses supported for explicit grouping
- **Tests:**
  - `test_query.py::TestODataFilterLogical` (5 tests)
  - `test_query.py::test_filter_multiple_and_conditions`
  - `test_query.py::test_filter_precedence`
  - `test_query_backend.py::test_query_filter_and`
  - `test_query_backend.py::test_query_filter_or`
- **Examples:**
  ```
  $filter=Price gt 50 and Stock lt 100
  $filter=Active eq true or Price lt 20
  $filter=not (Price gt 100)
  $filter=(Price gt 50 and Price lt 200) or Stock gt 150
  ```

### ✅ AC4: Select Parameter
- **Criteria:** Support `$select` for property projection
- **Implementation:**
  - Comma-separated list of property names
  - Always includes system properties: `PartitionKey`, `RowKey`, `Timestamp`
  - Properties not present in entity are omitted from result
  - Works in combination with `$filter`
- **Tests:**
  - `test_query.py::TestODataQuery::test_query_select_single_property`
  - `test_query.py::TestODataQuery::test_query_select_multiple_properties`
  - `test_query_backend.py::TestQueryEntitiesProjection` (3 tests)
  - `test_query_api.py::TestQuerySelect` (3 tests)
- **Examples:**
  ```
  $select=Name,Price
  $select=PartitionKey,RowKey,Active
  $select=Name&$filter=Price gt 50
  ```

### ✅ AC5: Top Parameter
- **Criteria:** Support `$top` for limiting result count
- **Implementation:**
  - Integer parameter limits number of entities returned
  - Works with filters and projection
  - Respects default page size of 1000
  - Generates continuation token when more results available
- **Tests:**
  - `test_query.py::TestODataQuery::test_query_top`
  - `test_query_backend.py::TestQueryEntitiesPagination::test_query_top_parameter`
  - `test_query_api.py::TestQueryTop` (3 tests)
- **Examples:**
  ```
  $top=10
  $top=5&$filter=Active eq true
  $top=3&$select=Name,Price&$filter=Price gt 50
  ```

### ✅ AC6: Continuation Tokens
- **Criteria:** Support pagination with continuation tokens
- **Implementation:**
  - Base64-encoded JSON with `NextPartitionKey` and `NextRowKey`
  - Returned in `x-ms-continuation-NextPartitionKey` header
  - Client passes `NextPartitionKey` and `NextRowKey` query parameters
  - Entities sorted by `(PartitionKey, RowKey)` for consistent pagination
  - Works with filters and projection
- **Tests:**
  - `test_query_backend.py::TestQueryEntitiesPagination::test_query_pagination_with_continuation_token`
  - `test_query_backend.py::TestQueryEntitiesPagination::test_query_pagination_with_filter`
  - `test_query_api.py::TestQueryPagination` (2 tests)
- **Examples:**
  ```
  # First page
  GET /table/testaccount/Products()?$top=10
  # Returns: x-ms-continuation-NextPartitionKey header
  
  # Second page
  GET /table/testaccount/Products()?$top=10&NextPartitionKey=Books&NextRowKey=002
  ```

### ✅ AC7: Query Optimization
- **Criteria:** Optimize queries based on PartitionKey presence
- **Implementation:**
  - **Point Query:** Filter on `PartitionKey eq` and `RowKey eq` → O(1) lookup
  - **Partition Scan:** Filter on `PartitionKey eq` → O(n) where n = partition size
  - **Table Scan:** No PartitionKey filter → O(n) where n = table size
  - All entities sorted for consistent pagination
- **Tests:**
  - `test_query_backend.py::TestQueryEntitiesPerformance::test_query_by_partition_key`
  - `test_query_backend.py::TestQueryEntitiesPerformance::test_query_point_query`
  - `test_query_backend.py::TestQueryEntitiesPerformance::test_query_table_scan`
  - `test_query_api.py::TestQueryPerformance` (3 tests)
- **Performance:**
  - Point query: ~0.001s for 1000 entities
  - Partition scan: ~0.01s for 1000 entities
  - Table scan: ~0.1s for 1000 entities

## Implementation Summary

### Core Components

1. **OData Query Parser** (`localzure/services/table/query.py`, 350 lines)
   - `ODataFilter`: Tokenizer and recursive descent parser for filter expressions
   - `ODataQuery`: Query orchestrator for filter evaluation and projection
   - Supports operators: `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `and`, `or`, `not`
   - Supports functions: `startswith`, `endswith`, `contains`
   - Parser includes:
     - Regex-based tokenizer for strings, numbers, operators, identifiers
     - Recursive descent parsing with proper precedence
     - Position reset and function caching for performance
     - Type-safe comparison with automatic coercion

2. **Backend Query Engine** (`localzure/services/table/backend.py`, +90 lines)
   - `query_entities()`: Main query method with filter/select/top/continuation support
   - Entity sorting by `(PartitionKey, RowKey)` for pagination consistency
   - Continuation token generation and consumption
   - Lazy filter evaluation using closures
   - Property projection with system property inclusion

3. **Query API Endpoint** (`localzure/services/table/api.py`, +100 lines)
   - `GET /{account}/{table}()`: Query entities endpoint
   - Query parameters: `filter`, `select`, `top`, `NextPartitionKey`, `NextRowKey`
   - Returns OData JSON format with `value` array
   - Continuation headers: `x-ms-continuation-NextPartitionKey`
   - Error handling for invalid filters and missing tables

### Files Modified

- `localzure/services/table/query.py` (NEW, 350 lines)
- `localzure/services/table/backend.py` (+90 lines)
- `localzure/services/table/api.py` (+100 lines)
- `localzure/services/table/__init__.py` (+3 exports)

**Total:** 540 lines of production code

### Test Coverage

#### Unit Tests

1. **Query Parser Tests** (`tests/unit/services/table/test_query.py`, 350 lines, 33 tests)
   - `TestODataFilterComparison`: 8 tests for comparison operators
   - `TestODataFilterLogical`: 5 tests for logical operators
   - `TestODataFilterStringFunctions`: 4 tests for string functions
   - `TestODataFilterEdgeCases`: 6 tests for edge cases and errors
   - `TestODataFilterMultipleConditions`: 3 tests for complex expressions
   - `TestODataQuery`: 7 tests for query orchestration

2. **Backend Query Tests** (`tests/unit/services/table/test_table_query_backend.py`, 400 lines, 21 tests)
   - `TestQueryEntitiesBasic`: 3 tests for basic queries
   - `TestQueryEntitiesFiltering`: 6 tests for filter combinations
   - `TestQueryEntitiesProjection`: 3 tests for property selection
   - `TestQueryEntitiesPagination`: 4 tests for continuation tokens
   - `TestQueryEntitiesPerformance`: 3 tests for query optimization
   - `TestQueryEntitiesCombined`: 2 tests for complex scenarios

#### Integration Tests

3. **API Query Tests** (`tests/integration/services/table/test_query_api.py`, 550 lines, 26 tests)
   - `TestQueryBasic`: 3 tests for basic endpoint functionality
   - `TestQueryFilter`: 7 tests for filter parameter
   - `TestQuerySelect`: 3 tests for select parameter
   - `TestQueryTop`: 3 tests for top parameter
   - `TestQueryPagination`: 2 tests for continuation tokens
   - `TestQueryCombined`: 2 tests for multiple parameters
   - `TestQueryPerformance`: 3 tests for query optimization
   - `TestQueryEdgeCases`: 3 tests for error handling

**Total:** 1,300 lines of test code, 80 tests

### Test Results

```
Complete Test Suite: 1104 tests
├── Parser Unit Tests: 33/33 passed ✅
├── Backend Unit Tests: 21/21 passed ✅
├── API Integration Tests: 26/26 passed ✅
└── Existing Tests: 1024/1024 passed ✅ (no regressions)

Total: 1104/1104 tests passing (100%)
Time: 16.65s
```

## Technical Highlights

### Parser Design

The OData parser uses a recursive descent approach with the following grammar:

```
expression := or_expr
or_expr    := and_expr ('or' and_expr)*
and_expr   := primary ('and' primary)*
primary    := 'not' primary
            | '(' expression ')'
            | comparison
            | string_function
comparison := property operator value
operator   := 'eq' | 'ne' | 'gt' | 'ge' | 'lt' | 'le'
string_fn  := function '(' property ',' value ')'
function   := 'startswith' | 'endswith' | 'contains'
```

This ensures correct operator precedence: `not` > `and` > `or`

### Continuation Token Format

```json
{
  "NextPartitionKey": "Books",
  "NextRowKey": "003"
}
```

Base64-encoded and returned in `x-ms-continuation-NextPartitionKey` header.

### Query Optimization Strategy

1. **Point Query Detection:**
   ```
   $filter=PartitionKey eq 'Books' and RowKey eq '001'
   → Direct dictionary lookup: O(1)
   ```

2. **Partition Scan Detection:**
   ```
   $filter=PartitionKey eq 'Books' and Price gt 50
   → Filter single partition: O(n) where n = partition size
   ```

3. **Table Scan Fallback:**
   ```
   $filter=Price gt 50
   → Filter all entities: O(n) where n = table size
   ```

## Usage Examples

### Basic Filtering
```bash
# Equality
GET /table/testaccount/Products()?$filter=Name eq 'Azure Book'

# Comparison
GET /table/testaccount/Products()?$filter=Price gt 50 and Stock lt 100

# Boolean
GET /table/testaccount/Products()?$filter=Active eq true
```

### String Functions
```bash
# Starts with
GET /table/testaccount/Products()?$filter=startswith(Name,'Azure')

# Contains
GET /table/testaccount/Products()?$filter=contains(Name,'Guide')

# Combined
GET /table/testaccount/Products()?$filter=startswith(Name,'Azure') and Price lt 100
```

### Property Projection
```bash
# Select specific properties
GET /table/testaccount/Products()?$select=Name,Price

# With filter
GET /table/testaccount/Products()?$select=Name,Stock&$filter=Active eq true
```

### Result Limiting
```bash
# Top N results
GET /table/testaccount/Products()?$top=10

# Combined with filter
GET /table/testaccount/Products()?$top=5&$filter=Price gt 50&$select=Name,Price
```

### Pagination
```bash
# First page
GET /table/testaccount/Products()?$top=10
# Response includes: x-ms-continuation-NextPartitionKey header

# Subsequent pages
GET /table/testaccount/Products()?$top=10&NextPartitionKey=Books&NextRowKey=003
```

### Complex Queries
```bash
# Multiple conditions
GET /table/testaccount/Products()?$filter=(Price gt 50 and Price lt 200) or Stock gt 150

# With projection and limiting
GET /table/testaccount/Products()?$filter=Active eq true&$select=Name,Price&$top=20
```

## OData Operator Support

| Operator | Type | Support | Example |
|----------|------|---------|---------|
| `eq` | Comparison | ✅ Full | `Name eq 'Azure'` |
| `ne` | Comparison | ✅ Full | `Active ne false` |
| `gt` | Comparison | ✅ Full | `Price gt 50` |
| `ge` | Comparison | ✅ Full | `Stock ge 100` |
| `lt` | Comparison | ✅ Full | `Price lt 200` |
| `le` | Comparison | ✅ Full | `Stock le 50` |
| `and` | Logical | ✅ Full | `Price gt 50 and Active eq true` |
| `or` | Logical | ✅ Full | `Price lt 20 or Stock gt 100` |
| `not` | Logical | ✅ Full | `not (Price gt 100)` |
| `startswith` | String | ✅ Full | `startswith(Name,'Azure')` |
| `endswith` | String | ✅ Full | `endswith(Name,'Book')` |
| `contains` | String | ✅ Full | `contains(Name,'Guide')` |
| `tolower` | String | ❌ Not supported | - |
| `toupper` | String | ❌ Not supported | - |
| `add` | Arithmetic | ❌ Not supported | - |
| `sub` | Arithmetic | ❌ Not supported | - |

## Performance Characteristics

Based on performance tests with 1000 entities:

| Query Type | Time (ms) | Entities Scanned | Optimization |
|------------|-----------|------------------|--------------|
| Point Query | ~1 | 1 | Direct lookup |
| Partition Scan | ~10 | 100-500 | Filter by PK |
| Table Scan | ~100 | 1000 | Full scan |

**Recommendations:**
- Always include `PartitionKey eq` when possible
- Use point queries (`PartitionKey eq` + `RowKey eq`) for best performance
- Limit result sets with `$top` for large tables
- Use continuation tokens for paginated results

## Known Limitations

1. **String Function Support:** Limited to `startswith`, `endswith`, `contains`. No support for `tolower`, `toupper`, `concat`, etc.

2. **Arithmetic Operations:** No support for `add`, `sub`, `mul`, `div`, `mod` in filter expressions.

3. **Date Functions:** No support for date/time functions like `year()`, `month()`, `day()`, `hour()`, etc.

4. **Property Path:** No support for nested property access (all properties are top-level).

5. **Type Casting:** No explicit type casting functions like `cast()`.

6. **Aggregation:** No support for aggregation functions like `count()`, `sum()`, `avg()`.

7. **Case Sensitivity:** String comparisons are case-insensitive for `eq`/`ne`, case-sensitive for string functions.

## Future Enhancements

1. **Additional String Functions:**
   - `tolower()`, `toupper()` for case normalization
   - `trim()`, `length()` for string manipulation
   - `substring()`, `indexof()` for substring operations

2. **Date/Time Support:**
   - Date comparison operators
   - Date extraction functions (`year()`, `month()`, `day()`)
   - Date arithmetic

3. **Arithmetic Expressions:**
   - Basic arithmetic in filters: `Price mul Quantity gt 100`
   - Mathematical functions: `round()`, `ceiling()`, `floor()`

4. **Query Hints:**
   - `$orderby` for custom sorting
   - `$expand` for related entities (if supported)
   - `$count` for result count without entities

5. **Performance Optimization:**
   - Index-based filtering for common properties
   - Query plan analysis and caching
   - Parallel partition scanning for large tables

6. **Advanced Features:**
   - Saved queries/query templates
   - Query execution statistics
   - Query timeout and cancellation

## Related Stories

- **SVC-TABLE-001:** Table and Entity Operations (✅ Complete)
- **SVC-TABLE-003:** Batch Operations (Planned)
- **SVC-TABLE-004:** Transaction Support (Planned)
- **SVC-TABLE-005:** Secondary Indexes (Future)

## References

- [Azure Table Storage Query Documentation](https://docs.microsoft.com/en-us/rest/api/storageservices/query-entities)
- [OData v3 Query Syntax](https://www.odata.org/documentation/odata-version-3-0/)
- Epic: Table Storage Service (SVC-TABLE)
- Implementation Guide: `implement-epic.prompt.md`

---

**Story delivered:** All acceptance criteria met, comprehensive test coverage (80 tests), zero regressions, complete documentation.
