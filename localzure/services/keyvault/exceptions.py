"""
Key Vault Exceptions.

Azure-consistent exception types for Key Vault operations.

Author: LocalZure Team
Date: 2025-12-11
"""


class KeyVaultError(Exception):
    """Base exception for Key Vault errors."""
    
    def __init__(self, message: str, error_code: str = "InternalError"):
        """Initialize Key Vault error.
        
        Args:
            message: Error message
            error_code: Azure error code
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class SecretNotFoundError(KeyVaultError):
    """Raised when a secret is not found."""
    
    def __init__(self, secret_name: str, version: str = None):
        """Initialize secret not found error.
        
        Args:
            secret_name: Name of the secret
            version: Version of the secret (optional)
        """
        if version:
            message = f"Secret '{secret_name}' version '{version}' not found"
        else:
            message = f"Secret '{secret_name}' not found"
        super().__init__(message, error_code="SecretNotFound")
        self.secret_name = secret_name
        self.version = version


class SecretDisabledError(KeyVaultError):
    """Raised when attempting to access a disabled secret."""
    
    def __init__(self, secret_name: str):
        """Initialize secret disabled error.
        
        Args:
            secret_name: Name of the disabled secret
        """
        message = f"Secret '{secret_name}' is disabled"
        super().__init__(message, error_code="SecretDisabled")
        self.secret_name = secret_name


class SecretAlreadyExistsError(KeyVaultError):
    """Raised when attempting to create a secret that already exists."""
    
    def __init__(self, secret_name: str):
        """Initialize secret already exists error.
        
        Args:
            secret_name: Name of the secret
        """
        message = f"Secret '{secret_name}' already exists"
        super().__init__(message, error_code="Conflict")
        self.secret_name = secret_name


class InvalidSecretNameError(KeyVaultError):
    """Raised when a secret name is invalid."""
    
    def __init__(self, secret_name: str, reason: str):
        """Initialize invalid secret name error.
        
        Args:
            secret_name: Invalid secret name
            reason: Reason why the name is invalid
        """
        message = f"Invalid secret name '{secret_name}': {reason}"
        super().__init__(message, error_code="BadParameter")
        self.secret_name = secret_name
        self.reason = reason


class VaultNotFoundError(KeyVaultError):
    """Raised when a vault is not found."""
    
    def __init__(self, vault_name: str):
        """Initialize vault not found error.
        
        Args:
            vault_name: Name of the vault
        """
        message = f"Vault '{vault_name}' not found"
        super().__init__(message, error_code="VaultNotFound")
        self.vault_name = vault_name


class ForbiddenError(KeyVaultError):
    """Raised when access is forbidden."""
    
    def __init__(self, message: str = "Access forbidden"):
        """Initialize forbidden error.
        
        Args:
            message: Error message
        """
        super().__init__(message, error_code="Forbidden")
