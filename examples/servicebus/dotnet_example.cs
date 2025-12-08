/*
 * LocalZure Service Bus - C# .NET Example
 * 
 * Complete example demonstrating queue and topic operations using Azure.Messaging.ServiceBus SDK.
 * 
 * Requirements:
 *     dotnet add package Azure.Messaging.ServiceBus
 * 
 * Usage:
 *     dotnet run
 */

using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Azure.Messaging.ServiceBus;

namespace LocalZureServiceBusExample
{
    class Program
    {
        // LocalZure connection string
        private const string ConnectionString = "Endpoint=sb://localhost:8000/servicebus/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=fake-key";

        static async Task Main(string[] args)
        {
            Console.WriteLine("=" + new string('=', 68));
            Console.WriteLine("LocalZure Service Bus - C# .NET Examples");
            Console.WriteLine("=" + new string('=', 68));
            
            Console.WriteLine("\nNote: This example requires:");
            Console.WriteLine("  1. LocalZure Service Bus running on localhost:8000");
            Console.WriteLine("  2. Entities created (queues, topics, subscriptions)");
            
            try
            {
                await QueueExample();
                await TopicSubscriptionExample();
                await SessionExample();
                await BatchExample();
                await ErrorHandlingExample();
                
                Console.WriteLine("\n" + new string('=', 70));
                Console.WriteLine("All examples completed successfully!");
                Console.WriteLine(new string('=', 70));
            }
            catch (Exception ex)
            {
                Console.WriteLine($"\n\n✗ Error running examples: {ex.Message}");
                Console.WriteLine(ex.StackTrace);
            }
        }

        static async Task QueueExample()
        {
            Console.WriteLine("\n=== Queue Example ===\n");
            
            await using var client = new ServiceBusClient(ConnectionString);
            
            // Send messages to queue
            Console.WriteLine("Sending messages to 'orders' queue...");
            ServiceBusSender sender = client.CreateSender("orders");
            
            var messages = new List<ServiceBusMessage>
            {
                new ServiceBusMessage("Order 1001")
                {
                    ApplicationProperties =
                    {
                        ["order_id"] = 1001,
                        ["priority"] = "high",
                        ["customer_tier"] = "premium"
                    }
                },
                new ServiceBusMessage("Order 1002")
                {
                    ApplicationProperties =
                    {
                        ["order_id"] = 1002,
                        ["priority"] = "normal",
                        ["customer_tier"] = "standard"
                    }
                },
                new ServiceBusMessage("Order 1003 (will be dead-lettered)")
                {
                    ApplicationProperties =
                    {
                        ["order_id"] = 1003,
                        ["priority"] = "low"
                    }
                }
            };
            
            await sender.SendMessagesAsync(messages);
            Console.WriteLine($"✓ Sent {messages.Count} messages\n");
            
            // Receive and process messages
            Console.WriteLine("Receiving messages from 'orders' queue...");
            ServiceBusReceiver receiver = client.CreateReceiver("orders");
            
            for (int i = 0; i < 3; i++)
            {
                ServiceBusReceivedMessage msg = await receiver.ReceiveMessageAsync(TimeSpan.FromSeconds(5));
                if (msg == null) break;
                
                Console.WriteLine($"\nMessage {i + 1}:");
                Console.WriteLine($"  Body: {msg.Body}");
                Console.WriteLine($"  Properties: {string.Join(", ", msg.ApplicationProperties)}");
                Console.WriteLine($"  MessageId: {msg.MessageId}");
                Console.WriteLine($"  EnqueuedTime: {msg.EnqueuedTime}");
                Console.WriteLine($"  DeliveryCount: {msg.DeliveryCount}");
                
                // Complete first two messages
                if (i < 2)
                {
                    await receiver.CompleteMessageAsync(msg);
                    Console.WriteLine("  ✓ Completed");
                }
                else
                {
                    // Dead-letter the third message
                    await receiver.DeadLetterMessageAsync(
                        msg,
                        deadLetterReason: "InvalidOrder",
                        deadLetterErrorDescription: "Order validation failed"
                    );
                    Console.WriteLine("  ✗ Dead-lettered");
                }
            }
            
            // Read from dead-letter queue
            Console.WriteLine("\n\nChecking dead-letter queue...");
            ServiceBusReceiver dlqReceiver = client.CreateReceiver(
                "orders",
                new ServiceBusReceiverOptions { SubQueue = SubQueue.DeadLetter }
            );
            
            await foreach (ServiceBusReceivedMessage msg in dlqReceiver.ReceiveMessagesAsync())
            {
                Console.WriteLine($"\nDead-letter message:");
                Console.WriteLine($"  Body: {msg.Body}");
                Console.WriteLine($"  Reason: {msg.DeadLetterReason}");
                Console.WriteLine($"  Description: {msg.DeadLetterErrorDescription}");
                await dlqReceiver.CompleteMessageAsync(msg);
            }
            
            await sender.CloseAsync();
            await receiver.CloseAsync();
            await dlqReceiver.CloseAsync();
        }

