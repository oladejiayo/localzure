"""
Integration tests for Blob Storage blob API endpoints.

Tests blob upload, download, block operations, list, metadata, and conditional requests.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
import base64
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from localzure.services.blob.api import router, backend


@pytest.fixture
def client():
    """Create test client."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
async def reset_backend():
    """Reset backend before each test."""
    await backend.reset()
    await backend.create_container("test-container")  # Lowercase with hyphen


class TestPutBlob:
    """Test Put Blob operation."""
    
    def test_put_blob(self, client):
        """Test uploading a blob."""
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"Hello, World!",
        )
        assert response.status_code == 201
        assert "ETag" in response.headers
        assert "Last-Modified" in response.headers
    
    def test_put_blob_with_content_type(self, client):
        """Test uploading blob with content type."""
        response = client.put(
            "/blob/testaccount/test-container/test.html",
            content=b"<html></html>",
            headers={"Content-Type": "text/html"},
        )
        assert response.status_code == 201
        
        # Verify by getting blob properties
        get_response = client.get(
            "/blob/testaccount/test-container/test.html",
            params={"comp": "metadata"},
        )
        assert get_response.headers["Content-Type"] == "text/html"
    
    def test_put_blob_with_metadata(self, client):
        """Test uploading blob with metadata."""
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"content",
            headers={"x-ms-meta-key": "value"},
        )
        assert response.status_code == 201
        
        # Verify metadata
        get_response = client.get(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "metadata"},
        )
        assert get_response.headers["x-ms-meta-key"] == "value"
    
    def test_put_blob_with_content_headers(self, client):
        """Test uploading blob with content headers."""
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"content",
            headers={
                "Content-Encoding": "gzip",
                "Content-Language": "en-US",
                "Cache-Control": "max-age=3600",
                "Content-Disposition": "attachment",
            },
        )
        assert response.status_code == 201
        
        # Verify properties
        get_response = client.get(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "metadata"},
        )
        assert get_response.headers["Content-Encoding"] == "gzip"
        assert get_response.headers["Content-Language"] == "en-US"
        assert get_response.headers["Cache-Control"] == "max-age=3600"
    
    def test_put_blob_container_not_found(self, client):
        """Test uploading blob to non-existent container."""
        response = client.put(
            "/testaccount/nonexistent/test.txt",
            content=b"content",
        )
        assert response.status_code == 404
    
    def test_put_blob_conditional_if_match(self, client):
        """Test Put Blob with If-Match header."""
        # Upload initial blob
        put_response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"content",
        )
        etag = put_response.headers["ETag"]
        
        # Update with matching ETag
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"new content",
            headers={"If-Match": etag},
        )
        assert response.status_code == 201
    
    def test_put_blob_conditional_if_match_fail(self, client):
        """Test Put Blob with non-matching If-Match."""
        # Upload initial blob
        client.put("/blob/testaccount/test-container/test.txt", content=b"content")
        
        # Try to update with wrong ETag
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"new content",
            headers={"If-Match": "wrong-etag"},
        )
        assert response.status_code == 412


