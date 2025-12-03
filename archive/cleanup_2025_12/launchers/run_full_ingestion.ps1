# =====================================================
# PVCFC Full Ingestion Launcher
# =====================================================
# This script runs full ingestion with all recommended flags
# to avoid missing OCR, PID tags, or other important features.

$ErrorActionPreference = "Stop"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "PVCFC FULL INGESTION LAUNCHER" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$SOURCE_DIR = "D:\Data_Raw"
$WORKERS = 2
$ENABLE_OCR = $true  # OCR is now enabled by default (requires Google Cloud Vision credentials)
$ENABLE_PID_TAGS = $true
$EXTRACT_TABLES = $true
$CHUNK_SIZE = 1000
$CHUNK_OVERLAP = 200

# Display configuration
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Source Directory: $SOURCE_DIR" -ForegroundColor White
Write-Host "  Workers: $WORKERS" -ForegroundColor White
Write-Host "  OCR Enabled: $ENABLE_OCR" -ForegroundColor White
Write-Host "  PID Tags Enabled: $ENABLE_PID_TAGS" -ForegroundColor White
Write-Host "  Table Extraction: $EXTRACT_TABLES" -ForegroundColor White
Write-Host "  Chunk Size: $CHUNK_SIZE" -ForegroundColor White
Write-Host "  Chunk Overlap: $CHUNK_OVERLAP" -ForegroundColor White
Write-Host ""

# Check if source directory exists
if (-not (Test-Path $SOURCE_DIR)) {
    Write-Host "ERROR: Source directory does not exist: $SOURCE_DIR" -ForegroundColor Red
    exit 1
}

# Count PDFs
$pdfCount = (Get-ChildItem -Path $SOURCE_DIR -Filter "*.pdf" -Recurse).Count
Write-Host "Found $pdfCount PDF files in source directory" -ForegroundColor Green
Write-Host ""

# Confirm before running
Write-Host "Press Enter to start ingestion or Ctrl+C to cancel..." -ForegroundColor Yellow
$null = Read-Host

Write-Host ""
Write-Host "Starting ingestion..." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Build command
$cmd = "python"
$args = @(
    "tools/ingest.py",
    "--source-dir", $SOURCE_DIR,
    "--workers", $WORKERS,
    "--chunk-size", $CHUNK_SIZE,
    "--chunk-overlap", $CHUNK_OVERLAP
)

if ($EXTRACT_TABLES) {
    $args += "--extract-tables"
}

# OCR is now enabled by default, only add flag if explicitly set
if ($ENABLE_OCR) {
    # No need to add --enable-ocr since it's default now
    # Add --no-ocr if you want to disable it
} else {
    $args += "--no-ocr"
}

if ($ENABLE_PID_TAGS) {
    $args += "--enable-pid-tags"
}

# Run ingestion
$startTime = Get-Date
& $cmd $args

$exitCode = $LASTEXITCODE
$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
if ($exitCode -eq 0) {
    Write-Host "INGESTION COMPLETED SUCCESSFULLY" -ForegroundColor Green
} else {
    Write-Host "INGESTION FAILED (Exit Code: $exitCode)" -ForegroundColor Red
}
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Duration: $($duration.ToString('hh\:mm\:ss'))" -ForegroundColor White
Write-Host ""

exit $exitCode
