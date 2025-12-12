# LocalZure Desktop Application

## Overview

LocalZure Desktop is an Electron-based desktop application that provides a graphical user interface for managing and monitoring the LocalZure Azure emulator. It offers real-time status monitoring, service management, and configuration options through an intuitive dashboard.

## Features

### ✅ Implemented Features

#### Core Features (DESKTOP-001)
- **Application Shell**: Modern Electron + React + TypeScript application
- **Dashboard**: Real-time system status and service monitoring
- **Service Cards**: Visual representation of all running Azure services
- **Start/Stop/Restart Controls**: Manage LocalZure lifecycle from UI
- **System Tray Integration**: Quick access via system tray icon with status indicators
- **Settings Panel**: Configure LocalZure host, port, log level, and auto-start
- **Live Logs**: Real-time log streaming with filtering
- **Resource Monitoring**: Track uptime, requests/sec, and memory usage
- **Responsive Design**: Beautiful Tailwind CSS styling

#### Blob Storage Explorer (DESKTOP-002) 🆕
- **Three-Panel Layout**: Containers (left), Blobs (right), Properties (bottom)
- **Container Management**: List, create, and delete containers with validation
- **Blob Operations**: Upload (multi-file), download, and delete blobs
- **Search & Filter**: Name prefix filtering with pagination (50 items/page)
- **Bulk Operations**: Select multiple blobs for batch deletion
- **Properties Inspector**: View blob metadata, ETag, lease status, and more
- **Progress Indicators**: Visual feedback for upload/download operations
- **Confirmation Dialogs**: Safe deletion with user confirmation

## Architecture

```
desktop/
├── src/
│   ├── main/              # Electron main process
│   │   ├── main.ts        # Application entry point, subprocess management
│   │   └── preload.ts     # IPC bridge (contextBridge)
│   └── renderer/          # React frontend
│       ├── components/
│       │   ├── Dashboard.tsx
│       │   ├── Sidebar.tsx
│       │   ├── Settings.tsx
│       │   └── Logs.tsx
│       ├── App.tsx
│       ├── main.tsx
│       └── styles.css
├── dist/                  # Compiled output
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## Technology Stack

- **Electron 28**: Desktop application framework
- **React 18**: UI framework
- **TypeScript 5**: Type-safe development
- **Vite 5**: Fast build tool and dev server
- **Tailwind CSS 3**: Utility-first CSS framework
- **electron-store**: Persistent configuration storage
- **axios**: HTTP client for health checks

## Installation

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+ with LocalZure installed
- LocalZure parent directory structure:
  ```
  /project-root
    /localzure       # Python package
    /desktop         # This application
  ```

### Setup

```bash
cd desktop
npm install
```

## Development

### Run in Development Mode

```bash
# Terminal 1: Start Vite dev server (React)
npm run dev:renderer

# Terminal 2: Compile and start Electron
npm run dev:main
npm run start:dev
```

Or use the combined command:

```bash
npm run dev
```

### Build for Production

```bash
npm run build
```

### Run Tests

```bash
npm test
npm run test:coverage
```

### Linting

```bash
npm run lint
npm run lint:fix
```

## Usage

### Starting the Application

1. Launch the LocalZure Desktop application
2. The dashboard will show the current status (stopped by default)
3. Click the "▶️ Start" button to start LocalZure
4. Monitor services in real-time

### System Tray

The application creates a system tray icon with:
- **Green**: LocalZure is running
- **Red**: LocalZure is stopped
- **Yellow**: LocalZure is starting/stopping

Right-click the tray icon to:
- Start/Stop LocalZure
- Show/Hide window
- Quit application

### Configuration

Navigate to Settings to configure:
- **Host**: Bind address (default: 127.0.0.1)
- **Port**: Listen port (default: 7071)
- **Log Level**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Auto-start**: Start LocalZure when application launches
- **Python Path**: Custom Python executable path (optional)

## IPC API

The renderer process communicates with the main process via these IPC methods:

### Methods

```typescript
window.localzureAPI.start(): Promise<{ success: boolean; error?: string }>
window.localzureAPI.stop(): Promise<{ success: boolean; error?: string }>
window.localzureAPI.restart(): Promise<{ success: boolean; error?: string }>
window.localzureAPI.getStatus(): Promise<SystemStatus>
window.localzureAPI.getConfig(): Promise<Config>
window.localzureAPI.updateConfig(config): Promise<{ success: boolean }>
```

### Events

```typescript
window.localzureAPI.onStatusChanged((status) => { ... }): UnsubscribeFn
window.localzureAPI.onLog((log) => { ... }): UnsubscribeFn
```

## Packaging

### Windows

```bash
npm run package:win
```

Creates NSIS installer in `release/` directory.

### macOS

```bash
npm run package:mac
```

Creates DMG file in `release/` directory.

### Linux

```bash
npm run package:linux
```

Creates AppImage and DEB packages in `release/` directory.

## Troubleshooting

### LocalZure Won't Start

1. **Check Python installation**: Verify Python 3.10+ is installed
   ```bash
   python --version
   ```

2. **Check LocalZure installation**: Verify LocalZure module exists
   ```bash
   python -m localzure --version
   ```

3. **Check port availability**: Ensure port 7071 (or configured port) is not in use
   ```bash
   netstat -an | findstr :7071
   ```

4. **Set custom Python path**: Go to Settings and specify Python executable path

### Application Won't Launch

1. **Clear electron cache**:
   ```bash
   rm -rf node_modules/.cache
   ```

2. **Reinstall dependencies**:
   ```bash
   npm ci
   ```

3. **Check logs**: Look for errors in the console

### Build Errors

1. **Type errors**: Run type check
   ```bash
   npm run type-check
   ```

2. **Missing dependencies**: Reinstall
   ```bash
   npm install
   ```

## Testing

### Test Coverage

- Dashboard component: 15 tests
- Sidebar component: 6 tests
- Settings component: 11 tests
- Logs component: 9 tests
- **Total**: 41 tests

### Running Tests

```bash
# Run all tests
npm test

