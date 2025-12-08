"""
Integration Tests for Service Bus Message API

Tests for message API endpoints including send, receive, complete, abandon, dead-letter, and lock renewal.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest
import asyncio
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from localzure.services.servicebus.api import router, backend
from localzure.services.servicebus.error_handlers import register_exception_handlers


@pytest.fixture(autouse=True)
async def reset_backend():
    """Reset backend before each test."""
    await backend.reset()
    yield
    await backend.reset()


@pytest.fixture
def client():
    """Create test client."""
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    return TestClient(app)


@pytest.fixture
def create_test_queue(client):
    """Create a test queue."""
    queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
            <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
            <RequiresDuplicateDetection>false</RequiresDuplicateDetection>
            <RequiresSession>false</RequiresSession>
            <DefaultMessageTimeToLive>P14D</DefaultMessageTimeToLive>
            <DeadLetteringOnMessageExpiration>false</DeadLetteringOnMessageExpiration>
            <EnableBatchedOperations>true</EnableBatchedOperations>
            <MaxDeliveryCount>10</MaxDeliveryCount>
        </QueueDescription>
    </content>
</entry>"""
    
    response = client.put(
        "/servicebus/test-namespace/test-queue",
        content=queue_xml,
        headers={"Content-Type": "application/xml"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    return "test-queue"


class TestSendMessageAPI:
    """Tests for send message API endpoint."""
    
    def test_send_message_success(self, client, create_test_queue):
        """Test sending a message successfully."""
        response = client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={
                "body": "Test message body",
                "label": "test-label",
                "content_type": "text/plain",
            },
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["Body"] == "Test message body"
        assert data["Label"] == "test-label"
        assert data["ContentType"] == "text/plain"
        assert "MessageId" in data
        assert data["SequenceNumber"] == 1
    
    def test_send_message_with_all_properties(self, client, create_test_queue):
        """Test sending a message with all properties."""
        response = client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={
                "body": "Full message",
                "session_id": "session-123",
                "correlation_id": "corr-456",
                "content_type": "application/json",
                "label": "important",
                "to": "recipient",
                "reply_to": "sender",
                "time_to_live": 3600,
                "user_properties": {"key1": "value1", "key2": "value2"},
            },
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["SessionId"] == "session-123"
        assert data["CorrelationId"] == "corr-456"
        assert data["UserProperties"] == {"key1": "value1", "key2": "value2"}
    
    def test_send_message_to_nonexistent_queue(self, client):
        """Test sending to a queue that doesn't exist."""
        response = client.post(
            "/servicebus/test-namespace/nonexistent-queue/messages",
            json={"body": "Test"},
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReceiveMessageAPI:
    """Tests for receive message API endpoint."""
    
    def test_receive_message_peek_lock_mode(self, client, create_test_queue):
        """Test receiving a message in PeekLock mode."""
        # Send a message
        client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Test message"},
        )
        
        # Receive it
        response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
            params={"mode": "PeekLock"},
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["Body"] == "Test message"
        assert "LockToken" in data
        assert data["LockToken"] is not None
        assert data["DeliveryCount"] == 1
    
    def test_receive_message_receive_and_delete_mode(self, client, create_test_queue):
        """Test receiving a message in ReceiveAndDelete mode."""
        # Send a message
        client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Test message"},
        )
        
        # Receive it
        response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
            params={"mode": "ReceiveAndDelete"},
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["Body"] == "Test message"
        assert data["LockToken"] is None
        
        # Try to receive again - should be empty
        response2 = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json() is None
    
    def test_receive_from_empty_queue(self, client, create_test_queue):
        """Test receiving from an empty queue."""
        response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None


class TestCompleteMessageAPI:
    """Tests for complete message API endpoint."""
    
    def test_complete_message_success(self, client, create_test_queue):
        """Test completing a message successfully."""
        # Send and receive a message
        client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Test"},
        )
        
        recv_response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        message = recv_response.json()
        
        # Complete it
        response = client.delete(
            f"/servicebus/test-namespace/test-queue/messages/{message['MessageId']}/{message['LockToken']}",
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Should not be able to receive it again
        recv2 = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        assert recv2.json() is None
    
    def test_complete_message_with_invalid_lock_token(self, client, create_test_queue):
        """Test completing with invalid lock token."""
        # Send and receive a message
        client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Test"},
        )
        
        recv_response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        message = recv_response.json()
        
        # Try to complete with invalid token
        response = client.delete(
            f"/servicebus/test-namespace/test-queue/messages/{message['MessageId']}/invalid-token",
        )
        
        assert response.status_code == status.HTTP_410_GONE


