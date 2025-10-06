# Kế hoạch Tổ chức lại Thư mục Gốc - PVCFC RAG Project

## 📋 Tổng quan

Thư mục gốc hiện tại đang rất lộn xộn với nhiều file .py, .md, .txt, .ps1, .json nằm rải rác. Cần sắp xếp lại để dễ quản lý và maintain.

---

## 🎯 Mục tiêu

1. ✅ Tổ chức file theo chức năng và mục đích sử dụng
2. ✅ Giữ lại cấu trúc thư mục quan trọng (app/, tests/, tools/, docs/, scripts/)
3. ✅ Di chuyển files không thường xuyên sử dụng vào các thư mục phù hợp
4. ✅ Đảm bảo không làm ảnh hưởng đến hoạt động của hệ thống
5. ✅ Tạo README trong các thư mục mới để giải thích

---

## 📂 Cấu trúc Thư mục Mới (Đề xuất)

```
root/
├── app/                     [GIỮ NGUYÊN - Source code chính]
├── tests/                   [GIỮ NGUYÊN - Unit tests]
├── tools/                   [GIỮ NGUYÊN - CLI tools & utilities]
├── scripts/                 [GIỮ NGUYÊN - Dev scripts]
├── docs/                    [GIỮ NGUYÊN - Documentation]
├── streamlit_app/           [GIỮ NGUYÊN - UI app]
├── data/                    [GIỮ NGUYÊN - Data files]
├── artifacts/               [GIỮ NGUYÊN - Build artifacts]
├── config/                  [GIỮ NGUYÊN - Config files]
├── logs/                    [GIỮ NGUYÊN - Logs]
├── results/                 [GIỮ NGUYÊN - Test results]
├── Build_plan_README/       [GIỮ NGUYÊN - Build plans]
├── CHANGLOG_README/         [GIỮ NGUYÊN - Changelogs]
├── Pipeline/                [GIỮ NGUYÊN - Pipeline diagrams]
│
├── launchers/               [MỚI - Launch scripts]
│   ├── start_api.ps1
│   ├── start_ui.ps1
│   ├── start_all.ps1
│   ├── quick_restart.ps1
│   └── README.md
│
├── utilities/               [MỚI - Utility scripts]
│   ├── check_embeddings.py
│   ├── generate_doc_id_map.py
│   ├── rag_cli.py
│   ├── run_all_tests.py
│   └── README.md
│
├── reports/                 [MỚI - Reports & summaries]
│   ├── summaries/          [Priority summaries, fix summaries]
│   ├── test_results/       [Test reports]
│   └── README.md
│
├── archive/                 [MỚI - Old/deprecated files]
│   ├── experiments/        [Experimental code]
│   ├── old_logs/           [Old log files]
│   └── README.md
│
├── README.md                [GIỮ NGUYÊN - Main readme]
├── requirements.txt         [GIỮ NGUYÊN - Dependencies]
├── Dockerfile               [GIỮ NGUYÊN - Docker config]
├── Makefile                 [GIỮ NGUYÊN - Make commands]
├── env.example              [GIỮ NGUYÊN - Env template]
└── .gitignore               [GIỮ NGUYÊN - Git ignore]
```

---

## 📝 Chi tiết Kế hoạch Di chuyển

### PHASE 1: Phân tích & Phân loại Files (HIỆN TẠI)

#### 1.1 Files Python (.py) ở Root - Cần Di chuyển

**Utility Scripts** → `utilities/`:
- ✅ `check_embeddings.py` - Kiểm tra page embeddings
- ✅ `generate_doc_id_map.py` - Tạo doc_id map từ FAISS
- ✅ `generate_doc_id_map_full_paths.py` - Tạo doc_id map với full paths
- ✅ `rag_cli.py` - CLI interface cho RAG queries
- ✅ `run_all_tests.py` - Test suite runner

