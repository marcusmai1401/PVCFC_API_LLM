# Start API server for PVCFC RAG
Write-Host "Starting PVCFC RAG API server..." -ForegroundColor Green
Write-Host "Server will run on http://localhost:8000" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
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

# Load environment variables from .env
if (Test-Path ".\.env") {
    Get-Content ".\.env" | ForEach-Object {
        if ($_ -match '^([^#].*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host "Loaded .env file" -ForegroundColor Green
} else {
    Write-Host "No .env file found, using defaults" -ForegroundColor Yellow
}

# Show current configuration
Write-Host "`nCurrent Configuration:" -ForegroundColor Cyan
Write-Host "  APP_ENV: $env:APP_ENV" -ForegroundColor Gray
Write-Host "  API_PORT: $env:API_PORT" -ForegroundColor Gray
Write-Host "  LLM_PROVIDER: $env:LLM_PROVIDER" -ForegroundColor Gray
Write-Host "  LLM_MODEL_LIGHT: $env:LLM_MODEL_LIGHT" -ForegroundColor Gray
Write-Host "  LLM_MODEL_HEAVY: $env:LLM_MODEL_HEAVY" -ForegroundColor Gray
Write-Host ""

# Start the server
Write-Host "Starting server..." -ForegroundColor Green
# Note: Removed --reload to prevent restarts when packages are installed
& $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
