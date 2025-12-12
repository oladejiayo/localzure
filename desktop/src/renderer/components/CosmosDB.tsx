import { useState, useEffect, useCallback } from 'react';

interface Document {
  id: string;
  [key: string]: any;
}

interface Container {
  id: string;
  partitionKey?: string;
}

interface Database {
  id: string;
}

interface CosmosDBProps {
  onRefresh?: () => void;
}

function CosmosDB({ onRefresh }: CosmosDBProps) {
  const [databases, setDatabases] = useState<Database[]>([]);
  const [selectedDatabase, setSelectedDatabase] = useState<Database | null>(null);
  const [containers, setContainers] = useState<Container[]>([]);
  const [selectedContainer, setSelectedContainer] = useState<Container | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  
  const [showCreateDatabaseModal, setShowCreateDatabaseModal] = useState(false);
  const [showCreateContainerModal, setShowCreateContainerModal] = useState(false);
  const [showCreateDocumentModal, setShowCreateDocumentModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [newDatabaseId, setNewDatabaseId] = useState('');
  const [newContainerId, setNewContainerId] = useState('');
  const [newContainerPartitionKey, setNewContainerPartitionKey] = useState('/id');
  const [newDocumentData, setNewDocumentData] = useState('{\n  "id": "",\n  \n}');

  const fetchDatabases = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await window.localzureAPI.listCosmosDatabases();
      // API returns {Databases: [{id: string, ...}]}
      setDatabases(result.Databases || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load databases');
      console.error('Failed to fetch databases:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchContainers = useCallback(async (databaseId: string) => {
    try {
      setLoading(true);
      setError(null);
      const result = await window.localzureAPI.listCosmosContainers(databaseId);
      // API returns {DocumentCollections: [{id: string, partitionKey: {paths: [string]}}]}
      // Map to expected format with partitionKey as string
      const containerList = (result.DocumentCollections || []).map((c: any) => ({
        id: c.id,
        partitionKey: c.partitionKey?.paths?.[0] || '/id'
      }));
      setContainers(containerList);
    } catch (err: any) {
      setError(err.message || 'Failed to load containers');
      console.error('Failed to fetch containers:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDocuments = useCallback(async (databaseId: string, containerId: string) => {
    try {
      setLoading(true);
      setError(null);
      const result = await window.localzureAPI.queryCosmosDocuments(databaseId, containerId);
      // API returns {Documents: [{id: string, ...}]}
      setDocuments(result.Documents || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load documents');
      console.error('Failed to fetch documents:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDatabases();
  }, [fetchDatabases]);

  useEffect(() => {
    if (selectedDatabase) {
      fetchContainers(selectedDatabase.id);
      setSelectedContainer(null);
      setDocuments([]);
      setSelectedDocument(null);
    }
  }, [selectedDatabase, fetchContainers]);

  useEffect(() => {
    if (selectedDatabase && selectedContainer) {
      fetchDocuments(selectedDatabase.id, selectedContainer.id);
      setSelectedDocument(null);
    }
  }, [selectedDatabase, selectedContainer, fetchDocuments]);

  const handleCreateDatabase = async () => {
    if (!newDatabaseId) {
      setError('Database ID is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.createCosmosDatabase(newDatabaseId);
      setShowCreateDatabaseModal(false);
      setNewDatabaseId('');
      await fetchDatabases();
    } catch (err: any) {
      setError(err.message || 'Failed to create database');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDatabase = async (id: string) => {
    if (!confirm(`Are you sure you want to delete database "${id}"?`)) return;

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.deleteCosmosDatabase(id);
      if (selectedDatabase?.id === id) {
        setSelectedDatabase(null);
        setContainers([]);
        setDocuments([]);
      }
      await fetchDatabases();
    } catch (err: any) {
      setError(err.message || 'Failed to delete database');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateContainer = async () => {
    if (!selectedDatabase || !newContainerId || !newContainerPartitionKey) {
      setError('Container ID and partition key are required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.createCosmosContainer(selectedDatabase.id, newContainerId, newContainerPartitionKey);
      setShowCreateContainerModal(false);
      setNewContainerId('');
      setNewContainerPartitionKey('/id');
      await fetchContainers(selectedDatabase.id);
    } catch (err: any) {
      setError(err.message || 'Failed to create container');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteContainer = async (id: string) => {
    if (!selectedDatabase) return;
    if (!confirm(`Are you sure you want to delete container "${id}"?`)) return;

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.deleteCosmosContainer(selectedDatabase.id, id);
      if (selectedContainer?.id === id) {
        setSelectedContainer(null);
        setDocuments([]);
      }
      await fetchContainers(selectedDatabase.id);
    } catch (err: any) {
      setError(err.message || 'Failed to delete container');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDocument = async () => {
    if (!selectedDatabase || !selectedContainer) {
      setError('Select a database and container first');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const doc = JSON.parse(newDocumentData);
      if (!doc.id || doc.id.trim() === '') {
        setError('Document must have a non-empty "id" field');
        setLoading(false);
        return;
      }
      await window.localzureAPI.createCosmosDocument(selectedDatabase.id, selectedContainer.id, doc);
      setShowCreateDocumentModal(false);
      setNewDocumentData('{\n  "id": "",\n  \n}');
      await fetchDocuments(selectedDatabase.id, selectedContainer.id);
    } catch (err: any) {
      setError(err.message || 'Failed to create document');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDocument = async (id: string) => {
    if (!selectedDatabase || !selectedContainer) return;
    if (!confirm(`Are you sure you want to delete document "${id}"?`)) return;

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.deleteCosmosDocument(selectedDatabase.id, selectedContainer.id, id);
      await fetchDocuments(selectedDatabase.id, selectedContainer.id);
      if (selectedDocument?.id === id) {
        setSelectedDocument(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete document');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 via-violet-50 to-fuchsia-50">
      {/* Header */}
      <div className="backdrop-blur-xl bg-white/80 border-b border-white/20 shadow-lg">
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 shadow-lg text-white">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-slate-800">Cosmos DB</h1>
                <p className="text-slate-600">Globally distributed multi-model database</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={fetchDatabases}
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
                onClick={() => setShowCreateDatabaseModal(true)}
                className="px-4 py-2 bg-gradient-to-r from-violet-500 to-fuchsia-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
              >
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  New Database
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

      {/* Main Content - 4 Columns: Databases | Containers | Documents | Document Details */}
      <div className="flex-1 flex overflow-hidden">
        {/* Column 1: Databases */}
        <div className="w-1/5 border-r border-white/20 bg-white/60 backdrop-blur-xl overflow-y-auto">
          <div className="p-4">
            <h3 className="text-lg font-bold text-slate-800 mb-4">Databases ({databases.length})</h3>
            {loading && databases.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <svg className="w-12 h-12 mx-auto animate-spin text-violet-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p className="mt-4">Loading...</p>
              </div>
            ) : databases.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <svg className="w-16 h-16 mx-auto text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                </svg>
                <p className="mt-4 font-medium">No databases</p>
                <p className="text-sm">Create one to start</p>
              </div>
            ) : (
              <div className="space-y-2">
                {databases.map((db) => (
                  <div key={db.id} className="relative">
                    <button
                      onClick={() => setSelectedDatabase(db)}
                      className={`w-full text-left p-4 rounded-xl transition-all duration-200 ${
                        selectedDatabase?.id === db.id
                          ? 'bg-gradient-to-r from-violet-500 to-fuchsia-600 text-white shadow-lg'
                          : 'bg-white/80 hover:bg-white text-slate-800 hover:shadow-md'
                      }`}
                    >
                      <p className="font-semibold truncate">{db.id}</p>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteDatabase(db.id);
                      }}
                      className="absolute top-3 right-3 p-1 hover:bg-white/20 rounded"
                      title="Delete database"
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

        {/* Column 2: Containers */}
        <div className="w-1/5 border-r border-white/20 bg-white/50 backdrop-blur-xl overflow-y-auto">
          {selectedDatabase ? (
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-slate-800">Containers ({containers.length})</h3>
                <button
                  onClick={() => setShowCreateContainerModal(true)}
                  className="px-2 py-1 bg-gradient-to-r from-violet-500 to-fuchsia-600 text-white rounded-lg font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 text-xs"
                >
                  <span className="flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    New
                  </span>
                </button>
              </div>
              {containers.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <svg className="w-12 h-12 mx-auto text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                  <p className="mt-4">No containers</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {containers.map((container) => (
                    <div key={container.id} className="relative">
                      <button
                        onClick={() => setSelectedContainer(container)}
                        className={`w-full text-left p-3 rounded-lg transition-all duration-200 ${
                          selectedContainer?.id === container.id
                            ? 'bg-violet-500 text-white shadow-lg'
                            : 'bg-white/80 hover:bg-white text-slate-800 hover:shadow-md'
                        }`}
                      >
                        <p className="font-semibold text-sm truncate">{container.id}</p>
                        {container.partitionKey && (
                          <p className={`text-xs mt-1 truncate ${selectedContainer?.id === container.id ? 'text-violet-100' : 'text-slate-500'}`}>
                            PK: {container.partitionKey}
                          </p>
                        )}
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteContainer(container.id);
                        }}
                        className="absolute top-2 right-2 p-1 hover:bg-white/20 rounded"
                        title="Delete container"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <p className="text-sm">Select a database</p>
            </div>
          )}
        </div>

        {/* Column 3: Documents */}
        <div className="w-1/5 border-r border-white/20 bg-white/40 backdrop-blur-xl overflow-y-auto">
          {selectedContainer ? (
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-slate-800">Documents ({documents.length})</h3>
                <button
                  onClick={() => setShowCreateDocumentModal(true)}
                  className="px-2 py-1 bg-gradient-to-r from-violet-500 to-fuchsia-600 text-white rounded-lg font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 text-xs"
                >
                  <span className="flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    New
                  </span>
                </button>
              </div>
              {documents.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <svg className="w-12 h-12 mx-auto text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="mt-4">No documents</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {documents.map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => setSelectedDocument(doc)}
                      className={`w-full text-left p-3 rounded-lg transition-all duration-200 ${
                        selectedDocument?.id === doc.id
                          ? 'bg-violet-500 text-white shadow-lg'
                          : 'bg-white/80 hover:bg-white text-slate-800 hover:shadow-md'
                      }`}
                    >
                      <p className="text-sm font-semibold truncate">{doc.id}</p>
                      <p className={`text-xs mt-1 ${selectedDocument?.id === doc.id ? 'text-violet-100' : 'text-slate-500'}`}>
                        {Object.keys(doc).length} fields
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <p className="text-sm">Select a container</p>
            </div>
          )}
        </div>

        {/* Column 4: Document Details */}
        <div className="flex-1 overflow-y-auto p-6">
          {selectedDocument ? (
            <div className="max-w-3xl">
              <div className="backdrop-blur-xl bg-white/80 border border-white/20 rounded-2xl shadow-xl p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold text-slate-800">Document: {selectedDocument.id}</h2>
                  <button
                    onClick={() => handleDeleteDocument(selectedDocument.id)}
                    className="px-3 py-2 bg-red-500 text-white rounded-lg font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 text-sm"
                  >
                    Delete
                  </button>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">JSON Document</label>
                  <pre className="bg-slate-100 rounded-lg p-4 text-xs border border-slate-200 overflow-x-auto max-h-[600px] overflow-y-auto">
                    {JSON.stringify(selectedDocument, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <div className="text-center">
                <svg className="w-24 h-24 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-lg font-medium">Select a document to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create Database Modal */}
      {showCreateDatabaseModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-2xl font-bold text-slate-800 mb-6">Create New Database</h3>
            
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Database ID *</label>
              <input
                type="text"
                value={newDatabaseId}
                onChange={(e) => setNewDatabaseId(e.target.value)}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                placeholder="my-database"
              />
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateDatabaseModal(false);
                  setNewDatabaseId('');
                  setError(null);
                }}
                className="flex-1 px-4 py-2 bg-slate-200 text-slate-800 rounded-lg font-medium hover:bg-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateDatabase}
                disabled={loading || !newDatabaseId}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-violet-500 to-fuchsia-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:hover:scale-100"
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Container Modal */}
      {showCreateContainerModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-2xl font-bold text-slate-800 mb-6">Create New Container</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Container ID *</label>
                <input
                  type="text"
                  value={newContainerId}
                  onChange={(e) => setNewContainerId(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  placeholder="my-container"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Partition Key *</label>
                <input
                  type="text"
                  value={newContainerPartitionKey}
                  onChange={(e) => setNewContainerPartitionKey(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  placeholder="/id"
                />
                <p className="text-xs text-slate-500 mt-1">e.g., /id, /category, /userId</p>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateContainerModal(false);
                  setNewContainerId('');
                  setNewContainerPartitionKey('/id');
                  setError(null);
                }}
                className="flex-1 px-4 py-2 bg-slate-200 text-slate-800 rounded-lg font-medium hover:bg-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateContainer}
                disabled={loading || !newContainerId || !newContainerPartitionKey}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-violet-500 to-fuchsia-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:hover:scale-100"
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Document Modal */}
      {showCreateDocumentModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6">
            <h3 className="text-2xl font-bold text-slate-800 mb-6">Create New Document</h3>
            
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Document Data (JSON) *</label>
              <textarea
                value={newDocumentData}
                onChange={(e) => setNewDocumentData(e.target.value)}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent font-mono text-sm"
                rows={12}
                placeholder='{\n  "id": "doc1",\n  "name": "Example"\n}'
              />
              <p className="text-xs text-slate-500 mt-1">Document must include an "id" field</p>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateDocumentModal(false);
                  setNewDocumentData('{\n  "id": "",\n  \n}');
                  setError(null);
                }}
                className="flex-1 px-4 py-2 bg-slate-200 text-slate-800 rounded-lg font-medium hover:bg-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateDocument}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-violet-500 to-fuchsia-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:hover:scale-100"
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

export default CosmosDB;
