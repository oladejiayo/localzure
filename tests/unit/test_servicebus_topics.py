"""
Unit Tests for Service Bus Topics and Subscriptions

Tests for topic/subscription CRUD, filter evaluation, and message fan-out.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta

from localzure.services.servicebus.backend import (
    ServiceBusBackend,
    TopicNotFoundError,
    TopicAlreadyExistsError,
    SubscriptionNotFoundError,
    SubscriptionAlreadyExistsError,
    RuleNotFoundError,
    RuleAlreadyExistsError,
)
from localzure.services.servicebus.models import (
    TopicProperties,
    SubscriptionProperties,
    SubscriptionFilter,
    FilterType,
    RuleDescription,
    ServiceBusMessage,
    SendMessageRequest,
    ReceiveMode,
)


@pytest.fixture
async def backend():
    """Create a fresh backend for each test."""
    return ServiceBusBackend()


@pytest.fixture
async def backend_with_topic(backend):
    """Create a backend with a test topic."""
    await backend.create_topic("test-topic")
    return backend


@pytest.fixture
async def backend_with_subscription(backend_with_topic):
    """Create a backend with a topic and subscription."""
    await backend_with_topic.create_subscription("test-topic", "test-sub")
    return backend_with_topic


# ========== Topic CRUD Tests ==========

@pytest.mark.asyncio
async def test_create_topic(backend):
    """Test creating a topic."""
    topic = await backend.create_topic("my-topic")
    
    assert topic.name == "my-topic"
    assert topic.properties.max_size_in_megabytes == 1024
    assert topic.runtime_info.subscription_count == 0


@pytest.mark.asyncio
async def test_create_topic_with_properties(backend):
    """Test creating a topic with custom properties."""
    props = TopicProperties(
        max_size_in_megabytes=2048,
        requires_duplicate_detection=True,
        enable_batched_operations=False,
    )
    
    topic = await backend.create_topic("my-topic", props)
    
    assert topic.properties.max_size_in_megabytes == 2048
    assert topic.properties.requires_duplicate_detection is True
    assert topic.properties.enable_batched_operations is False


@pytest.mark.asyncio
async def test_create_topic_already_exists(backend_with_topic):
    """Test creating a topic that already exists."""
    with pytest.raises(TopicAlreadyExistsError):
        await backend_with_topic.create_topic("test-topic")


@pytest.mark.asyncio
async def test_list_topics(backend):
    """Test listing topics."""
    await backend.create_topic("topic1")
    await backend.create_topic("topic2")
    await backend.create_topic("topic3")
    
    topics = await backend.list_topics()
    
    assert len(topics) == 3
    assert {t.name for t in topics} == {"topic1", "topic2", "topic3"}


@pytest.mark.asyncio
async def test_get_topic(backend_with_topic):
    """Test getting a topic."""
    topic = await backend_with_topic.get_topic("test-topic")
    
    assert topic.name == "test-topic"


@pytest.mark.asyncio
async def test_get_topic_not_found(backend):
    """Test getting a non-existent topic."""
    with pytest.raises(TopicNotFoundError):
        await backend.get_topic("nonexistent")


@pytest.mark.asyncio
async def test_update_topic(backend_with_topic):
    """Test updating a topic."""
    new_props = TopicProperties(max_size_in_megabytes=2048)
    
    topic = await backend_with_topic.update_topic("test-topic", new_props)
    
    assert topic.properties.max_size_in_megabytes == 2048


@pytest.mark.asyncio
async def test_update_topic_not_found(backend):
    """Test updating a non-existent topic."""
    props = TopicProperties()
    
    with pytest.raises(TopicNotFoundError):
        await backend.update_topic("nonexistent", props)


@pytest.mark.asyncio
async def test_delete_topic(backend_with_topic):
    """Test deleting a topic."""
    await backend_with_topic.delete_topic("test-topic")
    
    with pytest.raises(TopicNotFoundError):
        await backend_with_topic.get_topic("test-topic")


@pytest.mark.asyncio
async def test_delete_topic_not_found(backend):
    """Test deleting a non-existent topic."""
    with pytest.raises(TopicNotFoundError):
        await backend.delete_topic("nonexistent")


@pytest.mark.asyncio
async def test_delete_topic_deletes_subscriptions(backend_with_subscription):
    """Test that deleting a topic deletes all its subscriptions."""
    await backend_with_subscription.create_subscription("test-topic", "sub2")
    
    await backend_with_subscription.delete_topic("test-topic")
    
    # Verify topic and subscriptions are gone
    with pytest.raises(TopicNotFoundError):
        await backend_with_subscription.get_topic("test-topic")


# ========== Subscription CRUD Tests ==========

@pytest.mark.asyncio
async def test_create_subscription(backend_with_topic):
    """Test creating a subscription."""
    subscription = await backend_with_topic.create_subscription("test-topic", "my-sub")
    
    assert subscription.topic_name == "test-topic"
    assert subscription.subscription_name == "my-sub"
    assert subscription.properties.lock_duration == 60  # int seconds
    assert subscription.properties.max_delivery_count == 10
    assert len(subscription.rules) == 1  # Default TrueFilter rule
    assert subscription.rules[0].name == "$Default"
    assert subscription.rules[0].filter.filter_type == FilterType.TRUE_FILTER


@pytest.mark.asyncio
async def test_create_subscription_with_properties(backend_with_topic):
    """Test creating a subscription with custom properties."""
    props = SubscriptionProperties(
        lock_duration=120,  # int seconds
        max_delivery_count=5,
        dead_lettering_on_message_expiration=True,
    )
    
    subscription = await backend_with_topic.create_subscription("test-topic", "my-sub", props)
    
    assert subscription.properties.lock_duration == 120
    assert subscription.properties.max_delivery_count == 5
    assert subscription.properties.dead_lettering_on_message_expiration is True


@pytest.mark.asyncio
async def test_create_subscription_topic_not_found(backend):
    """Test creating a subscription on a non-existent topic."""
    with pytest.raises(TopicNotFoundError):
        await backend.create_subscription("nonexistent", "my-sub")


@pytest.mark.asyncio
async def test_create_subscription_already_exists(backend_with_subscription):
    """Test creating a subscription that already exists."""
    with pytest.raises(SubscriptionAlreadyExistsError):
        await backend_with_subscription.create_subscription("test-topic", "test-sub")


@pytest.mark.asyncio
async def test_list_subscriptions(backend_with_topic):
    """Test listing subscriptions."""
    await backend_with_topic.create_subscription("test-topic", "sub1")
    await backend_with_topic.create_subscription("test-topic", "sub2")
    await backend_with_topic.create_subscription("test-topic", "sub3")
    
    subscriptions = await backend_with_topic.list_subscriptions("test-topic")
    
    assert len(subscriptions) == 3
    assert {s.subscription_name for s in subscriptions} == {"sub1", "sub2", "sub3"}


@pytest.mark.asyncio
async def test_list_subscriptions_topic_not_found(backend):
    """Test listing subscriptions for a non-existent topic."""
    with pytest.raises(TopicNotFoundError):
        await backend.list_subscriptions("nonexistent")


@pytest.mark.asyncio
async def test_get_subscription(backend_with_subscription):
    """Test getting a subscription."""
    subscription = await backend_with_subscription.get_subscription("test-topic", "test-sub")
    
    assert subscription.topic_name == "test-topic"
    assert subscription.subscription_name == "test-sub"


@pytest.mark.asyncio
async def test_get_subscription_not_found(backend_with_topic):
    """Test getting a non-existent subscription."""
    with pytest.raises(SubscriptionNotFoundError):
        await backend_with_topic.get_subscription("test-topic", "nonexistent")


@pytest.mark.asyncio
async def test_update_subscription(backend_with_subscription):
    """Test updating a subscription."""
    new_props = SubscriptionProperties(lock_duration=180)  # int seconds
    
    subscription = await backend_with_subscription.update_subscription(
        "test-topic", "test-sub", new_props
    )
    
    assert subscription.properties.lock_duration == 180


@pytest.mark.asyncio
async def test_update_subscription_not_found(backend_with_topic):
    """Test updating a non-existent subscription."""
    props = SubscriptionProperties()
    
    with pytest.raises(SubscriptionNotFoundError):
        await backend_with_topic.update_subscription("test-topic", "nonexistent", props)


@pytest.mark.asyncio
async def test_delete_subscription(backend_with_subscription):
    """Test deleting a subscription."""
    await backend_with_subscription.delete_subscription("test-topic", "test-sub")
    
    with pytest.raises(SubscriptionNotFoundError):
        await backend_with_subscription.get_subscription("test-topic", "test-sub")


@pytest.mark.asyncio
async def test_delete_subscription_not_found(backend_with_topic):
    """Test deleting a non-existent subscription."""
    with pytest.raises(SubscriptionNotFoundError):
        await backend_with_topic.delete_subscription("test-topic", "nonexistent")


# ========== Rule Management Tests ==========

@pytest.mark.asyncio
async def test_add_rule(backend_with_subscription):
    """Test adding a rule to a subscription."""
    filter = SubscriptionFilter(
        filter_type=FilterType.SQL_FILTER,
        sql_expression="quantity > 100",
    )
    
    rule = await backend_with_subscription.add_rule(
        "test-topic", "test-sub", "high-quantity", filter
    )
    
    assert rule.name == "high-quantity"
    assert rule.filter.filter_type == FilterType.SQL_FILTER
    assert rule.filter.sql_expression == "quantity > 100"
    
    # Verify subscription has 2 rules now (default + new)
    subscription = await backend_with_subscription.get_subscription("test-topic", "test-sub")
    assert len(subscription.rules) == 2


@pytest.mark.asyncio
async def test_add_rule_already_exists(backend_with_subscription):
    """Test adding a rule that already exists."""
    filter = SubscriptionFilter(filter_type=FilterType.TRUE_FILTER)
    
    with pytest.raises(RuleAlreadyExistsError):
        await backend_with_subscription.add_rule("test-topic", "test-sub", "$Default", filter)


@pytest.mark.asyncio
async def test_update_rule(backend_with_subscription):
    """Test updating a rule."""
    new_filter = SubscriptionFilter(filter_type=FilterType.FALSE_FILTER)
    
    rule = await backend_with_subscription.update_rule(
        "test-topic", "test-sub", "$Default", new_filter
    )
    
    assert rule.filter.filter_type == FilterType.FALSE_FILTER


@pytest.mark.asyncio
async def test_update_rule_not_found(backend_with_subscription):
    """Test updating a non-existent rule."""
    filter = SubscriptionFilter(filter_type=FilterType.TRUE_FILTER)
    
    with pytest.raises(RuleNotFoundError):
        await backend_with_subscription.update_rule("test-topic", "test-sub", "nonexistent", filter)


@pytest.mark.asyncio
async def test_delete_rule(backend_with_subscription):
    """Test deleting a rule."""
    # Add a second rule first
    filter = SubscriptionFilter(filter_type=FilterType.SQL_FILTER, sql_expression="price > 50")
    await backend_with_subscription.add_rule("test-topic", "test-sub", "expensive", filter)
    
    await backend_with_subscription.delete_rule("test-topic", "test-sub", "expensive")
    
    subscription = await backend_with_subscription.get_subscription("test-topic", "test-sub")
    assert len(subscription.rules) == 1
    assert subscription.rules[0].name == "$Default"


@pytest.mark.asyncio
async def test_delete_rule_not_found(backend_with_subscription):
    """Test deleting a non-existent rule."""
    with pytest.raises(RuleNotFoundError):
        await backend_with_subscription.delete_rule("test-topic", "test-sub", "nonexistent")


@pytest.mark.asyncio
async def test_list_rules(backend_with_subscription):
    """Test listing rules."""
    filter1 = SubscriptionFilter(filter_type=FilterType.SQL_FILTER, sql_expression="price > 50")
    filter2 = SubscriptionFilter(filter_type=FilterType.SQL_FILTER, sql_expression="quantity < 10")
    
    await backend_with_subscription.add_rule("test-topic", "test-sub", "rule1", filter1)
    await backend_with_subscription.add_rule("test-topic", "test-sub", "rule2", filter2)
    
    rules = await backend_with_subscription.list_rules("test-topic", "test-sub")
    
    assert len(rules) == 3  # Default + 2 new
    assert {r.name for r in rules} == {"$Default", "rule1", "rule2"}


# ========== Filter Evaluation Tests ==========

@pytest.mark.asyncio
async def test_true_filter_matches_all(backend):
    """Test that TrueFilter matches all messages."""
    message = ServiceBusMessage(
        message_id="msg1",
        body="test",
        label="order",
    )
    
    assert backend._evaluate_true_filter(message) is True


@pytest.mark.asyncio
async def test_false_filter_matches_none(backend):
    """Test that FalseFilter matches no messages."""
    message = ServiceBusMessage(
        message_id="msg1",
        body="test",
    )
    
    assert backend._evaluate_false_filter(message) is False


@pytest.mark.asyncio
async def test_correlation_filter_matches(backend):
    """Test correlation filter matching."""
    message = ServiceBusMessage(
        message_id="msg1",
        body="test",
        correlation_id="corr-123",
        label="order",
        content_type="application/json",
        user_properties={"priority": "high", "category": "urgent"},
    )
    
    filter = SubscriptionFilter(
        filter_type=FilterType.CORRELATION_FILTER,
        correlation_id="corr-123",
        label="order",
        properties={"priority": "high"},
    )
    
    assert backend._evaluate_correlation_filter(filter, message) is True


@pytest.mark.asyncio
async def test_correlation_filter_no_match(backend):
    """Test correlation filter not matching."""
    message = ServiceBusMessage(
        message_id="msg1",
        body="test",
        correlation_id="corr-123",
        label="order",
    )
    
    filter = SubscriptionFilter(
        filter_type=FilterType.CORRELATION_FILTER,
        correlation_id="corr-456",  # Different ID
    )
    
    assert backend._evaluate_correlation_filter(filter, message) is False


@pytest.mark.asyncio
async def test_sql_filter_simple_equality(backend):
    """Test SQL filter with simple equality."""
    message = ServiceBusMessage(
        message_id="msg1",
        body="test",
        label="order",
    )
    
    filter = SubscriptionFilter(
        filter_type=FilterType.SQL_FILTER,
        sql_expression="sys.Label = 'order'",
    )
    
    assert backend._evaluate_sql_filter(filter, message) is True


@pytest.mark.asyncio
async def test_sql_filter_greater_than(backend):
    """Test SQL filter with greater than comparison."""
    message = ServiceBusMessage(
        message_id="msg1",
        body="test",
        user_properties={"quantity": "150"},  # Note: converted to string
    )
    
    filter = SubscriptionFilter(
        filter_type=FilterType.SQL_FILTER,
        sql_expression="quantity > 100",
    )
    
    assert backend._evaluate_sql_filter(filter, message) is True


@pytest.mark.asyncio
async def test_sql_filter_and_operator(backend):
    """Test SQL filter with AND operator."""
    message = ServiceBusMessage(
        message_id="msg1",
        body="test",
        label="order",
        user_properties={"quantity": "150"},
    )
    
    filter = SubscriptionFilter(
        filter_type=FilterType.SQL_FILTER,
        sql_expression="sys.Label = 'order' AND quantity > 100",
    )
    
    assert backend._evaluate_sql_filter(filter, message) is True


@pytest.mark.asyncio
async def test_sql_filter_or_operator(backend):
    """Test SQL filter with OR operator."""
    message = ServiceBusMessage(
        message_id="msg1",
        body="test",
        user_properties={"priority": "low"},
    )
    
    filter = SubscriptionFilter(
        filter_type=FilterType.SQL_FILTER,
        sql_expression="priority = 'high' OR priority = 'low'",
    )
    
    assert backend._evaluate_sql_filter(filter, message) is True


@pytest.mark.asyncio
async def test_sql_filter_in_operator(backend):
    """Test SQL filter with IN operator."""
    message = ServiceBusMessage(
        message_id="msg1",
        body="test",
        user_properties={"color": "blue"},
    )
    
    filter = SubscriptionFilter(
        filter_type=FilterType.SQL_FILTER,
        sql_expression="color IN ('red', 'blue', 'green')",
    )
    
    assert backend._evaluate_sql_filter(filter, message) is True


# ========== Message Fan-out Tests ==========

@pytest.mark.asyncio
async def test_send_to_topic_fans_out_to_subscriptions(backend_with_topic):
    """Test that sending to a topic fans out to all matching subscriptions."""
    # Create 3 subscriptions with TrueFilter (default)
    await backend_with_topic.create_subscription("test-topic", "sub1")
    await backend_with_topic.create_subscription("test-topic", "sub2")
    await backend_with_topic.create_subscription("test-topic", "sub3")
    
    # Send a message
    request = SendMessageRequest(body="test message", label="test")
    await backend_with_topic.send_to_topic("test-topic", request)
    
    # Verify all subscriptions received the message
    for sub_name in ["sub1", "sub2", "sub3"]:
        messages = await backend_with_topic.receive_from_subscription(
            "test-topic", sub_name, ReceiveMode.PEEK_LOCK, 1
        )
        assert len(messages) == 1
        assert messages[0].body == "test message"


@pytest.mark.asyncio
async def test_send_to_topic_with_sql_filter(backend_with_topic):
    """Test message fan-out with SQL filter."""
    # Create subscription with SQL filter
    await backend_with_topic.create_subscription("test-topic", "high-priority")
    
    # Replace default rule with SQL filter
    sql_filter = SubscriptionFilter(
        filter_type=FilterType.SQL_FILTER,
        sql_expression="priority = 'high'",
    )
    await backend_with_topic.delete_rule("test-topic", "high-priority", "$Default")
    await backend_with_topic.add_rule("test-topic", "high-priority", "priority-filter", sql_filter)
    
    # Send matching message
    request = SendMessageRequest(body="urgent", user_properties={"priority": "high"})
    await backend_with_topic.send_to_topic("test-topic", request)
    
    # Send non-matching message
    request2 = SendMessageRequest(body="normal", user_properties={"priority": "low"})
    await backend_with_topic.send_to_topic("test-topic", request2)
    
    # Verify only matching message was received
    messages = await backend_with_topic.receive_from_subscription(
        "test-topic", "high-priority", ReceiveMode.PEEK_LOCK, 10
    )
    assert len(messages) == 1
    assert messages[0].body == "urgent"


@pytest.mark.asyncio
async def test_send_to_topic_with_correlation_filter(backend_with_topic):
    """Test message fan-out with correlation filter."""
    await backend_with_topic.create_subscription("test-topic", "orders")
    
    # Replace default rule with correlation filter
    corr_filter = SubscriptionFilter(
        filter_type=FilterType.CORRELATION_FILTER,
        label="order",
        properties={"region": "us-west"},
    )
    await backend_with_topic.delete_rule("test-topic", "orders", "$Default")
    await backend_with_topic.add_rule("test-topic", "orders", "order-filter", corr_filter)
    
    # Send matching message
    request = SendMessageRequest(
        body="order data",
        label="order",
        user_properties={"region": "us-west", "amount": "100"},
    )
    await backend_with_topic.send_to_topic("test-topic", request)
    
    # Send non-matching message
    request2 = SendMessageRequest(body="other", label="event")
    await backend_with_topic.send_to_topic("test-topic", request2)
    
    # Verify only matching message was received
    messages = await backend_with_topic.receive_from_subscription(
        "test-topic", "orders", ReceiveMode.PEEK_LOCK, 10
    )
    assert len(messages) == 1
    assert messages[0].body == "order data"


@pytest.mark.asyncio
async def test_independent_subscription_queues(backend_with_topic):
    """Test that subscriptions maintain independent message queues."""
    # Create 2 subscriptions
    await backend_with_topic.create_subscription("test-topic", "sub1")
    await backend_with_topic.create_subscription("test-topic", "sub2")
    
    # Send messages
    for i in range(5):
        request = SendMessageRequest(body=f"message-{i}")
        await backend_with_topic.send_to_topic("test-topic", request)
    
    # Receive from sub1
    messages_sub1 = await backend_with_topic.receive_from_subscription(
        "test-topic", "sub1", ReceiveMode.PEEK_LOCK, 3
    )
    assert len(messages_sub1) == 3
    
    # Receive from sub2 (should still have all 5)
    messages_sub2 = await backend_with_topic.receive_from_subscription(
        "test-topic", "sub2", ReceiveMode.PEEK_LOCK, 5
    )
    assert len(messages_sub2) == 5


@pytest.mark.asyncio
async def test_receive_from_subscription_peek_lock(backend_with_subscription):
    """Test receiving messages with peek-lock mode."""
    # Send messages
    for i in range(3):
        request = SendMessageRequest(body=f"message-{i}")
        await backend_with_subscription.send_to_topic("test-topic", request)
    
    # Receive with peek-lock
    messages = await backend_with_subscription.receive_from_subscription(
        "test-topic", "test-sub", ReceiveMode.PEEK_LOCK, 3
    )
    
    assert len(messages) == 3
    assert all(msg.is_locked for msg in messages)
    assert all(msg.lock_token is not None for msg in messages)


@pytest.mark.asyncio
async def test_complete_subscription_message(backend_with_subscription):
    """Test completing a subscription message."""
    # Send and receive
    request = SendMessageRequest(body="test")
    await backend_with_subscription.send_to_topic("test-topic", request)
    
    messages = await backend_with_subscription.receive_from_subscription(
        "test-topic", "test-sub", ReceiveMode.PEEK_LOCK, 1
    )
    
    # Complete the message
    await backend_with_subscription.complete_subscription_message(
        "test-topic", "test-sub", messages[0].lock_token
    )
    
    # Try to receive again - should be empty
    messages2 = await backend_with_subscription.receive_from_subscription(
        "test-topic", "test-sub", ReceiveMode.PEEK_LOCK, 1
    )
    assert len(messages2) == 0


@pytest.mark.asyncio
async def test_abandon_subscription_message(backend_with_subscription):
    """Test abandoning a subscription message."""
    # Send and receive
    request = SendMessageRequest(body="test")
    await backend_with_subscription.send_to_topic("test-topic", request)
    
    messages = await backend_with_subscription.receive_from_subscription(
        "test-topic", "test-sub", ReceiveMode.PEEK_LOCK, 1
    )
    
    # Abandon the message
    await backend_with_subscription.abandon_subscription_message(
        "test-topic", "test-sub", messages[0].lock_token
    )
    
    # Message should be available again
    messages2 = await backend_with_subscription.receive_from_subscription(
        "test-topic", "test-sub", ReceiveMode.PEEK_LOCK, 1
    )
    assert len(messages2) == 1
    assert messages2[0].delivery_count == 2  # Incremented
