# Quick Restart Script for API
# Stops any running API process and starts fresh

Write-Host "🔄 Restarting API..." -ForegroundColor Cyan

# Stop any running Python/uvicorn processes
Write-Host "`n1️⃣ Stopping any running API processes..." -ForegroundColor Yellow
Get-Process -Name python,pythonw -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*app.main:app*"
} | Stop-Process -Force -ErrorAction SilentlyContinue

# Wait a moment
Start-Sleep -Seconds 2

# Check if port 8000 is free
Write-Host "`n2️⃣ Checking port 8000..." -ForegroundColor Yellow
$portCheck = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portCheck) {
    Write-Host "⚠️ Port 8000 still occupied, killing process..." -ForegroundColor Yellow
    $processId = $portCheck.OwningProcess
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Write-Host "✅ Port 8000 is now free" -ForegroundColor Green

# Start the API using the existing start script
Write-Host "`n3️⃣ Starting API server..." -ForegroundColor Yellow
Write-Host "   Opening new window for API logs..." -ForegroundColor Gray

Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '.\start_api.ps1'"

# Wait for API to start
Write-Host "`n4️⃣ Waiting for API to become ready..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$ready = $false

while ($attempt -lt $maxAttempts -and -not $ready) {
    $attempt++
    Start-Sleep -Seconds 2

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $ready = $true
            Write-Host "✅ API is ready!" -ForegroundColor Green

            # Get and display index stats
            Write-Host "`n5️⃣ Checking index stats..." -ForegroundColor Yellow
            $stats = Invoke-RestMethod -Uri "http://localhost:8000/index-stats" -ErrorAction SilentlyContinue

            $bm25Count = $stats.bm25.doc_count
            $faissCount = $stats.faiss.vector_count

            Write-Host "   BM25 documents: $bm25Count" -ForegroundColor Cyan
            Write-Host "   FAISS vectors: $faissCount" -ForegroundColor Cyan

            if ($faissCount -gt 9000) {
                Write-Host "`n✅ Index loaded successfully with new data (9420+ vectors)!" -ForegroundColor Green
            } else {
                Write-Host "`n⚠️ Warning: Index has fewer vectors than expected" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "." -NoNewline
    }
}

if (-not $ready) {
    Write-Host "`n❌ API did not become ready in time. Check the API log window." -ForegroundColor Red
    exit 1
}

Write-Host "`n✅ Restart complete! You can now run tests." -ForegroundColor Green
Write-Host "`n💡 Run tests with: python test_priority1_fixes.py" -ForegroundColor Cyan
