#!/usr/bin/env pwsh
# Start LocalZure Backend and Desktop App
# This script builds the desktop app, starts the LocalZure backend, and launches Electron

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "      LocalZure - Azure Services Emulator" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python virtual environment exists
if (-Not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "[ERROR] Python virtual environment not found!" -ForegroundColor Red
    Write-Host "   Please run: python -m venv .venv" -ForegroundColor Yellow
    Write-Host "   Then: .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "   Then: pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Check if node_modules exists in desktop folder
if (-Not (Test-Path "desktop\node_modules")) {
    Write-Host "[ERROR] Desktop dependencies not installed!" -ForegroundColor Red
    Write-Host "   Please run: cd desktop; npm install" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/4] Prerequisites check passed" -ForegroundColor Green
Write-Host ""

# Activate Python virtual environment
Write-Host "[2/4] Verifying Python dependencies..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

$testImport = python -c "from localzure.cli import main; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Some dependencies may be missing. Installing..." -ForegroundColor Yellow
    pip install -r requirements.txt -q
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Dependencies installed successfully" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "   Dependencies verified" -ForegroundColor Green
}
Write-Host ""

# Build desktop app
Write-Host "[3/3] Building desktop application..." -ForegroundColor Cyan
Set-Location desktop
Write-Host "   Building TypeScript (main process)..." -ForegroundColor Gray
npm run build:main --silent
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to build main process" -ForegroundColor Red
    exit 1
}
Write-Host "   Building React app (renderer)..." -ForegroundColor Gray
npm run build:renderer --silent
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to build renderer" -ForegroundColor Red
    exit 1
}
Write-Host "   Desktop build complete!" -ForegroundColor Green
Set-Location ..
Write-Host ""

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   Launching LocalZure Desktop Application" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NOTE: The desktop app is a UI for viewing and managing resources." -ForegroundColor Yellow
Write-Host "To start the LocalZure backend, run in a separate terminal:" -ForegroundColor Yellow
Write-Host "  localzure start" -ForegroundColor Cyan
Write-Host ""
Set-Location desktop

# Start Electron app (this will block until app closes)
npm run start

Write-Host ""
Write-Host "Desktop app closed. Goodbye! 👋" -ForegroundColor Cyan
Write-Host ""

Write-Host ""
Write-Host "LocalZure stopped. Goodbye! 👋" -ForegroundColor Cyan
Write-Host ""
