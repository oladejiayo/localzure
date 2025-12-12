import { useState, useEffect, useCallback } from 'react';

interface Entity {
  PartitionKey: string;
  RowKey: string;
  Timestamp?: string;
  [key: string]: any;
}

interface Table {
  name: string;
}

interface TableStorageProps {
  onRefresh?: () => void;
}

function TableStorage({ onRefresh }: TableStorageProps) {
  const [tables, setTables] = useState<Table[]>([]);
  const [selectedTable, setSelectedTable] = useState<Table | null>(null);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [showCreateTableModal, setShowCreateTableModal] = useState(false);
  const [showCreateEntityModal, setShowCreateEntityModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [newTableName, setNewTableName] = useState('');
  const [newEntityPartitionKey, setNewEntityPartitionKey] = useState('');
  const [newEntityRowKey, setNewEntityRowKey] = useState('');
  const [newEntityData, setNewEntityData] = useState('{}');

  const fetchTables = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await window.localzureAPI.listTables();
      // Map Azure Table Storage response format: {value: [{TableName: "..."}]} to {name: "..."}
      const tableList = (result.value || []).map((t: any) => ({ name: t.TableName }));
      setTables(tableList);
    } catch (err: any) {
      setError(err.message || 'Failed to load tables');
      console.error('Failed to fetch tables:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchEntities = useCallback(async (tableName: string) => {
    try {
      setLoading(true);
      setError(null);
      const result = await window.localzureAPI.queryTableEntities(tableName);
      // Azure Table Storage returns {value: [...]} format
      setEntities(result.value || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load entities');
      console.error('Failed to fetch entities:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTables();
  }, [fetchTables]);

  useEffect(() => {
    if (selectedTable) {
      fetchEntities(selectedTable.name);
    }
  }, [selectedTable, fetchEntities]);

  const handleCreateTable = async () => {
    if (!newTableName) {
      setError('Table name is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.createTable(newTableName);
      setShowCreateTableModal(false);
      setNewTableName('');
      await fetchTables();
    } catch (err: any) {
      setError(err.message || 'Failed to create table');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTable = async (name: string) => {
    if (!confirm(`Are you sure you want to delete table "${name}"?`)) return;

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.deleteTable(name);
      if (selectedTable?.name === name) {
        setSelectedTable(null);
        setEntities([]);
      }
      await fetchTables();
    } catch (err: any) {
      setError(err.message || 'Failed to delete table');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateEntity = async () => {
    if (!selectedTable || !newEntityPartitionKey || !newEntityRowKey) {
      setError('Partition key and row key are required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = JSON.parse(newEntityData);
      const entity = {
        PartitionKey: newEntityPartitionKey,
        RowKey: newEntityRowKey,
        ...data
      };
      await window.localzureAPI.insertTableEntity(selectedTable.name, entity);
      setShowCreateEntityModal(false);
      setNewEntityPartitionKey('');
      setNewEntityRowKey('');
      setNewEntityData('{}');
      await fetchEntities(selectedTable.name);
    } catch (err: any) {
      setError(err.message || 'Failed to create entity');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteEntity = async (partitionKey: string, rowKey: string) => {
    if (!selectedTable) return;
    if (!confirm('Are you sure you want to delete this entity?')) return;

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.deleteTableEntity(selectedTable.name, partitionKey, rowKey);
      await fetchEntities(selectedTable.name);
      if (selectedEntity?.PartitionKey === partitionKey && selectedEntity?.RowKey === rowKey) {
        setSelectedEntity(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete entity');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 via-indigo-50 to-purple-50">
      {/* Header */}
      <div className="backdrop-blur-xl bg-white/80 border-b border-white/20 shadow-lg">
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg text-white">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-slate-800">Table Storage</h1>
                <p className="text-slate-600">Manage tables and entities</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={fetchTables}
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
                onClick={() => setShowCreateTableModal(true)}
                className="px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
              >
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  New Table
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

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Tables List */}
        <div className="w-1/4 border-r border-white/20 bg-white/60 backdrop-blur-xl overflow-y-auto">
          <div className="p-4">
            <h3 className="text-lg font-bold text-slate-800 mb-4">Tables ({tables.length})</h3>
            {loading && tables.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <svg className="w-12 h-12 mx-auto animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p className="mt-4">Loading tables...</p>
              </div>
            ) : tables.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <svg className="w-16 h-16 mx-auto text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                <p className="mt-4 font-medium">No tables yet</p>
                <p className="text-sm">Create your first table</p>
              </div>
            ) : (
              <div className="space-y-2">
                {tables.map((table) => (
                  <div key={table.name} className="relative">
                    <button
                      onClick={() => setSelectedTable(table)}
                      className={`w-full text-left p-4 rounded-xl transition-all duration-200 ${
                        selectedTable?.name === table.name
                          ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-lg'
                          : 'bg-white/80 hover:bg-white text-slate-800 hover:shadow-md'
                      }`}
                    >
                      <p className="font-semibold truncate">{table.name}</p>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteTable(table.name);
                      }}
                      className="absolute top-3 right-3 p-1 hover:bg-white/20 rounded"
                      title="Delete table"
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

        {/* Entities List */}
        <div className="w-1/3 border-r border-white/20 bg-white/40 backdrop-blur-xl overflow-y-auto">
          {selectedTable ? (
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-slate-800">Entities ({entities.length})</h3>
                <button
                  onClick={() => setShowCreateEntityModal(true)}
                  className="px-3 py-1 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 text-sm"
                >
                  <span className="flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    New
                  </span>
                </button>
              </div>
              {entities.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <svg className="w-12 h-12 mx-auto text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="mt-4">No entities</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {entities.map((entity, index) => (
                    <button
                      key={`${entity.PartitionKey}-${entity.RowKey}-${index}`}
                      onClick={() => setSelectedEntity(entity)}
                      className={`w-full text-left p-3 rounded-lg transition-all duration-200 ${
                        selectedEntity === entity
                          ? 'bg-indigo-500 text-white shadow-lg'
                          : 'bg-white/80 hover:bg-white text-slate-800 hover:shadow-md'
                      }`}
                    >
                      <p className="text-xs font-semibold mb-1">PK: {entity.PartitionKey}</p>
                      <p className="text-xs truncate">RK: {entity.RowKey}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <p>Select a table</p>
            </div>
          )}
        </div>

        {/* Entity Details */}
        <div className="flex-1 overflow-y-auto p-6">
          {selectedEntity ? (
            <div className="max-w-2xl">
              <div className="backdrop-blur-xl bg-white/80 border border-white/20 rounded-2xl shadow-xl p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold text-slate-800">Entity Details</h2>
                  <button
                    onClick={() => handleDeleteEntity(selectedEntity.PartitionKey, selectedEntity.RowKey)}
                    className="px-3 py-2 bg-red-500 text-white rounded-lg font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 text-sm"
                  >
                    Delete
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">Partition Key</label>
                    <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200 font-mono">
                      {selectedEntity.PartitionKey}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">Row Key</label>
                    <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200 font-mono">
                      {selectedEntity.RowKey}
                    </div>
                  </div>

                  {selectedEntity.Timestamp && (
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-2">Timestamp</label>
                      <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200">
                        {new Date(selectedEntity.Timestamp).toLocaleString()}
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">All Properties (JSON)</label>
                    <pre className="bg-slate-100 rounded-lg p-4 text-xs border border-slate-200 overflow-x-auto">
                      {JSON.stringify(selectedEntity, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <div className="text-center">
                <svg className="w-24 h-24 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-lg font-medium">Select an entity to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create Table Modal */}
      {showCreateTableModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-2xl font-bold text-slate-800 mb-6">Create New Table</h3>
            
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Table Name *</label>
              <input
                type="text"
                value={newTableName}
                onChange={(e) => setNewTableName(e.target.value)}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="mytable"
              />
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateTableModal(false);
                  setNewTableName('');
                  setError(null);
                }}
                className="flex-1 px-4 py-2 bg-slate-200 text-slate-800 rounded-lg font-medium hover:bg-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateTable}
                disabled={loading || !newTableName}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:hover:scale-100"
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Entity Modal */}
      {showCreateEntityModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-2xl font-bold text-slate-800 mb-6">Create New Entity</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Partition Key *</label>
                <input
                  type="text"
                  value={newEntityPartitionKey}
                  onChange={(e) => setNewEntityPartitionKey(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="partition1"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Row Key *</label>
                <input
                  type="text"
                  value={newEntityRowKey}
                  onChange={(e) => setNewEntityRowKey(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="row1"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Additional Data (JSON)</label>
                <textarea
                  value={newEntityData}
                  onChange={(e) => setNewEntityData(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent font-mono text-sm"
                  rows={6}
                  placeholder='{"field1": "value1", "field2": 123}'
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateEntityModal(false);
                  setNewEntityPartitionKey('');
                  setNewEntityRowKey('');
                  setNewEntityData('{}');
                  setError(null);
                }}
                className="flex-1 px-4 py-2 bg-slate-200 text-slate-800 rounded-lg font-medium hover:bg-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateEntity}
                disabled={loading || !newEntityPartitionKey || !newEntityRowKey}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:hover:scale-100"
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

export default TableStorage;
