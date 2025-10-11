# Investigation Script: Capture API citations for PDF button root cause analysis
# Purpose: Query API, save full responses, analyze doc_id coverage in doc_id_map

Write-Host "=== PVCFC Citation Investigation Tool ===" -ForegroundColor Cyan
Write-Host ""

# Configuration
$API_BASE = "http://localhost:8000"
$OUTPUT_DIR = "investigation_output"
$DOC_ID_MAP = "artifacts\ingestion_production\doc_id_map.json"

# Create output directory
if (-not (Test-Path $OUTPUT_DIR)) {
    New-Item -ItemType Directory -Path $OUTPUT_DIR | Out-Null
}

# Function: Test API health
function Test-APIHealth {
    try {
        $response = Invoke-RestMethod -Uri "$API_BASE/healthz" -Method GET -TimeoutSec 5
        Write-Host "[OK] API is healthy" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "[ERROR] API is not responding: $_" -ForegroundColor Red
        return $false
    }
}

# Function: Query API and save response
function Query-AndCapture {
    param(
        [string]$Query,
        [string]$OutputFile,
        [string]$Description
    )

    Write-Host "`n--- Test: $Description ---" -ForegroundColor Yellow
    Write-Host "Query: $Query"

    $body = @{
        query = $Query
        max_context = 5
        hyde = $true
        language = "vi"
    } | ConvertTo-Json

    try {
        $response = Invoke-RestMethod -Uri "$API_BASE/ask" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body `
            -TimeoutSec 60

        # Save full response
        $response | ConvertTo-Json -Depth 10 | Out-File "$OUTPUT_DIR\$OutputFile" -Encoding UTF8

        Write-Host "[OK] Response saved to: $OUTPUT_DIR\$OutputFile" -ForegroundColor Green

        # Analyze citations
        if ($response.citations) {
            Write-Host "`nCitations found: $($response.citations.Count)" -ForegroundColor Cyan

            $withPDF = 0
            $withoutPDF = 0
            $missingDocID = 0

            foreach ($cite in $response.citations) {
                if ($cite.pdf_path) {
                    $withPDF++
                } else {
                    $withoutPDF++
                }

                if (-not $cite.doc_id) {
                    $missingDocID++
                }
            }

            Write-Host "  - With pdf_path: $withPDF" -ForegroundColor $(if ($withPDF -gt 0) { "Green" } else { "White" })
            Write-Host "  - WITHOUT pdf_path: $withoutPDF" -ForegroundColor $(if ($withoutPDF -gt 0) { "Red" } else { "White" })
            Write-Host "  - Missing doc_id: $missingDocID" -ForegroundColor $(if ($missingDocID -gt 0) { "Red" } else { "White" })
        }
        else {
            Write-Host "[!] No citations in response" -ForegroundColor Yellow
        }

        return $response
    }
    catch {
        Write-Host "[ERROR] Query failed: $_" -ForegroundColor Red
        return $null
    }
}

# Function: Analyze doc_id coverage
function Analyze-DocIDCoverage {
    Write-Host "`n=== Analyzing doc_id Coverage ===" -ForegroundColor Cyan

    # Load doc_id_map
    if (-not (Test-Path $DOC_ID_MAP)) {
        Write-Host "[ERROR] doc_id_map.json not found at: $DOC_ID_MAP" -ForegroundColor Red
        return
    }

    $docMap = Get-Content $DOC_ID_MAP | ConvertFrom-Json
    $mapKeys = $docMap.PSObject.Properties.Name
    Write-Host "doc_id_map entries: $($mapKeys.Count)" -ForegroundColor White

    # Collect all doc_ids from captured responses
    $allDocIDs = @()
    Get-ChildItem "$OUTPUT_DIR\*.json" | ForEach-Object {
        $data = Get-Content $_.FullName | ConvertFrom-Json
        if ($data.citations) {
            foreach ($cite in $data.citations) {
                if ($cite.doc_id) {
                    $allDocIDs += $cite.doc_id
                }
            }
        }
    }

    $uniqueDocIDs = $allDocIDs | Select-Object -Unique
    Write-Host "Unique doc_ids from API responses: $($uniqueDocIDs.Count)" -ForegroundColor White

    # Find missing doc_ids
    $missing = @()
    foreach ($docID in $uniqueDocIDs) {
        if ($docID -notin $mapKeys) {
            $missing += $docID
        }
    }

    if ($missing.Count -gt 0) {
        Write-Host "`n[WARNING] FOUND MISSING doc_ids in doc_id_map:" -ForegroundColor Red
        $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }

        # Save to file
        $missing | Out-File "$OUTPUT_DIR\missing_doc_ids.txt" -Encoding UTF8
        Write-Host "`nMissing doc_ids saved to: $OUTPUT_DIR\missing_doc_ids.txt" -ForegroundColor Green
    }
    else {
        Write-Host "`n[OK] All doc_ids found in doc_id_map" -ForegroundColor Green
    }

    # Coverage statistics
    $coverage = [math]::Round(($uniqueDocIDs.Count - $missing.Count) / $uniqueDocIDs.Count * 100, 2)
    Write-Host "`nCoverage: $coverage% ($($uniqueDocIDs.Count - $missing.Count)/$($uniqueDocIDs.Count))" -ForegroundColor Cyan
}

