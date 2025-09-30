# Start both API and UI for PVCFC RAG
# This script runs API and UI in parallel using Start-Job

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PVCFC RAG - Full Stack Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if venv exists
if (!(Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "[ERROR] Virtual environment not found at .\venv" -ForegroundColor Red
    Write-Host "Please create venv first: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

# Load environment variables from .env
if (Test-Path ".\.env") {
    Get-Content ".\.env" | ForEach-Object {
        if ($_ -match '^([^#].*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host "[OK] Loaded .env file" -ForegroundColor Green
} else {
    Write-Host "[WARN] No .env file found, using defaults" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  API will run on: http://localhost:8000" -ForegroundColor Gray
Write-Host "  UI will run on:  http://localhost:8502" -ForegroundColor Gray
Write-Host "  APP_ENV: $env:APP_ENV" -ForegroundColor Gray
Write-Host "  LLM_PROVIDER: $env:LLM_PROVIDER" -ForegroundColor Gray
Write-Host ""

# Function to start API
$apiScriptBlock = {
    param($rootPath)
    Set-Location $rootPath

    # Load .env again in this job
    if (Test-Path ".\.env") {
        Get-Content ".\.env" | ForEach-Object {
            if ($_ -match '^([^#].*)=(.*)$') {
                [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
            }
        }
    }

    Write-Host "[API] Starting API server on port 8000..." -ForegroundColor Green
    & ".\venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
}

# Function to start UI
$uiScriptBlock = {
    param($rootPath)
    Set-Location $rootPath

    # Wait for API to be ready
    Write-Host "[UI] Waiting for API to be ready..." -ForegroundColor Yellow
    $maxAttempts = 30
    $attempt = 0
    $apiReady = $false

    while ($attempt -lt $maxAttempts) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                Write-Host "[UI] API is ready!" -ForegroundColor Green
                $apiReady = $true
                break
            }
        }
        catch {
            $attempt++
            Start-Sleep -Seconds 2
        }
    }

    if (-not $apiReady) {
        Write-Host "[UI] WARNING: API did not become ready after 60 seconds" -ForegroundColor Yellow
        Write-Host "[UI] UI will start anyway, but may not work properly" -ForegroundColor Yellow
    }

    # Set environment variables for UI
    [Environment]::SetEnvironmentVariable("PVCFC_API_BASE_URL", "http://localhost:8000", "Process")
    [Environment]::SetEnvironmentVariable("API_BASE_URL", "http://localhost:8000", "Process")
    $env:PYTHONPATH = (Resolve-Path ".").Path

    Write-Host "[UI] Starting Streamlit UI on port 8502..." -ForegroundColor Green
    & ".\venv\Scripts\streamlit.exe" run "streamlit_app/app_debug.py" --server.port 8502 --server.headless false
}

# Start API in background job
Write-Host "[LAUNCHER] Starting API server..." -ForegroundColor Cyan
$apiJob = Start-Job -ScriptBlock $apiScriptBlock -ArgumentList (Get-Location).Path

# Wait a bit for API to start
Start-Sleep -Seconds 3

# Start UI in background job
Write-Host "[LAUNCHER] Starting UI server..." -ForegroundColor Cyan
$uiJob = Start-Job -ScriptBlock $uiScriptBlock -ArgumentList (Get-Location).Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Both services are starting up!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "  API:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "  UI:   http://localhost:8502" -ForegroundColor Yellow
Write-Host ""
Write-Host "Monitoring jobs..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Monitor jobs and display output
try {
    while ($true) {
        # Check if jobs are still running
        $apiState = (Get-Job -Id $apiJob.Id).State
        $uiState = (Get-Job -Id $uiJob.Id).State

        # Get and display job output
        $apiOutput = Receive-Job -Id $apiJob.Id -Keep
        $uiOutput = Receive-Job -Id $uiJob.Id -Keep

        if ($apiOutput) {
            $apiOutput | ForEach-Object { Write-Host "[API] $_" }
        }

        if ($uiOutput) {
            $uiOutput | ForEach-Object { Write-Host "[UI] $_" }
        }

        # Check if any job failed
        if ($apiState -eq "Failed") {
            Write-Host "[ERROR] API job failed!" -ForegroundColor Red
            Receive-Job -Id $apiJob.Id
            break
        }

        if ($uiState -eq "Failed") {
            Write-Host "[ERROR] UI job failed!" -ForegroundColor Red
            Receive-Job -Id $uiJob.Id
            break
        }

        # Check if both jobs completed (shouldn't happen in normal operation)
        if ($apiState -eq "Completed" -and $uiState -eq "Completed") {
            Write-Host "[INFO] Both jobs completed" -ForegroundColor Yellow
            break
        }

        Start-Sleep -Seconds 1
    }
}
catch {
    Write-Host ""
    Write-Host "[INFO] Stopping services..." -ForegroundColor Yellow
}
finally {
    # Clean up jobs
    Write-Host ""
    Write-Host "[CLEANUP] Stopping all services..." -ForegroundColor Yellow

    Stop-Job -Id $apiJob.Id -ErrorAction SilentlyContinue
    Stop-Job -Id $uiJob.Id -ErrorAction SilentlyContinue

    Remove-Job -Id $apiJob.Id -Force -ErrorAction SilentlyContinue
    Remove-Job -Id $uiJob.Id -Force -ErrorAction SilentlyContinue

    Write-Host "[CLEANUP] All services stopped" -ForegroundColor Green
    Write-Host ""
}
