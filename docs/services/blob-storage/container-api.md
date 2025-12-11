# Blob Storage Container API

**Version:** 1.0.0  
**Status:** Implemented  
**Azure API Version:** 2021-08-06

## Overview

LocalZure Blob Storage emulates Azure Blob Storage container operations. Containers are logical groupings for blobs, similar to directories in a file system.

## Authentication

Currently supported authentication methods:
- None (local emulator mode)

**Planned:**
- Shared Key authentication
- Shared Access Signature (SAS)
- Azure AD tokens

## Container Operations

### Create Container

Create a new container with the specified name.

**Request:**
```http
PUT /{account}/{container} HTTP/1.1
Host: 127.0.0.1:8080
x-ms-blob-public-access: {private|blob|container}
x-ms-meta-{key}: {value}
```

**Parameters:**
- `account` (path): Storage account name
- `container` (path): Container name (3-63 chars, lowercase, alphanumeric, hyphens)

**Headers:**
- `x-ms-blob-public-access` (optional): Public access level
  - `private`: No public access (default)
  - `blob`: Public read access for blobs only
  - `container`: Public read access for container and blobs
- `x-ms-meta-{key}` (optional): Custom metadata key-value pairs

**Response (201 Created):**
```http
HTTP/1.1 201 Created
ETag: "0x8D9A1B2C3D4E5F6"
Last-Modified: Wed, 04 Dec 2024 10:30:00 GMT
x-ms-request-id: localzure-request-id
x-ms-version: 2021-08-06
x-ms-lease-status: unlocked
x-ms-lease-state: available
```

**Error Responses:**
- `400 Bad Request`: Invalid container name
  ```json
  {
    "error": {
      "code": "InvalidContainerName",
      "message": "Container name must be at least 3 characters"
    }
  }
  ```
- `409 Conflict`: Container already exists
  ```json
  {
    "error": {
      "code": "ContainerAlreadyExists",
      "message": "The specified container already exists."
    }
  }
  ```

**Example:**
```bash
curl -X PUT http://127.0.0.1:8080/blob/devstoreaccount1/mycontainer \
  -H "x-ms-blob-public-access: private" \
  -H "x-ms-meta-environment: development" \
  -H "x-ms-meta-owner: team-alpha"
```

---

### List Containers

List all containers in a storage account.

**Request:**
```http
GET /{account}?prefix={prefix}&maxresults={count} HTTP/1.1
Host: 127.0.0.1:8080
```

**Parameters:**
- `account` (path): Storage account name
- `prefix` (query, optional): Filter containers by name prefix
- `maxresults` (query, optional): Maximum number of results to return

**Response (200 OK):**
```json
{
  "ServiceEndpoint": "https://devstoreaccount1.blob.core.windows.net/",
  "Prefix": "my",
  "MaxResults": 100,
  "Containers": [
    {
      "Name": "mycontainer",
      "Properties": {
        "Etag": "0x8D9A1B2C3D4E5F6",
        "Last-Modified": "2024-12-04T10:30:00Z",
        "LeaseStatus": "unlocked",
        "LeaseState": "available",
        "PublicAccess": "private"
      },
      "Metadata": {
        "environment": "development",
        "owner": "team-alpha"
      }
    }
  ]
}
```

**Example:**
```bash
# List all containers
curl http://127.0.0.1:8080/blob/devstoreaccount1

# List with prefix
curl http://127.0.0.1:8080/blob/devstoreaccount1?prefix=test-

# List with max results
curl http://127.0.0.1:8080/blob/devstoreaccount1?maxresults=10
```

---

### Get Container Properties

Get properties and metadata for a container.

**Request:**
```http
GET /{account}/{container} HTTP/1.1
Host: 127.0.0.1:8080
```

**Parameters:**
- `account` (path): Storage account name
- `container` (path): Container name

**Response (200 OK):**
```http
HTTP/1.1 200 OK
ETag: "0x8D9A1B2C3D4E5F6"
Last-Modified: Wed, 04 Dec 2024 10:30:00 GMT
x-ms-request-id: localzure-request-id
x-ms-version: 2021-08-06
x-ms-lease-status: unlocked
x-ms-lease-state: available
x-ms-blob-public-access: private
x-ms-has-immutability-policy: false
x-ms-has-legal-hold: false
x-ms-meta-environment: development
x-ms-meta-owner: team-alpha
```

**Error Responses:**
- `404 Not Found`: Container does not exist
  ```json
  {
    "error": {
      "code": "ContainerNotFound",
      "message": "The specified container does not exist."
    }
  }
  ```

**Example:**
```bash
curl http://127.0.0.1:8080/blob/devstoreaccount1/mycontainer -I
```

---

### Set Container Metadata

Update or replace container metadata.

**Request:**
```http
PUT /{account}/{container}/metadata HTTP/1.1
Host: 127.0.0.1:8080
x-ms-meta-{key}: {value}
```

**Parameters:**
- `account` (path): Storage account name
- `container` (path): Container name

**Headers:**
- `x-ms-meta-{key}`: Metadata key-value pairs (replaces all existing metadata)

