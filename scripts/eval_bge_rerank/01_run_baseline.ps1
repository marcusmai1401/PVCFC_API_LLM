#!/usr/bin/env pwsh
# Run baseline evaluation (no BGE reranking)

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "BGE RERANK EVALUATION - BASELINE RUN" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Set baseline config (disable BGE rerank)
$env:ENABLE_BGE_RERANK = "false"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  ENABLE_BGE_RERANK: $env:ENABLE_BGE_RERANK" -ForegroundColor White
Write-Host ""

# Ensure API is running
Write-Host "Checking API status..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✓ API is running" -ForegroundColor Green
} catch {
    Write-Host "✗ API is not running!" -ForegroundColor Red
    Write-Host "Please start the API first with: .\start_api_debug.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Run baseline queries
$inputFile = "artifacts/qa/filtered_qa_set.jsonl"
$outputFile = "artifacts/eval/run_baseline.jsonl"
$limit = 30

Write-Host "Running batch queries..." -ForegroundColor Yellow
Write-Host "  Input: $inputFile" -ForegroundColor White
Write-Host "  Output: $outputFile" -ForegroundColor White
Write-Host "  Limit: $limit queries" -ForegroundColor White
Write-Host ""

python tools/batch_query_runner.py `
    --input $inputFile `
    --output $outputFile `
    --limit $limit `
    --max-context 10 `
    --execution-mode heavy_only

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host "✓ BASELINE RUN COMPLETE" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host ""
    Write-Host "Results saved to: $outputFile" -ForegroundColor White
    Write-Host ""
    Write-Host "Next step: Run BGE rerank with:" -ForegroundColor Yellow
    Write-Host "  .\scripts\eval_bge_rerank\02_run_bge_chunk.ps1" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Red
    Write-Host "✗ BASELINE RUN FAILED" -ForegroundColor Red
    Write-Host "=" * 80 -ForegroundColor Red
    exit 1
}
