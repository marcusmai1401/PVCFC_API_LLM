# Test the EXACT query from screenshot
Write-Host "Testing actual query to see real response..." -ForegroundColor Cyan

$body = @{
    query = "Based on the provided assembly clearance records for the spare rotor with identification number 0898, the values for the Thrust Bearing are as follows"
    max_context = 3
    hyde = $true
    language = "en"
    execution_mode = "production"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/ask" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -TimeoutSec 60

    # Save full response
    $response | ConvertTo-Json -Depth 10 | Out-File "actual_response.json" -Encoding UTF8

    Write-Host "`n=== ANSWER ===" -ForegroundColor Yellow
    Write-Host $response.answer

    Write-Host "`n=== CITATIONS ===" -ForegroundColor Yellow
    if ($response.citations) {
        foreach ($cit in $response.citations) {
            Write-Host "Doc: $($cit.doc_id)" -ForegroundColor Cyan
            Write-Host "  Page: $($cit.page)" -ForegroundColor White
            Write-Host "  PDF Path: $($cit.pdf_path)" -ForegroundColor Gray
            Write-Host "  Has bbox: $($cit.bbox -ne $null)" -ForegroundColor Gray
            Write-Host ""
        }
    }

    Write-Host "`n=== META INFO ===" -ForegroundColor Yellow
    Write-Host "Has doc_number_map at meta level: $(($response.meta.doc_number_map -ne $null))"
    Write-Host "Has doc_number_map in vision_generation: $(($response.meta.vision_generation.doc_number_map -ne $null))"
    Write-Host "Has doc_number_map in generation_details: $(($response.generation_details.metadata.doc_number_map -ne $null))"

    # Check if doc_number_map exists anywhere
    if ($response.meta.vision_generation.doc_number_map) {
        Write-Host "`nFound doc_number_map in meta.vision_generation:" -ForegroundColor Green
        $response.meta.vision_generation.doc_number_map | ConvertTo-Json -Depth 2
    }

    Write-Host "`n✓ Response saved to actual_response.json" -ForegroundColor Green
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
