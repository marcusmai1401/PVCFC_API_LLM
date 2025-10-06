# Wrapper script to run verify_v5.py with PIR disabled
# This is needed for PaddlePaddle 3.0.0-beta compatibility

$env:FLAGS_enable_pir_api = "0"
$env:FLAGS_enable_pir_in_executor = "0"

Write-Host "Running with PIR disabled for PaddlePaddle 3.0.0-beta compatibility..." -ForegroundColor Green
python .\tools\verify\verify_v5.py
