#!/bin/bash
set -e

echo "🚀 Starting PDFMathTranslate API Server..."
echo "📂 Working directory: $(pwd)"
echo "🔍 Python path: $(which python)"
echo "📦 Python version: $(python --version)"

# Check if api_server.py exists
if [ ! -f "api_server.py" ]; then
    echo "❌ api_server.py not found in $(pwd)"
    echo "📁 Files in current directory:"
    ls -la
    exit 1
fi

echo "✅ api_server.py found"

# Test critical imports first
echo "🔍 Testing critical imports..."
python -c "
try:
    import babeldoc
    print(f'✅ BabelDOC version: {babeldoc.__version__}')
    
    from babeldoc.high_level import async_translate
    print('✅ BabelDOC high_level import successful')
    
    from pdf2zh_next.config import ConfigManager
    print('✅ PDF2ZH config import successful')
    
    import fastapi
    import uvicorn
    print('✅ FastAPI imports successful')
    
    print('🎉 All critical imports successful!')
except Exception as e:
    print(f'❌ Import failed: {e}')
    print('📦 Installed packages:')
    import subprocess
    subprocess.run(['pip', 'list'])
    exit(1)
"

echo "🌐 Starting server on ${HOST:-0.0.0.0}:${PORT:-8080}"

# Run the API server
exec python api_server.py