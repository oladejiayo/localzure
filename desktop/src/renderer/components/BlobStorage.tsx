import { useState, useEffect, useCallback } from 'react';

// Types
interface Container {
  name: string;
  properties: {
    lastModified: string;
    etag: string;
    leaseStatus: string;
    leaseState: string;
    publicAccess?: string;
  };
  metadata?: Record<string, string>;
}

interface BlobItem {
  name: string;
  properties: {
    contentLength: number;
    contentType: string;
    lastModified: string;
    etag: string;
    leaseStatus?: string;
    leaseState?: string;
    blobType: 'BlockBlob' | 'AppendBlob' | 'PageBlob';
  };
  metadata?: Record<string, string>;
  snapshot?: string;
}

interface BlobStorageProps {
  onRefresh?: () => void;
}

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

interface ProgressDialogProps {
  isOpen: boolean;
  title: string;
  progress: number;
  fileName?: string;
}

// Confirmation Dialog Component
function ConfirmDialog({ isOpen, title, message, onConfirm, onCancel }: ConfirmDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold mb-4 text-gray-900">{title}</h3>
        <p className="text-gray-600 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// Progress Dialog Component
function ProgressDialog({ isOpen, title, progress, fileName }: ProgressDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold mb-4 text-gray-900">{title}</h3>
        {fileName && <p className="text-sm text-gray-600 mb-4 truncate">{fileName}</p>}
        <div className="w-full bg-gray-200 rounded-full h-2.5">
          <div
            className="bg-azure-600 h-2.5 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
        <p className="text-sm text-gray-500 mt-2 text-right">{progress}%</p>
      </div>
    </div>
  );
}

