# ============================================================================
# PVCFC RAG Project Reorganization Script
# ============================================================================
# Tự động sắp xếp lại cấu trúc thư mục gốc
# Created: 2025-10-07
# ============================================================================

param(
    [switch]$DryRun = $false,  # Chỉ hiển thị những gì sẽ làm, không thực hiện
    [switch]$SkipBackup = $false,  # Bỏ qua tạo backup
    [switch]$Force = $false  # Ghi đè nếu file đã tồn tại
)

# Colors
$ErrorColor = "Red"
$WarningColor = "Yellow"
$SuccessColor = "Green"
$InfoColor = "Cyan"

function Write-Status {
    param([string]$Message, [string]$Type = "Info")

    $color = switch ($Type) {
        "Error" { $ErrorColor }
        "Warning" { $WarningColor }
        "Success" { $SuccessColor }
        default { $InfoColor }
    }

    $prefix = switch ($Type) {
        "Error" { "[❌]" }
        "Warning" { "[⚠️]" }
        "Success" { "[✅]" }
        default { "[ℹ️]" }
    }

    Write-Host "$prefix $Message" -ForegroundColor $color
}

function Test-GitRepository {
    try {
        git rev-parse --git-dir 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Move-FileOrDirectory {
    param(
        [string]$Source,
        [string]$Destination,
        [bool]$UseGitMv = $false
    )

    if (-not (Test-Path $Source)) {
        Write-Status "Source not found: $Source" "Warning"
        return $false
    }

    if ($DryRun) {
        Write-Status "[DRY RUN] Would move: $Source -> $Destination" "Info"
        return $true
    }

    try {
        # Ensure destination directory exists
        $destDir = Split-Path -Parent $Destination
        if ($destDir -and -not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }

        # Use git mv if in git repo and requested
        if ($UseGitMv -and (Test-GitRepository)) {
            git mv "$Source" "$Destination" 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Status "Moved (git): $Source -> $Destination" "Success"
                return $true
            }
        }

        # Fallback to regular move
        if (Test-Path $Destination) {
            if ($Force) {
                Remove-Item $Destination -Recurse -Force
            } else {
                Write-Status "Destination exists: $Destination (use -Force to overwrite)" "Warning"
                return $false
            }
        }

        Move-Item -Path $Source -Destination $Destination -Force
        Write-Status "Moved: $Source -> $Destination" "Success"
        return $true
    } catch {
        Write-Status "Failed to move $Source : $_" "Error"
        return $false
    }
}

function New-DirectoryStructure {
    $directories = @(
        "launchers",
        "utilities",
        "reports",
        "reports\summaries",
        "reports\test_results",
        "archive",
        "archive\experiments",
        "logs\archived",
        "results\benchmarks"
    )

    Write-Status "Creating directory structure..." "Info"

    foreach ($dir in $directories) {
        if ($DryRun) {
            Write-Status "[DRY RUN] Would create directory: $dir" "Info"
        } else {
            if (-not (Test-Path $dir)) {
                New-Item -ItemType Directory -Path $dir -Force | Out-Null
                Write-Status "Created: $dir" "Success"
            } else {
                Write-Status "Already exists: $dir" "Info"
            }
        }
    }
}

function Move-LauncherScripts {
    Write-Status "`n=== Moving Launcher Scripts ===" "Info"

    $scripts = @(
        @{ Source = "start_api.ps1"; Dest = "launchers\start_api.ps1" },
        @{ Source = "start_ui.ps1"; Dest = "launchers\start_ui.ps1" },
        @{ Source = "start_all.ps1"; Dest = "launchers\start_all.ps1" },
        @{ Source = "start.ps1"; Dest = "launchers\start.ps1" },
        @{ Source = "quick_restart.ps1"; Dest = "launchers\quick_restart.ps1" },
        @{ Source = "restart_and_test.ps1"; Dest = "launchers\restart_and_test.ps1" },
        @{ Source = "start_and_test_cove.ps1"; Dest = "launchers\start_and_test_cove.ps1" },
        @{ Source = "start_server.bat"; Dest = "launchers\start_server.bat" }
    )

    $useGit = Test-GitRepository
    foreach ($item in $scripts) {
        Move-FileOrDirectory -Source $item.Source -Destination $item.Dest -UseGitMv $useGit
    }
}

function Move-UtilityScripts {
    Write-Status "`n=== Moving Utility Scripts ===" "Info"

    $scripts = @(
        @{ Source = "check_embeddings.py"; Dest = "utilities\check_embeddings.py" },
        @{ Source = "generate_doc_id_map.py"; Dest = "utilities\generate_doc_id_map.py" },
        @{ Source = "generate_doc_id_map_full_paths.py"; Dest = "utilities\generate_doc_id_map_full_paths.py" },
        @{ Source = "rag_cli.py"; Dest = "utilities\rag_cli.py" },
        @{ Source = "run_all_tests.py"; Dest = "utilities\run_all_tests.py" }
    )

    $useGit = Test-GitRepository
    foreach ($item in $scripts) {
        Move-FileOrDirectory -Source $item.Source -Destination $item.Dest -UseGitMv $useGit
    }
}

function Move-TestScripts {
    Write-Status "`n=== Moving Test Scripts ===" "Info"

    $scripts = @(
        "test_5am_fix.py",
        "test_citation_retriever.py",
        "test_config.py",
        "test_cove_fix.py",
        "test_hybrid_ranking_integration.py",
        "test_ocr_cached.py",
        "test_paddleocr_integration.py",
        "test_page_reranker.py",
        "test_page_reranker_semantic.py",
        "test_pdf_citations.py",
        "test_post_validation_fix.py",
        "test_priority1_fixes.py",
        "test_retrieval_details.py",
        "test_snippet_extractor.py",
        "test_tokenization.py",
        "test_vision_citation_fixes.py"
    )

    # Ensure tests\integration exists
    if (-not (Test-Path "tests\integration")) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path "tests\integration" -Force | Out-Null
        }
    }

    $useGit = Test-GitRepository
    foreach ($script in $scripts) {
        $dest = "tests\integration\$script"
        Move-FileOrDirectory -Source $script -Destination $dest -UseGitMv $useGit
    }
}

