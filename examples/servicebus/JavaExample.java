/*
 * LocalZure Service Bus - Java Example
 * 
 * Complete example demonstrating queue and topic operations using Azure SDK for Java.
 * 
 * Requirements (Maven):
 *     <dependency>
 *         <groupId>com.azure</groupId>
 *         <artifactId>azure-messaging-servicebus</artifactId>
 *         <version>7.13.0</version>
 *     </dependency>
 * 
 * Usage:
 *     javac -cp azure-messaging-servicebus-7.13.0.jar JavaExample.java
 *     java -cp .:azure-messaging-servicebus-7.13.0.jar JavaExample
 */

import com.azure.messaging.servicebus.*;
import java.time.Duration;
import java.util.*;

public class JavaExample {
    
    // LocalZure connection string
    private static final String CONNECTION_STRING = 
        "Endpoint=sb://localhost:8000/servicebus/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=fake-key";
    
    public static void main(String[] args) {
        System.out.println("=".repeat(70));
        System.out.println("LocalZure Service Bus - Java Examples");
        System.out.println("=".repeat(70));
        
        System.out.println("\nNote: This example requires:");
        System.out.println("  1. LocalZure Service Bus running on localhost:8000");
        System.out.println("  2. Entities created (queues, topics, subscriptions)");
        
        try {
            queueExample();
            topicSubscriptionExample();
            sessionExample();
            batchExample();
            errorHandlingExample();
            
            System.out.println("\n" + "=".repeat(70));
            System.out.println("All examples completed successfully!");
            System.out.println("=".repeat(70));
        } catch (Exception ex) {
            System.out.println("\n\n✗ Error running examples: " + ex.getMessage());
            ex.printStackTrace();
        }
    }
    
    private static void queueExample() {
        System.out.println("\n=== Queue Example ===\n");
        
        ServiceBusClientBuilder builder = new ServiceBusClientBuilder()
            .connectionString(CONNECTION_STRING);
        
        // Send messages to queue
        System.out.println("Sending messages to 'orders' queue...");
        ServiceBusSenderClient sender = builder.sender()
            .queueName("orders")
            .buildClient();
        
        List<ServiceBusMessage> messages = Arrays.asList(
            new ServiceBusMessage("Order 1001")
                .getApplicationProperties()
                    .put("order_id", 1001)
                    .put("priority", "high")
                    .put("customer_tier", "premium")
                .getMessage(),
            new ServiceBusMessage("Order 1002")
                .getApplicationProperties()
                    .put("order_id", 1002)
                    .put("priority", "normal")
                    .put("customer_tier", "standard")
                .getMessage(),
            new ServiceBusMessage("Order 1003 (will be dead-lettered)")
                .getApplicationProperties()
                    .put("order_id", 1003)
                    .put("priority", "low")
                .getMessage()
        );
        
        sender.sendMessages(messages);
        System.out.println("✓ Sent " + messages.size() + " messages\n");
        
        // Receive and process messages
        System.out.println("Receiving messages from 'orders' queue...");
        ServiceBusReceiverClient receiver = builder.receiver()
            .queueName("orders")
            .buildClient();
        
        for (int i = 0; i < 3; i++) {
            ServiceBusReceivedMessage msg = receiver.receiveMessages(1, Duration.ofSeconds(5))
                .stream().findFirst().orElse(null);
            
            if (msg == null) break;
            
            System.out.println("\nMessage " + (i + 1) + ":");
            System.out.println("  Body: " + msg.getBody());
            System.out.println("  Properties: " + msg.getApplicationProperties());
            System.out.println("  MessageId: " + msg.getMessageId());
            System.out.println("  EnqueuedTime: " + msg.getEnqueuedTime());
            System.out.println("  DeliveryCount: " + msg.getDeliveryCount());
            
            // Complete first two messages
            if (i < 2) {
                receiver.complete(msg);
                System.out.println("  ✓ Completed");
            } else {
                // Dead-letter the third message
                receiver.deadLetter(msg, 
                    new DeadLetterOptions()
                        .setDeadLetterReason("InvalidOrder")
                        .setDeadLetterErrorDescription("Order validation failed")
                );
                System.out.println("  ✗ Dead-lettered");
            }
        }
        
        // Read from dead-letter queue
        System.out.println("\n\nChecking dead-letter queue...");
        ServiceBusReceiverClient dlqReceiver = builder.receiver()
            .queueName("orders")
            .subQueue(SubQueue.DEAD_LETTER_QUEUE)
            .buildClient();
        
        dlqReceiver.receiveMessages(10, Duration.ofSeconds(5))
            .forEach(msg -> {
                System.out.println("\nDead-letter message:");
                System.out.println("  Body: " + msg.getBody());
                System.out.println("  Reason: " + msg.getDeadLetterReason());
                System.out.println("  Description: " + msg.getDeadLetterErrorDescription());
                dlqReceiver.complete(msg);
            });
        
        sender.close();
        receiver.close();
        dlqReceiver.close();
    }
    
