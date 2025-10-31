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

# Check and start Redis if needed
Write-Host "Checking Redis status..." -ForegroundColor Cyan
$redisRunning = $false
try {
    $tcpTest = Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    $redisRunning = $tcpTest.TcpTestSucceeded
} catch {
    $redisRunning = $false
}

$redisProcess = $null
if ($redisRunning) {
    Write-Host "[OK] Redis is already running on port 6379" -ForegroundColor Green
} else {
    Write-Host "[!] Redis not detected. Attempting to start redis-server..." -ForegroundColor Yellow

    # Check if redis-server is available (try PATH first, then fallback to C:\Redis)
    $redisExe = Get-Command redis-server -ErrorAction SilentlyContinue
    if (-not $redisExe -and (Test-Path "C:\Redis\redis-server.exe")) {
        $redisExe = Get-Command "C:\Redis\redis-server.exe" -ErrorAction SilentlyContinue
    }

    if ($redisExe) {
        try {
            # Start Redis in background
            $redisPath = $redisExe.Source
            Write-Host "  Using: $redisPath" -ForegroundColor Gray
            $redisProcess = Start-Process -FilePath $redisPath -WindowStyle Hidden -PassThru
            Write-Host "[OK] Started Redis (PID: $($redisProcess.Id))" -ForegroundColor Green

            # Wait a moment for Redis to initialize
            Start-Sleep -Seconds 1

            # Verify Redis started
            try {
                $tcpTest = Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
                if ($tcpTest.TcpTestSucceeded) {
                    Write-Host "[OK] Redis is now available" -ForegroundColor Green
                } else {
                    Write-Host "[WARN] Redis may not be ready yet" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "[WARN] Could not verify Redis status" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "[WARN] Failed to start Redis: $_" -ForegroundColor Yellow
            Write-Host "  Multi-turn conversations will be disabled" -ForegroundColor Gray
        }
    } else {
        Write-Host "[WARN] redis-server not found in PATH" -ForegroundColor Yellow
        Write-Host "  To enable multi-turn chat, install Redis:" -ForegroundColor Gray
        Write-Host "    choco install redis-64 -y" -ForegroundColor Gray
        Write-Host "  Multi-turn conversations will be disabled" -ForegroundColor Gray
    }
}
Write-Host ""

# Cleanup handler to stop Redis when script exits
$cleanupScript = {
    if ($redisProcess -and !$redisProcess.HasExited) {
        Write-Host "`nStopping Redis (PID: $($redisProcess.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $redisProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Redis stopped" -ForegroundColor Green
    }
}

# Register cleanup on Ctrl+C
try {
    Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanupScript | Out-Null
} catch {
    # Ignore if already registered
}

# Start the server
Write-Host "Starting API server..." -ForegroundColor Green
# Note: Removed --reload to prevent restarts when packages are installed

try {
    & $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} finally {
    # Cleanup: Stop Redis if we started it
    if ($redisProcess -and !$redisProcess.HasExited) {
        Write-Host "`nStopping Redis (PID: $($redisProcess.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $redisProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Redis stopped" -ForegroundColor Green
    }
}
