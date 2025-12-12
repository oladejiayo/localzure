# LocalZure Desktop - Quick Start Guide

## Prerequisites

- Node.js 18+ and npm
- Python 3.10+ with LocalZure installed
- LocalZure working in the parent directory

## Installation

From the project root:

```bash
# Install desktop dependencies
cd desktop
npm install
```

## Development

### Option 1: Combined (Recommended)

```bash
npm run dev
```

This starts both the Vite dev server and Electron in watch mode.

### Option 2: Separate Terminals

Terminal 1 - React dev server:
```bash
npm run dev:renderer
```

Terminal 2 - Electron app:
```bash
npm run dev:main
npm run start:dev
```

## Building

### Development Build

```bash
npm run build
```

### Production Packages

Windows:
```bash
npm run package:win
```

macOS:
```bash
npm run package:mac
```

Linux:
```bash
npm run package:linux
```

Packages will be created in the `release/` directory.

## Testing

```bash
# Run all tests
npm test

# Watch mode
npm run test:watch

# With coverage
npm run test:coverage
```

## Project Structure

```
desktop/
├── src/
│   ├── main/              # Electron main process
│   │   ├── main.ts        # App lifecycle, subprocess management
│   │   └── preload.ts     # IPC bridge
│   └── renderer/          # React frontend
│       ├── components/
│       │   ├── Dashboard.tsx
│       │   ├── Sidebar.tsx
│       │   ├── Settings.tsx
│       │   └── Logs.tsx
│       ├── App.tsx
│       ├── main.tsx
│       └── styles.css
├── dist/                  # Build output
├── package.json
└── README.md
```

## Troubleshooting

### "Python not found"

Set the Python path in Settings or ensure Python is in your PATH:

```bash
python --version  # Should show 3.10+
```

### "Port already in use"

Change the port in Settings (default is 7071).

### "LocalZure won't start"

1. Verify LocalZure installation:
   ```bash
   python -m localzure --version
   ```

2. Check the logs panel for error details

3. Try starting LocalZure manually first:
   ```bash
   cd ..
   python -m localzure start
   ```

### Build errors

Clear cache and reinstall:
```bash
rm -rf node_modules dist
npm install
npm run build
```

## Features

✅ Start/Stop/Restart LocalZure from UI  
✅ Real-time service monitoring  
✅ System tray integration  
✅ Live log streaming  
✅ Configuration management  
✅ Cross-platform support  

## Learn More

- [Full Documentation](README.md)
- [Implementation Details](../docs/implementation/STORY-DESKTOP-001.md)
- [Architecture](../docs/reference/architecture.md)

---

**Need Help?** Open an issue at https://github.com/oladejiayo/localzure/issues
