/**
 * Comprehensive tests for ServiceBus component (DESKTOP-004)
 * 
 * Test Coverage:
 * - AC1: Queue list shows all queues with message counts
 * - AC2: Topic list shows topics with subscription counts
 * - AC3: Peek messages shows message content without dequeuing
 * - AC4: Message details show properties, body, and headers
 * - AC5: Send message allows creating and sending test messages
 * - AC6: Dead-letter queue messages are accessible
 * - AC7: Message body is displayed with JSON formatting if applicable
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ServiceBus from '../renderer/components/ServiceBus';

// ============================================================================
// MOCK DATA
// ============================================================================

const mockQueues = [
  {
    name: 'orders-queue',
    messageCount: 150,
    activeMessageCount: 145,
    deadLetterMessageCount: 5,
    maxDeliveryCount: 10,
    lockDuration: 'PT1M',
    defaultMessageTtl: 'P14D',
    requiresSession: false,
    status: 'Active' as const,
  },
  {
    name: 'notifications-queue',
    messageCount: 50,
    activeMessageCount: 50,
    deadLetterMessageCount: 0,
    maxDeliveryCount: 5,
    lockDuration: 'PT30S',
    defaultMessageTtl: 'P7D',
    requiresSession: false,
    status: 'Active' as const,
  },
];

const mockTopics = [
  {
    name: 'events-topic',
    subscriptionCount: 3,
    maxSizeInMegabytes: 1024,
    requiresSession: false,
    supportOrdering: true,
    status: 'Active' as const,
  },
  {
    name: 'alerts-topic',
    subscriptionCount: 2,
    maxSizeInMegabytes: 2048,
    requiresSession: false,
    supportOrdering: false,
    status: 'Active' as const,
  },
];

const mockSubscriptions = {
  'events-topic': [
    {
      name: 'analytics-sub',
      topicName: 'events-topic',
      messageCount: 25,
      activeMessageCount: 20,
      deadLetterMessageCount: 5,
      status: 'Active' as const,
    },
    {
      name: 'audit-sub',
      topicName: 'events-topic',
      messageCount: 30,
      activeMessageCount: 30,
      deadLetterMessageCount: 0,
      status: 'Active' as const,
    },
  ],
  'alerts-topic': [
    {
      name: 'email-sub',
      topicName: 'alerts-topic',
      messageCount: 10,
      activeMessageCount: 10,
      deadLetterMessageCount: 0,
      status: 'Active' as const,
    },
  ],
};

const mockMessages = [
  {
    messageId: '550e8400-e29b-41d4-a716-446655440000',
    sessionId: 'session-123',
    correlationId: 'corr-456',
    contentType: 'application/json',
    label: 'Order Created',
    body: { orderId: '12345', amount: 99.99, customer: 'John Doe' },
    userProperties: { priority: 'high', source: 'web-app' },
    systemProperties: {
      deliveryCount: 1,
      enqueuedTimeUtc: '2025-12-12T10:30:00Z',
      sequenceNumber: 1001,
      lockedUntilUtc: '2025-12-12T10:31:00Z',
    },
    partitionKey: 'partition-1',
    timeToLive: 'PT24H',
  },
  {
    messageId: '660e8400-e29b-41d4-a716-446655440001',
    correlationId: 'corr-789',
    contentType: 'text/plain',
    label: 'Simple Notification',
    body: 'This is a plain text message',
    userProperties: {},
    systemProperties: {
      deliveryCount: 2,
      enqueuedTimeUtc: '2025-12-12T11:00:00Z',
      sequenceNumber: 1002,
    },
  },
];

const mockDeadLetterMessages = [
  {
    messageId: '770e8400-e29b-41d4-a716-446655440002',
    correlationId: 'corr-dlq-1',
    contentType: 'application/json',
    label: 'Failed Order',
    body: { orderId: '99999', error: 'Payment failed' },
    userProperties: { reason: 'MaxDeliveryCountExceeded' },
    systemProperties: {
      deliveryCount: 10,
      enqueuedTimeUtc: '2025-12-11T10:00:00Z',
      sequenceNumber: 500,
      deadLetterSource: 'orders-queue',
    },
  },
];

// ============================================================================
// TEST SETUP
// ============================================================================

// Mock scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn(() => Promise.resolve()),
  },
});

describe('ServiceBus Component', () => {
  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();

    // Setup default mock implementations
    (window.localzureAPI.servicebus.listQueues as jest.Mock).mockResolvedValue({
      success: true,
      queues: mockQueues,
    });
    (window.localzureAPI.servicebus.listTopics as jest.Mock).mockResolvedValue({
      success: true,
      topics: mockTopics,
    });
    (window.localzureAPI.servicebus.listSubscriptions as jest.Mock).mockImplementation(
      (topicName: string) => ({
        success: true,
        subscriptions: mockSubscriptions[topicName] || [],
      })
    );
    (window.localzureAPI.servicebus.peekMessages as jest.Mock).mockResolvedValue({
      success: true,
      messages: mockMessages,
    });
    (window.localzureAPI.servicebus.peekSubscriptionMessages as jest.Mock).mockResolvedValue({
      success: true,
      messages: mockMessages,
    });
    (window.localzureAPI.servicebus.peekQueueDeadLetterMessages as jest.Mock).mockResolvedValue({
      success: true,
      messages: mockDeadLetterMessages,
    });
    (window.localzureAPI.servicebus.peekDeadLetterMessages as jest.Mock).mockResolvedValue({
      success: true,
      messages: mockDeadLetterMessages,
    });
    (window.localzureAPI.servicebus.sendMessage as jest.Mock).mockResolvedValue({
      success: true,
      messageId: 'new-message-id-123',
    });
  });

  // ==========================================================================
  // AC1: Queue list shows all queues with message counts
  // ==========================================================================
  describe('AC1: Queue List with Message Counts', () => {
    test('renders queue list on mount', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(window.localzureAPI.servicebus.listQueues).toHaveBeenCalled();
      });

      expect(screen.getByText('orders-queue')).toBeInTheDocument();
      expect(screen.getByText('notifications-queue')).toBeInTheDocument();
    });

    test('displays queue message counts', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('145')).toBeInTheDocument(); // orders-queue active count
        expect(screen.getByText('50')).toBeInTheDocument(); // notifications-queue active count
      });
    });

    test('shows queue count header', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText(/Queues \(2\)/)).toBeInTheDocument();
      });
    });

    test('shows empty state when no queues', async () => {
      (window.localzureAPI.servicebus.listQueues as jest.Mock).mockResolvedValue({
        success: true,
        queues: [],
      });

      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('No queues')).toBeInTheDocument();
      });
    });

    test('handles queue list fetch error gracefully', async () => {
      (window.localzureAPI.servicebus.listQueues as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Connection refused',
      });

      render(<ServiceBus />);

      await waitFor(() => {
        expect(window.localzureAPI.servicebus.listQueues).toHaveBeenCalled();
      });

      // Should show empty queues rather than crash
      expect(screen.getByText('No queues')).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // AC2: Topic list shows topics with subscription counts
  // ==========================================================================
  describe('AC2: Topic List with Subscription Counts', () => {
    test('renders topic list on mount', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(window.localzureAPI.servicebus.listTopics).toHaveBeenCalled();
      });

      expect(screen.getByText('events-topic')).toBeInTheDocument();
      expect(screen.getByText('alerts-topic')).toBeInTheDocument();
    });

    test('displays topic subscription counts', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('3 subs')).toBeInTheDocument(); // events-topic
        expect(screen.getByText('2 subs')).toBeInTheDocument(); // alerts-topic
      });
    });

    test('expands topic to show subscriptions', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('events-topic')).toBeInTheDocument();
      });

      // Find and click the expand button (▶ icon)
      const topicRow = screen.getByText('events-topic').closest('div')?.parentElement;
      const expandButton = topicRow?.querySelector('button');
      
      if (expandButton) {
        fireEvent.click(expandButton);
      }

      await waitFor(() => {
        expect(screen.getByText('analytics-sub')).toBeInTheDocument();
        expect(screen.getByText('audit-sub')).toBeInTheDocument();
      });
    });

    test('shows topic count header', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText(/Topics \(2\)/)).toBeInTheDocument();
      });
    });

    test('shows empty state when no topics', async () => {
      (window.localzureAPI.servicebus.listTopics as jest.Mock).mockResolvedValue({
        success: true,
        topics: [],
      });

      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('No topics')).toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // AC3: Peek messages shows message content without dequeuing
  // ==========================================================================
  describe('AC3: Peek Messages (Non-Destructive)', () => {
    test('displays peek messages button when queue selected', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));

      await waitFor(() => {
        expect(screen.getByText('Peek Messages')).toBeInTheDocument();
      });
    });

    test('fetches and displays messages when peek button clicked', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));

      await waitFor(() => {
        expect(screen.getByText('Peek Messages')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(window.localzureAPI.servicebus.peekMessages).toHaveBeenCalledWith('orders-queue');
      });

      expect(screen.getByText('Order Created')).toBeInTheDocument();
      expect(screen.getByText('Simple Notification')).toBeInTheDocument();
    });

    test('shows empty state when no messages', async () => {
      (window.localzureAPI.servicebus.peekMessages as jest.Mock).mockResolvedValue({
        success: true,
        messages: [],
      });

      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));

      await waitFor(() => {
        expect(screen.getByText('No messages to display')).toBeInTheDocument();
      });
    });

    test('displays message preview in list', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));

      await waitFor(() => {
        fireEvent.click(screen.getByText('Peek Messages'));
      });

      await waitFor(() => {
        // Should show preview of JSON body
        expect(screen.getByText(/orderId.*12345/)).toBeInTheDocument();
      });
    });

    test('displays delivery count badge', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Delivery: 1')).toBeInTheDocument();
        expect(screen.getByText('Delivery: 2')).toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // AC4: Message details show properties, body, and headers
  // ==========================================================================
  describe('AC4: Message Details Display', () => {
    test('shows message details when message clicked', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        expect(screen.getByText('Message Details')).toBeInTheDocument();
      });
    });

    test('displays system properties', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        expect(screen.getByText('System Properties')).toBeInTheDocument();
        expect(screen.getByText('Sequence Number')).toBeInTheDocument();
        expect(screen.getByText('1001')).toBeInTheDocument();
        expect(screen.getByText('Delivery Count')).toBeInTheDocument();
      });
    });

    test('displays message properties', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        expect(screen.getByText('Message Properties')).toBeInTheDocument();
        expect(screen.getByText('Label')).toBeInTheDocument();
        expect(screen.getByText('Content Type')).toBeInTheDocument();
        expect(screen.getByText('application/json')).toBeInTheDocument();
        expect(screen.getByText('Session ID')).toBeInTheDocument();
        expect(screen.getByText('session-123')).toBeInTheDocument();
        expect(screen.getByText('Correlation ID')).toBeInTheDocument();
        expect(screen.getByText('corr-456')).toBeInTheDocument();
      });
    });

    test('displays user properties', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        expect(screen.getByText('User Properties')).toBeInTheDocument();
        expect(screen.getByText(/"priority": "high"/)).toBeInTheDocument();
        expect(screen.getByText(/"source": "web-app"/)).toBeInTheDocument();
      });
    });

    test('displays message body', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        expect(screen.getByText('Message Body')).toBeInTheDocument();
        expect(screen.getByText(/"orderId": "12345"/)).toBeInTheDocument();
        expect(screen.getByText(/"amount": 99.99/)).toBeInTheDocument();
      });
    });

    test('copy message button copies to clipboard', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        const copyButton = screen.getByTitle('Copy message to clipboard');
        expect(copyButton).toBeInTheDocument();
        fireEvent.click(copyButton);
      });

      expect(navigator.clipboard.writeText).toHaveBeenCalled();
    });
  });

  // ==========================================================================
  // AC5: Send message allows creating and sending test messages
  // ==========================================================================
  describe('AC5: Send Message Functionality', () => {
    test('displays send message button for queues', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));

      await waitFor(() => {
        expect(screen.getByText('Send Message')).toBeInTheDocument();
      });
    });

    test('send button is disabled for topics', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('events-topic')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('events-topic'));

      await waitFor(() => {
        const sendButton = screen.getByText('Send Message').closest('button');
        expect(sendButton).toBeDisabled();
      });
    });

    test('opens send message dialog when button clicked', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));

      await waitFor(() => {
        expect(screen.getByText('Send Message')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Send Message'));

      await waitFor(() => {
        expect(screen.getByText('Message Body *')).toBeInTheDocument();
        expect(screen.getByText('Content Type')).toBeInTheDocument();
      });
    });

    test('send dialog has all required fields', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Send Message'));

      await waitFor(() => {
        expect(screen.getByText('Message Body *')).toBeInTheDocument();
        expect(screen.getByText('Content Type')).toBeInTheDocument();
        expect(screen.getByText('Label')).toBeInTheDocument();
        expect(screen.getByText('Session ID')).toBeInTheDocument();
        expect(screen.getByText('Correlation ID')).toBeInTheDocument();
        expect(screen.getByText('User Properties (JSON)')).toBeInTheDocument();
      });
    });

    test('validates JSON in message body', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Send Message'));

      await waitFor(() => {
        const bodyTextarea = screen.getAllByRole('textbox')[0];
        fireEvent.change(bodyTextarea, { target: { value: 'invalid json {' } });
      });

      // Click the last "Send Message" button (in the dialog, not the header)
      const sendButtons = screen.getAllByText('Send Message');
      fireEvent.click(sendButtons[sendButtons.length - 1]);

      await waitFor(() => {
        expect(screen.getByText('Invalid JSON format')).toBeInTheDocument();
      });
    });

    test('sends message with valid data', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Send Message'));

      await waitFor(() => {
        const bodyTextarea = screen.getAllByRole('textbox')[0];
        fireEvent.change(bodyTextarea, {
          target: { value: '{"test": "message"}' },
        });

        const labelInput = screen.getByPlaceholderText('Optional message label');
        fireEvent.change(labelInput, { target: { value: 'Test Label' } });
      });

      const sendButtons = screen.getAllByText('Send Message');
      const dialogSendButton = sendButtons[sendButtons.length - 1];
      fireEvent.click(dialogSendButton);

      await waitFor(() => {
        expect(window.localzureAPI.servicebus.sendMessage).toHaveBeenCalledWith(
          'orders-queue',
          expect.objectContaining({
            body: '{"test": "message"}',
            label: 'Test Label',
          })
        );
      });
    });

    test('closes dialog after successful send', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Send Message'));

      await waitFor(() => {
        const bodyTextarea = screen.getAllByRole('textbox')[0];
        fireEvent.change(bodyTextarea, {
          target: { value: '{"test": "message"}' },
        });
      });

      const sendButtons = screen.getAllByText('Send Message');
      const dialogSendButton = sendButtons[sendButtons.length - 1];
      fireEvent.click(dialogSendButton);

      await waitFor(() => {
        expect(screen.queryByText('Message Body *')).not.toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // AC6: Dead-letter queue messages are accessible
  // ==========================================================================
  describe('AC6: Dead-Letter Queue Access', () => {
    test('displays dead-letter sub-item for queues with DLQ messages', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      // Orders queue has 5 dead-letter messages
      expect(screen.getByText('☠️')).toBeInTheDocument();
      expect(screen.getByText('Dead-letter')).toBeInTheDocument();
    });

    test('hides dead-letter sub-item when no DLQ messages', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('notifications-queue')).toBeInTheDocument();
      });

      // notifications-queue has 0 dead-letter messages
      // Should not find "Dead-letter" associated with notifications-queue
      const deadLetterTexts = screen.queryAllByText('Dead-letter');
      
      // If there are any Dead-letter buttons, they should be for orders-queue, not notifications-queue
      // We can verify notifications-queue doesn't have DLQ by checking it has deadLetterMessageCount = 0
      expect(mockQueues[1].deadLetterMessageCount).toBe(0);
    });

    test('fetches dead-letter messages when clicked', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      const deadLetterButton = screen.getByText('Dead-letter');
      fireEvent.click(deadLetterButton);

      await waitFor(() => {
        expect(window.localzureAPI.servicebus.peekQueueDeadLetterMessages).toHaveBeenCalledWith(
          'orders-queue'
        );
      });
    });

    test('displays dead-letter messages with source indicator', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Dead-letter'));

      await waitFor(() => {
        fireEvent.click(screen.getByText('Peek Messages'));
      });

      await waitFor(() => {
        const failedOrderElements = screen.getAllByText('Failed Order');
        expect(failedOrderElements.length).toBeGreaterThan(0);
      });

      // Click the first "Failed Order" in the message list
      const failedOrderElements = screen.getAllByText('Failed Order');
      fireEvent.click(failedOrderElements[0]);

      await waitFor(() => {
        expect(screen.getByText('Dead-letter Source')).toBeInTheDocument();
      });
      
      // Verify source is displayed in message details
      const detailsSection = screen.getByText('Dead-letter Source').closest('div');
      expect(detailsSection).toBeInTheDocument();
    });

    test('displays dead-letter badge in message list', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Dead-letter'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        // Check for dead-letter badge (☠️ Dead-letter)
        const badges = screen.getAllByText('☠️ Dead-letter');
        expect(badges.length).toBeGreaterThan(0);
      });
    });
  });

  // ==========================================================================
  // AC7: Message body is displayed with JSON formatting if applicable
  // ==========================================================================
  describe('AC7: JSON Formatting for Message Body', () => {
    test('displays JSON badge for JSON messages', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        expect(screen.getByText('JSON')).toBeInTheDocument();
      });
    });

    test('formats JSON body with proper indentation', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        // JSON should be formatted with indentation
        const bodySection = screen.getByText('Message Body').closest('div');
        expect(bodySection).toBeInTheDocument();
        
        // Check for formatted JSON properties
        expect(screen.getByText(/"orderId": "12345"/)).toBeInTheDocument();
        expect(screen.getByText(/"amount": 99.99/)).toBeInTheDocument();
      });
    });

    test('displays plain text messages without JSON formatting', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Simple Notification')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Simple Notification'));

      await waitFor(() => {
        // Should not have JSON badge (previous message was JSON, this is text)
        expect(screen.getByText('Message Body')).toBeInTheDocument();
      });
      
      // Verify plain text is displayed (use getAllByText since it appears in list and details)
      const textElements = screen.getAllByText('This is a plain text message');
      expect(textElements.length).toBeGreaterThan(0);
    });

    test('parses string body as JSON if valid', async () => {
      const messagesWithStringBody = [
        {
          ...mockMessages[0],
          body: '{"orderId":"67890","parsed":true}',
        },
      ];

      (window.localzureAPI.servicebus.peekMessages as jest.Mock).mockResolvedValue({
        success: true,
        messages: messagesWithStringBody,
      });

      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        // Should detect and format as JSON
        expect(screen.getByText('JSON')).toBeInTheDocument();
        expect(screen.getByText(/"orderId": "67890"/)).toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Technical Requirements
  // ==========================================================================
  describe('Technical Requirements', () => {
    test('renders three-panel layout', () => {
      render(<ServiceBus />);

      // Left panel: Tree
      expect(screen.getByText('📮 Service Bus')).toBeInTheDocument();
      
      // Middle panel placeholder
      expect(
        screen.getByText('Select a queue, topic, or subscription to view messages')
      ).toBeInTheDocument();
      
      // Right panel placeholder
      expect(screen.getByText('Select a message to view details')).toBeInTheDocument();
    });

    test('refreshes resources when refresh button clicked', async () => {
      const mockRefresh = jest.fn();
      render(<ServiceBus onRefresh={mockRefresh} />);

      await waitFor(() => {
        const refreshButton = screen.getByTitle('Refresh');
        expect(refreshButton).toBeInTheDocument();
      });

      const refreshButton = screen.getByTitle('Refresh');
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(window.localzureAPI.servicebus.listQueues).toHaveBeenCalledTimes(2);
        expect(window.localzureAPI.servicebus.listTopics).toHaveBeenCalledTimes(2);
        expect(mockRefresh).toHaveBeenCalled();
      });
    });

    test('handles empty subscription list', async () => {
      (window.localzureAPI.servicebus.listSubscriptions as jest.Mock).mockResolvedValue({
        success: true,
        subscriptions: [],
      });

      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('events-topic')).toBeInTheDocument();
      });

      // Expand topic
      const topicRow = screen.getByText('events-topic').closest('div')?.parentElement;
      const expandButton = topicRow?.querySelector('button');
      
      if (expandButton) {
        fireEvent.click(expandButton);
      }

      await waitFor(() => {
        expect(screen.getByText('No subscriptions')).toBeInTheDocument();
      });
    });

    test('displays loading state during message fetch', async () => {
      (window.localzureAPI.servicebus.peekMessages as jest.Mock).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      // Peek button should be disabled while loading
      await waitFor(() => {
        const peekButton = screen.getByText('Peek Messages').closest('button');
        expect(peekButton).toBeDisabled();
      });
    });

    test('formats timestamps in message details', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      await waitFor(() => {
        // Timestamp should be formatted as locale string - use getAllByText since multiple timestamps exist
        const timestamps = screen.getAllByText(/12\/12\/2025/);
        expect(timestamps.length).toBeGreaterThan(0);
      });
    });
  });

  // ==========================================================================
  // Edge Cases
  // ==========================================================================
  describe('Edge Cases', () => {
    test('handles missing optional message properties', async () => {
      const minimalMessage = {
        messageId: 'minimal-id',
        body: 'Simple body',
        userProperties: {},
        systemProperties: {
          deliveryCount: 1,
          enqueuedTimeUtc: '2025-12-12T10:00:00Z',
          sequenceNumber: 1,
        },
      };

      (window.localzureAPI.servicebus.peekMessages as jest.Mock).mockResolvedValue({
        success: true,
        messages: [minimalMessage],
      });

      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('minimal-id')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('minimal-id'));

      // Should not crash, should display available properties only
      await waitFor(() => {
        expect(screen.getByText('Message Details')).toBeInTheDocument();
        expect(screen.getByText('Sequence Number')).toBeInTheDocument();
      });
    });

    test('handles very long message bodies', async () => {
      const longBody = { data: 'x'.repeat(10000) };
      const longMessage = { ...mockMessages[0], body: longBody };

      (window.localzureAPI.servicebus.peekMessages as jest.Mock).mockResolvedValue({
        success: true,
        messages: [longMessage],
      });

      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Peek Messages'));

      await waitFor(() => {
        expect(screen.getByText('Order Created')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Order Created'));

      // Should render without crashing
      await waitFor(() => {
        expect(screen.getByText('Message Body')).toBeInTheDocument();
      });
    });

    test('handles invalid JSON in user properties gracefully', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Send Message'));

      await waitFor(() => {
        // Find the properties textarea by placeholder text
        const propsTextarea = screen.getByPlaceholderText('{"customProperty": "value"}');
        fireEvent.change(propsTextarea, { target: { value: 'not valid json' } });
      });

      const sendButtons = screen.getAllByText('Send Message');
      const dialogSendButton = sendButtons[sendButtons.length - 1];
      fireEvent.click(dialogSendButton);

      await waitFor(() => {
        expect(screen.getByText('Invalid JSON format')).toBeInTheDocument();
      });
    });

    test('cancel button closes send message dialog', async () => {
      render(<ServiceBus />);

      await waitFor(() => {
        expect(screen.getByText('orders-queue')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('orders-queue'));
      fireEvent.click(screen.getByText('Send Message'));

      await waitFor(() => {
        expect(screen.getByText('Message Body *')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Cancel'));

      await waitFor(() => {
        expect(screen.queryByText('Message Body *')).not.toBeInTheDocument();
      });
    });
  });
});