function BlobStorage({ onRefresh }: BlobStorageProps) {
  // State
  const [containers, setContainers] = useState<Container[]>([]);
  const [selectedContainer, setSelectedContainer] = useState<Container | null>(null);
  const [blobs, setBlobs] = useState<BlobItem[]>([]);
  const [selectedBlob, setSelectedBlob] = useState<BlobItem | null>(null);
  const [selectedBlobs, setSelectedBlobs] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(0);
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  });
  const [progressDialog, setProgressDialog] = useState<{
    isOpen: boolean;
    title: string;
    progress: number;
    fileName?: string;
  }>({
    isOpen: false,
    title: '',
    progress: 0,
  });
  const [showCreateContainerModal, setShowCreateContainerModal] = useState(false);
  const [newContainerName, setNewContainerName] = useState('');

  const ITEMS_PER_PAGE = 50;

  // Load containers on mount
  useEffect(() => {
    loadContainers();
  }, []);

  const loadContainers = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await window.localzureAPI.blob.listContainers();
      if (result.success) {
        setContainers(result.containers || []);
      } else {
        setError(result.error || 'Failed to load containers');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load containers');
    } finally {
      setLoading(false);
    }
  };

  const loadBlobs = async (containerName: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await window.localzureAPI.blob.listBlobs(containerName, searchFilter);
      if (result.success) {
        setBlobs(result.blobs || []);
        setCurrentPage(0);
      } else {
        setError(result.error || 'Failed to load blobs');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load blobs');
    } finally {
      setLoading(false);
    }
  };

  const handleContainerClick = (container: Container) => {
    setSelectedContainer(container);
    setSelectedBlob(null);
    setSelectedBlobs(new Set());
    setSearchFilter('');
    loadBlobs(container.name);
  };

  const handleBlobClick = (blob: BlobItem) => {
    setSelectedBlob(blob);
  };

  const handleBlobSelection = (blobName: string, isSelected: boolean) => {
    const newSelection = new Set(selectedBlobs);
    if (isSelected) {
      newSelection.add(blobName);
    } else {
      newSelection.delete(blobName);
    }
    setSelectedBlobs(newSelection);
  };

  const handleSelectAllBlobs = (isSelected: boolean) => {
    if (isSelected) {
      const allBlobNames = paginatedBlobs.map((blob) => blob.name);
      setSelectedBlobs(new Set(allBlobNames));
    } else {
      setSelectedBlobs(new Set());
    }
  };

  const handleUpload = async () => {
    if (!selectedContainer) return;

    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;

    input.onchange = async (e) => {
      const files = (e.target as HTMLInputElement).files;
      if (!files || files.length === 0) return;

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setProgressDialog({
          isOpen: true,
          title: 'Uploading...',
          progress: 0,
          fileName: file.name,
        });

        try {
          // Read file as base64
          const reader = new FileReader();
          reader.onload = async (event) => {
            const base64Data = (event.target?.result as string).split(',')[1];

            // Simulate progress
            for (let progress = 0; progress <= 90; progress += 10) {
              setProgressDialog((prev) => ({ ...prev, progress }));
              await new Promise((resolve) => setTimeout(resolve, 100));
            }

            const result = await window.localzureAPI.blob.uploadBlob(
              selectedContainer.name,
              file.name,
              base64Data,
              file.type
            );

            setProgressDialog((prev) => ({ ...prev, progress: 100 }));
            await new Promise((resolve) => setTimeout(resolve, 300));

            if (result.success) {
              loadBlobs(selectedContainer.name);
            } else {
              setError(result.error || 'Upload failed');
            }
          };
          reader.readAsDataURL(file);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Upload failed');
        } finally {
          setProgressDialog({ isOpen: false, title: '', progress: 0 });
        }
      }
    };

    input.click();
  };

  const handleDownload = async (blob: BlobItem) => {
    if (!selectedContainer) return;

    setProgressDialog({
      isOpen: true,
      title: 'Downloading...',
      progress: 0,
      fileName: blob.name,
    });

    try {
      // Simulate progress
      for (let progress = 0; progress <= 90; progress += 10) {
        setProgressDialog((prev) => ({ ...prev, progress }));
        await new Promise((resolve) => setTimeout(resolve, 100));
      }

      const result = await window.localzureAPI.blob.downloadBlob(
        selectedContainer.name,
        blob.name
      );

      setProgressDialog((prev) => ({ ...prev, progress: 100 }));
      await new Promise((resolve) => setTimeout(resolve, 300));

      if (result.success && result.data) {
        // Create download link
        const base64Data = result.data;
        const binaryData = atob(base64Data);
        const arrayBuffer = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
          arrayBuffer[i] = binaryData.charCodeAt(i);
        }
        const blobData = new Blob([arrayBuffer], { type: blob.properties.contentType });
        const url = URL.createObjectURL(blobData);
        const a = document.createElement('a');
        a.href = url;
        a.download = blob.name;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        setError(result.error || 'Download failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setProgressDialog({ isOpen: false, title: '', progress: 0 });
    }
  };

  const handleDeleteBlob = (blob: BlobItem) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Blob',
      message: `Are you sure you want to delete "${blob.name}"? This action cannot be undone.`,
      onConfirm: async () => {
        setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} });
        if (!selectedContainer) return;

        try {
          const result = await window.localzureAPI.blob.deleteBlob(
            selectedContainer.name,
            blob.name
          );
          if (result.success) {
            loadBlobs(selectedContainer.name);
            if (selectedBlob?.name === blob.name) {
              setSelectedBlob(null);
            }
          } else {
            setError(result.error || 'Delete failed');
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Delete failed');
        }
      },
    });
  };

  const handleDeleteSelectedBlobs = () => {
    if (selectedBlobs.size === 0) return;

    setConfirmDialog({
      isOpen: true,
      title: 'Delete Multiple Blobs',
      message: `Are you sure you want to delete ${selectedBlobs.size} blob(s)? This action cannot be undone.`,
      onConfirm: async () => {
        setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} });
        if (!selectedContainer) return;

        for (const blobName of selectedBlobs) {
          try {
            await window.localzureAPI.blob.deleteBlob(selectedContainer.name, blobName);
          } catch (err) {
            console.error(`Failed to delete ${blobName}:`, err);
          }
        }

        setSelectedBlobs(new Set());
        loadBlobs(selectedContainer.name);
      },
    });
  };

  const handleDeleteContainer = (container: Container) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Container',
      message: `Are you sure you want to delete container "${container.name}"? All blobs in this container will be deleted. This action cannot be undone.`,
      onConfirm: async () => {
        setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} });

        try {
          const result = await window.localzureAPI.blob.deleteContainer(container.name);
          if (result.success) {
            loadContainers();
            if (selectedContainer?.name === container.name) {
              setSelectedContainer(null);
              setBlobs([]);
              setSelectedBlob(null);
            }
          } else {
            setError(result.error || 'Delete failed');
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Delete failed');
        }
      },
    });
  };

  const handleCreateContainer = async () => {
    const name = newContainerName.trim();
    if (!name) {
      setError('Container name cannot be empty');
      return;
    }

    // Validate container name
    if (!/^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$/.test(name)) {
      setError(
        'Invalid container name. Must be 3-63 characters, lowercase letters, numbers, and hyphens only.'
      );
      return;
    }

    try {
      setLoading(true);
      const result = await window.localzureAPI.blob.createContainer(name);
      if (result.success) {
        setShowCreateContainerModal(false);
        setNewContainerName('');
        loadContainers();
      } else {
        setError(result.error || 'Failed to create container');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create container');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    loadContainers();
    if (selectedContainer) {
      loadBlobs(selectedContainer.name);
    }
    onRefresh?.();
  };

  const handleSearchChange = (value: string) => {
    setSearchFilter(value);
    setCurrentPage(0);
  };

  const handleSearchSubmit = () => {
    if (selectedContainer) {
      loadBlobs(selectedContainer.name);
    }
  };

  // Format file size
  const formatSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  // Format date
  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch {
      return dateString;
    }
  };

  // Filter and paginate blobs
  const filteredBlobs = blobs.filter((blob) =>
    blob.name.toLowerCase().includes(searchFilter.toLowerCase())
  );
  const totalPages = Math.ceil(filteredBlobs.length / ITEMS_PER_PAGE);
  const paginatedBlobs = filteredBlobs.slice(
    currentPage * ITEMS_PER_PAGE,
    (currentPage + 1) * ITEMS_PER_PAGE
  );

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Blob Storage Explorer</h1>
            <p className="text-sm text-gray-500 mt-1">
              Browse and manage containers and blobs
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleRefresh}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors flex items-center gap-2"
              disabled={loading}
            >
              <span>🔄</span>
              Refresh
            </button>
            <button
              onClick={() => setShowCreateContainerModal(true)}
              className="px-4 py-2 text-sm font-medium text-white bg-azure-600 rounded-md hover:bg-azure-700 transition-colors flex items-center gap-2"
            >
              <span>➕</span>
              New Container
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md flex items-start gap-2">
            <span className="text-red-600">⚠️</span>
            <div className="flex-1">
              <p className="text-sm text-red-800">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-800"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Main Content - 3 Panel Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Containers */}
        <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Containers</h2>
            <p className="text-xs text-gray-500 mt-1">{containers.length} total</p>
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading && containers.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                <div className="animate-spin inline-block w-6 h-6 border-2 border-gray-300 border-t-azure-600 rounded-full"></div>
                <p className="mt-2 text-sm">Loading containers...</p>
              </div>
            ) : containers.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                <p className="text-sm">No containers found</p>
                <p className="text-xs mt-2">Create a new container to get started</p>
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {containers.map((container) => (
                  <li
                    key={container.name}
                    className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
                      selectedContainer?.name === container.name ? 'bg-azure-50' : ''
                    }`}
                    onClick={() => handleContainerClick(container)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-lg">📦</span>
                          <h3 className="text-sm font-medium text-gray-900 truncate">
                            {container.name}
                          </h3>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          {container.properties.leaseState}
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteContainer(container);
                        }}
                        className="text-red-600 hover:text-red-800 text-xs ml-2"
                        title="Delete container"
                      >
                        🗑️
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Right Panel - Blobs and Properties */}
        <div className="flex-1 flex flex-col">
          {/* Blob List */}
          <div className="flex-1 bg-white overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-gray-900">
                  {selectedContainer ? `Blobs in "${selectedContainer.name}"` : 'Select a container'}
                </h2>
                {selectedContainer && (
                  <div className="flex gap-2">
                    {selectedBlobs.size > 0 && (
                      <button
                        onClick={handleDeleteSelectedBlobs}
                        className="px-3 py-1.5 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 transition-colors flex items-center gap-1"
                      >
                        <span>🗑️</span>
                        Delete ({selectedBlobs.size})
                      </button>
                    )}
                    <button
                      onClick={handleUpload}
                      className="px-3 py-1.5 text-sm font-medium text-white bg-azure-600 rounded-md hover:bg-azure-700 transition-colors flex items-center gap-1"
                    >
                      <span>⬆️</span>
                      Upload
                    </button>
                  </div>
                )}
              </div>

              {selectedContainer && (
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Filter by name prefix..."
                    value={searchFilter}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearchSubmit()}
                    className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                  <button
                    onClick={handleSearchSubmit}
                    className="px-4 py-2 text-sm font-medium text-white bg-gray-700 rounded-md hover:bg-gray-800 transition-colors"
                  >
                    Search
                  </button>
                </div>
              )}
            </div>

            {selectedContainer ? (
              <div className="flex-1 overflow-auto">
                {loading && blobs.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">
                    <div className="animate-spin inline-block w-6 h-6 border-2 border-gray-300 border-t-azure-600 rounded-full"></div>
                    <p className="mt-2 text-sm">Loading blobs...</p>
                  </div>
                ) : filteredBlobs.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">
                    <p className="text-sm">
                      {searchFilter ? 'No blobs match your filter' : 'No blobs in this container'}
                    </p>
                    <p className="text-xs mt-2">Upload files to add blobs</p>
                  </div>
                ) : (
                  <>
                    <table className="w-full">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="px-6 py-3 text-left">
                            <input
                              type="checkbox"
                              checked={
                                paginatedBlobs.length > 0 &&
                                paginatedBlobs.every((blob) => selectedBlobs.has(blob.name))
                              }
                              onChange={(e) => handleSelectAllBlobs(e.target.checked)}
                              className="rounded border-gray-300 text-azure-600 focus:ring-azure-500"
                            />
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Name
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Type
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Size
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Last Modified
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {paginatedBlobs.map((blob) => (
                          <tr
                            key={blob.name}
                            className={`hover:bg-gray-50 cursor-pointer ${
                              selectedBlob?.name === blob.name ? 'bg-azure-50' : ''
                            }`}
                            onClick={() => handleBlobClick(blob)}
                          >
                            <td className="px-6 py-4">
                              <input
                                type="checkbox"
                                checked={selectedBlobs.has(blob.name)}
                                onChange={(e) => {
                                  e.stopPropagation();
                                  handleBlobSelection(blob.name, e.target.checked);
                                }}
                                onClick={(e) => e.stopPropagation()}
                                className="rounded border-gray-300 text-azure-600 focus:ring-azure-500"
                              />
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-2">
                                <span>📄</span>
                                <span className="text-sm font-medium text-gray-900 truncate max-w-xs">
                                  {blob.name}
                                </span>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <span className="text-sm text-gray-500">
                                {blob.properties.contentType || 'application/octet-stream'}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <span className="text-sm text-gray-500">
                                {formatSize(blob.properties.contentLength)}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <span className="text-sm text-gray-500">
                                {formatDate(blob.properties.lastModified)}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDownload(blob);
                                  }}
                                  className="text-azure-600 hover:text-azure-800 text-sm"
                                  title="Download"
                                >
                                  ⬇️
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteBlob(blob);
                                  }}
                                  className="text-red-600 hover:text-red-800 text-sm"
                                  title="Delete"
                                >
                                  🗑️
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {/* Pagination */}
                    {totalPages > 1 && (
                      <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
                        <p className="text-sm text-gray-500">
                          Showing {currentPage * ITEMS_PER_PAGE + 1} to{' '}
                          {Math.min((currentPage + 1) * ITEMS_PER_PAGE, filteredBlobs.length)} of{' '}
                          {filteredBlobs.length} blobs
                        </p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                            disabled={currentPage === 0}
                            className="px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Previous
                          </button>
                          <span className="px-3 py-1 text-sm text-gray-700">
                            Page {currentPage + 1} of {totalPages}
                          </span>
                          <button
                            onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
                            disabled={currentPage >= totalPages - 1}
                            className="px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Next
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400">
                <div className="text-center">
                  <span className="text-6xl mb-4 block">📦</span>
                  <p>Select a container to view its blobs</p>
                </div>
              </div>
            )}
          </div>

          {/* Bottom Panel - Properties */}
          {selectedBlob && (
            <div className="h-64 bg-gray-50 border-t border-gray-200 overflow-y-auto">
              <div className="px-6 py-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Blob Properties</h3>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Name</label>
                    <p className="text-sm text-gray-900 break-all">{selectedBlob.name}</p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Blob Type
                    </label>
                    <p className="text-sm text-gray-900">{selectedBlob.properties.blobType}</p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Content Type
                    </label>
                    <p className="text-sm text-gray-900">
                      {selectedBlob.properties.contentType || 'application/octet-stream'}
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Size</label>
                    <p className="text-sm text-gray-900">
                      {formatSize(selectedBlob.properties.contentLength)}
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">ETag</label>
                    <p className="text-sm text-gray-900 font-mono break-all">
                      {selectedBlob.properties.etag}
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Last Modified
                    </label>
                    <p className="text-sm text-gray-900">
                      {formatDate(selectedBlob.properties.lastModified)}
                    </p>
                  </div>

                  {selectedBlob.properties.leaseStatus && (
                    <>
                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          Lease Status
                        </label>
                        <p className="text-sm text-gray-900">
                          {selectedBlob.properties.leaseStatus}
                        </p>
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          Lease State
                        </label>
                        <p className="text-sm text-gray-900">
                          {selectedBlob.properties.leaseState}
                        </p>
                      </div>
                    </>
                  )}

                  {selectedBlob.snapshot && (
                    <div className="col-span-2">
                      <label className="block text-xs font-medium text-gray-500 mb-1">
                        Snapshot
                      </label>
                      <p className="text-sm text-gray-900 font-mono">{selectedBlob.snapshot}</p>
                    </div>
                  )}

                  {selectedBlob.metadata && Object.keys(selectedBlob.metadata).length > 0 && (
                    <div className="col-span-2">
                      <label className="block text-xs font-medium text-gray-500 mb-1">
                        Metadata
                      </label>
                      <div className="mt-2 space-y-2">
                        {Object.entries(selectedBlob.metadata).map(([key, value]) => (
                          <div key={key} className="flex gap-2">
                            <span className="text-sm font-medium text-gray-700">{key}:</span>
                            <span className="text-sm text-gray-900">{value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        onConfirm={confirmDialog.onConfirm}
        onCancel={() =>
          setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} })
        }
      />

      <ProgressDialog
        isOpen={progressDialog.isOpen}
        title={progressDialog.title}
        progress={progressDialog.progress}
        fileName={progressDialog.fileName}
      />

      {/* Create Container Modal */}
      {showCreateContainerModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4 text-gray-900">Create New Container</h3>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Container Name
              </label>
              <input
                type="text"
                value={newContainerName}
                onChange={(e) => setNewContainerName(e.target.value.toLowerCase())}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleCreateContainer();
                  } else if (e.key === 'Escape') {
                    setShowCreateContainerModal(false);
                    setNewContainerName('');
                  }
                }}
                placeholder="mycontainer"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
                autoFocus
              />
              <p className="text-xs text-gray-500 mt-1">
                3-63 characters, lowercase letters, numbers, and hyphens only
              </p>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowCreateContainerModal(false);
                  setNewContainerName('');
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={handleCreateContainer}
                className="px-4 py-2 text-sm font-medium text-white bg-azure-600 rounded-md hover:bg-azure-700 transition-colors disabled:opacity-50"
                disabled={loading || !newContainerName.trim()}
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

export default BlobStorage;
