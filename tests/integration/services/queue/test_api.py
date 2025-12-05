"""
Integration tests for Queue Storage API endpoints.

Tests queue creation, listing, metadata, deletion via HTTP API.

Author: Ayodele Oladeji
Date: 2025
"""

import pytest
from fastapi.testclient import TestClient

from localzure.services.queue.api import router, backend


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


class TestCreateQueue:
    """Test Create Queue operation."""
    
    def test_create_queue(self, client):
        """Test creating a queue."""
        response = client.put("/queue/testaccount/myqueue")
        
        assert response.status_code == 201
        assert "x-ms-request-id" in response.headers
        assert "x-ms-version" in response.headers
    
    def test_create_queue_with_metadata(self, client):
        """Test creating queue with metadata."""
        response = client.put(
            "/queue/testaccount/myqueue",
            headers={
                "x-ms-meta-key1": "value1",
                "x-ms-meta-key2": "value2",
            },
        )
        
        assert response.status_code == 201
    
    def test_create_queue_invalid_name(self, client):
        """Test creating queue with invalid name."""
        response = client.put("/queue/testaccount/InvalidQueue")
        
        assert response.status_code == 400
        assert "InvalidQueueName" in response.text
    
    def test_create_duplicate_queue(self, client):
        """Test creating duplicate queue."""
        client.put("/queue/testaccount/myqueue")
        response = client.put("/queue/testaccount/myqueue")
        
        assert response.status_code == 409
        assert "QueueAlreadyExists" in response.text


class TestListQueues:
    """Test List Queues operation."""
    
    def test_list_empty_queues(self, client):
        """Test listing when no queues exist."""
        response = client.get("/queue/testaccount?comp=list")
        
        assert response.status_code == 200
        assert "<Queues" in response.text
    
    def test_list_single_queue(self, client):
        """Test listing single queue."""
        client.put("/queue/testaccount/myqueue")
        
        response = client.get("/queue/testaccount?comp=list")
        
        assert response.status_code == 200
        assert "<Name>myqueue</Name>" in response.text
    
    def test_list_multiple_queues(self, client):
        """Test listing multiple queues."""
        client.put("/queue/testaccount/queue1")
        client.put("/queue/testaccount/queue2")
        client.put("/queue/testaccount/queue3")
        
        response = client.get("/queue/testaccount?comp=list")
        
        assert response.status_code == 200
        assert "<Name>queue1</Name>" in response.text
        assert "<Name>queue2</Name>" in response.text
        assert "<Name>queue3</Name>" in response.text
    
    def test_list_queues_with_prefix(self, client):
        """Test listing queues with prefix filter."""
        client.put("/queue/testaccount/test-queue-1")
        client.put("/queue/testaccount/test-queue-2")
        client.put("/queue/testaccount/other-queue")
        
        response = client.get("/queue/testaccount?comp=list&prefix=test-")
        
        assert response.status_code == 200
        assert "<Name>test-queue-1</Name>" in response.text
        assert "<Name>test-queue-2</Name>" in response.text
        assert "other-queue" not in response.text
    
    def test_list_queues_with_maxresults(self, client):
        """Test listing queues with max results."""
        client.put("/queue/testaccount/queue1")
        client.put("/queue/testaccount/queue2")
        client.put("/queue/testaccount/queue3")
        
        response = client.get("/queue/testaccount?comp=list&maxresults=2")
        
        assert response.status_code == 200
        assert "<Name>queue1</Name>" in response.text
        assert "<Name>queue2</Name>" in response.text
        assert "<NextMarker>queue2</NextMarker>" in response.text
    
    def test_list_queues_without_metadata(self, client):
        """Test listing queues without metadata (default)."""
        client.put(
            "/queue/testaccount/myqueue",
            headers={"x-ms-meta-key": "value"},
        )
        
        response = client.get("/queue/testaccount?comp=list")
        
        assert response.status_code == 200
        assert "<Metadata>" not in response.text
    
    def test_list_queues_with_metadata(self, client):
        """Test listing queues with metadata included."""
        client.put(
            "/queue/testaccount/myqueue",
            headers={"x-ms-meta-key": "value"},
        )
        
        response = client.get("/queue/testaccount?comp=list&include=metadata")
        
        assert response.status_code == 200
        assert "<Metadata" in response.text
        assert "<key>value</key>" in response.text
    
    def test_list_queues_invalid_comp(self, client):
        """Test listing queues with invalid comp parameter."""
        response = client.get("/queue/testaccount?comp=invalid")
        
        assert response.status_code == 400
        assert "InvalidQueryParameter" in response.text