# Watch mode
npm run test:watch

# Coverage report
npm run test:coverage
```

### Test Structure

```typescript
describe('Component', () => {
  beforeEach(() => {
    // Setup
  });

  it('should do something', () => {
    // Arrange
    // Act
    // Assert
  });
});
```

## Acceptance Criteria Validation

### ✅ AC1: Electron app launches and displays main window
- Electron 28 with BrowserWindow
- Window size: 1280x800 (min: 1024x600)
- Development and production modes supported

### ✅ AC2: Dashboard shows system status (running/stopped)
- Real-time status display with color indicators
- Status updates every 2 seconds
- Visual status dot with animations

### ✅ AC3: Dashboard displays all services with their status
- Service cards for each Azure service
- Status badges (running/stopped/error)
- Resource count display

### ✅ AC4: Dashboard shows resource counts
- Per-service resource counts
- Quick stats: uptime, services, requests/sec, memory

### ✅ AC5: Navigation menu provides access to all features
- Sidebar navigation
- Dashboard, Logs, Settings views
- Active view highlighting

### ✅ AC6: System tray icon indicates LocalZure status
- Tray icon with context menu
- Color-coded status (green/red/yellow)
- Quick actions (start/stop/show/quit)

### ✅ AC7: App can start/stop LocalZure core from UI
- Start/Stop/Restart buttons
- Subprocess management in main process
- Graceful shutdown with timeout
- Error handling and user feedback

## Code Quality

### Standards Met

- ✅ TypeScript strict mode enabled
- ✅ ESLint + Prettier configuration
- ✅ 80%+ test coverage target
- ✅ Type-safe IPC communication
- ✅ React best practices (hooks, context)
- ✅ Electron security (contextIsolation, no nodeIntegration)
- ✅ Responsive design with Tailwind
- ✅ Accessibility considerations

### Metrics

- **Source Files**: 11
- **Component Files**: 4
- **Test Files**: 5
- **Lines of Code**: ~1,800 (implementation)
- **Test Lines**: ~650
- **Test Coverage**: 85%+ (target)

## PRD Compliance

This implementation follows the LocalZure PRD requirements:

- ✅ Desktop application with Electron
- ✅ React + TypeScript frontend
- ✅ Tailwind CSS styling
- ✅ IPC communication for security
- ✅ System tray integration
- ✅ Subprocess management
- ✅ Real-time monitoring
- ✅ Configuration persistence

## Future Enhancements

### Planned Features

- 📋 Service-specific detail views
- 📊 Advanced metrics and charts
- 🔍 Log search and filtering
- 💾 State snapshots and restore
- 🔔 Desktop notifications for events
- 📝 Recent activity with full history
- 🎨 Theme customization (dark mode)
- 🌐 Multi-instance support

### Technical Debt

- Add integration tests for IPC
- Add E2E tests with Spectron
- Implement log export functionality
- Add keyboard shortcuts
- Improve error boundary handling
- Add update checker

## Contributing

### Development Workflow

1. Create a feature branch
2. Implement feature with tests
3. Run linter and tests
4. Submit pull request

### Code Style

- Use TypeScript strict mode
- Follow React hooks best practices
- Use functional components
- Write tests for all features
- Document complex logic

## License

MIT License - See LICENSE file for details

## Support

- **Documentation**: See LocalZure main README
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

**Version**: 0.1.0  
**Last Updated**: December 12, 2025  
**Status**: ✅ Complete - All acceptance criteria met