# Function: Generate detailed citation report
function Generate-CitationReport {
    Write-Host "`n=== Generating Detailed Citation Report ===" -ForegroundColor Cyan

    $report = @()
    $report += "# Citation Investigation Report"
    $report += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $report += ""
    $report += "## Summary"
    $report += ""

    # Load doc_id_map
    $docMap = Get-Content $DOC_ID_MAP | ConvertFrom-Json

    Get-ChildItem "$OUTPUT_DIR\response_*.json" | ForEach-Object {
        $data = Get-Content $_.FullName | ConvertFrom-Json
        $testName = $_.BaseName -replace "response_", ""

        $report += "### Test: $testName"
        $report += ""

        if ($data.citations) {
            $report += "| # | doc_id | page | pdf_path | in_map | source |"
            $report += "|---|--------|------|----------|--------|--------|"

            $index = 1
            foreach ($cite in $data.citations) {
                $inMap = if ($cite.doc_id -and $docMap.PSObject.Properties.Name -contains $cite.doc_id) { "YES" } else { "NO" }
                $hasPDF = if ($cite.pdf_path) { "YES" } else { "NO" }
                $page = if ($cite.page) { $cite.page } else { "-" }
                $docID = if ($cite.doc_id) { $cite.doc_id.Substring(0, [Math]::Min(50, $cite.doc_id.Length)) } else { "MISSING" }
                $source = if ($cite.source) { $cite.source } else { "-" }

                $report += "| $index | $docID | $page | $hasPDF | $inMap | $source |"
                $index++
            }
        }
        $report += ""
    }

    $report | Out-File "$OUTPUT_DIR\citation_report.md" -Encoding UTF8
    Write-Host "[OK] Report saved to: $OUTPUT_DIR\citation_report.md" -ForegroundColor Green
}

# Main execution
Write-Host "Step 1: Checking API health..." -ForegroundColor White
if (-not (Test-APIHealth)) {
    Write-Host "`n[!] Please start the API first with: .\launchers\start_api.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nStep 2: Running test queries..." -ForegroundColor White

# Test queries
Query-AndCapture -Query "What is the operating speed of CO2 compressor?" `
    -OutputFile "response_test1_co2_speed.json" `
    -Description "CO2 Compressor Speed (General query)"

Query-AndCapture -Query "Show me the datasheet specifications for document 3N4-S4274343" `
    -OutputFile "response_test2_specific_doc.json" `
    -Description "Specific document query"

Query-AndCapture -Query "What are the maintenance requirements for the turbine?" `
    -OutputFile "response_test3_maintenance.json" `
    -Description "Turbine Maintenance (Multi-doc)"

Write-Host "`nStep 3: Analyzing doc_id coverage..." -ForegroundColor White
Analyze-DocIDCoverage

Write-Host "`nStep 4: Generating detailed report..." -ForegroundColor White
Generate-CitationReport

Write-Host "`n=== Investigation Complete ===" -ForegroundColor Green
Write-Host "Results saved in: $OUTPUT_DIR\" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Review: $OUTPUT_DIR\citation_report.md" -ForegroundColor White
Write-Host "  2. Check missing doc_ids: $OUTPUT_DIR\missing_doc_ids.txt" -ForegroundColor White
Write-Host "  3. Examine full responses: $OUTPUT_DIR\response_*.json" -ForegroundColor White
