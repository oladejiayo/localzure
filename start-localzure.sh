#!/bin/bash
# Start LocalZure Backend and Desktop App
# This script starts both the Flask backend and Electron desktop app

echo "🚀 Starting LocalZure..."
echo ""

# Check if Python virtual environment exists
if [ ! -f ".venv/bin/activate" ]; then
    echo "❌ Python virtual environment not found!"
    echo "   Please run: python -m venv .venv"
    echo "   Then: source .venv/bin/activate"
    echo "   Then: pip install -e ."
    exit 1
fi

# Check if node_modules exists in desktop folder
if [ ! -d "desktop/node_modules" ]; then
    echo "❌ Desktop dependencies not installed!"
    echo "   Please run: cd desktop && npm install"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Activate Python virtual environment
echo "📦 Activating Python virtual environment..."
source .venv/bin/activate

# Start Flask backend in background
echo "🌐 Starting LocalZure backend (Flask)..."
export FLASK_APP="localzure.cli:create_app"
export FLASK_ENV="development"
python -m flask run --host=0.0.0.0 --port=5000 > /tmp/localzure-backend.log 2>&1 &
BACKEND_PID=$!

echo "✅ Backend started (PID: $BACKEND_PID)"
echo "   Backend URL: http://localhost:5000"
echo "   Logs: /tmp/localzure-backend.log"
echo ""

# Wait a bit for backend to initialize
echo "⏳ Waiting for backend to initialize..."
sleep 3

# Test backend health
if curl -s -f http://localhost:5000/health > /dev/null 2>&1; then
    echo "✅ Backend is healthy!"
else
    echo "⚠️  Backend health check failed, but continuing..."
    echo "   You may need to wait a few more seconds"
fi

echo ""
echo "🖥️  Starting Desktop app (Electron)..."
cd desktop

# Start Electron app (this will block until app closes)
npm run start

# Cleanup: Stop backend when desktop app closes
echo ""
echo "🛑 Desktop app closed. Stopping backend..."
kill $BACKEND_PID 2>/dev/null
echo "✅ Backend stopped"

echo ""
echo "👋 LocalZure stopped. Goodbye!"