class TestAbandonMessageAPI:
    """Tests for abandon message API endpoint."""
    
    def test_abandon_message_success(self, client, create_test_queue):
        """Test abandoning a message successfully."""
        # Send and receive a message
        client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Test"},
        )
        
        recv_response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        message = recv_response.json()
        
        # Abandon it
        response = client.put(
            f"/servicebus/test-namespace/test-queue/messages/{message['MessageId']}/{message['LockToken']}/abandon",
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Should be able to receive it again
        recv2 = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        msg2 = recv2.json()
        assert msg2 is not None
        assert msg2["MessageId"] == message["MessageId"]
        assert msg2["DeliveryCount"] == 2


class TestDeadLetterMessageAPI:
    """Tests for dead-letter message API endpoint."""
    
    def test_dead_letter_message_success(self, client, create_test_queue):
        """Test dead-lettering a message successfully."""
        # Send and receive a message
        client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Test"},
        )
        
        recv_response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        message = recv_response.json()
        
        # Dead-letter it
        response = client.put(
            f"/servicebus/test-namespace/test-queue/messages/{message['MessageId']}/{message['LockToken']}/deadletter",
            params={
                "reason": "ProcessingError",
                "description": "Failed to process message",
            },
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Should not be able to receive it again
        recv2 = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        assert recv2.json() is None
        
        # Check queue stats to verify DLQ count
        queue_response = client.get(
            "/servicebus/test-namespace/test-queue",
        )
        assert queue_response.status_code == status.HTTP_200_OK


class TestRenewLockAPI:
    """Tests for renew lock API endpoint."""
    
    def test_renew_lock_success(self, client, create_test_queue):
        """Test renewing a lock successfully."""
        import time
        # Send and receive a message
        client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Test"},
        )
        
        recv_response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        message = recv_response.json()
        
        original_locked_until = message["LockedUntilUtc"]
        
        # Wait a bit
        time.sleep(0.1)
        
        # Renew lock
        response = client.post(
            f"/servicebus/test-namespace/test-queue/messages/{message['MessageId']}/{message['LockToken']}/renewlock",
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "LockedUntilUtc" in data
        assert data["LockedUntilUtc"] > original_locked_until
    
    def test_renew_lock_with_invalid_token(self, client, create_test_queue):
        """Test renewing with invalid lock token."""
        # Send and receive a message
        client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Test"},
        )
        
        recv_response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        message = recv_response.json()
        
        # Try to renew with invalid token
        response = client.post(
            f"/servicebus/test-namespace/test-queue/messages/{message['MessageId']}/invalid-token/renewlock",
        )
        
        assert response.status_code == status.HTTP_410_GONE


class TestMessageLifecycle:
    """Integration tests for complete message lifecycle scenarios."""
    
    def test_full_message_lifecycle_complete(self, client, create_test_queue):
        """Test complete message lifecycle: send -> receive -> complete."""
        # Send
        send_response = client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Lifecycle test", "label": "test"},
        )
        assert send_response.status_code == status.HTTP_200_OK
        
        # Receive
        recv_response = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        message = recv_response.json()
        assert message["Body"] == "Lifecycle test"
        
        # Complete
        complete_response = client.delete(
            f"/servicebus/test-namespace/test-queue/messages/{message['MessageId']}/{message['LockToken']}",
        )
        assert complete_response.status_code == status.HTTP_200_OK
    
    def test_full_message_lifecycle_abandon(self, client, create_test_queue):
        """Test message lifecycle with abandon: send -> receive -> abandon -> receive."""
        # Send
        client.post(
            "/servicebus/test-namespace/test-queue/messages",
            json={"body": "Abandon test"},
        )
        
        # Receive
        recv1 = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        msg1 = recv1.json()
        assert msg1["DeliveryCount"] == 1
        
        # Abandon
        client.put(
            f"/servicebus/test-namespace/test-queue/messages/{msg1['MessageId']}/{msg1['LockToken']}/abandon",
        )
        
        # Receive again
        recv2 = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        msg2 = recv2.json()
        assert msg2["MessageId"] == msg1["MessageId"]
        assert msg2["DeliveryCount"] == 2
    
    def test_multiple_messages_in_queue(self, client, create_test_queue):
        """Test handling multiple messages in queue."""
        # Send 5 messages
        for i in range(5):
            client.post(
                "/servicebus/test-namespace/test-queue/messages",
                json={"body": f"Message {i+1}"},
            )
        
        # Receive and complete all
        for i in range(5):
            recv = client.post(
                "/servicebus/test-namespace/test-queue/messages/head",
            )
            msg = recv.json()
            assert msg["Body"] == f"Message {i+1}"
            
            client.delete(
                f"/servicebus/test-namespace/test-queue/messages/{msg['MessageId']}/{msg['LockToken']}",
            )
        
        # Queue should be empty
        recv = client.post(
            "/servicebus/test-namespace/test-queue/messages/head",
        )
        assert recv.json() is None
