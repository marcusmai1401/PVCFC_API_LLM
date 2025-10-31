# KẾ HOẠCH AUDIT TOÀN DIỆN HỆ THỐNG P&ID

**Ngày tạo:** 2025-10-23
**Mục tiêu:** Tìm toàn bộ vấn đề trong pipeline P&ID (ingestion → indexing → query) để lên kế hoạch fix
**Accuracy target:** 4/5 queries đúng (tối thiểu), tốt nhất 5/5 queries đúng
**Ground truth:** `test_pid.md` (100% chính xác, tuyệt đối tin cậy)

---

## 📋 TÓM TẮT EXECUTIVE

### Ground Truth Test Cases

| Query | Tag | Expected Page | Status | Độ ưu tiên |
|-------|-----|--------------|--------|-----------|
| Q1 | `04 PSV 3926` | 41/117 | ❓ Chưa test | P0 |
| Q2 | `04 TI 5058` | 58/117 | ❓ Chưa test | P0 |
| Q3 | `04 TXI 2077` | 17/117 | ❓ Chưa test | P0 |
| Q4 | `04 ZI 4502` | 100/117 | ❓ Chưa test | P0 |
| Q5 | `06 FIC 1134` | 103/117 | ❓ Chưa test | P1 - tolerant |

**Source File:** `D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf`

### Kiến trúc hệ thống đã xác nhận