function Move-SummaryReports {
    Write-Status "`n=== Moving Summary Reports ===" "Info"

    $reports = @(
        "ALL_PRIORITIES_COMPLETE_SUMMARY.md",
        "ALL_UI_FIXES_FINAL_SUMMARY.md",
        "CITEFIX_COMPLETION_SUMMARY.md",
        "FIX_COVE_WARNINGS_SUMMARY.md",
        "FIX_RETRIEVAL_DETAILS_SUMMARY.md",
        "FIX_VISION_VERIFY_UI_SUMMARY.md",
        "FIXES_REVIEW_AND_RECOMMENDATIONS.md",
        "PRIORITY1_FIXES_SUMMARY.md",
        "PRIORITY2_PDF_CITATIONS_SUMMARY.md",
        "PRIORITY3_COVE_IMPROVEMENTS_SUMMARY.md",
        "VISION_CITATION_4_FIXES_SUMMARY.md",
        "VISION_CITATION_FIXES_EXECUTIVE_SUMMARY.md",
        "VISION_FIXES_INDEX.md",
        "SYSTEM_READINESS_REPORT.md",
        "RESTRUCTURE_COMPLETE.md"
    )

    $useGit = Test-GitRepository
    foreach ($report in $reports) {
        $dest = "reports\summaries\$report"
        Move-FileOrDirectory -Source $report -Destination $dest -UseGitMv $useGit
    }
}

function Move-TestReports {
    Write-Status "`n=== Moving Test Reports ===" "Info"

    $reports = @(
        "test_report.md",
        "TEST_FAILURE_ANALYSIS.md",
        "TEST_INSTRUCTIONS.md"
    )

    $useGit = Test-GitRepository
    foreach ($report in $reports) {
        $dest = "reports\test_results\$report"
        Move-FileOrDirectory -Source $report -Destination $dest -UseGitMv $useGit
    }
}

function Move-LogFiles {
    Write-Status "`n=== Moving Log Files ===" "Info"

    $logs = @(
        "analysis_output.txt",
        "audit_run.txt",
        "reindex_phase1_log.txt",
        "server_error.txt",
        "server_output.txt",
        "test_vision_fixes_report_20251004_172105.txt",
        "test_vision_fixes_report_20251004_172653.txt"
    )

    $useGit = Test-GitRepository
    foreach ($log in $logs) {
        $dest = "logs\archived\$log"
        Move-FileOrDirectory -Source $log -Destination $dest -UseGitMv $useGit
    }
}

