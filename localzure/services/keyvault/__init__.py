"""
Azure Key Vault Service Emulator.

Provides local emulation of Azure Key Vault secrets management,
matching Azure Key Vault REST API behavior for development and testing.

Author: LocalZure Team
Date: 2025-12-11
"""

from .backend import KeyVaultBackend
from .models import (
    Secret,
    SecretAttributes,
    SecretBundle,
    SecretItem,
    SecretListResult,
    SetSecretRequest,
    UpdateSecretRequest,
    DeletedSecretBundle,
    DeletedSecretItem,
    DeletedSecretListResult,
)
from .exceptions import (
    KeyVaultError,
    SecretNotFoundError,
    SecretDisabledError,
    SecretAlreadyExistsError,
    InvalidSecretNameError,
    VaultNotFoundError,
)

__all__ = [
    # Backend
    "KeyVaultBackend",
    # Models
    "Secret",
    "SecretAttributes",
    "SecretBundle",
    "SecretItem",
    "SecretListResult",
    "SetSecretRequest",
    "UpdateSecretRequest",
    "DeletedSecretBundle",
    "DeletedSecretItem",
    "DeletedSecretListResult",
    # Exceptions
    "KeyVaultError",
    "SecretNotFoundError",
    "SecretDisabledError",
    "SecretAlreadyExistsError",
    "InvalidSecretNameError",
    "VaultNotFoundError",
]