    private static void topicSubscriptionExample() {
        System.out.println("\n\n=== Topic/Subscription Example ===\n");
        
        ServiceBusClientBuilder builder = new ServiceBusClientBuilder()
            .connectionString(CONNECTION_STRING);
        
        // Publish messages to topic
        System.out.println("Publishing messages to 'events' topic...");
        ServiceBusSenderClient sender = builder.sender()
            .topicName("events")
            .buildClient();
        
        List<ServiceBusMessage> messages = Arrays.asList(
            new ServiceBusMessage("High priority alert")
                .getApplicationProperties()
                    .put("priority", "high")
                    .put("region", "us-west")
                    .put("event_type", "alert")
                .getMessage(),
            new ServiceBusMessage("Normal priority notification")
                .getApplicationProperties()
                    .put("priority", "normal")
                    .put("region", "us-east")
                    .put("event_type", "notification")
                .getMessage(),
            new ServiceBusMessage("Low priority log")
                .getApplicationProperties()
                    .put("priority", "low")
                    .put("region", "eu-west")
                    .put("event_type", "log")
                .getMessage()
        );
        
        sender.sendMessages(messages);
        System.out.println("✓ Published " + messages.size() + " messages\n");
        
        // Receive from high-priority subscription
        System.out.println("Receiving from 'high-priority' subscription (filter: priority = 'high')...");
        ServiceBusReceiverClient receiver = builder.receiver()
            .topicName("events")
            .subscriptionName("high-priority")
            .buildClient();
        
        List<ServiceBusReceivedMessage> received = receiver.receiveMessages(10, Duration.ofSeconds(5))
            .stream().toList();
        System.out.println("  Received " + received.size() + " message(s)");
        
        for (ServiceBusReceivedMessage msg : received) {
            System.out.println("    - " + msg.getBody() + " (priority: " + 
                msg.getApplicationProperties().get("priority") + ")");
            receiver.complete(msg);
        }
        
        receiver.close();
        
        // Receive from us-west subscription
        System.out.println("\nReceiving from 'us-west' subscription (filter: region = 'us-west')...");
        receiver = builder.receiver()
            .topicName("events")
            .subscriptionName("us-west")
            .buildClient();
        
        received = receiver.receiveMessages(10, Duration.ofSeconds(5))
            .stream().toList();
        System.out.println("  Received " + received.size() + " message(s)");
        
        for (ServiceBusReceivedMessage msg : received) {
            System.out.println("    - " + msg.getBody() + " (region: " + 
                msg.getApplicationProperties().get("region") + ")");
            receiver.complete(msg);
        }
        
        receiver.close();
        sender.close();
    }
    
    private static void sessionExample() {
        System.out.println("\n\n=== Session Queue Example ===\n");
        
        ServiceBusClientBuilder builder = new ServiceBusClientBuilder()
            .connectionString(CONNECTION_STRING);
        
        // Send messages to session queue
        System.out.println("Sending messages to 'session-orders' queue with sessions...");
        ServiceBusSenderClient sender = builder.sender()
            .queueName("session-orders")
            .buildClient();
        
        String[] sessions = {"user-123", "user-456", "user-123", "user-456"};
        List<ServiceBusMessage> messages = new ArrayList<>();
        
        for (int i = 0; i < sessions.length; i++) {
            messages.add(new ServiceBusMessage("Order " + (i + 1) + " for " + sessions[i])
                .setSessionId(sessions[i])
                .getApplicationProperties()
                    .put("order_num", i + 1)
                .getMessage());
        }
        
        sender.sendMessages(messages);
        System.out.println("✓ Sent " + messages.size() + " messages across " + 
            new HashSet<>(Arrays.asList(sessions)).size() + " sessions\n");
        
        // Process messages from specific session
        System.out.println("Processing session 'user-123'...");
        ServiceBusSessionReceiverClient receiver = builder.sessionReceiver()
            .queueName("session-orders")
            .buildClient();
        
        ServiceBusReceiverClient sessionReceiver = receiver.acceptSession("user-123");
        
        // Set session state
        sessionReceiver.setSessionState("processing-orders".getBytes());
        byte[] state = sessionReceiver.getSessionState();
        System.out.println("  Session state: " + new String(state));
        
        List<ServiceBusReceivedMessage> received = sessionReceiver.receiveMessages(10, Duration.ofSeconds(5))
            .stream().toList();
        System.out.println("  Received " + received.size() + " message(s)");
        
        for (ServiceBusReceivedMessage msg : received) {
            System.out.println("    - " + msg.getBody());
            sessionReceiver.complete(msg);
        }
        
        // Update session state
        sessionReceiver.setSessionState("completed".getBytes());
        state = sessionReceiver.getSessionState();
        System.out.println("  Updated session state: " + new String(state));
        
        sessionReceiver.close();
        receiver.close();
        sender.close();
    }
    
