"""
LocalZure Service Bus - Python Example

Complete example demonstrating queue and topic operations using azure-servicebus SDK.

Requirements:
    pip install azure-servicebus

Usage:
    python python_example.py
"""

import asyncio
import os
from datetime import datetime
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage, ServiceBusSubQueue


# LocalZure connection string
CONNECTION_STRING = "Endpoint=sb://localhost:8000/servicebus/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=fake-key"


async def queue_example():
    """
    Demonstrates basic queue operations:
    - Send message
    - Receive message with peek-lock
    - Complete message
    - Dead-letter message
    """
    print("\n=== Queue Example ===\n")
    
    async with ServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
        
        # Send messages to queue
        print("Sending messages to 'orders' queue...")
        sender = client.get_queue_sender("orders")
        
        messages = [
            ServiceBusMessage(
                body="Order 1001",
                application_properties={
                    "order_id": 1001,
                    "priority": "high",
                    "customer_tier": "premium"
                }
            ),
            ServiceBusMessage(
                body="Order 1002",
                application_properties={
                    "order_id": 1002,
                    "priority": "normal",
                    "customer_tier": "standard"
                }
            ),
            ServiceBusMessage(
                body="Order 1003 (will be dead-lettered)",
                application_properties={
                    "order_id": 1003,
                    "priority": "low"
                }
            )
        ]
        
        async with sender:
            await sender.send_messages(messages)
        print(f"✓ Sent {len(messages)} messages\n")
        
        # Receive and process messages
        print("Receiving messages from 'orders' queue...")
        receiver = client.get_queue_receiver("orders")
        
        async with receiver:
            received_messages = await receiver.receive_messages(max_message_count=3, max_wait_time=5)
            
            for i, msg in enumerate(received_messages):
                print(f"\nMessage {i + 1}:")
                print(f"  Body: {str(msg)}")
                print(f"  Properties: {msg.application_properties}")
                print(f"  MessageId: {msg.message_id}")
                print(f"  EnqueuedTime: {msg.enqueued_time_utc}")
                print(f"  DeliveryCount: {msg.delivery_count}")
                
                # Complete first two messages
                if i < 2:
                    await receiver.complete_message(msg)
                    print("  ✓ Completed")
                else:
                    # Dead-letter the third message
                    await receiver.dead_letter_message(
                        msg,
                        reason="InvalidOrder",
                        error_description="Order validation failed"
                    )
                    print("  ✗ Dead-lettered")
        
        # Read from dead-letter queue
        print("\n\nChecking dead-letter queue...")
        dlq_receiver = client.get_queue_receiver("orders", sub_queue=ServiceBusSubQueue.DEAD_LETTER)
        
        async with dlq_receiver:
            dlq_messages = await dlq_receiver.receive_messages(max_message_count=10, max_wait_time=5)
            
            for msg in dlq_messages:
                print(f"\nDead-letter message:")
                print(f"  Body: {str(msg)}")
                print(f"  Reason: {msg.dead_letter_reason}")
                print(f"  Description: {msg.dead_letter_error_description}")
                await dlq_receiver.complete_message(msg)


async def topic_subscription_example():
    """
    Demonstrates topic/subscription operations:
    - Publish message to topic
    - Receive from multiple subscriptions with filters
    """
    print("\n\n=== Topic/Subscription Example ===\n")
    
    async with ServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
        
        # Publish messages to topic
        print("Publishing messages to 'events' topic...")
        sender = client.get_topic_sender("events")
        
        messages = [
            ServiceBusMessage(
                body="High priority alert",
                application_properties={
                    "priority": "high",
                    "region": "us-west",
                    "event_type": "alert"
                }
            ),
            ServiceBusMessage(
                body="Normal priority notification",
                application_properties={
                    "priority": "normal",
                    "region": "us-east",
                    "event_type": "notification"
                }
            ),
            ServiceBusMessage(
                body="Low priority log",
                application_properties={
                    "priority": "low",
                    "region": "eu-west",
                    "event_type": "log"
                }
            )
        ]
        
        async with sender:
            await sender.send_messages(messages)
        print(f"✓ Published {len(messages)} messages\n")
        
        # Receive from high-priority subscription
        print("Receiving from 'high-priority' subscription (filter: priority = 'high')...")
        receiver = client.get_subscription_receiver("events", "high-priority")
        
        async with receiver:
            received = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
            print(f"  Received {len(received)} message(s)")
            
            for msg in received:
                print(f"    - {str(msg)} (priority: {msg.application_properties.get('priority')})")
                await receiver.complete_message(msg)
        
        # Receive from us-west subscription
        print("\nReceiving from 'us-west' subscription (filter: region = 'us-west')...")
        receiver = client.get_subscription_receiver("events", "us-west")
        
        async with receiver:
            received = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
            print(f"  Received {len(received)} message(s)")
            
            for msg in received:
                print(f"    - {str(msg)} (region: {msg.application_properties.get('region')})")
                await receiver.complete_message(msg)
        
        # Receive from all-events subscription
        print("\nReceiving from 'all-events' subscription (no filter)...")
        receiver = client.get_subscription_receiver("events", "all-events")
        
        async with receiver:
            received = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
            print(f"  Received {len(received)} message(s)")
            
            for msg in received:
                print(f"    - {str(msg)}")
                await receiver.complete_message(msg)