function Move-BenchmarkResults {
    Write-Status "`n=== Moving Benchmark Results ===" "Info"

    $files = @(
        "benchmark_cpu_vs_gpu_results.json",
        "ocr_language_survey_baseline.json"
    )

    $useGit = Test-GitRepository
    foreach ($file in $files) {
        $dest = "results\benchmarks\$file"
        Move-FileOrDirectory -Source $file -Destination $dest -UseGitMv $useGit
    }
}

function Move-TestPowerShellScripts {
    Write-Status "`n=== Moving Test PowerShell Scripts ===" "Info"

    $scripts = @(
        "run_task2_test.ps1",
        "run_task2_test_v2.ps1",
        "run_verify_v5.ps1"
    )

    # Ensure scripts\test_scripts exists
    if (-not (Test-Path "scripts\test_scripts")) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path "scripts\test_scripts" -Force | Out-Null
        }
    }

    $useGit = Test-GitRepository
    foreach ($script in $scripts) {
        $dest = "scripts\test_scripts\$script"
        Move-FileOrDirectory -Source $script -Destination $dest -UseGitMv $useGit
    }
}

function Move-ExperimentalCode {
    Write-Status "`n=== Moving Experimental Code ===" "Info"

    if (Test-Path "AIstudio google") {
        $useGit = Test-GitRepository
        Move-FileOrDirectory -Source "AIstudio google" -Destination "archive\experiments\AIstudio google" -UseGitMv $useGit
    } else {
        Write-Status "AIstudio google not found, skipping" "Info"
    }
}

function Move-MiscFiles {
    Write-Status "`n=== Moving Miscellaneous Files ===" "Info"

    $useGit = Test-GitRepository

    # COMMIT_MSG
    if (Test-Path "COMMIT_MSG_VISION_CITATION_FIX.txt") {
        Move-FileOrDirectory -Source "COMMIT_MSG_VISION_CITATION_FIX.txt" -Destination "archive\COMMIT_MSG_VISION_CITATION_FIX.txt" -UseGitMv $useGit
    }

    # QUICK_TEST_GUIDE - copy to docs as .md, then move original to archive
    if (Test-Path "QUICK_TEST_GUIDE.txt") {
        if (-not $DryRun) {
            Copy-Item "QUICK_TEST_GUIDE.txt" "docs\QUICK_TEST_GUIDE.md" -Force
            Write-Status "Copied QUICK_TEST_GUIDE.txt -> docs\QUICK_TEST_GUIDE.md" "Success"
        }
        Move-FileOrDirectory -Source "QUICK_TEST_GUIDE.txt" -Destination "archive\QUICK_TEST_GUIDE.txt" -UseGitMv $useGit
    }

    # DONE_100% folder
    if (Test-Path "DONE_100%") {
        $response = Read-Host "Archive DONE_100% folder? (Y/N)"
        if ($response -eq "Y" -or $response -eq "y") {
            Move-FileOrDirectory -Source "DONE_100%" -Destination "archive\DONE_100%" -UseGitMv $useGit
        }
    }
}

