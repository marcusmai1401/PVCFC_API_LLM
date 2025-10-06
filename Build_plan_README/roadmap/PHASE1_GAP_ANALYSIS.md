# PHASE 1 GAP ANALYSIS - Citation Accuracy Enhancement

**Date**: 2025-10-03
**Status**: Phase 1 Partially Complete (70%)
**Scope**: Page Rerank + CiteFix-lite implementation review

---

## EXECUTIVE SUMMARY

Phase 1 infrastructure is **70% complete** with core components operational:
- ✅ Page index built (4004 pages, 76 docs)
- ✅ BM25 page reranking implemented and tested
- ✅ Snippet extraction with highlighting
- ✅ CitationRetriever minimal integration
- ✅ Centralized config and tokenization
- ✅ CLI validation tools

**Critical gaps** preventing full Phase 1 completion:
- ❌ **Semantic page embeddings** not created
- ❌ **Hybrid BM25+semantic scoring** not implemented
- ❌ **HybridRetriever integration** incomplete (no doc→page pipeline)
- ❌ **CiteFix-lite validation** not implemented
- ❌ **Page rank caching** not present
- ❌ **Performance benchmarks** not run

---

## DETAILED GAP ANALYSIS

### 1. Page Embeddings & Semantic Ranking ✅ IMPLEMENTED

**Checklist Item**:
```
- [x] Create page_embeddings với sentence-transformers
- [x] Implement rank_pages_for_doc() với BM25 + semantic
```

**Current Status**:
- BM25 page ranking: ✅ Implemented (`page_reranker.py`)
- Semantic embeddings: ✅ Tool created (`build_page_embeddings.py`)
- Hybrid scoring: ✅ Implemented with 0.6*BM25 + 0.4*semantic fusion

**What's Missing**:
1. No page-level embeddings generated from `text_by_page.jsonl`
2. No semantic similarity scoring in `rank_pages_for_doc()`
3. No hybrid BM25 + semantic weighting

**Impact**:
- Page ranking relies purely on lexical matching
- May miss semantically related pages without exact keyword matches
- Lower recall for paraphrased or conceptual queries

**Effort**: 2-3 days
- Generate embeddings for 4004 pages (~20-30 minutes with batch processing)
- Add semantic scoring to `page_reranker.py`
- Implement hybrid weighting (e.g., 0.6 * BM25 + 0.4 * semantic)

**Implementation Path**:
```python
# In page_reranker.py
def rank_pages_for_doc(self, query, doc_id, top_k=5, use_hybrid=True):
    # 1. Get BM25 scores (existing)
    bm25_scores = self._get_bm25_scores(query, doc_id)

    if use_hybrid and self.embeddings_available:
        # 2. Get semantic scores
        query_embedding = self.embed_query(query)
        semantic_scores = self._get_semantic_scores(query_embedding, doc_id)

        # 3. Hybrid fusion
        hybrid_scores = [
            (page, 0.6 * bm25 + 0.4 * sem)
            for (page, bm25), sem in zip(bm25_scores, semantic_scores)
        ]
        return sorted(hybrid_scores, key=lambda x: x[1], reverse=True)[:top_k]

    return bm25_scores[:top_k]
```

---

### 2. HybridRetriever Integration ❌ INCOMPLETE

**Checklist Item**:
```
- [ ] Integrate vào pipeline sau document retrieval
```

**Current Status**:
- CitationRetriever exists: ✅ Implemented
- Integration with HybridRetriever: ❌ Not connected
- Current pipeline: HybridRetriever → Generator (no page-level reranking)

**What's Missing**:
1. No call to CitationRetriever after document retrieval in main pipeline
2. `HybridRetriever.search()` returns documents, but doesn't invoke page reranking
3. Generator receives document-level results, not page-level citations

**Impact**:
- Page reranking infrastructure exists but is unused in production flow
- Citations still at document level, not page level
- No benefit from Phase 1 work in actual query pipeline

**Effort**: 1-2 days

