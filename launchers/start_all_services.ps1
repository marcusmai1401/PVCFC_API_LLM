# Start All Services - PVCFC RAG System
# Launches: OpenSearch, Weaviate, API, UI in correct order with health checks

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PVCFC RAG - Full System Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "[CHECK] Verifying Docker is running..." -ForegroundColor Yellow
try {
    docker info > $null 2>&1
    Write-Host "[OK] Docker is running" -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop first" -ForegroundColor Yellow
    exit 1
}

# Check if venv exists
Write-Host "[CHECK] Verifying Python virtual environment..." -ForegroundColor Yellow
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
    Write-Host "[ERROR] Virtual environment not found at .\.venv or .\venv" -ForegroundColor Red
    Write-Host "Please create venv first: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Found Python: $pythonExe" -ForegroundColor Green
Write-Host ""

# Load .env file
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
Write-Host "  OpenSearch: http://localhost:9200" -ForegroundColor Gray
Write-Host "  Weaviate:   http://localhost:8080" -ForegroundColor Gray
Write-Host "  API:        http://localhost:8000" -ForegroundColor Gray
Write-Host "  UI:         http://localhost:8502" -ForegroundColor Gray
Write-Host ""

# Step 1: Start OpenSearch
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 1/4: Starting OpenSearch" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting OpenSearch container..." -ForegroundColor Yellow

docker-compose -f docker-compose-opensearch.yml up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to start OpenSearch" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] OpenSearch container started" -ForegroundColor Green
Write-Host "Waiting for OpenSearch to be healthy..." -ForegroundColor Yellow

$maxAttempts = 30
$attempt = 0
$opensearchReady = $false

while ($attempt -lt $maxAttempts) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:9200/_cluster/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Write-Host "[OK] OpenSearch is healthy!" -ForegroundColor Green
            $opensearchReady = $true
            break
        }
    }
    catch {
        $attempt++
        Write-Host "  Attempt $attempt/$maxAttempts..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $opensearchReady) {
    Write-Host "[WARN] OpenSearch did not become ready, but continuing..." -ForegroundColor Yellow
} else {
    Write-Host "Waiting 10 seconds for OpenSearch to fully initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    Write-Host "[OK] OpenSearch initialization complete" -ForegroundColor Green
}

Write-Host ""

# Step 2: Start Weaviate
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 2/4: Starting Weaviate" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Weaviate container..." -ForegroundColor Yellow

docker-compose -f docker-compose-weaviate.yml up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to start Weaviate" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Weaviate container started" -ForegroundColor Green
Write-Host "Waiting for Weaviate to be healthy..." -ForegroundColor Yellow

$attempt = 0
$weaviateReady = $false

while ($attempt -lt $maxAttempts) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8080/v1/.well-known/ready" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Write-Host "[OK] Weaviate is healthy!" -ForegroundColor Green
            $weaviateReady = $true
            break
        }
    }
    catch {
        $attempt++
        Write-Host "  Attempt $attempt/$maxAttempts..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $weaviateReady) {
    Write-Host "[WARN] Weaviate did not become ready, but continuing..." -ForegroundColor Yellow
} else {
    Write-Host "Waiting 5 seconds for Weaviate to fully initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    Write-Host "[OK] Weaviate initialization complete" -ForegroundColor Green
}

Write-Host ""

# Step 3: Start API
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 3/4: Starting API Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting API server in background..." -ForegroundColor Yellow

# Start API in background job
$apiScriptBlock = {
    param($rootPath, $pythonPath)
    Set-Location $rootPath

    # Load .env again in this job
    if (Test-Path ".\.env") {
        Get-Content ".\.env" | ForEach-Object {
            if ($_ -match '^([^#].*)=(.*)$') {
                [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
            }
        }
    }

    Write-Host "[API] Starting uvicorn server..." -ForegroundColor Green
    & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}

$apiJob = Start-Job -ScriptBlock $apiScriptBlock -ArgumentList (Get-Location).Path, $pythonExe

Write-Host "[OK] API job started (Job ID: $($apiJob.Id))" -ForegroundColor Green
Write-Host "Waiting for API to be ready..." -ForegroundColor Yellow
Write-Host "(Showing API logs below)" -ForegroundColor Gray
Write-Host ""

Start-Sleep -Seconds 3

$attempt = 0
$apiReady = $false

while ($attempt -lt $maxAttempts) {
    # Check for API output and display it
    $apiOutput = Receive-Job -Id $apiJob.Id -ErrorAction SilentlyContinue 2>&1
    if ($apiOutput) {
        $apiOutput | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                Write-Host "[API] $($_.Exception.Message)" -ForegroundColor Cyan
            } else {
                Write-Host "[API] $_" -ForegroundColor Cyan
            }
        }
    }

    # Check if job failed
    $jobState = (Get-Job -Id $apiJob.Id).State
    if ($jobState -eq "Failed") {
        Write-Host ""
        Write-Host "[ERROR] API job crashed!" -ForegroundColor Red
        Write-Host "Full error output:" -ForegroundColor Red
        Receive-Job -Id $apiJob.Id -ErrorAction SilentlyContinue 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        break
    }

    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Write-Host ""
            Write-Host "[OK] API is healthy!" -ForegroundColor Green
            try {
                $health = $resp.Content | ConvertFrom-Json
                Write-Host "  Environment: $($health.app_env)" -ForegroundColor Gray
                Write-Host "  LLM Provider: $($health.llm_provider)" -ForegroundColor Gray
            } catch {}
            $apiReady = $true
            break
        }
    }
    catch {
        $attempt++
        if ($attempt % 5 -eq 0) {
            Write-Host "  [Wait] Attempt $attempt/$maxAttempts..." -ForegroundColor Gray
        }
        Start-Sleep -Seconds 2
    }
}

