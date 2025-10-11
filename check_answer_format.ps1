# Check answer format in the actual response

Write-Host "Checking answer text format..." -ForegroundColor Cyan

if (Test-Path "actual_response.json") {
    $data = Get-Content "actual_response.json" | ConvertFrom-Json

    Write-Host "`n=== ANSWER TEXT ===" -ForegroundColor Yellow
    Write-Host $data.answer

    Write-Host "`n=== ANALYSIS ===" -ForegroundColor Yellow

    # Check if answer contains [Doc X] format
    if ($data.answer -match '\[Doc\s+\d+') {
        Write-Host "✓ Answer CONTAINS [Doc X] citations" -ForegroundColor Green
        $matches = [regex]::Matches($data.answer, '\[Doc\s+(\d+)[^\]]*\]')
        Write-Host "Found $($matches.Count) inline citations:"
        foreach ($match in $matches) {
            Write-Host "  - $($match.Value)" -ForegroundColor Cyan
        }
    } else {
        Write-Host "✗ Answer DOES NOT contain [Doc X] citations" -ForegroundColor Red
        Write-Host "This means convert_to_ieee_style() will NOT find anything to convert!" -ForegroundColor Yellow
    }

    Write-Host "`n=== CITATIONS LIST ===" -ForegroundColor Yellow
    Write-Host "Total citations in response: $($data.citations.Count)"
    foreach ($cit in $data.citations) {
        Write-Host "  - Doc: $($cit.doc_id)" -ForegroundColor Cyan
        Write-Host "    Page: $($cit.page), Has PDF: $($cit.pdf_path -ne $null)" -ForegroundColor Gray
    }

    Write-Host "`n=== PROBLEM DIAGNOSIS ===" -ForegroundColor Yellow
    if ($data.answer -notmatch '\[Doc\s+\d+') {
        Write-Host @"
⚠️ ROOT CAUSE FOUND:
The answer text does NOT contain [Doc X, p.Y] citations!

Without [Doc X] in the answer text, convert_to_ieee_style() cannot:
1. Find any citations to convert
2. Build ieee_citation_list
3. Therefore no References section with page links!

This is a BACKEND issue - the generator is not adding [Doc X] citations to the answer.
The UI fix won't help if there are no [Doc X] citations to convert!
"@ -ForegroundColor Red
    }

} else {
    Write-Host "actual_response.json not found. Run test_actual_query.ps1 first!" -ForegroundColor Red
}