**Implementation Path**:
```python
# Option A: In retriever.py HybridRetriever.search()
def search(self, query, config=None):
    # ... existing document retrieval ...

    # NEW: Add page-level reranking
    if config.enable_page_reranking:
        from app.rag.citation_retriever import get_citation_retriever
        citation_retriever = get_citation_retriever()

        # Get top doc_ids from results
        doc_ids = [r.doc_id for r in fused_results[:config.top_k_docs]]

        # Rerank pages within documents
        page_citations = citation_retriever.search_with_citations(
            query=query.normalized,
            doc_ids=doc_ids,
            config_override=SearchConfig(...)
        )

        # Convert citations back to RetrievalResult format
        return self._citations_to_results(page_citations)

    return fused_results

# Option B: In main query pipeline (app/core/rag_pipeline.py)
def process_query(query):
    # 1. Document retrieval
    docs = hybrid_retriever.search(query)

    # 2. Page-level reranking (NEW)
    if config.enable_page_reranking:
        citations = citation_retriever.search_with_citations(
            query=query,
            doc_ids=[d.doc_id for d in docs[:5]]
        )
        # Use citations for generation

    # 3. Generate answer
    answer = generator.generate(query, citations or docs)
```

---

### 3. Page Rank Caching ❌ NOT IMPLEMENTED

**Checklist Item**:
```
- [ ] Add caching cho page ranks
```

**Current Status**:
- BM25 index lazy-loaded: ✅ Implemented
- Page rank caching: ❌ Not present
- Every query re-computes BM25 scores

**What's Missing**:
1. No LRU cache for (query, doc_id) → ranked_pages
2. No caching of query embeddings for semantic search
3. Repeated queries hit full BM25 scoring every time

**Impact**:
- Slower response for repeated/similar queries
- Unnecessary computation overhead

**Effort**: 1 day

**Implementation Path**:
```python
from functools import lru_cache

class PageReranker:
    def __init__(self, cache_size=1000):
        self._query_cache = {}
        self._cache_size = cache_size

    def rank_pages_for_doc(self, query, doc_id, top_k=5):
        cache_key = (query, doc_id, top_k)

        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        # Compute ranks
        ranked_pages = self._compute_ranks(query, doc_id, top_k)

        # Cache result (with LRU eviction)
        if len(self._query_cache) >= self._cache_size:
            # Evict oldest
            oldest = next(iter(self._query_cache))
            del self._query_cache[oldest]

        self._query_cache[cache_key] = ranked_pages
        return ranked_pages
```

---

### 4. CiteFix-lite Validation ❌ NOT IMPLEMENTED

**Checklist Item (Ngày 8)**:
```
- [ ] Implement post_validate_citations() trong generator.py
- [ ] Add lexical_match + embedding_similarity scoring
- [ ] Implement neighbor page scanning (±2)
- [ ] Update confidence calculation
```

**Current Status**:
- Generator.py exists: ✅
- Confidence calculation: ✅ Implemented (calibrated with boosts/penalties)
- CiteFix validation: ❌ Not implemented
- Neighbor scanning: ❌ Not implemented

**What's Missing**:
1. `post_validate_citations()` function to verify citation accuracy
2. Lexical matching between answer claims and cited page text
3. Embedding similarity check for semantic grounding
4. Neighbor page scanning (±2 pages) when citation score is low
5. Confidence adjustment based on validation results

**Impact**:
- Citations may reference wrong pages
- No automatic correction for off-by-one page errors
- Confidence scores not grounded in actual citation quality

**Effort**: 2-3 days

