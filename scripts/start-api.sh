#!/bin/bash

# PDFMathTranslate API Server Startup Script

set -e

echo "🚀 Starting PDFMathTranslate API Server..."

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed or not in PATH"
    exit 1
fi

# Create necessary directories
mkdir -p static pdf2zh_files config

# Check if dependencies are installed
echo "📦 Checking dependencies..."
python -c "
import fastapi, uvicorn, pydantic
from pdf2zh_next.config import ConfigManager
print('✓ All dependencies are available')
" || {
    echo "❌ Dependencies missing. Installing..."
    pip install fastapi uvicorn pydantic python-multipart
}

# Set default environment variables if not set
export HOST=${HOST:-"0.0.0.0"}
export PORT=${PORT:-"8000"}
export LOG_LEVEL=${LOG_LEVEL:-"info"}

echo "🌐 Starting server on http://${HOST}:${PORT}"
echo "📖 API documentation will be available at http://${HOST}:${PORT}/docs"
echo "🎯 Web interface will be available at http://${HOST}:${PORT}"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python api_server.py