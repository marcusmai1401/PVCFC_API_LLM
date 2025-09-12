# PVCFC RAG API - Development Environment Setup
# PowerShell script tương đương với `make dev`

Write-Host "Setting up development environment..." -ForegroundColor Blue

# Kiểm tra Python version
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python không được tìm thấy. Hãy cài Python 3.11+" -ForegroundColor Red
    exit 1
}

Write-Host "Found: $pythonVersion" -ForegroundColor Green

# Tạo virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Không thể tạo virtual environment" -ForegroundColor Red
    exit 1
}

# Kích hoạt virtual environment và cài dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "Lỗi khi cài dependencies" -ForegroundColor Red
    exit 1
}

Write-Host "Development environment ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "   1. Copy env.example to .env: cp env.example .env" -ForegroundColor White
Write-Host "   2. Edit .env to configure your settings" -ForegroundColor White
Write-Host "   3. Run the server: .\scripts\run.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To activate venv manually: venv\Scripts\Activate.ps1" -ForegroundColor Yellow
