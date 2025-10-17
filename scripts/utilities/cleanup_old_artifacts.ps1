# ============================================================================
# Cleanup Old Artifacts - Safe Cleanup Script
# ============================================================================
# Purpose: Remove old backups, test folders, and obsolete files
# Usage: .\scripts\utilities\cleanup_old_artifacts.ps1 [-Phase 1|2|3]
# ============================================================================

param(
    [ValidateSet("1", "2", "3", "All")]
    [string]$Phase = "1",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "ARTIFACTS CLEANUP UTILITY" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Get project root
$ProjectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$ArtifactsDir = Join-Path $ProjectRoot "artifacts"

if (-not (Test-Path $ArtifactsDir)) {
    Write-Host "[ERROR] Artifacts directory not found: $ArtifactsDir" -ForegroundColor Red
    exit 1
}

Write-Host "Artifacts Directory: $ArtifactsDir" -ForegroundColor Yellow
Write-Host "Phase: $Phase" -ForegroundColor Yellow
Write-Host "Dry Run: $DryRun" -ForegroundColor Yellow
Write-Host ""

# Helper function to safely delete
function Remove-SafelyWithReport {
    param(
        [string]$Path,
        [string]$Description,
        [bool]$IsDryRun
    )

    if (Test-Path $Path) {
        $size = (Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum).Sum
        $sizeMB = [math]::Round($size / 1MB, 2)

        if ($IsDryRun) {
            Write-Host "  [DRY RUN] Would delete: $Description ($sizeMB MB)" -ForegroundColor Yellow
        } else {
            try {
                Remove-Item -Path $Path -Recurse -Force -ErrorAction Stop
                Write-Host "  [OK] Deleted: $Description ($sizeMB MB)" -ForegroundColor Green
                return $sizeMB
            } catch {
                Write-Host "  [ERROR] Failed to delete: $Description - $_" -ForegroundColor Red
                return 0
            }
        }
    } else {
        Write-Host "  [SKIP] Not found: $Description" -ForegroundColor Gray
    }
    return 0
}

$totalSaved = 0

# ============================================================================
# PHASE 1: Safe Cleanup (Old Backups + Obsolete)
# ============================================================================

if ($Phase -eq "1" -or $Phase -eq "All") {
    Write-Host ""
    Write-Host "[PHASE 1] Cleaning old backups and obsolete folders..." -ForegroundColor Green
    Write-Host ""

    # Old backups (> 1 week)
    $phase1Items = @(
        @{Path="ingestion_production_backup_20251009_181153"; Desc="Old ingestion backup (Oct 9)"},
        @{Path="index_backup_before_phase1_fix_20251001_161503"; Desc="Old index backup (Oct 1)"},
        @{Path="index_production_backup_20251009_181821"; Desc="Old index backup (Oct 9)"}
    )

    # Obsolete folders
    $obsolete = @(
        @{Path="chroma_db"; Desc="Chroma DB (not used)"},
        @{Path="faiss"; Desc="Empty FAISS folder"},
        @{Path="bm25"; Desc="Empty BM25 folder"}
    )

    # Empty/obsolete files
    $obsoleteFiles = @(
        @{Path="gemini_models.json"; Desc="Empty gemini_models.json"}
    )

    Write-Host "Cleaning old backups:" -ForegroundColor Yellow
    foreach ($item in $phase1Items) {
        $fullPath = Join-Path $ArtifactsDir $item.Path
        $totalSaved += Remove-SafelyWithReport -Path $fullPath -Description $item.Desc -IsDryRun $DryRun
    }

    Write-Host ""
    Write-Host "Cleaning obsolete folders:" -ForegroundColor Yellow
    foreach ($item in $obsolete) {
        $fullPath = Join-Path $ArtifactsDir $item.Path
        $totalSaved += Remove-SafelyWithReport -Path $fullPath -Description $item.Desc -IsDryRun $DryRun
    }

    Write-Host ""
    Write-Host "Cleaning obsolete files:" -ForegroundColor Yellow
    foreach ($item in $obsoleteFiles) {
        $fullPath = Join-Path $ArtifactsDir $item.Path
        $totalSaved += Remove-SafelyWithReport -Path $fullPath -Description $item.Desc -IsDryRun $DryRun
    }

    Write-Host ""
    Write-Host "[OK] Phase 1 complete - Estimated savings: ~280MB" -ForegroundColor Green
}

# ============================================================================
# PHASE 2: Aggressive Cleanup (Test/Benchmark Folders)
# ============================================================================

if ($Phase -eq "2" -or $Phase -eq "All") {
    Write-Host ""
    Write-Host "[PHASE 2] Cleaning test and benchmark folders..." -ForegroundColor Green
    Write-Host ""

    # Test folders
    $testPatterns = @("test_*", "bench_*", "perf_*")

    foreach ($pattern in $testPatterns) {
        Write-Host "Searching for: $pattern" -ForegroundColor Yellow
        $folders = Get-ChildItem -Path $ArtifactsDir -Directory -Filter $pattern -ErrorAction SilentlyContinue

        foreach ($folder in $folders) {
            $totalSaved += Remove-SafelyWithReport -Path $folder.FullName -Description $folder.Name -IsDryRun $DryRun
        }
    }

    # Specific test folders
    $specificTest = @(
        "ingestion",
        "chunks",
        "eval",
        "qa",
        "tmp",
        "p2_test",
        "version_test",
        "evaluation_results"
    )

    Write-Host ""
    Write-Host "Cleaning specific test folders:" -ForegroundColor Yellow
    foreach ($folder in $specificTest) {
        $fullPath = Join-Path $ArtifactsDir $folder
        $totalSaved += Remove-SafelyWithReport -Path $fullPath -Description $folder -IsDryRun $DryRun
    }

    Write-Host ""
    Write-Host "[OK] Phase 2 complete - Estimated savings: ~165MB" -ForegroundColor Green
}

# ============================================================================
# PHASE 3: Recent Backup (Wait 1 week before running)
# ============================================================================

if ($Phase -eq "3" -or $Phase -eq "All") {
    Write-Host ""
    Write-Host "[PHASE 3] Cleaning recent backup (Oct 15)..." -ForegroundColor Green
    Write-Host ""

    $recentBackup = "ingestion_backup_20251015_063804"
    $backupDate = [DateTime]::ParseExact("20251015", "yyyyMMdd", $null)
    $daysSince = (Get-Date) - $backupDate

    Write-Host "Backup age: $($daysSince.Days) days" -ForegroundColor Cyan

    if ($daysSince.Days -lt 7 -and -not $DryRun) {
        Write-Host "[WARN] Backup is less than 1 week old!" -ForegroundColor Yellow
        Write-Host "       Recommended to wait until: $($backupDate.AddDays(7).ToString('yyyy-MM-dd'))" -ForegroundColor Yellow
        Write-Host ""

        $confirm = Read-Host "Delete anyway? (y/N)"
        if ($confirm -ne "y") {
            Write-Host "[SKIP] Keeping recent backup for safety" -ForegroundColor Gray
            return
        }
    }

    $fullPath = Join-Path $ArtifactsDir $recentBackup
    $totalSaved += Remove-SafelyWithReport -Path $fullPath -Description "Recent backup (Oct 15)" -IsDryRun $DryRun

    Write-Host ""
    Write-Host "[OK] Phase 3 complete - Estimated savings: ~282MB" -ForegroundColor Green
}

# ============================================================================
# Summary
# ============================================================================

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "CLEANUP SUMMARY" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

if ($DryRun) {
    Write-Host "[DRY RUN MODE] No files were actually deleted" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Estimated savings: $([math]::Round($totalSaved, 2)) MB" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Run without -DryRun to perform actual cleanup:" -ForegroundColor Yellow
    Write-Host "  .\scripts\utilities\cleanup_old_artifacts.ps1 -Phase $Phase" -ForegroundColor Gray
} else {
    Write-Host "Space freed: $([math]::Round($totalSaved, 2)) MB" -ForegroundColor Green
    Write-Host ""
    Write-Host "[OK] Cleanup complete!" -ForegroundColor Green
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
