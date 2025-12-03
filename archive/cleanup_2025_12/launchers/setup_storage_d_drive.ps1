# ============================================================================
# Quick Launcher: Setup Artifacts Storage on D Drive
# ============================================================================
# Purpose: One-click setup for CAD-like tag extraction storage requirements
# Usage: .\launchers\setup_storage_d_drive.ps1
# ============================================================================

param(
    [switch]$TestOnly
)

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     PVCFC - Artifacts Storage Setup (D Drive)                     ║" -ForegroundColor Cyan
Write-Host "║     CAD-like Tag Extraction Preparation                           ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Get project root
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$MigrationScript = Join-Path $ProjectRoot "scripts\utilities\migrate_artifacts_to_d_drive.ps1"
$VerifyScript = Join-Path $ProjectRoot "scripts\utilities\verify_artifacts_location.ps1"

if (-not (Test-Path $MigrationScript)) {
    Write-Host "❌ Migration script not found: $MigrationScript" -ForegroundColor Red
    exit 1
}

# Step 1: Info
Write-Host "📋 What this does:" -ForegroundColor Yellow
Write-Host "   1. Test D: drive accessibility and performance" -ForegroundColor White
Write-Host "   2. Migrate existing artifacts (if any)" -ForegroundColor White
Write-Host "   3. Configure ARTIFACTS_DIR=D:\PVCFC_Artifacts in .env" -ForegroundColor White
Write-Host "   4. Verify setup is correct" -ForegroundColor White
Write-Host ""

Write-Host "💡 Why D: drive?" -ForegroundColor Yellow
Write-Host "   • CAD-like tag extraction needs ~4-8GB for artifacts" -ForegroundColor White
Write-Host "   • Crops: ~2-5GB (PNG images of each tag)" -ForegroundColor White
Write-Host "   • Layouts: ~500MB-1GB (JSON vector drawings)" -ForegroundColor White
Write-Host "   • D: drive has more space, easier to manage" -ForegroundColor White
Write-Host ""

if ($TestOnly) {
    Write-Host "🧪 Running in TEST MODE (safe, no changes)" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "⚠️  This will update your .env file" -ForegroundColor Yellow
    Write-Host "   (Backup will be created automatically)" -ForegroundColor Gray
    Write-Host ""

    $confirm = Read-Host "Continue? (Y/n)"
    if ($confirm -eq "n" -or $confirm -eq "N") {
        Write-Host "Cancelled by user." -ForegroundColor Yellow
        exit 0
    }
}

# Step 2: Run migration
Write-Host ""
Write-Host "🚀 Running migration script..." -ForegroundColor Green
Write-Host ""

if ($TestOnly) {
    & $MigrationScript -TestOnly
} else {
    & $MigrationScript
}

$migrationExitCode = $LASTEXITCODE

if ($migrationExitCode -ne 0) {
    Write-Host ""
    Write-Host "❌ Migration encountered errors. Please check output above." -ForegroundColor Red
    exit $migrationExitCode
}

# Step 3: Verify (only if not test mode)
if (-not $TestOnly) {
    Write-Host ""
    Write-Host "✅ Migration completed! Running verification..." -ForegroundColor Green
    Write-Host ""

    & $VerifyScript

    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║     ✓ Setup Complete!                                             ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""

    Write-Host "📚 Next steps:" -ForegroundColor Yellow
    Write-Host "   1. Test with small ingestion:" -ForegroundColor White
    Write-Host "      python tools/ingest.py --source-dir ""D:\Data_Raw\test"" --workers 1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   2. Verify artifacts in D: drive:" -ForegroundColor White
    Write-Host "      ls D:\PVCFC_Artifacts\" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   3. If successful, proceed with CAD-like tag extraction implementation" -ForegroundColor White
    Write-Host ""

    Write-Host "📖 Documentation:" -ForegroundColor Yellow
    Write-Host "   scripts/utilities/README_ARTIFACTS_MIGRATION.md" -ForegroundColor Gray
    Write-Host "   Review_AI.md (Section 7.3 - Storage Configuration)" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "ℹ️  Test completed successfully!" -ForegroundColor Cyan
    Write-Host "   Run without -TestOnly to perform actual migration:" -ForegroundColor White
    Write-Host "   .\launchers\setup_storage_d_drive.ps1" -ForegroundColor Gray
    Write-Host ""
}
