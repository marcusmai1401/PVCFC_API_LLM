# Documentation Verification Script - v1.2.0
# Verifies all documentation updates are correct and consistent

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "DOCUMENTATION VERIFICATION - v1.2.0" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "" -ForegroundColor Cyan

$errors = 0
$warnings = 0
$successes = 0

# Test 1: Check artifacts directory exists
Write-Host "[TEST 1] Checking artifacts directory structure..." -ForegroundColor Yellow
if (Test-Path "artifacts\ingestion_production") {
    Write-Host "  ✓ artifacts\ingestion_production exists" -ForegroundColor Green
    $successes++

    # Check subdirectories
    $subdirs = @("entities", "chunks", "documents", "manifests", "markdown")
    foreach ($subdir in $subdirs) {
        if (Test-Path "artifacts\ingestion_production\$subdir") {
            Write-Host "  ✓ $subdir/ exists" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ $subdir/ missing (will be created on ingestion)" -ForegroundColor Yellow
            $warnings++
        }
    }
} else {
    Write-Host "  ✗ artifacts\ingestion_production NOT FOUND" -ForegroundColor Red
    Write-Host "    Run ingestion to create this directory" -ForegroundColor Yellow
    $warnings++
}

# Test 2: Check tags.jsonl exists
Write-Host "" -ForegroundColor Yellow
Write-Host "[TEST 2] Checking tags.jsonl location..." -ForegroundColor Yellow
$tagsPath = "artifacts\ingestion_production\entities\tags.jsonl"
if (Test-Path $tagsPath) {
    $tagCount = (Get-Content $tagsPath).Count
    Write-Host "  ✓ tags.jsonl found with $tagCount tags" -ForegroundColor Green
    $successes++
} else {
    Write-Host "  ⚠ tags.jsonl not found (run ingestion with ENABLE_PID_TAGS=true)" -ForegroundColor Yellow
    $warnings++
}

# Test 3: Check .env configuration
Write-Host "" -ForegroundColor Yellow
Write-Host "[TEST 3] Checking .env configuration..." -ForegroundColor Yellow
if (Test-Path ".env") {
    $envContent = Get-Content ".env"

    # Check ENABLE_PID_TAGS
    $pidTagsLine = $envContent | Select-String "ENABLE_PID_TAGS"
    if ($pidTagsLine -like "*=true*") {
        Write-Host "  ✓ ENABLE_PID_TAGS=true (correct)" -ForegroundColor Green
        $successes++
    } elseif ($pidTagsLine -like "*=false*") {
        Write-Host "  ⚠ ENABLE_PID_TAGS=false (production uses true)" -ForegroundColor Yellow
        $warnings++
    } else {
        Write-Host "  ✗ ENABLE_PID_TAGS not found in .env" -ForegroundColor Red
        $errors++
    }

    # Check ARTIFACTS_DIR
    $artifactsDirLine = $envContent | Select-String "ARTIFACTS_DIR"
    if ($artifactsDirLine) {
        Write-Host "  ✓ ARTIFACTS_DIR configured in .env" -ForegroundColor Green
        $successes++
    } else {
        Write-Host "  ⚠ ARTIFACTS_DIR not in .env (optional)" -ForegroundColor Yellow
        $warnings++
    }
} else {
    Write-Host "  ✗ .env file not found" -ForegroundColor Red
    $errors++
}

# Test 4: Check documentation file versions
Write-Host "" -ForegroundColor Yellow
Write-Host "[TEST 4] Checking documentation versions..." -ForegroundColor Yellow

# Check README.md
if (Test-Path "README.md") {
    $readmeContent = Get-Content "README.md" -Raw
    if ($readmeContent -match "LAST UPDATE: 01/11/2025") {
        Write-Host "  ✓ README.md updated to 01/11/2025" -ForegroundColor Green
        $successes++
    } else {
        Write-Host "  ✗ README.md date not updated" -ForegroundColor Red
        $errors++
    }
}

# Check SYSTEM_ARCHITECTURE.md
if (Test-Path "SYSTEM_ARCHITECTURE.md") {
    $archContent = Get-Content "SYSTEM_ARCHITECTURE.md" -Raw
    if ($archContent -match "Version.*1\.2\.0") {
        Write-Host "  ✓ SYSTEM_ARCHITECTURE.md version 1.2.0" -ForegroundColor Green
        $successes++
    } else {
        Write-Host "  ✗ SYSTEM_ARCHITECTURE.md version not updated" -ForegroundColor Red
        $errors++
    }
}

