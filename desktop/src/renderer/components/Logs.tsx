import { useState, useRef, useEffect, useMemo } from 'react';

// Enhanced log entry interface matching AC2 requirements
interface LogEntry {
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
  module: string;
  message: string;
  correlation_id?: string;
  context?: Record<string, any>;
}

interface LogsProps {
  logs: LogEntry[];
  onClearLogs?: () => void;
}

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'ALL';
type ExportFormat = 'json' | 'text';

function Logs({ logs, onClearLogs }: LogsProps) {
  // State for filters and controls
  const [levelFilter, setLevelFilter] = useState<LogLevel>('ALL');
  const [moduleFilter, setModuleFilter] = useState<string>('ALL');
  const [searchText, setSearchText] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [expandedLog, setExpandedLog] = useState<number | null>(null);

  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);

  // Buffer last 10,000 logs (AC requirement)
  const bufferedLogs = useMemo(() => logs.slice(-10000), [logs]);

  // Extract unique modules for filter dropdown
  const uniqueModules = useMemo(() => {
    const modules = new Set(bufferedLogs.map(log => log.module));
    return ['ALL', ...Array.from(modules).sort()];
  }, [bufferedLogs]);

  // Filter logs based on level, module, and search text
  const filteredLogs = useMemo(() => {
    return bufferedLogs.filter(log => {
      // Level filter
      if (levelFilter !== 'ALL' && log.level !== levelFilter) {
        return false;
      }

      // Module filter
      if (moduleFilter !== 'ALL' && log.module !== moduleFilter) {
        return false;
      }

      // Search text filter
      if (searchText) {
        const searchLower = searchText.toLowerCase();
        return (
          log.message.toLowerCase().includes(searchLower) ||
          log.module.toLowerCase().includes(searchLower) ||
          log.correlation_id?.toLowerCase().includes(searchLower) ||
          JSON.stringify(log.context || {}).toLowerCase().includes(searchLower)
        );
      }

      return true;
    });
  }, [bufferedLogs, levelFilter, moduleFilter, searchText]);

  // Auto-scroll to bottom when new logs arrive (if enabled)
  useEffect(() => {
    if (autoScroll && !isPaused && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [filteredLogs, autoScroll, isPaused]);

  // Detect manual scroll and disable auto-scroll
  useEffect(() => {
    const container = logsContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      if (!isAtBottom && autoScroll) {
        setAutoScroll(false);
      }
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [autoScroll]);

  const getLevelColor = (level: LogLevel): string => {
    switch (level) {
      case 'ERROR':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'WARN':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'INFO':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'DEBUG':
        return 'text-gray-600 bg-gray-50 border-gray-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getLevelIcon = (level: LogLevel): string => {
    switch (level) {
      case 'ERROR':
        return '❌';
      case 'WARN':
        return '⚠️';
      case 'INFO':
        return 'ℹ️';
      case 'DEBUG':
        return '🔍';
      default:
        return '📝';
    }
  };

  const getLevelBadgeColor = (level: LogLevel): string => {
    switch (level) {
      case 'ERROR':
        return 'bg-red-600 text-white';
      case 'WARN':
        return 'bg-yellow-500 text-white';
      case 'INFO':
        return 'bg-blue-600 text-white';
      case 'DEBUG':
        return 'bg-gray-500 text-white';
      default:
        return 'bg-gray-500 text-white';
    }
  };

  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3,
      });
    } catch {
      return timestamp;
    }
  };

  const handleClearLogs = () => {
    if (onClearLogs) {
      onClearLogs();
    }
  };

  const handleExportLogs = (format: ExportFormat) => {
    const dataToExport = filteredLogs;

    let content: string;
    let filename: string;
    let mimeType: string;

    if (format === 'json') {
      content = JSON.stringify(dataToExport, null, 2);
      filename = `localzure-logs-${Date.now()}.json`;
      mimeType = 'application/json';
    } else {
      // Text format
      content = dataToExport
        .map(
          log =>
            `[${formatTimestamp(log.timestamp)}] [${log.level}] [${log.module}] ${log.message}${
              log.correlation_id ? ` (${log.correlation_id})` : ''
            }${log.context ? `\nContext: ${JSON.stringify(log.context)}` : ''}`
        )
        .join('\n\n');
      filename = `localzure-logs-${Date.now()}.txt`;
      mimeType = 'text/plain';
    }

    // Create download
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopyLog = (log: LogEntry) => {
    const text = `[${formatTimestamp(log.timestamp)}] [${log.level}] [${log.module}] ${
      log.message
    }${log.correlation_id ? `\n  Correlation ID: ${log.correlation_id}` : ''}${
      log.context ? `\n  Context: ${JSON.stringify(log.context, null, 2)}` : ''
    }`;

    navigator.clipboard.writeText(text).then(() => {
      // Could show a toast notification here
      console.log('Log copied to clipboard');
    });
  };

  const togglePause = () => {
    setIsPaused(!isPaused);
  };

  const scrollToBottom = () => {
    setAutoScroll(true);
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Real-Time Logs Viewer</h1>
            <p className="text-sm text-gray-500 mt-1">
              {isPaused ? '⏸️ Paused' : '🔴 Streaming'} • {filteredLogs.length} of{' '}
              {bufferedLogs.length} entries
              {bufferedLogs.length >= 10000 && ' (max buffer)'}
            </p>
          </div>

          <div className="flex gap-2">
            <button
              onClick={togglePause}
              className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                isPaused
                  ? 'bg-green-600 text-white hover:bg-green-700'
                  : 'bg-yellow-600 text-white hover:bg-yellow-700'
              }`}
              title={isPaused ? 'Resume streaming' : 'Pause streaming'}
            >
              {isPaused ? '▶️ Resume' : '⏸️ Pause'}
            </button>

            <button
              onClick={() => handleExportLogs('text')}
              className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              title="Export as text"
            >
              📄 TXT
            </button>

            <button
              onClick={() => handleExportLogs('json')}
              className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              title="Export as JSON"
            >
              📋 JSON
            </button>

            <button
              onClick={handleClearLogs}
              className="px-3 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 transition-colors"
              title="Clear all logs"
            >
              🗑️ Clear
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="mt-4 flex gap-3 flex-wrap">
          {/* Level Filter */}
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Level:</label>
            <select
              data-testid="level-filter"
              value={levelFilter}
              onChange={e => setLevelFilter(e.target.value as LogLevel)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
            >
              <option value="ALL">All Levels</option>
              <option value="DEBUG">🔍 DEBUG</option>
              <option value="INFO">ℹ️ INFO</option>
              <option value="WARN">⚠️ WARN</option>
              <option value="ERROR">❌ ERROR</option>
            </select>
          </div>

          {/* Module Filter */}
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Module:</label>
            <select
              data-testid="module-filter"
              value={moduleFilter}
              onChange={e => setModuleFilter(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
            >
              {uniqueModules.map(module => (
                <option key={module} value={module}>
                  {module === 'ALL' ? 'All Modules' : module}
                </option>
              ))}
            </select>
          </div>

          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search logs..."
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-azure-500"
            />
          </div>

          {/* Auto-scroll Toggle */}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              autoScroll
                ? 'bg-azure-600 text-white hover:bg-azure-700'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
            title="Toggle auto-scroll"
          >
            {autoScroll ? '📌 Auto-scroll ON' : '📌 Auto-scroll OFF'}
          </button>

          {!autoScroll && (
            <button
              onClick={scrollToBottom}
              className="px-3 py-1.5 text-sm font-medium text-white bg-gray-700 rounded-md hover:bg-gray-800 transition-colors"
              title="Scroll to bottom"
            >
              ⬇️ Bottom
            </button>
          )}
        </div>
      </div>

      {/* Logs Container */}
      <div className="flex-1 overflow-hidden">
        {filteredLogs.length === 0 ? (
          <div className="h-full flex items-center justify-center text-gray-400">
            <div className="text-center">
              <p className="text-6xl mb-4">📜</p>
              <p className="text-lg font-medium">
                {bufferedLogs.length === 0 ? 'No logs yet' : 'No logs match filters'}
              </p>
              <p className="text-sm mt-2">
                {bufferedLogs.length === 0
                  ? 'Start LocalZure to see logs'
                  : 'Try adjusting your filters'}
              </p>
            </div>
          </div>
        ) : (
          <div
            ref={logsContainerRef}
            className="h-full overflow-y-auto px-6 py-4 space-y-1"
          >
            {filteredLogs.map((log, index) => (
              <div
                key={`${log.timestamp}-${index}`}
                className={`p-3 rounded-md border transition-colors hover:shadow-md ${getLevelColor(
                  log.level
                )}`}
              >
                <div className="flex items-start gap-3">
                  {/* Level Icon */}
                  <span className="text-lg">{getLevelIcon(log.level)}</span>

                  {/* Log Content */}
                  <div className="flex-1 min-w-0">
                    {/* Header Row */}
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded ${getLevelBadgeColor(
                          log.level
                        )}`}
                      >
                        {log.level}
                      </span>
                      <span className="text-xs font-medium text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
                        {log.module}
                      </span>
                      <span className="text-xs text-gray-500">
                        {formatTimestamp(log.timestamp)}
                      </span>
                      {log.correlation_id && (
                        <span className="text-xs text-gray-500 font-mono">
                          ID: {log.correlation_id.substring(0, 8)}...
                        </span>
                      )}
                    </div>

                    {/* Message */}
                    <p className="text-sm text-gray-900 font-mono break-words whitespace-pre-wrap">
                      {log.message}
                    </p>

                    {/* Context (expandable) */}
                    {log.context && Object.keys(log.context).length > 0 && (
                      <div className="mt-2">
                        <button
                          onClick={() =>
                            setExpandedLog(expandedLog === index ? null : index)
                          }
                          className="text-xs text-azure-600 hover:text-azure-700 font-medium"
                        >
                          {expandedLog === index ? '▼ Hide context' : '▶ Show context'}
                        </button>
                        {expandedLog === index && (
                          <pre className="mt-2 p-2 bg-white rounded text-xs font-mono overflow-x-auto">
                            {JSON.stringify(log.context, null, 2)}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Copy Button */}
                  <button
                    onClick={() => handleCopyLog(log)}
                    className="text-gray-400 hover:text-gray-600 text-sm"
                    title="Copy log to clipboard"
                  >
                    📋
                  </button>
                </div>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>

      {/* Footer with stats and legend */}
      <div className="bg-white border-t border-gray-200 px-6 py-3">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <div className="flex gap-4">
            <span>
              <span className="font-medium">Total:</span> {bufferedLogs.length}
            </span>
            <span>
              <span className="font-medium">Filtered:</span> {filteredLogs.length}
            </span>
            <span>
              <span className="font-medium">ERROR:</span>{' '}
              {bufferedLogs.filter(l => l.level === 'ERROR').length}
            </span>
            <span>
              <span className="font-medium">WARN:</span>{' '}
              {bufferedLogs.filter(l => l.level === 'WARN').length}
            </span>
          </div>
          <div className="flex gap-3">
            <span>❌ ERROR</span>
            <span>⚠️ WARN</span>
            <span>ℹ️ INFO</span>
            <span>🔍 DEBUG</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Logs;