function Create-READMEFiles {
    Write-Status "`n=== Creating README Files ===" "Info"

    $readmes = @{
        "launchers\README.md" = @"
# Launcher Scripts

Scripts để khởi động các services của PVCFC RAG.

## Scripts

- ``start_api.ps1`` - Khởi động FastAPI backend server
- ``start_ui.ps1`` - Khởi động Streamlit UI
- ``start_all.ps1`` - Khởi động cả API và UI
- ``start.ps1`` - Main start script
- ``quick_restart.ps1`` - Restart nhanh services
- ``restart_and_test.ps1`` - Restart và chạy tests
- ``start_and_test_cove.ps1`` - Start và test Chain-of-Verification
- ``start_server.bat`` - Start server (Windows batch)

## Usage

``````powershell
# Khởi động API
.\launchers\start_api.ps1

# Khởi động UI
.\launchers\start_ui.ps1

# Khởi động tất cả
.\launchers\start_all.ps1
``````
"@

        "utilities\README.md" = @"
# Utility Scripts

Các script tiện ích để quản lý và kiểm tra hệ thống.

## Scripts

- ``check_embeddings.py`` - Kiểm tra page embeddings và FAISS index
- ``generate_doc_id_map.py`` - Tạo doc_id_map.json từ FAISS metadata
- ``generate_doc_id_map_full_paths.py`` - Tạo doc_id_map với full paths
- ``rag_cli.py`` - Command-line interface cho RAG queries
- ``run_all_tests.py`` - Chạy tất cả tests trong project

## Usage

``````bash
# Kiểm tra embeddings
python utilities/check_embeddings.py

# Tạo doc_id_map
python utilities/generate_doc_id_map.py

# CLI query
python utilities/rag_cli.py query "What is the operating pressure?"

# Chạy all tests
python utilities/run_all_tests.py
``````
"@

        "reports\README.md" = @"
# Reports

Thư mục chứa các báo cáo về tiến độ, fixes, và test results.

## Structure

- ``summaries/`` - Báo cáo tổng hợp về fixes, priorities, system status
- ``test_results/`` - Kết quả test runs và analysis

## Summaries

Chứa các file báo cáo:
- Priority completion summaries
- Fix summaries (Vision, Citation, CoVE, etc.)
- System readiness reports
- Restructure completion reports

## Test Results

Chứa:
- Test reports
- Test failure analysis
- Test instructions
"@

        "archive\README.md" = @"
# Archive

Thư mục lưu trữ code cũ, experiments, và files không còn sử dụng thường xuyên.

## Structure

- ``experiments/`` - Code thử nghiệm, POCs
- ``old_logs/`` - Các log files cũ (đã archived)

## Note

Files trong thư mục này có thể đã lỗi thời hoặc không còn tương thích với version hiện tại.
Tham khảo để hiểu lịch sử phát triển của project.
"@
    }

    foreach ($file in $readmes.Keys) {
        if ($DryRun) {
            Write-Status "[DRY RUN] Would create: $file" "Info"
        } else {
            if (-not (Test-Path $file) -or $Force) {
                $content = $readmes[$file]
                Set-Content -Path $file -Value $content -Encoding UTF8
                Write-Status "Created: $file" "Success"
            } else {
                Write-Status "Already exists: $file" "Info"
            }
        }
    }
}

function Show-Summary {
    Write-Status "`n===========================================" "Success"
    Write-Status "        Reorganization Complete!          " "Success"
    Write-Status "===========================================" "Success"

    Write-Host "`nNext Steps:" -ForegroundColor $InfoColor
    Write-Host "1. Review the changes: git status" -ForegroundColor White
    Write-Host "2. Test launchers: .\launchers\start_api.ps1" -ForegroundColor White
    Write-Host "3. Test utilities: python utilities\rag_cli.py --help" -ForegroundColor White
    Write-Host "4. Update documentation if needed" -ForegroundColor White
    Write-Host "5. Commit: git add . && git commit -m 'chore: reorganize project structure'" -ForegroundColor White
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        PVCFC RAG Project Reorganization Script              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

if ($DryRun) {
    Write-Status "Running in DRY RUN mode - no changes will be made" "Warning"
}

# Check if in project root
if (-not (Test-Path "app") -or -not (Test-Path "README.md")) {
    Write-Status "Error: Not in project root directory!" "Error"
    Write-Status "Please run this script from the project root." "Error"
    exit 1
}

# Create backup if requested
if (-not $SkipBackup -and -not $DryRun) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Write-Status "Creating backup commit..." "Info"

    if (Test-GitRepository) {
        try {
            git add -A
            git commit -m "backup: before reorganization $timestamp" 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Status "Backup commit created" "Success"
            }
        } catch {
            Write-Status "Warning: Could not create backup commit" "Warning"
        }
    }
}

# Execute reorganization
try {
    New-DirectoryStructure
    Move-LauncherScripts
    Move-UtilityScripts
    Move-TestScripts
    Move-SummaryReports
    Move-TestReports
    Move-LogFiles
    Move-BenchmarkResults
    Move-TestPowerShellScripts
    Move-ExperimentalCode
    Move-MiscFiles
    Create-READMEFiles

    if (-not $DryRun) {
        Show-Summary
    } else {
        Write-Status "`nDRY RUN completed. Run without -DryRun to apply changes." "Info"
    }

} catch {
    Write-Status "Error during reorganization: $_" "Error"
    exit 1
}
