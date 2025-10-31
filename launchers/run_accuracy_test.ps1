# PowerShell launcher for RAG Accuracy Test
# Run from project root with: .\launchers\run_accuracy_test.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RAG API Accuracy Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment is activated
if (-not $env:VIRTUAL_ENV) {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & ".\.venv\Scripts\Activate.ps1"
}

Write-Host "Running test suite..." -ForegroundColor Green
Write-Host ""

# Run the test
python tests\integration\test_query_classification_accuracy.py

$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "✓ Test suite completed successfully!" -ForegroundColor Green
} else {
    Write-Host "✗ Test suite failed or had errors" -ForegroundColor Red
}

Write-Host ""
Write-Host "Test reports saved to: artifacts\test_reports\" -ForegroundColor Cyan

exit $exitCode
