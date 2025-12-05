"""
Example: Using LocalZure Service Bus with Python

This demonstrates how to use LocalZure as a drop-in replacement for Azure Service Bus.

Run LocalZure first:
    localzure start

Then run this script:
    python examples/test_servicebus.py
"""

import requests
import json
import time

LOCALZURE_URL = "http://127.0.0.1:8080"
NAMESPACE = "test-ns"


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_queue_operations():
    """Test queue creation and operations."""
    print_section("Testing Queue Operations")
    
    # Create a queue
    print("1️⃣  Creating queue 'demo-queue'...")
    queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
            <MaxDeliveryCount>10</MaxDeliveryCount>
        </QueueDescription>
    </content>
</entry>"""
    
    response = requests.put(
        f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/demo-queue",
        data=queue_xml,
        headers={"Content-Type": "application/xml"}
    )
    print(f"   ✅ Queue created: {response.status_code}")
    
    # Send a message
    print("\n2️⃣  Sending message to queue...")
    message = {
        "body": "Hello from LocalZure!",
        "user_properties": {
            "sender": "demo-app",
            "timestamp": str(time.time())
        }
    }
    
    response = requests.post(
        f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/demo-queue/messages",
        json=message
    )
    print(f"   ✅ Message sent: {response.status_code}")
    print(f"   📋 Response: {response.text[:200]}")  # Debug output
    if response.ok:
        resp_data = response.json()
        print(f"   📨 Message ID: {resp_data.get('message_id')}")
    
    # Receive a message
    print("\n3️⃣  Receiving message from queue...")
    response = requests.post(
        f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/demo-queue/messages/head?timeout=5"
    )
    print(f"   📋 Response status: {response.status_code}")
    print(f"   📋 Response text: {response.text[:200]}")  # Debug output
    
    if response.status_code == 200:
        received = response.json()
        print(f"   📋 Received type: {type(received)}")  # Debug
        if received:  # Check if message is not None
            print(f"   ✅ Message received!")
            print(f"   📬 Body: {received.get('body')}")
            print(f"   🏷️  Properties: {received.get('user_properties')}")
            print(f"   🔒 Lock Token: {received.get('lock_token')}")
            
            # Complete the message
            message_id = received.get('message_id')
            lock_token = received.get('lock_token')
            
            print(f"\n4️⃣  Completing message...")
            response = requests.delete(
                f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/demo-queue/messages/{message_id}/{lock_token}"
            )
            print(f"   ✅ Message completed: {response.status_code}")
        else:
            print("   ℹ️  No messages available (None returned)")
    elif response.status_code == 204:
        print("   ℹ️  No messages available")
    
    # List queues
    print("\n5️⃣  Listing all queues...")
    response = requests.get(f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/$Resources/Queues")
    print(f"   ✅ Queues retrieved: {response.status_code}")
    
    # Delete queue
    print("\n6️⃣  Deleting queue...")
    response = requests.delete(f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/demo-queue")
    print(f"   ✅ Queue deleted: {response.status_code}")


def test_topic_operations():
    """Test topic and subscription operations."""
    print_section("Testing Topic & Subscription Operations")
    
    # Create a topic
    print("1️⃣  Creating topic 'demo-topic'...")
    topic_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
        </TopicDescription>
    </content>
</entry>"""
    
    response = requests.put(
        f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/topics/demo-topic",
        data=topic_xml,
        headers={"Content-Type": "application/xml"}
    )
    print(f"   ✅ Topic created: {response.status_code}")
    
    # Create a subscription
    print("\n2️⃣  Creating subscription 'demo-subscription'...")
    sub_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT30S</LockDuration>
        </SubscriptionDescription>
    </content>
</entry>"""
    
    response = requests.put(
        f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/topics/demo-topic/subscriptions/demo-subscription",
        data=sub_xml,
        headers={"Content-Type": "application/xml"}
    )
    print(f"   ✅ Subscription created: {response.status_code}")
    
    # Send message to topic
    print("\n3️⃣  Publishing message to topic...")
    message = {
        "body": "Hello subscribers!",
        "user_properties": {
            "event_type": "demo.event",
            "priority": "high"
        }
    }
    
    response = requests.post(
        f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/topics/demo-topic/messages",
        json=message
    )
    print(f"   ✅ Message published: {response.status_code}")
    
    # Receive from subscription
    print("\n4️⃣  Receiving message from subscription...")
    response = requests.post(
        f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/topics/demo-topic/subscriptions/demo-subscription/messages/head?timeout=5"
    )
    
    if response.status_code == 200:
        messages = response.json()
        if messages:
            print(f"   ✅ Received {len(messages)} message(s)")
            print(f"   📬 Body: {messages[0].get('body')}")
    elif response.status_code == 204:
        print("   ℹ️  No messages available")
    
    # Clean up
    print("\n5️⃣  Cleaning up...")
    requests.delete(f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/topics/demo-topic/subscriptions/demo-subscription")
    requests.delete(f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/topics/demo-topic")
    print("   ✅ Resources deleted")


def test_error_handling():
    """Test error handling and responses."""
    print_section("Testing Error Handling")
    
    # Try to get non-existent queue
    print("1️⃣  Attempting to get non-existent queue...")
    response = requests.get(f"{LOCALZURE_URL}/servicebus/{NAMESPACE}/nonexistent-queue")
    print(f"   ✅ Response: {response.status_code}")
    
    if response.status_code == 404:
        error = response.json()
        print(f"   ❌ Error Code: {error['error']['code']}")
        print(f"   📝 Message: {error['error']['message']}")
        print(f"   🔍 Details: {error['error']['details']}")


def test_health_check():
    """Test health check endpoint."""
    print_section("Testing Health Check")
    
    response = requests.get(f"{LOCALZURE_URL}/health")
    if response.ok:
        health = response.json()
        print(f"   ✅ Status: {health['status']}")
        print(f"   📦 Version: {health['version']}")
        print(f"   🔧 Services: {json.dumps(health['services'], indent=6)}")
    else:
        print(f"   ❌ Health check failed: {response.status_code}")


def main():
    """Run all tests."""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║           🌀 LocalZure Service Bus Demo                  ║
    ║                                                           ║
    ║  This demonstrates LocalZure working like LocalStack     ║
    ║  with Azure Service Bus emulation                        ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Check if LocalZure is running
        response = requests.get(f"{LOCALZURE_URL}/health", timeout=2)
        if not response.ok:
            print("❌ LocalZure is not responding correctly!")
            print("   Please start LocalZure first: localzure start")
            return
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to LocalZure!")
        print("   Please start LocalZure first: localzure start")
        return
    
    # Run tests
    test_health_check()
    test_queue_operations()
    test_topic_operations()
    test_error_handling()
    
    print_section("✅ All Tests Completed!")
    print(f"\n💡 You can now use LocalZure with your Azure applications!")
    print(f"   Just point your Azure SDKs to: {LOCALZURE_URL}\n")


if __name__ == "__main__":
    main()
