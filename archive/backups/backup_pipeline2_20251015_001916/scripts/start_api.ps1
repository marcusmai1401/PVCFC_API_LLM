# Start Page-First RAG Agent API (PowerShell script for Windows)

Write-Host "=== Starting Page-First RAG Agent API ===" -ForegroundColor Green

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠ .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "✓ Created .env file" -ForegroundColor Green
    Write-Host "⚠ Please edit .env and add your API keys before starting!" -ForegroundColor Yellow
    exit 1
}

# Load environment variables from .env
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.+)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

# Check for required API keys
$openaiKey = $env:OPENAI_API_KEY
$geminiKey = $env:GEMINI_API_KEY

if (-not $openaiKey -or $openaiKey -eq "sk-your-openai-api-key-here") {
    Write-Host "⚠ OPENAI_API_KEY not set in .env file!" -ForegroundColor Red
    Write-Host "Please add your OpenAI API key to .env" -ForegroundColor Yellow
    exit 1
}

if (-not $geminiKey -or $geminiKey -eq "your-gemini-api-key-here") {
    Write-Host "⚠ GEMINI_API_KEY not set in .env file!" -ForegroundColor Red
    Write-Host "Please add your Gemini API key to .env" -ForegroundColor Yellow
    exit 1
}

# Check if artifacts exist
if (-not (Test-Path "artifacts\ingestion_production")) {
    Write-Host "⚠ Artifacts directory not found!" -ForegroundColor Red
    Write-Host "Please run the ingestion pipeline first to generate artifacts." -ForegroundColor Yellow
    exit 1
}

# Create logs directory
New-Item -ItemType Directory -Path "logs" -Force | Out-Null

# Get port from environment or use default
$port = if ($env:API_PORT) { $env:API_PORT } else { "8000" }
$host = if ($env:API_HOST) { $env:API_HOST } else { "0.0.0.0" }
$logLevel = if ($env:LOG_LEVEL) { $env:LOG_LEVEL.ToLower() } else { "info" }

# Start API with uvicorn
Write-Host ""
Write-Host "Starting API server on http://${host}:${port}..." -ForegroundColor Cyan
Write-Host "📚 API Documentation: http://localhost:${port}/docs" -ForegroundColor Cyan
Write-Host "❤️  Health Check: http://localhost:${port}/api/v1/health" -ForegroundColor Cyan
Write-Host ""

# Run uvicorn
python -m uvicorn app.api.page_first_api:app `
    --host $host `
    --port $port `
    --reload `
    --log-level $logLevel
