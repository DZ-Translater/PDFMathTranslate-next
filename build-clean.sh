#!/bin/bash

set -e

echo "🧹 Cleaning up Docker cache and images..."

# Clean up any existing images with this name
IMAGE_NAME="yzg963/$(basename $(pwd) | tr '[:upper:]' '[:lower:]')"

echo "📋 Cleaning up previous builds for: $IMAGE_NAME"

# Remove existing image if it exists
docker rmi "$IMAGE_NAME" 2>/dev/null || echo "No existing image to remove"

# Clean up build cache
docker builder prune -f

echo "🔨 Building fresh Docker image..."
docker buildx build --no-cache -f Dockerfile.api -t "$IMAGE_NAME" .

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Docker image built successfully!"
    echo ""
    echo "🧪 Testing the container..."
    
    # Quick test run
    echo "Starting container for 15 seconds to test startup..."
    timeout 15s docker run --rm -p 8080:8080 "$IMAGE_NAME" || echo "Container test completed"
    
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