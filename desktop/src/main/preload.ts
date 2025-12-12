/**
 * Preload script for LocalZure Desktop
 * 
 * Exposes safe IPC methods to the renderer process through contextBridge.
 */

import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';

// Define types for API
export interface BlobAPI {
  listContainers: () => Promise<{ success: boolean; containers: any[]; error?: string }>;
  listBlobs: (containerName: string, prefix?: string) => Promise<{ success: boolean; blobs: any[]; error?: string }>;
  createContainer: (containerName: string) => Promise<{ success: boolean; error?: string }>;
  deleteContainer: (containerName: string) => Promise<{ success: boolean; error?: string }>;
  uploadBlob: (containerName: string, blobName: string, data: string, contentType: string) => Promise<{ success: boolean; error?: string }>;
  downloadBlob: (containerName: string, blobName: string) => Promise<{ success: boolean; data?: string; error?: string }>;
  deleteBlob: (containerName: string, blobName: string) => Promise<{ success: boolean; error?: string }>;
}

export interface ServiceBusAPI {
  listQueues: () => Promise<{ success: boolean; queues: any[]; error?: string }>;
  listTopics: () => Promise<{ success: boolean; topics: any[]; error?: string }>;
  createQueue: (queueName: string) => Promise<{ success: boolean; error?: string }>;
  createTopic: (topicName: string) => Promise<{ success: boolean; error?: string }>;
  listSubscriptions: (topicName: string) => Promise<{ success: boolean; subscriptions: any[]; error?: string }>;
  peekMessages: (queueName: string, maxMessages?: number) => Promise<{ success: boolean; messages: any[]; error?: string }>;
  peekSubscriptionMessages: (topicName: string, subscriptionName: string, maxMessages?: number) => Promise<{ success: boolean; messages: any[]; error?: string }>;
  peekQueueDeadLetterMessages: (queueName: string, maxMessages?: number) => Promise<{ success: boolean; messages: any[]; error?: string }>;
  peekDeadLetterMessages: (topicName: string, subscriptionName: string, maxMessages?: number) => Promise<{ success: boolean; messages: any[]; error?: string }>;
  sendMessage: (destination: string, messageData: any) => Promise<{ success: boolean; messageId?: string; error?: string }>;
}

export interface KeyVaultAPI {
  listSecrets: () => Promise<any>;
  getSecret: (name: string) => Promise<any>;
  createSecret: (name: string, value: string, contentType?: string) => Promise<any>;
  deleteSecret: (name: string) => Promise<any>;
}

export interface QueueStorageAPI {
  listQueues: () => Promise<any>;
  createQueue: (queueName: string) => Promise<any>;
  deleteQueue: (queueName: string) => Promise<any>;
  peekQueueMessages: (queueName: string, numMessages?: number) => Promise<any>;
  sendQueueMessage: (queueName: string, content: string) => Promise<any>;
  deleteQueueMessage: (queueName: string, messageId: string, popReceipt: string) => Promise<any>;
}

export interface TableStorageAPI {
  listTables: () => Promise<any>;
  createTable: (tableName: string) => Promise<any>;
  deleteTable: (tableName: string) => Promise<any>;
  queryTableEntities: (tableName: string) => Promise<any>;
  insertTableEntity: (tableName: string, entity: any) => Promise<any>;
  deleteTableEntity: (tableName: string, partitionKey: string, rowKey: string) => Promise<any>;
}

export interface CosmosDBAPI {
  listCosmosDatabases: () => Promise<any>;
  createCosmosDatabase: (id: string) => Promise<any>;
  deleteCosmosDatabase: (databaseId: string) => Promise<any>;
  listCosmosContainers: (databaseId: string) => Promise<any>;
  createCosmosContainer: (databaseId: string, containerId: string, partitionKey: string) => Promise<any>;
  deleteCosmosContainer: (databaseId: string, containerId: string) => Promise<any>;
  queryCosmosDocuments: (databaseId: string, containerId: string) => Promise<any>;
  createCosmosDocument: (databaseId: string, containerId: string, document: any) => Promise<any>;
  deleteCosmosDocument: (databaseId: string, containerId: string, documentId: string) => Promise<any>;
}

