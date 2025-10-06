# PowerShell script to restart server and run Task 2 tests
# Usage: .\run_task2_test.ps1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "TASK 2: Testing Post-Validation Fix" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Kill existing server process
Write-Host "[1/4] Stopping existing server..." -ForegroundColor Yellow
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {$_.Path -like "*venv*"} | Stop-Process -Force
Start-Sleep -Seconds 2

# Start server in background
Write-Host "[2/4] Starting server with new code..." -ForegroundColor Yellow
$serverJob = Start-Job -ScriptBlock {
    Set-Location "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"
    & ".\venv\Scripts\python.exe" "run_api.py"
}

# Wait for server to be ready
Write-Host "[3/4] Waiting for server to be ready..." -ForegroundColor Yellow
$maxWait = 30
$waited = 0
$ready = $false

while ($waited -lt $maxWait) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/healthz" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # Server not ready yet
    }
    Start-Sleep -Seconds 2
    $waited += 2
    Write-Host "." -NoNewline
}

Write-Host ""

if (-not $ready) {
    Write-Host "✗ Server failed to start within ${maxWait}s" -ForegroundColor Red
    Stop-Job -Job $serverJob
    Remove-Job -Job $serverJob
    exit 1
}

Write-Host "✓ Server is ready!" -ForegroundColor Green

# Run test script
Write-Host "`n[4/4] Running tests..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" "test_post_validation_fix.py"

# Keep server running for manual inspection if needed
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Server is still running in background (Job ID: $($serverJob.Id))" -ForegroundColor Cyan
Write-Host "To stop: Stop-Job -Id $($serverJob.Id); Remove-Job -Id $($serverJob.Id)" -ForegroundColor Cyan
Write-Host "To view server logs: Receive-Job -Id $($serverJob.Id)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
