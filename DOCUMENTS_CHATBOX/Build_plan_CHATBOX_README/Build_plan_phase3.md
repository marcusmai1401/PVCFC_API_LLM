## Build Plan — Phase 3: Reranking & Page‑First Agent

### Goals
- Improve relevance using BGE CrossEncoder reranking; align page-level scoring.
- Produce IEEE-style citations (UI) with correct page numbers.

### Source of Truth
- `../../docs/IEEE_CITATION_FEATURE.md`
- `../../docs/PAGE_FIRST_IMPLEMENTATION.md`
- `../../reports/PAGE_FIRST_AGENT_PHASE1_COMPLETE.md`
- `tests/unit/test_rrf_merge.py`

### Prerequisites
- Phase 2 completed
- Optional: install `sentence-transformers` for hybrid rerank

### Steps
1) Enable/disable reranking via config
```ini
ENABLE_BGE_RERANK=true
BGE_RERANK_CANDIDATE_LIMIT=50
BGE_RERANK_TOP_K=10
BGE_RERANK_LEVEL=chunk  # or page/doc
BGE_RERANK_AGGREGATION=max
```

2) Page-first agent integration
- Load BM25 page index before reranking
- Map rerank scores back to candidate pages
- Ensure signature compatibility (no `page_candidates` arg if not supported)

3) IEEE citation formatting in UI
- Convert `[Doc N, p.X]` → `[n]` after validation/selection

### Validation
- Unit test `test_rrf_merge.py` passes
- Integration test returns reranked pages with scores

### KPIs (Phase Exit)
- p95 rerank latency < 400ms (cached)
- Page citations correct on top answers

### Troubleshooting
- First-call latency ~30s → model cold-start; warm cache then re-test
- Negative scores breaking confidence → clamp to ≥0 (fixed in v0.6.1)

### References
- `../../docs/IEEE_CITATION_FEATURE.md`
- `../../docs/PAGE_FIRST_IMPLEMENTATION.md`
