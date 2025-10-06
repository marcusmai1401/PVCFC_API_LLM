# HybridRetriever Integration Design Document

**Date**: 2025-10-03
**Status**: Design Approved
**Task**: Integrate CitationRetriever into HybridRetriever for page-level results

---

## CURRENT STATE ANALYSIS

### HybridRetriever
- **Input**: `TransformedQuery`
- **Output**: `List[RetrievalResult]` (chunk-level)
- **Flow**: BM25 + FAISS → RRF fusion → page-range expansion → parent expansion
- **Config**: `HybridSearchConfig` (k_bm25, k_faiss, top_rrf, etc.)

### CitationRetriever
- **Input**: query (str), doc_ids (List[str])
- **Output**: `List[CitationResult]` (page-level)
- **Flow**: Get doc_ids → rank pages in each doc → extract snippets → assemble citations
- **Config**: `SearchConfig` (top_k_docs, top_k_pages_per_doc, etc.)

### Key Differences

| Aspect | RetrievalResult | CitationResult |
|--------|----------------|----------------|
| Granularity | Chunk-level | Page-level |
| Text | chunk.text | page_text + snippets |
| Score | RRF score | BM25/hybrid page score |
| Metadata | chunk metadata | page metadata + doc_name |
| Structure | Simple | Nested (has Snippet[]) |

---

## INTEGRATION STRATEGY COMPARISON

### Option A: Modify HybridRetriever.search() to return CitationResult

**Approach**: Change return type from `List[RetrievalResult]` to `List[CitationResult]`

**Pros**:
- Clean API, no conversion needed
- Page-level results directly from retriever

**Cons**:
- ❌ **BREAKING CHANGE** - affects all existing code using HybridRetriever
- ❌ Generator expects RetrievalResult format
- ❌ High risk, requires updating many files

**Verdict**: ❌ **REJECTED** (too risky)

---

### Option B: Post-processing layer (Adapter pattern)

**Approach**: Keep HybridRetriever unchanged, add adapter that:
1. Calls HybridRetriever.search() → get RetrievalResult[]
2. Extracts doc_ids from results
3. Calls CitationRetriever with those doc_ids → get CitationResult[]
4. Converts back to RetrievalResult[] for generator

**Pros**:
- ✅ **Zero breaking changes** to existing code
- ✅ Easy to toggle on/off with feature flag
- ✅ Clean separation of concerns
- ✅ Can be added in pipeline layer

**Cons**:
- Extra conversion overhead
- Two-pass retrieval (doc-level → page-level)

**Verdict**: ✅ **BEST OPTION**

---

### Option C: Inline integration in search() method

**Approach**: Add optional page-reranking directly inside HybridRetriever.search():
1. Do normal BM25+FAISS → RRF fusion
2. If enable_page_reranking: extract doc_ids → page rerank → convert
3. Return RetrievalResult[] (same format)

**Pros**:
- ✅ No breaking changes (return type unchanged)
- ✅ Single-pass retrieval
- ✅ Configurable via HybridSearchConfig

**Cons**:
- Adds complexity to HybridRetriever
- Mixing chunk-level and page-level logic

**Verdict**: ✅ **GOOD ALTERNATIVE** (chosen if performance critical)

---

## CHOSEN STRATEGY: Option C (Inline Integration)

**Rationale**:
- No breaking changes (critical)
- Better performance (single pass)
- Keep same interface for Generator
- Configurable with feature flag

---

## DETAILED DESIGN

### 1. Add Config Fields to HybridSearchConfig

```python
@dataclass
class HybridSearchConfig:
    # ... existing fields ...

    # Page-level reranking (Phase 1)
    enable_page_reranking: bool = False  # Feature flag
    top_k_pages_per_doc: int = 3  # Pages per document
    max_snippets_per_page: int = 3  # Snippets per page
    page_reranking_min_score: float = 0.0  # Min BM25 score threshold
```

### 2. Integration Flow in HybridRetriever.search()

```python
def search(self, transformed_query, config_override=None):
    config = config_override or self.config

    # Step 1: Normal BM25 + FAISS → RRF fusion (existing)
    all_results = []
    # ... BM25 search ...
    # ... FAISS search ...
    fused_results = self._reciprocal_rank_fusion(all_results, ...)

    # Step 2: Page-level reranking (NEW - Phase 1)
    if config.enable_page_reranking:
        # Extract unique doc_ids from top results
        doc_ids = self._extract_doc_ids_from_results(fused_results, config.top_k_docs)

        # Call CitationRetriever for page-level ranking
        citations = self._rerank_at_page_level(
            query=transformed_query.normalized,
            doc_ids=doc_ids,
            config=config,
        )

        # Convert citations back to RetrievalResult format
        fused_results = self._citations_to_retrieval_results(citations)

    # Step 3: Apply page-range expansion or parent expansion (existing)
    if config.enable_page_range_expansion:
        fused_results = self.page_expander.expand_results(fused_results, ...)
    elif config.expand_parent:
        fused_results = self._expand_parent_context(fused_results, ...)

    return fused_results
```

