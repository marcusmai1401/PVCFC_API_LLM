#!/usr/bin/env pwsh
# Master script to run full BGE reranking evaluation

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Magenta
Write-Host "BGE CROSSENCODER RERANKING - FULL EVALUATION" -ForegroundColor Magenta
Write-Host "=" * 80 -ForegroundColor Magenta
Write-Host ""
Write-Host "This script will:" -ForegroundColor Yellow
Write-Host "  1. Run baseline (no reranking)" -ForegroundColor White
Write-Host "  2. Run BGE chunk-level reranking" -ForegroundColor White
Write-Host "  3. Compare results and generate recommendation" -ForegroundColor White
Write-Host ""
Write-Host "Estimated time: ~10-15 minutes (30 queries × 2 runs)" -ForegroundColor Yellow
Write-Host ""

# Check if API is running
Write-Host "Pre-flight check..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✓ API is running" -ForegroundColor Green
} catch {
    Write-Host "✗ API is not running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start the API first:" -ForegroundColor Yellow
    Write-Host "  .\start_api_debug.ps1" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

Write-Host ""
Read-Host "Press Enter to start evaluation (Ctrl+C to cancel)"

# Step 1: Baseline
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "STEP 1/3: Running baseline" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

& "$PSScriptRoot\01_run_baseline.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ Baseline failed. Aborting." -ForegroundColor Red
    exit 1
}

# Step 2: BGE chunk-level rerank
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "STEP 2/3: Running BGE chunk-level reranking" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

& "$PSScriptRoot\02_run_bge_chunk.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ BGE reranking failed. Aborting." -ForegroundColor Red
    exit 1
}

# Step 3: Compare
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "STEP 3/3: Comparing results" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

& "$PSScriptRoot\04_compare_results.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ Comparison failed." -ForegroundColor Red
    exit 1
}

# Success!
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Green
Write-Host "✓ FULL EVALUATION COMPLETE" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green
Write-Host ""
Write-Host "📊 Results:" -ForegroundColor Yellow
Write-Host "  - Baseline: artifacts/eval/run_baseline.jsonl" -ForegroundColor White
Write-Host "  - Rerank: artifacts/eval/run_bge_chunk.jsonl" -ForegroundColor White
Write-Host "  - Report: artifacts/eval/comparison_baseline_vs_chunk.json" -ForegroundColor White
Write-Host ""
Write-Host "📖 Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review the comparison report above" -ForegroundColor White
Write-Host "  2. Check the recommendation (enable/disable)" -ForegroundColor White
Write-Host "  3. Update .env if enabling reranking" -ForegroundColor White
Write-Host "  4. Read docs/BGE_RERANKING_EVALUATION_GUIDE.md for details" -ForegroundColor White
Write-Host ""
Write-Host "To view full report:" -ForegroundColor Cyan
Write-Host "  Get-Content artifacts/eval/comparison_baseline_vs_chunk.json | ConvertFrom-Json | ConvertTo-Json -Depth 10" -ForegroundColor White
Write-Host ""
