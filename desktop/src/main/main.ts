/**
 * LocalZure Desktop - Electron Main Process
 * 
 * Manages the Electron application lifecycle, window creation,
 * LocalZure subprocess, and IPC communication.
 */

import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } from 'electron';
import { spawn, spawnSync, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import Store from 'electron-store';
import axios from 'axios';

interface LocalZureConfig {
  port: number;
  host: string;
  logLevel: string;
  autoStart: boolean;
  pythonPath?: string;
}

interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'error';
  resourceCount?: number;
  endpoint?: string;
}

interface SystemStatus {
  status: 'running' | 'stopped' | 'starting' | 'stopping' | 'error';
  services: ServiceStatus[];
  version: string;
  uptime?: number;
  requestsPerSecond?: number;
  memoryUsage?: number;
}

class LocalZureManager {
  private process: ChildProcess | null = null;
  private config: LocalZureConfig;
  private store: Store<LocalZureConfig>;
  private startTime: number = 0;
  private isStarting: boolean = false;
  private mainWindow: BrowserWindow | null = null;

  constructor() {
    this.store = new Store<LocalZureConfig>({
      defaults: {
        port: 7071,
        host: '127.0.0.1',
        logLevel: 'INFO',
        autoStart: false,
      },
    });
    this.config = this.store.store;
  }

  setMainWindow(window: BrowserWindow): void {
    this.mainWindow = window;
  }

  async start(): Promise<void> {
    if (this.process || this.isStarting) {
      throw new Error('LocalZure is already running or starting');
    }

    this.isStarting = true;
    this.sendStatusUpdate('starting');

    try {
      const pythonPath = this.config.pythonPath || this.findPythonPath();
      const localzurePath = this.findLocalZurePath();

      console.log('[LocalZure] Starting LocalZure...');
      console.log('[LocalZure] Python:', pythonPath);
      console.log('[LocalZure] Path:', localzurePath);
      console.log('[LocalZure] Config:', this.config);

      // Start LocalZure subprocess
      this.process = spawn(pythonPath, [
        '-m',
        'localzure',
        'start',
        '--host',
        this.config.host,
        '--port',
        this.config.port.toString(),
        '--log-level',
        this.config.logLevel,
      ], {
        cwd: localzurePath,
        env: { ...process.env },
      });

      this.startTime = Date.now();

      // Handle stdout
      this.process.stdout?.on('data', (data: Buffer) => {
        const messages = data.toString().split('\n').filter(m => m.trim());
        messages.forEach(message => {
          console.log('[LocalZure]', message);
          const logEntry = this.parseLogMessage(message.trim(), 'INFO');
          this.mainWindow?.webContents.send('localzure:log', logEntry);
        });
      });

      // Handle stderr
      this.process.stderr?.on('data', (data: Buffer) => {
        const messages = data.toString().split('\n').filter(m => m.trim());
        messages.forEach(message => {
          console.error('[LocalZure Error]', message);
          const logEntry = this.parseLogMessage(message.trim(), 'ERROR');
          this.mainWindow?.webContents.send('localzure:log', logEntry);
        });
      });

      // Handle process exit
      this.process.on('exit', (code: number | null, signal: string | null) => {
        console.log(`[LocalZure] Process exited with code ${code}, signal ${signal}`);
        this.process = null;
        this.isStarting = false;
        this.sendStatusUpdate('stopped');
      });

      // Handle process errors
      this.process.on('error', (error: Error) => {
        console.error('[LocalZure] Process error:', error);
        this.process = null;
        this.isStarting = false;
        this.sendStatusUpdate('error');
        throw error;
      });

      // Wait for LocalZure to be ready
      await this.waitForReady();
      this.isStarting = false;
      this.sendStatusUpdate('running');

      console.log('[LocalZure] Started successfully');
    } catch (error) {
      this.isStarting = false;
      this.process = null;
      this.sendStatusUpdate('error');
      throw error;
    }
  }

  async stop(): Promise<void> {
    if (!this.process) {
      throw new Error('LocalZure is not running');
    }

    this.sendStatusUpdate('stopping');

    return new Promise<void>((resolve, reject) => {
      if (!this.process) {
        reject(new Error('Process is null'));
        return;
      }

      const timeout = setTimeout(() => {
        if (this.process) {
          console.log('[LocalZure] Force killing process');
          this.process.kill('SIGKILL');
        }
      }, 10000); // 10 second timeout

      this.process.once('exit', () => {
        clearTimeout(timeout);
        this.process = null;
        this.sendStatusUpdate('stopped');
        console.log('[LocalZure] Stopped successfully');
        resolve();
      });

      // Send SIGTERM for graceful shutdown
      this.process.kill('SIGTERM');
    });
  }

