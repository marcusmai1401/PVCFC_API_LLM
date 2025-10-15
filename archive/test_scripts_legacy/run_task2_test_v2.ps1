# PowerShell script to restart server and run Task 2 tests

Write-Host ""
Write-Host "========================================"
Write-Host "TASK 2: Testing Post-Validation Fix"
Write-Host "========================================"
Write-Host ""

# Kill existing server process
Write-Host "[1/4] Stopping existing server..."
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {$_.Path -like "*venv*"} | Stop-Process -Force
Start-Sleep -Seconds 2

# Start server in background
Write-Host "[2/4] Starting server with new code..."
$serverJob = Start-Job -ScriptBlock {
    Set-Location "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"
    & ".\venv\Scripts\python.exe" "run_api.py"
}

# Wait for server to be ready
Write-Host "[3/4] Waiting for server to be ready..."
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
    Write-Host "X Server failed to start" -ForegroundColor Red
    Stop-Job -Job $serverJob
    Remove-Job -Job $serverJob
    exit 1
}

Write-Host "✓ Server is ready!" -ForegroundColor Green

# Run test script
Write-Host ""
Write-Host "[4/4] Running tests..."
& ".\venv\Scripts\python.exe" "test_post_validation_fix.py"

# Cleanup
Write-Host ""
Write-Host "Stopping server..."
Stop-Job -Job $serverJob -ErrorAction SilentlyContinue
Remove-Job -Job $serverJob -ErrorAction SilentlyContinue

Write-Host "Done!"