**Test Scripts** → `tests/integration/` hoặc `archive/experiments/`:
- ✅ `test_5am_fix.py` - Test 5AM fix
- ✅ `test_citation_retriever.py` - Test citation retriever
- ✅ `test_config.py` - Test configuration
- ✅ `test_cove_fix.py` - Test CoVE fix
- ✅ `test_hybrid_ranking_integration.py` - Test hybrid ranking
- ✅ `test_ocr_cached.py` - Test OCR caching
- ✅ `test_paddleocr_integration.py` - Test PaddleOCR
- ✅ `test_page_reranker.py` - Test page reranker
- ✅ `test_page_reranker_semantic.py` - Test semantic reranker
- ✅ `test_pdf_citations.py` - Test PDF citations
- ✅ `test_post_validation_fix.py` - Test post validation
- ✅ `test_priority1_fixes.py` - Test priority 1 fixes
- ✅ `test_retrieval_details.py` - Test retrieval details
- ✅ `test_snippet_extractor.py` - Test snippet extraction
- ✅ `test_tokenization.py` - Test tokenization
- ✅ `test_vision_citation_fixes.py` - Test vision citation fixes

#### 1.2 Files Markdown (.md) ở Root - Cần Di chuyển

**Summary Reports** → `reports/summaries/`:
- ✅ `ALL_PRIORITIES_COMPLETE_SUMMARY.md` - Tổng hợp hoàn thành tất cả priorities
- ✅ `ALL_UI_FIXES_FINAL_SUMMARY.md` - Tổng hợp UI fixes
- ✅ `CITEFIX_COMPLETION_SUMMARY.md` - Tổng hợp citation fixes
- ✅ `FIX_COVE_WARNINGS_SUMMARY.md` - CoVE warnings fixes
- ✅ `FIX_RETRIEVAL_DETAILS_SUMMARY.md` - Retrieval details fixes
- ✅ `FIX_VISION_VERIFY_UI_SUMMARY.md` - Vision verify UI fixes
- ✅ `FIXES_REVIEW_AND_RECOMMENDATIONS.md` - Review và khuyến nghị
- ✅ `PRIORITY1_FIXES_SUMMARY.md` - Priority 1 fixes
- ✅ `PRIORITY2_PDF_CITATIONS_SUMMARY.md` - Priority 2 PDF citations
- ✅ `PRIORITY3_COVE_IMPROVEMENTS_SUMMARY.md` - Priority 3 CoVE
- ✅ `VISION_CITATION_4_FIXES_SUMMARY.md` - Vision citation 4 fixes
- ✅ `VISION_CITATION_FIXES_EXECUTIVE_SUMMARY.md` - Executive summary
- ✅ `VISION_FIXES_INDEX.md` - Vision fixes index
- ✅ `SYSTEM_READINESS_REPORT.md` - System readiness report
- ✅ `RESTRUCTURE_COMPLETE.md` - Restructure completion

**Test Reports** → `reports/test_results/`:
- ✅ `test_report.md` - Test report
- ✅ `TEST_FAILURE_ANALYSIS.md` - Test failure analysis
- ✅ `TEST_INSTRUCTIONS.md` - Test instructions

**Documentation** → `docs/` (có thể cân nhắc consolidate):
- ⚠️ Các file này CÓ THỂ đã có trong `docs/` hoặc `Build_plan_README/`

#### 1.3 Files Text (.txt) ở Root - Cần Di chuyển

**Logs** → `logs/archived/`:
- ✅ `analysis_output.txt` - Analysis output
- ✅ `audit_run.txt` - Audit run log
- ✅ `reindex_phase1_log.txt` - Reindex phase 1 log
- ✅ `server_error.txt` - Server error log
- ✅ `server_output.txt` - Server output log
- ✅ `test_vision_fixes_report_20251004_172105.txt` - Test report
- ✅ `test_vision_fixes_report_20251004_172653.txt` - Test report