```
┌─────────────────────────────────────────────────────────────┐
│                    INGESTION PHASE                           │
│  Input: D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf│
│  ↓                                                           │
│  CAD-like Gate (threshold: 0.55) → Phân loại P&ID           │
│  ↓                                                           │
│  Page Layout Extraction (bbox, font, vector drawings)       │
│  ↓                                                           │
│  Tag Extraction (CODE-anchored triplets: UNIT-PREFIX-SUFFIX)│
│  ↓                                                           │
│  Output:                                                     │
│    - chunks.jsonl (text chunks)                              │
│    - tags.jsonl (extracted tags với bbox) ⭐                │
│    - page_layout/*.json (spatial layout) ⭐                 │
│    - crops/*.png (tag bounding box images) ⭐               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     INDEXING PHASE                           │
│  tags.jsonl → OpenSearch `pvcfc_pid_tags` index ⭐         │
│  chunks.jsonl → OpenSearch `rag_chunks` index               │
│  chunks.jsonl → Weaviate `Chunk` collection                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      QUERY PHASE                             │
│  User Query (Vietnamese + query_type="pid")                 │
│  ↓                                                           │
│  PIDQueryEnhancer:                                           │
│    - Detect tag components (unit, prefix, suffix)           │
│    - Generate variants (04 PSV 3926, 04-PSV-3926, etc)     │
│  ↓                                                           │
│  DUAL BRANCH RETRIEVAL (Parallel):                          │
│    Branch A: pvcfc_pid_tags search (exact tag match) ⭐    │
│    Branch B: rag_chunks search (semantic + BM25)            │
│  ↓                                                           │
│  RRF Fusion → PID Tag Reranking → BGE Rerank (optional)    │
│  ↓                                                           │
│  Response với citations (doc_id + page + bbox + crop_path) │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 LAYER 1: INGESTION & DATA AUDIT

### 1.1 Kiểm tra file source có tồn tại và integrity

**Command:**
```powershell
Test-Path "D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
Get-FileHash "D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf" -Algorithm SHA256
```

**Expected:**
- File tồn tại ✅
- SHA-256 hash khớp với telemetry logs

**Potential Issues:**
- ❌ File bị corrupt
- ❌ File không accessible (quyền đọc)
- ❌ Wrong file path hoặc typo

---

### 1.2 Xác nhận CAD-like Gate đã classify đúng

**Data to check:**
- File: `artifacts/ingestion_production/logs/tag_extraction_telemetry.jsonl`
- Tìm entry cho document này

**Command:**
```powershell
Get-Content "artifacts\ingestion_production\logs\tag_extraction_telemetry.jsonl" | Select-String "01. P&ID Ammonia Unit Rev12" | ConvertFrom-Json
```

**Expected fields:**
```json
{
  "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_...",
  "cadlike_score": ≥ 0.55,
  "is_cadlike": true,
  "tags_found_total": > 0,
  "pages_processed": [...],
  ...
}
```

**Potential Issues:**
- ❌ `cadlike_score < 0.55` → Document được xử lý như technical doc thay vì P&ID
- ❌ `tags_found_total = 0` → Tag extraction failed hoàn toàn
- ❌ `is_cadlike = false` → CAD gate không detect, không có tags được extract

**Severity:** **P0 CRITICAL** - Nếu CAD gate sai, toàn bộ pipeline P&ID không chạy

---

### 1.3 Kiểm tra tags.jsonl có chứa 5 tags test không

**File location:** `artifacts/ingestion_production/entities/tags.jsonl`

**Command:**
```powershell
# Search for each tag
$tags = @("04 PSV 3926", "04 TI 5058", "04 TXI 2077", "04 ZI 4502", "06 FIC 1134")
foreach ($tag in $tags) {
    $found = Get-Content "artifacts\ingestion_production\entities\tags.jsonl" | Select-String $tag
    if ($found) {
        Write-Host "✓ Found: $tag" -ForegroundColor Green
        # Parse line để xem page number
        $found | ConvertFrom-Json | Select-Object tag, page, bbox, confidence
    } else {
        Write-Host "✗ MISSING: $tag" -ForegroundColor Red
    }
}
```

**Expected cho mỗi tag:**
```json
{
  "tag": "04 PSV 3926",
  "page": 41,  // ← Must match expected page
  "parts": {
    "unit": "04",
    "prefix": "PSV",
    "suffix": "3926",
    "variant": null
  },
  "bbox": [x0, y0, x1, y1],  // Non-null
  "confidence": > 0.5,
  "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_...",
  "crop_path": "crops/..." // Or null if lazy
}
```

**Potential Issues:**

| Issue | Severity | Symptom | Root Cause Hypothesis |
|-------|----------|---------|----------------------|
| Tag không tồn tại trong tags.jsonl | **P0** | 0 results từ API | Tag extraction regex miss tag format |
| Page number sai | **P0** | Wrong page trong response | Off-by-one error (0-based vs 1-based) |
| Tag format khác (04-PSV-3926 thay vì 04 PSV 3926) | **P1** | Retrieval miss do variant không match | Normalization inconsistent |
| bbox = null hoặc invalid | **P2** | Không ảnh hưởng retrieval nhưng mất spatial context | Layout extraction issue |
| confidence < 0.5 | **P2** | Tag có thể bị filter | Threshold quá cao |

**Fix actions nếu lỗi:**
- Re-run ingestion với debug mode để trace tag extraction
- Check config: `config/tag_grammar.yaml` - regex patterns
- Check config: `config/page_filters.yaml` - exclusion zones
- Verify PP-OCR output nếu PDF là scan

---

### 1.4 Kiểm tra page_layout có spatial data không

**File pattern:** `artifacts/ingestion_production/page_layout/page_{doc_id}_{page}.json`

**Example check for Q1 (page 41):**
```powershell
$doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"  # Replace with actual
$page = 41
Get-Content "artifacts\ingestion_production\page_layout\page_${doc_id}_${page}.json" | ConvertFrom-Json
```

**Expected:**
- File tồn tại
- Contains text spans với bbox
- Contains vector drawings (lines, circles, rectangles)

**Potential Issues:**
- ❌ File không tồn tại → Layout extraction skipped
- ❌ Empty spans → No text extracted từ page (possible OCR fail)

**Severity:** **P1** - Không critical cho retrieval nhưng ảnh hưởng tag extraction quality

---

## 🔍 LAYER 2: INDEXING AUDIT

### 2.1 Verify pvcfc_pid_tags index tồn tại và healthy

**Commands:**
```powershell
# Check index exists
curl http://localhost:9200/_cat/indices?v | Select-String "pvcfc_pid_tags"

# Get index stats
curl http://localhost:9200/pvcfc_pid_tags/_count

# Get mapping
curl http://localhost:9200/pvcfc_pid_tags/_mapping | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Expected:**
- Index tồn tại: `pvcfc_pid_tags` (open, green/yellow)
- Document count: > 0 (ideally > 200 dựa trên audit report cũ)
- Mapping có fields:
  - `tag` (text + keyword multi-field) ⭐
  - `page` (integer)
  - `doc_id` (keyword)
  - `parts` (nested object với `unit`, `prefix`, `suffix`, `variant`) ⭐
  - `bbox` (array of float)
  - `confidence` (float)
  - `crop_path` (keyword, nullable)

