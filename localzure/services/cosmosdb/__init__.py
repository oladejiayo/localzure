"""
Azure Cosmos DB Service Emulator.

Provides local emulation of Azure Cosmos DB SQL API,
matching Azure Cosmos DB REST API behavior for development and testing.

Author: LocalZure Team
Date: 2025-12-11
"""

from .backend import CosmosDBBackend
from .models import (
    Database,
    Container,
    PartitionKeyDefinition,
    PartitionKeyPath,
    CreateDatabaseRequest,
    CreateContainerRequest,
    DatabaseListResult,
    ContainerListResult,
    Document,
    CreateDocumentRequest,
    ReplaceDocumentRequest,
    PatchOperation,
    PatchDocumentRequest,
    DocumentListResult,
    QueryRequest,
    QueryResult,
)
from .exceptions import (
    CosmosDBError,
    DatabaseNotFoundError,
    DatabaseAlreadyExistsError,
    ContainerNotFoundError,
    ContainerAlreadyExistsError,
    InvalidPartitionKeyError,
    BadRequestError,
    DocumentNotFoundError,
    DocumentAlreadyExistsError,
    PreconditionFailedError,
)

__all__ = [
    # Backend
    "CosmosDBBackend",
    # Models - Database & Container
    "Database",
    "Container",
    "PartitionKeyDefinition",
    "PartitionKeyPath",
    "CreateDatabaseRequest",
    "CreateContainerRequest",
    "DatabaseListResult",
    "ContainerListResult",
    # Models - Document
    "Document",
    "CreateDocumentRequest",
    "ReplaceDocumentRequest",
    "PatchOperation",
    "PatchDocumentRequest",
    "DocumentListResult",
    # Models - Query
    "QueryRequest",
    "QueryResult",
    # Exceptions - Database & Container
    "CosmosDBError",
    "DatabaseNotFoundError",
    "DatabaseAlreadyExistsError",
    "ContainerNotFoundError",
    "ContainerAlreadyExistsError",
    "InvalidPartitionKeyError",
    "BadRequestError",
    # Exceptions - Document
    "DocumentNotFoundError",
    "DocumentAlreadyExistsError",
    "PreconditionFailedError",
]
