"""
Create Service Bus entities for examples.

Run this once before running example scripts.
"""

import asyncio
import aiohttp


BASE_URL = "http://localhost:8000/servicebus"


async def create_entities():
    """Create queues, topics, and subscriptions for examples."""
    
    print("Creating Service Bus entities...\n")
    
    async with aiohttp.ClientSession() as session:
        
        # Create queues
        queues = [
            ("orders", False),
            ("session-orders", True),
            ("batch-queue", False),
            ("error-test", False)
        ]
        
        for queue_name, requires_session in queues:
            xml = f'''<entry xmlns="http://www.w3.org/2005/Atom">
                <content type="application/xml">
                    <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
                        <RequiresSession>{"true" if requires_session else "false"}</RequiresSession>
                    </QueueDescription>
                </content>
            </entry>'''
            
            async with session.put(
                f"{BASE_URL}/queues/{queue_name}",
                headers={"Content-Type": "application/xml"},
                data=xml
            ) as resp:
                if resp.status in (200, 201):
                    print(f"✓ Created queue: {queue_name}")
                else:
                    print(f"✗ Failed to create queue {queue_name}: {resp.status}")
        
        # Create topic
        async with session.put(
            f"{BASE_URL}/topics/events",
            headers={"Content-Type": "application/xml"},
            data='<entry xmlns="http://www.w3.org/2005/Atom"><content type="application/xml"><TopicDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"></TopicDescription></content></entry>'
        ) as resp:
            if resp.status in (200, 201):
                print(f"✓ Created topic: events")
        
        # Create subscriptions with filters
        subscriptions = [
            ("high-priority", "priority = 'high'"),
            ("us-west", "region = 'us-west'"),
            ("all-events", "1=1")
        ]
        
        for sub_name, filter_expr in subscriptions:
            # Create subscription
            async with session.put(
                f"{BASE_URL}/topics/events/subscriptions/{sub_name}",
                headers={"Content-Type": "application/xml"},
                data='<entry xmlns="http://www.w3.org/2005/Atom"><content type="application/xml"><SubscriptionDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"></SubscriptionDescription></content></entry>'
            ) as resp:
                if resp.status in (200, 201):
                    print(f"✓ Created subscription: {sub_name}")
            
            # Delete default rule
            await session.delete(f"{BASE_URL}/topics/events/subscriptions/{sub_name}/rules/$Default")
            
            # Create filter rule
            async with session.put(
                f"{BASE_URL}/topics/events/subscriptions/{sub_name}/rules/filter",
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
            ) as resp:
                if resp.status in (200, 201):
                    print(f"  ✓ Created filter: {filter_expr}")
    
    print("\n✓ All entities created successfully!")
    print("\nYou can now run the examples:")
    print("  python python_example.py")
    print("  dotnet run (in .NET project)")
    print("  java JavaExample (with classpath)")


if __name__ == "__main__":
    asyncio.run(create_entities())
