# Online Pipeline Audit Tests

Bộ test scripts để kiểm tra toàn diện pipeline ONLINE (API endpoints).

## Prerequisites

### 1. API Server Running
```bash
# Start API server
cd launchers
.\start_api.ps1

# Or
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Indices Loaded
```bash
# Verify indices
curl http://localhost:8000/index-stats

# Should return BM25 and FAISS stats
```

### 3. doc_id_map.json (Optional but recommended)
```bash
# Check exists
ls artifacts/ingestion/doc_id_map.json

# If missing, citations won't have pdf_path
```

---

## Test Scripts

### 1. test_online_basic.py
**Purpose**: Basic functionality and error handling

**Tests**:
- Server health check
- Response schema validation
- Vietnamese query
- English query
- Empty query error (422)
- Invalid params error (422)

**Run**:
```bash
python scripts/test_scripts/online_audit/test_online_basic.py
```

**Expected**: All 6 tests PASS

---

### 2. test_online_retrieval_rerank.py
**Purpose**: Retrieval and reranking logic

**Tests**:
- Keyword-heavy query (BM25 dominance)
- Semantic query (FAISS contribution)
- EN cross-encoder reranking
- VI score-based fallback (no NaN)
- max_context variation (1, 5, 8, 15, 20)
- retrieval_details availability

**Run**:
```bash
python scripts/test_scripts/online_audit/test_online_retrieval_rerank.py
```

**Expected**: All 6 tests PASS, VI returns non-empty results

---

### 3. test_online_comprehensive.py
**Purpose**: Complete end-to-end audit

**Covers**:
1. Preconditions (server, indices, doc_id_map)
2. Basic queries (VI/EN)
3. Error handling (400/422)
4. Retrieval & reranking
5. Vision gating
6. Schema & telemetry
7. Metrics & tracing

**Run**:
```bash
python scripts/test_scripts/online_audit/test_online_comprehensive.py
```

**Expected**: All phases PASS

**Output**:
- Console summary
- JSON report in `reports/test_results/online_comprehensive_audit_*.json`
- Detailed log in `logs/online_audit_*.log`

---

### 4. test_citation_accuracy_golden.py ⭐ NEW
**Purpose**: Test citation accuracy with verified ground truth

**What it does**:
- Tests 5 verified Q&A pairs with known correct citations
- Compares API results against ground truth (doc + page)
- Tests with vision ON and OFF (10 total requests)
- Identifies citation mismatch patterns

**Run**:
```bash
# Test with both vision variants (default)
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py

# Test only with vision enabled
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py --vision-only

# Test only without vision
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py --no-vision

# Custom API URL
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py --api-url http://localhost:8001
```

**Expected**:
- Pass rate ≥ 60% (at least 3/5 questions correct)
- Identifies specific citation issues for investigation

**Output**:
- Console: Detailed per-question results with verdict
- JSON: `reports/test_results/citation_accuracy_golden_{timestamp}.json`
- Contains full response dumps for deep analysis

**Exit codes**:
- 0: Pass rate ≥ 60%
- 1: Pass rate < 60% (needs investigation)

**Dataset**: `golden_citation_dataset.json`
- Q1-Q2: CO2 compressor (VI/EN) → File: `003_3N4-S4274345...pdf`
- Q3-Q4: Ammonia pump (VI/EN) → File: `Ammonia Maintenance Schedule.pdf`
- Q5: Compressor datasheet (EN) → File: `002_3N4-S4274343...pdf`

---

## Golden Queries

**File**: `golden_queries.json`

Bộ 10 queries chuẩn để test:
- Technical queries (VI/EN)
- No-context queries (should refuse)
- Table/drawing queries (vision preferred)
- Unicode/units preservation
- Long queries
- Multi-document queries

**Usage**:
```python
import json
with open("golden_queries.json") as f:
    queries = json.load(f)

for q in queries:
    # Test with q["query_vi"] or q["query_en"]
    ...
```

---

## Interpreting Results

### PASS ✅
- All checks successful
- No issues found
- Production ready

### WARNING ⚠️
- Minor issues or missing optional features
- Core functionality works
- May need attention

### FAIL ❌
- Critical issues found
- Not production ready
- Requires fixes

---

## Common Issues & Solutions

### Issue: Connection Refused
```
Error: Cannot connect to localhost:8000
```

**Solution**:
```bash
# Start API server first
.\launchers\start_api.ps1
```

---

### Issue: 503 Service Unavailable
```
Error: Retriever not initialized
```

**Solution**:
- Index not loaded during startup
- Check: `artifacts/index/bm25/` and `artifacts/index/faiss/` exist
- Rebuild indices if needed

---

### Issue: VI Returns Empty Results
```
VI reranking returned empty results (NaN issue)
```

**Solution**:
- Check `app/rag/reranker.py` for VI fallback logic
- Should use score-based reranking, not cross-encoder for VI

---

## Performance Benchmarks (Expected)

### Latency (local, light_only mode)
- P50: < 800ms
- P95: < 1500ms

### Latency (production mode with vision)
- P50: < 1500ms
- P95: < 3000ms

### Citation Quality
- Correctness: ≥ 90%
- No-context refusal: ≥ 80%

---

## Related Documents

- `reports/OFFLINE_BUILD_AUDIT_FINAL_REPORT.md` - Offline audit results
- `Pipeline/PIPELINE_07-10-2025.md` - Complete pipeline diagram
- `README.md` - Main project README

---

**Created**: 2025-10-07
**Status**: Ready for use