**Potential Issues:**

| Issue | Severity | Detection | Fix |
|-------|----------|-----------|-----|
| Index không tồn tại | **P0** | _cat/indices không có entry | Run `scripts/opensearch/create_tags_index.py` |
| Document count = 0 | **P0** | _count = 0 | Run `scripts/opensearch/bulk_upsert_tags.py` |
| Mapping thiếu `tag.keyword` | **P0** | Exact term search fail | Re-create index với correct mapping |
| Mapping thiếu nested `parts.*` | **P0** | Component search fail | Re-create index (đây là lỗi đã fix trong P&ID_AUDIT_REPORT.md) |

---

### 2.2 Test exact term search cho từng tag

**Critical Test:** Đây là test quan trọng nhất để verify data layer

**Command template:**
```powershell
$body = @"
{
  "size": 5,
  "query": {
    "term": {
      "tag.keyword": "04 PSV 3926"
    }
  },
  "_source": ["tag", "page", "doc_id", "parts", "bbox"]
}
"@

curl -X POST "http://localhost:9200/pvcfc_pid_tags/_search" -H "Content-Type: application/json" -d $body | ConvertFrom-Json
```

**Run cho tất cả 5 tags:**

#### Q1: 04 PSV 3926 (expected page 41)
```json
{
  "query": {
    "term": { "tag.keyword": "04 PSV 3926" }
  }
}
```

**Expected hit:**
```json
{
  "_source": {
    "tag": "04 PSV 3926",
    "page": 41,
    "parts": {
      "unit": "04",
      "prefix": "PSV",
      "suffix": "3926"
    }
  }
}
```

#### Q2: 04 TI 5058 (expected page 58)
```json
{
  "query": {
    "term": { "tag.keyword": "04 TI 5058" }
  }
}
```

#### Q3: 04 TXI 2077 (expected page 17)
```json
{
  "query": {
    "term": { "tag.keyword": "04 TXI 2077" }
  }
}
```

#### Q4: 04 ZI 4502 (expected page 100)
```json
{
  "query": {
    "term": { "tag.keyword": "04 ZI 4502" }
  }
}
```

#### Q5: 06 FIC 1134 (expected page 103)
```json
{
  "query": {
    "term": { "tag.keyword": "06 FIC 1134" }
  }
}
```

**Scoring matrix:**

| Tag | Found? | Page Match? | Issue | Fix Priority |
|-----|--------|-------------|-------|--------------|
| 04 PSV 3926 | ✅/❌ | ✅/❌ | ... | P0/P1/P2 |
| 04 TI 5058 | ✅/❌ | ✅/❌ | ... | P0/P1/P2 |
| 04 TXI 2077 | ✅/❌ | ✅/❌ | ... | P0/P1/P2 |
| 04 ZI 4502 | ✅/❌ | ✅/❌ | ... | P0/P1/P2 |
| 06 FIC 1134 | ✅/❌ | ✅/❌ | ... | P1 (tolerant) |

**Potential Issues nếu FAIL:**

1. **Tag không found (0 hits):**
   - Hypothesis: Tag không được indexed hoặc format khác
   - Debug: Search với match_phrase thay vì term
   ```json
   {
     "query": {
       "match_phrase": { "tag": "04 PSV 3926" }
     }
   }
   ```
   - Nếu match_phrase found → Issue là field mapping (keyword missing)
   - Nếu vẫn không found → Issue là data (tag không có trong index)

2. **Tag found nhưng page sai:**
   - Hypothesis: Off-by-one error
   - Debug: Check difference (expected - actual)
   - Nếu diff = +1 → 0-based vs 1-based issue
   - Nếu diff != +1 → Tag extraction extracted từ wrong page

3. **Tag found với multiple pages:**
   - Normal nếu tag xuất hiện nhiều lần
   - Check nếu expected page có trong results
   - Nếu không → Tag extraction missed page đó

---

### 2.3 Test component-based search (nested parts)

