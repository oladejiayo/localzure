import { useState, useEffect, useCallback } from 'react';
import Dashboard from './components/Dashboard';
import Sidebar from './components/Sidebar';
import Settings from './components/Settings';
import Logs from './components/Logs';
import BlobStorage from './components/BlobStorage';
import ServiceBus from './components/ServiceBus';
import KeyVault from './components/KeyVault';
import QueueStorage from './components/QueueStorage';
import TableStorage from './components/TableStorage';
import CosmosDB from './components/CosmosDB';

type View = 'dashboard' | 'blob' | 'servicebus' | 'keyvault' | 'queue' | 'table' | 'cosmos' | 'settings' | 'logs';

interface SystemStatus {
  status: 'running' | 'stopped' | 'starting' | 'stopping' | 'error';
  services: ServiceStatus[];
  version: string;
  uptime?: number;
  requestsPerSecond?: number;
  memoryUsage?: number;
}

interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'error';
  resourceCount?: number;
  endpoint?: string;
}

interface LogEntry {
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
  module: string;
  message: string;
  correlation_id?: string;
  context?: Record<string, any>;
}

function App() {
  const [currentView, setCurrentView] = useState<View>('dashboard');
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    status: 'stopped',
    services: [],
    version: '0.1.0',
  });
  const [logs, setLogs] = useState<LogEntry[]>([]);

  // Fetch status periodically
  const fetchStatus = useCallback(async () => {
    try {
      const status = await window.localzureAPI.getStatus();
      setSystemStatus(status);
    } catch (error) {
      console.error('Failed to fetch status:', error);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    fetchStatus();

    // Poll every 2 seconds
    const interval = setInterval(fetchStatus, 2000);

    // Listen for status changes
    const unsubscribe = window.localzureAPI.onStatusChanged((status) => {
      console.log('Status changed:', status);
      fetchStatus();
    });

    // Listen for logs
    const unsubscribeLogs = window.localzureAPI.onLog((log: LogEntry) => {
      setLogs((prev) => [...prev.slice(-9999), log]); // Keep last 10,000 logs
    });

    return () => {
      clearInterval(interval);
      unsubscribe();
      unsubscribeLogs();
    };
  }, [fetchStatus]);

  const handleStart = async () => {
    try {
      const result = await window.localzureAPI.start();
      if (!result.success) {
        console.error('Failed to start:', result.error);
        alert(`Failed to start LocalZure: ${result.error}`);
      }
    } catch (error) {
      console.error('Start error:', error);
      alert('Failed to start LocalZure');
    }
  };

  const handleStop = async () => {
    try {
      const result = await window.localzureAPI.stop();
      if (!result.success) {
        console.error('Failed to stop:', result.error);
        alert(`Failed to stop LocalZure: ${result.error}`);
      }
    } catch (error) {
      console.error('Stop error:', error);
      alert('Failed to stop LocalZure');
    }
  };

  const handleRestart = async () => {
    try {
      const result = await window.localzureAPI.restart();
      if (!result.success) {
        console.error('Failed to restart:', result.error);
        alert(`Failed to restart LocalZure: ${result.error}`);
      }
    } catch (error) {
      console.error('Restart error:', error);
      alert('Failed to restart LocalZure');
    }
  };

  const handleClearLogs = () => {
    setLogs([]);
  };

  const handleNavigateToService = (serviceName: string) => {
    // Map service names to view names
    const serviceViewMap: Record<string, View> = {
      'Service Bus': 'servicebus',
      'Blob Storage': 'blob',
      'Key Vault': 'keyvault',
      'Queue Storage': 'queue',
      'Table Storage': 'table',
      'Cosmos DB': 'cosmos'
    };
    
    const targetView = serviceViewMap[serviceName] || 'dashboard';
    setCurrentView(targetView);
  };

  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar currentView={currentView} onViewChange={setCurrentView} />
      
      <main className="flex-1 overflow-y-auto">
        {currentView === 'dashboard' && (
          <Dashboard
            status={systemStatus}
            onStart={handleStart}
            onStop={handleStop}
            onRestart={handleRestart}
            onNavigateToService={handleNavigateToService}
          />
        )}
        
        {currentView === 'blob' && <BlobStorage onRefresh={fetchStatus} />}
        
        {currentView === 'servicebus' && <ServiceBus onRefresh={fetchStatus} />}
        
        {currentView === 'keyvault' && <KeyVault onRefresh={fetchStatus} />}
        
        {currentView === 'queue' && <QueueStorage onRefresh={fetchStatus} />}
        
        {currentView === 'table' && <TableStorage onRefresh={fetchStatus} />}
        
        {currentView === 'cosmos' && <CosmosDB onRefresh={fetchStatus} />}
        
        {currentView === 'logs' && <Logs logs={logs} onClearLogs={handleClearLogs} />}
        
        {currentView === 'settings' && <Settings />}
      </main>
    </div>
  );
}

export default App;
