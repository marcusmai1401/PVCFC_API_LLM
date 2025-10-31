# PLAN ĐẦY ĐỦ: FIX P&ID VÀ TEST 5 QUERIES

## TÓM TẮT VẤN ĐỀ ĐÃ PHÁT HIỆN

### Vấn Đề 1: Schema Mismatch (ĐÃ FIX ✅)
- **Root cause**: Code search top-level fields, data trong nested `parts.*`
- **Fix**: Updated `app/rag/indexers/opensearch_tags_retriever.py` (4 methods)
- **Status**: ✅ FIXED - Verified 5/5 unit tests PASS

### Vấn Đề 2: Missing Prefixes in Whitelist (ĐÃ FIX ✅)
- **Root cause**: PSV, TI, TXI, ZI không có trong `config/tag_grammar.yaml` whitelist
- **Impact**: 4/5 ground truth tags KHÔNG được extract
- **Fix**: Added 4 prefixes to whitelist
- **Status**: ✅ FIXED - Cần re-extract để apply

## CÁC FIX ĐÃ THỰC HIỆN

### Fix #1: opensearch_tags_retriever.py
```python
# Changed from top-level to nested paths:
{"term": {"prefix": x}}  →  {"term": {"parts.prefix.keyword": x}}
{"term": {"suffix": x}}  →  {"term": {"parts.suffix.keyword": x}}
{"term": {"unit": x}}    →  {"term": {"parts.unit.keyword": x}}
```

### Fix #2: tag_grammar.yaml
```yaml
Added prefixes:
  - PSV      # Pressure safety valve
  - TI       # Temperature indicator
  - TXI      # Temperature transmitter indicator
  - ZI       # Position indicator
```

## KẾ HOẠCH THỰC HIỆN ĐẦY ĐỦ

### PHASE 1: RE-EXTRACT TAGS (Required)

**Bước 1.1: Backup hiện tại**
```powershell
# Backup entities folder (nếu có data cũ)
Copy-Item "D:\PVCFC_Artifacts\entities" "D:\PVCFC_Artifacts\entities_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')" -Recurse -ErrorAction SilentlyContinue
```

**Bước 1.2: Clear old tags**
```powershell
# Remove old tags.jsonl if exists
Remove-Item "D:\PVCFC_Artifacts\entities\tags.jsonl" -ErrorAction SilentlyContinue
```

**Bước 1.3: Re-run ingestion với whitelist mới**
```powershell
# Activate venv_ingest (for PaddleOCR)
venv_ingest\Scripts\Activate.ps1

# Re-extract ONLY Ammonia PDF
python tools/ingest.py `
    --source-dir "D:\Data_Raw" `
    --output-dir "artifacts\ingestion_production" `
    --enable-ocr `
    --workers 2 `
    --enable-pid-tags

# Expected output:
# P&ID documents processed: 1
# P&ID tags extracted: 900-1000 (was 774-948, now should be MORE)
```

**Bước 1.4: Verify tags extracted**
```powershell
# Check tags file exists and count
Get-Content "D:\PVCFC_Artifacts\entities\tags.jsonl" | Measure-Object -Line

# Should show: 900-1000+ lines (increased from before)
```

### PHASE 2: RE-INDEX TAGS

**Bước 2.1: Switch to main venv**
```powershell
deactivate
.venv\Scripts\Activate.ps1
```

**Bước 2.2: Delete and recreate pvcfc_pid_tags index**
```powershell
python scripts/opensearch/create_tags_index.py --delete-if-exists
```

**Bước 2.3: Bulk upsert new tags**
```powershell
python scripts/opensearch/bulk_upsert_tags.py --tags-file "D:\PVCFC_Artifacts\entities\tags.jsonl"

# Expected output:
# Success: 900-1000 tags (much more than 207)
```

**Bước 2.4: Verify in OpenSearch**
```powershell
# Check count
Invoke-WebRequest -Uri "http://localhost:9200/pvcfc_pid_tags/_count" -UseBasicParsing

# Should show: {"count": 900-1000}

# Check prefixes
$body = '{"size": 0, "aggs": {"prefixes": {"terms": {"field": "parts.prefix.keyword", "size": 100}}}}'; Invoke-WebRequest -Uri "http://localhost:9200/pvcfc_pid_tags/_search" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing | ConvertFrom-Json | Select-Object -ExpandProperty aggregations | Select-Object -ExpandProperty prefixes | Select-Object -ExpandProperty buckets | Select-Object key, doc_count

