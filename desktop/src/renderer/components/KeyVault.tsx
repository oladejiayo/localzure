import { useState, useEffect, useCallback } from 'react';

interface Secret {
  name: string;
  value?: string;
  contentType?: string;
  attributes?: {
    enabled: boolean;
    created: number;
    updated: number;
    exp?: number;
    nbf?: number;
  };
  tags?: Record<string, string>;
}

interface KeyVaultProps {
  onRefresh?: () => void;
}

function KeyVault({ onRefresh }: KeyVaultProps) {
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [selectedSecret, setSelectedSecret] = useState<Secret | null>(null);
  const [showValue, setShowValue] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [newSecretName, setNewSecretName] = useState('');
  const [newSecretValue, setNewSecretValue] = useState('');
  const [newSecretContentType, setNewSecretContentType] = useState('');

  const fetchSecrets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await window.localzureAPI.listSecrets();
      // API returns {value: [{id: string, attributes: {...}}]}
      const secretList = (result.value || []).map((s: any) => ({
        name: s.id?.split('/').pop() || s.id,
        ...s
      }));
      setSecrets(secretList);
    } catch (err: any) {
      setError(err.message || 'Failed to load secrets');
      console.error('Failed to fetch secrets:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSecrets();
  }, [fetchSecrets]);

  const handleCreateSecret = async () => {
    if (!newSecretName || !newSecretValue) {
      setError('Secret name and value are required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.createSecret(newSecretName, newSecretValue, newSecretContentType || undefined);
      setShowCreateModal(false);
      setNewSecretName('');
      setNewSecretValue('');
      setNewSecretContentType('');
      await fetchSecrets();
    } catch (err: any) {
      setError(err.message || 'Failed to create secret');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSecret = async (name: string) => {
    if (!confirm(`Are you sure you want to delete secret "${name}"?`)) return;

    try {
      setLoading(true);
      setError(null);
      await window.localzureAPI.deleteSecret(name);
      if (selectedSecret?.name === name) {
        setSelectedSecret(null);
      }
      await fetchSecrets();
    } catch (err: any) {
      setError(err.message || 'Failed to delete secret');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSecret = async (secret: Secret) => {
    try {
      setLoading(true);
      setError(null);
      const result = await window.localzureAPI.getSecret(secret.name);
      setSelectedSecret(result);
      setShowValue(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load secret details');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 via-purple-50 to-pink-50">
      {/* Header */}
      <div className="backdrop-blur-xl bg-white/80 border-b border-white/20 shadow-lg">
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 shadow-lg text-white">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-slate-800">Key Vault</h1>
                <p className="text-slate-600">Manage secrets, keys, and certificates</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={fetchSecrets}
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
                onClick={() => setShowCreateModal(true)}
                className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
              >
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  New Secret
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
        {/* Secrets List */}
        <div className="w-1/3 border-r border-white/20 bg-white/60 backdrop-blur-xl overflow-y-auto">
          <div className="p-4">
            <h3 className="text-lg font-bold text-slate-800 mb-4">Secrets ({secrets.length})</h3>
            {loading && secrets.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <svg className="w-12 h-12 mx-auto animate-spin text-purple-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p className="mt-4">Loading secrets...</p>
              </div>
            ) : secrets.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <svg className="w-16 h-16 mx-auto text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
                <p className="mt-4 font-medium">No secrets yet</p>
                <p className="text-sm">Create your first secret to get started</p>
              </div>
            ) : (
              <div className="space-y-2">
                {secrets.map((secret) => (
                  <button
                    key={secret.name}
                    onClick={() => handleSelectSecret(secret)}
                    className={`w-full text-left p-4 rounded-xl transition-all duration-200 ${
                      selectedSecret?.name === secret.name
                        ? 'bg-gradient-to-r from-purple-500 to-pink-600 text-white shadow-lg'
                        : 'bg-white/80 hover:bg-white text-slate-800 hover:shadow-md'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold truncate">{secret.name}</p>
                        {secret.contentType && (
                          <p className={`text-xs mt-1 truncate ${selectedSecret?.name === secret.name ? 'text-purple-100' : 'text-slate-500'}`}>
                            {secret.contentType}
                          </p>
                        )}
                      </div>
                      <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Secret Details */}
        <div className="flex-1 overflow-y-auto p-6">
          {selectedSecret ? (
            <div className="max-w-3xl">
              <div className="backdrop-blur-xl bg-white/80 border border-white/20 rounded-2xl shadow-xl p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-2xl font-bold text-slate-800">{selectedSecret.name}</h2>
                  <button
                    onClick={() => handleDeleteSecret(selectedSecret.name)}
                    className="px-4 py-2 bg-red-500 text-white rounded-lg font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200"
                  >
                    <span className="flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                      Delete
                    </span>
                  </button>
                </div>

                {/* Secret Value */}
                <div className="mb-6">
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Secret Value</label>
                  <div className="relative">
                    <div className="bg-slate-100 rounded-lg p-4 font-mono text-sm border border-slate-200 break-all">
                      {showValue ? selectedSecret.value : '••••••••••••••••••••'}
                    </div>
                    <button
                      onClick={() => setShowValue(!showValue)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-800"
                    >
                      {showValue ? (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                {/* Metadata */}
                <div className="grid grid-cols-2 gap-4 mb-6">
                  {selectedSecret.contentType && (
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-2">Content Type</label>
                      <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200">
                        {selectedSecret.contentType}
                      </div>
                    </div>
                  )}
                  {selectedSecret.attributes && (
                    <>
                      <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-2">Status</label>
                        <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200">
                          <span className={`inline-flex items-center gap-2 ${selectedSecret.attributes.enabled ? 'text-green-700' : 'text-red-700'}`}>
                            <span className={`w-2 h-2 rounded-full ${selectedSecret.attributes.enabled ? 'bg-green-500' : 'bg-red-500'}`}></span>
                            {selectedSecret.attributes.enabled ? 'Enabled' : 'Disabled'}
                          </span>
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-2">Created</label>
                        <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200">
                          {new Date(selectedSecret.attributes.created * 1000).toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-2">Updated</label>
                        <div className="bg-slate-100 rounded-lg p-3 text-sm border border-slate-200">
                          {new Date(selectedSecret.attributes.updated * 1000).toLocaleString()}
                        </div>
                      </div>
                    </>
                  )}
                </div>

                {/* Tags */}
                {selectedSecret.tags && Object.keys(selectedSecret.tags).length > 0 && (
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">Tags</label>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(selectedSecret.tags).map(([key, value]) => (
                        <span key={key} className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm font-medium">
                          {key}: {value}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <div className="text-center">
                <svg className="w-24 h-24 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
                <p className="text-lg font-medium">Select a secret to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create Secret Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-2xl font-bold text-slate-800 mb-6">Create New Secret</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Secret Name *</label>
                <input
                  type="text"
                  value={newSecretName}
                  onChange={(e) => setNewSecretName(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  placeholder="my-secret"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Secret Value *</label>
                <textarea
                  value={newSecretValue}
                  onChange={(e) => setNewSecretValue(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-sm"
                  rows={4}
                  placeholder="Enter secret value..."
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Content Type (optional)</label>
                <input
                  type="text"
                  value={newSecretContentType}
                  onChange={(e) => setNewSecretContentType(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  placeholder="text/plain"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setNewSecretName('');
                  setNewSecretValue('');
                  setNewSecretContentType('');
                  setError(null);
                }}
                className="flex-1 px-4 py-2 bg-slate-200 text-slate-800 rounded-lg font-medium hover:bg-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateSecret}
                disabled={loading || !newSecretName || !newSecretValue}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-600 text-white rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:hover:scale-100"
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

export default KeyVault;
