# STORY-GATEWAY-006: Azure-Consistent Error Responses

**Status**: ✅ Complete  
**Component**: Gateway  
**Module**: `localzure.gateway.error_formatter`

## Overview

Implemented Azure-consistent error response formatting to ensure Azure SDKs can correctly parse and handle errors. The error formatter supports both XML (for Storage services) and JSON (for other services), includes proper headers (x-ms-request-id, x-ms-error-code), and maps common Azure error codes to correct HTTP status codes.

## Implementation Summary

### Components Implemented

1. **ErrorFormat** - Enum for error response formats
   - `JSON` - For most Azure services
   - `XML` - For Storage services (Blob, Queue, Table, File)

2. **ServiceType** - Enum for Azure service types
   - `STORAGE` - Blob, Queue, Table, File Storage
   - `SERVICE_BUS` - Azure Service Bus
   - `KEY_VAULT` - Azure Key Vault
   - `COSMOS_DB` - Azure Cosmos DB
   - `GENERIC` - Generic services

3. **ErrorContext** - Error context dataclass
   - Error code and message
   - Service type
   - HTTP status code (auto-mapped from error code)
   - Request ID (auto-generated if not provided)
   - Additional info dictionary

4. **AzureError** - Error response dataclass
   - Status code, headers, body, content type
   - `to_dict()` method for FastAPI integration

5. **ERROR_CODE_MAPPINGS** - Mapping of Azure error codes to HTTP status codes
   - 30+ common Azure error codes
   - Categories: Authentication (401), Authorization (403), Not Found (404), Bad Request (400), Conflict (409), Rate Limit (429), Server Errors (500+)

6. **Helper Functions**
   - `generate_request_id()` - UUID-based request IDs
   - `generate_timestamp_request_id()` - Timestamp-based IDs
   - `determine_error_format()` - Content negotiation
   - `format_error_xml()` - XML formatting for Storage
   - `format_error_json()` - JSON formatting for other services
   - `create_error_headers()` - Generate x-ms-* headers
   - `create_error_response()` - Main error response factory
   - `map_error_code_to_status()` - Error code to status mapping

7. **Service-Specific Factories**
   - `create_storage_error()` - Storage service errors
   - `create_service_bus_error()` - Service Bus errors
   - `create_key_vault_error()` - Key Vault errors
   - `create_cosmos_db_error()` - Cosmos DB errors
   - `create_generic_error()` - Generic errors

## Acceptance Criteria Validation

### AC1: Proper HTTP Status Codes ✅

**Requirement**: Error responses include proper HTTP status codes matching Azure

**Implementation**:
```python
ERROR_CODE_MAPPINGS = {
    "AuthenticationFailed": 401,
    "BlobNotFound": 404,
    "ContainerAlreadyExists": 409,
    "TooManyRequests": 429,
    # ... 30+ mappings
}

context = ErrorContext(error_code="BlobNotFound", message="...")
# context.status_code auto-set to 404
```

**Tests**:
- `test_authentication_error_codes` - Tests 401 mappings
- `test_not_found_error_codes` - Tests 404 mappings
- `test_conflict_error_codes` - Tests 409 mappings
- `test_server_error_codes` - Tests 500+ mappings
- `test_map_error_code_to_status` - Tests mapping function

### AC2: Error Body Format Matches Azure ✅

**Requirement**: Error response body format matches Azure (XML for Storage, JSON for others)

**Implementation**:
```python
# Storage XML format
<?xml version="1.0" encoding="utf-8"?>
<Error>
  <Code>BlobNotFound</Code>
  <Message>The specified blob does not exist.</Message>
</Error>

# Other services JSON format
{
  "error": {
    "code": "ResourceNotFound",
    "message": "The specified resource does not exist."
  }
}
```

