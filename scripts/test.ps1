# PVCFC RAG API - Run Tests
# PowerShell script tương đương với `make test`

Write-Host "Running tests..." -ForegroundColor Blue

# Kiểm tra virtual environment
if (!(Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run .\scripts\dev.ps1 first" -ForegroundColor Red
    exit 1
}

# Kiểm tra pytest
& "venv\Scripts\python.exe" -c "import pytest" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "pytest not installed. Run .\scripts\dev.ps1 to install dependencies" -ForegroundColor Red
    exit 1
}

# Chạy tests
& "venv\Scripts\python.exe" -m pytest tests/ -v --tb=short

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "All tests passed!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Some tests failed!" -ForegroundColor Red
}
