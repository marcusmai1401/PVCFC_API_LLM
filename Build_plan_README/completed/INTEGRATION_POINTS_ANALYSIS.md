# Integration Points Analysis - HybridRetriever ↔ CitationRetriever

**Date**: 2025-01-03
**Purpose**: Identify exact code locations for page-reranking integration
**Status**: ✅ Analysis Complete

---

## FILE LOCATIONS

### Primary Files
- **HybridRetriever**: `app/rag/retriever.py` (lines 1-783)
- **CitationRetriever**: `app/rag/citation_retriever.py` (lines 1-400+)
- **Config**: `app/rag/retriever.py` lines 70-86 (HybridSearchConfig)

---

## CURRENT FLOW IN HybridRetriever.search()

### Line-by-line breakdown of search() method (lines 177-311):

```python
177| def search(
178|     self,
179|     transformed_query: TransformedQuery,
180|     config_override: Optional[HybridSearchConfig] = None,
181| ) -> List[RetrievalResult]:
```

**KEY SECTIONS:**

### 1️⃣ **Configuration Setup** (lines 192-212)
```python
192|     config = config_override or self.config
193|
194|     logger.info(
195|         f"Starting hybrid search for: {transformed_query.normalized[:100]}..."
196|     )
197|
198|     # Collect results from both sources
199|     all_results = []
200|     faiss_failed = False
201|     degrade_reason = None
202|
203|     # Load degrade settings from config
204|     try:
205|         from app.core.config import settings
206|
207|         allow_fallback = settings.retrieval_allow_bm25_only_fallback
208|         bm25_k_degrade = settings.bm25_k_when_degrade
209|     except Exception:
210|         allow_fallback = True
211|         bm25_k_degrade = 80
```

**Integration Point**: None here, just setup.

---

### 2️⃣ **BM25 Search** (lines 214-222)
```python
214|     # BM25 search (always attempt)
215|     if self.bm25_indexer:
216|         bm25_results = self._search_bm25(
217|             query=transformed_query.normalized,
218|             filters=transformed_query.filters,
219|             top_k=config.k_bm25,
220|         )
221|         all_results.extend(bm25_results)
222|         logger.info(f"BM25 returned {len(bm25_results)} results")
```

**Integration Point**: None here.

---

### 3️⃣ **FAISS Search + Degrade Handling** (lines 224-271)
```python
224|     # FAISS search (with degrade fallback)
225|     if self.faiss_indexer and self.embedding_service:
226|         try:
227|             faiss_results = self._search_faiss(
228|                 query=transformed_query.normalized,
229|                 hyde_queries=transformed_query.hyde_queries
230|                 if config.use_hyde
231|                 else None,
232|                 filters=transformed_query.filters,
233|                 top_k=config.k_faiss,
234|             )
235|             all_results.extend(faiss_results)
236|             logger.info(f"FAISS returned {len(faiss_results)} results")
237|         except Exception as e:
238|             # ... degrade handling (lines 238-271) ...
```

**Integration Point**: None here.

---

### 4️⃣ **⭐ RRF FUSION** (lines 273-278) - **PRIMARY INTEGRATION POINT**
```python
273|     # Apply RRF fusion
274|     fused_results = self._reciprocal_rank_fusion(
275|         all_results, k=config.rrf_k, top_n=config.top_rrf
276|     )
277|
278|     logger.info(f"RRF fusion produced {len(fused_results)} results")
```

**✅ INTEGRATION POINT #1: After RRF fusion, before degrade metadata**
- **Location**: Line 278 (after RRF, before line 280)
- **Input**: `fused_results` (List[RetrievalResult])
- **Output**: Same type (List[RetrievalResult])
- **Condition**: `if config.enable_page_reranking:`

---

### 5️⃣ **Degrade Metadata Attachment** (lines 280-287)
```python
280|     # Attach degrade metadata if FAISS failed
281|     if faiss_failed:
282|         for result in fused_results:
283|             if result.metadata is None:
284|                 result.metadata = {}
285|             result.metadata["degrade_mode"] = True
286|             result.metadata["degrade_reason"] = degrade_reason
287|         logger.info("Degrade metadata attached to all results")
```

**Integration Point**: None here, but page-reranking should preserve degrade metadata.

---

### 6️⃣ **⭐ PAGE-RANGE EXPANSION** (lines 289-300) - **CONFLICT ZONE**
```python
289|     # Apply page-range expansion if enabled (before parent expansion)
290|     if config.enable_page_range_expansion:
291|         fused_results = self.page_expander.expand_results(
292|             fused_results, max_results=config.top_rrf
293|         )
294|         logger.info("Page-range expansion completed")
295|
296|         # Upgrade results to full page text where possible
297|         try:
298|             fused_results = self._upgrade_results_with_full_pages(fused_results)
299|         except Exception as e:
300|             logger.warning(f"Failed to upgrade results with full pages: {e}")
```

