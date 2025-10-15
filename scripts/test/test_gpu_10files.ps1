# Test GPU ingestion with 10 files
param(
    [int]$Workers = 2
)

Write-Host "TEST INGESTION - 10 FILES WITH GPU"
Write-Host "GPU: NVIDIA RTX 4060"
Write-Host "Workers: $Workers"
Write-Host ""

# Add cuDNN to PATH
$cudnn_bin = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Lib\site-packages\nvidia\cudnn\bin"
$cublas_bin = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Lib\site-packages\nvidia\cublas\bin"
$env:PATH = "$cudnn_bin;$cublas_bin;" + $env:PATH

# Clear OCR cache
Write-Host "Clearing OCR cache..."
$cache_dir = "data\staging\ocr_cache"
if (Test-Path $cache_dir) {
    Remove-Item "$cache_dir\*" -Force -ErrorAction SilentlyContinue
}

# Get 10 files
$quarantine = Get-Content "artifacts\ingestion_production\quarantine.jsonl" | ConvertFrom-Json
$ocr_files = $quarantine | Where-Object { $_.reason_code -eq "ocr_failed" -and $_.file -notlike "*__MACOSX*" } | Select-Object -First 10

# Create temp directory
$temp_source = "D:\Data_Raw_Test_10"
if (Test-Path $temp_source) {
    Remove-Item $temp_source -Recurse -Force
}
New-Item -ItemType Directory -Path $temp_source -Force | Out-Null

Write-Host "Copying 10 test files..."
$copied = 0
foreach ($entry in $ocr_files) {
    $source_file = $entry.file
    if (Test-Path $source_file) {
        $filename = Split-Path $source_file -Leaf
        Copy-Item $source_file "$temp_source\$filename" -Force
        $copied++
        Write-Host "  $copied. $filename"
    }
}

Write-Host ""
Write-Host "Copied $copied files"
Write-Host ""

# Run ingestion
$output_dir = "artifacts\ingestion_test_gpu"
if (Test-Path $output_dir) {
    Remove-Item $output_dir -Recurse -Force
}

Write-Host "Starting ingestion with GPU..."
Write-Host ""

$start_time = Get-Date

& "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\venv_ingest\Scripts\python.exe" "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\tools\ingest.py" --source-dir $temp_source --output-dir $output_dir --enable-ocr --ocr-lang "vie+eng" --workers $Workers --extract-tables

$elapsed = (Get-Date) - $start_time

Write-Host ""
Write-Host "TEST COMPLETED"
Write-Host "Time elapsed: $([math]::Round($elapsed.TotalMinutes, 1)) minutes"
Write-Host ""

# Show results
if (Test-Path "$output_dir\manifest.json") {
    $manifest = Get-Content "$output_dir\manifest.json" | ConvertFrom-Json
    Write-Host "Results:"
    Write-Host "  Processed: $($manifest.stats.processed)"
    Write-Host "  Quarantined: $($manifest.stats.quarantine_count)"
    Write-Host "  Total chunks: $($manifest.stats.total_chunks)"
}

# Cleanup
Write-Host ""
Write-Host "Cleanup..."
Remove-Item $temp_source -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Done!"
