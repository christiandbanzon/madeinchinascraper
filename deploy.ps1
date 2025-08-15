# Made-in-China Scraper Deployment Script for Windows
# This script helps deploy the scraper in cloud environments

Write-Host "🚀 Starting Made-in-China Scraper Deployment..." -ForegroundColor Green

# Check if Docker is installed
try {
    $dockerVersion = docker --version
    Write-Host "✅ Docker found: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if Docker Compose is installed
try {
    $composeVersion = docker-compose --version
    Write-Host "✅ Docker Compose found: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose is not installed. Please install Docker Compose first." -ForegroundColor Red
    exit 1
}

# Create necessary directories if they don't exist
Write-Host "📁 Creating necessary directories..." -ForegroundColor Yellow
if (!(Test-Path "data")) { New-Item -ItemType Directory -Path "data" }
if (!(Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" }
if (!(Test-Path "history")) { New-Item -ItemType Directory -Path "history" }

# Build the Docker image
Write-Host "🔨 Building Docker image..." -ForegroundColor Yellow
try {
    docker-compose build
    Write-Host "✅ Docker image built successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to build Docker image" -ForegroundColor Red
    exit 1
}

# Test the build
Write-Host "🧪 Testing the build..." -ForegroundColor Yellow
try {
    docker-compose run --rm made-in-china-scraper python main.py --help
    Write-Host "✅ Build test successful" -ForegroundColor Green
} catch {
    Write-Host "❌ Build test failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Deployment completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Usage Examples:" -ForegroundColor Cyan
Write-Host "  Search for products:" -ForegroundColor White
Write-Host "    docker-compose run --rm made-in-china-scraper python main.py search 'hair dryer'" -ForegroundColor Gray
Write-Host ""
Write-Host "  Export data to JSON:" -ForegroundColor White
Write-Host "    docker-compose run --rm made-in-china-scraper python main.py export 'hair dryer' --format json" -ForegroundColor Gray
Write-Host ""
Write-Host "  Export data to CSV:" -ForegroundColor White
Write-Host "    docker-compose run --rm made-in-china-scraper python main.py export 'hair dryer' --format csv" -ForegroundColor Gray
Write-Host ""
Write-Host "  View statistics:" -ForegroundColor White
Write-Host "    docker-compose run --rm made-in-china-scraper python main.py stats" -ForegroundColor Gray
Write-Host ""
Write-Host "  Schedule automated scraping:" -ForegroundColor White
Write-Host "    docker-compose run --rm made-in-china-scraper python main.py schedule 'hair dryer' --interval 3600" -ForegroundColor Gray
Write-Host ""
Write-Host "📂 Data will be saved in the ./data directory" -ForegroundColor Yellow
Write-Host "📝 Logs will be saved in the ./logs directory" -ForegroundColor Yellow
Write-Host "🕒 History will be saved in the ./history directory" -ForegroundColor Yellow







