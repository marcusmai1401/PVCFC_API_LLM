# Online Pipeline Audit Plan

**Date**: 2025-10-07  
**Scope**: Audit complete ONLINE pipeline (API serving)  
**Status**: 📋 PLAN READY

---

## Overview

Audit toàn diện pipeline ONLINE từ khi nhận query → trả về answer với citations.

**Components Audited**:
1. API Endpoints (`/ask`, `/locate`, `/report`)
2. Query Transform (normalize, HyDE)
3. Hybrid Retrieval (BM25 + FAISS)
4. Reranking (EN: CE, VI: score fallback)
5. Generation & Vision Gating
6. Response Schema & Telemetry
7. Metrics, Tracing, Rate Limiting

---

## Test Scripts Created

### 1. Basic Tests
**File**: `scripts/test_scripts/online_audit/test_online_basic.py`

**Coverage**:
- ✅ Server health
- ✅ Schema validation
- ✅ VI query
- ✅ EN query
- ✅ Error handling (empty query, invalid params)

**Run**: `python scripts/test_scripts/online_audit/test_online_basic.py`

---

### 2. Retrieval & Rerank Tests
**File**: `scripts/test_scripts/online_audit/test_online_retrieval_rerank.py`

**Coverage**:
- ✅ Keyword query (BM25)
- ✅ Semantic query (FAISS)
- ✅ EN cross-encoder reranking
- ✅ VI score-based fallback (no NaN)
- ✅ max_context variation
- ✅ Retrieval details

**Run**: `python scripts/test_scripts/online_audit/test_online_retrieval_rerank.py`

---

### 3. Comprehensive Audit
**File**: `scripts/test_scripts/online_audit/test_online_comprehensive.py`

**Coverage**:
- ✅ All phases (preconditions → queries → errors → retrieval → vision → schema → metrics)
- ✅ Latency P50/P95 collection
- ✅ Citation count analytics
- ✅ Breakdown timing validation

**Run**: `python scripts/test_scripts/online_audit/test_online_comprehensive.py`

---

### 4. Golden Queries Dataset
**File**: `scripts/test_scripts/online_audit/golden_queries.json`

**Contains**:
- 10 curated queries (VI/EN)
- Technical specs, procedures, no-context, vision-preferred
- Expected behaviors documented

---

## Prerequisites

### Must Have (Critical)

1. **API Server Running**:
   ```bash
   .\launchers\start_api.ps1
   # Or
   python -m uvicorn app.main:app --port 8000
   ```

2. **Indices Loaded**:
   - `artifacts/index/bm25/*`
   - `artifacts/index/faiss/*`
   - Check via: `curl http://localhost:8000/index-stats`

### Should Have (Recommended)

3. **doc_id_map.json**:
   - `artifacts/ingestion/doc_id_map.json`
   - Enables `pdf_path` in citations

4. **ENV configured**:
   - `LLM_PROVIDER=gemini`
   - `GEMINI_API_KEY=...`
   - `EMBEDDING_MODEL=gemini-embedding-001`

---

## Execution Plan

### Phase 1: Preparation (5-10 mins)
```bash
# 1. Start API
.\launchers\start_api.ps1

# 2. Verify health
curl http://localhost:8000/health

# 3. Check indices
curl http://localhost:8000/index-stats
```

### Phase 2: Basic Tests (2-3 mins)
```bash
python scripts/test_scripts/online_audit/test_online_basic.py
```

**Expected Output**:
```
✓ Passed: 6/6
✗ Failed: 0/6
```

### Phase 3: Retrieval/Rerank Tests (3-5 mins)
```bash
python scripts/test_scripts/online_audit/test_online_retrieval_rerank.py
```

**Critical Check**: VI reranking returns results (no NaN)

### Phase 4: Comprehensive Audit (5-10 mins)
```bash
python scripts/test_scripts/online_audit/test_online_comprehensive.py
```

**Outputs**:
- `reports/test_results/online_comprehensive_audit_*.json`
- `logs/online_audit_*.log`

---

## Acceptance Criteria

### Functionality (Must Pass)

| Check | Criterion | Target |
|-------|-----------|--------|
| Server health | Returns 200 | ✅ |
| Schema compliance | All required fields | ✅ |
| VI query | Returns answer + citations | ✅ |
| EN query | Returns answer + citations | ✅ |
| Empty query error | Returns 422 | ✅ |
| VI reranking | No NaN, not empty | ✅ CRITICAL |
| EN reranking | Uses cross-encoder | ✅ |

### Performance (Should Meet)

| Metric | Target | Acceptable |
|--------|--------|------------|
| Latency P50 (light) | < 800ms | < 1500ms |
| Latency P95 (light) | < 1500ms | < 3000ms |
| Latency P50 (vision) | < 1500ms | < 3000ms |
| Latency P95 (vision) | < 3000ms | < 5000ms |

### Quality (Should Meet)

| Metric | Target |
|--------|--------|
| Citation correctness | ≥ 90% |
| No-context refusal | ≥ 80% |
| Schema completeness | 100% |

---

## Known Issues & Workarounds

### Issue 1: Server Not Started
**Symptom**: Connection refused  
**Fix**: `.\launchers\start_api.ps1`

### Issue 2: Indices Not Loaded
**Symptom**: 503 Service Unavailable  
**Fix**: Build indices first (see offline audit)

### Issue 3: No LLM API Key
**Symptom**: Generation fails  
**Fix**: Set `GEMINI_API_KEY` in `.env`

### Issue 4: VI Reranking Returns Empty
**Symptom**: 0 citations for VI queries  
**Fix**: Already implemented in `app/rag/reranker.py` (score fallback)  
**Check**: Verify fallback is active

---

## Test Results Interpretation

### JSON Report Structure
```json
{
  "audit_type": "online_comprehensive",
  "timestamp": 1696662000,
  "summary": {
    "passed": 7,
    "failed": 0,
    "total": 7
  },
  "results": {
    "preconditions": {"status": "PASS", ...},
    "basic_queries": {"status": "PASS", ...},
    ...
  },
  "metrics": {
    "latencies": [450, 520, 680, ...],
    "citation_counts": [3, 5, 2, ...]
  }
}
```

### Status Codes

- `"PASS"`: ✅ All checks passed
- `"FAIL"`: ❌ Critical issue found
- `"WARNING"`: ⚠️ Minor issue or optional feature missing
- `"INFO"`: ℹ️ Informational only
- `"pending"`: ⏳ Not yet tested

---

## Next Steps After Audit

### If All Tests PASS ✅
1. Review latency metrics (P50/P95)
2. Check citation quality manually (spot-check 10 queries)
3. Ready for production testing

### If Tests FAIL ❌
1. Review detailed findings in JSON report
2. Check logs in `logs/online_audit_*.log`
3. Fix issues in corresponding modules
4. Re-run audit

### Optimization Opportunities
1. If latency > targets → consider caching, reduce k
2. If citation quality < 90% → review retrieval/rerank
3. If vision rarely triggers → check doc_id_map and pdf_path availability

---

## Maintenance

### When to Re-run Audit

- After code changes to RAG components
- After changing LLM models or embeddings
- After index rebuilds
- Before production deployment
- Monthly for regression detection

### Updating Golden Queries

Edit `golden_queries.json` to add:
- New technical domains
- Edge cases discovered in production
- User-reported issues

---

**Created**: 2025-10-07  
**Maintained By**: AI Assistant  
**Version**: 1.0