**Background:** Sau fix từ `P&ID_AUDIT_REPORT.md`, component search phải dùng nested paths `parts.prefix.keyword`

**Test query (theo fixed code):**
```json
{
  "size": 5,
  "query": {
    "bool": {
      "must": [
        { "term": { "parts.unit.keyword": "04" } },
        { "term": { "parts.prefix.keyword": "PSV" } },
        { "term": { "parts.suffix.keyword": "3926" } }
      ]
    }
  }
}
```

**Expected:** Same results như exact term search

**Potential Issues:**
- ❌ 0 results → Nested path không work, mapping sai
- ❌ Wrong results → Filter logic sai

**Severity:** **P0** - Component search là core feature của PID enhancement

---

### 2.4 Verify rag_chunks index có P&ID document chunks

**Command:**
```powershell
$body = @"
{
  "size": 3,
  "query": {
    "bool": {
      "must": [
        {
          "match_phrase": {
            "doc_id": "01. P&ID Ammonia Unit Rev12 (04000).pdf"
          }
        },
        {
          "term": {
            "page": 41
          }
        }
      ]
    }
  }
}
"@

curl -X POST "http://localhost:9200/rag_chunks/_search" -H "Content-Type: application/json" -d $body
```

**Expected:**
- Có ít nhất 1 chunk từ page 41
- `doc_id` field chứa filename hoặc doc_id

**Purpose:** Verify rằng P&ID document CŨNG có standard chunks (để fallback semantic search)

---

## 🔍 LAYER 3: QUERY PROCESSING AUDIT

### 3.1 Test PIDQueryEnhancer tag detection

**File to inspect:** `app/rag/query_processing/pid_query_enhancer.py`

**Test cases (manual trace):**

| Input Query | Expected Detection |
|-------------|-------------------|
| "Tìm cho tôi tag name 04 PSV 3926 trong bản vẽ P&ID" | strategy="component_search" OR "tag_focused", tags=["04 PSV 3926"], components={unit:"04", prefix:"PSV", suffix:"3926"} |
| "04 TI 5058" | strategy="tag_focused", tags=["04 TI 5058"] |

**Method to test:**
```python
# In Python REPL or test script
from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer

enhancer = PIDQueryEnhancer()

query1 = "Tìm cho tôi tag name 04 PSV 3926 trong bản vẽ P&ID"
result1 = enhancer.enhance(query1)
print(result1)
# Expected: {"strategy": "...", "tags": [...], "variants": {...}}

query2 = "04 TI 5058"
result2 = enhancer.enhance(query2)
print(result2)
```

**Potential Issues:**

| Issue | Detection | Root Cause | Fix Priority |
|-------|-----------|------------|--------------|
| Tags không được detect | `tags = []` hoặc missing | Regex trong `TagNormalizer` không match Vietnamese context | P0 |
| Components parse sai | `components` missing unit/prefix/suffix | `_parse_query_components()` logic bug | P0 |
| Strategy = "semantic" thay vì "tag_focused" | Wrong routing | Detection logic quá strict | P1 |
| Variants không đủ | Missing hyphen/space variants | `_generate_variants()` incomplete | P2 |

---

### 3.2 Trace query routing (query_type="pid" → correct retriever)

**File to inspect:** `app/api/routers/ask.py`

**Key code block (around line 185-192):**
```python
transformed_query = query_transformer.transform(
    query=request.query,
    filters=request.filters,
    language=request.language,
    query_type_override=getattr(request, 'query_type', None)  # ← This line critical
)
```

**Test:**
1. Request với `query_type="pid"` phải route tới `HybridWithTagsRetriever`
2. Request với `query_type="technical_doc"` phải route tới `TechnicalDocRetriever`

**Verification method:**
- Add logging hoặc breakpoint
- Hoặc check response có `meta.retriever_type` field

**Potential Issues:**
- ❌ `query_type` field không được pass qua schema
- ❌ Routing logic ignore `query_type` parameter
- ❌ `HybridWithTagsRetriever` không được init (check startup logs)

**Severity:** **P0 CRITICAL** - Nếu routing sai, toàn bộ PID logic bị bypass

---

### 3.3 Verify HybridWithTagsRetriever dual-branch execution

**File:** `app/rag/hybrid_with_tags_retriever.py`

