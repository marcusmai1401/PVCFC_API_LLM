# Test small ingestion with GPU (10 files)
param(
    [int]$Workers = 2
)

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "TEST INGESTION - 10 FILES WITH GPU" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Add cuDNN to PATH
$cudnn_bin = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Lib\site-packages\nvidia\cudnn\bin"
$cublas_bin = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Lib\site-packages\nvidia\cublas\bin"

$env:PATH = "$cudnn_bin;$cublas_bin;" + $env:PATH

Write-Host "✅ GPU: NVIDIA RTX 4060" -ForegroundColor Green
Write-Host "✅ Workers: $Workers" -ForegroundColor Green
Write-Host ""

# Clear OCR cache to test real speed
Write-Host "🗑️  Clearing OCR cache for fresh test..." -ForegroundColor Yellow
$cache_dir = "data\staging\ocr_cache"
if (Test-Path $cache_dir) {
    Remove-Item "$cache_dir\*" -Force -ErrorAction SilentlyContinue
    Write-Host "   ✓ Cache cleared" -ForegroundColor Green
}
Write-Host ""

# Get 10 ocr_failed files
$quarantine = Get-Content "artifacts\ingestion_production\quarantine.jsonl" | ConvertFrom-Json
$ocr_files = $quarantine | Where-Object { $_.reason_code -eq "ocr_failed" -and $_.file -notlike "*__MACOSX*" } | Select-Object -First 10

# Create temp directory with only these files
$temp_source = "D:\Data_Raw_Test_10"
if (Test-Path $temp_source) {
    Remove-Item $temp_source -Recurse -Force
}
New-Item -ItemType Directory -Path $temp_source -Force | Out-Null

Write-Host "📋 Copying 10 test files..." -ForegroundColor Yellow
$copied = 0
foreach ($entry in $ocr_files) {
    $source_file = $entry.file
    if (Test-Path $source_file) {
        $filename = Split-Path $source_file -Leaf
        Copy-Item $source_file "$temp_source\$filename" -Force
        $copied++
        Write-Host "   $copied. $filename" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "✓ Copied $copied files" -ForegroundColor Green
Write-Host ""

# Run ingestion
$output_dir = "artifacts\ingestion_test_gpu"
if (Test-Path $output_dir) {
    Remove-Item $output_dir -Recurse -Force
}

Write-Host "Starting ingestion with GPU (" -NoNewline -ForegroundColor Cyan
Write-Host "$Workers" -NoNewline -ForegroundColor Yellow
Write-Host " workers)..." -ForegroundColor Cyan
Write-Host ""

$start_time = Get-Date

& "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Scripts\python.exe" `
    "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\tools\ingest.py" `
    --source-dir $temp_source `
    --output-dir $output_dir `
    --enable-ocr `
    --ocr-lang "vie+eng" `
    --workers $Workers `
    --extract-tables

$elapsed = (Get-Date) - $start_time

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "TEST COMPLETED" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Time elapsed: $($elapsed.TotalMinutes.ToString('0.0')) minutes" -ForegroundColor Green
Write-Host ""

# Show results
$manifest = Get-Content "$output_dir\manifest.json" | ConvertFrom-Json
Write-Host "📊 Results:" -ForegroundColor Yellow
Write-Host "   Processed: $($manifest.stats.processed)" -ForegroundColor Green
Write-Host "   Quarantined: $($manifest.stats.quarantine_count)" -ForegroundColor Yellow
Write-Host "   Total chunks: $($manifest.stats.total_chunks)" -ForegroundColor Cyan
Write-Host ""

# Cleanup
Write-Host "🗑️  Cleanup temp files..." -ForegroundColor Gray
Remove-Item $temp_source -Recurse -Force -ErrorAction SilentlyContinue
