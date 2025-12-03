# Quick Script: Clear Caches and Restart UI
# Usage: .\launchers\restart_ui_clean.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== PVCFC UI Clean Restart ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop any running Streamlit processes
Write-Host "[1/5] Stopping Streamlit processes..." -ForegroundColor Yellow
Get-Process | Where-Object {$_.ProcessName -eq "streamlit"} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Write-Host "      ✅ Streamlit processes stopped" -ForegroundColor Green

# Step 2: Clear Streamlit cache
Write-Host "[2/5] Clearing Streamlit cache..." -ForegroundColor Yellow
$streamlitCache = "$env:USERPROFILE\.streamlit\cache"
if (Test-Path $streamlitCache) {
    Remove-Item -Recurse -Force $streamlitCache -ErrorAction SilentlyContinue
    Write-Host "      ✅ Streamlit cache cleared" -ForegroundColor Green
} else {
    Write-Host "      ℹ️  No Streamlit cache found" -ForegroundColor Gray
}

# Step 3: Clear Python bytecode cache
Write-Host "[3/5] Clearing Python bytecode cache..." -ForegroundColor Yellow
$pycacheCount = 0
Get-ChildItem -Path "." -Recurse -Include "__pycache__","*.pyc" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
    $pycacheCount++
}
Write-Host "      ✅ Cleared $pycacheCount cache items" -ForegroundColor Green

# Step 4: Check API is running
Write-Host "[4/5] Checking API connectivity..." -ForegroundColor Yellow
try {
    $apiResponse = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($apiResponse.StatusCode -eq 200) {
        Write-Host "      ✅ API is running and healthy" -ForegroundColor Green
    }
} catch {
    Write-Host "      ⚠️  API is not running at http://localhost:8000" -ForegroundColor Yellow
    Write-Host "      Please start API first: .\launchers\start_api.ps1" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne 'y') {
        Write-Host "Aborted. Please start API first." -ForegroundColor Red
        exit 1
    }
}

# Step 5: Start UI
Write-Host "[5/5] Starting Streamlit UI..." -ForegroundColor Yellow
Write-Host ""
Write-Host "      UI will open at: http://localhost:8502" -ForegroundColor Cyan
Write-Host "      Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""
Write-Host "=== Monitoring UI Startup ===" -ForegroundColor Cyan
Write-Host ""

# Set environment variables
$env:PVCFC_API_BASE_URL = "http://localhost:8000"
$env:API_BASE_URL = "http://localhost:8000"
$env:PYTHONPATH = (Resolve-Path ".").Path

# Find Python executable
$pythonCandidates = @(
    ".\.venv\Scripts\python.exe",
    ".\venv\Scripts\python.exe"
)
$pythonExe = $null
foreach ($cand in $pythonCandidates) {
    if (Test-Path $cand) {
        $pythonExe = $cand
        break
    }
}

if (-not $pythonExe) {
    Write-Host "❌ Virtual environment not found at .\.venv or .\venv" -ForegroundColor Red
    Write-Host "   Please run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Start Streamlit with logging
Write-Host "Using Python: $pythonExe" -ForegroundColor Gray
Write-Host "Starting app: streamlit_app/app.py" -ForegroundColor Gray
Write-Host ""
Write-Host "⏳ Loading components... (watch for 'query_lab_improved.py')" -ForegroundColor Yellow
Write-Host ""

# Start Streamlit
& $pythonExe -m streamlit run "streamlit_app/app.py" --server.port 8502 --server.headless false
