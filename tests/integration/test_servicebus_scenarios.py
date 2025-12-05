"""
End-to-End Scenario Tests for Service Bus

Complex integration scenarios testing combinations of features:
- Multi-subscription fan-out with different filters
- Concurrent operations on shared resources
- Session + topics integration
- Dead-letter queue scenarios
- Large message batches

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest
import asyncio
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor

from localzure.services.servicebus.api import router, backend


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
    return TestClient(app)


class TestComplexFanOutScenarios:
    """Tests for complex message fan-out scenarios."""
    
    def test_hierarchical_filtering(self, client):
        """Test hierarchical topic filtering with region, priority, and type filters."""
        # Create topic
        topic_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
        </TopicDescription>
    </content>
</entry>"""
        
        client.put(
            "/servicebus/test-namespace/topics/events",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        subscription_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
            <MaxDeliveryCount>10</MaxDeliveryCount>
        </SubscriptionDescription>
    </content>
</entry>"""
        
        # Create subscriptions with different filter combinations
        subscriptions = {
            "us-high": "region = 'us' AND priority = 'high'",
            "us-all": "region = 'us'",
            "high-all": "priority = 'high'",
            "orders-only": "message_type = 'order'",
        }
        
        for sub_name, filter_expr in subscriptions.items():
            client.put(
                f"/servicebus/test-namespace/topics/events/subscriptions/{sub_name}",
                content=subscription_xml,
                headers={"Content-Type": "application/xml"},
            )
            
            # Remove default rule and add SQL filter
            client.delete(f"/servicebus/test-namespace/topics/events/subscriptions/{sub_name}/rules/$Default")
            
            rule_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <Filter i:type="SqlFilter" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                <SqlExpression>{filter_expr}</SqlExpression>
            </Filter>
        </RuleDescription>
    </content>
</entry>"""
            
            client.put(
                f"/servicebus/test-namespace/topics/events/subscriptions/{sub_name}/rules/filter",
                content=rule_xml,
                headers={"Content-Type": "application/xml"},
            )
        
        # Send different messages
        messages = [
            {"body": "US High Order", "user_properties": {"region": "us", "priority": "high", "message_type": "order"}},
            {"body": "US Low Order", "user_properties": {"region": "us", "priority": "low", "message_type": "order"}},
            {"body": "EU High Order", "user_properties": {"region": "eu", "priority": "high", "message_type": "order"}},
            {"body": "US High Alert", "user_properties": {"region": "us", "priority": "high", "message_type": "alert"}},
        ]
        
        for msg in messages:
            client.post("/servicebus/test-namespace/topics/events/messages", json=msg)
        
        # Verify each subscription receives correct messages
        # us-high: Should receive US High Order, US High Alert (2 messages)
        response = client.post(
            "/servicebus/test-namespace/topics/events/subscriptions/us-high/messages/receive",
            json={"max_count": 10, "receive_mode": "PeekLock"},
        )
        us_high_messages = response.json()
        assert len(us_high_messages) == 2
        assert any("US High Order" in msg["Body"] for msg in us_high_messages)
        assert any("US High Alert" in msg["Body"] for msg in us_high_messages)
        
        # us-all: Should receive all US messages (3 messages)
        response = client.post(
            "/servicebus/test-namespace/topics/events/subscriptions/us-all/messages/receive",
            json={"max_count": 10, "receive_mode": "PeekLock"},
        )
        us_all_messages = response.json()
        assert len(us_all_messages) == 3
        
        # high-all: Should receive all high priority (3 messages)
        response = client.post(
            "/servicebus/test-namespace/topics/events/subscriptions/high-all/messages/receive",
            json={"max_count": 10, "receive_mode": "PeekLock"},
        )
        high_all_messages = response.json()
        assert len(high_all_messages) == 3
        
        # orders-only: Should receive all orders (3 messages)
        response = client.post(
            "/servicebus/test-namespace/topics/events/subscriptions/orders-only/messages/receive",
            json={"max_count": 10, "receive_mode": "PeekLock"},
        )
        orders_messages = response.json()
        assert len(orders_messages) == 3
    
    def test_broadcast_to_many_subscriptions(self, client):
        """Test broadcasting to 10+ subscriptions."""
        # Create topic
        topic_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
        </TopicDescription>
    </content>
</entry>"""
        
        client.put(
            "/servicebus/test-namespace/topics/broadcast",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        subscription_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </SubscriptionDescription>
    </content>
</entry>"""
        
        # Create 15 subscriptions (all with default TrueFilter)
        num_subscriptions = 15
        for i in range(num_subscriptions):
            client.put(
                f"/servicebus/test-namespace/topics/broadcast/subscriptions/sub-{i}",
                content=subscription_xml,
                headers={"Content-Type": "application/xml"},
            )
        
        # Send single message
        client.post(
            "/servicebus/test-namespace/topics/broadcast/messages",
            json={"body": "Broadcast message"},
        )
        
        # Verify all subscriptions received it
        for i in range(num_subscriptions):
            response = client.post(
                f"/servicebus/test-namespace/topics/broadcast/subscriptions/sub-{i}/messages/receive",
                json={"max_count": 1, "receive_mode": "PeekLock"},
            )
            messages = response.json()
            assert len(messages) == 1
            assert messages[0]["Body"] == "Broadcast message"


class TestConcurrentOperations:
    """Tests for concurrent operations."""
    
    def test_concurrent_sends_to_queue(self, client):
        """Test multiple concurrent sends to the same queue."""
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
            "/servicebus/test-namespace/concurrent-queue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send 50 messages concurrently
        def send_message(i):
            return client.post(
                "/servicebus/test-namespace/concurrent-queue/messages",
                json={"body": f"Message {i}"},
            )
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(send_message, range(50)))
        
        # Verify all sends succeeded
        assert all(r.status_code == status.HTTP_200_OK for r in results)
        
        # Receive all messages
        response = client.post(
            "/servicebus/test-namespace/concurrent-queue/messages/receive",
            json={"max_count": 100, "receive_mode": "PeekLock"},
        )
        
        messages = response.json()
        assert len(messages) == 50
    
    def test_concurrent_receives_from_queue(self, client):
        """Test multiple concurrent receives from the same queue."""
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
            "/servicebus/test-namespace/concurrent-queue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send 30 messages
        for i in range(30):
            client.post(
                "/servicebus/test-namespace/concurrent-queue/messages",
                json={"body": f"Message {i}"},
            )
        
        # Receive concurrently (10 threads, each requesting 5 messages)
        def receive_messages():
            return client.post(
                "/servicebus/test-namespace/concurrent-queue/messages/receive",
                json={"max_count": 5, "receive_mode": "PeekLock"},
            )
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(lambda _: receive_messages(), range(10)))
        
        # Collect all received messages
        all_messages = []
        for result in results:
            if result.status_code == status.HTTP_200_OK:
                all_messages.extend(result.json())
        
        # Verify all 30 messages received exactly once
        assert len(all_messages) == 30
        
        # Verify unique lock tokens (no duplicate receives)
        lock_tokens = [msg["LockToken"] for msg in all_messages]
        assert len(lock_tokens) == len(set(lock_tokens))