**Key logic (line 90-99):**
```python
def search(self, transformed_query, top_k=10, **kwargs):
    use_tags = self.tags_enabled and self._should_use_tags(transformed_query)

    if use_tags:
        return self._search_with_tags(transformed_query, top_k, **kwargs)  # ← Dual branch
    else:
        return self.hybrid_retriever.search(transformed_query, top_k, **kwargs)  # ← Standard
```

**Critical check: `_should_use_tags()` validation layers**

**Layers (line 101-200):**
- Layer 0: Quick filter for technical doc patterns (NEW - line 119-147)
- Layer 1: Strategy detection from PIDQueryEnhancer
- Layer 2: Context validation (false positive prevention)
- Layer 3: Confidence threshold check

**Potential Issues:**

| Issue | Layer | Symptom | Fix |
|-------|-------|---------|-----|
| Tech doc patterns trigger false negative | Layer 0 | P&ID queries classified as technical doc | Loosen pattern matching |
| Strategy not in ["suffix_search", "component_search", "tag_focused"] | Layer 1 | Falls back to semantic | Fix enhancer strategy output |
| Context validation fails | Layer 2 | Valid P&ID queries rejected | Tune validator thresholds |
| Confidence < 0.5 threshold | Layer 3 | Borderline queries rejected | Lower threshold or improve confidence scoring |

**Test method:**
```python
# Manual test in Python
from app.rag.hybrid_with_tags_retriever import HybridWithTagsRetriever
from app.rag.query_transform import QueryTransformer

retriever = HybridWithTagsRetriever()
transformer = QueryTransformer()

query = "Tìm cho tôi tag name 04 PSV 3926 trong bản vẽ P&ID"
transformed = transformer.transform(query, query_type_override="pid")

# Check if tags will be used
should_use = retriever._should_use_tags(transformed)
print(f"Will use tags: {should_use}")
# Expected: True

# If False, trace which layer failed
```

---

### 3.4 Test OpenSearchTagsRetriever query construction

**File:** `app/rag/indexers/opensearch_tags_retriever.py`

**Critical fix đã apply (P&ID_AUDIT_REPORT.md):**
- Line 159-164: `_build_structured_query()` - Fixed nested paths
- Line 243-249: `search_by_components()` - Fixed nested paths
- Line 297: `search_by_suffix()` - Fixed nested path

**Verify fix có apply đúng không:**

```python
# Check code tại line 159
# MUST BE: {"term": {"parts.prefix.keyword": prefix}}
# NOT: {"term": {"prefix": prefix}}
```

**Test method:**
```powershell
# Trace OpenSearch query được generate
# Add debug logging trong code hoặc capture request
```

**Potential Issues nếu vẫn lỗi:**
- Code chưa update (check git commit)
- Multiple code paths, chỉ fix 1 path
- Edge cases không được cover (variant handling, null values)

---

## 🔍 LAYER 4: RETRIEVAL & FUSION AUDIT

### 4.1 Test dual-branch parallel search

**Files:**
- `app/rag/hybrid_with_tags_retriever.py` - Line 223-286: `_search_with_tags()`

**Expected flow:**
```python
# Branch A: Tags retriever (OpenSearch pvcfc_pid_tags)
tags_task = asyncio.create_task(
    tags_retriever.search_by_components(unit="04", prefix="PSV", suffix="3926")
)

# Branch B: Chunks hybrid (OpenSearch rag_chunks + Weaviate)
chunks_task = asyncio.create_task(
    hybrid_search(query, k=50)
)

# Wait parallel
tags_results, chunks_results = await asyncio.gather(tags_task, chunks_task)
```

**Test verification:**
- Both branches execute? (check logs for timing)
- Results from both branches present?

**Potential Issues:**
- ❌ Only one branch executes → Parallel execution failed
- ❌ Tags branch returns 0 results → Previous layer issue
- ❌ Chunks branch dominates → RRF weights issue

---

### 4.2 Test RRF Fusion weights

**File:** `app/rag/hybrid_with_tags_retriever.py` - Around line 290-330

**Expected adaptive weights:**

