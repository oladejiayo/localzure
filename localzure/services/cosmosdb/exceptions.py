"""
Cosmos DB Exceptions.

Custom exception classes for Cosmos DB operations,
matching Azure Cosmos DB error codes and messages.

Author: LocalZure Team
Date: 2025-12-11
"""


class CosmosDBError(Exception):
    """Base exception for Cosmos DB errors.
    
    Attributes:
        message: Error message
        error_code: Azure Cosmos DB error code
    """
    
    def __init__(self, message: str, error_code: str = "InternalServerError"):
        """Initialize Cosmos DB error.
        
        Args:
            message: Error message
            error_code: Azure error code
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class DatabaseNotFoundError(CosmosDBError):
    """Database not found error."""
    
    def __init__(self, message: str, database_id: str = ""):
        """Initialize database not found error.
        
        Args:
            message: Error message
            database_id: Database identifier
        """
        super().__init__(message, "NotFound")
        self.database_id = database_id


class DatabaseAlreadyExistsError(CosmosDBError):
    """Database already exists error."""
    
    def __init__(self, message: str, database_id: str = ""):
        """Initialize database already exists error.
        
        Args:
            message: Error message
            database_id: Database identifier
        """
        super().__init__(message, "Conflict")
        self.database_id = database_id


class ContainerNotFoundError(CosmosDBError):
    """Container not found error."""
    
    def __init__(self, message: str, container_id: str = "", database_id: str = ""):
        """Initialize container not found error.
        
        Args:
            message: Error message
            container_id: Container identifier
            database_id: Database identifier
        """
        super().__init__(message, "NotFound")
        self.container_id = container_id
        self.database_id = database_id


class ContainerAlreadyExistsError(CosmosDBError):
    """Container already exists error."""
    
    def __init__(self, message: str, container_id: str = "", database_id: str = ""):
        """Initialize container already exists error.
        
        Args:
            message: Error message
            container_id: Container identifier
            database_id: Database identifier
        """
        super().__init__(message, "Conflict")
        self.container_id = container_id
        self.database_id = database_id


class InvalidPartitionKeyError(CosmosDBError):
    """Invalid partition key error."""
    
    def __init__(self, message: str, partition_key_path: str = ""):
        """Initialize invalid partition key error.
        
        Args:
            message: Error message
            partition_key_path: Invalid partition key path
        """
        super().__init__(message, "BadRequest")
        self.partition_key_path = partition_key_path


class BadRequestError(CosmosDBError):
    """Bad request error."""
    
    def __init__(self, message: str):
        """Initialize bad request error.
        
        Args:
            message: Error message
        """
        super().__init__(message, "BadRequest")


class DocumentNotFoundError(CosmosDBError):
    """Document not found error."""
    
    def __init__(self, message: str, document_id: str = "", partition_key: str = ""):
        """Initialize document not found error.
        
        Args:
            message: Error message
            document_id: Document identifier
            partition_key: Partition key value
        """
        super().__init__(message, "NotFound")
        self.document_id = document_id
        self.partition_key = partition_key


class DocumentAlreadyExistsError(CosmosDBError):
    """Document already exists error."""
    
    def __init__(self, message: str, document_id: str = "", partition_key: str = ""):
        """Initialize document already exists error.
        
        Args:
            message: Error message
            document_id: Document identifier
            partition_key: Partition key value
        """
        super().__init__(message, "Conflict")
        self.document_id = document_id
        self.partition_key = partition_key


class PreconditionFailedError(CosmosDBError):
    """Precondition failed error (ETag mismatch)."""
    
    def __init__(self, message: str, etag: str = ""):
        """Initialize precondition failed error.
        
        Args:
            message: Error message
            etag: Expected ETag value
        """
        super().__init__(message, "PreconditionFailed")
        self.etag = etag
        super().__init__(message, "BadRequest")
