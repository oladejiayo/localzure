"""
Unit tests for Blob Storage blob backend operations.

Tests blob upload, download, block operations, list, metadata, and error handling.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
import base64

from localzure.services.blob.backend import (
    BlobNotFoundError,
    ContainerBackend,
    ContainerNotFoundError,
    InvalidBlockIdError,
)
from localzure.services.blob.models import BlockListType


@pytest.fixture
def backend():
    """Create a fresh backend for each test."""
    return ContainerBackend()


@pytest.fixture
async def backend_with_container(backend):
    """Create a backend with a test container."""
    await backend.create_container("test-container")
    return backend


class TestBlobOperations:
    """Test blob CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_put_blob(self, backend_with_container):
        """Test uploading a blob."""
        blob = await backend_with_container.put_blob(
            "test-container",
            "test.txt",
            b"Hello, World!",
        )
        assert blob.name == "test.txt"
        assert blob.container_name == "test-container"
        assert blob.content == b"Hello, World!"
        assert blob.properties.content_length == 13
        assert blob.properties.content_type == "application/octet-stream"
    
    @pytest.mark.asyncio
    async def test_put_blob_with_metadata(self, backend_with_container):
        """Test uploading blob with metadata."""
        blob = await backend_with_container.put_blob(
            "test-container",
            "test.txt",
            b"content",
            metadata={"key": "value"},
        )
        assert blob.metadata.metadata == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_put_blob_with_content_headers(self, backend_with_container):
        """Test uploading blob with content headers."""
        blob = await backend_with_container.put_blob(
            "test-container",
            "test.html",
            b"<html></html>",
            content_type="text/html",
            content_encoding="gzip",
            content_language="en-US",
            cache_control="max-age=3600",
        )
        assert blob.properties.content_type == "text/html"
        assert blob.properties.content_encoding == "gzip"
        assert blob.properties.content_language == "en-US"
        assert blob.properties.cache_control == "max-age=3600"
    
    @pytest.mark.asyncio
    async def test_put_blob_container_not_found(self, backend):
        """Test uploading blob to non-existent container."""
        with pytest.raises(ContainerNotFoundError):
            await backend.put_blob("nonexistent", "test.txt", b"content")
    
    @pytest.mark.asyncio
    async def test_get_blob(self, backend_with_container):
        """Test downloading a blob."""
        await backend_with_container.put_blob(
            "test-container",
            "test.txt",
            b"Hello, World!",
        )
        blob = await backend_with_container.get_blob("test-container", "test.txt")
        assert blob.content == b"Hello, World!"
    
    @pytest.mark.asyncio
    async def test_get_blob_not_found(self, backend_with_container):
        """Test getting non-existent blob."""
        with pytest.raises(BlobNotFoundError):
            await backend_with_container.get_blob("test-container", "nonexistent.txt")
    
    @pytest.mark.asyncio
    async def test_get_blob_properties(self, backend_with_container):
        """Test getting blob properties."""
        await backend_with_container.put_blob(
            "test-container",
            "test.txt",
            b"content",
        )
        props = await backend_with_container.get_blob_properties("test-container", "test.txt")
        assert props.content_length == 7
        assert props.etag is not None
    
    @pytest.mark.asyncio
    async def test_set_blob_metadata(self, backend_with_container):
        """Test setting blob metadata."""
        await backend_with_container.put_blob(
            "test-container",
            "test.txt",
            b"content",
        )
        
        blob = await backend_with_container.set_blob_metadata(
            "test-container",
            "test.txt",
            {"new-key": "new-value"},
        )
        
        assert blob.metadata.metadata == {"new-key": "new-value"}
    
    @pytest.mark.asyncio
    async def test_delete_blob(self, backend_with_container):
        """Test deleting a blob."""
        await backend_with_container.put_blob(
            "test-container",
            "test.txt",
            b"content",
        )
        await backend_with_container.delete_blob("test-container", "test.txt")
        
        with pytest.raises(BlobNotFoundError):
            await backend_with_container.get_blob("test-container", "test.txt")
    
    @pytest.mark.asyncio
    async def test_delete_blob_not_found(self, backend_with_container):
        """Test deleting non-existent blob."""
        with pytest.raises(BlobNotFoundError):
            await backend_with_container.delete_blob("test-container", "nonexistent.txt")
    
    @pytest.mark.asyncio
    async def test_blob_exists(self, backend_with_container):
        """Test checking if blob exists."""
        assert not await backend_with_container.blob_exists("test-container", "test.txt")
        
        await backend_with_container.put_blob(
            "test-container",
            "test.txt",
            b"content",
        )
        
        assert await backend_with_container.blob_exists("test-container", "test.txt")