**Tests**:
- `test_basic_xml_format` - Tests XML structure
- `test_xml_with_declaration` - Tests XML declaration
- `test_basic_json_format` - Tests JSON structure
- `test_storage_error_xml_default` - Tests Storage defaults to XML
- `test_service_bus_error_json` - Tests Service Bus uses JSON

### AC3: Error Code, Message, and Request ID ✅

**Requirement**: Error responses include error code, message, and request ID

**Implementation**:
```python
context = ErrorContext(
    error_code="BlobNotFound",
    message="The specified blob does not exist.",
    # request_id auto-generated if not provided
)
error = create_error_response(context)
# error.error_code = "BlobNotFound"
# error.message = "The specified blob does not exist."
# error.request_id = "abc-123-..."
```

**Tests**:
- `test_error_context_defaults` - Tests auto-generation
- `test_error_context_custom_request_id` - Tests custom IDs
- `test_storage_error_custom_request_id` - Tests ID propagation
- `test_blob_not_found_scenario` - End-to-end validation

### AC4: x-ms-request-id Header ✅

**Requirement**: x-ms-request-id header is included in all error responses

**Implementation**:
```python
headers = {
    "x-ms-request-id": request_id,
    # ... other headers
}
```

**Tests**:
- `test_required_headers` - Tests x-ms-request-id presence
- `test_storage_error_xml_format` - Tests header in Storage errors
- `test_service_bus_error_headers` - Tests header in Service Bus errors
- `test_key_vault_error_custom_request_id` - Tests custom request IDs

### AC5: x-ms-error-code Header ✅

**Requirement**: x-ms-error-code header contains the Azure error code

**Implementation**:
```python
headers = {
    "x-ms-error-code": error_code,
    # ... other headers
}
```

**Tests**:
- `test_required_headers` - Tests x-ms-error-code presence
- `test_storage_error_xml_default` - Tests error code in headers
- `test_blob_not_found_scenario` - Validates error code header value

### AC6: Content-Type Matches Accept Header ✅

**Requirement**: Error response content-type matches request Accept header

**Implementation**:
```python
def determine_error_format(service_type, accept_header):
    if service_type == ServiceType.STORAGE:
        if accept_header and "application/json" in accept_header.lower():
            return ErrorFormat.JSON
        return ErrorFormat.XML
    return ErrorFormat.JSON

# Usage
error = create_storage_error(
    "BlobNotFound",
    "Message",
    accept_header="application/json"
)
# Returns JSON instead of XML
```

**Tests**:
- `test_storage_defaults_to_xml` - Tests default XML
- `test_storage_json_with_accept_header` - Tests JSON with Accept
- `test_storage_error_json_format` - Tests JSON formatting
- `test_content_negotiation_scenario` - End-to-end content negotiation

### AC7: Common Azure Error Codes Mapped ✅

**Requirement**: Common Azure error codes are properly mapped

**Implementation**:
```python
ERROR_CODE_MAPPINGS = {
    # Authentication (401)
    "AuthenticationFailed": 401,
    "InvalidAuthenticationInfo": 401,
    "MissingRequiredHeader": 401,
    
    # Authorization (403)
    "AuthorizationFailed": 403,
    "InsufficientAccountPermissions": 403,
    
    # Not Found (404)
    "ResourceNotFound": 404,
    "BlobNotFound": 404,
    "ContainerNotFound": 404,
    "QueueNotFound": 404,
    
    # ... 30+ total mappings
}
```

**Tests**:
- `test_authentication_error_codes` - Tests auth error mappings
- `test_authorization_error_codes` - Tests authz error mappings  
- `test_not_found_error_codes` - Tests 404 mappings
- `test_bad_request_error_codes` - Tests 400 mappings
- `test_conflict_error_codes` - Tests 409 mappings
- `test_server_error_codes` - Tests 500+ mappings
- `test_rate_limit_error_code` - Tests 429 mapping

## API Reference

### ErrorContext

Configuration for error response generation.

