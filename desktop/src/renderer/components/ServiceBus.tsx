import { useState, useEffect, useCallback } from 'react';

// ============================================================================
// TYPES & INTERFACES
// ============================================================================

/**
 * Service Bus Queue
 * Represents a message queue with metadata
 */
interface Queue {
  name: string;
  messageCount: number;
  activeMessageCount: number;
  deadLetterMessageCount: number;
  maxDeliveryCount: number;
  lockDuration: string;
  defaultMessageTtl: string;
  requiresSession: boolean;
  status: 'Active' | 'Disabled' | 'Creating' | 'Deleting';
}

/**
 * Service Bus Topic
 * Represents a pub/sub topic with subscriptions
 */
interface Topic {
  name: string;
  subscriptionCount: number;
  maxSizeInMegabytes: number;
  requiresSession: boolean;
  supportOrdering: boolean;
  status: 'Active' | 'Disabled' | 'Creating' | 'Deleting';
}

/**
 * Topic Subscription
 * Represents a subscription to a topic
 */
interface Subscription {
  name: string;
  topicName: string;
  messageCount: number;
  activeMessageCount: number;
  deadLetterMessageCount: number;
  status: 'Active' | 'Disabled' | 'ReceiveDisabled';
}

/**
 * Service Bus Message
 * Comprehensive message structure matching Azure Service Bus
 */
interface Message {
  messageId: string;
  sessionId?: string;
  correlationId?: string;
  contentType?: string;
  label?: string;
  body: any;
  userProperties: Record<string, any>;
  systemProperties: {
    deliveryCount: number;
    enqueuedTimeUtc: string;
    sequenceNumber: number;
    lockedUntilUtc?: string;
    deadLetterSource?: string;
  };
  partitionKey?: string;
  replyTo?: string;
  replyToSessionId?: string;
  timeToLive?: string;
}

/**
 * Resource type discriminator for tree navigation
 */
type ResourceType = 'queue' | 'topic' | 'subscription' | 'deadletter';

/**
 * Selected resource in the tree
 */
interface SelectedResource {
  type: ResourceType;
  name: string;
  topicName?: string; // For subscriptions
}

interface ServiceBusProps {
  onRefresh?: () => void;
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Format JSON with syntax highlighting
 */
function formatJson(data: any): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

/**
 * Parse body content - try JSON first, fallback to string
 */
function parseBody(body: any): { type: 'json' | 'text'; content: any } {
  if (typeof body === 'object' && body !== null) {
    return { type: 'json', content: body };
  }
  
  if (typeof body === 'string') {
    try {
      const parsed = JSON.parse(body);
      return { type: 'json', content: parsed };
    } catch {
      return { type: 'text', content: body };
    }
  }
  
  return { type: 'text', content: String(body) };
}

/**
 * Format timestamp for display
 */
function formatTimestamp(timestamp: string): string {
  try {
    return new Date(timestamp).toLocaleString();
  } catch {
    return timestamp;
  }
}

/**
 * Validate JSON string
 */
function isValidJson(str: string): boolean {
  try {
    JSON.parse(str);
    return true;
  } catch {
    return false;
  }
}

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

/**
 * Tree Panel - Left sidebar with queues, topics, and subscriptions
 */
interface TreePanelProps {
  queues: Queue[];
  topics: Topic[];
  subscriptions: Record<string, Subscription[]>; // topicName -> subscriptions
  selectedResource: SelectedResource | null;
  onSelectResource: (resource: SelectedResource) => void;
  onRefresh: () => void;
  onCreateQueue: () => void;
  onCreateTopic: () => void;
  loading: boolean;
}

function TreePanel({
  queues,
  topics,
  subscriptions,
  selectedResource,
  onSelectResource,
  onRefresh,
  onCreateQueue,
  onCreateTopic,
  loading,
}: TreePanelProps) {
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());

