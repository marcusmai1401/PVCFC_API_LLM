#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Sync text_by_page.jsonl from index_production to artifacts root

.DESCRIPTION
    This script copies text_by_page.jsonl from index_production subdirectory
    to the artifacts root where PageReranker/CitationValidator expects it.

    Run this after building/rebuilding the index to ensure file is in correct location.

.EXAMPLE
    .\scripts\sync_page_text.ps1
#>

$ErrorActionPreference = "Stop"

$srcPath = "D:\PVCFC_Artifacts\index_production\text_by_page.jsonl"
$dstPath = "D:\PVCFC_Artifacts\text_by_page.jsonl"

Write-Host "Syncing text_by_page.jsonl..." -ForegroundColor Cyan

# Check source exists
if (-not (Test-Path $srcPath)) {
    Write-Error "Source file not found: $srcPath"
    Write-Host "Have you built the index yet? Run: python tools/build_page_index.py" -ForegroundColor Yellow
    exit 1
}

# Copy file
try {
    Copy-Item -Path $srcPath -Destination $dstPath -Force
    Write-Host "✓ File copied successfully" -ForegroundColor Green

    # Show file info
    $file = Get-Item $dstPath
    Write-Host "`nFile Info:" -ForegroundColor Cyan
    Write-Host "  Path: $($file.FullName)"
    Write-Host "  Size: $([math]::Round($file.Length / 1MB, 2)) MB"
    Write-Host "  Last Modified: $($file.LastWriteTime)"

} catch {
    Write-Error "Failed to copy file: $_"
    exit 1
}

Write-Host "`n✓ Sync complete!" -ForegroundColor Green