class TestGetBlob:
    """Test Get Blob operation."""
    
    def test_get_blob(self, client):
        """Test downloading a blob."""
        # Upload blob
        client.put("/blob/testaccount/test-container/test.txt", content=b"Hello, World!")
        
        # Download blob
        response = client.get("/blob/testaccount/test-container/test.txt")
        assert response.status_code == 200
        assert response.content == b"Hello, World!"
    
    def test_get_blob_not_found(self, client):
        """Test getting non-existent blob."""
        response = client.get("/blob/testaccount/test-container/nonexistent.txt")
        assert response.status_code == 404
    
    def test_get_blob_properties(self, client):
        """Test getting blob properties."""
        # Upload blob
        put_response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"content",
            headers={"x-ms-meta-key": "value"},
        )
        
        # Get properties
        response = client.get(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "metadata"},
        )
        assert response.status_code == 200
        assert "ETag" in response.headers
        assert "Last-Modified" in response.headers
        assert response.headers["Content-Length"] == "7"
        assert response.headers["x-ms-meta-key"] == "value"
    
    def test_get_blob_conditional_if_match(self, client):
        """Test Get Blob with If-Match."""
        # Upload blob
        put_response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"content",
        )
        etag = put_response.headers["ETag"]
        
        # Get with matching ETag
        response = client.get(
            "/blob/testaccount/test-container/test.txt",
            headers={"If-Match": etag},
        )
        assert response.status_code == 200
    
    def test_get_blob_conditional_if_match_fail(self, client):
        """Test Get Blob with non-matching If-Match."""
        # Upload blob
        client.put("/blob/testaccount/test-container/test.txt", content=b"content")
        
        # Get with wrong ETag
        response = client.get(
            "/blob/testaccount/test-container/test.txt",
            headers={"If-Match": "wrong-etag"},
        )
        assert response.status_code == 412
    
    def test_get_blob_conditional_if_none_match(self, client):
        """Test Get Blob with If-None-Match."""
        # Upload blob
        put_response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"content",
        )
        etag = put_response.headers["ETag"]
        
        # Get with matching ETag (should return 304)
        response = client.get(
            "/blob/testaccount/test-container/test.txt",
            headers={"If-None-Match": etag},
        )
        assert response.status_code == 304
    
    def test_get_blob_conditional_if_modified_since(self, client):
        """Test Get Blob with If-Modified-Since."""
        # Upload blob
        put_response = client.put(
            "/blob/testaccount/test-container/test.txt",
            content=b"content",
        )
        
        # Use a future timestamp to test 304 response
        # (blob hasn't been modified since future date, so return 304)
        from datetime import datetime, timezone, timedelta
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        future_str = future_time.strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        response = client.get(
            "/blob/testaccount/test-container/test.txt",
            headers={"If-Modified-Since": future_str},
        )
        assert response.status_code == 304


class TestSetBlobMetadata:
    """Test Set Blob Metadata operation."""
    
    def test_set_blob_metadata(self, client):
        """Test setting blob metadata."""
        # Upload blob
        client.put("/blob/testaccount/test-container/test.txt", content=b"content")
        
        # Set metadata
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "metadata"},
            headers={"x-ms-meta-new-key": "new-value"},
        )
        assert response.status_code == 200
        
        # Verify metadata
        get_response = client.get(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "metadata"},
        )
        assert get_response.headers["x-ms-meta-new-key"] == "new-value"
    
    def test_set_blob_metadata_blob_not_found(self, client):
        """Test setting metadata on non-existent blob."""
        response = client.put(
            "/blob/testaccount/test-container/nonexistent.txt",
            params={"comp": "metadata"},
            headers={"x-ms-meta-key": "value"},
        )
        assert response.status_code == 404


class TestDeleteBlob:
    """Test Delete Blob operation."""
    
    def test_delete_blob(self, client):
        """Test deleting a blob."""
        # Upload blob
        client.put("/blob/testaccount/test-container/test.txt", content=b"content")
        
        # Delete blob
        response = client.delete("/blob/testaccount/test-container/test.txt")
        assert response.status_code == 202
        
        # Verify blob is gone
        get_response = client.get("/blob/testaccount/test-container/test.txt")
        assert get_response.status_code == 404
    
    def test_delete_blob_not_found(self, client):
        """Test deleting non-existent blob."""
        response = client.delete("/blob/testaccount/test-container/nonexistent.txt")
        assert response.status_code == 404