### 3. Conversion Helpers

#### 3.1 Extract doc_ids from results
```python
def _extract_doc_ids_from_results(self, results: List[RetrievalResult], top_n: int) -> List[str]:
    """Extract unique document IDs from top results"""
    seen = set()
    doc_ids = []

    for result in results:
        if result.doc_id and result.doc_id not in seen:
            doc_ids.append(result.doc_id)
            seen.add(result.doc_id)

            if len(doc_ids) >= top_n:
                break

    return doc_ids
```

#### 3.2 Call page reranker
```python
def _rerank_at_page_level(
    self,
    query: str,
    doc_ids: List[str],
    config: HybridSearchConfig,
) -> List[CitationResult]:
    """Perform page-level reranking within documents"""
    from app.rag.citation_retriever import get_citation_retriever, SearchConfig

    citation_retriever = get_citation_retriever()

    citation_config = SearchConfig(
        top_k_docs=len(doc_ids),  # Use all provided doc_ids
        top_k_pages_per_doc=config.top_k_pages_per_doc,
        min_page_score=config.page_reranking_min_score,
        max_snippets_per_page=config.max_snippets_per_page,
        max_total_citations=config.top_rrf,  # Match original top_rrf limit
    )

    return citation_retriever.search_with_citations(
        query=query,
        doc_ids=doc_ids,
        config_override=citation_config,
    )
```

#### 3.3 Convert citations to RetrievalResult
```python
def _citations_to_retrieval_results(
    self,
    citations: List[CitationResult],
) -> List[RetrievalResult]:
    """Convert page-level citations back to RetrievalResult format for Generator"""
    results = []

    for citation in citations:
        # Use page text (may include snippets in metadata)
        text = citation.page_text

        # Build metadata
        metadata = {
            **citation.metadata,
            "page": citation.page,
            "citation_rank": citation.rank,
            "page_level_result": True,  # Flag to indicate page-level
        }

        # Add snippets to metadata for Generator access
        if citation.snippets:
            metadata["snippets"] = [
                {
                    "text": s.text,
                    "highlighted": s.highlighted_text,
                    "score": s.score,
                }
                for s in citation.snippets
            ]

        result = RetrievalResult(
            chunk_id=f"page_{citation.doc_id}_{citation.page}",
            text=text,
            score=citation.score,
            source="page_reranked",  # Identify source
            metadata=metadata,
            doc_id=citation.doc_id,
            page=citation.page,
            bbox=None,
            parent_id=None,
        )

        results.append(result)

    return results
```

---

## METADATA MAPPING

| Field | CitationResult | RetrievalResult | Notes |
|-------|----------------|----------------|-------|
| doc_id | doc_id | doc_id | Direct copy |
| page | page | page | Direct copy |
| score | score (page BM25) | score | Direct copy |
| page_text | page_text | text | Main content |
| snippets | snippets[] | metadata['snippets'] | Nested in metadata |
| metadata | metadata{} | metadata{} | Merged + flags |
| rank | rank | metadata['citation_rank'] | For tracking |

---

## BACKWARD COMPATIBILITY

**With enable_page_reranking=False**:
- No changes to existing behavior
- Returns same RetrievalResult[] as before
- All existing code continues to work

**With enable_page_reranking=True**:
- Returns RetrievalResult[] (same type)
- But granularity is page-level instead of chunk-level
- `metadata['page_level_result'] = True` flag to identify
- Generator can detect and handle differently if needed

---

## PERFORMANCE CONSIDERATIONS

**Additional Latency**:
- Page reranking: ~50-200ms (depends on semantic embeddings)
- Snippet extraction: ~10-50ms per page
- Conversion: ~1ms (negligible)
- **Total overhead**: ~100-300ms

**Optimization**:
- Lazy-load embeddings (already implemented)
- Cache page ranks (future enhancement)
- Parallel page processing (future enhancement)

---

## TESTING STRATEGY

1. **Unit test**: _citations_to_retrieval_results() with mock data
2. **Integration test**: HybridRetriever with enable_page_reranking=True
3. **Regression test**: enable_page_reranking=False → same as before
4. **E2E test**: Full pipeline query → verify page numbers in response

---

## ROLLOUT PLAN

### Phase 1: Implementation (This task)
- Add config fields
- Add conversion helpers
- Integrate into search() flow
- Write unit tests

### Phase 2: Testing
- Run integration tests
- Verify backward compatibility
- Test with real queries

### Phase 3: Deployment
- Deploy with enable_page_reranking=False (default)
- Monitor performance
- Gradually enable for subset of users
- Full rollout after validation

---

## DECISION: ✅ APPROVED

**Strategy**: Option C (Inline Integration)
**Risk Level**: Low (no breaking changes)
**Implementation Time**: 2-3 hours
**Testing Time**: 1-2 hours

Proceeding with implementation.