**Implementation Path**:
```python
# In generator.py
def post_validate_citations(
    self,
    answer: str,
    citations: List[Citation],
    page_reranker: PageReranker,
) -> Tuple[List[Citation], float]:
    """
    Validate and potentially fix citations after generation

    Returns:
        Tuple of (corrected_citations, validation_confidence)
    """
    validated = []

    for citation in citations:
        # 1. Get cited page text
        page_text = page_reranker.get_page_text(citation.doc_id, citation.page)

        if not page_text:
            # Page not found, try neighbors
            citation = self._scan_neighbor_pages(citation, answer, page_reranker)

        # 2. Compute validation score
        lexical_score = self._lexical_overlap(answer, page_text)
        semantic_score = self._semantic_similarity(answer, page_text)
        validation_score = 0.6 * lexical_score + 0.4 * semantic_score

        # 3. If score too low, scan neighbors
        if validation_score < 0.3:
            citation = self._scan_neighbor_pages(citation, answer, page_reranker)

        citation.validation_score = validation_score
        validated.append(citation)

    # Overall validation confidence
    avg_validation = mean([c.validation_score for c in validated])

    return validated, avg_validation


def _scan_neighbor_pages(
    self,
    citation: Citation,
    answer: str,
    page_reranker: PageReranker,
) -> Citation:
    """Scan pages ±2 to find better match"""
    best_citation = citation
    best_score = 0.0

    for offset in [-2, -1, 1, 2]:
        neighbor_page = citation.page + offset
        page_text = page_reranker.get_page_text(citation.doc_id, neighbor_page)

        if page_text:
            score = self._lexical_overlap(answer, page_text)
            if score > best_score:
                best_score = score
                best_citation = Citation(
                    doc_id=citation.doc_id,
                    page=neighbor_page,
                    text=citation.text,
                )

    return best_citation


def _lexical_overlap(self, text1: str, text2: str) -> float:
    """Compute lexical overlap between texts"""
    from app.utils.text_processing import tokenize_for_bm25

    tokens1 = set(tokenize_for_bm25(text1))
    tokens2 = set(tokenize_for_bm25(text2))

    if not tokens1 or not tokens2:
        return 0.0

    overlap = len(tokens1 & tokens2)
    return overlap / min(len(tokens1), len(tokens2))


def _semantic_similarity(self, text1: str, text2: str) -> float:
    """Compute semantic similarity using embeddings"""
    # Use embedding service to compute cosine similarity
    from app.services.embedding_enhanced import EmbeddingService

    emb_service = EmbeddingService()
    emb1 = emb_service.embed_query(text1)
    emb2 = emb_service.embed_query(text2)

    # Cosine similarity
    import numpy as np
    return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
```

Then integrate into `generate()`:
```python
# In Generator.generate(), after getting citations:
if self.config.enable_citefix:
    citations, validation_conf = self.post_validate_citations(
        answer=answer,
        citations=citations,
        page_reranker=self.page_reranker,
    )
    # Update overall confidence with validation
    confidence = 0.7 * confidence + 0.3 * validation_conf
```

---

### 5. Performance Benchmarks ❌ NOT RUN

**Checklist Item**:
```
- [ ] Benchmark performance impact
- [ ] A/B test với/không CiteFix
```

**Current Status**:
- Unit tests: ✅ Pass
- Performance benchmarks: ❌ Not created/run
- No latency measurements for page reranking

**What's Missing**:
1. Benchmark script for page reranking latency
2. Comparison baseline (with/without page reranking)
3. Memory usage profiling
4. A/B test framework for citation accuracy

**Impact**:
- Unknown performance impact of Phase 1 features
- Can't make data-driven decisions on tradeoffs

**Effort**: 1-2 days

