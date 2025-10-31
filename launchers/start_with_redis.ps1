# Start PVCFC RAG API with Redis (Multi-turn Chat Support)
# PowerShell script for Windows

Write-Host "Starting PVCFC RAG API with Multi-turn Chat Support..." -ForegroundColor Cyan

# Check if Docker is running
Write-Host "`nChecking Docker..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker is running" -ForegroundColor Green

# Start Redis container
Write-Host "`nStarting Redis..." -ForegroundColor Yellow
docker-compose up -d redis
Start-Sleep -Seconds 3

# Check Redis health
$redisHealth = docker exec pvcfc_redis redis-cli ping 2>&1
if ($redisHealth -eq "PONG") {
    Write-Host "✓ Redis is healthy" -ForegroundColor Green
} else {
    Write-Host "Warning: Redis may not be ready yet" -ForegroundColor Yellow
}

# Check if Weaviate is needed
Write-Host "`nChecking Weaviate..." -ForegroundColor Yellow
$weaviateRunning = docker ps --filter "name=weaviate" --format "{{.Names}}"
if (-not $weaviateRunning) {
    Write-Host "Starting Weaviate..." -ForegroundColor Yellow
    docker-compose -f docker-compose-weaviate.yml up -d
    Write-Host "Waiting for Weaviate to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}
Write-Host "✓ Weaviate is running" -ForegroundColor Green

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "`nWarning: .env file not found. Copying from env.example..." -ForegroundColor Yellow
    Copy-Item "env.example" ".env"
    Write-Host "✓ Created .env file. Please configure your API keys." -ForegroundColor Green
}

# Activate virtual environment if needed
if (-not $env:VIRTUAL_ENV) {
    Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
    if (Test-Path ".venv\Scripts\Activate.ps1") {
        & .venv\Scripts\Activate.ps1
        Write-Host "✓ Virtual environment activated" -ForegroundColor Green
    } elseif (Test-Path "venv\Scripts\Activate.ps1") {
        & venv\Scripts\Activate.ps1
        Write-Host "✓ Virtual environment activated" -ForegroundColor Green
    } else {
        Write-Host "Warning: Virtual environment not found" -ForegroundColor Yellow
    }
}

# Start API
Write-Host "`nStarting API server..." -ForegroundColor Yellow
Write-Host "Multi-turn chat is enabled via Redis" -ForegroundColor Cyan
Write-Host "Access the API at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Documentation at: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to stop the server`n" -ForegroundColor Yellow

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