# Should now include: PSV, TI, TXI, ZI, FIC
```

### PHASE 3: VERIFY GROUND TRUTH

```powershell
python verify_tag_exists.py
```

**Expected output:**
```
Tags found: 5/5
Correct page: 5/5
Required queries correct: 4/4 (or 5/5)
Status: READY TO TEST
```

### PHASE 4: RUN ACCURACY TEST

**Bước 4.1: Start API**
```powershell
# Terminal 1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Wait for:
# ✓ Initialized P&ID tags retriever
# ✓ Startup completed
```

**Bước 4.2: Run test (Terminal 2)**
```powershell
python test_pid_accuracy_5queries.py
```

**Expected:**
```
FINAL RESULTS: 4/5 or 5/5 queries passed
Required queries (1-4): 4/4 passed
STATUS: SUCCESS
```

### PHASE 5: DEBUG IF NEEDED

Nếu bất kỳ Query 1-4 nào FAIL:

```powershell
# Example: Query 1 failed
python debug_pid_pipeline.py "04 PSV 3926" 41 "Tìm cho tôi tag name 04 PSV 3926 trong bản vẽ P&ID"
```

Output sẽ show layer nào fail:
- Layer 1 fail: Tag không trong OpenSearch
- Layer 2 fail: Tags retriever search logic sai
- Layer 3 fail: PIDQueryEnhancer không detect
- Layer 4 fail: Hybrid retriever không merge
- Layer 5 fail: API response formatting

### PHASE 6: GENERATE REPORT

```powershell
python generate_test_report.py

# Creates: TEST_REPORT_YYYYMMDD_HHMMSS.md
```

## TIMELINE DỰ KIẾN

| Phase | Task | Time |
|-------|------|------|
| 1 | Re-extract tags | 2-3 phút |
| 2 | Re-index tags | 30-60 giây |
| 3 | Verify ground truth | 10 giây |
| 4 | Run accuracy test | 10-15 phút (5 queries × 3 variants × 120s timeout) |
| 5 | Debug (if needed) | 5-10 phút per query |
| 6 | Generate report | 5 giây |

**Total**: 15-30 phút (nếu all PASS), 30-60 phút (nếu cần debug)

## SUCCESS CRITERIA

✅ **Minimum (Required):**
- Query 1-4: 4/4 PASS
- Each PASS = expected page in top-5 citations

🎯 **Target (Ideal):**
- All 5/5 PASS
- Bbox present in citations
- Confidence ≥ 0.7

## FILES CREATED

### Production Code (Modified)
1. ✅ `app/rag/indexers/opensearch_tags_retriever.py` - Search fix
2. ✅ `config/tag_grammar.yaml` - Whitelist expanded
3. ✅ `SYSTEM_ARCHITECTURE.md` - Documentation updates

### Test Scripts
1. ✅ `verify_tag_exists.py` - Ground truth sanity check
2. ✅ `test_pid_accuracy_5queries.py` - Main accuracy test (5 queries × 3 variants)
3. ✅ `debug_pid_pipeline.py` - 6-layer debugger for failed queries
4. ✅ `generate_test_report.py` - Report formatter

### Documentation
1. ✅ `P&ID_AUDIT_REPORT.md` - Audit findings
2. ✅ `QUICK_TEST_P&ID_FIX.md` - Quick test guide
3. ✅ `MISSING_PREFIXES_ANALYSIS.md` - Whitelist analysis
4. ✅ `FIX_AND_TEST_PLAN.md` - This file

### Temporary (Will generate)
- `TEST_RESULTS_{timestamp}.json` - Raw test data
- `TEST_REPORT_{timestamp}.md` - Formatted report

## NEXT STEPS

Bạn có 2 options:

**Option A: Tự động chạy toàn bộ plan (Recommended)**
- Tôi sẽ chạy Phase 1-6 tự động
- Báo cáo kết quả cuối cùng
- Debug nếu cần

**Option B: Manual step-by-step**
- Bạn tự chạy từng bước
- Tôi hỗ trợ khi cần

Bạn chọn option nào?
