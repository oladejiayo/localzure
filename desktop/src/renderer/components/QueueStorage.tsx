import { useState, useEffect, useCallback } from 'react';

interface QueueMessage {
  id: string;
  content: string;
  insertionTime?: string;
  expirationTime?: string;
  dequeueCount?: number;
  popReceipt?: string;
}

interface Queue {
  name: string;
  approximateMessageCount?: number;
  metadata?: Record<string, string>;
}

interface QueueStorageProps {
  onRefresh?: () => void;
}

function QueueStorage({ onRefresh }: QueueStorageProps) {
  const [queues, setQueues] = useState<Queue[]>([]);
  const [selectedQueue, setSelectedQueue] = useState<Queue | null>(null);
  const [messages, setMessages] = useState<QueueMessage[]>([]);
  const [selectedMessage, setSelectedMessage] = useState<QueueMessage | null>(null);
  const [showCreateQueueModal, setShowCreateQueueModal] = useState(false);
  const [showSendMessageModal, setShowSendMessageModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [newQueueName, setNewQueueName] = useState('');
  const [newMessageContent, setNewMessageContent] = useState('');

  const fetchQueues = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await window.localzureAPI.listQueues();
      // IPC handler now returns {queues: [{name: string}]}
      setQueues(result.queues || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load queues');
      console.error('Failed to fetch queues:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMessages = useCallback(async (queueName: string) => {
    try {
      setLoading(true);
      setError(null);
      const result = await window.localzureAPI.peekQueueMessages(queueName, 10);
      setMessages(result.messages || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load messages');
      console.error('Failed to fetch messages:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueues();
  }, [fetchQueues]);

  useEffect(() => {
    if (selectedQueue) {
      fetchMessages(selectedQueue.name);
    }
  }, [selectedQueue, fetchMessages]);

  const handleCreateQueue = async () => {
    if (!newQueueName) {
      setError('Queue name is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.createQueue(newQueueName);
      setShowCreateQueueModal(false);
      setNewQueueName('');
      await fetchQueues();
    } catch (err: any) {
      setError(err.message || 'Failed to create queue');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteQueue = async (name: string) => {
    if (!confirm(`Are you sure you want to delete queue "${name}"?`)) return;

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.deleteQueue(name);
      if (selectedQueue?.name === name) {
        setSelectedQueue(null);
        setMessages([]);
      }
      await fetchQueues();
    } catch (err: any) {
      setError(err.message || 'Failed to delete queue');
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!selectedQueue || !newMessageContent) {
      setError('Message content is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.sendQueueMessage(selectedQueue.name, newMessageContent);
      setShowSendMessageModal(false);
      setNewMessageContent('');
      await fetchMessages(selectedQueue.name);
    } catch (err: any) {
      setError(err.message || 'Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteMessage = async (messageId: string, popReceipt: string) => {
    if (!selectedQueue) return;
    if (!confirm('Are you sure you want to delete this message?')) return;

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.deleteQueueMessage(selectedQueue.name, messageId, popReceipt);
      await fetchMessages(selectedQueue.name);
      if (selectedMessage?.id === messageId) {
        setSelectedMessage(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete message');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 via-orange-50 to-red-50">
      {/* Header */}
      <div className="backdrop-blur-xl bg-white/80 border-b border-white/20 shadow-lg">
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 shadow-lg text-white">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-slate-800">Queue Storage</h1>
                <p className="text-slate-600">Manage queues and messages</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={fetchQueues}
                disabled={loading}
                className="px-4 py-2 bg-white text-slate-700 rounded-lg font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 disabled:opacity-50"
              >
                <span className="flex items-center gap-2">
                  <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Refresh
                </span>
              </button>
              <button
                onClick={() => setShowCreateQueueModal(true)}
                className="px-4 py-2 bg-gradient-to-r from-orange-500 to-red-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
              >
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  New Queue
                </span>
              </button>
            </div>
          </div>

          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 flex items-start gap-3">
              <svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div className="flex-1">
                <p className="font-semibold">Error</p>
                <p className="text-sm">{error}</p>
              </div>
              <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Content - 3 Columns: Queues | Messages | Message Details */}
      <div className="flex-1 flex overflow-hidden">
        {/* Column 1: Queues List */}
        <div className="w-1/4 border-r border-white/20 bg-white/60 backdrop-blur-xl overflow-y-auto">
          <div className="p-4">
            <h3 className="text-lg font-bold text-slate-800 mb-4">Queues ({queues.length})</h3>
            {loading && queues.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <svg className="w-12 h-12 mx-auto animate-spin text-orange-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p className="mt-4">Loading queues...</p>
              </div>
            ) : queues.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <svg className="w-16 h-16 mx-auto text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <p className="mt-4 font-medium">No queues yet</p>
                <p className="text-sm">Create your first queue</p>
              </div>
            ) : (
              <div className="space-y-2">
                {queues.map((queue) => (
                  <div key={queue.name} className="relative">
                    <button
                      onClick={() => setSelectedQueue(queue)}
                      className={`w-full text-left p-4 rounded-xl transition-all duration-200 ${
                        selectedQueue?.name === queue.name
                          ? 'bg-gradient-to-r from-orange-500 to-red-600 text-white shadow-lg'
                          : 'bg-white/80 hover:bg-white text-slate-800 hover:shadow-md'
                      }`}
                    >
                      <p className="font-semibold truncate">{queue.name}</p>
                      {queue.approximateMessageCount !== undefined && (
                        <p className={`text-xs mt-1 ${selectedQueue?.name === queue.name ? 'text-orange-100' : 'text-slate-500'}`}>
                          {queue.approximateMessageCount} messages
                        </p>
                      )}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteQueue(queue.name);
                      }}
                      className="absolute top-3 right-3 p-1 hover:bg-white/20 rounded"
                      title="Delete queue"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Column 2: Messages List */}
        <div className="w-1/3 border-r border-white/20 bg-white/40 backdrop-blur-xl overflow-y-auto">
          {selectedQueue ? (
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-slate-800">Messages ({messages.length})</h3>
                <button
                  onClick={() => setShowSendMessageModal(true)}
                  className="px-3 py-1 bg-gradient-to-r from-orange-500 to-red-600 text-white rounded-lg font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 text-sm"
                >
                  <span className="flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Send
                  </span>
                </button>
              </div>
              {messages.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <svg className="w-12 h-12 mx-auto text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                  </svg>
                  <p className="mt-4">No messages</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {messages.map((message) => (
                    <button
                      key={message.id}
                      onClick={() => setSelectedMessage(message)}
                      className={`w-full text-left p-3 rounded-lg transition-all duration-200 ${
                        selectedMessage?.id === message.id
                          ? 'bg-orange-500 text-white shadow-lg'
                          : 'bg-white/80 hover:bg-white text-slate-800 hover:shadow-md'
                      }`}
                    >
                      <p className="text-xs font-mono mb-1">{message.id}</p>
                      <p className="text-sm truncate">{message.content}</p>
                      {message.dequeueCount !== undefined && (
                        <p className={`text-xs mt-1 ${selectedMessage?.id === message.id ? 'text-orange-100' : 'text-slate-500'}`}>
                          Dequeue count: {message.dequeueCount}
                        </p>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <p>Select a queue</p>
            </div>
          )}
        </div>

        {/* Column 3: Message Details */}
        <div className="flex-1 overflow-y-auto p-6">
          {selectedMessage ? (
            <div className="max-w-2xl">
              <div className="backdrop-blur-xl bg-white/80 border border-white/20 rounded-2xl shadow-xl p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold text-slate-800">Message Details</h2>
                  {selectedMessage.popReceipt && (
                    <button
                      onClick={() => handleDeleteMessage(selectedMessage.id, selectedMessage.popReceipt!)}
                      className="px-3 py-2 bg-red-500 text-white rounded-lg font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 text-sm"
                    >
                      Delete
                    </button>
                  )}
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">Message ID</label>
                    <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200 font-mono break-all">
                      {selectedMessage.id}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">Content</label>
                    <div className="bg-slate-100 rounded-lg p-4 text-sm border border-slate-200 whitespace-pre-wrap break-words">
                      {selectedMessage.content}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    {selectedMessage.insertionTime && (
                      <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-2">Inserted</label>
                        <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200">
                          {new Date(selectedMessage.insertionTime).toLocaleString()}
                        </div>
                      </div>
                    )}
                    {selectedMessage.expirationTime && (
                      <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-2">Expires</label>
                        <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200">
                          {new Date(selectedMessage.expirationTime).toLocaleString()}
                        </div>
                      </div>
                    )}
                    {selectedMessage.dequeueCount !== undefined && (
                      <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-2">Dequeue Count</label>
                        <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200">
                          {selectedMessage.dequeueCount}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <div className="text-center">
                <svg className="w-24 h-24 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                </svg>
                <p className="text-lg font-medium">Select a message to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create Queue Modal */}
      {showCreateQueueModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-2xl font-bold text-slate-800 mb-6">Create New Queue</h3>
            
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Queue Name *</label>
              <input
                type="text"
                value={newQueueName}
                onChange={(e) => setNewQueueName(e.target.value)}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                placeholder="my-queue"
              />
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateQueueModal(false);
                  setNewQueueName('');
                  setError(null);
                }}
                className="flex-1 px-4 py-2 bg-slate-200 text-slate-800 rounded-lg font-medium hover:bg-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateQueue}
                disabled={loading || !newQueueName}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-orange-500 to-red-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:hover:scale-100"
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Send Message Modal */}
      {showSendMessageModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-2xl font-bold text-slate-800 mb-6">Send Message</h3>
            
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Message Content *</label>
              <textarea
                value={newMessageContent}
                onChange={(e) => setNewMessageContent(e.target.value)}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                rows={6}
                placeholder="Enter message content..."
              />
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowSendMessageModal(false);
                  setNewMessageContent('');
                  setError(null);
                }}
                className="flex-1 px-4 py-2 bg-slate-200 text-slate-800 rounded-lg font-medium hover:bg-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSendMessage}
                disabled={loading || !newMessageContent}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-orange-500 to-red-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:hover:scale-100"
              >
                {loading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default QueueStorage;
