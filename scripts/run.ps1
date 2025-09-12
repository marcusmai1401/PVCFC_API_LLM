# PVCFC RAG API - Run Development Server
# PowerShell script tương đương với `make run`

Write-Host "Starting PVCFC RAG API server..." -ForegroundColor Blue

# Kiểm tra .env file
if (!(Test-Path ".env")) {
    Write-Host "No .env file found. Using defaults..." -ForegroundColor Yellow
    Write-Host "Copy env.example to .env and configure for better experience" -ForegroundColor Cyan
}

# Kiểm tra virtual environment
if (!(Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run .\scripts\dev.ps1 first" -ForegroundColor Red
    exit 1
}

# Load environment variables từ .env nếu có
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^([^#].*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

# Lấy port từ environment hoặc dùng default
$port = if ($env:API_PORT) { $env:API_PORT } else { "8000" }

Write-Host "Server will start on http://localhost:$port" -ForegroundColor Green
Write-Host "Health check: http://localhost:$port/healthz" -ForegroundColor Green
Write-Host "API docs: http://localhost:$port/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Chạy server
& "venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port $port
