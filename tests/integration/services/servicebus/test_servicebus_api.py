"""
Integration tests for Service Bus API endpoints.

Tests queue management via HTTP API.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest
from fastapi.testclient import TestClient

from localzure.services.servicebus.api import router, backend
from localzure.services.servicebus.error_handlers import register_exception_handlers


@pytest.fixture
def client():
    """Create test client."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    return TestClient(app)


@pytest.fixture(autouse=True)
async def reset_backend():
    """Reset backend before each test."""
    await backend.reset()
    yield
    await backend.reset()


class TestCreateQueue:
    """Test Create Queue operation."""
    
    def test_create_queue_minimal(self, client):
        """Test creating a queue with minimal properties."""
        response = client.put(
            "/servicebus/myns/test-queue",
            content="",
        )
        
        assert response.status_code == 201
        assert "application/xml" in response.headers["content-type"]
        assert b"<QueueDescription" in response.content
        assert b"test-queue" in response.content
    
    def test_create_queue_with_properties(self, client):
        """Test creating a queue with custom properties."""
        xml_body = """<?xml version="1.0" encoding="utf-8"?>
<QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
    <MaxSizeInMegabytes>2048</MaxSizeInMegabytes>
    <LockDuration>PT120S</LockDuration>
    <RequiresSession>true</RequiresSession>
    <EnableDeadLetteringOnMessageExpiration>true</EnableDeadLetteringOnMessageExpiration>
</QueueDescription>"""
        
        response = client.put(
            "/servicebus/myns/custom-queue",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 201
        assert b"2048" in response.content
        assert b"PT120S" in response.content
        assert b"true" in response.content
    
    def test_create_queue_invalid_name(self, client):
        """Test creating a queue with invalid name."""
        response = client.put(
            "/servicebus/myns/-invalid",
            content="",
        )
        
        assert response.status_code == 400
        assert b"InvalidQueueName" in response.content
    
    def test_create_duplicate_queue(self, client):
        """Test creating a queue that already exists returns 200 (idempotent PUT)."""
        # Create first time
        response1 = client.put("/servicebus/myns/test-queue", content="")
        assert response1.status_code == 201
        
        # Try to create again (should return 200 OK, not 409)
        response2 = client.put("/servicebus/myns/test-queue", content="")
        assert response2.status_code == 200


class TestListQueues:
    """Test List Queues operation."""
    
    def test_list_empty_queues(self, client):
        """Test listing queues when none exist."""
        response = client.get("/servicebus/myns/$Resources/Queues")
        
        assert response.status_code == 200
        assert b"<feed" in response.content
        assert b"Queues" in response.content
    
    def test_list_single_queue(self, client):
        """Test listing a single queue."""
        client.put("/servicebus/myns/test-queue", content="")
        
        response = client.get("/servicebus/myns/$Resources/Queues")
        
        assert response.status_code == 200
        assert b"test-queue" in response.content
        assert b"<entry>" in response.content
    
    def test_list_multiple_queues(self, client):
        """Test listing multiple queues."""
        client.put("/servicebus/myns/queue-a", content="")
        client.put("/servicebus/myns/queue-b", content="")
        client.put("/servicebus/myns/queue-c", content="")
        
        response = client.get("/servicebus/myns/$Resources/Queues")
        
        assert response.status_code == 200
        assert b"queue-a" in response.content
        assert b"queue-b" in response.content
        assert b"queue-c" in response.content
    
    def test_list_queues_with_pagination(self, client):
        """Test listing queues with pagination."""
        # Create 10 queues
        for i in range(10):
            client.put(f"/servicebus/myns/queue-{i:02d}", content="")
        
        # Get first 5
        response = client.get("/servicebus/myns/$Resources/Queues?$skip=0&$top=5")
        
        assert response.status_code == 200
        content = response.content.decode()
        assert "queue-00" in content
        assert "queue-04" in content
        
        # Get next 5
        response = client.get("/servicebus/myns/$Resources/Queues?$skip=5&$top=5")
        
        assert response.status_code == 200
        content = response.content.decode()
        assert "queue-05" in content
        assert "queue-09" in content


class TestGetQueue:
    """Test Get Queue operation."""
    
    def test_get_existing_queue(self, client):
        """Test getting an existing queue."""
        # Create queue
        client.put("/servicebus/myns/test-queue", content="")
        
        # Get queue
        response = client.get("/servicebus/myns/test-queue")
        
        assert response.status_code == 200
        assert b"<QueueDescription" in response.content
        assert b"MaxSizeInMegabytes" in response.content
        assert b"LockDuration" in response.content
        assert b"MessageCount" in response.content
        assert b"ActiveMessageCount" in response.content
        assert b"DeadLetterMessageCount" in response.content
    
    def test_get_nonexistent_queue(self, client):
        """Test getting a nonexistent queue."""
        response = client.get("/servicebus/myns/nonexistent")
        
        assert response.status_code == 404
        assert b"EntityNotFound" in response.content


class TestUpdateQueue:
    """Test Update Queue operation."""
    
    def test_update_queue_properties(self, client):
        """Test updating queue properties."""
        # Create queue
        client.put("/servicebus/myns/test-queue", content="")
        
        # Update properties
        xml_body = """<?xml version="1.0" encoding="utf-8"?>
<QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
    <MaxSizeInMegabytes>3072</MaxSizeInMegabytes>
    <LockDuration>PT180S</LockDuration>
    <RequiresSession>true</RequiresSession>
</QueueDescription>"""
        
        response = client.put(
            "/servicebus/myns/test-queue",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 200
        assert b"3072" in response.content
        assert b"PT180S" in response.content
        
        # Verify update
        get_response = client.get("/servicebus/myns/test-queue")
        assert b"3072" in get_response.content
        assert b"PT180S" in get_response.content
    
    def test_update_nonexistent_queue(self, client):
        """Test updating a nonexistent queue creates it (PUT is idempotent)."""
        xml_body = """<?xml version="1.0" encoding="utf-8"?>
<QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
    <MaxSizeInMegabytes>2048</MaxSizeInMegabytes>
</QueueDescription>"""
        
        response = client.put(
            "/servicebus/myns/nonexistent",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Azure Service Bus PUT is idempotent - creates if doesn't exist
        assert response.status_code == 201
        assert b"2048" in response.content


class TestDeleteQueue:
    """Test Delete Queue operation."""
    
    def test_delete_existing_queue(self, client):
        """Test deleting an existing queue."""
        # Create queue
        client.put("/servicebus/myns/test-queue", content="")
        
        # Delete queue
        response = client.delete("/servicebus/myns/test-queue")
        
        assert response.status_code == 200
        
        # Verify deletion
        get_response = client.get("/servicebus/myns/test-queue")
        assert get_response.status_code == 404
    
    def test_delete_nonexistent_queue(self, client):
        """Test deleting a nonexistent queue."""
        response = client.delete("/servicebus/myns/nonexistent")
        
        assert response.status_code == 404
        assert b"EntityNotFound" in response.content


class TestCompleteWorkflow:
    """Test complete queue management workflow."""
    
    def test_full_lifecycle(self, client):
        """Test full queue lifecycle."""
        # Create queue
        xml_create = """<?xml version="1.0" encoding="utf-8"?>
<QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
    <MaxSizeInMegabytes>2048</MaxSizeInMegabytes>
    <LockDuration>PT60S</LockDuration>
    <RequiresDuplicateDetection>true</RequiresDuplicateDetection>
</QueueDescription>"""
        
        create_response = client.put(
            "/servicebus/myns/workflow-queue",
            content=xml_create,
        )
        assert create_response.status_code == 201
        
        # List queues
        list_response = client.get("/servicebus/myns/$Resources/Queues")
        assert list_response.status_code == 200
        assert b"workflow-queue" in list_response.content
        
        # Get queue
        get_response = client.get("/servicebus/myns/workflow-queue")
        assert get_response.status_code == 200
        assert b"2048" in get_response.content
        
        # Update queue
        xml_update = """<?xml version="1.0" encoding="utf-8"?>
<QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
    <MaxSizeInMegabytes>4096</MaxSizeInMegabytes>
    <LockDuration>PT120S</LockDuration>
</QueueDescription>"""
        
        update_response = client.put(
            "/servicebus/myns/workflow-queue",
            content=xml_update,
        )
        assert update_response.status_code == 200
        assert b"4096" in update_response.content
        
        # Delete queue
        delete_response = client.delete("/servicebus/myns/workflow-queue")
        assert delete_response.status_code == 200
        
        # Verify deletion
        final_get_response = client.get("/servicebus/myns/workflow-queue")
        assert final_get_response.status_code == 404