class TestListBlobs:
    """Test blob listing operations."""
    
    @pytest.mark.asyncio
    async def test_list_blobs_empty(self, backend_with_container):
        """Test listing blobs when empty."""
        blobs, marker = await backend_with_container.list_blobs("test-container")
        assert blobs == []
        assert marker is None
    
    @pytest.mark.asyncio
    async def test_list_blobs(self, backend_with_container):
        """Test listing blobs."""
        await backend_with_container.put_blob("test-container", "file1.txt", b"content1")
        await backend_with_container.put_blob("test-container", "file2.txt", b"content2")
        await backend_with_container.put_blob("test-container", "file3.txt", b"content3")
        
        blobs, marker = await backend_with_container.list_blobs("test-container")
        assert len(blobs) == 3
        names = [b.name for b in blobs]
        assert names == ["file1.txt", "file2.txt", "file3.txt"]
        assert marker is None
    
    @pytest.mark.asyncio
    async def test_list_blobs_with_prefix(self, backend_with_container):
        """Test listing blobs with prefix filter."""
        await backend_with_container.put_blob("test-container", "docs/file1.txt", b"content")
        await backend_with_container.put_blob("test-container", "docs/file2.txt", b"content")
        await backend_with_container.put_blob("test-container", "images/pic.jpg", b"content")
        
        blobs, _ = await backend_with_container.list_blobs("test-container", prefix="docs/")
        assert len(blobs) == 2
        names = [b.name for b in blobs]
        assert all(n.startswith("docs/") for n in names)
    
    @pytest.mark.asyncio
    async def test_list_blobs_with_max_results(self, backend_with_container):
        """Test listing blobs with max results."""
        for i in range(5):
            await backend_with_container.put_blob("test-container", f"file{i}.txt", b"content")
        
        blobs, marker = await backend_with_container.list_blobs("test-container", max_results=3)
        assert len(blobs) == 3
        assert marker == "file2.txt"
    
    @pytest.mark.asyncio
    async def test_list_blobs_with_marker(self, backend_with_container):
        """Test listing blobs with continuation marker."""
        for i in range(5):
            await backend_with_container.put_blob("test-container", f"file{i}.txt", b"content")
        
        blobs, _ = await backend_with_container.list_blobs("test-container", marker="file2.txt")
        names = [b.name for b in blobs]
        assert "file0.txt" not in names
        assert "file1.txt" not in names
        assert "file2.txt" not in names
        assert "file3.txt" in names


