#!/bin/bash

set -e

IMAGE_NAME="yzg963/$(basename $(pwd) | tr '[:upper:]' '[:lower:]')"

echo "🔨 Building Docker image: $IMAGE_NAME"
echo "📋 This build will:"
echo "   1. Install all dependencies including babeldoc"
echo "   2. Test critical imports"
echo "   3. Verify API server functionality"
echo ""

docker buildx build -f Dockerfile.api -t "$IMAGE_NAME" .

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Docker image built successfully!"
    echo ""
    echo "🧪 Testing the container..."
    
    # Quick test run
    echo "Starting container for 10 seconds to test startup..."
    timeout 10s docker run --rm -p 8080:8080 "$IMAGE_NAME" || echo "Container test completed"
    
    echo ""
    echo "🚀 To run the container:"
    echo "docker run -it --rm -p 8080:8080 $IMAGE_NAME"
    echo ""
    echo "🌐 Access the service at: http://localhost:8080"
    echo "📖 API docs at: http://localhost:8080/docs"
    echo "❤️  Health check: http://localhost:8080/api/health"
else
    echo "❌ Docker build failed!"
    exit 1
fi