if (-not $apiReady) {
    Write-Host ""
    Write-Host "[ERROR] API did not become ready after 60 seconds!" -ForegroundColor Red
    Write-Host "Dumping full API logs for debugging:" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Receive-Job -Id $apiJob.Id -ErrorAction SilentlyContinue 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Check if:" -ForegroundColor Yellow
    Write-Host "  1. Port 8000 is already in use" -ForegroundColor Gray
    Write-Host "  2. Python dependencies are missing" -ForegroundColor Gray
    Write-Host "  3. OpenSearch/Weaviate connection issues" -ForegroundColor Gray
    Write-Host ""

    $answer = Read-Host "Continue to start UI anyway? (y/N)"
    if ($answer -ne 'y' -and $answer -ne 'Y') {
        Write-Host "[INFO] Aborting..." -ForegroundColor Yellow
        throw "API startup failed"
    }
}

Write-Host ""

# Step 4: Start UI
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 4/4: Starting UI" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Streamlit UI in background..." -ForegroundColor Yellow

# Start UI in background job
$uiScriptBlock = {
    param($rootPath, $pythonPath)
    Set-Location $rootPath

    # Set environment variables for UI
    [Environment]::SetEnvironmentVariable("PVCFC_API_BASE_URL", "http://localhost:8000", "Process")
    [Environment]::SetEnvironmentVariable("API_BASE_URL", "http://localhost:8000", "Process")
    $env:PYTHONPATH = (Resolve-Path ".").Path

    Write-Host "[UI] Starting Streamlit..." -ForegroundColor Green
    & $pythonPath -m streamlit run "streamlit_app/app.py" --server.port 8502 --server.headless false
}

$uiJob = Start-Job -ScriptBlock $uiScriptBlock -ArgumentList (Get-Location).Path, $pythonExe

Write-Host "[OK] UI job started (Job ID: $($uiJob.Id))" -ForegroundColor Green

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  All Services Started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  OpenSearch: http://localhost:9200" -ForegroundColor Yellow
Write-Host "  Weaviate:   http://localhost:8080" -ForegroundColor Yellow
Write-Host "  API:        http://localhost:8000" -ForegroundColor Yellow
Write-Host "  API Docs:   http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "  UI:         http://localhost:8502" -ForegroundColor Yellow
Write-Host ""
Write-Host "Monitoring services..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Monitor jobs and display output
try {
    while ($true) {
        # Check job states
        $apiState = (Get-Job -Id $apiJob.Id).State
        $uiState = (Get-Job -Id $uiJob.Id).State

        # Get and display job output (but don't spam)
        $apiOutput = Receive-Job -Id $apiJob.Id -ErrorAction SilentlyContinue 2>&1
        $uiOutput = Receive-Job -Id $uiJob.Id -ErrorAction SilentlyContinue 2>&1

        if ($apiOutput) {
            $apiOutput | ForEach-Object { Write-Host "[API] $_" -ForegroundColor Cyan }
        }

        if ($uiOutput) {
            $uiOutput | ForEach-Object { Write-Host "[UI] $_" -ForegroundColor Magenta }
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

        # Check if both jobs completed (shouldn't happen normally)
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
    # Cleanup
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "  Shutting Down All Services" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow

    # Stop Python jobs
    Write-Host "[CLEANUP] Stopping API and UI..." -ForegroundColor Yellow
    Stop-Job -Id $apiJob.Id -ErrorAction SilentlyContinue
    Stop-Job -Id $uiJob.Id -ErrorAction SilentlyContinue
    Remove-Job -Id $apiJob.Id -Force -ErrorAction SilentlyContinue
    Remove-Job -Id $uiJob.Id -Force -ErrorAction SilentlyContinue

    # Stop Docker containers
    Write-Host "[CLEANUP] Stopping OpenSearch..." -ForegroundColor Yellow
    docker-compose -f docker-compose-opensearch.yml down

    Write-Host "[CLEANUP] Stopping Weaviate..." -ForegroundColor Yellow
    docker-compose -f docker-compose-weaviate.yml down

    Write-Host ""
    Write-Host "[OK] All services stopped" -ForegroundColor Green
    Write-Host ""
}