    private static void batchExample() {
        System.out.println("\n\n=== Batch Operations Example ===\n");
        
        ServiceBusClientBuilder builder = new ServiceBusClientBuilder()
            .connectionString(CONNECTION_STRING);
        
        // Send batch
        System.out.println("Sending batch of 100 messages...");
        ServiceBusSenderClient sender = builder.sender()
            .queueName("batch-queue")
            .buildClient();
        
        long start = System.currentTimeMillis();
        ServiceBusMessageBatch messageBatch = sender.createMessageBatch();
        
        for (int i = 0; i < 100; i++) {
            ServiceBusMessage message = new ServiceBusMessage("Message " + i)
                .getApplicationProperties()
                    .put("index", i)
                .getMessage();
            
            if (!messageBatch.tryAddMessage(message)) {
                // Batch full, send and start new batch
                sender.sendMessages(messageBatch);
                messageBatch = sender.createMessageBatch();
                messageBatch.tryAddMessage(message);
            }
        }
        
        // Send remaining messages
        if (messageBatch.getCount() > 0) {
            sender.sendMessages(messageBatch);
        }
        
        double elapsed = (System.currentTimeMillis() - start) / 1000.0;
        System.out.println(String.format("✓ Sent 100 messages in %.2fs (%.0f msg/s)\n", 
            elapsed, 100 / elapsed));
        
        // Receive batch
        System.out.println("Receiving batch...");
        ServiceBusReceiverClient receiver = builder.receiver()
            .queueName("batch-queue")
            .buildClient();
        
        start = System.currentTimeMillis();
        int totalReceived = 0;
        
        while (totalReceived < 100) {
            List<ServiceBusReceivedMessage> messages = receiver.receiveMessages(20, Duration.ofSeconds(2))
                .stream().toList();
            
            if (messages.isEmpty()) break;
            
            for (ServiceBusReceivedMessage msg : messages) {
                receiver.complete(msg);
                totalReceived++;
            }
        }
        
        elapsed = (System.currentTimeMillis() - start) / 1000.0;
        System.out.println(String.format("✓ Received %d messages in %.2fs (%.0f msg/s)", 
            totalReceived, elapsed, totalReceived / elapsed));
        
        sender.close();
        receiver.close();
    }
    
    private static void errorHandlingExample() {
        System.out.println("\n\n=== Error Handling Example ===\n");
        
        ServiceBusClientBuilder builder = new ServiceBusClientBuilder()
            .connectionString(CONNECTION_STRING);
        
        try {
            // Try to receive from non-existent queue
            System.out.println("Attempting to receive from non-existent queue...");
            ServiceBusReceiverClient receiver = builder.receiver()
                .queueName("nonexistent-queue")
                .buildClient();
            
            receiver.receiveMessages(1, Duration.ofSeconds(1));
        } catch (Exception ex) {
            System.out.println("  ✗ Error: " + ex.getClass().getSimpleName() + ": " + ex.getMessage() + "\n");
        }
        
        // Message processing with retry
        System.out.println("Processing messages with error handling...");
        ServiceBusSenderClient sender = builder.sender()
            .queueName("error-test")
            .buildClient();
        
        sender.sendMessages(Arrays.asList(
            new ServiceBusMessage("valid message"),
            new ServiceBusMessage("message that will fail")
        ));
        
        ServiceBusReceiverClient receiver = builder.receiver()
            .queueName("error-test")
            .buildClient();
        
        receiver.receiveMessages(10, Duration.ofSeconds(5))
            .forEach(msg -> {
                try {
                    // Simulate processing
                    if (msg.getBody().toString().contains("fail")) {
                        throw new RuntimeException("Simulated processing error");
                    }
                    
                    System.out.println("  ✓ Processed: " + msg.getBody());
                    receiver.complete(msg);
                } catch (Exception ex) {
                    System.out.println("  ✗ Failed: " + msg.getBody() + " - " + ex.getMessage());
                    
                    // Retry logic
                    if (msg.getDeliveryCount() < 3) {
                        System.out.println("    → Abandoning for retry (delivery count: " + 
                            msg.getDeliveryCount() + ")");
                        receiver.abandon(msg);
                    } else {
                        System.out.println("    → Dead-lettering after " + 
                            msg.getDeliveryCount() + " attempts");
                        receiver.deadLetter(msg,
                            new DeadLetterOptions()
                                .setDeadLetterReason("ProcessingFailed")
                                .setDeadLetterErrorDescription(ex.getMessage())
                        );
                    }
                }
            });
        
        sender.close();
        receiver.close();
    }
}