  async restart(): Promise<void> {
    if (this.process) {
      await this.stop();
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    await this.start();
  }

  isRunning(): boolean {
    return this.process !== null && !this.isStarting;
  }

  async getStatus(): Promise<SystemStatus> {
    // First check if backend is accessible (regardless of who started it)
    try {
      const response = await axios.get(
        `http://${this.config.host}:${this.config.port}/health`,
        { timeout: 2000 }
      );

      // Backend is running - calculate uptime if we started it, otherwise use 0
      const uptime = this.process ? Math.floor((Date.now() - this.startTime) / 1000) : 0;

      return {
        status: 'running',
        services: this.extractServices(response.data),
        version: response.data.version || '0.1.0',
        uptime,
        requestsPerSecond: 0,
        memoryUsage: process.memoryUsage().heapUsed / 1024 / 1024,
      };
    } catch (error) {
      // Backend not accessible - check our internal state
      if (this.process) {
        return {
          status: 'error',
          services: [],
          version: '0.1.0',
        };
      }

      if (this.isStarting) {
        return {
          status: 'starting',
          services: [],
          version: '0.1.0',
        };
      }

      // Backend not running
      return {
        status: 'stopped',
        services: [],
        version: '0.1.0',
      };
    }
  }

  getConfig(): LocalZureConfig {
    return { ...this.config };
  }

  updateConfig(config: Partial<LocalZureConfig>): void {
    this.config = { ...this.config, ...config };
    this.store.set(this.config);
  }

  private async waitForReady(maxAttempts: number = 30): Promise<void> {
    for (let i = 0; i < maxAttempts; i++) {
      try {
        const response = await axios.get(
          `http://${this.config.host}:${this.config.port}/health`,
          { timeout: 1000 }
        );
        if (response.status === 200) {
          return;
        }
      } catch (error) {
        // Not ready yet, continue waiting
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error('LocalZure failed to start within timeout period');
  }

  private findPythonPath(): string {
    // Try to find Python in common locations
    const candidates = [
      'python',
      'python3',
      'python3.10',
      'python3.11',
      'python3.12',
      path.join(process.cwd(), '..', '.venv', 'Scripts', 'python.exe'),
      path.join(process.cwd(), '..', '.venv', 'bin', 'python'),
    ];

    for (const candidate of candidates) {
      try {
        const result = spawnSync(candidate, ['--version']);
        if (result.status === 0) {
          return candidate;
        }
      } catch (error) {
        continue;
      }
    }

    throw new Error('Python not found. Please configure Python path in settings.');
  }

  private findLocalZurePath(): string {
    // Desktop app is in /desktop, LocalZure is in /localzure
    const candidates = [
      path.join(process.cwd(), '..'),
      path.join(app.getAppPath(), '..', '..'),
      process.cwd(),
    ];

    for (const candidate of candidates) {
      const localzureModule = path.join(candidate, 'localzure', '__init__.py');
      if (fs.existsSync(localzureModule)) {
        return candidate;
      }
    }

    throw new Error('LocalZure installation not found. Please ensure LocalZure is installed.');
  }

  private extractServices(healthData: any): ServiceStatus[] {
    const services: ServiceStatus[] = [];

    // Extract service information from health check response
    if (healthData.services) {
      for (const [name, data] of Object.entries(healthData.services as Record<string, any>)) {
        // Map service state to status
        let status: 'running' | 'stopped' | 'error' = 'stopped';
        
        // Check if data is an object with state/status fields, or just a string
        if (typeof data === 'object' && data !== null) {
          if (data.state === 'running' || data.status === 'healthy' || data.status === 'running') {
            status = 'running';
          } else if (data.state === 'error' || data.state === 'failed' || data.status === 'unhealthy' || data.status === 'error') {
            status = 'error';
          }
        } else if (typeof data === 'string') {
          // Handle case where service status is just a string
          if (data === 'running' || data === 'healthy') {
            status = 'running';
          } else if (data === 'error' || data === 'failed' || data === 'unhealthy') {
            status = 'error';
          }
        }

        services.push({
          name: this.formatServiceName(name),
          status,
          resourceCount: typeof data === 'object' ? data.resource_count : undefined,
          endpoint: typeof data === 'object' ? data.endpoint : undefined,
        });
      }
    } else {
      // Default services if health check doesn't provide details
      services.push(
        { name: 'Service Bus', status: 'running', resourceCount: 0 },
        { name: 'Key Vault', status: 'running', resourceCount: 0 },
        { name: 'Blob Storage', status: 'running', resourceCount: 0 }
      );
    }

    return services;
  }

  private formatServiceName(name: string): string {
    // Handle specific service names
    const nameMap: Record<string, string> = {
      'servicebus': 'Service Bus',
      'keyvault': 'Key Vault',
      'blobstorage': 'Blob Storage',
      'queuestorage': 'Queue Storage',
      'tablestorage': 'Table Storage',
      'cosmosdb': 'Cosmos DB'
    };
    
    const lowerName = name.toLowerCase();
    if (nameMap[lowerName]) {
      return nameMap[lowerName];
    }
    
    // Convert snake_case or lowercase to Title Case
    return name
      .split(/[_-]/)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }

  private sendStatusUpdate(
    status: 'running' | 'stopped' | 'starting' | 'stopping' | 'error'
  ): void {
    this.mainWindow?.webContents.send('localzure:status-changed', status);
  }

  private parseLogMessage(message: string, defaultLevel: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR'): any {
    // Try to parse structured log format: [TIMESTAMP] [LEVEL] [MODULE] message
    const structuredPattern = /^\[([^\]]+)\]\s*\[([^\]]+)\]\s*\[([^\]]+)\]\s*(.+)$/;
    const match = message.match(structuredPattern);

    if (match) {
      const [, timestamp, level, module, msg] = match;
      return {
        timestamp: timestamp || new Date().toISOString(),
        level: level.toUpperCase() as 'DEBUG' | 'INFO' | 'WARN' | 'ERROR',
        module: module || 'LocalZure',
        message: msg,
      };
    }

    // Try to parse Python logging format: LEVEL:module:message
    const pythonPattern = /^(DEBUG|INFO|WARNING|ERROR|CRITICAL):([^:]+):(.+)$/;
    const pythonMatch = message.match(pythonPattern);

    if (pythonMatch) {
      const [, level, module, msg] = pythonMatch;
      return {
        timestamp: new Date().toISOString(),
        level: level === 'WARNING' ? 'WARN' : level === 'CRITICAL' ? 'ERROR' : level as 'DEBUG' | 'INFO' | 'ERROR',
        module: module.trim(),
        message: msg.trim(),
      };
    }

    // Detect module from message content (common patterns)
    let module = 'LocalZure';
    let actualMessage = message;

    // Pattern: [module] message or module: message
    const modulePattern = /^(?:\[([^\]]+)\]|([^:]+):)\s*(.+)$/;
    const moduleMatch = message.match(modulePattern);
    
