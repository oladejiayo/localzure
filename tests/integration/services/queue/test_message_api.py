"""
Integration tests for Queue Storage message API endpoints.

Tests message put, get, peek, update, delete via HTTP API.

Author: Ayodele Oladeji
Date: 2025
"""

import base64
import pytest
from urllib.parse import quote
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


class TestPutMessage:
    """Tests for PUT message endpoint."""
    
    def test_put_message_basic(self, client):
        """Test putting a basic message."""
        # Create queue first
        client.put("/queue/testaccount/myqueue")
        
        # Put message
        message_text = base64.b64encode("Hello, World!".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        response = client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 201
        assert "<MessageId>" in response.text
        assert "<InsertionTime>" in response.text
        assert "<ExpirationTime>" in response.text
        assert "<PopReceipt>" in response.text
        assert "<TimeNextVisible>" in response.text
    
    def test_put_message_with_visibility_timeout(self, client):
        """Test putting message with visibility timeout."""
        client.put("/queue/testaccount/myqueue")
        
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        response = client.post(
            "/queue/testaccount/myqueue/messages?visibilitytimeout=60",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 201
    
    def test_put_message_with_ttl(self, client):
        """Test putting message with custom TTL."""
        client.put("/queue/testaccount/myqueue")
        
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        response = client.post(
            "/queue/testaccount/myqueue/messages?messagettl=3600",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 201
    
    def test_put_message_empty_text(self, client):
        """Test putting message with empty text."""
        client.put("/queue/testaccount/myqueue")
        
        xml_body = '<QueueMessage><MessageText></MessageText></QueueMessage>'
        response = client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 400
        assert "InvalidMessageContent" in response.text
    
    def test_put_message_queue_not_found(self, client):
        """Test putting message to non-existent queue."""
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        response = client.post(
            "/queue/testaccount/nonexistent/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 404
        assert "QueueNotFound" in response.text


class TestGetMessages:
    """Tests for GET messages endpoint."""
    
    def test_get_messages_empty_queue(self, client):
        """Test getting messages from empty queue."""
        client.put("/queue/testaccount/myqueue")
        
        response = client.get("/queue/testaccount/myqueue/messages")
        
        assert response.status_code == 200
        assert "<QueueMessagesList" in response.text
    
    def test_get_single_message(self, client):
        """Test getting a single message."""
        # Create queue and add message
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Test Message".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Get messages
        response = client.get("/queue/testaccount/myqueue/messages")
        
        assert response.status_code == 200
        assert "<MessageId>" in response.text
        assert "<PopReceipt>" in response.text
        assert "<TimeNextVisible>" in response.text
        assert "<DequeueCount>1</DequeueCount>" in response.text
        assert f"<MessageText>{message_text}</MessageText>" in response.text
    
    def test_get_multiple_messages(self, client):
        """Test getting multiple messages."""
        client.put("/queue/testaccount/myqueue")
        
        # Add 3 messages
        for i in range(3):
            message_text = base64.b64encode(f"Msg{i}".encode('utf-8')).decode('utf-8')
            xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
            client.post(
                "/queue/testaccount/myqueue/messages",
                content=xml_body,
                headers={"Content-Type": "application/xml"},
            )
        
        # Get all messages
        response = client.get("/queue/testaccount/myqueue/messages?numofmessages=3")
        
        assert response.status_code == 200
        # Should have 3 QueueMessage elements
        assert response.text.count("<QueueMessage>") == 3
    
    def test_get_messages_with_visibility_timeout(self, client):
        """Test getting messages with custom visibility timeout."""
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Get with 60 second visibility timeout
        response = client.get("/queue/testaccount/myqueue/messages?visibilitytimeout=60")
        
        assert response.status_code == 200
        assert "<TimeNextVisible>" in response.text
        
        # Try to get again - should be empty (message hidden)
        response2 = client.get("/queue/testaccount/myqueue/messages")
        assert response2.text.count("<QueueMessage>") == 0
    
    def test_get_messages_increments_dequeue_count(self, client):
        """Test that dequeue count increments."""
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Get first time - sets visibility=0 so message is immediately visible again
        response1 = client.get("/queue/testaccount/myqueue/messages?visibilitytimeout=0")
        assert "<DequeueCount>1</DequeueCount>" in response1.text
        
        # Get second time - should retrieve same message with incremented count
        response2 = client.get("/queue/testaccount/myqueue/messages?visibilitytimeout=0")
        assert "<DequeueCount>2</DequeueCount>" in response2.text
        
        # Third time to verify continues incrementing
        response3 = client.get("/queue/testaccount/myqueue/messages?visibilitytimeout=0")
        assert "<DequeueCount>3</DequeueCount>" in response3.text
    
    def test_get_messages_queue_not_found(self, client):
        """Test getting messages from non-existent queue."""
        response = client.get("/queue/testaccount/nonexistent/messages")
        
        assert response.status_code == 404
        assert "QueueNotFound" in response.text


class TestPeekMessages:
    """Tests for peek messages endpoint."""
    
    def test_peek_messages(self, client):
        """Test peeking at messages."""
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Peek at messages
        response = client.get("/queue/testaccount/myqueue/messages?peekonly=true")
        
        assert response.status_code == 200
        assert "<MessageId>" in response.text
        assert "<PopReceipt>" not in response.text  # Pop receipt not included in peek
        assert "<TimeNextVisible>" not in response.text
        assert "<DequeueCount>0</DequeueCount>" in response.text  # Not incremented
    
    def test_peek_does_not_change_visibility(self, client):
        """Test that peek doesn't change message visibility."""
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Peek
        peek_response = client.get("/queue/testaccount/myqueue/messages?peekonly=true")
        assert "<DequeueCount>0</DequeueCount>" in peek_response.text
        
        # Peek again - dequeue count should still be 0
        peek_response2 = client.get("/queue/testaccount/myqueue/messages?peekonly=true")
        assert "<DequeueCount>0</DequeueCount>" in peek_response2.text
    
    def test_peek_multiple_messages(self, client):
        """Test peeking at multiple messages."""
        client.put("/queue/testaccount/myqueue")
        
        for i in range(3):
            message_text = base64.b64encode(f"Msg{i}".encode('utf-8')).decode('utf-8')
            xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
            client.post(
                "/queue/testaccount/myqueue/messages",
                content=xml_body,
                headers={"Content-Type": "application/xml"},
            )
        
        response = client.get("/queue/testaccount/myqueue/messages?peekonly=true&numofmessages=3")
        
        assert response.status_code == 200
        assert response.text.count("<QueueMessage>") == 3


class TestUpdateMessage:
    """Tests for update message endpoint."""
    
    def test_update_message_visibility(self, client):
        """Test updating message visibility timeout."""
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Get message
        get_response = client.get("/queue/testaccount/myqueue/messages")
        # Parse message ID and pop receipt from XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(get_response.text)
        message_elem = root.find("QueueMessage")
        message_id = message_elem.find("MessageId").text
        pop_receipt = message_elem.find("PopReceipt").text
        
        # Update message
        response = client.put(
            f"/queue/testaccount/myqueue/messages/{message_id}?popreceipt={quote(pop_receipt)}&visibilitytimeout=60"
        )
        
        assert response.status_code == 204
        assert "x-ms-popreceipt" in response.headers
    
    def test_update_message_text(self, client):
        """Test updating message text."""
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Original".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Get message
        get_response = client.get("/queue/testaccount/myqueue/messages?visibilitytimeout=0")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(get_response.text)
        message_elem = root.find("QueueMessage")
        message_id = message_elem.find("MessageId").text
        pop_receipt = message_elem.find("PopReceipt").text
        
        # Update with new text
        new_text = base64.b64encode("Updated".encode('utf-8')).decode('utf-8')
        update_xml = f'<QueueMessage><MessageText>{new_text}</MessageText></QueueMessage>'
        response = client.put(
            f"/queue/testaccount/myqueue/messages/{message_id}?popreceipt={quote(pop_receipt)}&visibilitytimeout=0",
            content=update_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == 204
        
        # Verify text changed
        peek_response = client.get("/queue/testaccount/myqueue/messages?peekonly=true")
        assert f"<MessageText>{new_text}</MessageText>" in peek_response.text
    
    def test_update_message_invalid_pop_receipt(self, client):
        """Test updating with invalid pop receipt."""
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Get message
        get_response = client.get("/queue/testaccount/myqueue/messages")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(get_response.text)
        message_elem = root.find("QueueMessage")
        message_id = message_elem.find("MessageId").text
        
        # Try to update with invalid receipt
        response = client.put(
            f"/queue/testaccount/myqueue/messages/{message_id}?popreceipt={quote('invalid')}&visibilitytimeout=30"
        )
        
        assert response.status_code == 400
        assert "InvalidPopReceipt" in response.text
    
    def test_update_message_not_found(self, client):
        """Test updating non-existent message."""
        client.put("/queue/testaccount/myqueue")
        
        response = client.put(
            "/queue/testaccount/myqueue/messages/nonexistent?popreceipt=receipt&visibilitytimeout=30"
        )
        
        assert response.status_code == 404
        assert "MessageNotFound" in response.text
    
    def test_update_message_queue_not_found(self, client):
        """Test updating message in non-existent queue."""
        response = client.put(
            "/queue/testaccount/nonexistent/messages/msg-id?popreceipt=receipt&visibilitytimeout=30"
        )
        
        assert response.status_code == 404
        assert "QueueNotFound" in response.text


class TestDeleteMessage:
    """Tests for delete message endpoint."""
    
    def test_delete_message(self, client):
        """Test deleting a message."""
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Get message
        get_response = client.get("/queue/testaccount/myqueue/messages")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(get_response.text)
        message_elem = root.find("QueueMessage")
        message_id = message_elem.find("MessageId").text
        pop_receipt = message_elem.find("PopReceipt").text
        
        # Delete message
        response = client.delete(
            f"/queue/testaccount/myqueue/messages/{message_id}?popreceipt={quote(pop_receipt)}"
        )
        
        assert response.status_code == 204
        
        # Verify message is gone
        peek_response = client.get("/queue/testaccount/myqueue/messages?peekonly=true")
        assert peek_response.text.count("<QueueMessage>") == 0
    
    def test_delete_message_invalid_pop_receipt(self, client):
        """Test deleting with invalid pop receipt."""
        client.put("/queue/testaccount/myqueue")
        message_text = base64.b64encode("Test".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        # Get message
        get_response = client.get("/queue/testaccount/myqueue/messages")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(get_response.text)
        message_elem = root.find("QueueMessage")
        message_id = message_elem.find("MessageId").text
        
        # Try to delete with invalid receipt
        response = client.delete(
            f"/queue/testaccount/myqueue/messages/{message_id}?popreceipt={quote('invalid')}"
        )
        
        assert response.status_code == 400
        assert "InvalidPopReceipt" in response.text
    
    def test_delete_message_not_found(self, client):
        """Test deleting non-existent message."""
        client.put("/queue/testaccount/myqueue")
        
        response = client.delete(
            "/queue/testaccount/myqueue/messages/nonexistent?popreceipt=receipt"
        )
        
        assert response.status_code == 404
        assert "MessageNotFound" in response.text
    
    def test_delete_message_queue_not_found(self, client):
        """Test deleting message from non-existent queue."""
        response = client.delete(
            "/queue/testaccount/nonexistent/messages/msg-id?popreceipt=receipt"
        )
        
        assert response.status_code == 404
        assert "QueueNotFound" in response.text


class TestMessageWorkflows:
    """Integration tests for complete message workflows."""
    
    def test_complete_message_lifecycle(self, client):
        """Test put -> get -> update -> delete workflow."""
        # Create queue
        client.put("/queue/testaccount/myqueue")
        
        # Put message
        message_text = base64.b64encode("Original Message".encode('utf-8')).decode('utf-8')
        xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
        put_response = client.post(
            "/queue/testaccount/myqueue/messages",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        assert put_response.status_code == 201
        
        # Get message
        get_response = client.get("/queue/testaccount/myqueue/messages?visibilitytimeout=0")
        assert get_response.status_code == 200
        
        import xml.etree.ElementTree as ET
        root = ET.fromstring(get_response.text)
        message_elem = root.find("QueueMessage")
        message_id = message_elem.find("MessageId").text
        pop_receipt = message_elem.find("PopReceipt").text
        
        # Update message
        new_text = base64.b64encode("Updated Message".encode('utf-8')).decode('utf-8')
        update_xml = f'<QueueMessage><MessageText>{new_text}</MessageText></QueueMessage>'
        update_response = client.put(
            f"/queue/testaccount/myqueue/messages/{message_id}?popreceipt={quote(pop_receipt)}&visibilitytimeout=0",
            content=update_xml,
            headers={"Content-Type": "application/xml"},
        )
        assert update_response.status_code == 204
        new_pop_receipt = update_response.headers["x-ms-popreceipt"]
        
        # Delete message
        delete_response = client.delete(
            f"/queue/testaccount/myqueue/messages/{message_id}?popreceipt={quote(new_pop_receipt)}"
        )
        assert delete_response.status_code == 204
        
        # Verify gone
        peek_response = client.get("/queue/testaccount/myqueue/messages?peekonly=true")
        assert peek_response.text.count("<QueueMessage>") == 0
    
    def test_batch_operations(self, client):
        """Test adding and retrieving multiple messages."""
        client.put("/queue/testaccount/myqueue")
        
        # Add 5 messages
        for i in range(5):
            message_text = base64.b64encode(f"Message {i}".encode('utf-8')).decode('utf-8')
            xml_body = f'<QueueMessage><MessageText>{message_text}</MessageText></QueueMessage>'
            response = client.post(
                "/queue/testaccount/myqueue/messages",
                content=xml_body,
                headers={"Content-Type": "application/xml"},
            )
            assert response.status_code == 201
        
        # Get 3 messages (makes them invisible)
        response = client.get("/queue/testaccount/myqueue/messages?numofmessages=3")
        assert response.status_code == 200
        assert response.text.count("<QueueMessage>") == 3
        
        # Peek at remaining visible messages (should be 2, since 3 are hidden)
        peek_response = client.get("/queue/testaccount/myqueue/messages?peekonly=true&numofmessages=32")
        # In Azure Queue Storage, peek only shows visible messages (not hidden by get)
        assert peek_response.text.count("<QueueMessage>") == 2
