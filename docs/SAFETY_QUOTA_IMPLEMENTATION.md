# Safety Quota Implementation - Technical Documentation

**Date:** November 22, 2025
**Version:** 1.7.1
**Status:** ✅ PRODUCTION READY

---

## Executive Summary

Successfully implemented **Safety Quota** system to prevent exact match flooding in hybrid retrieval pipeline. The refactoring enforces a hard limit of **20 exact matches** while reserving remaining slots for semantic search, protecting the system against header/footer noise scenarios.

---

## Problem Statement

### Original Risk Scenario
**Query:** "Thông số áp suất KT06101"
**Data:** Code `KT06101` appears in header/footer of 100 pages
**Previous behavior:** ALL 50+ chunks with KT06101 would fill `top_k`, blocking semantic results
**Impact:** BGE Reranker receives ZERO semantic candidates → poor answer quality

### Root Cause
The previous implementation (`_extract_exact_matches`) had **unlimited** exact match acceptance:
- Detected ALL chunks containing query codes
- Boosted ALL to score 1.0
- No quota enforcement
- **Result:** Header/footer flooding risk

---

## Solution Architecture

### 1. Safety Quota Logic

```python
def _extract_exact_matches(
    self,
    query: str,
    results: List[RetrievalResult],
    limit: int = 20  # NEW: Hard limit parameter
) -> Tuple[List[RetrievalResult], List[RetrievalResult]]:
    """
    Safety Quota Enforcement:
    1. Detect ALL exact matches in candidate list
    2. SORT by original RRF/BM25 score (descending)
    3. TRUNCATE to top {limit} exact matches
    4. Return dropped exact matches to semantic pool
    """
```

**Key Innovation:** Sorting by original score ensures **quality-first** selection:
- Top 5 content chunks (score 0.7-0.9) → kept
- 15 best header chunks (score 0.3) → kept
- 30 low-quality headers (score 0.1-0.2) → **dropped to semantic pool**

### 2. Data Flow

```
Input: 60 chunks (50 exact matches + 10 semantic)
  ├─ 5 content chunks with code (score: 0.7-0.9)
  ├─ 45 header chunks with code (score: 0.1-0.3)
  └─ 10 semantic chunks (no code, score: 0.4-0.6)

↓ Safety Quota Processing

Exact Matches Kept: 20 (limit=20)
  ├─ 5 content chunks (scores 0.7-0.9 → boosted to 1.0)
  └─ 15 best headers (score 0.3 → boosted to 1.0)

Remaining Pool: 40
  ├─ 30 dropped headers (original scores 0.1-0.2 preserved)
  └─ 10 semantic chunks (original scores 0.4-0.6)

↓ BGE Reranking

BGE Input: 40 remaining candidates
BGE Slots: top_k - 20 = 30 slots

↓ Final Merge

Final Results: 20 exact + 30 BGE = 50 total
```

### 3. Slot Reservation Formula

```python
# At search() method (line 447)
bge_slots = top_k - len(exact_matches)

# Example scenarios:
top_k=50, exact=20 → BGE gets 30 slots ✅
top_k=50, exact=5  → BGE gets 45 slots ✅
top_k=10, exact=2  → BGE gets 8 slots ✅
```

---

## Implementation Details

### Files Modified

#### 1. `app/rag/hybrid_weaviate_opensearch_retriever.py`

**Method: `_extract_exact_matches()` (Lines 590-676)**

Changes:
- Added `limit: int = 20` parameter
- Implemented score-based sorting: `exact_matches.sort(key=lambda x: x.score, reverse=True)`
- Truncation logic: `exact_matches_top = exact_matches[:limit]`
- Dropped matches return: `remaining_candidates.extend(exact_matches_dropped)`
- Enhanced logging with 🛡️ Safety Quota emoji

**Method: `search()` (Lines 435-438)**

Changes:
```python
exact_matches, remaining_candidates = self._extract_exact_matches(
    query=enhanced["original"],
    results=fused_results,
    limit=20  # NEW: Safety quota parameter
)
```

#### 2. `app/core/config.py`

**Line 227-229:**
```python
opensearch_retrieval_limit: int = Field(
    default=200,  # CHANGED: 100 → 200
    description="Number of results to retrieve from OpenSearch before reranking (200 for deep code search + header/footer filtering)",
)
```

**Rationale:** Increase OpenSearch limit to 200 to:
- Retrieve more candidates for filtering
- Better recall on low-ranked exact matches
- Compensate for header/footer noise removal

#### 3. `.env`

**Line 108:**
```bash
OPENSEARCH_RETRIEVAL_LIMIT=200  # CHANGED: 100 → 200
```

---

## Test Results

### Test Suite: `scripts/test_safety_quota.py`

**Test Case 1: No Codes Query**
- Query: "What is the operating pressure?"
- Expected: 0 exact matches, 3 semantic
- Result: ✅ PASSED

**Test Case 2: Flooding Scenario**
- Query: "Thông số áp suất KT06101"
- Input: 60 chunks (50 exact + 10 semantic)
- Expected: 20 exact kept, 40 remaining
- Result: ✅ PASSED
- **Key Verification:**
  - Top 5 = content chunks (high quality)
  - Dropped 30 headers (low quality)
  - Score boosting only for top 20