**⚠️ CONFLICT**: Page-range expansion and page-reranking are mutually exclusive!
- Both operate at page level
- Cannot both be enabled simultaneously
- **Decision**: Page-reranking should replace page-range expansion when enabled

---

### 7️⃣ **Parent Expansion** (lines 302-309)
```python
302|     # Expand parent context if enabled (now optional with page-range)
303|     elif config.expand_parent:
304|         fused_results = self._expand_parent_context(
305|             fused_results,
306|             max_tokens=config.parent_tokens,
307|             window_size=config.sentence_window,
308|         )
309|         logger.info("Parent context expansion completed")
```

**Integration Point**: None here (this is fallback when page-range disabled).

---

### 8️⃣ **Return** (line 311)
```python
311|     return fused_results
```

---

## EXACT INTEGRATION LOGIC

### Current Flow (without page reranking):
```
BM25 search (line 216)
    ↓
FAISS search (line 227)
    ↓
RRF fusion (line 274)
    ↓
[278: log results]
    ↓
Attach degrade metadata (line 281)
    ↓
IF enable_page_range_expansion (line 290):
    → page_expander.expand_results()
    → _upgrade_results_with_full_pages()
ELIF expand_parent (line 303):
    → _expand_parent_context()
    ↓
Return results (line 311)
```

### New Flow (with page reranking):
```
BM25 search (line 216)
    ↓
FAISS search (line 227)
    ↓
RRF fusion (line 274)
    ↓
[278: log results]
    ↓
⭐ IF enable_page_reranking (NEW - line ~279):
    → Extract doc_ids from fused_results
    → Call CitationRetriever.search_with_citations()
    → Convert CitationResult[] back to RetrievalResult[]
    → SKIP page-range expansion (incompatible)
    ↓
ELSE:
    → Attach degrade metadata (line 281)
    → IF enable_page_range_expansion (line 290):
        → page_expander.expand_results()
    → ELIF expand_parent (line 303):
        → _expand_parent_context()
    ↓
Return results (line 311)
```

---

## PRECISE CODE INSERTION POINT

**Location**: After line 278, before line 280

### Exact insertion:
```python
278|     logger.info(f"RRF fusion produced {len(fused_results)} results")
279|
280|     # ⭐ NEW CODE BLOCK STARTS HERE ⭐
281|     # Page-level reranking with citations (Phase 1)
282|     if config.enable_page_reranking:
283|         logger.info("Applying page-level reranking with citations")
284|
285|         # Extract unique doc_ids from top results
286|         doc_ids = self._extract_doc_ids_from_results(
287|             fused_results,
288|             top_n=config.top_k_docs_for_page_rerank or config.top_rrf
289|         )
290|
291|         if doc_ids:
292|             # Call CitationRetriever for page-level ranking
293|             try:
294|                 citations = self._rerank_at_page_level(
295|                     query=transformed_query.normalized,
296|                     doc_ids=doc_ids,
297|                     config=config,
298|                 )
299|
300|                 # Convert citations back to RetrievalResult format
301|                 fused_results = self._citations_to_retrieval_results(citations)
302|
303|                 logger.info(
304|                     f"Page reranking completed: {len(fused_results)} page-level results"
305|                 )
306|             except Exception as e:
307|                 logger.error(f"Page reranking failed: {e}, falling back to chunk-level")
308|                 # Keep original fused_results on failure
309|
310|         # Preserve degrade metadata if FAISS failed
311|         if faiss_failed:
312|             for result in fused_results:
313|                 if result.metadata is None:
314|                     result.metadata = {}
315|                 result.metadata["degrade_mode"] = True
316|                 result.metadata["degrade_reason"] = degrade_reason
317|
318|         # Skip page-range expansion (incompatible with page reranking)
319|         logger.info("Skipping page-range expansion (page reranking active)")
320|
321|         return fused_results
322|     # ⭐ NEW CODE BLOCK ENDS HERE ⭐
323|
324|     # Attach degrade metadata if FAISS failed (EXISTING CODE)
325|     if faiss_failed:
326|         for result in fused_results:
327|             # ... (lines 283-287 unchanged) ...
328|
329|     # Apply page-range expansion if enabled (EXISTING CODE)
330|     if config.enable_page_range_expansion:
331|         # ... (lines 291-300 unchanged) ...
332|
333|     # Expand parent context if enabled (EXISTING CODE)
334|     elif config.expand_parent:
335|         # ... (lines 304-309 unchanged) ...
336|
337|     return fused_results
```

---

## CONFIG CHANGES NEEDED

### Add to HybridSearchConfig (after line 86):