**Documentation** → `docs/` hoặc giữ root:
- ⚠️ `QUICK_TEST_GUIDE.txt` - Có thể chuyển thành .md và vào docs/
- ⚠️ `COMMIT_MSG_VISION_CITATION_FIX.txt` - Archive hoặc xóa nếu đã commit

**Keep in Root**:
- ✅ `requirements.txt` - GIỮ NGUYÊN

#### 1.4 Files PowerShell (.ps1) ở Root - Cần Di chuyển

**Launcher Scripts** → `launchers/`:
- ✅ `start_api.ps1` - Khởi động API server
- ✅ `start_ui.ps1` - Khởi động Streamlit UI
- ✅ `start_all.ps1` - Khởi động tất cả services
- ✅ `start.ps1` - Main start script
- ✅ `quick_restart.ps1` - Quick restart script
- ✅ `restart_and_test.ps1` - Restart và test
- ✅ `start_and_test_cove.ps1` - Start và test CoVE

**Test Scripts** → `scripts/test_scripts/` (đã có folder này):
- ✅ `run_task2_test.ps1` - Task 2 test
- ✅ `run_task2_test_v2.ps1` - Task 2 test v2
- ✅ `run_verify_v5.ps1` - Verify v5

**Keep in Root** (nếu là entry points chính):
- ⚠️ Cân nhắc giữ `start.ps1`, `start_api.ps1` ở root để dễ access

#### 1.5 Files JSON ở Root - Cần Di chuyển

**Benchmark Results** → `results/benchmarks/`:
- ✅ `benchmark_cpu_vs_gpu_results.json` - CPU vs GPU benchmark
- ✅ `ocr_language_survey_baseline.json` - OCR language survey

