# Run ingestion with GPU acceleration
param(
    [string]$SourceDir = "D:\Data_Raw",
    [string]$OutputDir = "artifacts\ingestion_production",
    [int]$Workers = 2,
    [string]$OcrLang = "vie+eng"
)

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "INGESTION WITH GPU ACCELERATION" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Add cuDNN to PATH
$cudnn_bin = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Lib\site-packages\nvidia\cudnn\bin"
$cublas_bin = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Lib\site-packages\nvidia\cublas\bin"

$env:PATH = "$cudnn_bin;$cublas_bin;" + $env:PATH

Write-Host "✅ GPU: NVIDIA RTX 4060 (8GB)" -ForegroundColor Green
Write-Host "✅ CUDA: 11.8 + cuDNN: 8.9" -ForegroundColor Green
Write-Host "✅ Workers: $Workers (GPU parallel)" -ForegroundColor Green
Write-Host ""

# Run ingestion
Write-Host "Starting ingestion..." -ForegroundColor Yellow
Write-Host ""

& "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Scripts\python.exe" `
    "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\tools\ingest.py" `
    --source-dir $SourceDir `
    --output-dir $OutputDir `
    --enable-ocr `
    --ocr-lang $OcrLang `
    --workers $Workers `
    --extract-tables

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "INGESTION COMPLETED" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