**Test Case 3: Slot Allocation**
- Scenarios: (10,2,8), (50,20,30), (50,5,45)
- Result: ✅ ALL PASSED

**Test Case 4: Code Detection**
- Patterns: LS006343, HCD025, E-04217, KT06101, Vietnamese
- Result: ✅ ALL PASSED (7/7 patterns)

---

## Configuration Reference

### Default Values

| Parameter | Default | Description |
|-----------|---------|-------------|
| `limit` (exact matches) | **20** | Maximum exact matches to keep |
| `OPENSEARCH_RETRIEVAL_LIMIT` | **200** | OpenSearch candidate retrieval |
| `WEAVIATE_RETRIEVAL_LIMIT` | **100** | Weaviate candidate retrieval |
| `MAX_CONTEXT` | **20** | Final context chunks to LLM |
| `BGE_RERANK_TOP_K` | **20** | BGE reranking output |

### Tuning Recommendations

**Conservative (High Precision):**
```python
limit=10  # Fewer exact matches
OPENSEARCH_RETRIEVAL_LIMIT=150
```

**Balanced (Current - RECOMMENDED):**
```python
limit=20  # DEFAULT
OPENSEARCH_RETRIEVAL_LIMIT=200
```

**Aggressive (High Recall):**
```python
limit=30  # More exact matches
OPENSEARCH_RETRIEVAL_LIMIT=300
```

⚠️ **Warning:** Increasing `limit` beyond 30 reduces semantic slots and may degrade answer quality on non-code queries.

---

## Verification Checklist

- [x] Safety quota enforced (max 20 exact matches)
- [x] Score-based sorting (quality-first selection)
- [x] Dropped matches return to semantic pool
- [x] BGE slot reservation correct (`top_k - len(exact)`)
- [x] No duplicates in final results
- [x] Logging includes 🛡️ emoji for monitoring
- [x] OpenSearch limit increased to 200
- [x] All test cases passed (4/4)

---

## Monitoring & Observability

### Log Signatures

**Exact Match Detection:**
```
INFO | 🎯 Exact Match Guardrails: Detected codes ['KT06101', 'HCD025']
```

**Safety Quota Enforcement:**
```
INFO | 🛡️ Safety Quota: 20/50 exact matches kept (limit=20, dropped=30 to semantic pool)
```

**Score Boosting:**
```
DEBUG | ⚡ Top exact match: content_chunk_0... (score: 0.900 → 1.0)
```

### Metrics to Monitor

1. **Exact Match Distribution:**
   - Alert if `exact_matches_kept` consistently = 20 (may need limit increase)
   - Alert if `exact_matches_found` > 100 (potential data quality issue)

2. **Slot Allocation:**
   - Track `bge_slots` average (should be ~30 for top_k=50)
   - Alert if `bge_slots < 10` (too many exact matches)

3. **Query Performance:**
   - Compare answer quality for code queries before/after
   - Monitor latency impact (expected: +5-10ms for sorting)

---

## Deployment Notes

### Pre-Deployment

1. ✅ Backup `.env` configuration
2. ✅ Run test suite: `python scripts/test_safety_quota.py`
3. ✅ Verify OpenSearch connectivity with `limit=200`

### Deployment Steps

1. Pull latest code with Safety Quota changes
2. Update `.env` with `OPENSEARCH_RETRIEVAL_LIMIT=200`
3. Restart API server
4. Monitor logs for 🛡️ Safety Quota messages

### Rollback Plan

If issues occur:
1. Revert `OPENSEARCH_RETRIEVAL_LIMIT` to 100
2. Change `limit=20` to `limit=100` in code (line 438)
3. Restart API server

**Rollback Time:** < 2 minutes

---

## Future Enhancements

### Phase 1 (Optional)
- [ ] Make `limit` configurable via ENV: `EXACT_MATCH_SAFETY_LIMIT`
- [ ] Add metrics API endpoint: `/metrics/safety_quota`
- [ ] A/B test optimal limit value (15 vs 20 vs 25)

### Phase 2 (Advanced)
- [ ] Dynamic limit based on query type (PID=30, Technical=15)
- [ ] Header/footer detection heuristic (auto-filter noise)
- [ ] Smart boosting: Content chunks get 1.0, headers get 0.8

---

## References

### Related Documentation
- [Exact Match Guardrails](Fix_Critical_Data_Integrity_Issues.md)
- [Hybrid Retrieval Architecture](SYSTEM_ARCHITECTURE.md)
- [BGE Reranker Configuration](CHANGELOG.md#v160)

### Code Locations
- Implementation: `app/rag/hybrid_weaviate_opensearch_retriever.py:590-676`
- Config: `app/core/config.py:227-229`
- Tests: `scripts/test_safety_quota.py`

---

## Conclusion

The Safety Quota implementation successfully addresses the flooding risk while maintaining high recall for genuine exact matches. The quality-first sorting ensures content chunks are prioritized over header noise, and the configurable limit provides flexibility for future optimization.

**Status:** ✅ PRODUCTION READY
**Risk Level:** Low (additive logic, no breaking changes)
**Performance Impact:** +5-10ms per query (negligible)

---

**Approved by:** Lead Software Architect
**Implementation Date:** 2025-11-22
**Next Review:** 2025-12-22 (1 month)
