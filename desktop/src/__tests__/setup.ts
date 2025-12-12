import '@testing-library/jest-dom';

// Mock window.localzureAPI
const mockAPI = {
  start: jest.fn(() => Promise.resolve({ success: true })),
  stop: jest.fn(() => Promise.resolve({ success: true })),
  restart: jest.fn(() => Promise.resolve({ success: true })),
  getStatus: jest.fn(() =>
    Promise.resolve({
      status: 'stopped',
      services: [],
      version: '0.1.0',
    })
  ),
  getConfig: jest.fn(() =>
    Promise.resolve({
      port: 7071,
      host: '127.0.0.1',
      logLevel: 'INFO',
      autoStart: false,
    })
  ),
  updateConfig: jest.fn(() => Promise.resolve({ success: true })),
  onStatusChanged: jest.fn(() => jest.fn()),
  onLog: jest.fn(() => jest.fn()),
  blob: {
    listContainers: jest.fn(() => Promise.resolve({ success: true, containers: [] })),
    listBlobs: jest.fn(() => Promise.resolve({ success: true, blobs: [] })),
    createContainer: jest.fn(() => Promise.resolve({ success: true })),
    deleteContainer: jest.fn(() => Promise.resolve({ success: true })),
    uploadBlob: jest.fn(() => Promise.resolve({ success: true })),
    downloadBlob: jest.fn(() => Promise.resolve({ success: true, data: '' })),
    deleteBlob: jest.fn(() => Promise.resolve({ success: true })),
  },
  servicebus: {
    listQueues: jest.fn(() => Promise.resolve({ success: true, queues: [] })),
    listTopics: jest.fn(() => Promise.resolve({ success: true, topics: [] })),
    listSubscriptions: jest.fn(() => Promise.resolve({ success: true, subscriptions: [] })),
    peekMessages: jest.fn(() => Promise.resolve({ success: true, messages: [] })),
    peekSubscriptionMessages: jest.fn(() => Promise.resolve({ success: true, messages: [] })),
    peekQueueDeadLetterMessages: jest.fn(() => Promise.resolve({ success: true, messages: [] })),
    peekDeadLetterMessages: jest.fn(() => Promise.resolve({ success: true, messages: [] })),
    sendMessage: jest.fn(() => Promise.resolve({ success: true, messageId: 'test-id' })),
  },
};

Object.defineProperty(window, 'localzureAPI', {
  writable: true,
  value: mockAPI,
});

// Reset mocks before each test
beforeEach(() => {
  jest.clearAllMocks();
});