class TestSessionTopicIntegration:
    """Tests for sessions with topics."""
    
    def test_session_messages_to_topic(self, client):
        """Test sending session messages to topic and receiving from subscription."""
        # Create topic
        topic_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
        </TopicDescription>
    </content>
</entry>"""
        
        client.put(
            "/servicebus/test-namespace/topics/session-topic",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Create session-enabled subscription
        subscription_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <RequiresSession>true</RequiresSession>
            <LockDuration>PT60S</LockDuration>
        </SubscriptionDescription>
    </content>
</entry>"""
        
        client.put(
            "/servicebus/test-namespace/topics/session-topic/subscriptions/session-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send messages with different session IDs
        sessions = ["session-A", "session-B", "session-C"]
        for session_id in sessions:
            for i in range(3):
                client.post(
                    "/servicebus/test-namespace/topics/session-topic/messages",
                    json={
                        "body": f"Message {i} for {session_id}",
                        "session_id": session_id,
                    },
                )
        
        # Accept sessions and verify FIFO within each session
        for session_id in sessions:
            # Accept session
            accept_response = client.post(
                "/servicebus/test-namespace/topics/session-topic/subscriptions/session-sub/sessions/accept",
                json={"session_id": session_id},
            )
            assert accept_response.status_code == status.HTTP_200_OK
            session_data = accept_response.json()
            
            # Receive messages from session
            receive_response = client.post(
                "/servicebus/test-namespace/topics/session-topic/subscriptions/session-sub/messages/receive",
                json={"max_count": 10, "receive_mode": "PeekLock", "session_id": session_id},
            )
            messages = receive_response.json()
            
            # Verify correct session and FIFO order
            assert len(messages) == 3
            for i, msg in enumerate(messages):
                assert msg["SessionId"] == session_id
                assert f"Message {i}" in msg["Body"]


class TestDeadLetterScenarios:
    """Tests for dead-letter queue scenarios."""
    
    def test_max_delivery_count_to_dead_letter(self, client):
        """Test message moves to dead-letter after max delivery count."""
        # Create queue with MaxDeliveryCount=3
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT1S</LockDuration>
            <MaxDeliveryCount>3</MaxDeliveryCount>
        </QueueDescription>
    </content>
</entry>"""
        
        client.put(
            "/servicebus/test-namespace/dlq-test-queue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send message
        client.post(
            "/servicebus/test-namespace/dlq-test-queue/messages",
            json={"body": "Test message"},
        )
        
        # Abandon 3 times
        for _ in range(3):
            # Receive
            receive_response = client.post(
                "/servicebus/test-namespace/dlq-test-queue/messages/receive",
                json={"max_count": 1, "receive_mode": "PeekLock"},
            )
            messages = receive_response.json()
            
            if len(messages) > 0:
                lock_token = messages[0]["LockToken"]
                
                # Abandon
                client.post(
                    "/servicebus/test-namespace/dlq-test-queue/messages/abandon",
                    json={"lock_token": lock_token},
                )
            
            # Wait for lock to expire
            import time
            time.sleep(1.5)
        
        # Try to receive again - should be no messages in main queue
        receive_response = client.post(
            "/servicebus/test-namespace/dlq-test-queue/messages/receive",
            json={"max_count": 1, "receive_mode": "PeekLock"},
        )
        messages = receive_response.json()
        assert len(messages) == 0
        
        # Check dead-letter queue
        dlq_response = client.post(
            "/servicebus/test-namespace/dlq-test-queue/$deadletterqueue/messages/receive",
            json={"max_count": 1, "receive_mode": "PeekLock"},
        )
        dlq_messages = dlq_response.json()
        assert len(dlq_messages) == 1
        assert dlq_messages[0]["Body"] == "Test message"


class TestBatchOperations:
    """Tests for large batch operations."""
    
    def test_send_large_batch_to_queue(self, client):
        """Test sending a large batch of messages."""
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
            "/servicebus/test-namespace/batch-queue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send 200 messages
        for i in range(200):
            response = client.post(
                "/servicebus/test-namespace/batch-queue/messages",
                json={"body": f"Message {i}"},
            )
            assert response.status_code == status.HTTP_200_OK
        
        # Receive in batches
        all_messages = []
        for _ in range(20):  # 20 batches of 10
            response = client.post(
                "/servicebus/test-namespace/batch-queue/messages/receive",
                json={"max_count": 10, "receive_mode": "PeekLock"},
            )
            all_messages.extend(response.json())
        
        assert len(all_messages) == 200
    
    def test_fan_out_large_batch(self, client):
        """Test fan-out of large batch to multiple subscriptions."""
        # Create topic
        topic_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
        </TopicDescription>
    </content>
</entry>"""
        
        client.put(
            "/servicebus/test-namespace/topics/batch-topic",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        subscription_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </SubscriptionDescription>
    </content>
</entry>"""
        
        # Create 5 subscriptions
        for i in range(5):
            client.put(
                f"/servicebus/test-namespace/topics/batch-topic/subscriptions/sub-{i}",
                content=subscription_xml,
                headers={"Content-Type": "application/xml"},
            )
        
        # Send 100 messages
        for i in range(100):
            client.post(
                "/servicebus/test-namespace/topics/batch-topic/messages",
                json={"body": f"Message {i}"},
            )
        
        # Verify each subscription received all 100 messages
        for i in range(5):
            all_messages = []
            for _ in range(10):  # 10 batches of 10
                response = client.post(
                    f"/servicebus/test-namespace/topics/batch-topic/subscriptions/sub-{i}/messages/receive",
                    json={"max_count": 10, "receive_mode": "PeekLock"},
                )
                all_messages.extend(response.json())
            
            assert len(all_messages) == 100
