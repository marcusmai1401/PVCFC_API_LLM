# PVCFC RAG - V1 Ingestion & Index Pipeline
# PowerShell script to run complete ingestion and indexing process

param(
    [string]$SourceDir = "D:\Data_Raw",
    [string]$OutputDir = "artifacts\ingestion",
    [switch]$EnableOCR = $true,
    [string]$OcrLang = "vie+eng",
    [int]$ChunkSize = 1000,
    [int]$ChunkOverlap = 200,
    [string]$EmbeddingModel = "intfloat/multilingual-e5-small",
    [switch]$SkipIngest = $false,
    [switch]$SkipBM25 = $false,
    [switch]$SkipFAISS = $false
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Colors for output
function Write-ColorOutput([string]$Message, [string]$Color = "Green") {
    Write-Host $Message -ForegroundColor $Color
}

# Banner
Write-ColorOutput "========================================" "Cyan"
Write-ColorOutput "  PVCFC RAG V1 - Ingest & Index Pipeline" "Cyan"
Write-ColorOutput "========================================" "Cyan"
Write-Host ""

# Display configuration
Write-ColorOutput "Configuration:" "Yellow"
Write-Host "Source Directory: $SourceDir"
Write-Host "Output Directory: $OutputDir"
Write-Host "OCR Enabled: $EnableOCR"
Write-Host "OCR Languages: $OcrLang"
Write-Host "Chunk Size: $ChunkSize"
Write-Host "Chunk Overlap: $ChunkOverlap"
Write-Host "Embedding Model: $EmbeddingModel"
Write-Host ""

# Check if source directory exists
if (-not (Test-Path $SourceDir)) {
    Write-ColorOutput "ERROR: Source directory does not exist: $SourceDir" "Red"
    exit 1
}

# Check Python availability
try {
    $pythonVersion = python --version 2>&1
    Write-ColorOutput "Python: $pythonVersion" "Green"
} catch {
    Write-ColorOutput "ERROR: Python not found in PATH" "Red"
    exit 1
}

# Step 1: Ingest PDFs
if (-not $SkipIngest) {
    Write-ColorOutput "`n[Step 1/3] Running Ingestion Pipeline..." "Yellow"
    Write-ColorOutput "========================================" "Yellow"

$ocrFlag = @()
if ($EnableOCR) { $ocrFlag = @('--enable-ocr') }

$ingestArgs = @(
    'tools\\ingest.py',
    '--source-dir', $SourceDir,
    '--output-dir', $OutputDir
) + $ocrFlag + @(
    '--ocr-lang', $OcrLang,
    '--parser', 'auto',
    '--chunk-size', $ChunkSize,
    '--chunk-overlap', $ChunkOverlap,
    '--emit-jsonl'
)

Write-Host "Command: python $($ingestArgs -join ' ')" -ForegroundColor Gray

try {
    & python @ingestArgs
    Write-ColorOutput "✓ Ingestion completed successfully" "Green"
} catch {
    Write-ColorOutput "✗ Ingestion failed: $_" "Red"
    exit 1
}
} else {
    Write-ColorOutput "`n[Step 1/3] Skipping Ingestion (using existing data)" "Gray"
}

# Check if chunks were created
$chunksFile = Join-Path $OutputDir "chunks\chunks.jsonl"
if (-not (Test-Path $chunksFile)) {
    Write-ColorOutput "ERROR: Chunks file not found: $chunksFile" "Red"
    Write-ColorOutput "Please run ingestion first" "Red"
    exit 1
}

# Step 2: Build BM25 Index
if (-not $SkipBM25) {
    Write-ColorOutput "`n[Step 2/3] Building BM25 Index..." "Yellow"
    Write-ColorOutput "========================================" "Yellow"

$bm25Args = @(
    'tools\\build_bm25_index.py',
    '--chunks-jsonl', $chunksFile,
    '--index-dir', 'artifacts\\index\\bm25'
)

Write-Host "Command: python $($bm25Args -join ' ')" -ForegroundColor Gray

try {
    & python @bm25Args
    Write-ColorOutput "✓ BM25 index built successfully" "Green"
} catch {
    Write-ColorOutput "✗ BM25 index build failed: $_" "Red"
    exit 1
}
} else {
    Write-ColorOutput "`n[Step 2/3] Skipping BM25 Index (using existing index)" "Gray"
}

# Step 3: Build FAISS Index
if (-not $SkipFAISS) {
    Write-ColorOutput "`n[Step 3/3] Building FAISS Index..." "Yellow"
    Write-ColorOutput "========================================" "Yellow"

    # Check memory before FAISS
    $memInfo = Get-WmiObject Win32_OperatingSystem
    $totalMemGB = [math]::Round($memInfo.TotalVisibleMemorySize / 1MB, 2)
    $freeMemGB = [math]::Round($memInfo.FreePhysicalMemory / 1MB, 2)
    Write-Host "Memory: $freeMemGB GB free of $totalMemGB GB total" -ForegroundColor Cyan

    if ($freeMemGB -lt 4) {
        Write-ColorOutput "WARNING: Low memory ($freeMemGB GB). FAISS build may be slow." "Yellow"
    }

$faissArgs = @(
    'tools\\build_faiss_local.py',
    '--bm25-dir', 'artifacts\\index\\bm25',
    '--faiss-dir', 'artifacts\\index\\faiss',
    '--embedding_model', $EmbeddingModel,
    '--max-memory-gb', '10.0'
)

Write-Host "Command: python $($faissArgs -join ' ')" -ForegroundColor Gray

try {
    & python @faissArgs
    Write-ColorOutput "✓ FAISS index built successfully" "Green"
} catch {
    Write-ColorOutput "✗ FAISS index build failed: $_" "Red"
    exit 1
}
} else {
    Write-ColorOutput "`n[Step 3/3] Skipping FAISS Index (using existing index)" "Gray"
}

# Summary
Write-ColorOutput "`n========================================" "Cyan"
Write-ColorOutput "         Pipeline Complete!" "Cyan"
Write-ColorOutput "========================================" "Cyan"

# Check outputs
Write-ColorOutput "`nOutput Summary:" "Yellow"

# Check doc_id_map
$docIdMapFile = Join-Path $OutputDir "doc_id_map.json"
if (Test-Path $docIdMapFile) {
    $docIdMap = Get-Content $docIdMapFile | ConvertFrom-Json
    $docCount = ($docIdMap | Get-Member -MemberType NoteProperty).Count
    Write-Host "✓ Document ID Map: $docCount documents" -ForegroundColor Green
} else {
    Write-Host "✗ Document ID Map not found" -ForegroundColor Red
}

# Check chunks
if (Test-Path $chunksFile) {
    $chunkCount = (Get-Content $chunksFile | Measure-Object).Count
    Write-Host "✓ Chunks: $chunkCount chunks" -ForegroundColor Green
} else {
    Write-Host "✗ Chunks not found" -ForegroundColor Red
}

# Check BM25
$bm25Dir = "artifacts\index\bm25"
if (Test-Path "$bm25Dir\metadata.json") {
    Write-Host "✓ BM25 Index: Ready" -ForegroundColor Green
} else {
    Write-Host "✗ BM25 Index not found" -ForegroundColor Red
}

# Check FAISS
$faissDir = "artifacts\index\faiss"
if ((Test-Path "$faissDir\index.faiss") -or (Test-Path "$faissDir\embeddings.npy")) {
    Write-Host "✓ FAISS Index: Ready" -ForegroundColor Green
} else {
    Write-Host "✗ FAISS Index not found" -ForegroundColor Red
}

# Check quarantine
$quarantineFile = Join-Path $OutputDir "quarantine.jsonl"
if (Test-Path $quarantineFile) {
    $quarantineCount = (Get-Content $quarantineFile | Measure-Object).Count
    if ($quarantineCount -gt 0) {
        Write-ColorOutput "`n⚠ Quarantined files: $quarantineCount" "Yellow"
        Write-Host "  Check $quarantineFile for details" -ForegroundColor Gray
    }
}

# Check dedup report
$dedupReport = Join-Path $OutputDir "manifests\dedup_report.json"
if (Test-Path $dedupReport) {
    $dedup = Get-Content $dedupReport | ConvertFrom-Json
    if ($dedup.total_duplicates -gt 0) {
        Write-ColorOutput "`nℹ Duplicates found: $($dedup.total_duplicates) files" "Cyan"
        Write-Host "  Check $dedupReport for details" -ForegroundColor Gray
    }
}

Write-ColorOutput "`n✅ Pipeline execution completed!" "Green"
Write-Host ""

# Prompt to start API
$response = Read-Host "Do you want to start the API server? (Y/N)"
if ($response -eq 'Y' -or $response -eq 'y') {
    Write-ColorOutput "`nStarting API server..." "Yellow"
    & ".\start_api.ps1"
}
