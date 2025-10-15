#!/usr/bin/env pwsh

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FULL PRODUCTION INGESTION - GPU MODE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "GPU: NVIDIA RTX 4060" -ForegroundColor Green
Write-Host "Workers: 1 (Stable)" -ForegroundColor Green
Write-Host "Source: D:\Data_Raw (77 PDFs)" -ForegroundColor Green
Write-Host "Output: artifacts\ingestion" -ForegroundColor Green
Write-Host ""

# Activate venv and set GPU paths
Write-Host "Activating environment with GPU support..." -ForegroundColor Yellow
& ".\venv_ingest\Scripts\Activate.ps1"

$env:CUDA_PATH = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8"
$cudnnPath = (python -c "import site; print(site.getsitepackages()[0])") + "\nvidia\cudnn\bin"
$cublasPath = (python -c "import site; print(site.getsitepackages()[0])") + "\nvidia\cublas\bin"
$env:PATH = "$cudnnPath;$cublasPath;" + $env:PATH

Write-Host "Environment ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Starting full ingestion..." -ForegroundColor Cyan
Write-Host "Estimated time: 10-15 minutes for 77 files" -ForegroundColor Yellow
Write-Host ""

$startTime = Get-Date

# Run ingestion
python tools/ingest.py `
    --source-dir "D:\Data_Raw" `
    --output-dir "artifacts\ingestion" `
    --workers 1 `
    --enable-ocr `
    --ocr-lang vie+eng `
    --extract-tables `
    --chunk-strategy hierarchical

$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "INGESTION COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Duration: $($duration.ToString('hh\:mm\:ss'))" -ForegroundColor Yellow
Write-Host ""

# Show results
if (Test-Path "artifacts\ingestion\documents") {
    $docCount = (Get-ChildItem "artifacts\ingestion\documents" -Filter "*.json" -Recurse).Count
    Write-Host "Documents processed: $docCount" -ForegroundColor Green
}

if (Test-Path "artifacts\ingestion\chunks") {
    $chunkCount = (Get-ChildItem "artifacts\ingestion\chunks" -Filter "*.json" -Recurse).Count
    Write-Host "Chunks created: $chunkCount" -ForegroundColor Green
}

if (Test-Path "artifacts\ingestion\quarantine.jsonl") {
    $quarantineCount = (Get-Content "artifacts\ingestion\quarantine.jsonl" | Measure-Object -Line).Lines
    Write-Host "Quarantined files: $quarantineCount" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Output location: artifacts\ingestion" -ForegroundColor Cyan
