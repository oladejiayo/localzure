"""
Key Vault Models.

Pydantic models for Azure Key Vault secrets, matching Azure SDK data structures.

Author: LocalZure Team
Date: 2025-12-11
"""

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SecretAttributes(BaseModel):
    """Secret attributes matching Azure Key Vault SecretAttributes.
    
    Attributes:
        enabled: Whether the secret is enabled
        not_before: Activation date (not valid before this time)
        expires: Expiration date
        created: Creation timestamp
        updated: Last update timestamp
        recovery_level: Recovery level for soft-delete
    """
    
    enabled: bool = True
    not_before: Optional[datetime] = Field(default=None, alias="nbf")
    expires: Optional[datetime] = Field(default=None, alias="exp")
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    recovery_level: Optional[str] = Field(default="Recoverable+Purgeable", alias="recoveryLevel")
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "enabled": True,
                "nbf": 1639094400,
                "exp": 1670630400,
                "created": 1639094400,
                "updated": 1639094400,
                "recoveryLevel": "Recoverable+Purgeable"
            }
        }
    )

class SecretBundle(BaseModel):
    """Complete secret bundle with value and metadata.
    
    Matches Azure Key Vault SecretBundle structure.
    
    Attributes:
        id: Full secret identifier URL
        value: Secret value (plaintext or base64)
        content_type: MIME type hint
        attributes: Secret attributes
        tags: User-defined tags
        kid: Key identifier (if secret is a password for a key)
        managed: Whether secret is managed by Azure service
    """
    
    id: str
    value: str
    content_type: Optional[str] = Field(default=None, alias="contentType")
    attributes: SecretAttributes
    tags: Optional[Dict[str, str]] = None
    kid: Optional[str] = None
    managed: bool = False
    
    model_config = ConfigDict(populate_by_name=True)


class SecretItem(BaseModel):
    """Secret identifier without value (for list operations).
    
    Matches Azure Key Vault SecretItem structure.
    
    Attributes:
        id: Full secret identifier URL
        content_type: MIME type hint
        attributes: Secret attributes
        tags: User-defined tags
        managed: Whether secret is managed by Azure service
    """
    
    id: str
    content_type: Optional[str] = Field(default=None, alias="contentType")
    attributes: SecretAttributes
    tags: Optional[Dict[str, str]] = None
    managed: bool = False
    
    model_config = ConfigDict(populate_by_name=True)


class SecretListResult(BaseModel):
    """Paginated list of secrets.
    
    Attributes:
        value: List of secret items
        next_link: URL for next page of results
    """
    value: List[SecretItem]
    next_link: Optional[str] = Field(default=None, alias="nextLink")
    
    model_config = ConfigDict(populate_by_name=True)


class SetSecretRequest(BaseModel):
    """Request to set (create/update) a secret.
    
    Attributes:
        value: Secret value
        content_type: MIME type hint
        attributes: Secret attributes
        tags: User-defined tags
    """
    
    value: str
    content_type: Optional[str] = Field(default=None, alias="contentType")
    attributes: Optional[SecretAttributes] = None
    tags: Optional[Dict[str, str]] = None
    
    model_config = ConfigDict(populate_by_name=True)


class UpdateSecretRequest(BaseModel):
    """Request to update secret properties (not value).
    
    Attributes:
        content_type: MIME type hint
        attributes: Secret attributes
        tags: User-defined tags
    """
    content_type: Optional[str] = Field(default=None, alias="contentType")
    attributes: Optional[SecretAttributes] = None
    tags: Optional[Dict[str, str]] = None
    
    model_config = ConfigDict(populate_by_name=True)


class Secret(BaseModel):
    """Internal secret storage model.
    
    Represents a secret with all its versions.
    
    Attributes:
        name: Secret name
        versions: Dictionary mapping version ID to SecretBundle
        current_version: Current version ID
        deleted: Whether secret is soft-deleted
        deleted_date: Deletion timestamp
        recovery_id: Recovery identifier for deleted secret
    """
    
    name: str
    versions: Dict[str, SecretBundle] = Field(default_factory=dict)
    current_version: Optional[str] = None
    deleted: bool = False
    deleted_date: Optional[datetime] = None
    recovery_id: Optional[str] = None
    
    @field_validator("name")
    @classmethod
    def validate_secret_name(cls, v: str) -> str:
        """Validate secret name follows Azure rules.
        
        Rules:
        - 1-127 characters
        - Alphanumeric and hyphens only
        - Must start with letter
        - Must not end with hyphen
        
        Args:
            v: Secret name
            
        Returns:
            Validated secret name
            
        Raises:
            ValueError: If name is invalid
        """
        if not v:
            raise ValueError("Secret name cannot be empty")
        
        if len(v) > 127:
            raise ValueError("Secret name must be 127 characters or less")
        
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9-]*[a-zA-Z0-9]$", v):
            raise ValueError(
                "Secret name must start with a letter, "
                "contain only alphanumeric characters and hyphens, "
                "and not end with a hyphen"
            )
        
        return v


class DeletedSecretBundle(BaseModel):
    """Deleted secret with recovery information.
    
    Attributes:
        id: Full secret identifier URL
        recovery_id: Recovery identifier
        scheduled_purge_date: When secret will be purged
        deleted_date: When secret was deleted
        value: Secret value (if retrieving deleted secret)
        content_type: MIME type hint
        attributes: Secret attributes
        tags: User-defined tags
    """
    
    id: str
    recovery_id: str = Field(alias="recoveryId")
    scheduled_purge_date: Optional[datetime] = Field(default=None, alias="scheduledPurgeDate")
    deleted_date: Optional[datetime] = Field(default=None, alias="deletedDate")
    value: Optional[str] = None
    content_type: Optional[str] = Field(default=None, alias="contentType")
    attributes: Optional[SecretAttributes] = None
    tags: Optional[Dict[str, str]] = None
    
    model_config = ConfigDict(populate_by_name=True)


class DeletedSecretItem(BaseModel):
    """Deleted secret identifier without value (for list operations).
    
    Attributes:
        id: Full secret identifier URL
        recovery_id: Recovery identifier
        scheduled_purge_date: When secret will be purged
        deleted_date: When secret was deleted
        content_type: MIME type hint
        attributes: Secret attributes
        tags: User-defined tags
    """
    
    id: str
    recovery_id: str = Field(alias="recoveryId")
    scheduled_purge_date: Optional[datetime] = Field(default=None, alias="scheduledPurgeDate")
    deleted_date: Optional[datetime] = Field(default=None, alias="deletedDate")
    content_type: Optional[str] = Field(default=None, alias="contentType")
    attributes: Optional[SecretAttributes] = None
    tags: Optional[Dict[str, str]] = None
    
    model_config = ConfigDict(populate_by_name=True)


class DeletedSecretListResult(BaseModel):
    """Paginated list of deleted secrets.
    
    Attributes:
        value: List of deleted secret items
        next_link: URL for next page of results
    """
    value: List[DeletedSecretItem]
    next_link: Optional[str] = Field(default=None, alias="nextLink")
    
    model_config = ConfigDict(populate_by_name=True)
