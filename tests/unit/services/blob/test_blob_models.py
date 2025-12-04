"""
Unit tests for Blob Storage blob models.

Tests Block, BlobProperties, Blob, and ConditionalHeaders models.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
import base64
from datetime import datetime, timezone

from localzure.services.blob.models import (
    Block,
    BlobProperties,
    Blob,
    BlobType,
    BlobTier,
    ConditionalHeaders,
    ContainerMetadata,
)


class TestBlockModel:
    """Test Block model."""
    
    def test_create_block(self):
        """Test creating a block."""
        block_id = base64.b64encode(b"block1").decode()
        block = Block(
            block_id=block_id,
            size=10,
            content=b"test bytes",
        )
        assert block.block_id == block_id
        assert block.size == 10
        assert block.content == b"test bytes"
        assert not block.committed
    
    def test_block_validation_invalid_base64(self):
        """Test block ID must be valid base64."""
        with pytest.raises(ValueError, match="Invalid base64"):
            Block(block_id="not-base64!", size=10, content=b"content")
    
    def test_block_validation_too_long(self):
        """Test block ID cannot exceed 64 bytes when decoded."""
        # Create base64 that decodes to 65 bytes
        long_data = b"x" * 65
        long_id = base64.b64encode(long_data).decode()
        
        with pytest.raises(ValueError, match="Block ID must be at most 64 bytes"):
            Block(block_id=long_id, size=10, content=b"content")
    
    def test_block_committed_flag(self):
        """Test block committed flag."""
        block = Block(
            block_id=base64.b64encode(b"block1").decode(),
            size=10,
            content=b"test",
            committed=True,
        )
        assert block.committed


class TestBlobPropertiesModel:
    """Test BlobProperties model."""
    
    def test_create_blob_properties(self):
        """Test creating blob properties."""
        now = datetime.now(timezone.utc)
        props = BlobProperties(
            etag="abc123",
            last_modified=now,
            content_length=100,
            content_type="text/plain",
        )
        assert props.etag == "abc123"
        assert props.last_modified == now
        assert props.content_length == 100
        assert props.content_type == "text/plain"
    
    def test_blob_properties_defaults(self):
        """Test blob properties with defaults."""
        now = datetime.now(timezone.utc)
        props = BlobProperties(
            etag="abc",
            last_modified=now,
            content_length=0,
        )
        assert props.content_type == "application/octet-stream"  # Default value
        assert props.content_encoding is None
        assert props.blob_type == BlobType.BLOCK_BLOB
        assert props.lease_status == "unlocked"
        assert props.lease_state == "available"
    
    def test_blob_properties_to_headers(self):
        """Test converting blob properties to headers."""
        now = datetime.now(timezone.utc)
        props = BlobProperties(
            etag="abc123",
            last_modified=now,
            content_length=100,
            content_type="text/html",
            content_encoding="gzip",
            content_language="en",
            cache_control="max-age=3600",
            blob_type=BlobType.BLOCK_BLOB,
            blob_tier=BlobTier.HOT,
        )
        
        headers = props.to_headers()
        assert headers["ETag"] == '"abc123"'  # ETags are quoted
        assert headers["Content-Type"] == "text/html"
        assert headers["Content-Encoding"] == "gzip"
        assert headers["Content-Language"] == "en"
        assert headers["Cache-Control"] == "max-age=3600"
        assert headers["x-ms-blob-type"] == "BlockBlob"
        assert headers["x-ms-access-tier"] == "Hot"


class TestBlobModel:
    """Test Blob model."""
    
    def test_create_blob(self):
        """Test creating a blob."""
        now = datetime.now(timezone.utc)
        props = BlobProperties(
            etag="abc",
            last_modified=now,
            content_length=10,
        )
        blob = Blob(
            name="test.txt",
            container_name="container",
            content=b"test bytes",
            properties=props,
        )
        assert blob.name == "test.txt"
        assert blob.container_name == "container"
        assert blob.content == b"test bytes"
        assert blob.properties == props
    
    def test_blob_with_metadata(self):
        """Test blob with metadata."""
        now = datetime.now(timezone.utc)
        props = BlobProperties(etag="abc", last_modified=now, content_length=0)
        metadata = ContainerMetadata(metadata={"key": "value"})
        
        blob = Blob(
            name="test.txt",
            container_name="container",
            content=b"",
            properties=props,
            metadata=metadata,
        )
        assert blob.metadata.metadata == {"key": "value"}
    
    def test_blob_with_blocks(self):
        """Test blob with uncommitted blocks."""
        now = datetime.now(timezone.utc)
        props = BlobProperties(etag="abc", last_modified=now, content_length=0)
        
        block = Block(
            block_id=base64.b64encode(b"block1").decode(),
            size=10,
            content=b"test",
        )
        
        blob = Blob(
            name="test.txt",
            container_name="container",
            content=b"",
            properties=props,
            uncommitted_blocks={"block1": block},
        )
        assert len(blob.uncommitted_blocks) == 1
    
    def test_blob_to_dict(self):
        """Test converting blob to dictionary."""
        now = datetime.now(timezone.utc)
        props = BlobProperties(
            etag="abc",
            last_modified=now,
            content_length=10,
            content_type="text/plain",
        )
        metadata = ContainerMetadata(metadata={"key": "value"})
        
        blob = Blob(
            name="test.txt",
            container_name="container",
            content=b"test bytes",
            properties=props,
            metadata=metadata,
        )
        
        data = blob.to_dict()
        assert data["Name"] == "test.txt"  # Keys are capitalized
        assert data["Properties"]["Content-Length"] == 10
        assert data["Metadata"] == {"key": "value"}


class TestConditionalHeadersModel:
    """Test ConditionalHeaders model."""
    
    def test_conditional_headers_empty(self):
        """Test empty conditional headers."""
        headers = ConditionalHeaders()
        assert headers.if_match is None
        assert headers.if_none_match is None
        assert headers.if_modified_since is None
        assert headers.if_unmodified_since is None
    
    def test_check_conditions_no_conditions(self):
        """Test check_conditions with no conditions."""
        headers = ConditionalHeaders()
        etag = "abc123"
        last_modified = datetime.now(timezone.utc)
        
        result = headers.check_conditions(etag, last_modified)
        assert result is None  # Conditions pass
    
    def test_check_conditions_if_match_pass(self):
        """Test If-Match passes when ETags match."""
        headers = ConditionalHeaders(if_match="abc123")
        result = headers.check_conditions("abc123", datetime.now(timezone.utc))
        assert result is None
    
    def test_check_conditions_if_match_fail(self):
        """Test If-Match fails when ETags don't match."""
        headers = ConditionalHeaders(if_match="abc123")
        result = headers.check_conditions("xyz789", datetime.now(timezone.utc))
        assert result == 412
    
    def test_check_conditions_if_none_match_pass(self):
        """Test If-None-Match passes when ETags differ."""
        headers = ConditionalHeaders(if_none_match="abc123")
        result = headers.check_conditions("xyz789", datetime.now(timezone.utc))
        assert result is None
    
    def test_check_conditions_if_none_match_fail(self):
        """Test If-None-Match fails when ETags match."""
        headers = ConditionalHeaders(if_none_match="abc123")
        result = headers.check_conditions("abc123", datetime.now(timezone.utc))
        assert result == 304
    
    def test_check_conditions_if_modified_since_pass(self):
        """Test If-Modified-Since passes when resource is newer."""
        old_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        new_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        headers = ConditionalHeaders(if_modified_since=old_time)
        result = headers.check_conditions("etag", new_time)
        assert result is None
    
    def test_check_conditions_if_modified_since_fail(self):
        """Test If-Modified-Since fails when resource is not newer."""
        old_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        
        headers = ConditionalHeaders(if_modified_since=old_time)
        result = headers.check_conditions("etag", old_time)
        assert result == 304
    
    def test_check_conditions_if_unmodified_since_pass(self):
        """Test If-Unmodified-Since passes when resource is not newer."""
        time = datetime(2024, 1, 2, tzinfo=timezone.utc)
        old_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        
        headers = ConditionalHeaders(if_unmodified_since=time)
        result = headers.check_conditions("etag", old_time)
        assert result is None
    
    def test_check_conditions_if_unmodified_since_fail(self):
        """Test If-Unmodified-Since fails when resource is newer."""
        old_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        new_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        headers = ConditionalHeaders(if_unmodified_since=old_time)
        result = headers.check_conditions("etag", new_time)
        assert result == 412
    
    def test_check_conditions_multiple_conditions(self):
        """Test multiple conditions together."""
        # Both If-Match and If-Modified-Since must pass
        time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        new_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        headers = ConditionalHeaders(
            if_match="abc123",
            if_modified_since=time,
        )
        
        # If-Match passes, If-Modified-Since passes
        result = headers.check_conditions("abc123", new_time)
        assert result is None
        
        # If-Match fails
        result = headers.check_conditions("xyz789", new_time)
        assert result == 412
