#!/bin/bash

# Test script to verify Docker configuration
echo "🧪 Testing Docker Configuration..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✅ Docker is running"

# Test building the image
echo "🔨 Building Docker image..."
if docker build -t made-in-china-scraper .; then
    echo "✅ Docker image built successfully"
else
    echo "❌ Failed to build Docker image"
    exit 1
fi

# Test running the container
echo "🚀 Testing container..."
if docker run --rm made-in-china-scraper python main.py --help; then
    echo "✅ Container test successful"
else
    echo "❌ Container test failed"
    exit 1
fi

echo "🎉 All tests passed! Your Docker configuration is ready for deployment."
