# Check HUONG_DAN_INGESTION.md
if (Test-Path "HUONG_DAN_INGESTION.md") {
    $huongDanContent = Get-Content "HUONG_DAN_INGESTION.md" -Raw
    if ($huongDanContent -match "2025-11-01") {
        Write-Host "  ✓ HUONG_DAN_INGESTION.md updated to 2025-11-01" -ForegroundColor Green
        $successes++
    } else {
        Write-Host "  ✗ HUONG_DAN_INGESTION.md date not updated" -ForegroundColor Red
        $errors++
    }
}

# Check CHANGELOG.md
if (Test-Path "CHANGELOG.md") {
    $changelogContent = Get-Content "CHANGELOG.md" -Raw
    if ($changelogContent -match "\[1\.2\.0\].*2025-11-01") {
        Write-Host "  ✓ CHANGELOG.md has v1.2.0 entry" -ForegroundColor Green
        $successes++
    } else {
        Write-Host "  ✗ CHANGELOG.md missing v1.2.0 entry" -ForegroundColor Red
        $errors++
    }
}

# Test 5: Check for old D:\ paths in documentation
Write-Host "" -ForegroundColor Yellow
Write-Host "[TEST 5] Checking for legacy D:\ paths..." -ForegroundColor Yellow
$docsToCheck = @("HUONG_DAN_INGESTION.md", "README.md", "SYSTEM_ARCHITECTURE.md")
$foundLegacyPaths = $false

foreach ($doc in $docsToCheck) {
    if (Test-Path $doc) {
        $content = Get-Content $doc -Raw
        # Allow D:\ in comments/notes but not in commands
        $commandMatches = [regex]::Matches($content, 'Test-Path.*D:\\PVCFC_Artifacts')
        if ($commandMatches.Count -gt 0) {
            Write-Host "  ⚠ $doc still has D:\ in commands" -ForegroundColor Yellow
            $warnings++
            $foundLegacyPaths = $true
        }
    }
}

if (-not $foundLegacyPaths) {
    Write-Host "  ✓ No legacy D:\ paths in command examples" -ForegroundColor Green
    $successes++
}

# Test 6: Verify tags preservation fix exists
Write-Host "" -ForegroundColor Yellow
Write-Host "[TEST 6] Checking tags preservation fix..." -ForegroundColor Yellow
if (Test-Path "docs\FIX_TAGS_PRESERVATION.md") {
    Write-Host "  ✓ FIX_TAGS_PRESERVATION.md exists" -ForegroundColor Green
    $successes++
} else {
    Write-Host "  ✗ FIX_TAGS_PRESERVATION.md missing" -ForegroundColor Red
    $errors++
}

if (Test-Path "scripts\deduplicate_tags.py") {
    Write-Host "  ✓ deduplicate_tags.py exists" -ForegroundColor Green
    $successes++
} else {
    Write-Host "  ⚠ deduplicate_tags.py missing" -ForegroundColor Yellow
    $warnings++
}

# Test 7: Check documentation update summary
Write-Host "" -ForegroundColor Yellow
Write-Host "[TEST 7] Checking documentation update summary..." -ForegroundColor Yellow
if (Test-Path "docs\DOCUMENTATION_UPDATE_v1.2.0.md") {
    Write-Host "  ✓ DOCUMENTATION_UPDATE_v1.2.0.md exists" -ForegroundColor Green
    $successes++
} else {
    Write-Host "  ✗ DOCUMENTATION_UPDATE_v1.2.0.md missing" -ForegroundColor Red
    $errors++
}

# Summary
Write-Host "" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "VERIFICATION SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Successes: $successes" -ForegroundColor Green
Write-Host "Warnings:  $warnings" -ForegroundColor Yellow
Write-Host "Errors:    $errors" -ForegroundColor Red

if ($errors -eq 0 -and $warnings -eq 0) {
    Write-Host "" -ForegroundColor Green
    Write-Host "✅ ALL CHECKS PASSED!" -ForegroundColor Green
    Write-Host "Documentation is up-to-date and consistent." -ForegroundColor Green
    Write-Host "" -ForegroundColor Green
    exit 0
} elseif ($errors -eq 0) {
    Write-Host "" -ForegroundColor Yellow
    Write-Host "⚠️ PASSED WITH WARNINGS" -ForegroundColor Yellow
    Write-Host "Documentation is mostly correct but has minor issues." -ForegroundColor Yellow
    Write-Host "" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "" -ForegroundColor Red
    Write-Host "❌ VERIFICATION FAILED" -ForegroundColor Red
    Write-Host "Please review and fix the errors above." -ForegroundColor Red
    Write-Host "" -ForegroundColor Red
    exit 1
}