        static async Task TopicSubscriptionExample()
        {
            Console.WriteLine("\n\n=== Topic/Subscription Example ===\n");
            
            await using var client = new ServiceBusClient(ConnectionString);
            
            // Publish messages to topic
            Console.WriteLine("Publishing messages to 'events' topic...");
            ServiceBusSender sender = client.CreateSender("events");
            
            var messages = new List<ServiceBusMessage>
            {
                new ServiceBusMessage("High priority alert")
                {
                    ApplicationProperties =
                    {
                        ["priority"] = "high",
                        ["region"] = "us-west",
                        ["event_type"] = "alert"
                    }
                },
                new ServiceBusMessage("Normal priority notification")
                {
                    ApplicationProperties =
                    {
                        ["priority"] = "normal",
                        ["region"] = "us-east",
                        ["event_type"] = "notification"
                    }
                },
                new ServiceBusMessage("Low priority log")
                {
                    ApplicationProperties =
                    {
                        ["priority"] = "low",
                        ["region"] = "eu-west",
                        ["event_type"] = "log"
                    }
                }
            };
            
            await sender.SendMessagesAsync(messages);
            Console.WriteLine($"✓ Published {messages.Count} messages\n");
            
            // Receive from high-priority subscription
            Console.WriteLine("Receiving from 'high-priority' subscription (filter: priority = 'high')...");
            ServiceBusReceiver receiver = client.CreateReceiver("events", "high-priority");
            
            var received = await receiver.ReceiveMessagesAsync(maxMessages: 10, maxWaitTime: TimeSpan.FromSeconds(5));
            Console.WriteLine($"  Received {received.Count} message(s)");
            
            foreach (var msg in received)
            {
                Console.WriteLine($"    - {msg.Body} (priority: {msg.ApplicationProperties["priority"]})");
                await receiver.CompleteMessageAsync(msg);
            }
            
            await receiver.CloseAsync();
            
            // Receive from us-west subscription
            Console.WriteLine("\nReceiving from 'us-west' subscription (filter: region = 'us-west')...");
            receiver = client.CreateReceiver("events", "us-west");
            
            received = await receiver.ReceiveMessagesAsync(maxMessages: 10, maxWaitTime: TimeSpan.FromSeconds(5));
            Console.WriteLine($"  Received {received.Count} message(s)");
            
            foreach (var msg in received)
            {
                Console.WriteLine($"    - {msg.Body} (region: {msg.ApplicationProperties["region"]})");
                await receiver.CompleteMessageAsync(msg);
            }
            
            await receiver.CloseAsync();
            await sender.CloseAsync();
        }

        static async Task SessionExample()
        {
            Console.WriteLine("\n\n=== Session Queue Example ===\n");
            
            await using var client = new ServiceBusClient(ConnectionString);
            
            // Send messages to session queue
            Console.WriteLine("Sending messages to 'session-orders' queue with sessions...");
            ServiceBusSender sender = client.CreateSender("session-orders");
            
            var sessions = new[] { "user-123", "user-456", "user-123", "user-456" };
            var messages = new List<ServiceBusMessage>();
            
            for (int i = 0; i < sessions.Length; i++)
            {
                messages.Add(new ServiceBusMessage($"Order {i + 1} for {sessions[i]}")
                {
                    SessionId = sessions[i],
                    ApplicationProperties = { ["order_num"] = i + 1 }
                });
            }
            
            await sender.SendMessagesAsync(messages);
            Console.WriteLine($"✓ Sent {messages.Count} messages across {new HashSet<string>(sessions).Count} sessions\n");
            
            // Process messages from specific session
            Console.WriteLine("Processing session 'user-123'...");
            ServiceBusSessionReceiver receiver = await client.AcceptSessionAsync(
                "session-orders",
                "user-123"
            );
            
            // Set session state
            await receiver.SetSessionStateAsync(new BinaryData("processing-orders"));
            var state = await receiver.GetSessionStateAsync();
            Console.WriteLine($"  Session state: {state}");
            
            var received = await receiver.ReceiveMessagesAsync(maxMessages: 10, maxWaitTime: TimeSpan.FromSeconds(5));
            Console.WriteLine($"  Received {received.Count} message(s)");
            
            foreach (var msg in received)
            {
                Console.WriteLine($"    - {msg.Body}");
                await receiver.CompleteMessageAsync(msg);
            }
            
            // Update session state
            await receiver.SetSessionStateAsync(new BinaryData("completed"));
            state = await receiver.GetSessionStateAsync();
            Console.WriteLine($"  Updated session state: {state}");
            
            await receiver.CloseAsync();
            await sender.CloseAsync();
        }

