"""
Integration Tests for Service Bus Topics and Subscriptions API

Tests for topic/subscription/rule HTTP API endpoints including CRUD operations,
message fan-out, and filter evaluation.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest
import asyncio
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

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


@pytest.fixture
def topic_xml():
    """Default topic XML for creation."""
    return """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
            <RequiresDuplicateDetection>false</RequiresDuplicateDetection>
            <DefaultMessageTimeToLive>P14D</DefaultMessageTimeToLive>
            <EnableBatchedOperations>true</EnableBatchedOperations>
        </TopicDescription>
    </content>
</entry>"""


@pytest.fixture
def subscription_xml():
    """Default subscription XML for creation."""
    return """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
            <RequiresSession>false</RequiresSession>
            <DefaultMessageTimeToLive>P14D</DefaultMessageTimeToLive>
            <DeadLetteringOnMessageExpiration>false</DeadLetteringOnMessageExpiration>
            <MaxDeliveryCount>10</MaxDeliveryCount>
        </SubscriptionDescription>
    </content>
</entry>"""


@pytest.fixture
def create_test_topic(client, topic_xml):
    """Create a test topic."""
    response = client.put(
        "/servicebus/test-namespace/topics/test-topic",
        content=topic_xml,
        headers={"Content-Type": "application/xml"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    return "test-topic"


class TestTopicCRUDAPI:
    """Tests for topic CRUD API endpoints."""
    
    def test_create_topic_success(self, client, topic_xml):
        """Test creating a topic successfully."""
        response = client.put(
            "/servicebus/test-namespace/topics/my-topic",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert "my-topic" in response.text
        assert "TopicDescription" in response.text
    
    def test_create_topic_already_exists(self, client, topic_xml):
        """Test creating a topic that already exists returns 200."""
        # Create first time
        client.put(
            "/servicebus/test-namespace/topics/my-topic",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Create again
        response = client.put(
            "/servicebus/test-namespace/topics/my-topic",
            content=topic_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_list_topics_empty(self, client):
        """Test listing topics when none exist."""
        response = client.get("/servicebus/test-namespace/topics")
        
        assert response.status_code == status.HTTP_200_OK
        assert "feed" in response.text.lower()
    
    def test_list_topics_with_data(self, client, topic_xml):
        """Test listing topics with multiple topics."""
        # Create multiple topics
        for i in range(3):
            client.put(
                f"/servicebus/test-namespace/topics/topic-{i}",
                content=topic_xml,
                headers={"Content-Type": "application/xml"},
            )
        
        response = client.get("/servicebus/test-namespace/topics")
        
        assert response.status_code == status.HTTP_200_OK
        assert "topic-0" in response.text
        assert "topic-1" in response.text
        assert "topic-2" in response.text
    
    def test_get_topic_success(self, client, create_test_topic):
        """Test getting a topic successfully."""
        response = client.get("/servicebus/test-namespace/topics/test-topic")
        
        assert response.status_code == status.HTTP_200_OK
        assert "test-topic" in response.text
        assert "TopicDescription" in response.text
    
    def test_get_topic_not_found(self, client):
        """Test getting a non-existent topic."""
        response = client.get("/servicebus/test-namespace/topics/nonexistent")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_topic_success(self, client, create_test_topic):
        """Test updating a topic successfully."""
        update_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>2048</MaxSizeInMegabytes>
            <DefaultMessageTimeToLive>P7D</DefaultMessageTimeToLive>
        </TopicDescription>
    </content>
</entry>"""
        
        response = client.put(
            "/servicebus/test-namespace/topics/test-topic",
            content=update_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert "2048" in response.text
    
    def test_delete_topic_success(self, client, create_test_topic):
        """Test deleting a topic successfully."""
        response = client.delete("/servicebus/test-namespace/topics/test-topic")
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify topic is gone
        get_response = client.get("/servicebus/test-namespace/topics/test-topic")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_topic_not_found(self, client):
        """Test deleting a non-existent topic."""
        response = client.delete("/servicebus/test-namespace/topics/nonexistent")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSubscriptionCRUDAPI:
    """Tests for subscription CRUD API endpoints."""
    
    def test_create_subscription_success(self, client, create_test_topic, subscription_xml):
        """Test creating a subscription successfully."""
        response = client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert "my-sub" in response.text
        assert "SubscriptionDescription" in response.text
    
    def test_create_subscription_topic_not_found(self, client, subscription_xml):
        """Test creating a subscription for non-existent topic."""
        response = client.put(
            "/servicebus/test-namespace/topics/nonexistent/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_create_subscription_already_exists(self, client, create_test_topic, subscription_xml):
        """Test creating a subscription that already exists."""
        # Create first time
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Create again
        response = client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_list_subscriptions_empty(self, client, create_test_topic):
        """Test listing subscriptions when none exist."""
        response = client.get("/servicebus/test-namespace/topics/test-topic/subscriptions")
        
        assert response.status_code == status.HTTP_200_OK
        assert "feed" in response.text.lower()
    
    def test_list_subscriptions_with_data(self, client, create_test_topic, subscription_xml):
        """Test listing subscriptions with multiple subscriptions."""
        # Create multiple subscriptions
        for i in range(3):
            client.put(
                f"/servicebus/test-namespace/topics/test-topic/subscriptions/sub-{i}",
                content=subscription_xml,
                headers={"Content-Type": "application/xml"},
            )
        
        response = client.get("/servicebus/test-namespace/topics/test-topic/subscriptions")
        
        assert response.status_code == status.HTTP_200_OK
        assert "sub-0" in response.text
        assert "sub-1" in response.text
        assert "sub-2" in response.text
    
    def test_get_subscription_success(self, client, create_test_topic, subscription_xml):
        """Test getting a subscription successfully."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        response = client.get("/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub")
        
        assert response.status_code == status.HTTP_200_OK
        assert "my-sub" in response.text
        assert "SubscriptionDescription" in response.text
    
    def test_get_subscription_not_found(self, client, create_test_topic):
        """Test getting a non-existent subscription."""
        response = client.get("/servicebus/test-namespace/topics/test-topic/subscriptions/nonexistent")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_subscription_success(self, client, create_test_topic, subscription_xml):
        """Test updating a subscription successfully."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Update subscription
        update_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT120S</LockDuration>
            <MaxDeliveryCount>5</MaxDeliveryCount>
        </SubscriptionDescription>
    </content>
</entry>"""
        
        response = client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=update_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert "120" in response.text
    
    def test_delete_subscription_success(self, client, create_test_topic, subscription_xml):
        """Test deleting a subscription successfully."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        response = client.delete("/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub")
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify subscription is gone
        get_response = client.get("/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_subscription_not_found(self, client, create_test_topic):
        """Test deleting a non-existent subscription."""
        response = client.delete("/servicebus/test-namespace/topics/test-topic/subscriptions/nonexistent")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestRuleAPI:
    """Tests for subscription rule API endpoints."""
    
    def test_add_sql_rule_success(self, client, create_test_topic, subscription_xml):
        """Test adding a SQL filter rule successfully."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Add SQL rule
        rule_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <Filter i:type="SqlFilter" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                <SqlExpression>priority = 'high'</SqlExpression>
            </Filter>
        </RuleDescription>
    </content>
</entry>"""
        
        response = client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub/rules/high-priority",
            content=rule_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert "SqlFilter" in response.text
        assert "high" in response.text
    
    def test_add_correlation_rule_success(self, client, create_test_topic, subscription_xml):
        """Test adding a correlation filter rule successfully."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Add correlation rule
        rule_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <Filter i:type="CorrelationFilter" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                <CorrelationId>order-123</CorrelationId>
                <Label>order.created</Label>
            </Filter>
        </RuleDescription>
    </content>
</entry>"""
        
        response = client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub/rules/order-filter",
            content=rule_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert "CorrelationFilter" in response.text
        assert "order-123" in response.text
    
    def test_list_rules(self, client, create_test_topic, subscription_xml):
        """Test listing rules for a subscription."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # List rules (should have default $Default rule)
        response = client.get("/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub/rules")
        
        assert response.status_code == status.HTTP_200_OK
        assert "$Default" in response.text or "TrueFilter" in response.text
    
    def test_delete_rule_success(self, client, create_test_topic, subscription_xml):
        """Test deleting a rule successfully."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Add rule
        rule_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <Filter i:type="SqlFilter" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                <SqlExpression>1=1</SqlExpression>
            </Filter>
        </RuleDescription>
    </content>
</entry>"""
        
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub/rules/test-rule",
            content=rule_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Delete rule
        response = client.delete(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub/rules/test-rule"
        )
        
        assert response.status_code == status.HTTP_200_OK


class TestTopicMessagingAPI:
    """Tests for topic message operations."""
    
    def test_send_to_topic_success(self, client, create_test_topic, subscription_xml):
        """Test sending a message to a topic."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send message
        response = client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={
                "body": "Test message to topic",
                "label": "test-label",
                "user_properties": {"priority": "high"},
            },
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["Body"] == "Test message to topic"
        assert "MessageId" in data
    
    def test_send_to_topic_not_found(self, client):
        """Test sending to non-existent topic."""
        response = client.post(
            "/servicebus/test-namespace/topics/nonexistent/messages",
            json={"body": "Test message"},
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_receive_from_subscription_success(self, client, create_test_topic, subscription_xml):
        """Test receiving a message from a subscription."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send message to topic
        client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={"body": "Test message", "label": "test"},
        )
        
        # Receive from subscription
        response = client.post(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub/messages/receive",
            json={"max_count": 1, "receive_mode": "PeekLock"},
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["Body"] == "Test message"
        assert "LockToken" in data[0]
    
    def test_receive_from_subscription_no_messages(self, client, create_test_topic, subscription_xml):
        """Test receiving when no messages available."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Try to receive (no messages)
        response = client.post(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub/messages/receive",
            json={"max_count": 1, "receive_mode": "PeekLock"},
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0
    
    def test_complete_subscription_message_success(self, client, create_test_topic, subscription_xml):
        """Test completing a subscription message."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send and receive message
        client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={"body": "Test message"},
        )
        
        receive_response = client.post(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub/messages/receive",
            json={"max_count": 1, "receive_mode": "PeekLock"},
        )
        message = receive_response.json()[0]
        lock_token = message["LockToken"]
        
        # Complete message
        response = client.post(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/my-sub/messages/complete",
            json={"lock_token": lock_token},
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_message_fan_out_to_multiple_subscriptions(self, client, create_test_topic, subscription_xml):
        """Test message fan-out to multiple subscriptions."""
        # Create multiple subscriptions
        for i in range(3):
            client.put(
                f"/servicebus/test-namespace/topics/test-topic/subscriptions/sub-{i}",
                content=subscription_xml,
                headers={"Content-Type": "application/xml"},
            )
        
        # Send one message to topic
        client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={"body": "Fan-out message"},
        )
        
        # Verify all subscriptions received the message
        for i in range(3):
            response = client.post(
                f"/servicebus/test-namespace/topics/test-topic/subscriptions/sub-{i}/messages/receive",
                json={"max_count": 1, "receive_mode": "PeekLock"},
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["Body"] == "Fan-out message"


class TestFilterEvaluationAPI:
    """Tests for filter evaluation in message fan-out."""
    
    def test_sql_filter_matching(self, client, create_test_topic, subscription_xml):
        """Test SQL filter matches only appropriate messages."""
        # Create subscription with SQL filter
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/high-priority-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Update with SQL filter
        rule_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <Filter i:type="SqlFilter" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                <SqlExpression>priority = 'high'</SqlExpression>
            </Filter>
        </RuleDescription>
    </content>
</entry>"""
        
        # Delete default rule and add SQL rule
        client.delete(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/high-priority-sub/rules/$Default"
        )
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/high-priority-sub/rules/filter",
            content=rule_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send matching message
        client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={"body": "High priority", "user_properties": {"priority": "high"}},
        )
        
        # Send non-matching message
        client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={"body": "Low priority", "user_properties": {"priority": "low"}},
        )
        
        # Receive - should only get matching message
        response = client.post(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/high-priority-sub/messages/receive",
            json={"max_count": 10, "receive_mode": "PeekLock"},
        )
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["Body"] == "High priority"
    
    def test_correlation_filter_matching(self, client, create_test_topic, subscription_xml):
        """Test correlation filter matches only appropriate messages."""
        # Create subscription
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/order-sub",
            content=subscription_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Update with correlation filter
        rule_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <Filter i:type="CorrelationFilter" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                <Label>order.created</Label>
            </Filter>
        </RuleDescription>
    </content>
</entry>"""
        
        client.delete(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/order-sub/rules/$Default"
        )
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/order-sub/rules/filter",
            content=rule_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send matching message
        client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={"body": "Order created", "label": "order.created"},
        )
        
        # Send non-matching message
        client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={"body": "Order deleted", "label": "order.deleted"},
        )
        
        # Receive - should only get matching message
        response = client.post(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/order-sub/messages/receive",
            json={"max_count": 10, "receive_mode": "PeekLock"},
        )
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["Body"] == "Order created"
    
    def test_multiple_subscriptions_with_different_filters(self, client, create_test_topic, subscription_xml):
        """Test multiple subscriptions with different filters receive appropriate messages."""
        # Create two subscriptions with different filters
        for sub_name in ["high-sub", "low-sub"]:
            client.put(
                f"/servicebus/test-namespace/topics/test-topic/subscriptions/{sub_name}",
                content=subscription_xml,
                headers={"Content-Type": "application/xml"},
            )
        
        # Add SQL filter for high priority
        high_rule_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <Filter i:type="SqlFilter" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                <SqlExpression>priority = 'high'</SqlExpression>
            </Filter>
        </RuleDescription>
    </content>
</entry>"""
        
        # Add SQL filter for low priority
        low_rule_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <Filter i:type="SqlFilter" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                <SqlExpression>priority = 'low'</SqlExpression>
            </Filter>
        </RuleDescription>
    </content>
</entry>"""
        
        client.delete("/servicebus/test-namespace/topics/test-topic/subscriptions/high-sub/rules/$Default")
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/high-sub/rules/filter",
            content=high_rule_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        client.delete("/servicebus/test-namespace/topics/test-topic/subscriptions/low-sub/rules/$Default")
        client.put(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/low-sub/rules/filter",
            content=low_rule_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Send messages with different priorities
        client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={"body": "High priority message", "user_properties": {"priority": "high"}},
        )
        client.post(
            "/servicebus/test-namespace/topics/test-topic/messages",
            json={"body": "Low priority message", "user_properties": {"priority": "low"}},
        )
        
        # Verify high-sub only receives high priority
        high_response = client.post(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/high-sub/messages/receive",
            json={"max_count": 10, "receive_mode": "PeekLock"},
        )
        high_data = high_response.json()
        assert len(high_data) == 1
        assert high_data[0]["Body"] == "High priority message"
        
        # Verify low-sub only receives low priority
        low_response = client.post(
            "/servicebus/test-namespace/topics/test-topic/subscriptions/low-sub/messages/receive",
            json={"max_count": 10, "receive_mode": "PeekLock"},
        )
        low_data = low_response.json()
        assert len(low_data) == 1
        assert low_data[0]["Body"] == "Low priority message"