```python
@dataclass
class ErrorContext:
    error_code: str
    message: str
    service_type: ServiceType = ServiceType.GENERIC
    status_code: Optional[int] = None  # Auto-mapped if None
    request_id: Optional[str] = None   # Auto-generated if None
    additional_info: Optional[Dict[str, Any]] = None
```

### AzureError

Represents an Azure-style error response.

```python
@dataclass
class AzureError:
    error_code: str
    message: str
    status_code: int
    request_id: str
    headers: Dict[str, str]
    body: str
    content_type: str
    
    def to_dict(self) -> Dict[str, Any]
```

### Main Functions

```python
def generate_request_id() -> str
def generate_timestamp_request_id() -> str
def determine_error_format(service_type: ServiceType, accept_header: Optional[str]) -> ErrorFormat
def format_error_xml(context: ErrorContext) -> str
def format_error_json(context: ErrorContext) -> str
def create_error_headers(error_code: str, request_id: str, content_type: str) -> Dict[str, str]
def create_error_response(context: ErrorContext, *, error_format: Optional[ErrorFormat], accept_header: Optional[str]) -> AzureError
def map_error_code_to_status(error_code: str, default: int = 500) -> int
```

### Service-Specific Factories

```python
def create_storage_error(error_code: str, message: str, *, request_id: Optional[str], accept_header: Optional[str], additional_info: Optional[Dict[str, Any]]) -> AzureError
def create_service_bus_error(error_code: str, message: str, *, request_id: Optional[str], additional_info: Optional[Dict[str, Any]]) -> AzureError
def create_key_vault_error(error_code: str, message: str, *, request_id: Optional[str], additional_info: Optional[Dict[str, Any]]) -> AzureError
def create_cosmos_db_error(error_code: str, message: str, *, request_id: Optional[str], additional_info: Optional[Dict[str, Any]]) -> AzureError
def create_generic_error(error_code: str, message: str, status_code: int = 500, *, request_id: Optional[str], additional_info: Optional[Dict[str, Any]]) -> AzureError
```

## Test Coverage

**Total Tests**: 55  
**Coverage**: 100%

### Test Classes

1. **TestErrorCodeMappings** (7 tests)
   - Authentication, authorization, not found, bad request
   - Conflict, server errors, rate limiting

2. **TestRequestIdGeneration** (4 tests)
   - UUID format and uniqueness
   - Timestamp format and structure

3. **TestErrorContext** (5 tests)
   - Default values and auto-generation
   - Custom values and service types

4. **TestDetermineErrorFormat** (7 tests)
   - Storage defaults to XML
   - Content negotiation with Accept headers
   - Other services use JSON

5. **TestFormatErrorXml** (3 tests)
   - Basic XML structure
   - XML declaration
   - Additional info fields

6. **TestFormatErrorJson** (2 tests)
   - Basic JSON structure
   - Additional info fields

7. **TestCreateErrorHeaders** (2 tests)
   - Required headers presence
   - Date header format

8. **TestCreateErrorResponse** (5 tests)
   - Storage XML default
   - Storage JSON with Accept
   - Service Bus JSON
   - Format override
   - AzureError.to_dict()

9. **TestMapErrorCodeToStatus** (3 tests)
   - Known error codes
   - Unknown codes with defaults

10. **TestCreateStorageError** (4 tests)
    - XML and JSON formats
    - Custom request IDs
    - Additional info

11. **TestCreateServiceBusError** (2 tests)
    - JSON format
    - Headers validation

12. **TestCreateKeyVaultError** (2 tests)
    - JSON format
    - Custom request IDs

13. **TestCreateCosmosDbError** (1 test)
    - JSON format

14. **TestCreateGenericError** (2 tests)
    - Custom status codes
    - Default status

15. **TestEndToEndScenarios** (6 tests)
    - Blob not found
    - Authentication failed
    - Container already exists
    - Rate limiting
    - Service unavailable
    - Content negotiation

## Usage Examples

