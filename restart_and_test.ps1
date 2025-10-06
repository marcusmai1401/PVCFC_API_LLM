# ============================================
# Automated Restart and Test Script
# ============================================
# This script will:
# 1. Stop any running API process
# 2. Start API in background
# 3. Wait for API to be ready
# 4. Run verification tests
# ============================================

$ErrorActionPreference = "Continue"

Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "  AUTOMATED RESTART AND TEST FOR PRIORITY 1 FIXES" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor Cyan

# Step 1: Stop existing API processes
Write-Host "`n[STEP 1] Stopping existing API processes..." -ForegroundColor Yellow

$apiProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -match "uvicorn" -or
    $_.CommandLine -match "uvicorn" -or
    $_.CommandLine -match "app.main:app"
}

if ($apiProcesses) {
    Write-Host "  Found $($apiProcesses.Count) API process(es). Stopping..." -ForegroundColor Gray
    $apiProcesses | ForEach-Object {
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            Write-Host "  ✓ Stopped process ID: $($_.Id)" -ForegroundColor Green
        } catch {
            Write-Host "  ⚠ Could not stop process ID: $($_.Id)" -ForegroundColor Yellow
        }
    }
    Start-Sleep -Seconds 2
} else {
    Write-Host "  No existing API processes found." -ForegroundColor Gray
}

# Step 2: Check if port 8000 is free
Write-Host "`n[STEP 2] Checking port 8000..." -ForegroundColor Yellow

$portCheck = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

if ($portCheck) {
    Write-Host "  ⚠ Port 8000 is still in use. Attempting to free it..." -ForegroundColor Yellow
    $processId = $portCheck.OwningProcess
    try {
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Write-Host "  ✓ Freed port 8000" -ForegroundColor Green
        Start-Sleep -Seconds 2
    } catch {
        Write-Host "  ❌ Could not free port 8000. Please manually close the process." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ✓ Port 8000 is free" -ForegroundColor Green
}

# Step 3: Start API server in background
Write-Host "`n[STEP 3] Starting API server..." -ForegroundColor Yellow

$currentDir = Get-Location

# Start API in new window directly
try {
    $apiCommand = "Set-Location '$currentDir'; & '.\venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    $apiProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCommand -PassThru
    Write-Host "  ✓ API process started (PID: $($apiProcess.Id))" -ForegroundColor Green
    Write-Host "  ℹ API window opened. You can close it later with Ctrl+C" -ForegroundColor Cyan
} catch {
    Write-Host "  ❌ Failed to start API: $_" -ForegroundColor Red
    exit 1
}

# Step 4: Wait for API to be ready
Write-Host "`n[STEP 4] Waiting for API to be ready..." -ForegroundColor Yellow

$maxWaitTime = 60  # seconds
$waitInterval = 2   # seconds
$elapsed = 0
$apiReady = $false

while ($elapsed -lt $maxWaitTime -and -not $apiReady) {
    Start-Sleep -Seconds $waitInterval
    $elapsed += $waitInterval

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $apiReady = $true
            Write-Host "  ✓ API is ready! (took ${elapsed}s)" -ForegroundColor Green

            # Parse health response
            $health = $response.Content | ConvertFrom-Json
            Write-Host "    Status: $($health.status)" -ForegroundColor Gray
            Write-Host "    LLM Provider: $($health.llm_provider) (Ready: $($health.llm_provider_ready))" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  . Waiting... (${elapsed}s)" -ForegroundColor Gray
    }
}

if (-not $apiReady) {
    Write-Host "  ❌ API did not start within ${maxWaitTime}s" -ForegroundColor Red
    Write-Host "  Please check the API window for errors." -ForegroundColor Yellow
    exit 1
}

# Step 5: Check index stats
Write-Host "`n[STEP 5] Checking index statistics..." -ForegroundColor Yellow

try {
    $statsResponse = Invoke-WebRequest -Uri "http://localhost:8000/index-stats" -UseBasicParsing -TimeoutSec 5
    $stats = $statsResponse.Content | ConvertFrom-Json

    $bm25Count = $stats.bm25.doc_count
    $faissCount = $stats.faiss.vector_count

    Write-Host "  ✓ BM25 index: $bm25Count documents" -ForegroundColor Green
    Write-Host "  ✓ FAISS index: $faissCount vectors" -ForegroundColor Green

    if ($faissCount -gt 9000) {
        Write-Host "  🎉 Using NEW index with 9420+ vectors!" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Still using OLD index ($faissCount vectors)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠ Could not fetch index stats: $_" -ForegroundColor Yellow
}

# Step 6: Run verification tests
Write-Host "`n[STEP 6] Running verification tests..." -ForegroundColor Yellow
Write-Host ""

try {
    & python test_priority1_fixes.py
    $testExitCode = $LASTEXITCODE

    if ($testExitCode -eq 0) {
        Write-Host "`n" -NoNewline
        Write-Host ("🎉" * 40) -ForegroundColor Green
        Write-Host "  ALL TESTS PASSED!" -ForegroundColor Green
        Write-Host "  Priority 1 fixes verified successfully!" -ForegroundColor Green
        Write-Host ("🎉" * 40) -ForegroundColor Green
    } else {
        Write-Host "`n" -NoNewline
        Write-Host ("⚠️" * 40) -ForegroundColor Yellow
        Write-Host "  SOME TESTS FAILED" -ForegroundColor Yellow
        Write-Host "  Please review the test output above." -ForegroundColor Yellow
        Write-Host ("⚠️" * 40) -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Failed to run tests: $_" -ForegroundColor Red
}

# Summary
Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "  SUMMARY" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host ""
Write-Host "API Server:" -ForegroundColor Cyan
Write-Host "  • Running on http://localhost:8000" -ForegroundColor Gray
Write-Host "  • API Docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  • Process ID: $($apiProcess.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop the API:" -ForegroundColor Cyan
Write-Host "  • Close the API terminal window, OR" -ForegroundColor Gray
Write-Host "  • Run: Stop-Process -Id $($apiProcess.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  • Start UI with: .\start_ui.ps1" -ForegroundColor Gray
Write-Host "  • Test queries in UI at http://localhost:8502" -ForegroundColor Gray
Write-Host ""
