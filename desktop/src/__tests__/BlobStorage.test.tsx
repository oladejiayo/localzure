/**
 * Tests for BlobStorage component
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BlobStorage from '../renderer/components/BlobStorage';

// Mock data
const mockContainers = [
  {
    name: 'test-container-1',
    properties: {
      lastModified: '2025-12-12T10:00:00Z',
      etag: '"0x8DBC123456"',
      leaseStatus: 'unlocked',
      leaseState: 'available',
    },
    metadata: {},
  },
  {
    name: 'test-container-2',
    properties: {
      lastModified: '2025-12-12T11:00:00Z',
      etag: '"0x8DBC123457"',
      leaseStatus: 'unlocked',
      leaseState: 'available',
    },
    metadata: {},
  },
];

const mockBlobs = [
  {
    name: 'test-file-1.txt',
    properties: {
      contentLength: 1024,
      contentType: 'text/plain',
      lastModified: '2025-12-12T12:00:00Z',
      etag: '"0x8DBC234567"',
      blobType: 'BlockBlob' as const,
      leaseStatus: 'unlocked',
      leaseState: 'available',
    },
    metadata: { author: 'test' },
  },
  {
    name: 'test-file-2.json',
    properties: {
      contentLength: 2048,
      contentType: 'application/json',
      lastModified: '2025-12-12T13:00:00Z',
      etag: '"0x8DBC234568"',
      blobType: 'BlockBlob' as const,
    },
    metadata: {},
  },
];

describe('BlobStorage Component', () => {
  beforeEach(() => {
    // Reset mocks before each test
    (window.localzureAPI.blob.listContainers as jest.Mock).mockResolvedValue({
      success: true,
      containers: mockContainers,
    });
    (window.localzureAPI.blob.listBlobs as jest.Mock).mockResolvedValue({
      success: true,
      blobs: mockBlobs,
    });
  });

  describe('Header and Controls', () => {
    test('renders header with title and description', () => {
      render(<BlobStorage />);
      expect(screen.getByText('Blob Storage Explorer')).toBeInTheDocument();
      expect(screen.getByText('Browse and manage containers and blobs')).toBeInTheDocument();
    });

    test('renders refresh button', () => {
      render(<BlobStorage />);
      expect(screen.getByText('Refresh')).toBeInTheDocument();
    });

    test('renders new container button', () => {
      render(<BlobStorage />);
      expect(screen.getByText('New Container')).toBeInTheDocument();
    });

    test('calls onRefresh prop when refresh button clicked', () => {
      const mockRefresh = jest.fn();
      render(<BlobStorage onRefresh={mockRefresh} />);
      
      fireEvent.click(screen.getByText('Refresh'));
      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  describe('Container List', () => {
    test('loads and displays containers on mount', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(window.localzureAPI.blob.listContainers).toHaveBeenCalled();
      });

      expect(screen.getByText('test-container-1')).toBeInTheDocument();
      expect(screen.getByText('test-container-2')).toBeInTheDocument();
    });

    test('shows container count', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('2 total')).toBeInTheDocument();
      });
    });

    test('shows loading state while fetching containers', () => {
      (window.localzureAPI.blob.listContainers as jest.Mock).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<BlobStorage />);
      expect(screen.getByText('Loading containers...')).toBeInTheDocument();
    });

    test('shows empty state when no containers', async () => {
      (window.localzureAPI.blob.listContainers as jest.Mock).mockResolvedValue({
        success: true,
        containers: [],
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('No containers found')).toBeInTheDocument();
      });
    });

    test('selects container when clicked', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(window.localzureAPI.blob.listBlobs).toHaveBeenCalledWith('test-container-1', '');
      });
    });

    test('highlights selected container', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      const container = screen.getByText('test-container-1').closest('li');
      expect(container).not.toHaveClass('bg-azure-50');

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(container).toHaveClass('bg-azure-50');
      });
    });
  });

  describe('Blob List', () => {
    test('shows placeholder when no container selected', () => {
      render(<BlobStorage />);
      expect(screen.getByText('Select a container to view its blobs')).toBeInTheDocument();
    });

    test('loads and displays blobs when container selected', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
        expect(screen.getByText('test-file-2.json')).toBeInTheDocument();
      });
    });

    test('displays blob properties in table', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
        expect(screen.getByText('text/plain')).toBeInTheDocument();
        expect(screen.getByText('1.00 KB')).toBeInTheDocument();
      });
    });

    test('shows upload button when container selected', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('Upload')).toBeInTheDocument();
      });
    });

    test('shows empty state when no blobs in container', async () => {
      (window.localzureAPI.blob.listBlobs as jest.Mock).mockResolvedValue({
        success: true,
        blobs: [],
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('No blobs in this container')).toBeInTheDocument();
      });
    });
  });

  describe('Blob Selection', () => {
    test('allows single blob selection', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole('checkbox');
      const firstBlobCheckbox = checkboxes[1]; // Skip the "select all" checkbox
      
      fireEvent.click(firstBlobCheckbox);
      expect(firstBlobCheckbox).toBeChecked();
    });

    test('allows select all blobs', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole('checkbox');
      const selectAllCheckbox = checkboxes[0];
      
      fireEvent.click(selectAllCheckbox);
      
      checkboxes.slice(1).forEach((checkbox) => {
        expect(checkbox).toBeChecked();
      });
    });

    test('shows delete button for selected blobs', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole('checkbox');
      fireEvent.click(checkboxes[1]);
      
      await waitFor(() => {
        expect(screen.getByText(/Delete \(1\)/)).toBeInTheDocument();
      });
    });
  });

  describe('Blob Properties Panel', () => {
    test('shows properties panel when blob selected', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-file-1.txt'));
      
      await waitFor(() => {
        expect(screen.getByText('Blob Properties')).toBeInTheDocument();
      });
    });

    test('displays all blob properties', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-file-1.txt'));
      
      await waitFor(() => {
        expect(screen.getByText('Blob Type')).toBeInTheDocument();
        expect(screen.getByText('BlockBlob')).toBeInTheDocument();
        expect(screen.getByText('ETag')).toBeInTheDocument();
        expect(screen.getByText('Lease Status')).toBeInTheDocument();
      });
    });

    test('displays metadata when present', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-file-1.txt'));
      
      await waitFor(() => {
        expect(screen.getByText('Metadata')).toBeInTheDocument();
        expect(screen.getByText('author:')).toBeInTheDocument();
        expect(screen.getByText('test')).toBeInTheDocument();
      });
    });
  });

  describe('Search and Filter', () => {
    test('renders search input when container selected', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Filter by name prefix...')).toBeInTheDocument();
      });
    });

    test('filters blobs by name', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
        expect(screen.getByText('test-file-2.json')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Filter by name prefix...');
      fireEvent.change(searchInput, { target: { value: '.txt' } });
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
        expect(screen.queryByText('test-file-2.json')).not.toBeInTheDocument();
      });
    });

    test('calls search API when search button clicked', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Filter by name prefix...')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Filter by name prefix...');
      fireEvent.change(searchInput, { target: { value: 'test-' } });
      
      const searchButton = screen.getByText('Search');
      fireEvent.click(searchButton);
      
      await waitFor(() => {
        expect(window.localzureAPI.blob.listBlobs).toHaveBeenCalledWith('test-container-1', 'test-');
      });
    });
  });

  describe('Pagination', () => {
    test('shows pagination when more than 50 blobs', async () => {
      const manyBlobs = Array.from({ length: 100 }, (_, i) => ({
        name: `blob-${i}.txt`,
        properties: {
          contentLength: 1024,
          contentType: 'text/plain',
          lastModified: '2025-12-12T12:00:00Z',
          etag: `"0x8DBC${i}"`,
          blobType: 'BlockBlob' as const,
        },
        metadata: {},
      }));

      (window.localzureAPI.blob.listBlobs as jest.Mock).mockResolvedValue({
        success: true,
        blobs: manyBlobs,
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText(/Showing 1 to 50 of 100 blobs/)).toBeInTheDocument();
        expect(screen.getByText('Previous')).toBeInTheDocument();
        expect(screen.getByText('Next')).toBeInTheDocument();
      });
    });

    test('navigates to next page', async () => {
      const manyBlobs = Array.from({ length: 100 }, (_, i) => ({
        name: `blob-${i}.txt`,
        properties: {
          contentLength: 1024,
          contentType: 'text/plain',
          lastModified: '2025-12-12T12:00:00Z',
          etag: `"0x8DBC${i}"`,
          blobType: 'BlockBlob' as const,
        },
        metadata: {},
      }));

      (window.localzureAPI.blob.listBlobs as jest.Mock).mockResolvedValue({
        success: true,
        blobs: manyBlobs,
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('blob-0.txt')).toBeInTheDocument();
      });

      const nextButton = screen.getByText('Next');
      fireEvent.click(nextButton);
      
      await waitFor(() => {
        expect(screen.getByText(/Showing 51 to 100 of 100 blobs/)).toBeInTheDocument();
      });
    });
  });

  describe('Create Container', () => {
    test('shows prompt when new container button clicked', async () => {
      global.prompt = jest.fn(() => 'new-container');
      (window.localzureAPI.blob.createContainer as jest.Mock).mockResolvedValue({
        success: true,
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('New Container')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('New Container'));
      
      expect(global.prompt).toHaveBeenCalledWith('Enter container name (lowercase, no spaces):');
    });

    test('validates container name format', async () => {
      global.prompt = jest.fn(() => 'INVALID_NAME');

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('New Container')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('New Container'));
      
      await waitFor(() => {
        expect(screen.getByText(/Invalid container name/)).toBeInTheDocument();
      });

      expect(window.localzureAPI.blob.createContainer).not.toHaveBeenCalled();
    });

    test('creates container with valid name', async () => {
      global.prompt = jest.fn(() => 'new-container');
      (window.localzureAPI.blob.createContainer as jest.Mock).mockResolvedValue({
        success: true,
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('New Container')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('New Container'));
      
      await waitFor(() => {
        expect(window.localzureAPI.blob.createContainer).toHaveBeenCalledWith('new-container');
      });
    });
  });

  describe('Delete Operations', () => {
    test('shows confirmation dialog before deleting blob', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTitle('Delete');
      fireEvent.click(deleteButtons[0]);
      
      await waitFor(() => {
        expect(screen.getByText('Delete Blob')).toBeInTheDocument();
        expect(screen.getByText(/Are you sure you want to delete "test-file-1.txt"/)).toBeInTheDocument();
      });
    });

    test('deletes blob when confirmed', async () => {
      (window.localzureAPI.blob.deleteBlob as jest.Mock).mockResolvedValue({
        success: true,
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTitle('Delete');
      fireEvent.click(deleteButtons[0]);
      
      await waitFor(() => {
        expect(screen.getByText('Delete Blob')).toBeInTheDocument();
      });

      const confirmButton = screen.getByRole('button', { name: 'Delete' });
      fireEvent.click(confirmButton);
      
      await waitFor(() => {
        expect(window.localzureAPI.blob.deleteBlob).toHaveBeenCalledWith('test-container-1', 'test-file-1.txt');
      });
    });

    test('shows confirmation dialog before deleting container', async () => {
      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTitle('Delete container');
      fireEvent.click(deleteButtons[0]);
      
      await waitFor(() => {
        expect(screen.getByText('Delete Container')).toBeInTheDocument();
        expect(screen.getByText(/All blobs in this container will be deleted/)).toBeInTheDocument();
      });
    });

    test('deletes multiple selected blobs', async () => {
      (window.localzureAPI.blob.deleteBlob as jest.Mock).mockResolvedValue({
        success: true,
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('test-file-1.txt')).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole('checkbox');
      fireEvent.click(checkboxes[1]);
      fireEvent.click(checkboxes[2]);
      
      await waitFor(() => {
        expect(screen.getByText(/Delete \(2\)/)).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText(/Delete \(2\)/));
      
      await waitFor(() => {
        expect(screen.getByText('Delete Multiple Blobs')).toBeInTheDocument();
      });

      const confirmButton = screen.getByRole('button', { name: 'Delete' });
      fireEvent.click(confirmButton);
      
      await waitFor(() => {
        expect(window.localzureAPI.blob.deleteBlob).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Error Handling', () => {
    test('displays error message when container list fails', async () => {
      (window.localzureAPI.blob.listContainers as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Failed to connect',
        containers: [],
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('Failed to connect')).toBeInTheDocument();
      });
    });

    test('displays error message when blob list fails', async () => {
      (window.localzureAPI.blob.listBlobs as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Container not found',
        blobs: [],
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('Container not found')).toBeInTheDocument();
      });
    });

    test('allows dismissing error messages', async () => {
      (window.localzureAPI.blob.listContainers as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Test error',
        containers: [],
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('Test error')).toBeInTheDocument();
      });

      const closeButton = screen.getByText('✕');
      fireEvent.click(closeButton);
      
      await waitFor(() => {
        expect(screen.queryByText('Test error')).not.toBeInTheDocument();
      });
    });
  });

  describe('File Size Formatting', () => {
    test('formats bytes correctly', async () => {
      const blobsWithSizes = [
        {
          name: 'small.txt',
          properties: {
            contentLength: 500,
            contentType: 'text/plain',
            lastModified: '2025-12-12T12:00:00Z',
            etag: '"0x8DBC1"',
            blobType: 'BlockBlob' as const,
          },
          metadata: {},
        },
        {
          name: 'medium.txt',
          properties: {
            contentLength: 1048576, // 1 MB
            contentType: 'text/plain',
            lastModified: '2025-12-12T12:00:00Z',
            etag: '"0x8DBC2"',
            blobType: 'BlockBlob' as const,
          },
          metadata: {},
        },
      ];

      (window.localzureAPI.blob.listBlobs as jest.Mock).mockResolvedValue({
        success: true,
        blobs: blobsWithSizes,
      });

      render(<BlobStorage />);
      
      await waitFor(() => {
        expect(screen.getByText('test-container-1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('test-container-1'));
      
      await waitFor(() => {
        expect(screen.getByText('500 B')).toBeInTheDocument();
        expect(screen.getByText('1.00 MB')).toBeInTheDocument();
      });
    });
  });
});