class TestGetQueueMetadata:
    """Test Get Queue Metadata operation."""
    
    def test_get_queue_metadata(self, client):
        """Test getting queue metadata."""
        client.put(
            "/queue/testaccount/myqueue",
            headers={
                "x-ms-meta-key1": "value1",
                "x-ms-meta-key2": "value2",
            },
        )
        
        response = client.get("/queue/testaccount/myqueue?comp=metadata")
        
        assert response.status_code == 200
        assert response.headers.get("x-ms-meta-key1") == "value1"
        assert response.headers.get("x-ms-meta-key2") == "value2"
        assert "x-ms-approximate-messages-count" in response.headers
    
    def test_get_queue_metadata_nonexistent(self, client):
        """Test getting metadata for non-existent queue."""
        response = client.get("/queue/testaccount/nonexistent?comp=metadata")
        
        assert response.status_code == 404
        assert "QueueNotFound" in response.text
    
    def test_get_queue_metadata_invalid_comp(self, client):
        """Test getting metadata with invalid comp parameter."""
        client.put("/queue/testaccount/myqueue")
        response = client.get("/queue/testaccount/myqueue?comp=invalid")
        
        assert response.status_code == 400
        assert "InvalidQueryParameter" in response.text


class TestSetQueueMetadata:
    """Test Set Queue Metadata operation."""
    
    def test_set_queue_metadata(self, client):
        """Test setting queue metadata."""
        client.put("/queue/testaccount/myqueue")
        
        response = client.put(
            "/queue/testaccount/myqueue?comp=metadata",
            headers={
                "x-ms-meta-new-key": "new-value",
            },
        )
        
        assert response.status_code == 204
        
        # Verify metadata was updated
        get_response = client.get("/queue/testaccount/myqueue?comp=metadata")
        assert get_response.headers.get("x-ms-meta-new-key") == "new-value"
    
    def test_set_queue_metadata_empty(self, client):
        """Test setting empty metadata."""
        client.put(
            "/queue/testaccount/myqueue",
            headers={"x-ms-meta-old-key": "old-value"},
        )
        
        response = client.put("/queue/testaccount/myqueue?comp=metadata")
        
        assert response.status_code == 204
        
        # Verify metadata was cleared
        get_response = client.get("/queue/testaccount/myqueue?comp=metadata")
        assert "x-ms-meta-old-key" not in get_response.headers
    
    def test_set_queue_metadata_nonexistent(self, client):
        """Test setting metadata for non-existent queue."""
        response = client.put(
            "/queue/testaccount/nonexistent?comp=metadata",
            headers={"x-ms-meta-key": "value"},
        )
        
        assert response.status_code == 404
        assert "QueueNotFound" in response.text
    
    def test_set_queue_metadata_invalid_comp(self, client):
        """Test setting metadata with invalid comp parameter."""
        client.put("/queue/testaccount/myqueue")
        response = client.put("/queue/testaccount/myqueue?comp=invalid")
        
        assert response.status_code == 400
        assert "InvalidQueryParameter" in response.text


class TestDeleteQueue:
    """Test Delete Queue operation."""
    
    def test_delete_queue(self, client):
        """Test deleting a queue."""
        client.put("/queue/testaccount/myqueue")
        
        response = client.delete("/queue/testaccount/myqueue")
        
        assert response.status_code == 204
        
        # Verify queue was deleted
        get_response = client.get("/queue/testaccount/myqueue?comp=metadata")
        assert get_response.status_code == 404
    
    def test_delete_nonexistent_queue(self, client):
        """Test deleting non-existent queue."""
        response = client.delete("/queue/testaccount/nonexistent")
        
        assert response.status_code == 404
        assert "QueueNotFound" in response.text