**Response (200 OK):**
```http
HTTP/1.1 200 OK
ETag: "0x8D9A1B2C3D4E5F7"
Last-Modified: Wed, 04 Dec 2024 10:35:00 GMT
x-ms-request-id: localzure-request-id
x-ms-version: 2021-08-06
```

**Error Responses:**
- `404 Not Found`: Container does not exist

**Notes:**
- Setting metadata replaces all existing metadata
- To remove all metadata, send request with no `x-ms-meta-*` headers
- Metadata keys are case-insensitive and stored in lowercase
- ETag and Last-Modified are updated on metadata changes

**Example:**
```bash
curl -X PUT http://127.0.0.1:8080/blob/devstoreaccount1/mycontainer/metadata \
  -H "x-ms-meta-updated: true" \
  -H "x-ms-meta-version: 2.0"
```

---

### Delete Container

Delete a container and all its blobs.

**Request:**
```http
DELETE /{account}/{container} HTTP/1.1
Host: 127.0.0.1:8080
```

**Parameters:**
- `account` (path): Storage account name
- `container` (path): Container name

**Response (202 Accepted):**
```http
HTTP/1.1 202 Accepted
x-ms-request-id: localzure-request-id
x-ms-version: 2021-08-06
```

**Error Responses:**
- `404 Not Found`: Container does not exist

**Notes:**
- Deletion is immediate in LocalZure (no soft delete)
- All blobs in the container are deleted
- Cannot be undone

**Example:**
```bash
curl -X DELETE http://127.0.0.1:8080/blob/devstoreaccount1/mycontainer
```

---

## Container Naming Rules

Container names must follow these rules:

1. **Length:** 3-63 characters
2. **Characters:** Lowercase letters (a-z), numbers (0-9), hyphens (-) only
3. **Start/End:** Must start and end with a letter or number
4. **Hyphens:** No consecutive hyphens (--)

**Valid Examples:**
- `mycontainer`
- `test-container-123`
- `data-2024`
- `abc`

**Invalid Examples:**
- `MyContainer` (uppercase)
- `ab` (too short)
- `-test` (starts with hyphen)
- `test-` (ends with hyphen)
- `test--container` (consecutive hyphens)
- `test_container` (underscore)

---

## Container Metadata

Metadata consists of name-value pairs that you specify for a container.

**Rules:**
- Keys are prefixed with `x-ms-meta-` in HTTP headers
- Keys are case-insensitive (stored as lowercase)
- Values are strings
- Total size limit: 8 KB per container (Azure spec, not enforced in LocalZure)

**Example:**
```http
x-ms-meta-environment: production
x-ms-meta-owner: data-team
x-ms-meta-created-by: deployment-pipeline
```

**Accessing in API:**
```json
{
  "Metadata": {
    "environment": "production",
    "owner": "data-team",
    "created-by": "deployment-pipeline"
  }
}
```

---

## Container Properties

Properties are system-defined metadata that cannot be modified directly.

| Property | Type | Description |
|----------|------|-------------|
| `ETag` | string | Unique identifier, updated on changes |
| `Last-Modified` | datetime | Last modification timestamp |
| `LeaseStatus` | enum | locked \| unlocked |
| `LeaseState` | enum | available \| leased \| expired \| breaking \| broken |
| `PublicAccess` | enum | private \| blob \| container |
| `HasImmutabilityPolicy` | boolean | Whether immutability policy exists |
| `HasLegalHold` | boolean | Whether legal hold is active |

---

## Public Access Levels

| Level | Description | Blob Access | Container Metadata Access |
|-------|-------------|-------------|---------------------------|
| `private` | No public access (default) | ❌ | ❌ |
| `blob` | Public read for blobs only | ✅ | ❌ |
| `container` | Public read for container and blobs | ✅ | ✅ |

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `ContainerAlreadyExists` | 409 | Container name already in use |
| `ContainerNotFound` | 404 | Container does not exist |
| `InvalidContainerName` | 400 | Name violates Azure rules |
| `InvalidHeaderValue` | 400 | Invalid header value provided |

---

## Testing Endpoint

LocalZure provides a testing endpoint not present in Azure:

**Reset Backend:**
```http
POST /blob/reset HTTP/1.1
Host: 127.0.0.1:8080
```

**Response (200 OK):**
```json
{
  "message": "Backend reset successfully"
}
```

**Use Case:** Clear all containers between tests.

---

## Differences from Azure

LocalZure aims for high compatibility but has some differences:

| Feature | Azure | LocalZure |
|---------|-------|-----------|
| Authentication | Required | Optional (local mode) |
| Soft Delete | Supported | Not implemented |
| CORS | Configurable | Not implemented |
| Leases | Supported | Planned |
| Snapshots | Supported | Planned |
| Immutability | Supported | Not implemented |
| Legal Hold | Supported | Not implemented |
| Size Limits | Enforced | Not enforced |

---

## Next Steps

- Implement blob operations (upload, download, list, delete)
- Add lease support
- Implement Shared Key authentication
- Add SAS token validation
- Support CORS configuration

---

**Author:** Ayodele Oladeji  
**Date:** December 4, 2025
