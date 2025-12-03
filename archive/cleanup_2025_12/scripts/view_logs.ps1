<#
.SYNOPSIS
    View and analyze UI event logs for the Streamlit Query Lab.

.DESCRIPTION
    This script helps you quickly locate, tail, and filter JSONL and text log files
    produced by the UI event logger. Works best on Windows PowerShell.

.PARAMETER Last
    Number of recent events to show from the JSONL logs.

.PARAMETER Tail
    Tail the session JSONL log file in real time.

.PARAMETER Session
    Specific session ID to view (matches session_*.jsonl files). If not provided,
    the most recent session is used.

.PARAMETER OpenDir
    Open the log directory in File Explorer.

.EXAMPLE
    # Show last 50 events
    .\view_logs.ps1 -Last 50

.EXAMPLE
    # Tail the most recent session log in real-time
    .\view_logs.ps1 -Tail

.EXAMPLE
    # Open the logs folder
    .\view_logs.ps1 -OpenDir
#>
[CmdletBinding()] param(
    [int]$Last = 50,
    [switch]$Tail,
    [string]$Session,
    [switch]$OpenDir
)

$ErrorActionPreference = 'Stop'

# Resolve project root based on this script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$LogDir = Join-Path $ProjectRoot 'logs/ui_events'

if (-not (Test-Path $LogDir)) {
    Write-Host "Log directory not found: $LogDir" -ForegroundColor Yellow
    Write-Host "No logs yet. Interact with the UI to generate logs." -ForegroundColor Yellow
    exit 0
}

if ($OpenDir) {
    Start-Process explorer.exe $LogDir
    exit 0
}

# Get session files
$sessionFiles = Get-ChildItem -Path $LogDir -Filter 'session_*.jsonl' | Sort-Object LastWriteTime -Descending
if (-not $sessionFiles) {
    Write-Host "No session JSONL files found in $LogDir" -ForegroundColor Yellow
    exit 0
}

# Select session file
$targetFile = $null
if ($Session) {
    $targetFile = $sessionFiles | Where-Object { $_.Name -like "*${Session}*.jsonl" } | Select-Object -First 1
    if (-not $targetFile) {
        Write-Host "No session matching '$Session' found. Using most recent session." -ForegroundColor Yellow
        $targetFile = $sessionFiles[0]
    }
} else {
    $targetFile = $sessionFiles[0]
}

Write-Host "Using session log: $($targetFile.FullName)" -ForegroundColor Cyan

if ($Tail) {
    Write-Host "Tailing log (Ctrl+C to stop)..." -ForegroundColor Green
    Get-Content -Path $targetFile.FullName -Wait
    exit 0
}

# Read last N lines efficiently
$lines = Get-Content -Path $targetFile.FullName -Tail $Last

if (-not $lines) {
    Write-Host "No log lines found." -ForegroundColor Yellow
    exit 0
}

# Try to parse each JSON line and output a human-friendly table
$events = @()
foreach ($line in $lines) {
    try {
        $obj = $line | ConvertFrom-Json -ErrorAction Stop
        $events += [PSCustomObject]@{
            Time       = $obj.timestamp
            Type       = $obj.event_type
            Severity   = $obj.severity_name
            Message    = $obj.message
        }
    }
    catch {
        # Fallback: keep raw line
        $events += [PSCustomObject]@{
            Time       = ''
            Type       = 'raw'
            Severity   = ''
            Message    = $line
        }
    }
}

$events | Format-Table -AutoSize

# Also show some quick stats
try {
    $allLines = Get-Content -Path $targetFile.FullName
    $total = $allLines.Count
    $errors = ($allLines | Select-String -Pattern '"severity_name"\s*:\s*"ERROR"').Count
    $warnings = ($allLines | Select-String -Pattern '"severity_name"\s*:\s*"WARNING"').Count
    Write-Host "`nSession stats: total=$total, errors=$errors, warnings=$warnings" -ForegroundColor Magenta
}
catch {
    # Ignore errors here
}
