# Start API with DEBUG logging enabled for citation debugging
Write-Host "Setting DEBUG logging level..." -ForegroundColor Green
$env:LOGURU_LEVEL = "DEBUG"

Write-Host "Starting API with enhanced debug logging..." -ForegroundColor Green
Write-Host "Watch for logs showing:" -ForegroundColor Yellow
Write-Host "  - 'Prepared LLM context' (what docs were sent to LLM)" -ForegroundColor Yellow
Write-Host "  - 'Doc mapping summary' (which [Doc N] maps to which doc_id)" -ForegroundColor Yellow
Write-Host "  - 'Prompt preview' and 'Answer preview' (LLM input/output)" -ForegroundColor Yellow
Write-Host "  - 'Parsed citations' (final citations with doc_id + page + pdf_path)" -ForegroundColor Yellow
Write-Host ""

# Start API
.\launchers\start_api.ps1
