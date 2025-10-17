# ============================================================================
# Verify Artifacts Location - Post-Migration Check
# ============================================================================
# Purpose: Verify artifacts are correctly configured and accessible
# Usage: .\scripts\utilities\verify_artifacts_location.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "ARTIFACTS LOCATION VERIFICATION" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Get project root
$ProjectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$EnvFile = Join-Path $ProjectRoot ".env"
$DefaultArtifactsDir = Join-Path $ProjectRoot "artifacts"

# Check .env configuration
Write-Host "[1/4] Checking configuration..." -ForegroundColor Green

$configuredDir = $null
if (Test-Path $EnvFile) {
    $envContent = Get-Content -Path $EnvFile -Raw
    if ($envContent -match "ARTIFACTS_DIR\s*=\s*(.+)") {
        $configuredDir = $Matches[1].Trim()
        Write-Host "  ✓ .env file found" -ForegroundColor Green
        Write-Host "  ✓ ARTIFACTS_DIR configured: $configuredDir" -ForegroundColor Green
    } else {
        Write-Host "  ℹ️  ARTIFACTS_DIR not set in .env (using default)" -ForegroundColor Cyan
        $configuredDir = $DefaultArtifactsDir
    }
} else {
    Write-Host "  ℹ️  No .env file (using default location)" -ForegroundColor Cyan
    $configuredDir = $DefaultArtifactsDir
}

# Check if directory exists
Write-Host ""
Write-Host "[2/4] Checking directory access..." -ForegroundColor Green

if (Test-Path $configuredDir) {
    Write-Host "  ✓ Directory exists: $configuredDir" -ForegroundColor Green

    # Check write permission
    $testFile = Join-Path $configuredDir "_test_write_permission.tmp"
    try {
        "test" | Out-File -FilePath $testFile -ErrorAction Stop
        Remove-Item -Path $testFile -ErrorAction SilentlyContinue
        Write-Host "  ✓ Write permission: OK" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ No write permission!" -ForegroundColor Red
        Write-Host "     Error: $_" -ForegroundColor Yellow
    }

    # Check disk space
    $driveLetter = ($configuredDir -split ':')[0]
    if ($driveLetter) {
        try {
            $drive = Get-PSDrive -Name $driveLetter -ErrorAction Stop
            $freeSpaceGB = [math]::Round($drive.Free / 1GB, 2)
            $usedSpaceGB = [math]::Round($drive.Used / 1GB, 2)
            $totalSpaceGB = [math]::Round(($drive.Free + $drive.Used) / 1GB, 2)

            Write-Host "  ✓ Disk space on ${driveLetter}:" -ForegroundColor Green
            Write-Host "    - Total: $totalSpaceGB GB" -ForegroundColor Gray
            Write-Host "    - Used: $usedSpaceGB GB" -ForegroundColor Gray
            Write-Host "    - Free: $freeSpaceGB GB" -ForegroundColor Gray

            if ($freeSpaceGB -lt 50) {
                Write-Host "  ⚠️  Warning: Less than 50GB free" -ForegroundColor Yellow
                Write-Host "     Recommend at least 100GB for CAD-like tag extraction" -ForegroundColor Yellow
            } elseif ($freeSpaceGB -lt 100) {
                Write-Host "  ⚠️  Consider freeing up space (< 100GB)" -ForegroundColor Yellow
            } else {
                Write-Host "  ✓ Sufficient space available" -ForegroundColor Green
            }
        } catch {
            Write-Host "  ⚠️  Could not check disk space" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  ⚠️  Directory does not exist: $configuredDir" -ForegroundColor Yellow
    Write-Host "     It will be created automatically on first use" -ForegroundColor Cyan
}

# Check for existing artifacts
Write-Host ""
Write-Host "[3/4] Checking for existing artifacts..." -ForegroundColor Green

$artifactsDirs = @(
    @{Path="ingestion_production"; Critical=$true},
    @{Path="index_production"; Critical=$true},
    @{Path="logs"; Critical=$false},
    @{Path="versions"; Critical=$false},
    @{Path="cache"; Critical=$false}
)

$foundCritical = $false
foreach ($dir in $artifactsDirs) {
    $fullPath = Join-Path $configuredDir $dir.Path
    if (Test-Path $fullPath) {
        $size = (Get-ChildItem -Path $fullPath -Recurse -File -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum).Sum
        $sizeMB = [math]::Round($size / 1MB, 2)

        $marker = if ($dir.Critical) { "✓" } else { "ℹ️" }
        $color = if ($dir.Critical) { "Green" } else { "Cyan" }

        Write-Host "  $marker $($dir.Path): $sizeMB MB" -ForegroundColor $color

        if ($dir.Critical -and $size -gt 0) {
            $foundCritical = $true
        }
    } else {
        $marker = if ($dir.Critical) { "⚠️" } else { "○" }
        $color = if ($dir.Critical) { "Yellow" } else { "Gray" }
        Write-Host "  $marker $($dir.Path): Not found" -ForegroundColor $color
    }
}

if (-not $foundCritical) {
    Write-Host ""
    Write-Host "  ℹ️  No critical artifacts found (fresh install or not yet ingested)" -ForegroundColor Cyan
}

# Check critical files
Write-Host ""
Write-Host "[4/4] Checking critical files..." -ForegroundColor Green

$criticalFiles = @(
    "ingestion_production\chunks.jsonl",
    "ingestion_production\doc_id_map.json"
)

$allCriticalFound = $true
foreach ($file in $criticalFiles) {
    $fullPath = Join-Path $configuredDir $file
    if (Test-Path $fullPath) {
        $size = (Get-Item $fullPath).Length / 1MB
        Write-Host "  ✓ $file ($([math]::Round($size, 2)) MB)" -ForegroundColor Green
    } else {
        Write-Host "  ○ $file (not found)" -ForegroundColor Gray
        $allCriticalFound = $false
    }
}

if (-not $allCriticalFound) {
    Write-Host ""
    Write-Host "  ℹ️  Missing critical files indicate fresh install or pending ingestion" -ForegroundColor Cyan
}

# Summary
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "VERIFICATION SUMMARY" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

Write-Host "Configuration: $configuredDir" -ForegroundColor White
if (Test-Path $configuredDir) {
    Write-Host "Status: ✓ READY" -ForegroundColor Green
} else {
    Write-Host "Status: ⚠️  Will be created on first use" -ForegroundColor Yellow
}

Write-Host ""

if ($configuredDir -match "^D:") {
    Write-Host "💡 Tips for D: Drive Storage:" -ForegroundColor Yellow
    Write-Host "  • Keep at least 100GB free for CAD-like tag extraction" -ForegroundColor White
    Write-Host "  • Monitor disk usage during ingestion" -ForegroundColor White
    Write-Host "  • Old artifacts in C:\...\artifacts\ can be deleted after verification" -ForegroundColor White
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
