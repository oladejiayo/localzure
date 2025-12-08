"""
Integration Tests for Service Bus Error Handling

Tests for API error responses and exception handling.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from localzure.services.servicebus.api import router, backend
from localzure.services.servicebus.error_handlers import register_exception_handlers
from localzure.services.servicebus.error_handlers import register_exception_handlers


@pytest.fixture(autouse=True, scope="function")
async def reset_backend():
    """Reset backend before and after each test."""
    await backend.reset()
    yield
    await backend.reset()


@pytest.fixture
def client():
    """Create test client with exception handlers."""
    from localzure.services.servicebus.logging_utils import CorrelationContext
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class CorrelationIDMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # Extract correlation ID from header or generate new one
            correlation_id = request.headers.get("x-correlation-id")
            if correlation_id:
                CorrelationContext.set_correlation_id(correlation_id)
            response = await call_next(request)
            return response
    
    app = FastAPI()
    app.add_middleware(CorrelationIDMiddleware)
    app.include_router(router)
    register_exception_handlers(app)  # Register at app level
    return TestClient(app)


class TestEntityNotFoundErrors:
    """Tests for entity not found error responses."""
    
    def test_queue_not_found(self, client):
        """Test queue not found returns 404."""
        response = client.get("/servicebus/test-ns/nonexistent-queue")
        
        assert response.status_code == 404
        data = response.json()
        
        assert "error" in data
        assert data["error"]["code"] == "EntityNotFound"
        assert "nonexistent-queue" in data["error"]["message"]
        assert data["error"]["details"]["entity_type"] == "queue"
        assert data["error"]["details"]["entity_name"] == "nonexistent-queue"
        assert "correlation_id" in data["error"]["details"]
    
    def test_topic_not_found(self, client):
        """Test topic not found returns 404."""
        response = client.get("/servicebus/test-ns/topics/nonexistent-topic")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["error"]["code"] == "EntityNotFound"
        assert "nonexistent-topic" in data["error"]["message"]
        assert data["error"]["details"]["entity_type"] == "topic"
    
    def test_subscription_not_found(self, client):
        """Test subscription not found returns 404."""
        # Create topic first
        topic_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
        </TopicDescription>
    </content>
</entry>"""
        
        client.put(
            "/servicebus/test-ns/topics/mytopic",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Try to get nonexistent subscription
        response = client.get("/servicebus/test-ns/topics/mytopic/subscriptions/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["error"]["code"] == "EntityNotFound"
        assert "nonexistent" in data["error"]["message"]


class TestEntityAlreadyExistsErrors:
    """Tests for entity already exists error responses."""
    
    def test_queue_already_exists(self, client):
        """Test queue PUT is idempotent (create-or-update)."""
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        # Create queue
        response1 = client.put(
            "/servicebus/test-ns/myqueue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        assert response1.status_code == 201  # Created
        
        # PUT again - should update (idempotent)
        response2 = client.put(
            "/servicebus/test-ns/myqueue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Azure Service Bus PUT is idempotent (create-or-update)
        assert response2.status_code == 200  # OK (updated)
    
    def test_topic_already_exists(self, client):
        """Test topic PUT is idempotent (create-or-update)."""
        topic_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
        </TopicDescription>
    </content>
</entry>"""
        
        # Create topic
        response1 = client.put(
            "/servicebus/test-ns/topics/mytopic",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        assert response1.status_code in [200, 201]  # Created or already exists
        
        # PUT again - should update (idempotent)
        response2 = client.put(
            "/servicebus/test-ns/topics/mytopic",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Azure Service Bus PUT is idempotent (create-or-update)
        assert response2.status_code == 200  # OK (updated)


class TestInvalidEntityNameErrors:
    """Tests for invalid entity name error responses."""
    
    def test_invalid_queue_name_too_long(self, client):
        """Test invalid queue name (too long) returns 400."""
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        # Try to create queue with invalid name (too long)
        long_name = "a" * 300
        response = client.put(
            f"/servicebus/test-ns/{long_name}",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["error"]["code"] == "InvalidEntityName"
        assert data["error"]["details"]["entity_type"] == "queue"
    
    def test_invalid_queue_name_special_chars(self, client):
        """Test invalid queue name (special chars) returns 400."""
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        # Try to create queue with special characters
        response = client.put(
            "/servicebus/test-ns/invalid@name!",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["error"]["code"] == "InvalidEntityName"


class TestMessageErrors:
    """Tests for message-related error responses."""
    
    def test_message_not_found(self, client):
        """Test invalid message lock token returns 410 Gone."""
        # Create queue
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        client.put(
            "/servicebus/test-ns/myqueue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Try to complete with invalid lock token (message never received)
        response = client.delete(
            "/servicebus/test-ns/myqueue/messages/nonexistent-message-id/fake-lock-token"
        )
        
        # Invalid lock token returns 410 Gone (lock lost)
        assert response.status_code == 410
        data = response.json()
        
        assert data["error"]["code"] == "MessageLockLost"
        assert "lock token" in data["error"]["message"].lower()


class TestCorrelationIDPropagation:
    """Tests for correlation ID propagation in errors."""
    
    def test_correlation_id_in_error_response(self, client):
        """Test correlation ID is included in error response."""
        response = client.get(
            "/servicebus/test-ns/nonexistent",
            headers={"x-correlation-id": "test-correlation-123"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["error"]["details"]["correlation_id"] == "test-correlation-123"
    
    def test_generated_correlation_id_in_error(self, client):
        """Test generated correlation ID is included if not provided."""
        response = client.get("/servicebus/test-ns/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        
        assert "correlation_id" in data["error"]["details"]
        # Should be a UUID
        correlation_id = data["error"]["details"]["correlation_id"]
        assert len(correlation_id) == 36  # UUID format


class TestErrorResponseFormat:
    """Tests for standardized error response format."""
    
    def test_error_response_structure(self, client):
        """Test error response has correct structure."""
        response = client.get("/servicebus/test-ns/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        
        # Check top-level structure
        assert "error" in data
        assert set(data.keys()) == {"error"}
        
        # Check error structure
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "details" in error
        
        # Check details structure
        details = error["details"]
        assert isinstance(details, dict)
        assert "correlation_id" in details
    
    def test_error_details_contain_context(self, client):
        """Test error details contain contextual information."""
        response = client.get("/servicebus/test-ns/nonexistent-queue")
        
        assert response.status_code == 404
        data = response.json()
        
        details = data["error"]["details"]
        assert details["entity_type"] == "queue"
        assert details["entity_name"] == "nonexistent-queue"


class TestMultipleErrorScenarios:
    """Tests for various error scenarios in sequence."""
    
    def test_multiple_errors_have_different_correlation_ids(self, client):
        """Test each request gets unique correlation ID."""
        response1 = client.get("/servicebus/test-ns/queue1")
        response2 = client.get("/servicebus/test-ns/queue2")
        
        correlation_id1 = response1.json()["error"]["details"]["correlation_id"]
        correlation_id2 = response2.json()["error"]["details"]["correlation_id"]
        
        assert correlation_id1 != correlation_id2
    
    def test_same_correlation_id_preserved(self, client):
        """Test provided correlation ID is preserved."""
        correlation_id = "my-trace-id"
        
        response = client.get(
            "/servicebus/test-ns/nonexistent",
            headers={"x-correlation-id": correlation_id}
        )
        
        assert response.json()["error"]["details"]["correlation_id"] == correlation_id