| Query Type | Tags Branch Weight | Chunks Branch Weight | Rationale |
|------------|-------------------|---------------------|-----------|
| tag_only | 1.0 | 0.3 | Prioritize exact tag match |
| component_search | 0.7 | 0.7 | Balanced |
| suffix_search | 1.0 | 0.3 | Exact suffix critical |
| semantic | 0.5 | 1.0 | Semantic understanding needed |

**Test method:**
- Log RRF scores for each result
- Verify tag results have higher final scores than chunk results

**Potential Issues:**
- Weights inverted (chunks prioritized over tags)
- Fixed weights instead of adaptive
- RRF k parameter too low (causes score compression)

---

### 4.3 Test PID Tag Reranking boost

**File:** `app/rag/rerankers/pid_tag_reranker.py`

**Expected boosts:**
- Exact metadata match: × 10.0
- Exact text match: × 5.0
- Fuzzy match (≥90%): × 2.0-3.0
- Tag-parameter proximity: × 3.0

**Test:**
```python
# Verify reranker is applied
# Check if tag results move to top after rerank
```

**Potential Issues:**
- Reranker not invoked
- Boost factors too low (doesn't affect ranking)
- Fuzzy threshold too high (90% → lower to 85%?)

---

## 🔍 LAYER 5: RESPONSE BUILDING AUDIT

### 5.1 Verify page number extraction and format

**File:** `app/rag/generator.py`

**Critical check:**
- Citations include `page` field?
- Page number is 1-based? (không phải 0-based)
- Page number từ đúng source (tags or chunks)?

**Test method:**
```python
# Check response JSON structure
{
  "citations": [
    {
      "doc_id": "...",
      "page": 41,  # ← Must be 1-based integer
      "bbox": [...],  # ← From tags
      "crop_path": "...",  # ← From tags
      "source": "tags_index"  # ← Identifier
    }
  ]
}
```

**Potential Issues:**
- Page off-by-one (41 stored as 40, returned as 40)
- Page từ chunks thay vì tags (mất bbox info)
- Multiple pages returned, expected page không top 1

---

### 5.2 Test bbox and crop_path attachment

**Expected:** Khi result từ tags index, phải có:
- `bbox`: [x0, y0, x1, y1]
- `crop_path`: "crops/{doc_id}_p{page}_{tag}.png" (nếu có)

**Potential Issues:**
- Fields missing → Response builder không copy từ tag result
- Path invalid → Crop file không tồn tại

---

## 📊 PRIORITIZED ISSUES CHECKLIST

### P0 - CRITICAL (Blocking, phải fix trước)

- [ ] **CAD-like Gate classify sai** → Check telemetry, adjust threshold nếu cần
- [ ] **Tags không extracted** → Check ingestion logs, verify regex patterns
- [ ] **pvcfc_pid_tags index không tồn tại hoặc empty** → Re-run indexing
- [ ] **Exact term search fail (0 results)** → Verify mapping có `.keyword`, check nested paths
- [ ] **query_type="pid" routing sai** → Fix API router
- [ ] **HybridWithTagsRetriever không được init** → Check startup logs
- [ ] **Component search fail (nested path issue)** → Verify fix đã apply

### P1 - HIGH (Ảnh hưởng accuracy)

- [ ] **Page numbers off-by-one** → Fix ingestion hoặc response builder
- [ ] **Tags có nhưng wrong page** → Check tag extraction logic per page
- [ ] **Tag normalization inconsistent** → Standardize format (space vs hyphen)
- [ ] **RRF weights không ưu tiên tags** → Adjust adaptive weights
- [ ] **PID Tag Reranker không boost đủ** → Increase boost factors
- [ ] **Query 5 tolerance không work** → Implement ±1 check

### P2 - MEDIUM (Chức năng phụ)

- [ ] **bbox hoặc crop_path missing** → Fix response attachment logic
- [ ] **Confidence scores thấp** → Tune thresholds
- [ ] **BGE reranking conflict với PID** → Disable hoặc adjust ordering

### P3 - LOW (Nice to have)

- [ ] **Debug mode không có** → Add intermediate results logging
- [ ] **Telemetry incomplete** → Enhance metrics collection

---

## 🧪 AUTOMATED TEST EXECUTION

### Script đã tạo: `test_pid_accuracy_audit.py`

**Usage:**
```powershell
# Ensure API is running first
# Terminal 1:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Run audit
python test_pid_accuracy_audit.py
```

**Output:**
- `logs/pid_audit/{timestamp}/`
  - `report.md` - Comprehensive report
  - `summary.csv` - Test results table
  - `audit.log` - Detailed execution log
  - `api_response_q1.json` ... `api_response_q5.json`
  - `os_indices.txt`, `os_mapping_pvcfc_pid_tags.json`

**Fallback manual tests:**
```powershell
# Test 1: Direct OpenSearch query
curl -X POST "http://localhost:9200/pvcfc_pid_tags/_search" -H "Content-Type: application/json" -d '{
  "size": 5,
  "query": { "term": { "tag.keyword": "04 PSV 3926" } }
}'

# Test 2: API query
curl -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{
  "query": "Tìm cho tôi tag name 04 PSV 3926 trong bản vẽ P&ID",
  "query_type": "pid",
  "language": "vi",
  "max_context": 10
}'
```

---

## 🔧 RECOMMENDED FIX WORKFLOW

### Bước 1: Kiểm tra data layer (Layer 1-2)

1. Chạy OpenSearch checks (Section 2.2)
2. Nếu tags không có → Re-run ingestion
3. Nếu tags có nhưng search fail → Fix mapping/nested paths
4. Verify tất cả 5 tags found với correct pages

**Exit criteria:** 5/5 tags found trong pvcfc_pid_tags với exact pages

---

### Bước 2: Kiểm tra query layer (Layer 3)

1. Test PIDQueryEnhancer với 5 queries
2. Verify routing với query_type="pid"
3. Check HybridWithTagsRetriever._should_use_tags() logic
4. Trace OpenSearchTagsRetriever query construction

**Exit criteria:** Tags được detect, routing đúng, queries được construct đúng

---

### Bước 3: Kiểm tra retrieval & fusion (Layer 4)

1. Verify dual-branch parallel execution
2. Test RRF fusion weights
3. Apply PID Tag Reranking
4. Check final ranking order

**Exit criteria:** Tag results ranked higher than chunk results

---

### Bước 4: Kiểm tra response (Layer 5)

1. Verify page numbers 1-based
2. Check bbox/crop_path attached
3. Validate citations format

**Exit criteria:** Response format correct, expected pages present

---

### Bước 5: End-to-end test

```powershell
python test_pid_accuracy_audit.py
```

**Target:** ≥4/5 accuracy (ideally 5/5)

---

## 📝 KNOWN ISSUES FROM PREVIOUS AUDIT

Từ `P&ID_AUDIT_REPORT.md` (2025-10-23):

### ✅ FIXED:
- Nested schema mismatch trong opensearch_tags_retriever.py
  - Was: `{"term": {"prefix": "PSV"}}`
  - Fixed: `{"term": {"parts.prefix.keyword": "PSV"}}`
  - Applied to 4 locations: `_build_structured_query()`, `search_by_components()`, `search_by_suffix()`, `_build_text_query()`

### ⚠️ TO VERIFY:
- Fix đã deploy chưa?
- Có edge cases nào chưa cover?
- Test với data mới có pass không?

---

## 🎯 SUCCESS CRITERIA

### Minimum (4/5):
- Q1, Q2, Q3, Q4 phải đúng 100%
- Q5 có thể sai (nhưng tốt nhất vẫn đúng)

### Ideal (5/5):
- Tất cả queries đều trả về đúng expected page
- Response time < 3s per query
- Confidence > 0.7

---

## 📞 NEXT ACTIONS

1. ✅ **ĐỌC KẾ HOẠCH NÀY**
2. ⏭️ **Chọn layer để bắt đầu audit** (recommend: Layer 2 - Indexing trước)
3. ⏭️ **Chạy manual checks** cho layer đó
4. ⏭️ **Document findings** (PASS/FAIL per check)
5. ⏭️ **Identify root causes** dựa trên audit results
6. ⏭️ **Prioritize fixes** (P0 → P1 → P2)
7. ⏭️ **Create fix plan** (tách file riêng: `KE_HOACH_FIX_PID.md`)

---

**Người lập kế hoạch:** AI Assistant
**Review:** User validation required
**Status:** READY FOR EXECUTION 🚀
