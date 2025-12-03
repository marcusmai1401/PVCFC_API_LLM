# P&ID Retrieval Enhancement - Setup Script
# Runs all necessary steps to enable P&ID enhancement

param(
    [switch]$DryRun,
    [switch]$SkipBackfill
)

Write-Host "=" -ForegroundColor Cyan -NoNewline; Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "P&ID RETRIEVAL ENHANCEMENT - SETUP" -ForegroundColor Cyan
Write-Host "=" -ForegroundColor Cyan -NoNewline; Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify environment
Write-Host "[Step 1/4] Verifying environment..." -ForegroundColor Yellow

# Check OpenSearch
try {
    $osHealth = Invoke-RestMethod -Uri "http://localhost:9200/_cluster/health" -ErrorAction Stop
    Write-Host "  ✓ OpenSearch: " -NoNewline -ForegroundColor Green
    Write-Host $osHealth.status
} catch {
    Write-Host "  ✗ OpenSearch not available" -ForegroundColor Red
    Write-Host "    Please start OpenSearch first" -ForegroundColor Red
    exit 1
}

# Check Weaviate
try {
    $wvReady = Invoke-RestMethod -Uri "http://localhost:8080/v1/.well-known/ready" -ErrorAction Stop
    Write-Host "  ✓ Weaviate: Ready" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Weaviate not available" -ForegroundColor Red
    Write-Host "    Please start Weaviate first" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 2: Update OpenSearch mapping
Write-Host "[Step 2/4] Updating OpenSearch mapping..." -ForegroundColor Yellow
python scripts\opensearch\update_tags_mapping.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ OpenSearch mapping update failed" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 3: Update Weaviate schema
Write-Host "[Step 3/4] Updating Weaviate schema..." -ForegroundColor Yellow
python scripts\weaviate\add_tags_property.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Weaviate schema update failed" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 4: Backfill tags
if (-not $SkipBackfill) {
    Write-Host "[Step 4/4] Backfilling tags to indexes..." -ForegroundColor Yellow

    if ($DryRun) {
        Write-Host "  (Dry run mode)" -ForegroundColor Cyan
        python scripts\utilities\backfill_tags.py --dry-run
    } else {
        python scripts\utilities\backfill_tags.py
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ Backfill failed" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[Step 4/4] Skipping backfill (--SkipBackfill flag)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" -ForegroundColor Green -NoNewline; Write-Host ("=" * 79) -ForegroundColor Green
Write-Host "SETUP COMPLETE" -ForegroundColor Green
Write-Host "=" -ForegroundColor Green -NoNewline; Write-Host ("=" * 79) -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Update .env with P&ID settings (see env.example)"
Write-Host "  2. Run evaluation: python tests\eval_pid_retrieval.py"
Write-Host "  3. Test with real queries in your application"
Write-Host ""
