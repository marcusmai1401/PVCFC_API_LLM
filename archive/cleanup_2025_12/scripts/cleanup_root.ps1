# Root Directory Cleanup Script
# Removes htmlcov folders and moves test scripts to archive

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "ROOT DIRECTORY CLEANUP" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

# Step 1: Delete htmlcov folders
Write-Host "[STEP 1] Deleting htmlcov folders..." -ForegroundColor Yellow

$htmlcovFolders = @("htmlcov", "htmlcov_all", "htmlcov_verification", "htmlcov_week3_final")
$deletedCount = 0
$deletedSize = 0

foreach ($folder in $htmlcovFolders) {
    if (Test-Path $folder) {
        $size = (Get-ChildItem $folder -Recurse | Measure-Object -Property Length -Sum).Sum
        Remove-Item -Recurse -Force $folder
        $deletedCount++
        $deletedSize += $size
        Write-Host "  ✓ Deleted: $folder" -ForegroundColor Green
    } else {
        Write-Host "  - Skipped: $folder (not found)" -ForegroundColor Gray
    }
}

Write-Host "  ✅ Deleted $deletedCount folders (~$([math]::Round($deletedSize/1MB, 2)) MB freed)`n" -ForegroundColor Green

# Step 2: Create archive folder
Write-Host "[STEP 2] Creating archive folder..." -ForegroundColor Yellow

$archivePath = "archive\test_scripts_2025_11_01"
if (!(Test-Path $archivePath)) {
    New-Item -ItemType Directory -Path $archivePath -Force | Out-Null
    Write-Host "  ✓ Created: $archivePath`n" -ForegroundColor Green
} else {
    Write-Host "  - Already exists: $archivePath`n" -ForegroundColor Gray
}

# Step 3: Move test scripts
Write-Host "[STEP 3] Moving test scripts to archive..." -ForegroundColor Yellow

$scripts = @(
    "analyze_chunk_sizes.py",
    "check_cad_score.py",
    "check_final_results.py",
    "check_ingestion.py",
    "check_test_results.py",
    "test_chunk_merging.py",
    "test_dotenv.py",
    "test_page_aware_chunking.py",
    "test_page_detection_simple.py",
    "verify_system.py"
)

$movedCount = 0
foreach ($script in $scripts) {
    if (Test-Path $script) {
        Move-Item $script $archivePath -Force
        $movedCount++
        Write-Host "  ✓ Moved: $script" -ForegroundColor Green
    } else {
        Write-Host "  - Skipped: $script (not found)" -ForegroundColor Gray
    }
}

Write-Host "  ✅ Moved $movedCount scripts to archive/`n" -ForegroundColor Green

# Step 4: Create README in archive
Write-Host "[STEP 4] Creating README in archive..." -ForegroundColor Yellow

$readmeContent = @"
# Test Scripts Archive - 2025-11-01

## Purpose

These scripts were used during the chunk merging and ingestion pipeline investigation on 2025-11-01.

## Scripts Included

### Analysis Scripts
- **analyze_chunk_sizes.py** - Analyze chunk size distribution after ingestion
- **check_final_results.py** - Check final ingestion results
- **check_ingestion.py** - Quick ingestion sanity check

### Testing Scripts
- **test_chunk_merging.py** - Test chunk merge logic (small chunks merged with neighbors)
- **test_page_aware_chunking.py** - Test page-aware chunking strategy
- **test_page_detection_simple.py** - Simple page detection test
- **test_dotenv.py** - Test .env file loading

### Verification Scripts
- **check_cad_score.py** - Check CAD-like detection score for P&ID documents
- **check_test_results.py** - Check test output formatting
- **verify_system.py** - System verification and health check

## Investigation Context

**Date**: 2025-11-01
**Issues Addressed**:
- Chunk size distribution problems (too many small chunks)
- CAD-like detection threshold tuning (0.60 → 0.55)
- Chunk merging feature implementation
- Tags preservation fix (.env loading issues)

**Results**:
- ✅ All features verified working
- ✅ Chunk merging successfully deployed
- ✅ CAD-like detection accurate
- ✅ Tags preservation fixed

## Status

All scripts were **one-time verification tools**. Features tested are now in production and working correctly.

**Archived**: 2025-11-01
**Reason**: Cleanup root directory, keep for historical reference
"@

$readmePath = Join-Path $archivePath "README.md"
$readmeContent | Out-File -FilePath $readmePath -Encoding UTF8
Write-Host "  ✓ Created: README.md`n" -ForegroundColor Green

# Step 5: Verification
Write-Host "[STEP 5] Verification..." -ForegroundColor Yellow

# Check htmlcov folders deleted
$remainingHtmlcov = Get-ChildItem htmlcov* -Directory -ErrorAction SilentlyContinue
if ($remainingHtmlcov) {
    Write-Host "  ⚠ Warning: Some htmlcov folders still exist" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ All htmlcov folders deleted" -ForegroundColor Green
}

# Check scripts moved
$archivedItems = Get-ChildItem -Path $archivePath | Measure-Object
Write-Host "  ✓ Archive contains $($archivedItems.Count) items" -ForegroundColor Green

# Check root cleaned
$remainingTestScripts = Get-ChildItem *.py | Where-Object {$_.Name -match "^(test_|check_|analyze_|verify_)"}
if ($remainingTestScripts) {
    Write-Host "  ⚠ Warning: Some test scripts still in root" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ Root directory cleaned of test scripts" -ForegroundColor Green
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "CLEANUP COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deleted:      $deletedCount htmlcov folders" -ForegroundColor Green
Write-Host "Freed space:  $([math]::Round($deletedSize/1MB, 2)) MB" -ForegroundColor Green
Write-Host "Archived:     $movedCount test scripts" -ForegroundColor Green
Write-Host "Location:     archive\test_scripts_2025_11_01\" -ForegroundColor Green
Write-Host "`nRoot directory is now cleaner! ✨`n" -ForegroundColor Cyan