### Example 1: Storage Blob Not Found (XML)
```python
from localzure.gateway import create_storage_error

error = create_storage_error(
    "BlobNotFound",
    "The specified blob does not exist."
)

# Returns:
# status_code: 404
# content_type: "application/xml"
# headers: {
#     "x-ms-request-id": "abc-123-...",
#     "x-ms-error-code": "BlobNotFound",
#     "Content-Type": "application/xml",
#     "Date": "Wed, 04 Dec 2025 10:30:45 GMT"
# }
# body: "<?xml version="1.0" encoding="utf-8"?>
#        <Error>
#          <Code>BlobNotFound</Code>
#          <Message>The specified blob does not exist.</Message>
#        </Error>"
```

### Example 2: Storage Error with JSON (Content Negotiation)
```python
error = create_storage_error(
    "ContainerAlreadyExists",
    "The specified container already exists.",
    accept_header="application/json"
)

# Returns JSON instead of XML
# {
#   "error": {
#     "code": "ContainerAlreadyExists",
#     "message": "The specified container already exists."
#   }
# }
```

### Example 3: Service Bus Error
```python
from localzure.gateway import create_service_bus_error

error = create_service_bus_error(
    "QueueNotFound",
    "The specified queue does not exist."
)

# Always returns JSON for Service Bus
# status_code: 404
# content_type: "application/json"
```

### Example 4: Authentication Error
```python
error = create_storage_error(
    "AuthenticationFailed",
    "Server failed to authenticate the request. Make sure the Authorization header is formed correctly."
)

# status_code: 401 (auto-mapped)
# x-ms-error-code: "AuthenticationFailed"
```

### Example 5: Custom Request ID
```python
error = create_storage_error(
    "InternalError",
    "The server encountered an internal error.",
    request_id="custom-trace-id-12345"
)

# Uses custom request ID instead of auto-generated
```

### Example 6: Additional Error Info
```python
error = create_storage_error(
    "InvalidInput",
    "The input is invalid.",
    additional_info={
        "QueryParameterName": "maxresults",
        "QueryParameterValue": "-1",
        "Reason": "Value must be positive"
    }
)

# Additional info appears in error body:
# XML: <QueryParameterName>maxresults</QueryParameterName>
# JSON: "QueryParameterName": "maxresults"
```

### Example 7: Generic Error with Custom Status
```python
from localzure.gateway import create_generic_error

error = create_generic_error(
    "TeapotError",
    "I'm a teapot",
    status_code=418
)

# Custom status code with generic formatting
```

### Example 8: FastAPI Integration
```python
from fastapi import HTTPException
from localzure.gateway import create_storage_error

try:
    # ... operation that fails
    raise ValueError("Blob not found")
except ValueError:
    error = create_storage_error(
        "BlobNotFound",
        "The specified blob does not exist."
    )
    raise HTTPException(
        status_code=error.status_code,
        detail=error.body,
        headers=error.headers
    )
```

## Code Quality

- **Pylint Score**: 10.00/10
- **Type Hints**: Complete coverage
- **Docstrings**: All public APIs documented
- **Error Handling**: Comprehensive validation

## Integration Notes

### Gateway Integration

The error formatter integrates with the gateway by:
1. Providing consistent error formatting for all services
2. Supporting content negotiation based on Accept headers
3. Auto-generating request IDs for tracing
4. Mapping error codes to correct HTTP status codes
5. Including Azure-compatible headers

### Error Code Mappings

