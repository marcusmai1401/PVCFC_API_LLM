# Start API and Test CoVe Fix
# This script starts the API in background and runs the test

Write-Host "`n========================================"  -ForegroundColor Cyan
Write-Host "Starting API and Testing CoVe Fix" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if API is already running
$apiRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/healthz" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        $apiRunning = $true
    }
} catch {
    $apiRunning = $false
}

if ($apiRunning) {
    Write-Host "API is already running" -ForegroundColor Green
    Write-Host "NOTE: Using existing API instance (changes may not be applied)" -ForegroundColor Yellow
    Write-Host "   If you want to test with new code, please restart API manually:" -ForegroundColor Yellow
    Write-Host "   1. Stop current API (Ctrl+C in API terminal)" -ForegroundColor Yellow
    Write-Host "   2. Run: start_api.ps1" -ForegroundColor Yellow
    Write-Host "`nProceeding with test in 3 seconds...`n" -ForegroundColor Yellow
    Start-Sleep -Seconds 3
} else {
    Write-Host "API not running. Starting API in background..." -ForegroundColor Yellow

    # Start API in new PowerShell window
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\start_api.ps1"

    Write-Host "Waiting for API to be ready (max 30 seconds)..." -ForegroundColor Yellow

    # Wait for API to be ready
    $maxAttempts = 30
    $attempt = 0
    $ready = $false

    while ($attempt -lt $maxAttempts -and -not $ready) {
        Start-Sleep -Seconds 1
        $attempt++

        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/healthz" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $ready = $true
                Write-Host "API is ready after $attempt seconds!" -ForegroundColor Green
            }
        } catch {
            Write-Host "   Attempt $attempt/$maxAttempts..." -NoNewline
            Write-Host "`r" -NoNewline
        }
    }

    if (-not $ready) {
        Write-Host "`nAPI failed to start within 30 seconds" -ForegroundColor Red
        Write-Host "Please check the API terminal for errors" -ForegroundColor Red
        exit 1
    }

    Write-Host "`nAPI started successfully!`n" -ForegroundColor Green
}

# Run the test
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Running CoVe Fix Test" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

python test_cove_fix.py

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Review test results above" -ForegroundColor White
Write-Host "   2. Check API logs for detailed CoVe verification info" -ForegroundColor White
Write-Host "   3. Test via UI with start_ui.ps1" -ForegroundColor White
Write-Host ""
