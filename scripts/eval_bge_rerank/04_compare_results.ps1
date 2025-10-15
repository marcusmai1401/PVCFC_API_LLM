#!/usr/bin/env pwsh
# Compare baseline vs BGE reranking results

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "BGE RERANK EVALUATION - COMPARISON" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

$baselineFile = "artifacts/eval/run_baseline.jsonl"
$rerankFile = "artifacts/eval/run_bge_chunk.jsonl"
$outputFile = "artifacts/eval/comparison_baseline_vs_chunk.json"

# Check if baseline exists
if (-not (Test-Path $baselineFile)) {
    Write-Host "✗ Baseline results not found: $baselineFile" -ForegroundColor Red
    Write-Host "Please run baseline first: .\scripts\eval_bge_rerank\01_run_baseline.ps1" -ForegroundColor Yellow
    exit 1
}

# Check if rerank exists
if (-not (Test-Path $rerankFile)) {
    Write-Host "✗ Rerank results not found: $rerankFile" -ForegroundColor Red
    Write-Host "Please run rerank first: .\scripts\eval_bge_rerank\02_run_bge_chunk.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "Comparing results..." -ForegroundColor Yellow
Write-Host "  Baseline: $baselineFile" -ForegroundColor White
Write-Host "  Rerank: $rerankFile" -ForegroundColor White
Write-Host "  Output: $outputFile" -ForegroundColor White
Write-Host ""

python tools/evaluate_rerank_results.py `
    --baseline $baselineFile `
    --rerank $rerankFile `
    --output $outputFile

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host "✓ COMPARISON COMPLETE" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host ""
    Write-Host "Detailed report saved to: $outputFile" -ForegroundColor White
    Write-Host ""
    Write-Host "To view the report:" -ForegroundColor Yellow
    Write-Host "  Get-Content $outputFile | ConvertFrom-Json | ConvertTo-Json -Depth 10" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Red
    Write-Host "✗ COMPARISON FAILED" -ForegroundColor Red
    Write-Host "=" * 80 -ForegroundColor Red
    exit 1
}

# Optional: Compare doc-level if it exists
$docRerankFile = "artifacts/eval/run_bge_doc.jsonl"
if (Test-Path $docRerankFile) {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "BONUS: Comparing doc-level reranking..." -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host ""

    $docOutputFile = "artifacts/eval/comparison_baseline_vs_doc.json"

    python tools/evaluate_rerank_results.py `
        --baseline $baselineFile `
        --rerank $docRerankFile `
        --output $docOutputFile

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✓ Doc-level comparison saved to: $docOutputFile" -ForegroundColor Green
    }
}
