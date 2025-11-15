<#
.SYNOPSIS
    Verification script for PVCFC RAG system setup and configuration

.DESCRIPTION
    This script validates the PVCFC RAG system environment by checking:
    - Presence of tags, page layouts, and telemetry in artifact directories
    - ENABLE_PID_TAGS environment variable setting
    - PaddleOCR model availability (not Tesseract)
    - Required directory structure
    - Configuration consistency

.EXAMPLE
    .\Verify-SystemSetup.ps1

.EXAMPLE
    .\Verify-SystemSetup.ps1 -Verbose

.NOTES
    Author: PVCFC RAG System
    Version: 1.0.0
    Last Updated: 2025
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectRoot = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"
)

# Script configuration
$ErrorActionPreference = "Continue"
$WarningPreference = "Continue"

# Color output helpers
function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Failure {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

function Write-SectionHeader {
    param([string]$Title)
    Write-Host "`n$("=" * 70)" -ForegroundColor Yellow
    Write-Host "  $Title" -ForegroundColor Yellow
    Write-Host $("=" * 70) -ForegroundColor Yellow
}

# Validation results tracking
$script:ValidationResults = @{
    Passed = 0
    Failed = 0
    Warnings = 0
    Details = @()
}

function Add-ValidationResult {
    param(
        [string]$Category,
        [string]$Check,
        [ValidateSet("Pass", "Fail", "Warning")]
        [string]$Status,
        [string]$Message = ""
    )

    $result = [PSCustomObject]@{
        Category = $Category
        Check = $Check
        Status = $Status
        Message = $Message
        Timestamp = Get-Date
    }

    $script:ValidationResults.Details += $result

    switch ($Status) {
        "Pass" { $script:ValidationResults.Passed++ }
        "Fail" { $script:ValidationResults.Failed++ }
        "Warning" { $script:ValidationResults.Warnings++ }
    }

    return $result
}

#region Environment Validation

function Test-EnvironmentVariables {
    Write-SectionHeader "Environment Variables Validation"

    # Check ENABLE_PID_TAGS
    $enablePidTags = [System.Environment]::GetEnvironmentVariable("ENABLE_PID_TAGS", "Process")
    if (-not $enablePidTags) {
        $enablePidTags = [System.Environment]::GetEnvironmentVariable("ENABLE_PID_TAGS", "User")
    }
    if (-not $enablePidTags) {
        $enablePidTags = [System.Environment]::GetEnvironmentVariable("ENABLE_PID_TAGS", "Machine")
    }

    if ($enablePidTags -eq "true" -or $enablePidTags -eq "1") {
        Write-Success "ENABLE_PID_TAGS is set to true (correct)"
        Add-ValidationResult -Category "Environment" -Check "ENABLE_PID_TAGS" -Status "Pass" -Message "Set to: $enablePidTags"
    }
    elseif ($null -eq $enablePidTags -or $enablePidTags -eq "") {
        Write-Info "ENABLE_PID_TAGS not found in environment (will use default: true)"
        Add-ValidationResult -Category "Environment" -Check "ENABLE_PID_TAGS" -Status "Warning" -Message "Not set, using default (true)"
    }
    else {
        Write-Failure "ENABLE_PID_TAGS is set to '$enablePidTags' (expected: true)"
        Add-ValidationResult -Category "Environment" -Check "ENABLE_PID_TAGS" -Status "Fail" -Message "Incorrect value: $enablePidTags"
    }

    # Check ARTIFACTS_DIR (legacy, now informational)
    $artifactsDir = [System.Environment]::GetEnvironmentVariable("ARTIFACTS_DIR", "Process")
    if (-not $artifactsDir) {
        $artifactsDir = [System.Environment]::GetEnvironmentVariable("ARTIFACTS_DIR", "User")
    }
    if (-not $artifactsDir) {
        $artifactsDir = [System.Environment]::GetEnvironmentVariable("ARTIFACTS_DIR", "Machine")
    }

    if ($artifactsDir) {
        Write-Info "ARTIFACTS_DIR is set to: $artifactsDir (legacy, not actively used)"
        Add-ValidationResult -Category "Environment" -Check "ARTIFACTS_DIR" -Status "Pass" -Message "Set to: $artifactsDir (legacy)"
    }
    else {
        Write-Info "ARTIFACTS_DIR not set (normal - using hardcoded paths)"
        Add-ValidationResult -Category "Environment" -Check "ARTIFACTS_DIR" -Status "Pass" -Message "Not set (using hardcoded paths)"
    }
}

#endregion

#region Directory Structure Validation

function Test-DirectoryStructure {
    Write-SectionHeader "Directory Structure Validation"

    $requiredDirs = @(
        @{Path = "artifacts/ingestion_production"; Description = "Production ingestion artifacts"},
        @{Path = "data/raw"; Description = "Raw document storage"},
        @{Path = "data/staging"; Description = "Staging area"},
        @{Path = "models/ocr"; Description = "OCR models directory"},
        @{Path = "app/ingestion"; Description = "Ingestion module"},
        @{Path = "app/retrieval"; Description = "Retrieval module"}
    )

    foreach ($dir in $requiredDirs) {
        $fullPath = Join-Path $ProjectRoot $dir.Path
        if (Test-Path $fullPath -PathType Container) {
            Write-Success "$($dir.Description): $($dir.Path)"
            Add-ValidationResult -Category "Directory" -Check $dir.Path -Status "Pass" -Message "Exists"
        }
        else {
            Write-Failure "$($dir.Description): $($dir.Path) NOT FOUND"
            Add-ValidationResult -Category "Directory" -Check $dir.Path -Status "Fail" -Message "Missing"
        }
    }
}

#endregion

#region Artifact Files Validation

function Test-ArtifactFiles {
    Write-SectionHeader "Artifact Files Validation"

    $artifactsBase = Join-Path $ProjectRoot "artifacts/ingestion_production"

    if (-not (Test-Path $artifactsBase)) {
        Write-Failure "Artifacts directory not found: $artifactsBase"
        Add-ValidationResult -Category "Artifacts" -Check "Base Directory" -Status "Fail" -Message "Directory missing"
        return
    }

    # Check for tags files
    Write-Host "`nChecking PID Tags Files..." -ForegroundColor Cyan
    $tagsFiles = Get-ChildItem -Path $artifactsBase -Filter "*_tags.json" -Recurse -ErrorAction SilentlyContinue
    if ($tagsFiles.Count -gt 0) {
        Write-Success "Found $($tagsFiles.Count) tags file(s)"
        $tagsFiles | Select-Object -First 5 | ForEach-Object {
            Write-Host "  - $($_.Name) ($([math]::Round($_.Length/1KB, 2)) KB)" -ForegroundColor Gray
        }
        if ($tagsFiles.Count -gt 5) {
            Write-Host "  ... and $($tagsFiles.Count - 5) more" -ForegroundColor Gray
        }
        Add-ValidationResult -Category "Artifacts" -Check "PID Tags" -Status "Pass" -Message "$($tagsFiles.Count) files found"
    }
    else {
        Write-Failure "No tags files found"
        Add-ValidationResult -Category "Artifacts" -Check "PID Tags" -Status "Fail" -Message "No files found"
    }

    # Check for page layout files
    Write-Host "`nChecking Page Layout Files..." -ForegroundColor Cyan
    $layoutFiles = Get-ChildItem -Path $artifactsBase -Filter "*_page_layouts.json" -Recurse -ErrorAction SilentlyContinue
    if ($layoutFiles.Count -gt 0) {
        Write-Success "Found $($layoutFiles.Count) page layout file(s)"
        $layoutFiles | Select-Object -First 5 | ForEach-Object {
            Write-Host "  - $($_.Name) ($([math]::Round($_.Length/1KB, 2)) KB)" -ForegroundColor Gray
        }
        if ($layoutFiles.Count -gt 5) {
            Write-Host "  ... and $($layoutFiles.Count - 5) more" -ForegroundColor Gray
        }
        Add-ValidationResult -Category "Artifacts" -Check "Page Layouts" -Status "Pass" -Message "$($layoutFiles.Count) files found"
    }
    else {
        Write-Failure "No page layout files found"
        Add-ValidationResult -Category "Artifacts" -Check "Page Layouts" -Status "Fail" -Message "No files found"
    }

    # Check for telemetry files
    Write-Host "`nChecking Telemetry Files..." -ForegroundColor Cyan
    $telemetryFiles = Get-ChildItem -Path $artifactsBase -Filter "*_telemetry.json" -Recurse -ErrorAction SilentlyContinue
    if ($telemetryFiles.Count -gt 0) {
        Write-Success "Found $($telemetryFiles.Count) telemetry file(s)"
        $telemetryFiles | Select-Object -First 5 | ForEach-Object {
            Write-Host "  - $($_.Name) ($([math]::Round($_.Length/1KB, 2)) KB)" -ForegroundColor Gray
        }
        if ($telemetryFiles.Count -gt 5) {
            Write-Host "  ... and $($telemetryFiles.Count - 5) more" -ForegroundColor Gray
        }
        Add-ValidationResult -Category "Artifacts" -Check "Telemetry" -Status "Pass" -Message "$($telemetryFiles.Count) files found"
    }
    else {
        Write-Info "No telemetry files found (may not be generated yet)"
        Add-ValidationResult -Category "Artifacts" -Check "Telemetry" -Status "Warning" -Message "No files found"
    }

    # Check artifact directory size
    Write-Host "`nArtifact Directory Statistics..." -ForegroundColor Cyan
    $allFiles = Get-ChildItem -Path $artifactsBase -File -Recurse -ErrorAction SilentlyContinue
    $totalSize = ($allFiles | Measure-Object -Property Length -Sum).Sum
    $totalSizeMB = [math]::Round($totalSize / 1MB, 2)

    Write-Host "  Total Files: $($allFiles.Count)" -ForegroundColor Gray
    Write-Host "  Total Size: $totalSizeMB MB" -ForegroundColor Gray
    Add-ValidationResult -Category "Artifacts" -Check "Directory Size" -Status "Pass" -Message "$($allFiles.Count) files, $totalSizeMB MB"
}

#endregion

#region OCR Configuration Validation

function Test-OCRConfiguration {
    Write-SectionHeader "OCR Configuration Validation (PaddleOCR)"

    # Check PaddleOCR models
    $ocrModelsBase = Join-Path $ProjectRoot "models/ocr"

    if (-not (Test-Path $ocrModelsBase)) {
        Write-Failure "OCR models directory not found: $ocrModelsBase"
        Add-ValidationResult -Category "OCR" -Check "Models Directory" -Status "Fail" -Message "Directory missing"
        return
    }

    # Check for PP-OCRv5 models
    Write-Host "`nChecking PP-OCRv5 Models..." -ForegroundColor Cyan

    $detModel = Join-Path $ocrModelsBase "en_PP-OCRv5_det_infer"
    $clsModel = Join-Path $ocrModelsBase "ch_ppocr_mobile_v2.0_cls_infer"
    $recModel = Join-Path $ocrModelsBase "en_PP-OCRv4_rec_infer"

    # Detection model
    if (Test-Path $detModel) {
        $detFiles = Get-ChildItem -Path $detModel -Filter "inference.*" -ErrorAction SilentlyContinue
        if ($detFiles.Count -ge 2) {
            Write-Success "Detection model found: en_PP-OCRv5_det_infer"
            Add-ValidationResult -Category "OCR" -Check "Detection Model" -Status "Pass" -Message "PP-OCRv5 det model present"
        }
        else {
            Write-Failure "Detection model incomplete: missing inference files"
            Add-ValidationResult -Category "OCR" -Check "Detection Model" -Status "Fail" -Message "Missing inference files"
        }
    }
    else {
        Write-Failure "Detection model not found: $detModel"
        Add-ValidationResult -Category "OCR" -Check "Detection Model" -Status "Fail" -Message "Model directory missing"
    }

    # Classifier model
    if (Test-Path $clsModel) {
        $clsFiles = Get-ChildItem -Path $clsModel -Filter "inference.*" -ErrorAction SilentlyContinue
        if ($clsFiles.Count -ge 2) {
            Write-Success "Classifier model found: ch_ppocr_mobile_v2.0_cls_infer"
            Add-ValidationResult -Category "OCR" -Check "Classifier Model" -Status "Pass" -Message "PP-OCR cls model present"
        }
        else {
            Write-Failure "Classifier model incomplete: missing inference files"
            Add-ValidationResult -Category "OCR" -Check "Classifier Model" -Status "Fail" -Message "Missing inference files"
        }
    }
    else {
        Write-Failure "Classifier model not found: $clsModel"
        Add-ValidationResult -Category "OCR" -Check "Classifier Model" -Status "Fail" -Message "Model directory missing"
    }

    # Recognition model (optional - can auto-download)
    if (Test-Path $recModel) {
        $recFiles = Get-ChildItem -Path $recModel -Filter "inference.*" -ErrorAction SilentlyContinue
        if ($recFiles.Count -ge 2) {
            Write-Success "Recognition model found: en_PP-OCRv4_rec_infer (cached)"
            Add-ValidationResult -Category "OCR" -Check "Recognition Model" -Status "Pass" -Message "PP-OCRv4 rec model cached"
        }
        else {
            Write-Info "Recognition model incomplete (will auto-download)"
            Add-ValidationResult -Category "OCR" -Check "Recognition Model" -Status "Warning" -Message "Will auto-download"
        }
    }
    else {
        Write-Info "Recognition model not cached (will auto-download on first use)"
        Add-ValidationResult -Category "OCR" -Check "Recognition Model" -Status "Warning" -Message "Will auto-download"
    }

    # Verify Tesseract is NOT being used (legacy check)
    Write-Host "`nVerifying OCR Engine..." -ForegroundColor Cyan
    $tesseractPath = $env:TESSERACT_PATH
    if ($tesseractPath) {
        Write-Host "  TESSERACT_PATH is set but NOT used (legacy, replaced by PaddleOCR)" -ForegroundColor Yellow
        Add-ValidationResult -Category "OCR" -Check "OCR Engine" -Status "Warning" -Message "Tesseract path set but not used"
    }
    else {
        Write-Success "Using PaddleOCR (Tesseract not configured)"
        Add-ValidationResult -Category "OCR" -Check "OCR Engine" -Status "Pass" -Message "PaddleOCR only"
    }
}

#endregion

#region Configuration File Validation

function Test-ConfigurationFiles {
    Write-SectionHeader "Configuration Files Validation"

    # Check requirements.txt
    $requirementsFile = Join-Path $ProjectRoot "requirements.txt"
    if (Test-Path $requirementsFile) {
        $content = Get-Content $requirementsFile -Raw

        # Check for PaddleOCR
        if ($content -match "paddleocr") {
            Write-Success "PaddleOCR dependency present in requirements.txt"
            Add-ValidationResult -Category "Config" -Check "PaddleOCR Dependency" -Status "Pass" -Message "Found in requirements.txt"
        }
        else {
            Write-Failure "PaddleOCR not found in requirements.txt"
            Add-ValidationResult -Category "Config" -Check "PaddleOCR Dependency" -Status "Fail" -Message "Missing"
        }

        # Check for deprecated pytesseract
        if ($content -match "pytesseract") {
            Write-Host "  pytesseract found (should be marked as deprecated)" -ForegroundColor Yellow
            if ($content -match "pytesseract.*deprecated") {
                Write-Success "pytesseract correctly marked as deprecated"
                Add-ValidationResult -Category "Config" -Check "Tesseract Deprecated" -Status "Pass" -Message "Marked as deprecated"
            }
            else {
                Write-Host "  pytesseract should be marked as deprecated" -ForegroundColor Yellow
                Add-ValidationResult -Category "Config" -Check "Tesseract Deprecated" -Status "Warning" -Message "Not marked deprecated"
            }
        }
        else {
            Write-Success "pytesseract not in requirements (correctly removed)"
            Add-ValidationResult -Category "Config" -Check "Tesseract Deprecated" -Status "Pass" -Message "Removed from requirements"
        }
    }
    else {
        Write-Failure "requirements.txt not found"
        Add-ValidationResult -Category "Config" -Check "Requirements File" -Status "Fail" -Message "File missing"
    }

    # Check .env file
    $envFile = Join-Path $ProjectRoot ".env"
    if (Test-Path $envFile) {
        Write-Success ".env file exists"
        $envContent = Get-Content $envFile -Raw

        # Check for ENABLE_PID_TAGS
        if ($envContent -match "ENABLE_PID_TAGS\s*=\s*true") {
            Write-Success ".env has ENABLE_PID_TAGS=true"
            Add-ValidationResult -Category "Config" -Check ".env ENABLE_PID_TAGS" -Status "Pass" -Message "Set to true"
        }
        elseif ($envContent -match "ENABLE_PID_TAGS") {
            Write-Host "  .env has ENABLE_PID_TAGS but not set to true" -ForegroundColor Yellow
            Add-ValidationResult -Category "Config" -Check ".env ENABLE_PID_TAGS" -Status "Warning" -Message "Not set to true"
        }
        else {
            Write-Info ".env does not set ENABLE_PID_TAGS (using default)"
            Add-ValidationResult -Category "Config" -Check ".env ENABLE_PID_TAGS" -Status "Pass" -Message "Using default"
        }
    }
    else {
        Write-Info ".env file not found (may use system environment variables)"
        Add-ValidationResult -Category "Config" -Check ".env File" -Status "Warning" -Message "File not found"
    }
}

#endregion

#region Summary Report

function Show-ValidationSummary {
    Write-SectionHeader "Validation Summary"

    Write-Host ""
    Write-Host "Total Checks: $($script:ValidationResults.Details.Count)" -ForegroundColor White
    Write-Success "Passed: $($script:ValidationResults.Passed)"
    Write-Failure "Failed: $($script:ValidationResults.Failed)"
    Write-Host "⚠ Warnings: $($script:ValidationResults.Warnings)" -ForegroundColor Yellow

    # Show failures
    if ($script:ValidationResults.Failed -gt 0) {
        Write-Host "`nFailed Checks:" -ForegroundColor Red
        $script:ValidationResults.Details | Where-Object { $_.Status -eq "Fail" } | ForEach-Object {
            Write-Host "  ✗ [$($_.Category)] $($_.Check): $($_.Message)" -ForegroundColor Red
        }
    }

    # Show warnings
    if ($script:ValidationResults.Warnings -gt 0) {
        Write-Host "`nWarnings:" -ForegroundColor Yellow
        $script:ValidationResults.Details | Where-Object { $_.Status -eq "Warning" } | ForEach-Object {
            Write-Host "  ⚠ [$($_.Category)] $($_.Check): $($_.Message)" -ForegroundColor Yellow
        }
    }

    # Overall status
    Write-Host ""
    if ($script:ValidationResults.Failed -eq 0) {
        if ($script:ValidationResults.Warnings -eq 0) {
            Write-Success "✅ All validation checks passed!"
        }
        else {
            Write-Host "✅ Validation passed with warnings" -ForegroundColor Yellow
        }
    }
    else {
        Write-Failure "❌ Validation failed - please review errors above"
    }

    Write-Host ""
}

#endregion

#region Main Execution

function Main {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║   PVCFC RAG System - Environment Verification Script             ║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray
    Write-Host "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray

    # Verify project root exists
    if (-not (Test-Path $ProjectRoot)) {
        Write-Failure "Project root not found: $ProjectRoot"
        return
    }

    # Run all validation checks
    Test-EnvironmentVariables
    Test-DirectoryStructure
    Test-ArtifactFiles
    Test-OCRConfiguration
    Test-ConfigurationFiles

    # Show summary
    Show-ValidationSummary

    # Export results if requested
    if ($VerbosePreference -eq "Continue") {
        $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $reportPath = Join-Path $ProjectRoot "scripts\validation_report_$timestamp.json"
        $script:ValidationResults.Details | ConvertTo-Json -Depth 5 | Out-File $reportPath -Encoding UTF8
        Write-Info "Detailed report saved to: $reportPath"
    }
}

# Run main
Main

#endregion
