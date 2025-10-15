#!/usr/bin/env pwsh
# Run BGE reranking evaluation (doc-level with aggregation)

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "BGE RERANK EVALUATION - DOC-LEVEL RERANKING" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Set BGE rerank config (doc-level)
$env:ENABLE_BGE_RERANK = "true"
$env:BGE_RERANK_LEVEL = "doc"
$env:BGE_RERANK_TOP_K = "10"
$env:BGE_RERANK_CANDIDATE_LIMIT = "50"
$env:BGE_RERANK_AGGREGATION = "top3_mean"
$env:RERANKER_MODEL = "BAAI/bge-reranker-base"
$env:RERANKER_BATCH_SIZE = "32"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  ENABLE_BGE_RERANK: $env:ENABLE_BGE_RERANK" -ForegroundColor White
Write-Host "  BGE_RERANK_LEVEL: $env:BGE_RERANK_LEVEL" -ForegroundColor White
Write-Host "  BGE_RERANK_TOP_K: $env:BGE_RERANK_TOP_K" -ForegroundColor White
Write-Host "  BGE_RERANK_CANDIDATE_LIMIT: $env:BGE_RERANK_CANDIDATE_LIMIT" -ForegroundColor White
Write-Host "  BGE_RERANK_AGGREGATION: $env:BGE_RERANK_AGGREGATION" -ForegroundColor White
Write-Host "  RERANKER_MODEL: $env:RERANKER_MODEL" -ForegroundColor White
Write-Host "  RERANKER_BATCH_SIZE: $env:RERANKER_BATCH_SIZE" -ForegroundColor White
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

# Run BGE doc-level rerank queries
$inputFile = "artifacts/qa/filtered_qa_set.jsonl"
$outputFile = "artifacts/eval/run_bge_doc.jsonl"
$limit = 30

Write-Host "Running batch queries with doc-level BGE reranking..." -ForegroundColor Yellow
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
    Write-Host "✓ BGE DOC-LEVEL RERANK RUN COMPLETE" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host ""
    Write-Host "Results saved to: $outputFile" -ForegroundColor White
    Write-Host ""
    Write-Host "Next step: Compare all results with:" -ForegroundColor Yellow
    Write-Host "  .\scripts\eval_bge_rerank\04_compare_results.ps1" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Red
    Write-Host "✗ BGE DOC-LEVEL RERANK RUN FAILED" -ForegroundColor Red
    Write-Host "=" * 80 -ForegroundColor Red
    exit 1
}