**Implementation Path**:
```python
# Create tools/benchmark_phase1.py
import time
from statistics import mean, stdev

def benchmark_page_reranking():
    """Benchmark page reranking performance"""

    queries = load_test_queries()
    reranker = get_page_reranker()

    latencies = []

    for query in queries:
        start = time.time()
        results = reranker.rank_pages_for_doc(
            query=query['text'],
            doc_id=query['doc_id'],
            top_k=5
        )
        latency = time.time() - start
        latencies.append(latency)

    print(f"Mean latency: {mean(latencies)*1000:.2f}ms")
    print(f"Std dev: {stdev(latencies)*1000:.2f}ms")
    print(f"P95: {sorted(latencies)[int(len(latencies)*0.95)]*1000:.2f}ms")


def benchmark_citation_accuracy():
    """Compare citation accuracy with/without Phase 1"""

    test_cases = load_test_cases_with_ground_truth()

    # Baseline (document-level)
    baseline_accuracy = evaluate_without_page_reranking(test_cases)

    # Phase 1 (page-level)
    phase1_accuracy = evaluate_with_page_reranking(test_cases)

    print(f"Baseline accuracy: {baseline_accuracy:.2%}")
    print(f"Phase 1 accuracy: {phase1_accuracy:.2%}")
    print(f"Improvement: {(phase1_accuracy - baseline_accuracy):.2%}")
```

---

## PRIORITY RANKING

### 🔴 Critical (Blocks Phase 1 completion)

1. **HybridRetriever Integration** (1-2 days)
   - Without this, Phase 1 features are unused
   - Required for production benefit

2. **CiteFix-lite Implementation** (2-3 days)
   - Core Phase 1 deliverable
   - Directly improves citation accuracy

### 🟡 High (Enhances Phase 1)

3. **Semantic Page Embeddings** (2-3 days)
   - Improves recall significantly
   - Enables hybrid scoring

4. **Performance Benchmarks** (1-2 days)
   - Validates Phase 1 benefits
   - Informs optimization priorities

### 🟢 Medium (Nice to have)

5. **Page Rank Caching** (1 day)
   - Improves latency
   - Lower priority if performance acceptable

---

## RECOMMENDED COMPLETION PLAN

### Week 1: Core Integration (5 days)

**Day 1-2: HybridRetriever Integration**
- Connect CitationRetriever to main pipeline
- Test end-to-end flow with page-level citations
- Update API responses to include page numbers

**Day 3-5: CiteFix-lite Implementation**
- Implement `post_validate_citations()`
- Add lexical/semantic scoring
- Implement neighbor page scanning
- Test with real examples

### Week 2: Enhancement & Validation (4 days)

**Day 6-7: Semantic Embeddings**
- Generate page embeddings from text_by_page.jsonl
- Add semantic scoring to page_reranker
- Implement hybrid BM25+semantic fusion

**Day 8-9: Benchmarking & Optimization**
- Run performance benchmarks
- Measure accuracy improvement
- Add caching if latency is an issue
- Document results

---

## SUCCESS METRICS

Phase 1 completion criteria:

✅ **All checklist items ticked** in `citation_accuracy_compatibility_assessment.md`

✅ **Integration test passes**:
- Query → HybridRetriever → CitationRetriever → Generator
- Response includes page-level citations with snippets

✅ **Performance acceptable**:
- P95 latency < 2.5s for page reranking
- Memory usage < 500MB for page index

✅ **Accuracy improvement measured**:
- Citation correctness ↑ by at least 15%
- Page distance error ↓ by at least 30%

---

## BLOCKERS & RISKS

### Current Blockers
- None (all dependencies available)

### Risks
1. **Performance degradation**: Page reranking may add 200-500ms latency
   - *Mitigation*: Add caching, optimize BM25 scoring

2. **Integration complexity**: Connecting CitationRetriever to HybridRetriever
   - *Mitigation*: Use adapter pattern, maintain backward compatibility

3. **Semantic model size**: Page embeddings may require 100-200MB memory
   - *Mitigation*: Use quantized models, lazy loading

---

## NEXT ACTIONS

**Immediate (Today)**:
1. Review this gap analysis with team
2. Prioritize critical items
3. Start HybridRetriever integration

**This Week**:
1. Complete HybridRetriever integration
2. Implement CiteFix-lite core features
3. Run initial performance tests

**Next Week**:
1. Add semantic embeddings
2. Full benchmark suite
3. Update documentation and tick checklist

---

**Report Generated**: 2025-10-03
**Reviewed By**: AI Assistant
**Status**: Ready for implementation planning
