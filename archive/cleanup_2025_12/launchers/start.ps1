# Quick start script for PVCFC RAG (API + UI)
# Opens API and UI in separate terminal windows

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PVCFC RAG - Quick Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if venv exists
if (!(Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "[ERROR] Virtual environment not found at .\venv" -ForegroundColor Red
    Write-Host "Please create venv first: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

# Get current directory
$currentDir = Get-Location

Write-Host "[1/2] Starting API server..." -ForegroundColor Green
Write-Host "      Opening in new terminal window..." -ForegroundColor Gray

# Start API in new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$currentDir'; .\start_api.ps1"

Write-Host "[OK] API terminal opened" -ForegroundColor Green
Write-Host ""

# Wait a bit for API to start
Write-Host "Waiting 5 seconds for API to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "[2/2] Starting UI..." -ForegroundColor Green
Write-Host "      Opening in new terminal window..." -ForegroundColor Gray

# Start UI in new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$currentDir'; .\start_ui.ps1"

Write-Host "[OK] UI terminal opened" -ForegroundColor Green
Write-Host ""

# Wait for services to be ready
Write-Host "Checking services..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Check API
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    Write-Host "[OK] API is running at http://localhost:8000" -ForegroundColor Green
}
catch {
    Write-Host "[WAIT] API is still starting..." -ForegroundColor Yellow
}

# Check UI (Streamlit takes longer to start)
Start-Sleep -Seconds 5
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8502" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    Write-Host "[OK] UI is running at http://localhost:8502" -ForegroundColor Green
}
catch {
    Write-Host "[WAIT] UI is still starting..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Services launched successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "  API:      http://localhost:8000" -ForegroundColor Yellow
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "  UI:       http://localhost:8502" -ForegroundColor Yellow
Write-Host ""
Write-Host "Two terminal windows have been opened:" -ForegroundColor Cyan
Write-Host "  1. API terminal (port 8000)" -ForegroundColor Gray
Write-Host "  2. UI terminal (port 8502)" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop services:" -ForegroundColor Cyan
Write-Host "  - Press Ctrl+C in each terminal window" -ForegroundColor Gray
Write-Host "  - Or close the terminal windows" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit this launcher..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