**Keep in artifacts/** (đã có):
- ✅ Files trong `artifacts/` - GIỮ NGUYÊN

#### 1.6 Files BAT ở Root - Cần Di chuyển

**Launcher Scripts** → `launchers/`:
- ✅ `start_server.bat` - Start server script

#### 1.7 Thư mục ở Root - Xem xét

**Experimental Code** → `archive/experiments/`:
- ⚠️ `AIstudio google/` - Có vẻ là experimental code với Gemini models
  - Chứa: `gemini-2.5-flash.py`, `gemini-2.5-pro.py`
  - Nếu không dùng nữa → archive
  - Nếu còn dùng → giữ hoặc move vào `tools/experimental/`

**Temporary/Done Folders** → `archive/`:
- ⚠️ `DONE_100%/` - Nếu là folder đánh dấu completion, có thể xóa hoặc archive
- ⚠️ `manifests/` - Kiểm tra nội dung, có thể thuộc artifacts hoặc archive

---

## 🔧 PHASE 2: Tạo Cấu trúc Thư mục Mới

### Step 1: Tạo các thư mục mới

```powershell
# Tạo thư mục chính
New-Item -ItemType Directory -Path "launchers" -Force
New-Item -ItemType Directory -Path "utilities" -Force
New-Item -ItemType Directory -Path "reports" -Force
New-Item -ItemType Directory -Path "archive" -Force

# Tạo thư mục con
New-Item -ItemType Directory -Path "reports\summaries" -Force
New-Item -ItemType Directory -Path "reports\test_results" -Force
New-Item -ItemType Directory -Path "archive\experiments" -Force
New-Item -ItemType Directory -Path "logs\archived" -Force
New-Item -ItemType Directory -Path "results\benchmarks" -Force
```

---

## 📦 PHASE 3: Di chuyển Files

### 3.1 Di chuyển Launcher Scripts

```powershell
# Di chuyển launcher scripts
Move-Item "start_api.ps1" "launchers\" -Force
Move-Item "start_ui.ps1" "launchers\" -Force
Move-Item "start_all.ps1" "launchers\" -Force
Move-Item "start.ps1" "launchers\" -Force
Move-Item "quick_restart.ps1" "launchers\" -Force
Move-Item "restart_and_test.ps1" "launchers\" -Force
Move-Item "start_and_test_cove.ps1" "launchers\" -Force
Move-Item "start_server.bat" "launchers\" -Force
```

### 3.2 Di chuyển Utility Scripts

```powershell
# Di chuyển utility scripts
Move-Item "check_embeddings.py" "utilities\" -Force
Move-Item "generate_doc_id_map.py" "utilities\" -Force
Move-Item "generate_doc_id_map_full_paths.py" "utilities\" -Force
Move-Item "rag_cli.py" "utilities\" -Force
Move-Item "run_all_tests.py" "utilities\" -Force
```

### 3.3 Di chuyển Test Scripts

```powershell
# Di chuyển test scripts vào tests/integration/
$testScripts = @(
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

foreach ($script in $testScripts) {
    if (Test-Path $script) {
        Move-Item $script "tests\integration\" -Force
    }
}
```

### 3.4 Di chuyển Summary Reports

```powershell
# Di chuyển summary reports
$summaryReports = @(
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

foreach ($report in $summaryReports) {
    if (Test-Path $report) {
        Move-Item $report "reports\summaries\" -Force
    }
}
```

### 3.5 Di chuyển Test Reports

```powershell
# Di chuyển test reports
$testReports = @(
    "test_report.md",
    "TEST_FAILURE_ANALYSIS.md",
    "TEST_INSTRUCTIONS.md"
)

foreach ($report in $testReports) {
    if (Test-Path $report) {
        Move-Item $report "reports\test_results\" -Force
    }
}
```

### 3.6 Di chuyển Log Files

```powershell
# Di chuyển old logs
$logFiles = @(
    "analysis_output.txt",
    "audit_run.txt",
    "reindex_phase1_log.txt",
    "server_error.txt",
    "server_output.txt",
    "test_vision_fixes_report_20251004_172105.txt",
    "test_vision_fixes_report_20251004_172653.txt"
)

foreach ($log in $logFiles) {
    if (Test-Path $log) {
        Move-Item $log "logs\archived\" -Force
    }
}
```

### 3.7 Di chuyển Benchmark Results

```powershell
# Di chuyển benchmark results
Move-Item "benchmark_cpu_vs_gpu_results.json" "results\benchmarks\" -Force -ErrorAction SilentlyContinue
Move-Item "ocr_language_survey_baseline.json" "results\benchmarks\" -Force -ErrorAction SilentlyContinue
```

### 3.8 Di chuyển Test PowerShell Scripts

```powershell
# Di chuyển test PowerShell scripts
Move-Item "run_task2_test.ps1" "scripts\test_scripts\" -Force -ErrorAction SilentlyContinue
Move-Item "run_task2_test_v2.ps1" "scripts\test_scripts\" -Force -ErrorAction SilentlyContinue
Move-Item "run_verify_v5.ps1" "scripts\test_scripts\" -Force -ErrorAction SilentlyContinue
```

### 3.9 Di chuyển Experimental Code

```powershell
# Di chuyển AIstudio google nếu không còn dùng
if (Test-Path "AIstudio google") {
    Move-Item "AIstudio google" "archive\experiments\" -Force
}
```

### 3.10 Xử lý DONE_100% folder

```powershell
# Archive hoặc xóa DONE_100%
if (Test-Path "DONE_100%") {
    # Option 1: Archive
    Move-Item "DONE_100%" "archive\" -Force

    # Option 2: Xóa (nếu chắc chắn không cần)
    # Remove-Item "DONE_100%" -Recurse -Force
}
```

### 3.11 Xử lý các files khác

```powershell
# Di chuyển COMMIT_MSG nếu đã commit
if (Test-Path "COMMIT_MSG_VISION_CITATION_FIX.txt") {
    Move-Item "COMMIT_MSG_VISION_CITATION_FIX.txt" "archive\" -Force
}

# Chuyển QUICK_TEST_GUIDE.txt thành .md và move vào docs
if (Test-Path "QUICK_TEST_GUIDE.txt") {
    Copy-Item "QUICK_TEST_GUIDE.txt" "docs\QUICK_TEST_GUIDE.md" -Force
    Move-Item "QUICK_TEST_GUIDE.txt" "archive\" -Force
}
```

---

## 📚 PHASE 4: Tạo README Files

### 4.1 launchers/README.md

```markdown
# Launcher Scripts

Scripts để khởi động các services của PVCFC RAG.

## Scripts

- `start_api.ps1` - Khởi động FastAPI backend server
- `start_ui.ps1` - Khởi động Streamlit UI
- `start_all.ps1` - Khởi động cả API và UI
- `start.ps1` - Main start script
- `quick_restart.ps1` - Restart nhanh services
- `restart_and_test.ps1` - Restart và chạy tests
- `start_and_test_cove.ps1` - Start và test Chain-of-Verification
- `start_server.bat` - Start server (Windows batch)

## Usage

```powershell
# Khởi động API
.\launchers\start_api.ps1

# Khởi động UI
.\launchers\start_ui.ps1

# Khởi động tất cả
.\launchers\start_all.ps1
```
```

### 4.2 utilities/README.md

```markdown
# Utility Scripts

Các script tiện ích để quản lý và kiểm tra hệ thống.

## Scripts

- `check_embeddings.py` - Kiểm tra page embeddings và FAISS index
- `generate_doc_id_map.py` - Tạo doc_id_map.json từ FAISS metadata
- `generate_doc_id_map_full_paths.py` - Tạo doc_id_map với full paths
- `rag_cli.py` - Command-line interface cho RAG queries
- `run_all_tests.py` - Chạy tất cả tests trong project

## Usage

```bash
# Kiểm tra embeddings
python utilities/check_embeddings.py

# Tạo doc_id_map
python utilities/generate_doc_id_map.py

# CLI query
python utilities/rag_cli.py query "What is the operating pressure?"

# Chạy all tests
python utilities/run_all_tests.py
```
```

### 4.3 reports/README.md

```markdown
# Reports

Thư mục chứa các báo cáo về tiến độ, fixes, và test results.

## Structure

- `summaries/` - Báo cáo tổng hợp về fixes, priorities, system status
- `test_results/` - Kết quả test runs và analysis

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
```

### 4.4 archive/README.md

```markdown
# Archive

Thư mục lưu trữ code cũ, experiments, và files không còn sử dụng thường xuyên.

## Structure

- `experiments/` - Code thử nghiệm, POCs
- `old_logs/` - Các log files cũ (đã archived)

## Note

Files trong thư mục này có thể đã lỗi thời hoặc không còn tương thích với version hiện tại.
Tham khảo để hiểu lịch sử phát triển của project.
```

---

## 🔍 PHASE 5: Cập nhật References

### 5.1 Cập nhật Scripts References

Các scripts có thể cần cập nhật path:

1. **Launcher scripts trong `scripts/`**:
   - Kiểm tra nếu có reference đến `start_api.ps1`, etc.
   - Cập nhật path từ `..\start_api.ps1` → `..\launchers\start_api.ps1`

2. **Documentation trong `docs/`**:
   - Tìm kiếm references đến files đã di chuyển
   - Cập nhật paths trong documentation

3. **GitHub Actions / CI/CD**:
   - Kiểm tra `.github/workflows/` nếu có
   - Cập nhật paths trong workflow files

### 5.2 Cập nhật Import Paths

Kiểm tra nếu có Python scripts import từ files đã di chuyển:

```python
# Old
from check_embeddings import something

# New
from utilities.check_embeddings import something
```

---

## ✅ PHASE 6: Verification Checklist

### 6.1 Kiểm tra Structure

- [ ] Tất cả launcher scripts đã trong `launchers/`
- [ ] Tất cả utility scripts đã trong `utilities/`
- [ ] Tất cả test scripts đã trong `tests/integration/`
- [ ] Tất cả summary reports đã trong `reports/summaries/`
- [ ] Tất cả test reports đã trong `reports/test_results/`
- [ ] Tất cả old logs đã trong `logs/archived/`
- [ ] Tất cả benchmark results đã trong `results/benchmarks/`
- [ ] Experimental code đã trong `archive/experiments/`
- [ ] README files đã được tạo trong các thư mục mới

### 6.2 Kiểm tra Functionality

- [ ] Launcher scripts vẫn hoạt động (test `launchers/start_api.ps1`)
- [ ] Utility scripts vẫn chạy được (test `python utilities/rag_cli.py --help`)
- [ ] Test scripts vẫn executable (test `python tests/integration/test_config.py`)
- [ ] Import paths không bị break
- [ ] Documentation references đã được cập nhật

### 6.3 Kiểm tra Root Folder

Sau khi reorganize, root folder chỉ nên chứa:

**Core Files (Essential)**:
- ✅ `README.md`
- ✅ `requirements.txt`
- ✅ `Dockerfile`
- ✅ `Makefile`
- ✅ `env.example`
- ✅ `.gitignore`
- ✅ `.git/` (nếu có)

**Core Directories**:
- ✅ `app/` - Source code
- ✅ `tests/` - Tests
- ✅ `tools/` - Tools
- ✅ `scripts/` - Scripts
- ✅ `docs/` - Documentation
- ✅ `streamlit_app/` - UI
- ✅ `data/` - Data
- ✅ `artifacts/` - Build artifacts
- ✅ `config/` - Config
- ✅ `logs/` - Logs
- ✅ `results/` - Results
- ✅ `Build_plan_README/` - Build plans
- ✅ `CHANGLOG_README/` - Changelogs
- ✅ `Pipeline/` - Pipeline diagrams
- ✅ `venv/` - Virtual environment

**New Directories**:
- ✅ `launchers/` - Launch scripts
- ✅ `utilities/` - Utility scripts
- ✅ `reports/` - Reports
- ✅ `archive/` - Archived files

---

## 🚀 PHASE 7: Execution

### Automated Script

Tạo file `reorganize_project.ps1` để tự động hóa:

```powershell
# See attached script in next section
```

### Manual Verification

Sau khi chạy script:
1. Kiểm tra git status: `git status`
2. Review changes: `git diff`
3. Test các scripts chính
4. Commit changes: `git add . && git commit -m "chore: reorganize project structure"`

---

## 📊 Tổng kết Files Di chuyển

### Statistics

- **Python files**: ~21 files → `utilities/`, `tests/integration/`
- **Markdown files**: ~18 files → `reports/summaries/`, `reports/test_results/`
- **Text files**: ~7 files → `logs/archived/`, `archive/`
- **PowerShell files**: ~10 files → `launchers/`, `scripts/test_scripts/`
- **JSON files**: ~2 files → `results/benchmarks/`
- **Batch files**: ~1 file → `launchers/`
- **Directories**: ~2 folders → `archive/experiments/`

**Total**: ~61 files/folders di chuyển

---

## ⚠️ Lưu ý Quan trọng

1. **Backup trước khi thực hiện**: Tạo backup hoặc commit code hiện tại
2. **Test sau khi di chuyển**: Đảm bảo hệ thống vẫn hoạt động
3. **Update documentation**: Cập nhật paths trong docs
4. **Git tracking**: Sử dụng `git mv` thay vì `Move-Item` để giữ history
5. **Team communication**: Thông báo team về thay đổi cấu trúc

---

## 🔄 Next Steps

Sau khi hoàn thành reorganization:

1. ✅ Update main README.md với cấu trúc mới
2. ✅ Update CONTRIBUTING.md (nếu có)
3. ✅ Update .gitignore nếu cần
4. ✅ Tạo PR với description đầy đủ
5. ✅ Review với team
6. ✅ Merge và deploy

---

**Created**: 2025-10-07
**Status**: Ready for Review
**Estimated Time**: 2-3 hours (với verification)
