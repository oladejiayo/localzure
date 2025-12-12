"""
Key Vault Backend.

Backend implementation for Azure Key Vault secret operations.
Provides in-memory storage and operations for secrets with versioning,
soft-delete, and Azure-compatible behavior.

Author: LocalZure Team
Date: 2025-12-11
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from .models import (
    Secret,
    SecretAttributes,
    SecretBundle,
    SecretItem,
    SecretListResult,
    SetSecretRequest,
    UpdateSecretRequest,
    DeletedSecretBundle,
)
from .exceptions import (
    KeyVaultError,
    SecretNotFoundError,
    SecretDisabledError,
    InvalidSecretNameError,
    VaultNotFoundError,
)


class KeyVaultBackend:
    """
    Backend for Key Vault secret operations.
    
    Manages secrets in memory with full versioning support,
    providing Azure-compatible CRUD operations.
    
    Attributes:
        _vaults: Dictionary mapping vault names to secret storage
        _deleted_secrets: Dictionary mapping vault names to deleted secrets
        _lock: Asyncio lock for thread-safe operations
        _soft_delete_enabled: Whether soft-delete is enabled
        _retention_days: Retention period for deleted secrets
    """
    
    def __init__(
        self,
        soft_delete_enabled: bool = True,
        retention_days: int = 90
    ):
        """Initialize the Key Vault backend.
        
        Args:
            soft_delete_enabled: Enable soft-delete for secrets
            retention_days: Retention period for deleted secrets (7-90 days)
        """
        # Vault storage: vault_name -> secret_name -> Secret
        self._vaults: Dict[str, Dict[str, Secret]] = {}
        
        # Deleted secrets: vault_name -> secret_name -> Secret
        self._deleted_secrets: Dict[str, Dict[str, Secret]] = {}
        
        self._lock = asyncio.Lock()
        self._soft_delete_enabled = soft_delete_enabled
        self._retention_days = max(7, min(90, retention_days))
    
    def _ensure_vault_exists(self, vault_name: str) -> None:
        """Ensure vault storage exists.
        
        Args:
            vault_name: Name of the vault
        """
        if vault_name not in self._vaults:
            self._vaults[vault_name] = {}
        if vault_name not in self._deleted_secrets:
            self._deleted_secrets[vault_name] = {}
    
    def _generate_secret_id(
        self,
        vault_name: str,
        secret_name: str,
        version: Optional[str] = None
    ) -> str:
        """Generate full secret identifier URL.
        
        Args:
            vault_name: Vault name
            secret_name: Secret name
            version: Secret version (optional)
            
        Returns:
            Full secret URL
        """
        base_url = f"https://{vault_name}.vault.azure.net/secrets/{secret_name}"
        if version:
            return f"{base_url}/{version}"
        return base_url
    
    def _generate_version_id(self, secret_name: str, value: str) -> str:
        """Generate version ID for a secret.
        
        Uses deterministic hash of name + value + timestamp for consistency.
        
        Args:
            secret_name: Secret name
            value: Secret value
            
        Returns:
            Version ID (UUID format)
        """
        # Create deterministic but unique version ID
        content = f"{secret_name}:{value}:{datetime.now(timezone.utc).isoformat()}"
        hash_hex = hashlib.sha256(content.encode()).hexdigest()[:32]
        
        # Format as UUID
        version_uuid = f"{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"
        return version_uuid
    
    def _check_secret_validity(self, bundle: SecretBundle) -> None:
        """Check if secret is valid (enabled and within validity period).
        
        Args:
            bundle: Secret bundle to check
            
        Raises:
            SecretDisabledError: If secret is disabled or invalid
        """
        attrs = bundle.attributes
        now = datetime.now(timezone.utc)
        
        # Check enabled status
        if not attrs.enabled:
            raise SecretDisabledError(bundle.id.split("/")[-2])
        
        # Check not-before date
        if attrs.not_before and now < attrs.not_before.replace(tzinfo=timezone.utc):
            raise SecretDisabledError(bundle.id.split("/")[-2])
        
        # Check expiration date
        if attrs.expires and now > attrs.expires.replace(tzinfo=timezone.utc):
            raise SecretDisabledError(bundle.id.split("/")[-2])
    
    async def set_secret(
        self,
        vault_name: str,
        secret_name: str,
        request: SetSecretRequest
    ) -> SecretBundle:
        """Set (create or update) a secret.
        
        Creates a new version of the secret with the provided value.
        
        Args:
            vault_name: Vault name
            secret_name: Secret name
            request: Secret value and properties
            
        Returns:
            Created secret bundle
            
        Raises:
            InvalidSecretNameError: If secret name is invalid
        """
        async with self._lock:
            self._ensure_vault_exists(vault_name)
            
            # Validate secret name
            try:
                validated_secret = Secret(name=secret_name, versions={})
            except ValueError as e:
                raise InvalidSecretNameError(secret_name, str(e))
            
            # Generate version ID
            version_id = self._generate_version_id(secret_name, request.value)
            
            # Create attributes with timestamps
            now = datetime.now(timezone.utc)
            attributes = request.attributes or SecretAttributes()
            attributes.created = now
            attributes.updated = now
            
            # Create secret bundle
            secret_id = self._generate_secret_id(vault_name, secret_name, version_id)
            bundle = SecretBundle(
                id=secret_id,
                value=request.value,
                content_type=request.content_type,
                attributes=attributes,
                tags=request.tags or {},
            )
            
            # Store secret
            vault = self._vaults[vault_name]
            if secret_name in vault:
                # Update existing secret with new version
                secret = vault[secret_name]
                secret.versions[version_id] = bundle
                secret.current_version = version_id
            else:
                # Create new secret
                secret = Secret(
                    name=secret_name,
                    versions={version_id: bundle},
                    current_version=version_id
                )
                vault[secret_name] = secret
            
            return bundle
    
    async def get_secret(
        self,
        vault_name: str,
        secret_name: str,
        version: Optional[str] = None
    ) -> SecretBundle:
        """Get a secret by name and optional version.
        
        Args:
            vault_name: Vault name
            secret_name: Secret name
            version: Secret version (optional, returns latest if not specified)
            
        Returns:
            Secret bundle with value
            
        Raises:
            VaultNotFoundError: If vault doesn't exist
            SecretNotFoundError: If secret or version not found
            SecretDisabledError: If secret is disabled or expired
        """
        async with self._lock:
            if vault_name not in self._vaults:
                raise VaultNotFoundError(vault_name)
            
            vault = self._vaults[vault_name]
            if secret_name not in vault:
                raise SecretNotFoundError(secret_name)
            
            secret = vault[secret_name]
            
            # Check if secret is deleted
            if secret.deleted:
                raise SecretNotFoundError(secret_name)
            
            # Get specific version or current version
            if version:
                if version not in secret.versions:
                    raise SecretNotFoundError(secret_name, version)
                bundle = secret.versions[version]
            else:
                if not secret.current_version:
                    raise SecretNotFoundError(secret_name)
                bundle = secret.versions[secret.current_version]
            
            # Check validity
            self._check_secret_validity(bundle)
            
            return bundle
    
    async def list_secrets(
        self,
        vault_name: str,
        max_results: Optional[int] = None
    ) -> SecretListResult:
        """List all secrets in a vault (identifiers only, no values).
        
        Args:
            vault_name: Vault name
            max_results: Maximum number of results (optional)
            
        Returns:
            List of secret items without values
            
        Raises:
            VaultNotFoundError: If vault doesn't exist
        """
        async with self._lock:
            if vault_name not in self._vaults:
                raise VaultNotFoundError(vault_name)
            
            vault = self._vaults[vault_name]
            items: List[SecretItem] = []
            
            for secret_name, secret in vault.items():
                # Skip deleted secrets
                if secret.deleted:
                    continue
                
                # Skip if no current version
                if not secret.current_version:
                    continue
                
                # Get current version bundle
                bundle = secret.versions[secret.current_version]
                
                # Create secret item (without value)
                item = SecretItem(
                    id=self._generate_secret_id(vault_name, secret_name),
                    content_type=bundle.content_type,
                    attributes=bundle.attributes,
                    tags=bundle.tags,
                    managed=bundle.managed
                )
                items.append(item)
            
            # Apply max results limit
            if max_results:
                items = items[:max_results]
            
            return SecretListResult(value=items)
    
    async def list_secret_versions(
        self,
        vault_name: str,
        secret_name: str,
        max_results: Optional[int] = None
    ) -> SecretListResult:
        """List all versions of a secret.
        
        Args:
            vault_name: Vault name
            secret_name: Secret name
            max_results: Maximum number of results (optional)
            
        Returns:
            List of secret version items without values
            
        Raises:
            VaultNotFoundError: If vault doesn't exist
            SecretNotFoundError: If secret not found
        """
        async with self._lock:
            if vault_name not in self._vaults:
                raise VaultNotFoundError(vault_name)
            
            vault = self._vaults[vault_name]
            if secret_name not in vault:
                raise SecretNotFoundError(secret_name)
            
            secret = vault[secret_name]
            items: List[SecretItem] = []
            
            # Get all versions sorted by creation time (newest first)
            sorted_versions = sorted(
                secret.versions.items(),
                key=lambda x: x[1].attributes.created,
                reverse=True
            )
            
            for version_id, bundle in sorted_versions:
                item = SecretItem(
                    id=self._generate_secret_id(vault_name, secret_name, version_id),
                    content_type=bundle.content_type,
                    attributes=bundle.attributes,
                    tags=bundle.tags,
                    managed=bundle.managed
                )
                items.append(item)
            
            # Apply max results limit
            if max_results:
                items = items[:max_results]
            
            return SecretListResult(value=items)
    
    async def delete_secret(
        self,
        vault_name: str,
        secret_name: str
    ) -> DeletedSecretBundle:
        """Delete a secret (soft-delete if enabled).
        
        Args:
            vault_name: Vault name
            secret_name: Secret name
            
        Returns:
            Deleted secret bundle with recovery information
            
        Raises:
            VaultNotFoundError: If vault doesn't exist
            SecretNotFoundError: If secret not found
        """
        async with self._lock:
            if vault_name not in self._vaults:
                raise VaultNotFoundError(vault_name)
            
            vault = self._vaults[vault_name]
            if secret_name not in vault:
                raise SecretNotFoundError(secret_name)
            
            secret = vault[secret_name]
            
            # Check if already deleted
            if secret.deleted:
                raise SecretNotFoundError(secret_name)
            
            now = datetime.now(timezone.utc)
            
            if self._soft_delete_enabled:
                # Soft delete
                secret.deleted = True
                secret.deleted_date = now
                secret.recovery_id = f"https://{vault_name}.vault.azure.net/deletedsecrets/{secret_name}"
                
                # Move to deleted secrets
                deleted_vault = self._deleted_secrets[vault_name]
                deleted_vault[secret_name] = secret
                
                # Calculate purge date
                purge_date = now + timedelta(days=self._retention_days)
                
                # Get current version for response
                bundle = secret.versions[secret.current_version]
                
                return DeletedSecretBundle(
                    id=self._generate_secret_id(vault_name, secret_name),
                    recovery_id=secret.recovery_id,
                    scheduled_purge_date=purge_date,
                    deleted_date=now,
                    value=bundle.value,
                    content_type=bundle.content_type,
                    attributes=bundle.attributes,
                    tags=bundle.tags
                )
            else:
                # Hard delete
                del vault[secret_name]
                
                # Return minimal deleted bundle
                bundle = secret.versions[secret.current_version]
                return DeletedSecretBundle(
                    id=self._generate_secret_id(vault_name, secret_name),
                    recovery_id="",
                    deleted_date=now,
                    value=bundle.value,
                    content_type=bundle.content_type,
                    attributes=bundle.attributes,
                    tags=bundle.tags
                )
    
    async def update_secret_properties(
        self,
        vault_name: str,
        secret_name: str,
        version: str,
        request: UpdateSecretRequest
    ) -> SecretBundle:
        """Update secret properties without changing the value.
        
        Args:
            vault_name: Vault name
            secret_name: Secret name
            version: Secret version
            request: Updated properties
            
        Returns:
            Updated secret bundle
            
        Raises:
            VaultNotFoundError: If vault doesn't exist
            SecretNotFoundError: If secret or version not found
        """
        async with self._lock:
            if vault_name not in self._vaults:
                raise VaultNotFoundError(vault_name)
            
            vault = self._vaults[vault_name]
            if secret_name not in vault:
                raise SecretNotFoundError(secret_name)
            
            secret = vault[secret_name]
            
            if version not in secret.versions:
                raise SecretNotFoundError(secret_name, version)
            
            bundle = secret.versions[version]
            
            # Update properties
            if request.content_type is not None:
                bundle.content_type = request.content_type
            
            if request.attributes:
                # Update only provided attributes
                if request.attributes.enabled is not None:
                    bundle.attributes.enabled = request.attributes.enabled
                if request.attributes.not_before is not None:
                    bundle.attributes.not_before = request.attributes.not_before
                if request.attributes.expires is not None:
                    bundle.attributes.expires = request.attributes.expires
            
            if request.tags is not None:
                bundle.tags = request.tags
            
            # Update timestamp
            bundle.attributes.updated = datetime.now(timezone.utc)
            
            return bundle
    
    async def get_deleted_secret(
        self,
        vault_name: str,
        secret_name: str
    ) -> DeletedSecretBundle:
        """Get a soft-deleted secret.
        
        Args:
            vault_name: Vault name
            secret_name: Secret name
            
        Returns:
            Deleted secret bundle with recovery information
            
        Raises:
            VaultNotFoundError: If vault doesn't exist
            SecretNotFoundError: If secret not found in deleted secrets
        """
        async with self._lock:
            if vault_name not in self._deleted_secrets:
                raise SecretNotFoundError(secret_name)
            
            deleted_vault = self._deleted_secrets[vault_name]
            if secret_name not in deleted_vault:
                raise SecretNotFoundError(secret_name)
            
            secret = deleted_vault[secret_name]
            
            # Get current version bundle
            bundle = secret.versions[secret.current_version]
            
            # Calculate purge date
            purge_date = None
            if secret.deleted_date:
                purge_date = secret.deleted_date + timedelta(days=self._retention_days)
            
            return DeletedSecretBundle(
                id=self._generate_secret_id(vault_name, secret_name),
                recovery_id=secret.recovery_id or "",
                scheduled_purge_date=purge_date,
                deleted_date=secret.deleted_date,
                value=bundle.value,
                content_type=bundle.content_type,
                attributes=bundle.attributes,
                tags=bundle.tags
            )
    
    async def list_deleted_secrets(
        self,
        vault_name: str,
        max_results: Optional[int] = None
    ):
        """List all soft-deleted secrets in a vault.
        
        Args:
            vault_name: Vault name
            max_results: Maximum number of results (optional)
            
        Returns:
            List of deleted secret items
            
        Raises:
            VaultNotFoundError: If vault doesn't exist
        """
        from .models import DeletedSecretItem, DeletedSecretListResult
        
        async with self._lock:
            if vault_name not in self._deleted_secrets:
                raise VaultNotFoundError(vault_name)
            
            deleted_vault = self._deleted_secrets[vault_name]
            items = []
            
            for secret_name, secret in deleted_vault.items():
                # Get current version bundle
                bundle = secret.versions[secret.current_version]
                
                # Calculate purge date
                purge_date = None
                if secret.deleted_date:
                    purge_date = secret.deleted_date + timedelta(days=self._retention_days)
                
                # Create deleted secret item
                item = DeletedSecretItem(
                    id=self._generate_secret_id(vault_name, secret_name),
                    recovery_id=secret.recovery_id or "",
                    scheduled_purge_date=purge_date,
                    deleted_date=secret.deleted_date,
                    content_type=bundle.content_type,
                    attributes=bundle.attributes,
                    tags=bundle.tags
                )
                items.append(item)
            
            # Apply max results limit
            if max_results:
                items = items[:max_results]
            
            return DeletedSecretListResult(value=items)
    
    async def recover_deleted_secret(
        self,
        vault_name: str,
        secret_name: str
    ) -> SecretBundle:
        """Recover a soft-deleted secret.
        
        Args:
            vault_name: Vault name
            secret_name: Secret name
            
        Returns:
            Recovered secret bundle
            
        Raises:
            VaultNotFoundError: If vault doesn't exist
            SecretNotFoundError: If secret not found in deleted secrets
        """
        async with self._lock:
            if vault_name not in self._deleted_secrets:
                raise SecretNotFoundError(secret_name)
            
            deleted_vault = self._deleted_secrets[vault_name]
            if secret_name not in deleted_vault:
                raise SecretNotFoundError(secret_name)
            
            secret = deleted_vault[secret_name]
            
            # Restore secret
            secret.deleted = False
            secret.deleted_date = None
            secret.recovery_id = None
            
            # Move back to active secrets
            self._vaults[vault_name][secret_name] = secret
            del deleted_vault[secret_name]
            
            # Return current version
            return secret.versions[secret.current_version]
    
    async def purge_deleted_secret(
        self,
        vault_name: str,
        secret_name: str
    ) -> None:
        """Permanently delete a soft-deleted secret.
        
        Args:
            vault_name: Vault name
            secret_name: Secret name
            
        Raises:
            VaultNotFoundError: If vault doesn't exist
            SecretNotFoundError: If secret not found in deleted secrets
        """
        async with self._lock:
            if vault_name not in self._deleted_secrets:
                raise SecretNotFoundError(secret_name)
            
            deleted_vault = self._deleted_secrets[vault_name]
            if secret_name not in deleted_vault:
                raise SecretNotFoundError(secret_name)
            
            # Permanently delete
            del deleted_vault[secret_name]
    
    async def health(self) -> dict:
        """Check backend health.
        
        Returns:
            Health status dictionary
        """
        async with self._lock:
            total_vaults = len(self._vaults)
            total_secrets = sum(len(v) for v in self._vaults.values())
            total_deleted = sum(len(v) for v in self._deleted_secrets.values())
            
            return {
                "status": "healthy",
                "vaults": total_vaults,
                "secrets": total_secrets,
                "deleted_secrets": total_deleted,
                "soft_delete_enabled": self._soft_delete_enabled,
                "retention_days": self._retention_days
            }
    
    async def reset(self) -> None:
        """Reset all data (for testing)."""
        async with self._lock:
            self._vaults.clear()
            self._deleted_secrets.clear()