    if (moduleMatch) {
      module = (moduleMatch[1] || moduleMatch[2] || 'LocalZure').trim();
      actualMessage = moduleMatch[3].trim();
    }

    // Detect log level from message content
    let level = defaultLevel;
    const lowerMsg = message.toLowerCase();
    
    if (lowerMsg.includes('error') || lowerMsg.includes('failed') || lowerMsg.includes('exception')) {
      level = 'ERROR';
    } else if (lowerMsg.includes('warn') || lowerMsg.includes('warning')) {
      level = 'WARN';
    } else if (lowerMsg.includes('debug') || lowerMsg.includes('trace')) {
      level = 'DEBUG';
    }

    // Return parsed log entry
    return {
      timestamp: new Date().toISOString(),
      level,
      module,
      message: actualMessage,
    };
  }
}

// Application State
let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
const localzure = new LocalZureManager();

// Window Management
function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 600,
    title: 'LocalZure',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    show: false, // Show after ready-to-show event
  });

  localzure.setMainWindow(mainWindow);

  // Load the React app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.on('close', (event) => {
    if (process.platform === 'darwin') {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// System Tray
function createTray(): void {
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAKrSURBVFhH7ZbNaxNBGMZ3k6ZJ2yRN0zZtYqtFRBQVEQRBPHjw4MWbePTgP+BJ8OZJ8OhBEMGDBy+iR8WDiKgH0YMgKoqKH1UUtLa2abPZZHc/nHdmd5Nsm91N1IMPPOzszO/dmZ2dTRohhBBCCCGEEEIIIYQQQv4vhMMRzE5fwMxkHG/fZpFKJZFMJrCT+I3BYBCBQAChUAhRuwMHD+3H0aOHcOzYYRw/fhgXL15AuVz+A2HHdw88PDqG+fl5zM7OYmpqCvF4HMViEd1uF+iaxXq7Ddu2YVkW2u02Go0GarUayuUy0uk0nCMn8erVjNsGw/DAfwQzZ88bdXQBvq0WkM/ncflyAlevXjUEEokEcrmcsVqthnK5DLfbQ7ffg2VZaLVa2Gw2jalWq1hfX0ehUIDT6RgPpNNpDA8iGMa+fftMRa7cPdFqtWDbtilobm4OS0tLGB0dxcTEBEZGRhCNRs0u4l+apqHT6cDlcsF+9xHvUik8ePAAb968Qblc/gdhGIZhAKempnD69GlcunTJXLHrW+VyGalUyvx0OLwIBAKIxWIIh8PmZ8PJk+NwOBxm1tbW1pDJZNBoNFCr1dBsNk0gIZ/P+wK+ffv2dR+IxWLmzm63G6FQyLxw3W4XLpeLMFRV8zd1XUe/3zf3lqZpZo7qum72slar1YDxoK7rXgA6HA4bPxj1VCfQWwH6fr+ParXqBez1el6AXqVS8QJKpZIXkM1mvYB8Pu8F5HI5L0DxBfwCVFV1y36AUpbXAbpT0u22+T/hda1WM7PX6/V+AV7glYcKBK6J7I1GA7VazQuo1+smQHEDvoDNzc1fgOKVndTV9H4BB8WfQ59O9xegDINhCPAr4L9nYBgMQ4Bf7hjDMGx9+wW/AL2vHw+8VAAAAABJRU5ErkJggg=='
  );

  tray = new Tray(icon);
  updateTrayMenu('stopped');

  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
      }
    }
  });
}

