"""
Unit tests for Blob Storage container models.

Tests container name validation, metadata, properties, and model creation.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from datetime import datetime

from localzure.services.blob.models import (
    Container,
    ContainerMetadata,
    ContainerNameValidator,
    ContainerProperties,
    CreateContainerRequest,
    LeaseState,
    LeaseStatus,
    PublicAccessLevel,
    SetContainerMetadataRequest,
)


class TestContainerNameValidator:
    """Test container name validation rules."""
    
    def test_valid_names(self):
        """Test valid container names."""
        valid_names = [
            "abc",
            "test-container",
            "my-container-123",
            "a" * 63,  # Max length
            "123",
            "test123",
        ]
        for name in valid_names:
            is_valid, error = ContainerNameValidator.validate(name)
            assert is_valid, f"Name '{name}' should be valid but got error: {error}"
            assert error is None
    
    def test_invalid_names(self):
        """Test invalid container names."""
        invalid_names = [
            "",  # Empty
            "ab",  # Too short
            "a" * 64,  # Too long
            "TEST",  # Uppercase
            "test_container",  # Underscore
            "-test",  # Starts with hyphen
            "test-",  # Ends with hyphen
            "test--container",  # Consecutive hyphens
            "test container",  # Space
            "test.container",  # Dot
        ]
        for name in invalid_names:
            is_valid, error = ContainerNameValidator.validate(name)
            assert not is_valid, f"Name '{name}' should be invalid"
            assert error is not None
    
    def test_validate_raise_valid(self):
        """Test validate_raise with valid name."""
        ContainerNameValidator.validate_raise("valid-container")  # Should not raise
    
    def test_validate_raise_invalid(self):
        """Test validate_raise with invalid name."""
        with pytest.raises(ValueError):
            ContainerNameValidator.validate_raise("INVALID")


class TestContainerMetadata:
    """Test container metadata model."""
    
    def test_initialization(self):
        """Test metadata initialization."""
        metadata = ContainerMetadata(metadata={"key1": "value1", "key2": "value2"})
        assert metadata.metadata == {"key1": "value1", "key2": "value2"}
    
    def test_empty_metadata(self):
        """Test empty metadata."""
        metadata = ContainerMetadata()
        assert metadata.metadata == {}
    
    def test_lowercase_keys(self):
        """Test that keys are converted to lowercase."""
        metadata = ContainerMetadata(metadata={"KEY1": "value1", "Key2": "value2"})
        assert metadata.metadata == {"key1": "value1", "key2": "value2"}
    
    def test_to_headers(self):
        """Test conversion to HTTP headers."""
        metadata = ContainerMetadata(metadata={"key1": "value1", "key2": "value2"})
        headers = metadata.to_headers()
        assert headers == {
            "x-ms-meta-key1": "value1",
            "x-ms-meta-key2": "value2",
        }
    
    def test_from_headers(self):
        """Test extraction from HTTP headers."""
        headers = {
            "x-ms-meta-key1": "value1",
            "x-ms-meta-key2": "value2",
            "Content-Type": "application/json",  # Should be ignored
        }
        metadata = ContainerMetadata.from_headers(headers)
        assert metadata.metadata == {"key1": "value1", "key2": "value2"}
    
    def test_from_headers_case_insensitive(self):
        """Test header extraction is case-insensitive."""
        headers = {
            "X-MS-META-Key1": "value1",
            "x-ms-meta-key2": "value2",
        }
        metadata = ContainerMetadata.from_headers(headers)
        assert metadata.metadata == {"key1": "value1", "key2": "value2"}


class TestContainerProperties:
    """Test container properties model."""
    
    def test_initialization(self):
        """Test properties initialization."""
        props = ContainerProperties(
            etag="abc123",
            last_modified=datetime(2025, 1, 1, 12, 0, 0),
        )
        assert props.etag == "abc123"
        assert props.last_modified == datetime(2025, 1, 1, 12, 0, 0)
        assert props.lease_status == LeaseStatus.UNLOCKED
        assert props.lease_state == LeaseState.AVAILABLE
        assert props.public_access == PublicAccessLevel.PRIVATE
    
    def test_to_headers(self):
        """Test conversion to HTTP headers."""
        props = ContainerProperties(
            etag="abc123",
            last_modified=datetime(2025, 1, 1, 12, 0, 0),
            lease_status=LeaseStatus.LOCKED,
            lease_state=LeaseState.LEASED,
            public_access=PublicAccessLevel.BLOB,
        )
        headers = props.to_headers()
        assert headers['ETag'] == '"abc123"'
        assert headers['Last-Modified'] == 'Wed, 01 Jan 2025 12:00:00 GMT'
        assert headers['x-ms-lease-status'] == 'locked'
        assert headers['x-ms-lease-state'] == 'leased'
        assert headers['x-ms-blob-public-access'] == 'blob'
        assert headers['x-ms-has-immutability-policy'] == 'false'
        assert headers['x-ms-has-legal-hold'] == 'false'
    
    def test_lease_duration(self):
        """Test lease duration in headers."""
        props = ContainerProperties(
            etag="abc123",
            last_modified=datetime(2025, 1, 1, 12, 0, 0),
            lease_duration="60",
        )
        headers = props.to_headers()
        assert headers['x-ms-lease-duration'] == "60"


class TestContainer:
    """Test container model."""
    
    def test_initialization_valid_name(self):
        """Test container initialization with valid name."""
        props = ContainerProperties(
            etag="abc123",
            last_modified=datetime(2025, 1, 1, 12, 0, 0),
        )
        container = Container(name="test-container", properties=props)
        assert container.name == "test-container"
        assert container.properties == props
        assert isinstance(container.metadata, ContainerMetadata)
    
    def test_initialization_invalid_name(self):
        """Test container initialization with invalid name."""
        props = ContainerProperties(
            etag="abc123",
            last_modified=datetime(2025, 1, 1, 12, 0, 0),
        )
        with pytest.raises(ValueError):
            Container(name="INVALID", properties=props)
    
    def test_with_metadata(self):
        """Test container with metadata."""
        metadata = ContainerMetadata(metadata={"key": "value"})
        props = ContainerProperties(
            etag="abc123",
            last_modified=datetime(2025, 1, 1, 12, 0, 0),
        )
        container = Container(
            name="test-container",
            metadata=metadata,
            properties=props,
        )
        assert container.metadata.metadata == {"key": "value"}
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        metadata = ContainerMetadata(metadata={"key": "value"})
        props = ContainerProperties(
            etag="abc123",
            last_modified=datetime(2025, 1, 1, 12, 0, 0),
            public_access=PublicAccessLevel.CONTAINER,
        )
        container = Container(
            name="test-container",
            metadata=metadata,
            properties=props,
        )
        result = container.to_dict()
        assert result['Name'] == "test-container"
        assert result['Properties']['Etag'] == "abc123"
        assert result['Properties']['PublicAccess'] == "container"
        assert result['Metadata'] == {"key": "value"}


class TestRequestModels:
    """Test request models."""
    
    def test_create_container_request(self):
        """Test CreateContainerRequest."""
        req = CreateContainerRequest(
            metadata={"key": "value"},
            public_access=PublicAccessLevel.BLOB,
        )
        assert req.metadata == {"key": "value"}
        assert req.public_access == PublicAccessLevel.BLOB
    
    def test_create_container_request_defaults(self):
        """Test CreateContainerRequest defaults."""
        req = CreateContainerRequest()
        assert req.metadata is None
        assert req.public_access == PublicAccessLevel.PRIVATE
    
    def test_set_container_metadata_request(self):
        """Test SetContainerMetadataRequest."""
        req = SetContainerMetadataRequest(metadata={"key": "value"})
        assert req.metadata == {"key": "value"}
    
    def test_set_container_metadata_request_empty(self):
        """Test SetContainerMetadataRequest with empty metadata."""
        req = SetContainerMetadataRequest()
        assert req.metadata == {}
