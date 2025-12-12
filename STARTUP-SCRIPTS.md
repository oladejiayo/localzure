# LocalZure Startup Scripts

This directory contains convenience scripts to start both the LocalZure backend and desktop app together.

## Usage

### Windows (PowerShell)

```powershell
.\start-localzure.ps1
```

### macOS/Linux (Bash)

```bash
chmod +x start-localzure.sh
./start-localzure.sh
```

## What the Scripts Do

1. **Prerequisites Check**
   - Verifies Python virtual environment exists (`.venv`)
   - Verifies desktop dependencies are installed (`desktop/node_modules`)

2. **Start Backend**
   - Activates Python virtual environment
   - Starts Flask development server on `http://localhost:5000`
   - Runs backend as a background job/process

3. **Health Check**
   - Waits for backend to initialize (3 seconds)
   - Tests backend health endpoint

4. **Start Desktop App**
   - Launches Electron desktop app
   - Desktop app automatically connects to backend

5. **Cleanup**
   - When you close the desktop app, the script automatically stops the backend
   - Clean shutdown of all processes

## Manual Setup

If you prefer to run services manually:

### Backend (Terminal 1)
```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.\.venv\Scripts\Activate.ps1  # Windows

# Start backend
python -m flask run --host=0.0.0.0 --port=5000
# Or: localzure start
```

### Desktop App (Terminal 2)
```bash
cd desktop
npm run start
```

## Troubleshooting

### "Virtual environment not found"
```bash
# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux
.\.venv\Scripts\Activate.ps1  # Windows

# Install dependencies
pip install -e .
```

### "Desktop dependencies not installed"
```bash
cd desktop
npm install
```

### Backend health check fails
- The script continues anyway, but you may need to wait a few more seconds
- Check if port 5000 is already in use
- Look for Flask error messages in the console

### Can't execute PowerShell script (Windows)
```powershell
# Check execution policy
Get-ExecutionPolicy

# If restricted, run as admin:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Can't execute bash script (macOS/Linux)
```bash
# Make it executable
chmod +x start-localzure.sh

# Then run
./start-localzure.sh
```

## Environment Variables

The scripts set these environment variables:

- `FLASK_APP=localzure.cli:create_app`
- `FLASK_ENV=development`

You can customize these by editing the scripts directly.

## Ports

Default ports used:
- Backend: `5000` (Flask/HTTP)
- Service Bus: `7071` (AMQP)
- Blob Storage: `10000` (HTTP)
- Queue Storage: `10001` (HTTP)
- Table Storage: `10002` (HTTP)

## Logs

### Windows (PowerShell)
- Backend logs are shown in the console where you ran the script
- Use `Get-Job` to check background job status

### macOS/Linux (Bash)
- Backend logs: `/tmp/localzure-backend.log`
- Use `tail -f /tmp/localzure-backend.log` to follow logs

## Need Help?

See the main [README.md](README.md) for more information about LocalZure.
