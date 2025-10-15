# Activate GPU environment for PaddleOCR ingestion
Write-Host "Activating Python venv with GPU support..." -ForegroundColor Green

# Add cuDNN to PATH
$cudnn_bin = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Lib\site-packages\nvidia\cudnn\bin"
$cublas_bin = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Lib\site-packages\nvidia\cublas\bin"

if (Test-Path $cudnn_bin) {
    $env:PATH = "$cudnn_bin;$cublas_bin;" + $env:PATH
    Write-Host "✅ cuDNN added to PATH" -ForegroundColor Green
}

# Activate venv
& "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Scripts\Activate.ps1"

Write-Host ""
Write-Host "🚀 GPU environment ready!" -ForegroundColor Cyan
Write-Host "   GPU: NVIDIA RTX 4060" -ForegroundColor Yellow
Write-Host "   CUDA: 11.8" -ForegroundColor Yellow
Write-Host "   cuDNN: 8.9" -ForegroundColor Yellow
Write-Host ""