        static async Task BatchExample()
        {
            Console.WriteLine("\n\n=== Batch Operations Example ===\n");
            
            await using var client = new ServiceBusClient(ConnectionString);
            
            // Send batch
            Console.WriteLine("Sending batch of 100 messages...");
            ServiceBusSender sender = client.CreateSender("batch-queue");
            
            var start = DateTime.Now;
            using ServiceBusMessageBatch messageBatch = await sender.CreateMessageBatchAsync();
            
            for (int i = 0; i < 100; i++)
            {
                if (!messageBatch.TryAddMessage(new ServiceBusMessage($"Message {i}")
                {
                    ApplicationProperties = { ["index"] = i }
                }))
                {
                    // Batch full, send and start new batch
                    await sender.SendMessagesAsync(messageBatch);
                    messageBatch.Clear();
                }
            }
            
            // Send remaining messages
            if (messageBatch.Count > 0)
            {
                await sender.SendMessagesAsync(messageBatch);
            }
            
            var elapsed = (DateTime.Now - start).TotalSeconds;
            Console.WriteLine($"✓ Sent 100 messages in {elapsed:F2}s ({100/elapsed:F0} msg/s)\n");
            
            // Receive batch
            Console.WriteLine("Receiving batch...");
            ServiceBusReceiver receiver = client.CreateReceiver("batch-queue");
            
            start = DateTime.Now;
            int totalReceived = 0;
            
            while (totalReceived < 100)
            {
                var messages = await receiver.ReceiveMessagesAsync(
                    maxMessages: 20,
                    maxWaitTime: TimeSpan.FromSeconds(2)
                );
                
                if (messages.Count == 0) break;
                
                foreach (var msg in messages)
                {
                    await receiver.CompleteMessageAsync(msg);
                    totalReceived++;
                }
            }
            
            elapsed = (DateTime.Now - start).TotalSeconds;
            Console.WriteLine($"✓ Received {totalReceived} messages in {elapsed:F2}s ({totalReceived/elapsed:F0} msg/s)");
            
            await sender.CloseAsync();
            await receiver.CloseAsync();
        }

        static async Task ErrorHandlingExample()
        {
            Console.WriteLine("\n\n=== Error Handling Example ===\n");
            
            await using var client = new ServiceBusClient(ConnectionString);
            
            try
            {
                // Try to receive from non-existent queue
                Console.WriteLine("Attempting to receive from non-existent queue...");
                ServiceBusReceiver receiver = client.CreateReceiver("nonexistent-queue");
                
                var messages = await receiver.ReceiveMessagesAsync(
                    maxMessages: 1,
                    maxWaitTime: TimeSpan.FromSeconds(1)
                );
            }
            catch (Exception ex)
            {
                Console.WriteLine($"  ✗ Error: {ex.GetType().Name}: {ex.Message}\n");
            }
            
            // Message processing with retry
            Console.WriteLine("Processing messages with error handling...");
            ServiceBusSender sender = client.CreateSender("error-test");
            
            await sender.SendMessagesAsync(new[]
            {
                new ServiceBusMessage("valid message"),
                new ServiceBusMessage("message that will fail")
            });
            
            ServiceBusReceiver errorReceiver = client.CreateReceiver("error-test");
            var msgs = await errorReceiver.ReceiveMessagesAsync(
                maxMessages: 10,
                maxWaitTime: TimeSpan.FromSeconds(5)
            );
            
            foreach (var msg in msgs)
            {
                try
                {
                    // Simulate processing
                    if (msg.Body.ToString().Contains("fail"))
                    {
                        throw new InvalidOperationException("Simulated processing error");
                    }
                    
                    Console.WriteLine($"  ✓ Processed: {msg.Body}");
                    await errorReceiver.CompleteMessageAsync(msg);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"  ✗ Failed: {msg.Body} - {ex.Message}");
                    
                    // Retry logic
                    if (msg.DeliveryCount < 3)
                    {
                        Console.WriteLine($"    → Abandoning for retry (delivery count: {msg.DeliveryCount})");
                        await errorReceiver.AbandonMessageAsync(msg);
                    }
                    else
                    {
                        Console.WriteLine($"    → Dead-lettering after {msg.DeliveryCount} attempts");
                        await errorReceiver.DeadLetterMessageAsync(
                            msg,
                            deadLetterReason: "ProcessingFailed",
                            deadLetterErrorDescription: ex.Message
                        );
                    }
                }
            }
            
            await sender.CloseAsync();
            await errorReceiver.CloseAsync();
        }
    }
}