async def session_example():
    """
    Demonstrates session-enabled queue operations:
    - Send messages to specific sessions
    - Accept and process session messages
    - Set and get session state
    """
    print("\n\n=== Session Queue Example ===\n")
    
    async with ServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
        
        # Send messages to session queue
        print("Sending messages to 'session-orders' queue with sessions...")
        sender = client.get_queue_sender("session-orders")
        
        sessions = ["user-123", "user-456", "user-123", "user-456"]
        messages = []
        
        for i, session_id in enumerate(sessions):
            msg = ServiceBusMessage(
                body=f"Order {i + 1} for {session_id}",
                session_id=session_id,
                application_properties={"order_num": i + 1}
            )
            messages.append(msg)
        
        async with sender:
            await sender.send_messages(messages)
        print(f"✓ Sent {len(messages)} messages across {len(set(sessions))} sessions\n")
        
        # Process messages from specific session
        print("Processing session 'user-123'...")
        receiver = client.get_queue_receiver("session-orders", session_id="user-123")
        
        async with receiver:
            # Set session state
            await receiver.set_session_state(b"processing-orders")
            print(f"  Session state: {await receiver.get_session_state()}")
            
            received = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
            print(f"  Received {len(received)} message(s)")
            
            for msg in received:
                print(f"    - {str(msg)}")
                await receiver.complete_message(msg)
            
            # Update session state
            await receiver.set_session_state(b"completed")
            print(f"  Updated session state: {await receiver.get_session_state()}")


async def batch_example():
    """
    Demonstrates batch operations for better performance.
    """
    print("\n\n=== Batch Operations Example ===\n")
    
    async with ServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
        
        # Send batch
        print("Sending batch of 100 messages...")
        sender = client.get_queue_sender("batch-queue")
        
        start = datetime.now()
        batch_message = await sender.create_message_batch()
        
        for i in range(100):
            try:
                batch_message.add_message(
                    ServiceBusMessage(
                        body=f"Message {i}",
                        application_properties={"index": i}
                    )
                )
            except ValueError:
                # Batch full, send and start new batch
                async with sender:
                    await sender.send_messages(batch_message)
                batch_message = await sender.create_message_batch()
        
        # Send remaining messages
        if batch_message:
            async with sender:
                await sender.send_messages(batch_message)
        
        elapsed = (datetime.now() - start).total_seconds()
        print(f"✓ Sent 100 messages in {elapsed:.2f}s ({100/elapsed:.0f} msg/s)\n")
        
        # Receive batch
        print("Receiving batch...")
        receiver = client.get_queue_receiver("batch-queue")
        
        start = datetime.now()
        total_received = 0
        
        async with receiver:
            # Receive in batches
            while total_received < 100:
                messages = await receiver.receive_messages(max_message_count=20, max_wait_time=2)
                if not messages:
                    break
                
                for msg in messages:
                    await receiver.complete_message(msg)
                    total_received += 1
        
        elapsed = (datetime.now() - start).total_seconds()
        print(f"✓ Received {total_received} messages in {elapsed:.2f}s ({total_received/elapsed:.0f} msg/s)")


