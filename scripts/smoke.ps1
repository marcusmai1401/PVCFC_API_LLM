# PVCFC RAG API - Smoke Test
# PowerShell script tương đương với `make smoke`

Write-Host "Running smoke tests..." -ForegroundColor Blue

# Kiểm tra virtual environment
if (!(Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run .\scripts\dev.ps1 first" -ForegroundColor Red
    exit 1
}

# Load environment variables từ .env nếu có
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^([^#].*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

# Kiểm tra LLM provider settings
$llmProvider = if ($env:LLM_PROVIDER) { $env:LLM_PROVIDER } else { "none" }
$openaiKey = $env:OPENAI_API_KEY
$geminiKey = $env:GEMINI_API_KEY

Write-Host "LLM Provider: $llmProvider" -ForegroundColor Cyan

if ($llmProvider -eq "none") {
    Write-Host "LLM Provider set to 'none' - skipping connection tests" -ForegroundColor Yellow
    Write-Host "Configure LLM_PROVIDER and API keys in .env to test connections" -ForegroundColor Cyan
    exit 0
}

# Kiểm tra API keys
$hasKeys = $false
if ($llmProvider -eq "openai" -and $openaiKey) {
    Write-Host "OpenAI API key found" -ForegroundColor Green
    $hasKeys = $true
} elseif ($llmProvider -eq "gemini" -and $geminiKey) {
    Write-Host "Gemini API key found" -ForegroundColor Green
    $hasKeys = $true
}

if (-not $hasKeys) {
    Write-Host "No valid API keys found for provider: $llmProvider" -ForegroundColor Yellow
    Write-Host "Add your API key to .env file" -ForegroundColor Cyan
    exit 0
}

# TODO: Implement actual LLM connection test
Write-Host "LLM connection test will be implemented in future phases" -ForegroundColor Yellow
Write-Host "Smoke test completed (placeholder)" -ForegroundColor Green