export interface LocalZureAPI {
  start: () => Promise<{ success: boolean; error?: string }>;
  stop: () => Promise<{ success: boolean; error?: string }>;
  restart: () => Promise<{ success: boolean; error?: string }>;
  getStatus: () => Promise<any>;
  getConfig: () => Promise<any>;
  updateConfig: (config: any) => Promise<{ success: boolean; error?: string }>;
  onStatusChanged: (callback: (status: string) => void) => () => void;
  onLog: (callback: (log: any) => void) => () => void;
  blob: BlobAPI;
  servicebus: ServiceBusAPI;
  listSecrets: () => Promise<any>;
  getSecret: (name: string) => Promise<any>;
  createSecret: (name: string, value: string, contentType?: string) => Promise<any>;
  deleteSecret: (name: string) => Promise<any>;
  listQueues: () => Promise<any>;
  createQueue: (queueName: string) => Promise<any>;
  deleteQueue: (queueName: string) => Promise<any>;
  peekQueueMessages: (queueName: string, numMessages?: number) => Promise<any>;
  sendQueueMessage: (queueName: string, content: string) => Promise<any>;
  deleteQueueMessage: (queueName: string, messageId: string, popReceipt: string) => Promise<any>;
  listTables: () => Promise<any>;
  createTable: (tableName: string) => Promise<any>;
  deleteTable: (tableName: string) => Promise<any>;
  queryTableEntities: (tableName: string) => Promise<any>;
  insertTableEntity: (tableName: string, entity: any) => Promise<any>;
  deleteTableEntity: (tableName: string, partitionKey: string, rowKey: string) => Promise<any>;
  listCosmosDatabases: () => Promise<any>;
  createCosmosDatabase: (id: string) => Promise<any>;
  deleteCosmosDatabase: (databaseId: string) => Promise<any>;
  listCosmosContainers: (databaseId: string) => Promise<any>;
  createCosmosContainer: (databaseId: string, containerId: string, partitionKey: string) => Promise<any>;
  deleteCosmosContainer: (databaseId: string, containerId: string) => Promise<any>;
  queryCosmosDocuments: (databaseId: string, containerId: string) => Promise<any>;
  createCosmosDocument: (databaseId: string, containerId: string, document: any) => Promise<any>;
  deleteCosmosDocument: (databaseId: string, containerId: string, documentId: string) => Promise<any>;
}