async def error_handling_example():
    """
    Demonstrates proper error handling patterns.
    """
    print("\n\n=== Error Handling Example ===\n")
    
    async with ServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
        
        try:
            # Try to receive from non-existent queue
            print("Attempting to receive from non-existent queue...")
            receiver = client.get_queue_receiver("nonexistent-queue")
            
            async with receiver:
                messages = await receiver.receive_messages(max_message_count=1, max_wait_time=1)
        
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {e}\n")
        
        # Message processing with retry
        print("Processing messages with error handling...")
        sender = client.get_queue_sender("error-test")
        
        async with sender:
            await sender.send_messages([
                ServiceBusMessage("valid message"),
                ServiceBusMessage("message that will fail")
            ])
        
        receiver = client.get_queue_receiver("error-test")
        
        async with receiver:
            messages = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
            
            for msg in messages:
                try:
                    # Simulate processing
                    if "fail" in str(msg):
                        raise ValueError("Simulated processing error")
                    
                    print(f"  ✓ Processed: {str(msg)}")
                    await receiver.complete_message(msg)
                
                except Exception as e:
                    print(f"  ✗ Failed: {str(msg)} - {e}")
                    
                    # Retry logic
                    if msg.delivery_count < 3:
                        print(f"    → Abandoning for retry (delivery count: {msg.delivery_count})")
                        await receiver.abandon_message(msg)
                    else:
                        print(f"    → Dead-lettering after {msg.delivery_count} attempts")
                        await receiver.dead_letter_message(
                            msg,
                            reason="ProcessingFailed",
                            error_description=str(e)
                        )


async def main():
    """Run all examples."""
    print("=" * 70)
    print("LocalZure Service Bus - Python Examples")
    print("=" * 70)
    
    print("\nNote: This example requires:")
    print("  1. LocalZure Service Bus running on localhost:8000")
    print("  2. Entities created (queues, topics, subscriptions)")
    print("\nCreating entities...")
    
    # In production, you would create entities via management API or Azure Portal
    # For this example, we'll create them via REST API
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        # Create queues
        for queue in ["orders", "session-orders", "batch-queue", "error-test"]:
            requires_session = "session" in queue
            xml = f'''<entry xmlns="http://www.w3.org/2005/Atom">
                <content type="application/xml">
                    <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
                        <RequiresSession>{"true" if requires_session else "false"}</RequiresSession>
                    </QueueDescription>
                </content>
            </entry>'''
            
            await session.put(
                f"http://localhost:8000/servicebus/queues/{queue}",
                headers={"Content-Type": "application/xml"},
                data=xml
            )
        
        # Create topic
        await session.put(
            "http://localhost:8000/servicebus/topics/events",
            headers={"Content-Type": "application/xml"},
            data='<entry xmlns="http://www.w3.org/2005/Atom"><content type="application/xml"><TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"></TopicDescription></content></entry>'
        )
        
        # Create subscriptions with filters
        subscriptions = [
            ("high-priority", "priority = 'high'"),
            ("us-west", "region = 'us-west'"),
            ("all-events", "1=1")
        ]
        
        for sub_name, filter_expr in subscriptions:
            # Create subscription
            await session.put(
                f"http://localhost:8000/servicebus/topics/events/subscriptions/{sub_name}",
                headers={"Content-Type": "application/xml"},
                data='<entry xmlns="http://www.w3.org/2005/Atom"><content type="application/xml"><SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"></SubscriptionDescription></content></entry>'
            )
            
            # Create filter rule
            await session.put(
                f"http://localhost:8000/servicebus/topics/events/subscriptions/{sub_name}/rules/filter",
                headers={"Content-Type": "application/xml"},
                data=f'''<entry xmlns="http://www.w3.org/2005/Atom">
                    <content type="application/xml">
                        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
                            <Filter>
                                <SqlFilter>
                                    <SqlExpression>{filter_expr}</SqlExpression>
                                </SqlFilter>
                            </Filter>
                        </RuleDescription>
                    </content>
                </entry>'''
            )
    
    print("✓ Entities created\n")
    
    # Run examples
    try:
        await queue_example()
        await topic_subscription_example()
        await session_example()
        await batch_example()
        await error_handling_example()
        
        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)
    
    except Exception as e:
        print(f"\n\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
