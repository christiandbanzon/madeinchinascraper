#!/bin/bash

# Made-in-China Scraper Deployment Script
# This script helps deploy the scraper in cloud environments

set -e

echo "🚀 Starting Made-in-China Scraper Deployment..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories if they don't exist
echo "📁 Creating necessary directories..."
mkdir -p data logs history

# Build the Docker image
echo "🔨 Building Docker image..."
docker-compose build

# Test the build
echo "🧪 Testing the build..."
docker-compose run --rm made-in-china-scraper python main.py --help

echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Usage Examples:"
echo "  Search for products:"
echo "    docker-compose run --rm made-in-china-scraper python main.py search 'hair dryer'"
echo ""
echo "  Export data to JSON:"
echo "    docker-compose run --rm made-in-china-scraper python main.py export 'hair dryer' --format json"
echo ""
echo "  Export data to CSV:"
echo "    docker-compose run --rm made-in-china-scraper python main.py export 'hair dryer' --format csv"
echo ""
echo "  View statistics:"
echo "    docker-compose run --rm made-in-china-scraper python main.py stats"
echo ""
echo "  Schedule automated scraping:"
echo "    docker-compose run --rm made-in-china-scraper python main.py schedule 'hair dryer' --interval 3600"
echo ""
echo "📂 Data will be saved in the ./data directory"
echo "📝 Logs will be saved in the ./logs directory"
echo "🕒 History will be saved in the ./history directory"







