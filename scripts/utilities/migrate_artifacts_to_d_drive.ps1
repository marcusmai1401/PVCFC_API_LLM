# ============================================================================
# Migrate Artifacts to D Drive - Safe Migration Script
# ============================================================================
# Purpose: Safely migrate artifacts from C: to D: drive with validation
# Author: AI Agent
# Date: 2025-10-16
# ============================================================================

param(
    [string]$TargetDir = "D:\PVCFC_Artifacts",
    [switch]$TestOnly,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "ARTIFACTS MIGRATION TO D DRIVE" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Get project root
$ProjectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$SourceDir = Join-Path $ProjectRoot "artifacts"
$EnvFile = Join-Path $ProjectRoot ".env"

Write-Host "📂 Source Directory: $SourceDir" -ForegroundColor Yellow
Write-Host "📂 Target Directory: $TargetDir" -ForegroundColor Yellow
Write-Host ""

# ============================================================================
# STEP 1: Pre-flight Checks
# ============================================================================

Write-Host "[1/6] Pre-flight Checks..." -ForegroundColor Green

# Check if D: exists and is accessible
if (-not (Test-Path "D:\")) {
    Write-Host "❌ D: drive not found or not accessible!" -ForegroundColor Red
    exit 1
}

# Check D: free space
$DDrive = Get-PSDrive -Name D
$FreeSpaceGB = [math]::Round($DDrive.Free / 1GB, 2)
Write-Host "✓ D: drive accessible" -ForegroundColor Green
Write-Host "  Free space: $FreeSpaceGB GB" -ForegroundColor White

if ($FreeSpaceGB -lt 50) {
    Write-Host "⚠️  Warning: Less than 50GB free space. Recommend at least 100GB for CAD-like tag extraction." -ForegroundColor Yellow
    if (-not $Force) {
        $confirm = Read-Host "Continue anyway? (y/N)"
        if ($confirm -ne "y") {
            Write-Host "Migration cancelled." -ForegroundColor Yellow
            exit 0
        }
    }
}

# Check if source artifacts exist
$HasExistingData = $false
if (Test-Path $SourceDir) {
    $SourceSize = (Get-ChildItem -Path $SourceDir -Recurse -File -ErrorAction SilentlyContinue |
                   Measure-Object -Property Length -Sum).Sum
    if ($SourceSize -gt 0) {
        $HasExistingData = $true
        $SourceSizeMB = [math]::Round($SourceSize / 1MB, 2)
        Write-Host "✓ Found existing artifacts: $SourceSizeMB MB" -ForegroundColor Green
    }
} else {
    Write-Host "ℹ️  No existing artifacts directory found (fresh install)" -ForegroundColor Cyan
}

# ============================================================================
# STEP 2: Performance Test
# ============================================================================

Write-Host ""
Write-Host "[2/6] Testing D: Drive Write Performance..." -ForegroundColor Green

$TestDir = Join-Path $TargetDir "_performance_test"
New-Item -ItemType Directory -Path $TestDir -Force | Out-Null

$TestResult = Measure-Command {
    1..100 | ForEach-Object {
        $testFile = Join-Path $TestDir "test_$_.txt"
        "Performance test content - iteration $_" | Out-File -FilePath $testFile -Encoding UTF8
    }
}

# Cleanup test files
Remove-Item -Path $TestDir -Recurse -Force -ErrorAction SilentlyContinue

$TestSeconds = [math]::Round($TestResult.TotalSeconds, 2)
Write-Host "✓ Write test completed: $TestSeconds seconds (100 small files)" -ForegroundColor Green

if ($TestSeconds -gt 10) {
    Write-Host "⚠️  Warning: Write performance seems slow. Check if D: is a network/external drive." -ForegroundColor Yellow
}

# ============================================================================
# STEP 3: Backup Existing .env
# ============================================================================

Write-Host ""
Write-Host "[3/6] Backing up configuration..." -ForegroundColor Green

if (Test-Path $EnvFile) {
    $BackupEnvFile = "$EnvFile.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item -Path $EnvFile -Destination $BackupEnvFile
    Write-Host "✓ Backed up .env to: $(Split-Path $BackupEnvFile -Leaf)" -ForegroundColor Green
} else {
    Write-Host "ℹ️  No .env file found (will be created)" -ForegroundColor Cyan
}

if ($TestOnly) {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "TEST MODE - Stopping here (no actual migration)" -ForegroundColor Yellow
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Summary:" -ForegroundColor White
    Write-Host "  ✓ D: drive accessible with $FreeSpaceGB GB free" -ForegroundColor Green
    Write-Host "  ✓ Write performance: $TestSeconds seconds" -ForegroundColor Green
    if ($HasExistingData) {
        Write-Host "  ℹ️  Existing data: $SourceSizeMB MB to migrate" -ForegroundColor Cyan
    }
    Write-Host ""
    Write-Host "Run without -TestOnly to proceed with migration." -ForegroundColor Yellow
    exit 0
}

# ============================================================================
# STEP 4: Create Target Directory Structure
# ============================================================================

Write-Host ""
Write-Host "[4/6] Creating target directory structure..." -ForegroundColor Green

$RequiredDirs = @(
    "ingestion_production",
    "index_production\bm25",
    "index_production\faiss",
    "logs",
    "versions",
    "cache"
)

foreach ($dir in $RequiredDirs) {
    $fullPath = Join-Path $TargetDir $dir
    New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    Write-Host "  ✓ Created: $dir" -ForegroundColor Gray
}

Write-Host "✓ Directory structure created" -ForegroundColor Green

# ============================================================================
# STEP 5: Migrate Existing Data (if any)
# ============================================================================

if ($HasExistingData) {
    Write-Host ""
    Write-Host "[5/6] Migrating existing artifacts..." -ForegroundColor Green
    Write-Host "  Source: $SourceDir" -ForegroundColor Gray
    Write-Host "  Target: $TargetDir" -ForegroundColor Gray
    Write-Host ""

    # Use robocopy for efficient copying
    $robocopyArgs = @(
        "`"$SourceDir`"",
        "`"$TargetDir`"",
        "/E",           # Copy subdirectories including empty
        "/COPY:DAT",    # Copy data, attributes, timestamps
        "/R:3",         # Retry 3 times on failure
        "/W:5",         # Wait 5 seconds between retries
        "/NP",          # No progress (cleaner output)
        "/NFL",         # No file list
        "/NDL"          # No directory list
    )

    $robocopyCommand = "robocopy $($robocopyArgs -join ' ')"
    Write-Host "  Running: robocopy..." -ForegroundColor Gray

    # Execute robocopy (exit codes 0-7 are success)
    $process = Start-Process -FilePath "robocopy" -ArgumentList $robocopyArgs -NoNewWindow -Wait -PassThru
    $exitCode = $process.ExitCode

    if ($exitCode -le 7) {
        Write-Host "✓ Data migration completed successfully" -ForegroundColor Green

        # Verify critical files
        $criticalFiles = @(
            "ingestion_production\chunks.jsonl",
            "ingestion_production\doc_id_map.json"
        )

        $allFilesExist = $true
        foreach ($file in $criticalFiles) {
            $targetFile = Join-Path $TargetDir $file
            if (Test-Path $targetFile) {
                $size = (Get-Item $targetFile).Length / 1MB
                Write-Host "  ✓ Verified: $file ($([math]::Round($size, 2)) MB)" -ForegroundColor Gray
            } else {
                Write-Host "  ⚠️  Missing: $file" -ForegroundColor Yellow
                $allFilesExist = $false
            }
        }

        if (-not $allFilesExist) {
            Write-Host "⚠️  Warning: Some expected files are missing. Check source data." -ForegroundColor Yellow
        }
    } else {
        Write-Host "❌ Robocopy failed with exit code: $exitCode" -ForegroundColor Red
        Write-Host "Migration incomplete. Please check errors above." -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "[5/6] No existing data to migrate (fresh install)" -ForegroundColor Green
}

# ============================================================================
# STEP 6: Update .env Configuration
# ============================================================================

Write-Host ""
Write-Host "[6/6] Updating .env configuration..." -ForegroundColor Green

$envContent = ""
$artifactsDirLine = "ARTIFACTS_DIR=$TargetDir"
$updated = $false

if (Test-Path $EnvFile) {
    # Read existing .env
    $envContent = Get-Content -Path $EnvFile -Raw

    # Check if ARTIFACTS_DIR already exists
    if ($envContent -match "^\s*ARTIFACTS_DIR\s*=") {
        # Update existing line
        $envContent = $envContent -replace "^\s*ARTIFACTS_DIR\s*=.*", $artifactsDirLine
        $updated = $true
        Write-Host "  ✓ Updated existing ARTIFACTS_DIR" -ForegroundColor Gray
    } else {
        # Add new line
        $envContent += "`n`n# Artifacts storage location (migrated to D: drive)`n$artifactsDirLine`n"
        Write-Host "  ✓ Added ARTIFACTS_DIR" -ForegroundColor Gray
    }
} else {
    # Create new .env
    $envContent = @"
# ============================================================================
# ARTIFACTS STORAGE CONFIGURATION
# ============================================================================
# Artifacts directory migrated to D: drive for better disk space management
# Original location: C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts
# Migrated on: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
# ============================================================================

$artifactsDirLine
"@
    Write-Host "  ✓ Created new .env file" -ForegroundColor Gray
}

# Write updated .env
$envContent | Out-File -FilePath $EnvFile -Encoding UTF8 -NoNewline

Write-Host "✓ Configuration updated" -ForegroundColor Green

# ============================================================================
# STEP 7: Summary & Next Steps
# ============================================================================

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "MIGRATION COMPLETED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

Write-Host "📊 Summary:" -ForegroundColor White
Write-Host "  ✓ Target directory: $TargetDir" -ForegroundColor Green
Write-Host "  ✓ Configuration: Updated in .env" -ForegroundColor Green
Write-Host "  ✓ D: free space: $FreeSpaceGB GB" -ForegroundColor Green
if ($HasExistingData) {
    Write-Host "  ✓ Migrated data: $SourceSizeMB MB" -ForegroundColor Green
}
Write-Host ""

Write-Host "🔧 Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Test with a small ingestion:" -ForegroundColor White
Write-Host "     python tools/ingest.py --source-dir ""D:\Data_Raw\test"" --workers 1" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Verify artifacts are created in D: drive:" -ForegroundColor White
Write-Host "     ls $TargetDir" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. If successful, you can safely delete old artifacts:" -ForegroundColor White
Write-Host "     Remove-Item -Path ""$SourceDir"" -Recurse -Force" -ForegroundColor Gray
Write-Host "     (Recommended: Keep for 1 week before deleting)" -ForegroundColor Yellow
Write-Host ""

Write-Host "🔄 Rollback (if needed):" -ForegroundColor Yellow
Write-Host "  1. Remove or comment out ARTIFACTS_DIR from .env" -ForegroundColor White
Write-Host "  2. System will revert to default: artifacts/ in project folder" -ForegroundColor White
Write-Host ""

Write-Host "=" * 80 -ForegroundColor Cyan
