# Online Pipeline Audit - Summary

**Date**: 2025-10-07  
**Status**: 📋 **TEST SCRIPTS READY** (awaiting API server to run)

---

## What Was Done

### ✅ Created Comprehensive Test Suite

#### 1. **Test Scripts** (3 files)
- `test_online_basic.py` - Basic functionality & errors (6 tests)
- `test_online_retrieval_rerank.py` - Hybrid search & reranking (6 tests)
- `test_online_comprehensive.py` - Full audit (7 phases)

#### 2. **Golden Dataset**
- `golden_queries.json` - 10 curated queries with expected behaviors

#### 3. **Documentation**
- `README.md` - Complete guide for running tests

---

## Test Coverage

### Functionality Tests

| Component | Tests | Critical Checks |
|-----------|-------|-----------------|
| **Server** | Health check | 503 handling, uptime |
| **Schema** | Response validation | Required fields, types |
| **Query Transform** | VI/EN, HyDE | Normalization, preserve units |
| **Hybrid Retrieval** | BM25+FAISS | Both return results, RRF merge |
| **Reranking** | EN (CE), VI (fallback) | **VI no NaN** ⚠️ CRITICAL |
| **Generation** | Heavy/light tiers | Citations extraction |
| **Vision** | Gating logic | pages_used/failed, ≤10 limit |
| **Telemetry** | Breakdown, trace_id | Timing accuracy |
| **Metrics** | /metrics endpoint | Prometheus format |

### Performance Tests

| Metric | Target | How Tested |
|--------|--------|------------|
| Latency P50 | < 1500ms | Comprehensive audit |
| Latency P95 | < 3000ms | Comprehensive audit |
| Error rate | < 1% | Error handling tests |
| Rate limit | 429 at threshold | (Pending - load test) |

### Quality Tests

| Aspect | Target | How Tested |
|--------|--------|------------|
| Citation correctness | ≥ 90% | Golden queries (manual) |
| No-context refusal | ≥ 80% | Golden queries (manual) |
| Schema completeness | 100% | Automated validation |
| VI reranking works | 100% | Automated (critical) |

---

## How to Run

### Quick Start (5 minutes)

```bash
# 1. Start API
.\launchers\start_api.ps1

# 2. Run basic test
python scripts/test_scripts/online_audit/test_online_basic.py

# 3. Run comprehensive audit
python scripts/test_scripts/online_audit/test_online_comprehensive.py
```

### Full Audit (15 minutes)

```bash
# 1. Start API
.\launchers\start_api.ps1

# 2. Run all test suites
python scripts/test_scripts/online_audit/test_online_basic.py
python scripts/test_scripts/online_audit/test_online_retrieval_rerank.py
python scripts/test_scripts/online_audit/test_online_comprehensive.py

# 3. Review reports
ls reports/test_results/online_*
```

---

## Key Findings (Proactive)

### ✅ What's Already Good (Based on Code Review)

1. **Error Handling**: 
   - Empty query → 422 ✅
   - Missing retriever → 503 ✅
   - Global exception handler → 500 ✅

2. **VI Reranking Fallback**:
   - Code uses `rerank_method = "cross_encoder" if request.language == "en" else "score"`
   - Should prevent NaN issues ✅

3. **Vision Gating**:
   - Checks `settings.vision_page_selector_enabled AND request.enable_vision_generation`
   - Won't trigger without `pdf_path` ✅

4. **Schema**:
   - Pydantic models enforce structure ✅
   - Required fields validated ✅

### ⚠️ Potential Issues (Need Runtime Verification)

1. **Retrieval Alignment**:
   - Need to verify BM25 and FAISS indices have same doc_id order
   - RRF merge may produce duplicates if not handled

2. **Vision Page Limit**:
   - Code says ≤10 pages
   - Need to verify clamp and dedup logic

3. **Breakdown Timing**:
   - Sum of breakdown should ≈ total latency
   - Need to verify accuracy

4. **Rate Limiting**:
   - Middleware exists
   - Need to test actual 429 response

---

## Recommendations

### Before Running Tests

1. ✅ **Build indices** (if not done):
   ```bash
   python tools/ingest.py --source-dir test_docs --output-dir artifacts/test_build
   python tools/build_bm25_index.py --chunks-jsonl artifacts/test_build/chunks/chunks.jsonl --index-dir artifacts/index/bm25
   ```

2. ✅ **Start API server**:
   ```bash
   .\launchers\start_api.ps1
   ```

3. ✅ **Verify health**:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/index-stats
   ```

### After Running Tests

1. **Review reports** in `reports/test_results/online_*`
2. **Check logs** in `logs/online_audit_*`
3. **Address any failures** before production

---

## Expected Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Setup** | 10 mins | Start API, verify indices |
| **Basic tests** | 2-3 mins | test_online_basic.py |
| **Retrieval tests** | 3-5 mins | test_online_retrieval_rerank.py |
| **Comprehensive** | 5-10 mins | test_online_comprehensive.py |
| **Manual review** | 10-15 mins | Check reports, spot-check queries |
| **TOTAL** | ~30-45 mins | Full online audit |

---

## Files Created

### Test Scripts
- ✅ `scripts/test_scripts/online_audit/test_online_basic.py`
- ✅ `scripts/test_scripts/online_audit/test_online_retrieval_rerank.py`
- ✅ `scripts/test_scripts/online_audit/test_online_comprehensive.py`
- ✅ `scripts/test_scripts/online_audit/golden_queries.json`
- ✅ `scripts/test_scripts/online_audit/README.md`

### Reports (to be generated)
- `reports/test_results/online_basic_test_*.json`
- `reports/test_results/online_retrieval_test_*.json`
- `reports/test_results/online_comprehensive_audit_*.json`

### Documentation
- ✅ `reports/ONLINE_AUDIT_PLAN.md` (this file)
- (Pending) `reports/ONLINE_AUDIT_FINAL_REPORT.md` (after tests run)

---

## Next Actions

### Immediate (For User)

1. **Start API server**:
   ```bash
   cd C:\Users\Admin\Desktop\Code - API_LLM_PVCFC
   .\launchers\start_api.ps1
   ```

2. **Run basic test** to verify:
   ```bash
   python scripts/test_scripts/online_audit/test_online_basic.py
   ```

3. If PASS → run comprehensive:
   ```bash
   python scripts/test_scripts/online_audit/test_online_comprehensive.py
   ```

### After Tests Complete

4. **Review findings** in JSON reports
5. **Share results** - tôi sẽ analyze và đưa ra recommendations
6. **Fix any issues** discovered
7. **Re-test** để confirm fixes

---

## Comparison: Offline vs Online Audit

| Aspect | Offline Audit | Online Audit |
|--------|---------------|--------------|
| **Scope** | PDF → Index | API serving |
| **Duration** | ~6 mins | ~30 mins (with API calls) |
| **Tests** | 9 steps | 7 phases |
| **Critical Issues** | 1 (file hash dedup) | TBD (need to run) |
| **Status** | ✅ COMPLETE | 📋 READY TO RUN |

---

**Created**: 2025-10-07  
**Status**: Ready for execution  
**Next**: User starts API → runs tests → shares results

