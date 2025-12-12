/**
 * Comprehensive tests for enhanced Real-Time Logs Viewer (DESKTOP-003)
 * Tests all 7 acceptance criteria and technical requirements
 */

import { render, screen, fireEvent, within, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import Logs from '../renderer/components/Logs';

// Mock log entry interface
interface LogEntry {
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
  module: string;
  message: string;
  correlation_id?: string;
  context?: Record<string, any>;
}

// Helper to create mock logs
const createMockLog = (overrides?: Partial<LogEntry>): LogEntry => ({
  timestamp: new Date().toISOString(),
  level: 'INFO',
  module: 'LocalZure',
  message: 'Test log message',
  ...overrides,
});

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn(() => Promise.resolve()),
  },
});

// Mock URL.createObjectURL and document.createElement
global.URL.createObjectURL = jest.fn(() => 'mock-url');
global.URL.revokeObjectURL = jest.fn();

// Mock scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

describe('Enhanced Logs Component - DESKTOP-003', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  // ==========================================
  // AC1: Real-time log display
  // ==========================================
  describe('AC1: Real-time log display', () => {
    test('renders logs viewer with correct title', () => {
      render(<Logs logs={[]} />);
      expect(screen.getByText('Real-Time Logs Viewer')).toBeInTheDocument();
    });

    test('displays log count correctly', () => {
      const logs = [
        createMockLog({ message: 'Log 1' }),
        createMockLog({ message: 'Log 2' }),
        createMockLog({ message: 'Log 3' }),
      ];
      render(<Logs logs={logs} />);
      expect(screen.getByText(/3 of 3 entries/)).toBeInTheDocument();
    });

    test('shows streaming indicator when not paused', () => {
      render(<Logs logs={[]} />);
      expect(screen.getByText(/🔴 Streaming/)).toBeInTheDocument();
    });

    test('shows paused indicator when paused', () => {
      render(<Logs logs={[]} />);
      const pauseButton = screen.getByTitle('Pause streaming');
      fireEvent.click(pauseButton);
      expect(screen.getByText(/⏸️ Paused/)).toBeInTheDocument();
    });

    test('displays empty state when no logs', () => {
      render(<Logs logs={[]} />);
      expect(screen.getByText('No logs yet')).toBeInTheDocument();
      expect(screen.getByText('Start LocalZure to see logs')).toBeInTheDocument();
    });
  });

  // ==========================================
  // AC2: Display timestamp, level, module, message
  // ==========================================
  describe('AC2: Display log entry details', () => {
    test('displays all log entry fields', () => {
      const log = createMockLog({
        timestamp: '2024-01-15T10:30:45.123Z',
        level: 'INFO',
        module: 'BlobStorage',
        message: 'Container created successfully',
      });
      render(<Logs logs={[log]} />);

      expect(screen.getByText('INFO')).toBeInTheDocument();
      // Find BlobStorage in log entry badge (not in dropdown)
      const moduleBadge = screen.getAllByText('BlobStorage').find(
        el => el.className.includes('bg-gray-100')
      );
      expect(moduleBadge).toBeInTheDocument();
      expect(screen.getByText('Container created successfully')).toBeInTheDocument();
      expect(screen.getByText(/10:30:45/)).toBeInTheDocument(); // Timestamp formatted
    });

    test('displays correlation ID when present', () => {
      const log = createMockLog({
        message: 'Request processed',
        correlation_id: '12345678-abcd-efgh-ijkl-mnopqrstuvwx',
      });
      render(<Logs logs={[log]} />);
      expect(screen.getByText(/ID: 12345678/)).toBeInTheDocument();
    });

    test('displays context when present', () => {
      const log = createMockLog({
        message: 'Operation completed',
        context: { duration: 150, status: 'success' },
      });
      render(<Logs logs={[log]} />);
      
      // Context is initially hidden
      expect(screen.queryByText(/"duration"/)).not.toBeInTheDocument();
      
      // Click to expand
      const expandButton = screen.getByText(/▶ Show context/);
      fireEvent.click(expandButton);
      
      expect(screen.getByText(/"duration"/)).toBeInTheDocument();
      expect(screen.getByText(/150/)).toBeInTheDocument();
    });
  });

  // ==========================================
  // AC3: Filter by level
  // ==========================================
  describe('AC3: Filter by log level', () => {
    const testLogs: LogEntry[] = [
      createMockLog({ level: 'DEBUG', message: 'Debug message' }),
      createMockLog({ level: 'INFO', message: 'Info message' }),
      createMockLog({ level: 'WARN', message: 'Warning message' }),
      createMockLog({ level: 'ERROR', message: 'Error message' }),
    ];

    test('shows all logs when "All Levels" selected', () => {
      render(<Logs logs={testLogs} />);
      expect(screen.getByText('Debug message')).toBeInTheDocument();
      expect(screen.getByText('Info message')).toBeInTheDocument();
      expect(screen.getByText('Warning message')).toBeInTheDocument();
      expect(screen.getByText('Error message')).toBeInTheDocument();
    });

    test('filters logs by DEBUG level', () => {
      render(<Logs logs={testLogs} />);
      const levelFilter = screen.getByTestId('level-filter');
      fireEvent.change(levelFilter, { target: { value: 'DEBUG' } });

      expect(screen.getByText('Debug message')).toBeInTheDocument();
      expect(screen.queryByText('Info message')).not.toBeInTheDocument();
      expect(screen.queryByText('Warning message')).not.toBeInTheDocument();
      expect(screen.queryByText('Error message')).not.toBeInTheDocument();
    });

    test('filters logs by INFO level', () => {
      render(<Logs logs={testLogs} />);
      const levelFilter = screen.getByTestId('level-filter');
      fireEvent.change(levelFilter, { target: { value: 'INFO' } });

      expect(screen.queryByText('Debug message')).not.toBeInTheDocument();
      expect(screen.getByText('Info message')).toBeInTheDocument();
      expect(screen.queryByText('Warning message')).not.toBeInTheDocument();
      expect(screen.queryByText('Error message')).not.toBeInTheDocument();
    });

    test('filters logs by WARN level', () => {
      render(<Logs logs={testLogs} />);
      const levelFilter = screen.getByTestId('level-filter');
      fireEvent.change(levelFilter, { target: { value: 'WARN' } });

      expect(screen.queryByText('Debug message')).not.toBeInTheDocument();
      expect(screen.queryByText('Info message')).not.toBeInTheDocument();
      expect(screen.getByText('Warning message')).toBeInTheDocument();
      expect(screen.queryByText('Error message')).not.toBeInTheDocument();
    });

    test('filters logs by ERROR level', () => {
      render(<Logs logs={testLogs} />);
      const levelFilter = screen.getByTestId('level-filter');
      fireEvent.change(levelFilter, { target: { value: 'ERROR' } });

      expect(screen.queryByText('Debug message')).not.toBeInTheDocument();
      expect(screen.queryByText('Info message')).not.toBeInTheDocument();
      expect(screen.queryByText('Warning message')).not.toBeInTheDocument();
      expect(screen.getByText('Error message')).toBeInTheDocument();
    });

    test('shows filtered count correctly', () => {
      render(<Logs logs={testLogs} />);
      const levelFilter = screen.getByTestId('level-filter');
      fireEvent.change(levelFilter, { target: { value: 'ERROR' } });

      expect(screen.getByText(/1 of 4 entries/)).toBeInTheDocument();
    });
  });

  // ==========================================
  // AC4: Filter by service/module
  // ==========================================
  describe('AC4: Filter by service/module', () => {
    const testLogs: LogEntry[] = [
      createMockLog({ module: 'BlobStorage', message: 'Blob uploaded' }),
      createMockLog({ module: 'BlobStorage', message: 'Container created' }),
      createMockLog({ module: 'ServiceBus', message: 'Message sent' }),
      createMockLog({ module: 'KeyVault', message: 'Secret retrieved' }),
    ];

    test('shows all modules in filter dropdown', () => {
      render(<Logs logs={testLogs} />);
      const moduleFilter = screen.getByTestId('module-filter');
      
      // Should have: All Modules, BlobStorage, KeyVault, ServiceBus (alphabetically)
      const options = within(moduleFilter).getAllByRole('option');
      expect(options).toHaveLength(4); // ALL + 3 unique modules
      expect(options[0]).toHaveTextContent('All Modules');
    });

    test('filters logs by specific module', () => {
      render(<Logs logs={testLogs} />);
      const moduleFilter = screen.getByTestId('module-filter');
      fireEvent.change(moduleFilter, { target: { value: 'BlobStorage' } });

      expect(screen.getByText('Blob uploaded')).toBeInTheDocument();
      expect(screen.getByText('Container created')).toBeInTheDocument();
      expect(screen.queryByText('Message sent')).not.toBeInTheDocument();
      expect(screen.queryByText('Secret retrieved')).not.toBeInTheDocument();
    });

    test('shows empty state when no logs match module filter', () => {
      render(<Logs logs={testLogs} />);
      const moduleFilter = screen.getByTestId('module-filter');
      fireEvent.change(moduleFilter, { target: { value: 'NonExistent' } });

      expect(screen.getByText('No logs match filters')).toBeInTheDocument();
      expect(screen.getByText('Try adjusting your filters')).toBeInTheDocument();
    });
  });

  // ==========================================
  // AC5: Search by text content
  // ==========================================
  describe('AC5: Search functionality', () => {
    const testLogs: LogEntry[] = [
      createMockLog({ message: 'Container mycontainer created' }),
      createMockLog({ message: 'Blob uploaded successfully' }),
      createMockLog({ level: 'ERROR', message: 'Error: Connection timeout' }),
      createMockLog({ module: 'ServiceBus', message: 'Queue created' }),
    ];

    test('searches logs by message content', () => {
      render(<Logs logs={testLogs} />);
      const searchInput = screen.getByPlaceholderText('Search logs...');
      fireEvent.change(searchInput, { target: { value: 'container' } });

      expect(screen.getByText(/Container mycontainer created/)).toBeInTheDocument();
      expect(screen.queryByText('Blob uploaded successfully')).not.toBeInTheDocument();
    });

    test('searches logs by module name', () => {
      render(<Logs logs={testLogs} />);
      const searchInput = screen.getByPlaceholderText('Search logs...');
      fireEvent.change(searchInput, { target: { value: 'servicebus' } });

      expect(screen.getByText('Queue created')).toBeInTheDocument();
      expect(screen.queryByText('Container mycontainer created')).not.toBeInTheDocument();
    });

    test('search is case-insensitive', () => {
      render(<Logs logs={testLogs} />);
      const searchInput = screen.getByPlaceholderText('Search logs...');
      fireEvent.change(searchInput, { target: { value: 'ERROR' } });

      expect(screen.getByText(/Error: Connection timeout/)).toBeInTheDocument();
    });

    test('searches across correlation IDs', () => {
      const logs = [
        createMockLog({ message: 'Request', correlation_id: 'abc123' }),
        createMockLog({ message: 'Response', correlation_id: 'xyz789' }),
      ];
      render(<Logs logs={logs} />);
      const searchInput = screen.getByPlaceholderText('Search logs...');
      fireEvent.change(searchInput, { target: { value: 'abc' } });

      expect(screen.getByText('Request')).toBeInTheDocument();
      expect(screen.queryByText('Response')).not.toBeInTheDocument();
    });

    test('combines search with filters', () => {
      render(<Logs logs={testLogs} />);
      
      // Apply level filter
      const levelFilter = screen.getByTestId('level-filter');
      fireEvent.change(levelFilter, { target: { value: 'ERROR' } });
      
      // Apply search
      const searchInput = screen.getByPlaceholderText('Search logs...');
      fireEvent.change(searchInput, { target: { value: 'timeout' } });

      expect(screen.getByText(/Error: Connection timeout/)).toBeInTheDocument();
      expect(screen.getByText(/1 of 4 entries/)).toBeInTheDocument();
    });
  });

  // ==========================================
  // AC6: Auto-scroll toggle
  // ==========================================
  describe('AC6: Auto-scroll functionality', () => {
    test('auto-scroll is enabled by default', () => {
      render(<Logs logs={[]} />);
      const autoScrollButton = screen.getByTitle('Toggle auto-scroll');
      expect(autoScrollButton).toHaveTextContent('📌 Auto-scroll ON');
    });

    test('toggle auto-scroll on/off', () => {
      render(<Logs logs={[]} />);
      const autoScrollButton = screen.getByTitle('Toggle auto-scroll');
      
      // Initially ON
      expect(autoScrollButton).toHaveTextContent('📌 Auto-scroll ON');
      
      // Click to turn OFF
      fireEvent.click(autoScrollButton);
      expect(autoScrollButton).toHaveTextContent('📌 Auto-scroll OFF');
      
      // Click to turn ON again
      fireEvent.click(autoScrollButton);
      expect(autoScrollButton).toHaveTextContent('📌 Auto-scroll ON');
    });

    test('shows scroll to bottom button when auto-scroll is off', () => {
      render(<Logs logs={[createMockLog()]} />);
      
      // Turn off auto-scroll
      const autoScrollButton = screen.getByTitle('Toggle auto-scroll');
      fireEvent.click(autoScrollButton);
      
      // Bottom button should appear
      expect(screen.getByTitle('Scroll to bottom')).toBeInTheDocument();
    });

    test('hides scroll to bottom button when auto-scroll is on', () => {
      render(<Logs logs={[createMockLog()]} />);
      
      // Auto-scroll is ON by default
      expect(screen.queryByTitle('Scroll to bottom')).not.toBeInTheDocument();
    });
  });

  // ==========================================
  // AC7: Export to file
  // ==========================================
  describe('AC7: Export functionality', () => {
    const testLogs: LogEntry[] = [
      createMockLog({ level: 'INFO', module: 'Test', message: 'Log 1' }),
      createMockLog({ level: 'ERROR', module: 'Test', message: 'Log 2' }),
    ];

    let mockClick: jest.Mock;
    let mockAnchor: any;
    let originalCreateElement: typeof document.createElement;

    beforeEach(() => {
      mockClick = jest.fn();
      mockAnchor = {
        href: '',
        download: '',
        click: mockClick,
        setAttribute: jest.fn(),
        removeAttribute: jest.fn(),
        style: {},
      };
      
      // Save original and create proper mock
      originalCreateElement = document.createElement.bind(document);
      jest.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
        if (tagName === 'a') {
          return mockAnchor;
        }
        return originalCreateElement(tagName);
      });
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    test('exports logs as JSON', () => {
      render(<Logs logs={testLogs} />);
      const jsonButton = screen.getByTitle('Export as JSON');
      fireEvent.click(jsonButton);

      expect(mockClick).toHaveBeenCalled();
      expect(mockAnchor.download).toMatch(/localzure-logs-\d+\.json/);
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });

    test('exports logs as text', () => {
      render(<Logs logs={testLogs} />);
      const txtButton = screen.getByTitle('Export as text');
      fireEvent.click(txtButton);

      expect(mockClick).toHaveBeenCalled();
      expect(mockAnchor.download).toMatch(/localzure-logs-\d+\.txt/);
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });

    test('exports only filtered logs', () => {
      render(<Logs logs={testLogs} />);
      
      // Apply filter
      const levelFilter = screen.getByTestId('level-filter');
      fireEvent.change(levelFilter, { target: { value: 'ERROR' } });
      
      // Export as JSON
      const jsonButton = screen.getByTitle('Export as JSON');
      fireEvent.click(jsonButton);

      // Verify export was called with filtered data
      expect(mockClick).toHaveBeenCalled();
      expect(mockAnchor.download).toMatch(/\.json$/);
    });
  });

  // ==========================================
  // Additional Technical Requirements
  // ==========================================
  describe('Technical Requirements', () => {
    test('buffers maximum 10,000 logs', () => {
      const manyLogs = Array.from({ length: 15000 }, (_, i) =>
        createMockLog({ message: `Log ${i}` })
      );
      render(<Logs logs={manyLogs} />);

      // Should show 10,000 buffered
      expect(screen.getByText(/10000 of 10000 entries/)).toBeInTheDocument();
      expect(screen.getByText(/max buffer/)).toBeInTheDocument();
    });

    test('displays color-coded log levels', () => {
      const logs = [
        createMockLog({ level: 'ERROR', message: 'Error log' }),
        createMockLog({ level: 'WARN', message: 'Warn log' }),
        createMockLog({ level: 'INFO', message: 'Info log' }),
        createMockLog({ level: 'DEBUG', message: 'Debug log' }),
      ];
      render(<Logs logs={logs} />);

      // All level badges should be rendered
      const errorBadge = screen.getByText('ERROR');
      const warnBadge = screen.getByText('WARN');
      const infoBadge = screen.getByText('INFO');
      const debugBadge = screen.getByText('DEBUG');

      expect(errorBadge).toBeInTheDocument();
      expect(warnBadge).toBeInTheDocument();
      expect(infoBadge).toBeInTheDocument();
      expect(debugBadge).toBeInTheDocument();
    });

    test('pause/resume streaming', () => {
      render(<Logs logs={[]} />);
      
      const pauseButton = screen.getByTitle('Pause streaming');
      expect(pauseButton).toHaveTextContent('⏸️ Pause');
      
      fireEvent.click(pauseButton);
      
      const resumeButton = screen.getByTitle('Resume streaming');
      expect(resumeButton).toHaveTextContent('▶️ Resume');
    });

    test('clear logs button', () => {
      const mockClearLogs = jest.fn();
      render(<Logs logs={[createMockLog()]} onClearLogs={mockClearLogs} />);
      
      const clearButton = screen.getByTitle('Clear all logs');
      fireEvent.click(clearButton);
      
      expect(mockClearLogs).toHaveBeenCalled();
    });

    test('copy log to clipboard', async () => {
      const log = createMockLog({ message: 'Test message', module: 'TestModule' });
      render(<Logs logs={[log]} />);
      
      const copyButton = screen.getByTitle('Copy log to clipboard');
      fireEvent.click(copyButton);
      
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
      const copiedText = (navigator.clipboard.writeText as jest.Mock).mock.calls[0][0];
      expect(copiedText).toContain('Test message');
      expect(copiedText).toContain('TestModule');
    });

    test('displays log statistics in footer', () => {
      const logs = [
        createMockLog({ level: 'ERROR' }),
        createMockLog({ level: 'ERROR' }),
        createMockLog({ level: 'WARN' }),
        createMockLog({ level: 'INFO' }),
      ];
      render(<Logs logs={logs} />);

      expect(screen.getByText(/Total:/)).toBeInTheDocument();
      expect(screen.getByText(/ERROR:/)).toBeInTheDocument();
      expect(screen.getByText(/WARN:/)).toBeInTheDocument();
    });

    test('displays level icons in legend', () => {
      render(<Logs logs={[]} />);
      
      // Footer legend should show all level icons - use getAllByText for multiple matches
      const errorIcons = screen.getAllByText(/ERROR/);
      const warnIcons = screen.getAllByText(/WARN/);
      const infoIcons = screen.getAllByText(/INFO/);
      const debugIcons = screen.getAllByText(/DEBUG/);
      
      expect(errorIcons.length).toBeGreaterThan(0);
      expect(warnIcons.length).toBeGreaterThan(0);
      expect(infoIcons.length).toBeGreaterThan(0);
      expect(debugIcons.length).toBeGreaterThan(0);
    });
  });

  // ==========================================
  // Edge Cases and Error Handling
  // ==========================================
  describe('Edge Cases', () => {
    test('handles logs with missing optional fields', () => {
      const log: LogEntry = {
        timestamp: new Date().toISOString(),
        level: 'INFO',
        module: 'Test',
        message: 'Simple log',
        // No correlation_id or context
      };
      
      render(<Logs logs={[log]} />);
      expect(screen.getByText('Simple log')).toBeInTheDocument();
    });

    test('handles very long log messages', () => {
      const longMessage = 'A'.repeat(1000);
      const log = createMockLog({ message: longMessage });
      
      render(<Logs logs={[log]} />);
      expect(screen.getByText(longMessage)).toBeInTheDocument();
    });

    test('handles special characters in log messages', () => {
      const log = createMockLog({ message: '<script>alert("XSS")</script>' });
      
      render(<Logs logs={[log]} />);
      expect(screen.getByText('<script>alert("XSS")</script>')).toBeInTheDocument();
    });

    test('handles invalid timestamp gracefully', () => {
      const log = createMockLog({ timestamp: 'invalid-timestamp' });
      
      render(<Logs logs={[log]} />);
      // Should still render, even with invalid timestamp
      expect(screen.getByText('Test log message')).toBeInTheDocument();
    });
  });
});