```python
70| @dataclass
71| class HybridSearchConfig:
72|     """Configuration for hybrid search"""
73|
74|     k_bm25: int = 50
75|     k_faiss: int = 50
76|     top_rrf: int = 60
77|     rrf_k: int = 60
78|     use_hyde: bool = True
79|     expand_parent: bool = True
80|     parent_tokens: int = 1200
81|     sentence_window: int = 2
82|     # Page-range expansion config
83|     enable_page_range_expansion: bool = True
84|     max_pages_to_scan: int = 5
85|     min_cluster_score: float = 0.1
86|     page_gap_tolerance: int = 1
87|
88|     # ⭐ NEW FIELDS FOR PAGE RERANKING ⭐
89|     # Phase 1: Page-level reranking with citations
90|     enable_page_reranking: bool = False  # Feature flag (default OFF)
91|     top_k_docs_for_page_rerank: Optional[int] = None  # None = use top_rrf
92|     top_k_pages_per_doc: int = 3  # Pages to extract per document
93|     max_snippets_per_page: int = 3  # Snippets per page for metadata
94|     page_reranking_min_score: float = 0.0  # Minimum BM25 score threshold
```

---

## HELPER METHODS TO ADD

All helper methods should be added as private methods of `HybridRetriever` class:

### 1. `_extract_doc_ids_from_results()` (add after line 612)
```python
def _extract_doc_ids_from_results(
    self,
    results: List[RetrievalResult],
    top_n: int
) -> List[str]:
    """Extract unique document IDs from top results"""
    # Implementation from design doc
```

### 2. `_rerank_at_page_level()` (add after _extract_doc_ids_from_results)
```python
def _rerank_at_page_level(
    self,
    query: str,
    doc_ids: List[str],
    config: HybridSearchConfig,
) -> List[CitationResult]:
    """Perform page-level reranking within documents"""
    # Implementation from design doc
```

### 3. `_citations_to_retrieval_results()` (add after _rerank_at_page_level)
```python
def _citations_to_retrieval_results(
    self,
    citations: List[CitationResult],
) -> List[RetrievalResult]:
    """Convert page-level citations back to RetrievalResult format"""
    # Implementation from design doc
```

---

## VALIDATION RULES

### ⚠️ Mutual Exclusion
**enable_page_reranking** and **enable_page_range_expansion** cannot both be True.

### Option 1: Config validation in __init__
```python
def __init__(self, ...):
    # ... existing code ...

    # Validate mutually exclusive options
    if self.config.enable_page_reranking and self.config.enable_page_range_expansion:
        logger.warning(
            "enable_page_reranking and enable_page_range_expansion are mutually exclusive. "
            "Disabling page_range_expansion."
        )
        self.config.enable_page_range_expansion = False
```

### Option 2: Runtime check in search()
Already handled in the integration logic above (early return when page_reranking enabled).

---

## TESTING REQUIREMENTS

### Unit Tests
1. **test_extract_doc_ids_from_results**: Verify doc_id extraction and deduplication
2. **test_citations_to_retrieval_results**: Verify conversion preserves all fields
3. **test_page_reranking_integration**: End-to-end with mock CitationRetriever

### Integration Tests
1. **test_page_reranking_enabled**: Verify page-level results when flag=True
2. **test_page_reranking_disabled**: Verify chunk-level results when flag=False (regression)
3. **test_mutual_exclusion**: Verify page_range_expansion disabled when page_reranking=True

### E2E Tests
1. **test_full_pipeline_with_page_reranking**: Real query → verify page numbers in response

---

## BACKWARD COMPATIBILITY CHECKLIST

✅ **No breaking changes**:
- Default `enable_page_reranking = False` preserves existing behavior
- Return type unchanged: `List[RetrievalResult]`
- Existing tests should pass without modification

✅ **Feature flag**:
- Can be toggled via config
- Can be overridden per-query via `config_override`

✅ **Graceful degradation**:
- If page reranking fails, falls back to original `fused_results`
- If CitationRetriever not available, raises clear error

---

## SUMMARY

### ✅ Exact Integration Points Identified:

| Point | Location | Action |
|-------|----------|--------|
| **Config** | Lines 70-86 | Add 5 new fields for page reranking |
| **Main Logic** | After line 278 | Insert page reranking block (~45 lines) |
| **Helper Methods** | After line 612 | Add 3 new private methods (~80 lines) |
| **Validation** | Line 116 (or 193) | Add mutual exclusion check |

### Total Code Changes:
- **Config**: +5 fields
- **Main logic**: +45 lines (conditional block)
- **Helpers**: +80 lines (3 methods)
- **Total**: ~130 lines added, 0 lines removed

### Risk Assessment: ✅ LOW
- No breaking changes
- Feature flag allows safe rollout
- Fallback on error
- Isolated changes (no existing logic modified)

---

## NEXT STEPS

1. ✅ **Build page embeddings** (prerequisite for page reranking)
2. ✅ **Implement config changes** in HybridSearchConfig
3. ✅ **Implement helper methods** (_extract, _rerank, _convert)
4. ✅ **Integrate main logic** in search() method
5. ✅ **Write unit tests** for helpers
6. ✅ **Write integration tests** for full flow
7. ✅ **Run regression tests** to verify backward compatibility

---

**Status**: Ready for implementation ✅