class TestListBlobs:
    """Test List Blobs operation."""
    
    def test_list_blobs_empty(self, client):
        """Test listing blobs when empty."""
        response = client.get(
            "/blob/testaccount/test-container",
            params={"restype": "container", "comp": "list"},
        )
        assert response.status_code == 200
        assert b"<Blobs" in response.content  # Check for Blobs element
    
    def test_list_blobs(self, client):
        """Test listing blobs."""
        # Upload blobs
        client.put("/blob/testaccount/test-container/file1.txt", content=b"content1")
        client.put("/blob/testaccount/test-container/file2.txt", content=b"content2")
        client.put("/blob/testaccount/test-container/file3.txt", content=b"content3")
        
        # List blobs
        response = client.get(
            "/blob/testaccount/test-container",
            params={"restype": "container", "comp": "list"},
        )
        assert response.status_code == 200
        assert b"file1.txt" in response.content
        assert b"file2.txt" in response.content
        assert b"file3.txt" in response.content
    
    def test_list_blobs_with_prefix(self, client):
        """Test listing blobs with prefix."""
        # Upload blobs
        client.put("/blob/testaccount/test-container/docs/file1.txt", content=b"content")
        client.put("/blob/testaccount/test-container/docs/file2.txt", content=b"content")
        client.put("/blob/testaccount/test-container/images/pic.jpg", content=b"content")
        
        # List with prefix
        response = client.get(
            "/blob/testaccount/test-container",
            params={"restype": "container", "comp": "list", "prefix": "docs/"},
        )
        assert response.status_code == 200
        assert b"docs/file1.txt" in response.content
        assert b"docs/file2.txt" in response.content
        assert b"images/pic.jpg" not in response.content
    
    def test_list_blobs_with_max_results(self, client):
        """Test listing blobs with max results."""
        # Upload blobs
        for i in range(5):
            client.put(f"/blob/testaccount/test-container/file{i}.txt", content=b"content")
        
        # List with max results
        response = client.get(
            "/blob/testaccount/test-container",
            params={"restype": "container", "comp": "list", "maxresults": "3"},
        )
        assert response.status_code == 200
        assert b"<NextMarker>" in response.content
    
    def test_list_blobs_with_marker(self, client):
        """Test listing blobs with marker."""
        # Upload blobs
        for i in range(5):
            client.put(f"/blob/testaccount/test-container/file{i}.txt", content=b"content")
        
        # List with marker
        response = client.get(
            "/blob/testaccount/test-container",
            params={"restype": "container", "comp": "list", "marker": "file2.txt"},
        )
        assert response.status_code == 200
        assert b"file0.txt" not in response.content
        assert b"file3.txt" in response.content


class TestBlockOperations:
    """Test block blob operations."""
    
    def test_put_block(self, client):
        """Test staging a block."""
        block_id = base64.b64encode(b"block1").decode()
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "block", "blockid": block_id},
            content=b"Hello, ",
        )
        assert response.status_code == 201
    
    def test_put_block_list(self, client):
        """Test committing blocks."""
        # Stage blocks
        block1_id = base64.b64encode(b"block1").decode()
        block2_id = base64.b64encode(b"block2").decode()
        
        client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "block", "blockid": block1_id},
            content=b"Hello, ",
        )
        client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "block", "blockid": block2_id},
            content=b"World!",
        )
        
        # Commit blocks
        block_list_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<BlockList>
  <Uncommitted>{block1_id}</Uncommitted>
  <Uncommitted>{block2_id}</Uncommitted>
</BlockList>"""
        
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "blocklist"},
            content=block_list_xml.encode(),
        )
        assert response.status_code == 201
        
        # Verify blob content
        get_response = client.get("/blob/testaccount/test-container/test.txt")
        assert get_response.content == b"Hello, World!"
    
    def test_put_block_list_with_metadata(self, client):
        """Test committing blocks with metadata."""
        block_id = base64.b64encode(b"block1").decode()
        
        # Stage block
        client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "block", "blockid": block_id},
            content=b"content",
        )
        
        # Commit with metadata
        block_list_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<BlockList>
  <Uncommitted>{block_id}</Uncommitted>
</BlockList>"""
        
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "blocklist"},
            content=block_list_xml.encode(),
            headers={"x-ms-meta-key": "value"},
        )
        assert response.status_code == 201
        
        # Verify metadata
        get_response = client.get(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "metadata"},
        )
        assert get_response.headers["x-ms-meta-key"] == "value"
    
    def test_put_block_list_invalid_block_id(self, client):
        """Test committing with invalid block ID."""
        # Need to create blob first by staging a valid block
        valid_id = base64.b64encode(b"valid").decode()
        client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "block", "blockid": valid_id},
            content=b"content",
        )
        
        # Now try to commit with invalid block ID
        invalid_id = base64.b64encode(b"nonexistent").decode()
        
        block_list_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<BlockList>
  <Uncommitted>{invalid_id}</Uncommitted>