  const toggleTopic = (topicName: string) => {
    setExpandedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(topicName)) {
        next.delete(topicName);
      } else {
        next.add(topicName);
      }
      return next;
    });
  };

  const isSelected = (type: ResourceType, name: string, topicName?: string): boolean => {
    if (!selectedResource) return false;
    return (
      selectedResource.type === type &&
      selectedResource.name === name &&
      selectedResource.topicName === topicName
    );
  };

  return (
    <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold text-gray-900">📮 Service Bus</h2>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="p-2 text-gray-600 hover:bg-gray-200 rounded-md transition-colors disabled:opacity-50"
            title="Refresh"
          >
            <span className={loading ? 'animate-spin' : ''}>🔄</span>
          </button>
        </div>
        <p className="text-xs text-gray-500">Queues, Topics & Messages</p>
      </div>

      {/* Tree Content */}
      <div className="flex-1 overflow-y-auto p-2">
        {/* Queues Section */}
        <div className="mb-4">
          <div className="flex items-center justify-between px-2 py-1">
            <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <span>📬</span>
              <span>Queues ({queues.length})</span>
            </h3>
            <button
              onClick={onCreateQueue}
              className="p-1 text-xs text-azure-600 hover:bg-azure-50 rounded transition-colors"
              title="Create Queue"
            >
              ➕
            </button>
          </div>
          <ul className="mt-1 space-y-1">
            {queues.map((queue) => (
              <li key={queue.name}>
                <button
                  onClick={() => onSelectResource({ type: 'queue', name: queue.name })}
                  className={`w-full text-left px-3 py-2 rounded-md flex items-center justify-between transition-colors ${
                    isSelected('queue', queue.name)
                      ? 'bg-azure-100 text-azure-900 font-medium'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-sm truncate">{queue.name}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      queue.activeMessageCount > 0
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {queue.activeMessageCount}
                  </span>
                </button>
                {/* Dead-letter sub-item */}
                {queue.deadLetterMessageCount > 0 && (
                  <button
                    onClick={() => onSelectResource({ type: 'deadletter', name: queue.name })}
                    className={`w-full text-left px-3 py-1 ml-4 mt-1 rounded-md flex items-center justify-between transition-colors text-xs ${
                      isSelected('deadletter', queue.name)
                        ? 'bg-red-100 text-red-900 font-medium'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <span className="flex items-center gap-1">
                      <span>☠️</span>
                      <span>Dead-letter</span>
                    </span>
                    <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                      {queue.deadLetterMessageCount}
                    </span>
                  </button>
                )}
              </li>
            ))}
            {queues.length === 0 && (
              <li className="px-3 py-2 text-sm text-gray-400 italic">No queues</li>
            )}
          </ul>
        </div>

        {/* Topics Section */}
        <div>
          <div className="flex items-center justify-between px-2 py-1">
            <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <span>📡</span>
              <span>Topics ({topics.length})</span>
            </h3>
            <button
              onClick={onCreateTopic}
              className="p-1 text-xs text-azure-600 hover:bg-azure-50 rounded transition-colors"
              title="Create Topic"
            >
              ➕
            </button>
          </div>
          <ul className="mt-1 space-y-1">
            {topics.map((topic) => (
              <li key={topic.name}>
                <div className="flex items-center">
                  <button
                    onClick={() => toggleTopic(topic.name)}
                    className="p-1 text-gray-600 hover:bg-gray-100 rounded"
                  >
                    <span className="text-xs">
                      {expandedTopics.has(topic.name) ? '▼' : '▶'}
                    </span>
                  </button>
                  <button
                    onClick={() => onSelectResource({ type: 'topic', name: topic.name })}
                    className={`flex-1 text-left px-2 py-2 rounded-md flex items-center justify-between transition-colors ${
                      isSelected('topic', topic.name)
                        ? 'bg-azure-100 text-azure-900 font-medium'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <span className="text-sm truncate">{topic.name}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                      {topic.subscriptionCount} subs
                    </span>
                  </button>
                </div>
                
                {/* Subscriptions */}
                {expandedTopics.has(topic.name) && (
                  <ul className="ml-6 mt-1 space-y-1">
                    {(subscriptions[topic.name] || []).map((sub) => (
                      <li key={sub.name}>
                        <button
                          onClick={() =>
                            onSelectResource({
                              type: 'subscription',
                              name: sub.name,
                              topicName: topic.name,
                            })
                          }
                          className={`w-full text-left px-3 py-1 rounded-md flex items-center justify-between transition-colors text-xs ${
                            isSelected('subscription', sub.name, topic.name)
                              ? 'bg-azure-100 text-azure-900 font-medium'
                              : 'text-gray-600 hover:bg-gray-100'
                          }`}
                        >
                          <span className="truncate">{sub.name}</span>
                          <span
                            className={`px-2 py-0.5 rounded-full ${
                              sub.activeMessageCount > 0
                                ? 'bg-green-100 text-green-700'
                                : 'bg-gray-100 text-gray-600'
                            }`}
                          >
                            {sub.activeMessageCount}
                          </span>
                        </button>
                        {/* Dead-letter for subscription */}
                        {sub.deadLetterMessageCount > 0 && (
                          <button
                            onClick={() =>
                              onSelectResource({
                                type: 'deadletter',
                                name: sub.name,
                                topicName: topic.name,
                              })
                            }
                            className={`w-full text-left px-3 py-1 ml-2 mt-1 rounded-md flex items-center justify-between transition-colors text-xs ${
                              isSelected('deadletter', sub.name, topic.name)
                                ? 'bg-red-100 text-red-900 font-medium'
                                : 'text-gray-500 hover:bg-gray-100'
                            }`}
                          >
                            <span className="flex items-center gap-1">
                              <span>☠️</span>
                              <span>Dead-letter</span>
                            </span>
                            <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                              {sub.deadLetterMessageCount}
                            </span>
                          </button>
                        )}
                      </li>
                    ))}
                    {(subscriptions[topic.name] || []).length === 0 && (
                      <li className="px-3 py-1 text-xs text-gray-400 italic">
                        No subscriptions
                      </li>
                    )}
                  </ul>
                )}
              </li>
            ))}
            {topics.length === 0 && (
              <li className="px-3 py-2 text-sm text-gray-400 italic">No topics</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}

/**
 * Message List Panel - Middle panel showing peeked messages
 */
interface MessageListPanelProps {
  messages: Message[];
  selectedMessage: Message | null;
  onSelectMessage: (message: Message) => void;
  onPeekMessages: () => void;
  onSendMessage: () => void;
  selectedResource: SelectedResource | null;
  loading: boolean;
}

function MessageListPanel({
  messages,
  selectedMessage,
  onSelectMessage,
  onPeekMessages,
  onSendMessage,
  selectedResource,
  loading,
}: MessageListPanelProps) {
  if (!selectedResource) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center text-gray-400">
          <p className="text-lg mb-2">📮</p>
          <p>Select a queue, topic, or subscription to view messages</p>
        </div>
      </div>
    );
  }

  const resourceLabel = selectedResource.topicName
    ? `${selectedResource.topicName}/${selectedResource.name}`
    : selectedResource.name;

  const resourceTypeLabel = {
    queue: 'Queue',
    topic: 'Topic',
    subscription: 'Subscription',
    deadletter: 'Dead-letter Queue',
  }[selectedResource.type];

  return (
    <div className="flex-1 flex flex-col bg-white">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{resourceLabel}</h2>
            <p className="text-xs text-gray-500">{resourceTypeLabel}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onSendMessage}
              disabled={selectedResource.type === 'topic' || selectedResource.type === 'deadletter'}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium flex items-center gap-2"
              title={selectedResource.type === 'topic' ? 'Send to subscription instead' : 'Send test message'}
            >
              <span>📤</span>
              <span>Send Message</span>
            </button>
            <button
              onClick={onPeekMessages}
              disabled={loading}
              className="px-4 py-2 bg-azure-600 text-white rounded-md hover:bg-azure-700 transition-colors disabled:opacity-50 text-sm font-medium flex items-center gap-2"
            >
              <span className={loading ? 'animate-spin' : ''}>🔄</span>
              <span>Peek Messages</span>
            </button>
          </div>
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <p className="text-lg mb-2">📭</p>
              <p>No messages to display</p>
              <p className="text-sm mt-1">Click "Peek Messages" to load messages</p>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {messages.map((message) => {
              const bodyPreview = parseBody(message.Body || message.body || '');
              const preview =
                bodyPreview.type === 'json'
                  ? JSON.stringify(bodyPreview.content).substring(0, 100)
                  : String(bodyPreview.content).substring(0, 100);

              const messageId = message.MessageId || message.messageId || '';
              const label = message.Label || message.label;
              const deliveryCount = message.DeliveryCount || message.deliveryCount || 0;
              const enqueuedTime = message.EnqueuedTimeUtc || message.enqueuedTimeUtc || new Date().toISOString();
              const correlationId = message.CorrelationId || message.correlationId;
              const deadLetterSource = message.DeadLetterSource || message.deadLetterSource;

              return (
                <li key={messageId}>
                  <button
                    onClick={() => onSelectMessage(message)}
                    className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                      selectedMessage?.MessageId === messageId || selectedMessage?.messageId === messageId
                        ? 'bg-azure-50 border-l-4 border-azure-600'
                        : ''
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {label || messageId}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          ID: {messageId.substring(0, 24)}...
                        </p>
                      </div>
                      <div className="ml-4 flex flex-col items-end gap-1">
                        <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600">
                          Delivery: {deliveryCount}
                        </span>
                        {deadLetterSource && (
                          <span className="text-xs px-2 py-1 rounded-full bg-red-100 text-red-700">
                            ☠️ Dead-letter
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-gray-600 mb-1">
                      {formatTimestamp(enqueuedTime)}
                    </p>
                    <p className="text-sm text-gray-700 truncate bg-gray-50 px-2 py-1 rounded font-mono">
                      {preview}
                      {preview.length >= 100 && '...'}
                    </p>
                    {correlationId && (
                      <p className="text-xs text-gray-500 mt-1">
                        Correlation: {correlationId}
                      </p>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

/**
 * Message Details Panel - Right panel showing full message details
 */
interface MessageDetailsPanelProps {
  message: Message | null;
  onCopyMessage: () => void;
}

function MessageDetailsPanel({ message, onCopyMessage }: MessageDetailsPanelProps) {
  if (!message) {
    return (
      <div className="w-96 bg-gray-50 border-l border-gray-200 flex items-center justify-center">
        <div className="text-center text-gray-400">
          <p className="text-lg mb-2">📄</p>
          <p>Select a message to view details</p>
        </div>
      </div>
    );
  }

  const messageId = message.MessageId || message.messageId || '';
  const body = message.Body || message.body || '';
  const label = message.Label || message.label;
  const contentType = message.ContentType || message.contentType;
  const sessionId = message.SessionId || message.sessionId;
  const correlationId = message.CorrelationId || message.correlationId;
  const replyTo = message.ReplyTo || message.replyTo;
  const timeToLive = message.TimeToLive || message.timeToLive;
  const userProperties = message.UserProperties || message.userProperties || {};
  const sequenceNumber = message.SequenceNumber || message.sequenceNumber || 0;
  const deliveryCount = message.DeliveryCount || message.deliveryCount || 0;
  const enqueuedTimeUtc = message.EnqueuedTimeUtc || message.enqueuedTimeUtc;
  const lockedUntilUtc = message.LockedUntilUtc || message.lockedUntilUtc;
  const deadLetterSource = message.DeadLetterSource || message.deadLetterSource;

  const bodyParsed = parseBody(body);

  return (
    <div className="w-96 bg-white border-l border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold text-gray-900">Message Details</h2>
          <button
            onClick={onCopyMessage}
            className="p-2 text-gray-600 hover:bg-gray-200 rounded-md transition-colors"
            title="Copy message to clipboard"
          >
            📋
          </button>
        </div>
        <p className="text-xs text-gray-500 break-all">{messageId}</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* System Properties */}
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
            <span>⚙️</span>
            <span>System Properties</span>
          </h3>
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-gray-500">Sequence Number</dt>
              <dd className="text-gray-900 font-mono">{sequenceNumber}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Delivery Count</dt>
              <dd className="text-gray-900 font-mono">{deliveryCount}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Enqueued Time</dt>
              <dd className="text-gray-900 font-mono">
                {formatTimestamp(enqueuedTimeUtc)}
              </dd>
            </div>
            {lockedUntilUtc && (
              <div>
                <dt className="text-gray-500">Locked Until</dt>
                <dd className="text-gray-900 font-mono">
                  {formatTimestamp(lockedUntilUtc)}
                </dd>
              </div>
            )}
            {deadLetterSource && (
              <div>
                <dt className="text-gray-500">Dead-letter Source</dt>
                <dd className="text-gray-900 font-mono">{deadLetterSource}</dd>
              </div>
            )}
          </dl>
        </div>

        {/* Message Properties */}
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
            <span>🏷️</span>
            <span>Message Properties</span>
          </h3>
          <dl className="space-y-2 text-sm">
            {label && (
              <div>
                <dt className="text-gray-500">Label</dt>
                <dd className="text-gray-900">{label}</dd>
              </div>
            )}
            {contentType && (
              <div>
                <dt className="text-gray-500">Content Type</dt>
                <dd className="text-gray-900 font-mono">{contentType}</dd>
              </div>
            )}
            {sessionId && (
              <div>
                <dt className="text-gray-500">Session ID</dt>
                <dd className="text-gray-900 font-mono">{sessionId}</dd>
              </div>
            )}
            {correlationId && (
              <div>
                <dt className="text-gray-500">Correlation ID</dt>
                <dd className="text-gray-900 font-mono break-all">{correlationId}</dd>
              </div>
            )}
            {replyTo && (
              <div>
                <dt className="text-gray-500">Reply To</dt>
                <dd className="text-gray-900">{replyTo}</dd>
              </div>
            )}
            {timeToLive && (
              <div>
                <dt className="text-gray-500">Time To Live</dt>
                <dd className="text-gray-900 font-mono">{timeToLive}</dd>
              </div>
            )}
          </dl>
        </div>

        {/* User Properties */}
        {Object.keys(userProperties).length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <span>👤</span>
              <span>User Properties</span>
            </h3>
            <div className="bg-gray-50 rounded-md p-3 font-mono text-xs overflow-x-auto">
              <pre className="text-gray-900 whitespace-pre-wrap break-words">
                {formatJson(userProperties)}
              </pre>
            </div>
          </div>
        )}

        {/* Message Body */}
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
            <span>📦</span>
            <span>Message Body</span>
            {bodyParsed.type === 'json' && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                JSON
              </span>
            )}
          </h3>
          <div className="bg-gray-900 rounded-md p-3 font-mono text-xs overflow-x-auto max-h-96">
            {bodyParsed.type === 'json' ? (
              <pre className="text-green-400 whitespace-pre-wrap break-words">
                {formatJson(bodyParsed.content)}
              </pre>
            ) : (
              <pre className="text-gray-300 whitespace-pre-wrap break-words">
                {bodyParsed.content}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Send Message Dialog
 */
interface SendMessageDialogProps {
  isOpen: boolean;
  selectedResource: SelectedResource | null;
  onClose: () => void;
  onSend: (messageData: {
    body: string;
    properties: Record<string, string>;
    sessionId?: string;
    correlationId?: string;
    label?: string;
    contentType?: string;
  }) => void;
}

function SendMessageDialog({
  isOpen,
  selectedResource,
  onClose,
  onSend,
}: SendMessageDialogProps) {
  const [body, setBody] = useState('{\n  "message": "Test message"\n}');
  const [label, setLabel] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [correlationId, setCorrelationId] = useState('');
  const [contentType, setContentType] = useState('application/json');
  const [properties, setProperties] = useState('{}');
  const [bodyError, setBodyError] = useState('');
  const [propertiesError, setPropertiesError] = useState('');

  const validateAndSend = () => {
    // Validate body if content type is JSON
    if (contentType === 'application/json' && !isValidJson(body)) {
      setBodyError('Invalid JSON format');
      return;
    }
    setBodyError('');

    // Validate properties
    if (!isValidJson(properties)) {
      setPropertiesError('Invalid JSON format');
      return;
    }
    setPropertiesError('');

    // Parse properties
    let parsedProperties: Record<string, string> = {};
    try {
      parsedProperties = JSON.parse(properties);
    } catch {
      setPropertiesError('Failed to parse properties');
      return;
    }

    // Send message
    onSend({
      body,
      properties: parsedProperties,
      sessionId: sessionId || undefined,
      correlationId: correlationId || undefined,
      label: label || undefined,
      contentType: contentType || undefined,
    });

    // Reset form
    setBody('{\n  "message": "Test message"\n}');
    setLabel('');
    setSessionId('');
    setCorrelationId('');
    setContentType('application/json');
    setProperties('{}');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Send Message</h2>
          <p className="text-sm text-gray-500 mt-1">
            {selectedResource?.topicName
              ? `${selectedResource.topicName}/${selectedResource.name}`
              : selectedResource?.name}
          </p>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Message Body */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Message Body *
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className={`w-full h-40 px-3 py-2 border rounded-md font-mono text-sm ${
                bodyError ? 'border-red-500' : 'border-gray-300'
              } focus:outline-none focus:ring-2 focus:ring-azure-500`}
              placeholder='{"key": "value"}'
            />
            {bodyError && <p className="text-sm text-red-600 mt-1">{bodyError}</p>}
          </div>

          {/* Content Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Content Type
            </label>
            <select
              value={contentType}
              onChange={(e) => setContentType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
            >
              <option value="application/json">application/json</option>
              <option value="text/plain">text/plain</option>
              <option value="application/xml">application/xml</option>
            </select>
          </div>

          {/* Label */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Label</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
              placeholder="Optional message label"
            />
          </div>

          {/* Session ID */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Session ID
            </label>
            <input
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
              placeholder="Optional session ID for ordered delivery"
            />
          </div>

          {/* Correlation ID */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Correlation ID
            </label>
            <input
              type="text"
              value={correlationId}
              onChange={(e) => setCorrelationId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
              placeholder="Optional correlation ID for request tracking"
            />
          </div>

          {/* User Properties */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              User Properties (JSON)
            </label>
            <textarea
              value={properties}
              onChange={(e) => setProperties(e.target.value)}
              className={`w-full h-24 px-3 py-2 border rounded-md font-mono text-sm ${
                propertiesError ? 'border-red-500' : 'border-gray-300'
              } focus:outline-none focus:ring-2 focus:ring-azure-500`}
              placeholder='{"customProperty": "value"}'
            />
            {propertiesError && (
              <p className="text-sm text-red-600 mt-1">{propertiesError}</p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={validateAndSend}
            className="px-4 py-2 text-sm font-medium text-white bg-azure-600 rounded-md hover:bg-azure-700 transition-colors"
          >
            Send Message
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

function ServiceBus({ onRefresh }: ServiceBusProps) {
  // State
  const [queues, setQueues] = useState<Queue[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [subscriptions, setSubscriptions] = useState<Record<string, Subscription[]>>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedResource, setSelectedResource] = useState<SelectedResource | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [loading, setLoading] = useState(false);
  const [sendDialogOpen, setSendDialogOpen] = useState(false);
  const [showCreateQueueModal, setShowCreateQueueModal] = useState(false);
  const [showCreateTopicModal, setShowCreateTopicModal] = useState(false);
  const [newQueueName, setNewQueueName] = useState('');
  const [newTopicName, setNewTopicName] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Fetch queues and topics
  const fetchResources = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch queues
      const queueResult = await window.localzureAPI.servicebus.listQueues();
      if (queueResult.success) {
        setQueues(queueResult.queues || []);
      } else {
        console.error('Failed to fetch queues:', queueResult.error);
      }

      // Fetch topics
      const topicResult = await window.localzureAPI.servicebus.listTopics();
      if (topicResult.success) {
        setTopics(topicResult.topics || []);
        
        // Fetch subscriptions for each topic
        const subsMap: Record<string, Subscription[]> = {};
        for (const topic of topicResult.topics || []) {
          const subResult = await window.localzureAPI.servicebus.listSubscriptions(topic.name);
          if (subResult.success) {
            subsMap[topic.name] = subResult.subscriptions || [];
          }
        }
        setSubscriptions(subsMap);
      } else {
        console.error('Failed to fetch topics:', topicResult.error);
      }
    } catch (error) {
      console.error('Failed to fetch resources:', error);
    } finally {
      setLoading(false);
      onRefresh?.();
    }
  }, [onRefresh]);

  // Fetch messages for selected resource
  const fetchMessages = useCallback(async () => {
    if (!selectedResource) return;

    setLoading(true);
    try {
      let result;
      if (selectedResource.type === 'queue') {
        result = await window.localzureAPI.servicebus.peekMessages(selectedResource.name);
      } else if (selectedResource.type === 'subscription' && selectedResource.topicName) {
        result = await window.localzureAPI.servicebus.peekSubscriptionMessages(
          selectedResource.topicName,
          selectedResource.name
        );
      } else if (selectedResource.type === 'deadletter') {
        if (selectedResource.topicName) {
          result = await window.localzureAPI.servicebus.peekDeadLetterMessages(
            selectedResource.topicName,
            selectedResource.name
          );
        } else {
          result = await window.localzureAPI.servicebus.peekQueueDeadLetterMessages(
            selectedResource.name
          );
        }
      }

      if (result?.success) {
        setMessages(result.messages || []);
      } else {
        console.error('Failed to fetch messages:', result?.error);
        setMessages([]);
      }
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      setMessages([]);
    } finally {
      setLoading(false);
    }
  }, [selectedResource]);

  // Send message
  const handleSendMessage = useCallback(
    async (messageData: {
      body: string;
      properties: Record<string, string>;
      sessionId?: string;
      correlationId?: string;
      label?: string;
      contentType?: string;
    }) => {
      if (!selectedResource) return;

      try {
        setLoading(true);
        let result;
        if (selectedResource.type === 'queue') {
          result = await window.localzureAPI.servicebus.sendMessage(
            selectedResource.name,
            messageData
          );
        } else if (selectedResource.type === 'subscription' && selectedResource.topicName) {
          result = await window.localzureAPI.servicebus.sendMessage(
            `${selectedResource.topicName}/${selectedResource.name}`,
            messageData
          );
        }

        if (result?.success) {
          // Refresh messages
          await fetchMessages();
        } else {
          console.error('Failed to send message:', result?.error);
          setError(result?.error || 'Failed to send message');
        }
      } catch (error) {
        console.error('Failed to send message:', error);
        setError(error instanceof Error ? error.message : 'Failed to send message');
      } finally {
        setLoading(false);
      }
    },
    [selectedResource, fetchMessages]
  );

  // Copy message to clipboard
  const handleCopyMessage = useCallback(() => {
    if (!selectedMessage) return;

    const messageJson = JSON.stringify(selectedMessage, null, 2);
    navigator.clipboard.writeText(messageJson).then(
      () => {
        // Success - could show a toast notification here
        console.log('Message copied to clipboard');
      },
      (err) => {
        console.error('Failed to copy message:', err);
      }
    );
  }, [selectedMessage]);

  // Create queue
  const handleCreateQueue = async () => {
    const name = newQueueName.trim();
    if (!name) {
      setError('Queue name cannot be empty');
      return;
    }

    try {
      setLoading(true);
      const result = await window.localzureAPI.servicebus.createQueue(name);
      if (result.success) {
        setShowCreateQueueModal(false);
        setNewQueueName('');
        fetchResources();
      } else {
        setError(result.error || 'Failed to create queue');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create queue');
    } finally {
      setLoading(false);
    }
  };

  // Create topic
  const handleCreateTopic = async () => {
    const name = newTopicName.trim();
    if (!name) {
      setError('Topic name cannot be empty');
      return;
    }

    try {
      setLoading(true);
      const result = await window.localzureAPI.servicebus.createTopic(name);
      if (result.success) {
        setShowCreateTopicModal(false);
        setNewTopicName('');
        fetchResources();
      } else {
        setError(result.error || 'Failed to create topic');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create topic');
    } finally {
      setLoading(false);
    }
  };

  // Load resources on mount
  useEffect(() => {
    fetchResources();
  }, [fetchResources]);

  // Fetch messages when resource changes
  useEffect(() => {
    if (selectedResource) {
      setMessages([]);
      setSelectedMessage(null);
      fetchMessages();
    }
  }, [selectedResource, fetchMessages]);

  return (
    <div className="h-screen flex bg-gray-100">
      {/* Left Panel: Tree */}
      <TreePanel
        queues={queues}
        topics={topics}
        subscriptions={subscriptions}
        selectedResource={selectedResource}
        onSelectResource={setSelectedResource}
        onRefresh={fetchResources}
        onCreateQueue={() => setShowCreateQueueModal(true)}
        onCreateTopic={() => setShowCreateTopicModal(true)}
        loading={loading}
      />

      {/* Middle Panel: Message List */}
      <MessageListPanel
        messages={messages}
        selectedMessage={selectedMessage}
        onSelectMessage={setSelectedMessage}
        onPeekMessages={fetchMessages}
        onSendMessage={() => setSendDialogOpen(true)}
        selectedResource={selectedResource}
        loading={loading}
      />

      {/* Right Panel: Message Details */}
      <MessageDetailsPanel message={selectedMessage} onCopyMessage={handleCopyMessage} />

      {/* Send Message Dialog */}
      <SendMessageDialog
        isOpen={sendDialogOpen}
        selectedResource={selectedResource}
        onClose={() => setSendDialogOpen(false)}
        onSend={handleSendMessage}
      />

      {/* Create Queue Modal */}
      {showCreateQueueModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4 text-gray-900">Create New Queue</h3>
            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-800">
                {error}
              </div>
            )}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Queue Name
              </label>
              <input
                type="text"
                value={newQueueName}
                onChange={(e) => setNewQueueName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleCreateQueue();
                  } else if (e.key === 'Escape') {
                    setShowCreateQueueModal(false);
                    setNewQueueName('');
                    setError(null);
                  }
                }}
                placeholder="myqueue"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
                autoFocus
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowCreateQueueModal(false);
                  setNewQueueName('');
                  setError(null);
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={handleCreateQueue}
                className="px-4 py-2 text-sm font-medium text-white bg-azure-600 rounded-md hover:bg-azure-700 transition-colors disabled:opacity-50"
                disabled={loading || !newQueueName.trim()}
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Topic Modal */}
      {showCreateTopicModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4 text-gray-900">Create New Topic</h3>
            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-800">
                {error}
              </div>
            )}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Topic Name
              </label>
              <input
                type="text"
                value={newTopicName}
                onChange={(e) => setNewTopicName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleCreateTopic();
                  } else if (e.key === 'Escape') {
                    setShowCreateTopicModal(false);
                    setNewTopicName('');
                    setError(null);
                  }
                }}
                placeholder="mytopic"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
                autoFocus
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowCreateTopicModal(false);
                  setNewTopicName('');
                  setError(null);
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={handleCreateTopic}
                className="px-4 py-2 text-sm font-medium text-white bg-azure-600 rounded-md hover:bg-azure-700 transition-colors disabled:opacity-50"
                disabled={loading || !newTopicName.trim()}
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ServiceBus;
