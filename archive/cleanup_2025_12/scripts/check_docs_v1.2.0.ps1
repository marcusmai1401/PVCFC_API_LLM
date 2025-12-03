# Simple Documentation Check - v1.2.0
Write-Host "========================================"
Write-Host "DOCUMENTATION CHECK - v1.2.0"
Write-Host "========================================"
Write-Host ""

$pass = 0
$warn = 0
$fail = 0

# Test 1: Artifacts directory
Write-Host "[1] Checking artifacts/ingestion_production..."
if (Test-Path "artifacts\ingestion_production") {
    Write-Host "    PASS - Directory exists" -ForegroundColor Green
    $pass++
} else {
    Write-Host "    WARN - Directory not found (run ingestion first)" -ForegroundColor Yellow
    $warn++
}

# Test 2: Tags file
Write-Host "[2] Checking tags.jsonl..."
if (Test-Path "artifacts\ingestion_production\entities\tags.jsonl") {
    $count = (Get-Content "artifacts\ingestion_production\entities\tags.jsonl").Count
    Write-Host "    PASS - Found $count tags" -ForegroundColor Green
    $pass++
} else {
    Write-Host "    WARN - tags.jsonl not found" -ForegroundColor Yellow
    $warn++
}

# Test 3: .env config
Write-Host "[3] Checking .env ENABLE_PID_TAGS..."
if (Test-Path ".env") {
    $pidTags = Get-Content ".env" | Select-String "ENABLE_PID_TAGS"
    if ($pidTags -like "*true*") {
        Write-Host "    PASS - ENABLE_PID_TAGS=true" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "    WARN - ENABLE_PID_TAGS not set to true" -ForegroundColor Yellow
        $warn++
    }
} else {
    Write-Host "    FAIL - .env not found" -ForegroundColor Red
    $fail++
}

# Test 4: README date
Write-Host "[4] Checking README.md date..."
if (Test-Path "README.md") {
    $readme = Get-Content "README.md" -Raw
    if ($readme -match "01/11/2025") {
        Write-Host "    PASS - Updated to 01/11/2025" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "    FAIL - Date not updated" -ForegroundColor Red
        $fail++
    }
}

# Test 5: CHANGELOG v1.2.0
Write-Host "[5] Checking CHANGELOG.md v1.2.0..."
if (Test-Path "CHANGELOG.md") {
    $changelog = Get-Content "CHANGELOG.md" -Raw
    if ($changelog -match "1\.2\.0.*2025-11-01") {
        Write-Host "    PASS - v1.2.0 entry exists" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "    FAIL - v1.2.0 entry missing" -ForegroundColor Red
        $fail++
    }
}

# Test 6: Fix documentation exists
Write-Host "[6] Checking FIX_TAGS_PRESERVATION.md..."
if (Test-Path "docs\FIX_TAGS_PRESERVATION.md") {
    Write-Host "    PASS - Fix documentation exists" -ForegroundColor Green
    $pass++
} else {
    Write-Host "    FAIL - Fix documentation missing" -ForegroundColor Red
    $fail++
}

# Test 7: Update summary
Write-Host "[7] Checking DOCUMENTATION_UPDATE_v1.2.0.md..."
if (Test-Path "docs\DOCUMENTATION_UPDATE_v1.2.0.md") {
    Write-Host "    PASS - Update summary exists" -ForegroundColor Green
    $pass++
} else {
    Write-Host "    FAIL - Update summary missing" -ForegroundColor Red
    $fail++
}

# Summary
Write-Host ""
Write-Host "========================================"
Write-Host "RESULTS"
Write-Host "========================================"
Write-Host "Passed:   $pass" -ForegroundColor Green
Write-Host "Warnings: $warn" -ForegroundColor Yellow
Write-Host "Failed:   $fail" -ForegroundColor Red
Write-Host ""

if ($fail -eq 0 -and $warn -eq 0) {
    Write-Host "ALL CHECKS PASSED!" -ForegroundColor Green
} elseif ($fail -eq 0) {
    Write-Host "PASSED WITH WARNINGS" -ForegroundColor Yellow
} else {
    Write-Host "SOME CHECKS FAILED" -ForegroundColor Red
}
