# Start Streamlit UI for PVCFC RAG
$ErrorActionPreference = "Stop"

Write-Host "Starting PVCFC RAG Debug UI..." -ForegroundColor Green
Write-Host "UI will run on http://localhost:8502" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Set API base URL environment variables
[Environment]::SetEnvironmentVariable("PVCFC_API_BASE_URL", "http://localhost:8000", "Process")
[Environment]::SetEnvironmentVariable("API_BASE_URL", "http://localhost:8000", "Process")
# Ensure Python can import local packages
$env:PYTHONPATH = (Resolve-Path ".").Path
Write-Host "API Base URL set to: http://localhost:8000" -ForegroundColor Cyan
Write-Host ("PYTHONPATH = {0}" -f $env:PYTHONPATH) -ForegroundColor Cyan
Write-Host ""

# Check if API is running
Write-Host "Checking API connectivity..." -ForegroundColor Yellow
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    Write-Host "[OK] API is running and healthy" -ForegroundColor Green
    try { $health = $resp.Content | ConvertFrom-Json } catch { $health = $null }
    if ($health) {
        Write-Host ("  Environment: {0}" -f $health.app_env) -ForegroundColor Gray
        Write-Host ("  LLM Provider: {0} (Ready: {1})" -f $health.llm_provider, $health.llm_provider_ready) -ForegroundColor Gray
    }
}
catch {
    Write-Host "[WARN] API is not reachable at http://localhost:8000" -ForegroundColor Yellow
    Write-Host "  Please start the API first: .\start_api.ps1" -ForegroundColor Yellow
    Write-Host ""
    $answer = Read-Host "Do you want to continue anyway? (y/N)"
    if ($answer -ne 'y') { exit 1 }
}
Write-Host ""

# Start Streamlit (production UI)
Write-Host "Starting Streamlit UI..." -ForegroundColor Green
Write-Host "  Using production app: streamlit_app/app.py" -ForegroundColor Cyan
Write-Host "  (For debug UI, use: streamlit run streamlit_app/app_debug.py)" -ForegroundColor Gray
Write-Host ""

# Choose Python interpreter: prefer .venv, fallback to venv
$pythonCandidates = @(
    ".\.venv\Scripts\python.exe",
    ".\venv\Scripts\python.exe"
)
$pythonExe = $null
foreach ($cand in $pythonCandidates) {
    if (Test-Path $cand) { $pythonExe = $cand; break }
}
if (-not $pythonExe) {
    Write-Host "Virtual environment not found at .\.venv or .\venv" -ForegroundColor Red
    exit 1
}
Write-Host ("Using Python: {0}" -f $pythonExe) -ForegroundColor Gray

& $pythonExe -m streamlit run "streamlit_app/app.py" --server.port 8502 --server.headless false