</BlockList>"""
        
        response = client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "blocklist"},
            content=block_list_xml.encode(),
        )
        assert response.status_code == 400
    
    def test_put_block_list_ordering(self, client):
        """Test blocks are committed in specified order."""
        # Stage blocks
        block1_id = base64.b64encode(b"block1").decode()
        block2_id = base64.b64encode(b"block2").decode()
        block3_id = base64.b64encode(b"block3").decode()
        
        client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "block", "blockid": block1_id},
            content=b"A",
        )
        client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "block", "blockid": block2_id},
            content=b"B",
        )
        client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "block", "blockid": block3_id},
            content=b"C",
        )
        
        # Commit in different order (3, 1, 2)
        block_list_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<BlockList>
  <Uncommitted>{block3_id}</Uncommitted>
  <Uncommitted>{block1_id}</Uncommitted>
  <Uncommitted>{block2_id}</Uncommitted>
</BlockList>"""
        
        client.put(
            "/blob/testaccount/test-container/test.txt",
            params={"comp": "blocklist"},
            content=block_list_xml.encode(),
        )
        
        # Verify content is in specified order
        get_response = client.get("/blob/testaccount/test-container/test.txt")
        assert get_response.content == b"CAB"


class TestBlobWorkflow:
    """Test complete blob workflows."""
    
    def test_upload_download_workflow(self, client):
        """Test complete upload and download workflow."""
        # Upload blob with metadata
        put_response = client.put(
            "/blob/testaccount/test-container/document.txt",
            content=b"Important document",
            headers={
                "Content-Type": "text/plain",
                "x-ms-meta-author": "John Doe",
                "x-ms-meta-version": "1.0",
            },
        )
        assert put_response.status_code == 201
        etag = put_response.headers["ETag"]
        
        # Get blob properties
        props_response = client.get(
            "/blob/testaccount/test-container/document.txt",
            params={"comp": "metadata"},
        )
        assert props_response.headers["x-ms-meta-author"] == "John Doe"
        
        # Download blob
        download_response = client.get("/blob/testaccount/test-container/document.txt")
        assert download_response.content == b"Important document"
        
        # Update metadata
        client.put(
            "/blob/testaccount/test-container/document.txt",
            params={"comp": "metadata"},
            headers={"x-ms-meta-version": "2.0"},
        )
        
        # Delete blob
        delete_response = client.delete("/blob/testaccount/test-container/document.txt")
        assert delete_response.status_code == 202
    
    def test_block_blob_workflow(self, client):
        """Test complete block blob workflow."""
        # Stage multiple blocks
        blocks = []
        for i in range(3):
            block_id = base64.b64encode(f"block{i}".encode()).decode()
            blocks.append(block_id)
            client.put(
                "/blob/testaccount/test-container/large-file.dat",
                params={"comp": "block", "blockid": block_id},
                content=f"Block {i} content. ".encode(),
            )
        
        # Commit all blocks
        block_list_xml = '<?xml version="1.0" encoding="utf-8"?><BlockList>'
        for block_id in blocks:
            block_list_xml += f"<Uncommitted>{block_id}</Uncommitted>"
        block_list_xml += "</BlockList>"
        
        commit_response = client.put(
            "/blob/testaccount/test-container/large-file.dat",
            params={"comp": "blocklist"},
            content=block_list_xml.encode(),
            headers={
                "Content-Type": "application/octet-stream",
                "x-ms-meta-chunks": "3",
            },
        )
        assert commit_response.status_code == 201
        
        # Download and verify
        download_response = client.get("/blob/testaccount/test-container/large-file.dat")
        assert b"Block 0" in download_response.content
        assert b"Block 1" in download_response.content
        assert b"Block 2" in download_response.content