function updateTrayMenu(status: 'running' | 'stopped' | 'starting' | 'stopping' | 'error'): void {
  if (!tray) return;

  const statusText = status.charAt(0).toUpperCase() + status.slice(1);
  const contextMenu = Menu.buildFromTemplate([
    {
      label: `LocalZure - ${statusText}`,
      enabled: false,
    },
    { type: 'separator' },
    {
      label: status === 'running' ? 'Stop LocalZure' : 'Start LocalZure',
      enabled: status === 'running' || status === 'stopped',
      click: async () => {
        try {
          if (status === 'running') {
            await localzure.stop();
          } else {
            await localzure.start();
          }
        } catch (error) {
          console.error('[Tray]', error);
        }
      },
    },
    { type: 'separator' },
    {
      label: 'Show Window',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        } else {
          createWindow();
        }
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: async () => {
        if (localzure.isRunning()) {
          await localzure.stop();
        }
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.setToolTip(`LocalZure - ${statusText}`);
}

// IPC Handlers
function setupIpcHandlers(): void {
  // Start LocalZure - Desktop app doesn't manage backend lifecycle
  // User must start LocalZure via CLI: localzure start
  ipcMain.handle('localzure:start', async () => {
    return { 
      success: false, 
      error: 'Please start LocalZure using the CLI command: localzure start' 
    };
  });

  // Stop LocalZure - Desktop app doesn't manage backend lifecycle
  ipcMain.handle('localzure:stop', async () => {
    return { 
      success: false, 
      error: 'Please stop LocalZure using the CLI command: localzure stop (or Ctrl+C in the terminal)' 
    };
  });

  // Restart LocalZure - Desktop app doesn't manage backend lifecycle
  ipcMain.handle('localzure:restart', async () => {
    return { 
      success: false, 
      error: 'Please restart LocalZure using the CLI: localzure stop && localzure start' 
    };
  });

  // Get status
  ipcMain.handle('localzure:get-status', async () => {
    try {
      const status = await localzure.getStatus();
      return status;
    } catch (error: any) {
      console.error('[IPC] Get status error:', error);
      return {
        status: 'error',
        services: [],
        version: '0.1.0',
      };
    }
  });

  // Get config
  ipcMain.handle('localzure:get-config', () => {
    return localzure.getConfig();
  });

  // Update config
  ipcMain.handle('localzure:update-config', (_event, config: Partial<LocalZureConfig>) => {
    try {
      localzure.updateConfig(config);
      return { success: true };
    } catch (error: any) {
      console.error('[IPC] Update config error:', error);
      return { success: false, error: error.message };
    }
  });

  // Blob Storage - List Containers
  ipcMain.handle('blob:list-containers', async () => {
    try {
      const config = localzure.getConfig();
      console.log('[IPC] Listing blob containers');
      const response = await axios.get(
        `http://${config.host}:${config.port}/blob/devstoreaccount1`,
        { timeout: 5000 }
      );
      
      console.log('[IPC] List containers response:', response.data);
      
      // Backend returns JSON: { Containers: [{ Name, Properties, Metadata }] }
      const containers = (response.data.Containers || []).map((c: any) => ({
        name: c.Name,
        properties: {
          lastModified: c.Properties?.['Last-Modified'] || new Date().toISOString(),
          etag: c.Properties?.Etag || '',
          leaseStatus: c.Properties?.LeaseStatus || 'unlocked',
          leaseState: c.Properties?.LeaseState || 'available',
          publicAccess: c.Properties?.PublicAccess,
        },
        metadata: c.Metadata || {},
      }));
      
      console.log('[IPC] Parsed containers:', containers);
      return { success: true, containers };
    } catch (error: any) {
      console.error('[IPC] List containers error:', error.response?.data || error.message);
      return { success: false, error: error.message, containers: [] };
    }
  });

  // Blob Storage - List Blobs
  ipcMain.handle('blob:list-blobs', async (_event, containerName: string, prefix?: string) => {
    try {
      const config = localzure.getConfig();
      let url = `http://${config.host}:${config.port}/blob/devstoreaccount1/${containerName}?restype=container&comp=list`;
      if (prefix) {
        url += `&prefix=${encodeURIComponent(prefix)}`;
      }
      
      const response = await axios.get(url, { timeout: 5000 });
      
      // Parse XML response to extract blobs
      const blobs = parseBlobListResponse(response.data);
      return { success: true, blobs };
    } catch (error: any) {
      console.error('[IPC] List blobs error:', error);
      return { success: false, error: error.message, blobs: [] };
    }
  });

  // Blob Storage - Create Container
  ipcMain.handle('blob:create-container', async (_event, containerName: string) => {
    try {
      const config = localzure.getConfig();
      console.log('[IPC] Creating blob container:', containerName);
      const response = await axios.put(
        `http://${config.host}:${config.port}/blob/devstoreaccount1/${containerName}?restype=container`,
        null,
        {
          timeout: 5000,
          headers: {
            'x-ms-version': '2021-08-06',
          },
        }
      );
      console.log('[IPC] Container created successfully, status:', response.status);
      return { success: true };
    } catch (error: any) {
      console.error('[IPC] Create container error:', error.response?.data || error.message);
      console.error('[IPC] Full error:', error);
      return { success: false, error: error.response?.data?.error?.message || error.message };
    }
  });

  // Blob Storage - Delete Container
  ipcMain.handle('blob:delete-container', async (_event, containerName: string) => {
    try {
      const config = localzure.getConfig();
      await axios.delete(
        `http://${config.host}:${config.port}/blob/devstoreaccount1/${containerName}?restype=container`,
        {
          timeout: 5000,
          headers: {
            'x-ms-version': '2021-08-06',
          },
        }
      );
      return { success: true };
    } catch (error: any) {
      console.error('[IPC] Delete container error:', error);
      return { success: false, error: error.message };
    }
  });

  // Blob Storage - Upload Blob
  ipcMain.handle('blob:upload-blob', async (_event, containerName: string, blobName: string, data: string, contentType: string) => {
    try {
      const config = localzure.getConfig();
      const binaryData = Buffer.from(data, 'base64');
      
      await axios.put(
        `http://${config.host}:${config.port}/blob/devstoreaccount1/${containerName}/${encodeURIComponent(blobName)}`,
        binaryData,
        {
          timeout: 30000,
          headers: {
            'x-ms-version': '2021-08-06',
            'x-ms-blob-type': 'BlockBlob',
            'Content-Type': contentType || 'application/octet-stream',
            'Content-Length': binaryData.length.toString(),
          },
        }
      );
      return { success: true };
    } catch (error: any) {
      console.error('[IPC] Upload blob error:', error);
      return { success: false, error: error.message };
    }
  });

  // Blob Storage - Download Blob
  ipcMain.handle('blob:download-blob', async (_event, containerName: string, blobName: string) => {
    try {
      const config = localzure.getConfig();
      const response = await axios.get(
        `http://${config.host}:${config.port}/blob/devstoreaccount1/${containerName}/${encodeURIComponent(blobName)}`,
        {
          timeout: 30000,
          responseType: 'arraybuffer',
          headers: {
            'x-ms-version': '2021-08-06',
          },
        }
      );
      
      const base64Data = Buffer.from(response.data).toString('base64');
      return { success: true, data: base64Data };
    } catch (error: any) {
      console.error('[IPC] Download blob error:', error);
      return { success: false, error: error.message };
    }
  });

  // Blob Storage - Delete Blob
  ipcMain.handle('blob:delete-blob', async (_event, containerName: string, blobName: string) => {
    try {
      const config = localzure.getConfig();
      await axios.delete(
        `http://${config.host}:${config.port}/blob/devstoreaccount1/${containerName}/${encodeURIComponent(blobName)}`,
        {
          timeout: 5000,
          headers: {
            'x-ms-version': '2021-08-06',
          },
        }
      );
      return { success: true };
    } catch (error: any) {
      console.error('[IPC] Delete blob error:', error);
      return { success: false, error: error.message };
    }
  });

  // =========================================================================
  // Service Bus IPC Handlers
  // =========================================================================

  // Service Bus - List Queues
  ipcMain.handle('servicebus:list-queues', async () => {
    try {
      const config = localzure.getConfig();
      const response = await axios.get(
        `http://${config.host}:${config.port}/servicebus/localnamespace/$Resources/Queues`,
        {
          timeout: 5000,
        }
      );
      
      // Backend returns XML ATOM feed - parse it
      const xmlData = response.data;
      const titleMatches = xmlData.matchAll(/<title type="text">(.+?)<\/title>/g);
      const queues = [];
      
      // Skip first title (feed title "Queues")
      let isFirst = true;
      for (const match of titleMatches) {
        if (isFirst) {
          isFirst = false;
          continue;
        }
        queues.push({
          name: match[1],
          messageCount: 0,
          activeMessageCount: 0,
          deadLetterMessageCount: 0,
          maxSizeInMegabytes: 1024,
          requiresSession: false,
          status: 'Active',
        });
      }
      
      return { success: true, queues };
    } catch (error: any) {
      console.error('[IPC] List queues error:', error);
      return { success: true, queues: [] };
    }
  });

  // Service Bus - Create Queue
  ipcMain.handle('servicebus:create-queue', async (_event, queueName: string) => {
    try {
      const config = localzure.getConfig();
      console.log('[IPC] Creating Service Bus queue:', queueName);
      await axios.put(
        `http://${config.host}:${config.port}/servicebus/localnamespace/${queueName}`,
        '',
        {
          timeout: 5000,
          headers: {
            'Content-Type': 'application/atom+xml',
          },
        }
      );
      console.log('[IPC] Queue created successfully');
      return { success: true };
    } catch (error: any) {
      console.error('[IPC] Create queue error:', error.response?.data || error.message);
      return { success: false, error: error.response?.data?.error?.message || error.message };
    }
  });

  // Service Bus - Create Topic
  ipcMain.handle('servicebus:create-topic', async (_event, topicName: string) => {
    try {
      const config = localzure.getConfig();
      console.log('[IPC] Creating Service Bus topic:', topicName);
      await axios.put(
        `http://${config.host}:${config.port}/servicebus/localnamespace/topics/${topicName}`,
        '',
        {
          timeout: 5000,
          headers: {
            'Content-Type': 'application/atom+xml',
          },
        }
      );
      console.log('[IPC] Topic created successfully');
      return { success: true };
    } catch (error: any) {
      console.error('[IPC] Create topic error:', error.response?.data || error.message);
      return { success: false, error: error.response?.data?.error?.message || error.message };
    }
  });

  // Service Bus - List Topics
  ipcMain.handle('servicebus:list-topics', async () => {
    try {
      const config = localzure.getConfig();
      const response = await axios.get(
        `http://${config.host}:${config.port}/servicebus/localnamespace/topics`,
        {
          timeout: 5000,
        }
      );
      
      // Backend returns XML ATOM feed - parse it
      const xmlData = response.data;
      const titleMatches = xmlData.matchAll(/<title type="text">(.+?)<\/title>/g);
      const topics = [];
      
      // Skip first title (feed title "Topics")
      let isFirst = true;
      for (const match of titleMatches) {
        if (isFirst) {
          isFirst = false;
          continue;
        }
        topics.push({
          name: match[1],
          subscriptionCount: 0,
          maxSizeInMegabytes: 1024,
          requiresSession: false,
          supportOrdering: false,
          status: 'Active',
        });
      }
      
      return { success: true, topics };
    } catch (error: any) {
      console.error('[IPC] List topics error:', error);
      return { success: true, topics: [] };
    }
  });

  // Service Bus - List Subscriptions
  ipcMain.handle('servicebus:list-subscriptions', async (_event, topicName: string) => {
    try {
      const config = localzure.getConfig();
      const response = await axios.get(
        `http://${config.host}:${config.port}/servicebus/localnamespace/topics/${topicName}/subscriptions`,
        {
          timeout: 5000,
        }
      );
      
      // Backend returns XML ATOM feed - parse it
      const xmlData = response.data;
      const titleMatches = xmlData.matchAll(/<title type="text">(.+?)<\/title>/g);
      const subscriptions = [];
      
      // Skip first title (feed title "Subscriptions")
      let isFirst = true;
      for (const match of titleMatches) {
        if (isFirst) {
          isFirst = false;
          continue;
        }
        subscriptions.push({
          name: match[1],
          topicName: topicName,
          messageCount: 0,
          activeMessageCount: 0,
          deadLetterMessageCount: 0,
          status: 'Active',
        });
      }
      
      return { success: true, subscriptions };
    } catch (error: any) {
      console.error('[IPC] List subscriptions error:', error);
      return { success: true, subscriptions: [] };
    }
  });

  // Service Bus - Peek Messages (Queue)
  ipcMain.handle('servicebus:peek-messages', async (_event, queueName: string, maxMessages: number = 32) => {
    try {
      const config = localzure.getConfig();
      const response = await axios.post(
        `http://${config.host}:${config.port}/servicebus/localnamespace/${queueName}/messages/head`,
        {},
        {
          timeout: 5000,
          headers: {
            'Content-Type': 'application/atom+xml',
          },
          params: {
            maxMessages,
          },
        }
      );
      
      const messages = response.data?.messages || [];
      return { success: true, messages };
    } catch (error: any) {
      console.error('[IPC] Peek messages error:', error);
      return { success: true, messages: [] };
    }
  });

  // Service Bus - Peek Subscription Messages
  ipcMain.handle('servicebus:peek-subscription-messages', async (_event, topicName: string, subscriptionName: string, maxMessages: number = 32) => {
    try {
      const config = localzure.getConfig();
      const response = await axios.post(
        `http://${config.host}:${config.port}/servicebus/localnamespace/${topicName}/Subscriptions/${subscriptionName}/messages/head`,
        {},
        {
          timeout: 5000,
          headers: {
            'Content-Type': 'application/atom+xml',
          },
          params: {
            maxMessages,
          },
        }
      );
      
      const messages = response.data?.messages || [];
      return { success: true, messages };
    } catch (error: any) {
      console.error('[IPC] Peek subscription messages error:', error);
      return { success: true, messages: [] };
    }
  });

  // Service Bus - Peek Dead-letter Messages (Queue)
  ipcMain.handle('servicebus:peek-queue-deadletter', async (_event, queueName: string, maxMessages: number = 32) => {
    try {
      const config = localzure.getConfig();
      const response = await axios.post(
        `http://${config.host}:${config.port}/servicebus/localnamespace/${queueName}/$DeadLetterQueue/messages/head`,
        {},
        {
          timeout: 5000,
          headers: {
            'Content-Type': 'application/atom+xml',
          },
          params: {
            maxMessages,
          },
        }
      );
      
      const messages = response.data?.messages || [];
      return { success: true, messages };
    } catch (error: any) {
      console.error('[IPC] Peek queue dead-letter messages error:', error);
      return { success: true, messages: [] };
    }
  });

  // Service Bus - Peek Dead-letter Messages (Subscription)
  ipcMain.handle('servicebus:peek-deadletter', async (_event, topicName: string, subscriptionName: string, maxMessages: number = 32) => {
    try {
      const config = localzure.getConfig();
      const response = await axios.post(
        `http://${config.host}:${config.port}/servicebus/localnamespace/${topicName}/Subscriptions/${subscriptionName}/$DeadLetterQueue/messages/head`,
        {},
        {
          timeout: 5000,
          headers: {
            'Content-Type': 'application/atom+xml',
          },
          params: {
            maxMessages,
          },
        }
      );
      
      const messages = response.data?.messages || [];
      return { success: true, messages };
    } catch (error: any) {
      console.error('[IPC] Peek dead-letter messages error:', error);
      return { success: true, messages: [] };
    }
  });

  // Service Bus - Send Message
  ipcMain.handle('servicebus:send-message', async (_event, destination: string, messageData: any) => {
    try {
      const config = localzure.getConfig();
      
      // Build message payload
      const message = {
        body: messageData.body,
        contentType: messageData.contentType || 'application/json',
        label: messageData.label,
        sessionId: messageData.sessionId,
        correlationId: messageData.correlationId,
        userProperties: messageData.properties || {},
      };
      
      const response = await axios.post(
        `http://${config.host}:${config.port}/servicebus/localnamespace/${destination}/messages`,
        message,
        {
          timeout: 5000,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
      
      return { success: true, messageId: response.data?.messageId };
    } catch (error: any) {
      console.error('[IPC] Send message error:', error);
      return { success: false, error: error.message };
    }
  });
}

// Helper function to parse blob list XML response
function parseBlobListResponse(xmlData: string): any[] {
  const blobs: any[] = [];
  
  // Simple XML parsing for blobs
  const blobRegex = /<Blob>[\s\S]*?<Name>(.*?)<\/Name>[\s\S]*?<\/Blob>/g;
  const propertyRegex = /<Properties>([\s\S]*?)<\/Properties>/;
  
  let match;
  while ((match = blobRegex.exec(xmlData)) !== null) {
    const blobXml = match[0];
    const name = match[1];
    
    const propsMatch = propertyRegex.exec(blobXml);
    const propsXml = propsMatch ? propsMatch[1] : '';
    
    blobs.push({
      name,
      properties: {
        contentLength: parseInt(extractXmlValue(propsXml, 'Content-Length') || '0', 10),
        contentType: extractXmlValue(propsXml, 'Content-Type') || 'application/octet-stream',
        lastModified: extractXmlValue(propsXml, 'Last-Modified') || new Date().toISOString(),
        etag: extractXmlValue(propsXml, 'Etag') || '',
        blobType: extractXmlValue(propsXml, 'BlobType') || 'BlockBlob',
        leaseStatus: extractXmlValue(propsXml, 'LeaseStatus'),
        leaseState: extractXmlValue(propsXml, 'LeaseState'),
      },
      metadata: {},
      snapshot: extractXmlValue(blobXml, 'Snapshot'),
    });
  }
  
  return blobs;
}

// Helper function to extract value from XML
function extractXmlValue(xml: string, tagName: string): string | undefined {
  const regex = new RegExp(`<${tagName}>(.*?)<\/${tagName}>`, 'i');
  const match = regex.exec(xml);
  return match ? match[1] : undefined;
}

// ============================================================================
// Additional IPC Handlers for Key Vault, Queue Storage, Table Storage, Cosmos DB
// ============================================================================

function setupAdditionalIpcHandlers(): void {
  // Helper to get base URL dynamically
  const getBaseUrl = () => {
    const config = localzure.getConfig();
    return `http://${config.host}:${config.port}`;
  };

  // -------------------------------------------------------------------------
  // Key Vault Handlers
  // -------------------------------------------------------------------------
  
  ipcMain.handle('listSecrets', async () => {
    try {
      const response = await axios.get(`${getBaseUrl()}/localvault/secrets?api-version=7.3`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] List secrets error:', error.message);
      return { value: [] };
    }
  });

  ipcMain.handle('getSecret', async (_event, name: string) => {
    try {
      const response = await axios.get(`${getBaseUrl()}/localvault/secrets/${name}?api-version=7.3`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Get secret error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('createSecret', async (_event, name: string, value: string, contentType?: string) => {
    try {
      const response = await axios.put(`${getBaseUrl()}/localvault/secrets/${name}?api-version=7.3`, 
        { value, contentType },
        { timeout: 5000 }
      );
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Create secret error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('deleteSecret', async (_event, name: string) => {
    try {
      const response = await axios.delete(`${getBaseUrl()}/localvault/secrets/${name}?api-version=7.3`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Delete secret error:', error.message);
      throw error;
    }
  });

  // -------------------------------------------------------------------------
  // Queue Storage Handlers
  // -------------------------------------------------------------------------
  
  ipcMain.handle('listQueues', async () => {
    try {
      const response = await axios.get(`${getBaseUrl()}/queue/devstoreaccount1?comp=list`, { timeout: 5000 });
      // Parse XML response to extract queue names
      const xmlData = response.data as string;
      const queueMatches = xmlData.matchAll(/<Name>(.*?)<\/Name>/g);
      const queues = Array.from(queueMatches).map(match => ({
        name: match[1]
      }));
      return { queues };
    } catch (error: any) {
      console.error('[IPC] List queues error:', error.message);
      return { queues: [] };
    }
  });

  ipcMain.handle('createQueue', async (_event, queueName: string) => {
    try {
      const response = await axios.put(`${getBaseUrl()}/queue/devstoreaccount1/${queueName}`, {}, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Create queue error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('deleteQueue', async (_event, queueName: string) => {
    try {
      const response = await axios.delete(`${getBaseUrl()}/queue/devstoreaccount1/${queueName}`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Delete queue error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('peekQueueMessages', async (_event, queueName: string, numMessages: number = 32) => {
    try {
      const response = await axios.get(`${getBaseUrl()}/queue/devstoreaccount1/${queueName}/messages`, {
        params: { numofmessages: numMessages, peekonly: true },
        timeout: 5000
      });
      // Parse XML response to extract messages
      const xmlData = response.data as string;
      const messageMatches = xmlData.matchAll(/<QueueMessage>(.*?)<\/QueueMessage>/gs);
      const messages = Array.from(messageMatches).map(match => {
        const msgXml = match[1];
        const idMatch = msgXml.match(/<MessageId>(.*?)<\/MessageId>/);
        const textMatch = msgXml.match(/<MessageText>(.*?)<\/MessageText>/);
        const insertionMatch = msgXml.match(/<InsertionTime>(.*?)<\/InsertionTime>/);
        const expirationMatch = msgXml.match(/<ExpirationTime>(.*?)<\/ExpirationTime>/);
        const dequeueMatch = msgXml.match(/<DequeueCount>(.*?)<\/DequeueCount>/);
        
        return {
          id: idMatch ? idMatch[1] : '',
          content: textMatch ? textMatch[1] : '',
          insertionTime: insertionMatch ? insertionMatch[1] : '',
          expirationTime: expirationMatch ? expirationMatch[1] : '',
          dequeueCount: dequeueMatch ? parseInt(dequeueMatch[1]) : 0
        };
      });
      return { messages };
    } catch (error: any) {
      console.error('[IPC] Peek queue messages error:', error.message);
      return { messages: [] };
    }
  });

  ipcMain.handle('sendQueueMessage', async (_event, queueName: string, content: string) => {
    try {
      // Azure Queue Storage expects XML format
      const xmlBody = `<?xml version="1.0" encoding="utf-8"?><QueueMessage><MessageText>${content}</MessageText></QueueMessage>`;
      const response = await axios.post(
        `${getBaseUrl()}/queue/devstoreaccount1/${queueName}/messages`,
        xmlBody,
        { 
          timeout: 5000,
          headers: { 'Content-Type': 'application/xml' }
        }
      );
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Send queue message error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('deleteQueueMessage', async (_event, queueName: string, messageId: string, popReceipt: string) => {
    try {
      const response = await axios.delete(`${getBaseUrl()}/queue/devstoreaccount1/${queueName}/messages/${messageId}`, {
        params: { popreceipt: popReceipt },
        timeout: 5000
      });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Delete queue message error:', error.message);
      throw error;
    }
  });

  // -------------------------------------------------------------------------
  // Table Storage Handlers
  // -------------------------------------------------------------------------
  
  ipcMain.handle('listTables', async () => {
    try {
      const response = await axios.get(`${getBaseUrl()}/table/devstoreaccount1/Tables`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] List tables error:', error.message);
      return { value: [] };
    }
  });

  ipcMain.handle('createTable', async (_event, tableName: string) => {
    try {
      const response = await axios.post(`${getBaseUrl()}/table/devstoreaccount1/Tables`, 
        { TableName: tableName },
        { timeout: 5000 }
      );
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Create table error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('deleteTable', async (_event, tableName: string) => {
    try {
      const response = await axios.delete(`${getBaseUrl()}/table/devstoreaccount1/Tables('${tableName}')`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Delete table error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('queryTableEntities', async (_event, tableName: string) => {
    try {
      const response = await axios.get(`${getBaseUrl()}/table/devstoreaccount1/${tableName}()`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Query table entities error:', error.message);
      return { value: [] };
    }
  });

  ipcMain.handle('insertTableEntity', async (_event, tableName: string, entity: any) => {
    try {
      const response = await axios.post(`${getBaseUrl()}/table/devstoreaccount1/${tableName}`, entity, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Insert table entity error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('deleteTableEntity', async (_event, tableName: string, partitionKey: string, rowKey: string) => {
    try {
      const response = await axios.delete(
        `${getBaseUrl()}/table/devstoreaccount1/${tableName}(PartitionKey='${partitionKey}',RowKey='${rowKey}')`,
        { timeout: 5000 }
      );
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Delete table entity error:', error.message);
      throw error;
    }
  });

  // -------------------------------------------------------------------------
  // Cosmos DB Handlers
  // -------------------------------------------------------------------------
  
  ipcMain.handle('listCosmosDatabases', async () => {
    try {
      const response = await axios.get(`${getBaseUrl()}/cosmosdb/dbs`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] List Cosmos databases error:', error.message);
      return { Databases: [] };
    }
  });

  ipcMain.handle('createCosmosDatabase', async (_event, id: string) => {
    try {
      const response = await axios.post(`${getBaseUrl()}/cosmosdb/dbs`, { id }, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Create Cosmos database error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('deleteCosmosDatabase', async (_event, databaseId: string) => {
    try {
      const response = await axios.delete(`${getBaseUrl()}/cosmosdb/dbs/${databaseId}`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Delete Cosmos database error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('listCosmosContainers', async (_event, databaseId: string) => {
    try {
      const response = await axios.get(`${getBaseUrl()}/cosmosdb/dbs/${databaseId}/colls`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] List Cosmos containers error:', error.message);
      return { DocumentCollections: [] };
    }
  });

  ipcMain.handle('createCosmosContainer', async (_event, databaseId: string, containerId: string, partitionKey: string) => {
    try {
      const response = await axios.post(`${getBaseUrl()}/cosmosdb/dbs/${databaseId}/colls`, 
        { 
          id: containerId,
          partitionKey: {
            paths: [partitionKey],
            kind: 'Hash'
          }
        },
        { timeout: 5000 }
      );
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Create Cosmos container error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('deleteCosmosContainer', async (_event, databaseId: string, containerId: string) => {
    try {
      const response = await axios.delete(`${getBaseUrl()}/cosmosdb/dbs/${databaseId}/colls/${containerId}`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Delete Cosmos container error:', error.message);
      throw error;
    }
  });

  ipcMain.handle('queryCosmosDocuments', async (_event, databaseId: string, containerId: string) => {
    try {
      const response = await axios.get(`${getBaseUrl()}/cosmosdb/dbs/${databaseId}/colls/${containerId}/docs`, { timeout: 5000 });
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Query Cosmos documents error:', error.message);
      return { Documents: [] };
    }
  });

  ipcMain.handle('createCosmosDocument', async (_event, databaseId: string, containerId: string, document: any) => {
    try {
      console.log('[IPC] Creating Cosmos document:', { databaseId, containerId, document });
      
      // Get the container to find the partition key path
      const containerResponse = await axios.get(`${getBaseUrl()}/cosmosdb/dbs/${databaseId}/colls/${containerId}`, { timeout: 5000 });
      const container = containerResponse.data;
      
      console.log('[IPC] Container info:', container);
      
      // Extract partition key value from document
      let partitionKeyValue = document.id; // default to id
      if (container.partitionKey?.paths?.[0]) {
        const pkPath = container.partitionKey.paths[0].substring(1); // remove leading '/'
        partitionKeyValue = document[pkPath] || document.id;
      }
      
      console.log('[IPC] Partition key value:', partitionKeyValue);
      
      const response = await axios.post(
        `${getBaseUrl()}/cosmosdb/dbs/${databaseId}/colls/${containerId}/docs`, 
        document,
        { 
          timeout: 5000,
          headers: {
            'x-ms-documentdb-partitionkey': JSON.stringify([partitionKeyValue])
          }
        }
      );
      
      console.log('[IPC] Document created successfully');
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Create Cosmos document error:', error.message);
      console.error('[IPC] Full error:', error);
      throw error;
    }
  });

  ipcMain.handle('deleteCosmosDocument', async (_event, databaseId: string, containerId: string, documentId: string, partitionKeyValue?: string) => {
    try {
      // If partition key not provided, fetch the document first
      let pkValue = partitionKeyValue;
      if (!pkValue) {
        // Get the container to find partition key path
        const containerResponse = await axios.get(`${getBaseUrl()}/cosmosdb/dbs/${databaseId}/colls/${containerId}`, { timeout: 5000 });
        const container = containerResponse.data;
        
        // Get the document to extract partition key value
        const docResponse = await axios.get(`${getBaseUrl()}/cosmosdb/dbs/${databaseId}/colls/${containerId}/docs/${documentId}`, {
          timeout: 5000,
          headers: { 'x-ms-documentdb-partitionkey': JSON.stringify([documentId]) }
        });
        const doc = docResponse.data;
        
        // Extract partition key value
        if (container.partitionKey?.paths?.[0]) {
          const pkPath = container.partitionKey.paths[0].substring(1);
          pkValue = doc[pkPath] || documentId;
        } else {
          pkValue = documentId;
        }
      }
      
      const response = await axios.delete(
        `${getBaseUrl()}/cosmosdb/dbs/${databaseId}/colls/${containerId}/docs/${documentId}`,
        { 
          timeout: 5000,
          headers: {
            'x-ms-documentdb-partitionkey': JSON.stringify([pkValue])
          }
        }
      );
      return response.data;
    } catch (error: any) {
      console.error('[IPC] Delete Cosmos document error:', error.message);
      throw error;
    }
  });
}

// App Lifecycle
app.on('ready', () => {
  createWindow();
  createTray();
  setupIpcHandlers();
  setupAdditionalIpcHandlers();

  // Backend is started by the start script before the desktop app launches
  // The desktop app can still control it via Start/Stop/Restart buttons
  console.log('[App] Desktop app ready. Backend should already be running.');
});

app.on('window-all-closed', () => {
  // Keep app running in tray on Windows/Linux
  if (process.platform !== 'darwin') {
    // Don't quit immediately
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

app.on('before-quit', async (event) => {
  if (localzure.isRunning()) {
    event.preventDefault();
    try {
      await localzure.stop();
      app.quit();
    } catch (error) {
      console.error('[App] Failed to stop LocalZure:', error);
      app.quit();
    }
  }
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('[App] Uncaught exception:', error);
});

process.on('unhandledRejection', (reason) => {
  console.error('[App] Unhandled rejection:', reason);
});
