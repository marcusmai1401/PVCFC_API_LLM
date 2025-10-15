# ============================================================================
# INGEST PDF - Automatically switches to venv_ingest environment
# Usage: .\scripts\ingest_pdf.ps1 -PdfPath "C:\path\to\file.pdf" -IndexName "my_index"
# ============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$PdfPath,

    [Parameter(Mandatory=$false)]
    [string]$IndexName = "pvcfc_docs",

    [Parameter(Mandatory=$false)]
    [string]$BatchSize = "100",

    [Parameter(Mandatory=$false)]
    [string]$OpenSearchUrl = $env:OPENSEARCH_URL
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "PDF INGESTION (PaddleOCR Environment)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if PDF exists
if (-not (Test-Path $PdfPath)) {
    Write-Host "ERROR: PDF file not found: $PdfPath" -ForegroundColor Red
    exit 1
}

# Get repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

# Check if venv_ingest exists
$venvPath = Join-Path $repoRoot "venv_ingest"
if (-not (Test-Path $venvPath)) {
    Write-Host "ERROR: venv_ingest not found at: $venvPath" -ForegroundColor Red
    Write-Host "Please create it first:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv_ingest" -ForegroundColor Yellow
    Write-Host "  .\venv_ingest\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements_ingest.txt" -ForegroundColor Yellow
    exit 1
}

# Set default OpenSearch URL if not provided
if (-not $OpenSearchUrl) {
    $OpenSearchUrl = "http://localhost:9200"
}

Write-Host "Configuration:" -ForegroundColor Green
Write-Host "  PDF: $PdfPath" -ForegroundColor Gray
Write-Host "  Index: $IndexName" -ForegroundColor Gray
Write-Host "  OpenSearch: $OpenSearchUrl" -ForegroundColor Gray
Write-Host "  Batch Size: $BatchSize" -ForegroundColor Gray
Write-Host ""

# Activate venv_ingest
Write-Host "Switching to ingestion environment (venv_ingest)..." -ForegroundColor Yellow
& "$venvPath\Scripts\Activate.ps1"

try {
    # Step 1: Update OpenSearch mapping (add tag fields if needed)
    Write-Host ""
    Write-Host "[1/3] Updating OpenSearch mapping..." -ForegroundColor Cyan
    $mappingScript = Join-Path $repoRoot "scripts\opensearch\update_mapping_add_tags.py"
    if (Test-Path $mappingScript) {
        python $mappingScript --host $OpenSearchUrl --index $IndexName
        if ($LASTEXITCODE -ne 0) {
            Write-Host "WARNING: Mapping update failed, but continuing..." -ForegroundColor Yellow
        }
    } else {
        Write-Host "WARNING: Mapping script not found, skipping..." -ForegroundColor Yellow
    }

    # Step 2: Ingest PDF
    Write-Host ""
    Write-Host "[2/3] Ingesting PDF with PaddleOCR..." -ForegroundColor Cyan
    $ingestScript = Join-Path $repoRoot "tools\ingest_single_pdf.py"
    python $ingestScript --pdf $PdfPath --index $IndexName --batch-size $BatchSize

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Ingestion failed!" -ForegroundColor Red
        exit 1
    }

    # Step 3: Verify tags
    Write-Host ""
    Write-Host "[3/3] Verifying tags in index..." -ForegroundColor Cyan
    $verifyScript = Join-Path $repoRoot "tools\verify_tags_in_index.py"
    if (Test-Path $verifyScript) {
        python $verifyScript --host $OpenSearchUrl --index $IndexName --sample 10
    } else {
        Write-Host "WARNING: Verify script not found, skipping..." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "SUCCESS! PDF ingested successfully" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now start the API server:" -ForegroundColor Yellow
    Write-Host "  .\launchers\start_api.ps1" -ForegroundColor Cyan
}
catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    # Deactivate venv_ingest
    Write-Host ""
    Write-Host "Returning to base environment..." -ForegroundColor Yellow
    deactivate
}
