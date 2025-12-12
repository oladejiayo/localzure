"""
Key Vault Routes.

FastAPI routes for Azure Key Vault REST API endpoints.
Matches Azure Key Vault API version 7.3 behavior.

Author: LocalZure Team
Date: 2025-12-11
"""

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from fastapi.responses import JSONResponse
from typing import Optional

from .backend import KeyVaultBackend
from .models import (
    SecretBundle,
    SecretListResult,
    SetSecretRequest,
    UpdateSecretRequest,
    DeletedSecretBundle,
    DeletedSecretListResult,
)
from .exceptions import (
    KeyVaultError,
    SecretNotFoundError,
    SecretDisabledError,
    InvalidSecretNameError,
    VaultNotFoundError,
)


# Global backend instance
_backend: Optional[KeyVaultBackend] = None


def get_backend() -> KeyVaultBackend:
    """Get or create Key Vault backend instance.
    
    Returns:
        KeyVaultBackend instance
    """
    global _backend
    if _backend is None:
        _backend = KeyVaultBackend()
    return _backend


def create_router() -> APIRouter:
    """Create FastAPI router for Key Vault endpoints.
    
    Returns:
        Configured APIRouter
    """
    router = APIRouter()
    
    @router.put(
        "/{vault_name}/secrets/{secret_name}",
        response_model=SecretBundle,
        status_code=status.HTTP_200_OK,
        tags=["Secrets"]
    )
    async def set_secret(
        vault_name: str = Path(..., description="Vault name"),
        secret_name: str = Path(..., description="Secret name"),
        request: SetSecretRequest = ...,
        api_version: str = Query("7.3", alias="api-version")
    ) -> SecretBundle:
        """Set (create or update) a secret.
        
        Creates a new version of the secret with the specified value.
        
        Args:
            vault_name: Name of the vault
            secret_name: Name of the secret
            request: Secret value and properties
            api_version: API version
            
        Returns:
            Created secret bundle
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.set_secret(vault_name, secret_name, request)
        except InvalidSecretNameError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except KeyVaultError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.get(
        "/{vault_name}/secrets/{secret_name}/{version}",
        response_model=SecretBundle,
        status_code=status.HTTP_200_OK,
        tags=["Secrets"]
    )
    async def get_secret_version(
        vault_name: str = Path(..., description="Vault name"),
        secret_name: str = Path(..., description="Secret name"),
        version: str = Path(..., description="Secret version"),
        api_version: str = Query("7.3", alias="api-version")
    ) -> SecretBundle:
        """Get a specific version of a secret.
        
        Args:
            vault_name: Name of the vault
            secret_name: Name of the secret
            version: Version ID
            api_version: API version
            
        Returns:
            Secret bundle with value
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.get_secret(vault_name, secret_name, version)
        except SecretNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except SecretDisabledError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.get(
        "/{vault_name}/secrets/{secret_name}",
        response_model=SecretBundle,
        status_code=status.HTTP_200_OK,
        tags=["Secrets"]
    )
    async def get_secret(
        vault_name: str = Path(..., description="Vault name"),
        secret_name: str = Path(..., description="Secret name"),
        api_version: str = Query("7.3", alias="api-version")
    ) -> SecretBundle:
        """Get the latest version of a secret.
        
        Args:
            vault_name: Name of the vault
            secret_name: Name of the secret
            api_version: API version
            
        Returns:
            Secret bundle with value
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.get_secret(vault_name, secret_name)
        except SecretNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except SecretDisabledError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.get(
        "/{vault_name}/secrets",
        response_model=SecretListResult,
        status_code=status.HTTP_200_OK,
        tags=["Secrets"]
    )
    async def list_secrets(
        vault_name: str = Path(..., description="Vault name"),
        maxresults: Optional[int] = Query(None, description="Maximum results"),
        api_version: str = Query("7.3", alias="api-version")
    ) -> SecretListResult:
        """List all secrets in the vault (identifiers only).
        
        Args:
            vault_name: Name of the vault
            maxresults: Maximum number of results
            api_version: API version
            
        Returns:
            List of secret items without values
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.list_secrets(vault_name, maxresults)
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.get(
        "/{vault_name}/secrets/{secret_name}/versions",
        response_model=SecretListResult,
        status_code=status.HTTP_200_OK,
        tags=["Secrets"]
    )
    async def list_secret_versions(
        vault_name: str = Path(..., description="Vault name"),
        secret_name: str = Path(..., description="Secret name"),
        maxresults: Optional[int] = Query(None, description="Maximum results"),
        api_version: str = Query("7.3", alias="api-version")
    ) -> SecretListResult:
        """List all versions of a secret.
        
        Args:
            vault_name: Name of the vault
            secret_name: Name of the secret
            maxresults: Maximum number of results
            api_version: API version
            
        Returns:
            List of secret version items without values
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.list_secret_versions(vault_name, secret_name, maxresults)
        except SecretNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.delete(
        "/{vault_name}/secrets/{secret_name}",
        response_model=DeletedSecretBundle,
        status_code=status.HTTP_200_OK,
        tags=["Secrets"]
    )
    async def delete_secret(
        vault_name: str = Path(..., description="Vault name"),
        secret_name: str = Path(..., description="Secret name"),
        api_version: str = Query("7.3", alias="api-version")
    ) -> DeletedSecretBundle:
        """Delete a secret (soft-delete if enabled).
        
        Args:
            vault_name: Name of the vault
            secret_name: Name of the secret
            api_version: API version
            
        Returns:
            Deleted secret bundle with recovery info
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.delete_secret(vault_name, secret_name)
        except SecretNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.patch(
        "/{vault_name}/secrets/{secret_name}/{version}",
        response_model=SecretBundle,
        status_code=status.HTTP_200_OK,
        tags=["Secrets"]
    )
    async def update_secret_properties(
        vault_name: str = Path(..., description="Vault name"),
        secret_name: str = Path(..., description="Secret name"),
        version: str = Path(..., description="Secret version"),
        request: UpdateSecretRequest = ...,
        api_version: str = Query("7.3", alias="api-version")
    ) -> SecretBundle:
        """Update secret properties without changing value.
        
        Args:
            vault_name: Name of the vault
            secret_name: Name of the secret
            version: Version ID
            request: Updated properties
            api_version: API version
            
        Returns:
            Updated secret bundle
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.update_secret_properties(
                vault_name, secret_name, version, request
            )
        except SecretNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.get(
        "/{vault_name}/deletedsecrets/{secret_name}",
        response_model=DeletedSecretBundle,
        status_code=status.HTTP_200_OK,
        tags=["Deleted Secrets"]
    )
    async def get_deleted_secret(
        vault_name: str = Path(..., description="Vault name"),
        secret_name: str = Path(..., description="Secret name"),
        api_version: str = Query("7.3", alias="api-version")
    ) -> DeletedSecretBundle:
        """Get a soft-deleted secret.
        
        Args:
            vault_name: Name of the vault
            secret_name: Name of the secret
            api_version: API version
            
        Returns:
            Deleted secret bundle with recovery information
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.get_deleted_secret(vault_name, secret_name)
        except SecretNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.get(
        "/{vault_name}/deletedsecrets",
        response_model=DeletedSecretListResult,
        status_code=status.HTTP_200_OK,
        tags=["Deleted Secrets"]
    )
    async def list_deleted_secrets(
        vault_name: str = Path(..., description="Vault name"),
        maxresults: Optional[int] = Query(None, description="Maximum results"),
        api_version: str = Query("7.3", alias="api-version")
    ) -> DeletedSecretListResult:
        """List all soft-deleted secrets in the vault.
        
        Args:
            vault_name: Name of the vault
            maxresults: Maximum number of results
            api_version: API version
            
        Returns:
            List of deleted secret items
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.list_deleted_secrets(vault_name, maxresults)
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.post(
        "/{vault_name}/deletedsecrets/{secret_name}/recover",
        response_model=SecretBundle,
        status_code=status.HTTP_200_OK,
        tags=["Deleted Secrets"]
    )
    async def recover_deleted_secret(
        vault_name: str = Path(..., description="Vault name"),
        secret_name: str = Path(..., description="Secret name"),
        api_version: str = Query("7.3", alias="api-version")
    ) -> SecretBundle:
        """Recover a soft-deleted secret.
        
        Args:
            vault_name: Name of the vault
            secret_name: Name of the secret
            api_version: API version
            
        Returns:
            Recovered secret bundle
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            return await backend.recover_deleted_secret(vault_name, secret_name)
        except SecretNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.delete(
        "/{vault_name}/deletedsecrets/{secret_name}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Deleted Secrets"]
    )
    async def purge_deleted_secret(
        vault_name: str = Path(..., description="Vault name"),
        secret_name: str = Path(..., description="Secret name"),
        api_version: str = Query("7.3", alias="api-version")
    ) -> None:
        """Permanently purge a soft-deleted secret.
        
        Args:
            vault_name: Name of the vault
            secret_name: Name of the secret
            api_version: API version
            
        Returns:
            No content
            
        Raises:
            HTTPException: On error
        """
        backend = get_backend()
        try:
            await backend.purge_deleted_secret(vault_name, secret_name)
        except SecretNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
        except VaultNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.error_code,
                        "message": e.message
                    }
                }
            )
    
    @router.get(
        "/_health",
        status_code=status.HTTP_200_OK,
        tags=["Health"]
    )
    async def health() -> dict:
        """Health check endpoint.
        
        Returns:
            Health status
        """
        backend = get_backend()
        return await backend.health()
    
    @router.post(
        "/_reset",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Testing"]
    )
    async def reset() -> None:
        """Reset all data (testing only).
        
        Returns:
            No content
        """
        backend = get_backend()
        await backend.reset()
    
    return router