// Expose protected methods via contextBridge
contextBridge.exposeInMainWorld('localzureAPI', {
  // LocalZure control
  start: () => ipcRenderer.invoke('localzure:start'),
  stop: () => ipcRenderer.invoke('localzure:stop'),
  restart: () => ipcRenderer.invoke('localzure:restart'),
  getStatus: () => ipcRenderer.invoke('localzure:get-status'),
  getConfig: () => ipcRenderer.invoke('localzure:get-config'),
  updateConfig: (config: any) => ipcRenderer.invoke('localzure:update-config', config),

  // Event listeners
  onStatusChanged: (callback: (status: string) => void) => {
    const subscription = (_event: IpcRendererEvent, status: string) => callback(status);
    ipcRenderer.on('localzure:status-changed', subscription);
    
    // Return unsubscribe function
    return () => {
      ipcRenderer.removeListener('localzure:status-changed', subscription);
    };
  },

  onLog: (callback: (log: any) => void) => {
    const subscription = (_event: IpcRendererEvent, log: any) => callback(log);
    ipcRenderer.on('localzure:log', subscription);
    
    // Return unsubscribe function
    return () => {
      ipcRenderer.removeListener('localzure:log', subscription);
    };
  },

  // Blob Storage API
  blob: {
    listContainers: () => ipcRenderer.invoke('blob:list-containers'),
    listBlobs: (containerName: string, prefix?: string) => ipcRenderer.invoke('blob:list-blobs', containerName, prefix),
    createContainer: (containerName: string) => ipcRenderer.invoke('blob:create-container', containerName),
    deleteContainer: (containerName: string) => ipcRenderer.invoke('blob:delete-container', containerName),
    uploadBlob: (containerName: string, blobName: string, data: string, contentType: string) => 
      ipcRenderer.invoke('blob:upload-blob', containerName, blobName, data, contentType),
    downloadBlob: (containerName: string, blobName: string) => ipcRenderer.invoke('blob:download-blob', containerName, blobName),
    deleteBlob: (containerName: string, blobName: string) => ipcRenderer.invoke('blob:delete-blob', containerName, blobName),
  },

  // Service Bus API
  servicebus: {
    listQueues: () => ipcRenderer.invoke('servicebus:list-queues'),
    listTopics: () => ipcRenderer.invoke('servicebus:list-topics'),
    createQueue: (queueName: string) => ipcRenderer.invoke('servicebus:create-queue', queueName),
    createTopic: (topicName: string) => ipcRenderer.invoke('servicebus:create-topic', topicName),
    listSubscriptions: (topicName: string) => ipcRenderer.invoke('servicebus:list-subscriptions', topicName),
    peekMessages: (queueName: string, maxMessages?: number) => ipcRenderer.invoke('servicebus:peek-messages', queueName, maxMessages),
    peekSubscriptionMessages: (topicName: string, subscriptionName: string, maxMessages?: number) => 
      ipcRenderer.invoke('servicebus:peek-subscription-messages', topicName, subscriptionName, maxMessages),
    peekQueueDeadLetterMessages: (queueName: string, maxMessages?: number) => 
      ipcRenderer.invoke('servicebus:peek-queue-deadletter', queueName, maxMessages),
    peekDeadLetterMessages: (topicName: string, subscriptionName: string, maxMessages?: number) => 
      ipcRenderer.invoke('servicebus:peek-deadletter', topicName, subscriptionName, maxMessages),
    sendMessage: (destination: string, messageData: any) => 
      ipcRenderer.invoke('servicebus:send-message', destination, messageData),
  },

  // Key Vault API
  listSecrets: () => ipcRenderer.invoke('listSecrets'),
  getSecret: (name: string) => ipcRenderer.invoke('getSecret', name),
  createSecret: (name: string, value: string, contentType?: string) => 
    ipcRenderer.invoke('createSecret', name, value, contentType),
  deleteSecret: (name: string) => ipcRenderer.invoke('deleteSecret', name),

  // Queue Storage API
  listQueues: () => ipcRenderer.invoke('listQueues'),
  createQueue: (queueName: string) => ipcRenderer.invoke('createQueue', queueName),
  deleteQueue: (queueName: string) => ipcRenderer.invoke('deleteQueue', queueName),
  peekQueueMessages: (queueName: string, numMessages?: number) => 
    ipcRenderer.invoke('peekQueueMessages', queueName, numMessages),
  sendQueueMessage: (queueName: string, content: string) => 
    ipcRenderer.invoke('sendQueueMessage', queueName, content),
  deleteQueueMessage: (queueName: string, messageId: string, popReceipt: string) => 
    ipcRenderer.invoke('deleteQueueMessage', queueName, messageId, popReceipt),

  // Table Storage API
  listTables: () => ipcRenderer.invoke('listTables'),
  createTable: (tableName: string) => ipcRenderer.invoke('createTable', tableName),
  deleteTable: (tableName: string) => ipcRenderer.invoke('deleteTable', tableName),
  queryTableEntities: (tableName: string) => ipcRenderer.invoke('queryTableEntities', tableName),
  insertTableEntity: (tableName: string, entity: any) => 
    ipcRenderer.invoke('insertTableEntity', tableName, entity),
  deleteTableEntity: (tableName: string, partitionKey: string, rowKey: string) => 
    ipcRenderer.invoke('deleteTableEntity', tableName, partitionKey, rowKey),

  // Cosmos DB API
  listCosmosDatabases: () => ipcRenderer.invoke('listCosmosDatabases'),
  createCosmosDatabase: (id: string) => ipcRenderer.invoke('createCosmosDatabase', id),
  deleteCosmosDatabase: (databaseId: string) => ipcRenderer.invoke('deleteCosmosDatabase', databaseId),
  listCosmosContainers: (databaseId: string) => ipcRenderer.invoke('listCosmosContainers', databaseId),
  createCosmosContainer: (databaseId: string, containerId: string, partitionKey: string) => 
    ipcRenderer.invoke('createCosmosContainer', databaseId, containerId, partitionKey),
  deleteCosmosContainer: (databaseId: string, containerId: string) => 
    ipcRenderer.invoke('deleteCosmosContainer', databaseId, containerId),
  queryCosmosDocuments: (databaseId: string, containerId: string) => 
    ipcRenderer.invoke('queryCosmosDocuments', databaseId, containerId),
  createCosmosDocument: (databaseId: string, containerId: string, document: any) => 
    ipcRenderer.invoke('createCosmosDocument', databaseId, containerId, document),
    deleteCosmosDocument: (databaseId: string, containerId: string, documentId: string, partitionKeyValue?: string) => 
      ipcRenderer.invoke('deleteCosmosDocument', databaseId, containerId, documentId, partitionKeyValue),
} as LocalZureAPI);

// Type declaration for TypeScript
declare global {
  interface Window {
    localzureAPI: LocalZureAPI;
  }
}