class TestBlockOperations:
    """Test block blob operations."""
    
    @pytest.mark.asyncio
    async def test_put_block(self, backend_with_container):
        """Test staging a block."""
        block_id = base64.b64encode(b"block1").decode()
        await backend_with_container.put_block(
            "test-container",
            "test.txt",
            block_id,
            b"Hello, ",
        )
        
        # Verify blob was created with uncommitted block
        blob = await backend_with_container.get_blob("test-container", "test.txt")
        assert block_id in blob.uncommitted_blocks
        assert blob.uncommitted_blocks[block_id].content == b"Hello, "
    
    @pytest.mark.asyncio
    async def test_put_multiple_blocks(self, backend_with_container):
        """Test staging multiple blocks."""
        block1_id = base64.b64encode(b"block1").decode()
        block2_id = base64.b64encode(b"block2").decode()
        
        await backend_with_container.put_block("test-container", "test.txt", block1_id, b"Hello, ")
        await backend_with_container.put_block("test-container", "test.txt", block2_id, b"World!")
        
        blob = await backend_with_container.get_blob("test-container", "test.txt")
        assert len(blob.uncommitted_blocks) == 2
    
    @pytest.mark.asyncio
    async def test_put_block_list(self, backend_with_container):
        """Test committing blocks."""
        block1_id = base64.b64encode(b"block1").decode()
        block2_id = base64.b64encode(b"block2").decode()
        
        await backend_with_container.put_block("test-container", "test.txt", block1_id, b"Hello, ")
        await backend_with_container.put_block("test-container", "test.txt", block2_id, b"World!")
        
        block_list = [
            (block1_id, BlockListType.UNCOMMITTED),
            (block2_id, BlockListType.UNCOMMITTED),
        ]
        
        blob = await backend_with_container.put_block_list(
            "test-container",
            "test.txt",
            block_list,
        )
        
        assert blob.content == b"Hello, World!"
        assert blob.properties.content_length == 13
        assert len(blob.uncommitted_blocks) == 0  # Blocks cleared after commit
    
    @pytest.mark.asyncio
    async def test_put_block_list_with_metadata(self, backend_with_container):
        """Test committing blocks with metadata."""
        block_id = base64.b64encode(b"block1").decode()
        await backend_with_container.put_block("test-container", "test.txt", block_id, b"content")
        
        blob = await backend_with_container.put_block_list(
            "test-container",
            "test.txt",
            [(block_id, BlockListType.UNCOMMITTED)],
            metadata={"key": "value"},
        )
        
        assert blob.metadata.metadata == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_put_block_list_invalid_block_id(self, backend_with_container):
        """Test committing with invalid block ID."""
        block_id = base64.b64encode(b"block1").decode()
        invalid_id = base64.b64encode(b"invalid").decode()
        
        await backend_with_container.put_block("test-container", "test.txt", block_id, b"content")
        
        block_list = [(invalid_id, BlockListType.UNCOMMITTED)]
        
        with pytest.raises(InvalidBlockIdError):
            await backend_with_container.put_block_list(
                "test-container",
                "test.txt",
                block_list,
            )
    
    @pytest.mark.asyncio
    async def test_put_block_list_ordering(self, backend_with_container):
        """Test that blocks are committed in the specified order."""
        block1_id = base64.b64encode(b"block1").decode()
        block2_id = base64.b64encode(b"block2").decode()
        block3_id = base64.b64encode(b"block3").decode()
        
        await backend_with_container.put_block("test-container", "test.txt", block1_id, b"A")
        await backend_with_container.put_block("test-container", "test.txt", block2_id, b"B")
        await backend_with_container.put_block("test-container", "test.txt", block3_id, b"C")
        
        # Commit in different order
        block_list = [
            (block3_id, BlockListType.UNCOMMITTED),
            (block1_id, BlockListType.UNCOMMITTED),
            (block2_id, BlockListType.UNCOMMITTED),
        ]
        
        blob = await backend_with_container.put_block_list(
            "test-container",
            "test.txt",
            block_list,
        )
        
        assert blob.content == b"CAB"


class TestDeleteContainerWithBlobs:
    """Test deleting container deletes blobs."""
    
    @pytest.mark.asyncio
    async def test_delete_container_deletes_blobs(self, backend_with_container):
        """Test that deleting container removes all blobs."""
        await backend_with_container.put_blob("test-container", "file1.txt", b"content")
        await backend_with_container.put_blob("test-container", "file2.txt", b"content")
        
        await backend_with_container.delete_container("test-container")
        
        # Recreate container
        await backend_with_container.create_container("test-container")
        
        # Blobs should be gone
        blobs, _ = await backend_with_container.list_blobs("test-container")
        assert len(blobs) == 0