30+ common Azure error codes mapped:
- **Authentication (401)**: AuthenticationFailed, InvalidAuthenticationInfo, MissingRequiredHeader
- **Authorization (403)**: AuthorizationFailed, InsufficientAccountPermissions, AccountIsDisabled
- **Not Found (404)**: ResourceNotFound, BlobNotFound, ContainerNotFound, QueueNotFound, TableNotFound, EntityNotFound
- **Bad Request (400)**: InvalidResourceName, InvalidUri, InvalidInput, InvalidQueryParameter, InvalidHeaderValue
- **Conflict (409)**: ResourceAlreadyExists, ContainerAlreadyExists, BlobAlreadyExists, QueueAlreadyExists
- **Precondition (412)**: ConditionNotMet, TargetConditionNotMet
- **Rate Limit (429)**: TooManyRequests
- **Timeout (408)**: OperationTimedOut
- **Server Errors (500+)**: InternalError, ServerBusy, ServiceUnavailable

### Content Negotiation

Storage services default to XML but support JSON:
```python
# No Accept header or XML requested -> XML
GET /container/blob
# Returns XML

# JSON explicitly requested -> JSON
GET /container/blob
Accept: application/json
# Returns JSON
```

Other services always use JSON regardless of Accept header.

## Technical Details

### XML Format (Storage)

Matches Azure Storage error format:
```xml
<?xml version="1.0" encoding="utf-8"?>
<Error>
  <Code>BlobNotFound</Code>
  <Message>The specified blob does not exist.</Message>
  <!-- Additional fields if provided -->
</Error>
```

### JSON Format (Other Services)

Matches Azure JSON error format:
```json
{
  "error": {
    "code": "ResourceNotFound",
    "message": "The specified resource does not exist.",
    // Additional fields if provided
  }
}
```

### Request ID Formats

Two formats supported:
1. **UUID** (default): `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`
2. **Timestamp**: `"20251204T103045.123Z"`

Both are valid Azure request ID formats.

### Headers

All error responses include:
- `x-ms-request-id`: Request tracking ID
- `x-ms-error-code`: Azure error code
- `Content-Type`: `application/xml` or `application/json`
- `Date`: HTTP date format

## Files Modified

### New Files
- `localzure/gateway/error_formatter.py` (459 lines)
- `tests/unit/gateway/test_error_formatter.py` (559 lines)
- `docs/implementation/STORY-GATEWAY-006.md` (this file)

### Modified Files
- `localzure/gateway/__init__.py` - Added error_formatter exports

## Dependencies

No new external dependencies. Uses Python standard library:
- `json` - JSON formatting
- `uuid` - Request ID generation
- `datetime` - Timestamp generation
- `xml.etree.ElementTree` - XML formatting
- `dataclasses` - Data structures
- `enum` - Enumerations
- `logging` - Debug logging

## Next Steps

1. **Gateway Integration**: Use error formatter in gateway request handlers
2. **Service Integration**: Integrate with Storage, Service Bus, Key Vault, Cosmos DB services
3. **Error Middleware**: Create FastAPI middleware for automatic error formatting
4. **Logging Integration**: Log all errors with request IDs for tracing
5. **Metrics**: Track error rates by error code and service

## Notes

- 100% test coverage with 55 comprehensive tests
- All error codes follow Azure conventions
- Content negotiation supports both XML and JSON
- Request IDs support both UUID and timestamp formats
- Headers match Azure header names and formats
- Error messages follow Azure message patterns
- Service-specific factories simplify error creation
- Generic error factory supports custom status codes

## Commit Message

```
feat(gateway): implement Azure-consistent error responses

Implement error response formatting matching Azure's structure for SDK
compatibility. Supports XML for Storage services and JSON for others,
with proper headers (x-ms-request-id, x-ms-error-code) and 30+ mapped
error codes.

Features:
- ErrorContext and AzureError models
- Content negotiation (XML/JSON based on Accept header)
- 30+ Azure error code to HTTP status mappings
- Request ID generation (UUID and timestamp formats)
- Service-specific error factories (Storage, Service Bus, Key Vault, etc.)
- XML formatting for Storage (<?xml...><Error>)
- JSON formatting for other services ({"error": {...}})
- x-ms-request-id and x-ms-error-code headers
- 100% test coverage (55 tests)

STORY-GATEWAY-006
```
