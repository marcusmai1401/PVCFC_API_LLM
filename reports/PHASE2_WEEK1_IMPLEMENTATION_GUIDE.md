# Phase 2 - Week 1 Implementation Guide

**Goal:** Implement Steps B-D (Retrieval & Reranking)
**Date:** 2025-10-08
**Status:** Ready for implementation

---

## Overview

Week 1 focuses on implementing the core retrieval and reranking pipeline:
- **Step B:** Hybrid page search (BM25 + Vector)
- **Step C:** RRF merge and deduplication
- **Step D:** Cross-encoder reranking

---

## Day 1: RRF Merge + BM25 Search

### Task 1.1: Implement `rrf_merge()` in PageFirstAgent

**File:** `app/rag/page_first_agent.py`

**Replace the NotImplementedError in `rrf_merge()` with:**

```python
def rrf_merge(
    self,
    bm25_hits: List[PageHit],
    vec_hits: List[PageHit]
) -> List[PageHit]:
    """
    Step C: Reciprocal Rank Fusion (RRF) and deduplication.

    RRF formula: score = sum(1 / (k + rank_i)) for each list
    Standard k = 60
    """
    from collections import defaultdict

    logger.debug(f"Merging {len(bm25_hits)} BM25 + {len(vec_hits)} vector hits")

    # RRF constant
    k = 60

    # Accumulate scores by (doc_id, page)
    scores = defaultdict(float)
    hit_info = {}  # Store metadata for each (doc_id, page)

    # Process BM25 hits
    for rank, hit in enumerate(bm25_hits, start=1):
        key = (hit['doc_id'], hit['page'])
        scores[key] += 1.0 / (k + rank)

        if key not in hit_info:
            hit_info[key] = {
                'doc_id': hit['doc_id'],
                'page': hit['page'],
                'text': hit.get('text', ''),
                'bm25_score': hit.get('score', 0.0),
                'bm25_rank': rank,
            }

    # Process vector hits
    for rank, hit in enumerate(vec_hits, start=1):
        key = (hit['doc_id'], hit['page'])
        scores[key] += 1.0 / (k + rank)

        if key not in hit_info:
            hit_info[key] = {
                'doc_id': hit['doc_id'],
                'page': hit['page'],
                'text': hit.get('text', ''),
                'vec_score': hit.get('score', 0.0),
                'vec_rank': rank,
            }
        else:
            hit_info[key]['vec_score'] = hit.get('score', 0.0)
            hit_info[key]['vec_rank'] = rank

    # Create merged results
    merged = []
    for key, rrf_score in scores.items():
        info = hit_info[key]
        merged.append({
            'doc_id': info['doc_id'],
            'page': info['page'],
            'text': info['text'],
            'fused_score': rrf_score,
            'bm25_score': info.get('bm25_score', 0.0),
            'vec_score': info.get('vec_score', 0.0),
            'bm25_rank': info.get('bm25_rank', None),
            'vec_rank': info.get('vec_rank', None),
        })

    # Sort by fused score descending
    merged.sort(key=lambda x: x['fused_score'], reverse=True)

    # Keep top MERGED_K
    top_merged = merged[:self.config.MERGED_K]

    logger.debug(
        f"RRF merged to {len(merged)} unique pages, "
        f"kept top {len(top_merged)}"
    )

    return top_merged
```

**Unit Test:**

Create `tests/unit/test_rrf_merge.py`:

```python
import sys
sys.path.insert(0, '.')

from app.rag.page_first_config import PageFirstConfig
from app.rag.page_first_agent import PageFirstAgent

def test_rrf_merge():
    """Test RRF merging with mock hits"""
    config = PageFirstConfig(MERGED_K=5)
    agent = PageFirstAgent(config)

    # Mock BM25 hits
    bm25_hits = [
        {'doc_id': 'doc1', 'page': 1, 'score': 10.0, 'text': 'text1'},
        {'doc_id': 'doc1', 'page': 2, 'score': 8.0, 'text': 'text2'},
        {'doc_id': 'doc2', 'page': 1, 'score': 7.0, 'text': 'text3'},
    ]

    # Mock vector hits (some overlap)
    vec_hits = [
        {'doc_id': 'doc1', 'page': 1, 'score': 0.95, 'text': 'text1'},  # Overlap
        {'doc_id': 'doc3', 'page': 1, 'score': 0.90, 'text': 'text4'},
        {'doc_id': 'doc2', 'page': 2, 'score': 0.85, 'text': 'text5'},
    ]

    # Merge
    merged = agent.rrf_merge(bm25_hits, vec_hits)

    # Assertions
    assert len(merged) <= 5, "Should respect MERGED_K limit"
    assert merged[0]['doc_id'] == 'doc1', "Doc1 Page1 should rank highest (in both lists)"
    assert merged[0]['page'] == 1
    assert 'fused_score' in merged[0], "Should have fused_score"
    assert merged[0]['fused_score'] > 0, "Fused score should be positive"

    # Check deduplication
    keys = [(h['doc_id'], h['page']) for h in merged]
    assert len(keys) == len(set(keys)), "Should have no duplicate (doc_id, page)"

    print("✓ RRF merge test passed")

if __name__ == "__main__":
    test_rrf_merge()
```

**Run test:**
```bash
python tests/unit/test_rrf_merge.py
```

---

### Task 1.2: Implement BM25 Page Search Helper

**File:** `app/rag/page_first_agent.py`

**Add new helper method (before `search_pages_hybrid`):**

```python
def _search_pages_bm25(self, query: str, top_k: int) -> List[PageHit]:
    """
    Search pages using BM25.

    Uses PageReranker's BM25 index to search across all pages.

    Args:
        query: Search query
        top_k: Number of results to return

    Returns:
        List of page hits with BM25 scores
    """
    if not self.reranker:
        logger.warning("PageReranker not available, returning empty BM25 results")
        return []

    try:
        # PageReranker has BM25 page index
        # Call its search method (assumes it exists)
        # Format varies by implementation, adapt as needed

        # Option 1: If PageReranker has search_all_pages():
        # results = self.reranker.search_all_pages(query, top_k=top_k)

        # Option 2: Load BM25 index directly
        if hasattr(self.reranker, '_page_index') and self.reranker._page_index:
            from rank_bm25 import BM25Okapi

            # Get BM25 index
            bm25 = self.reranker._page_index.get('bm25')
            doc_ids = self.reranker._page_index.get('doc_ids', [])
            pages = self.reranker._page_index.get('pages', [])
            corpus = self.reranker._page_index.get('corpus', [])

            if not bm25:
                logger.warning("BM25 index not loaded")
                return []

            # Tokenize query (use same tokenization as index)
            from app.utils.text_processing import tokenize_for_bm25
            query_tokens = tokenize_for_bm25(query)

            # Get scores
            scores = bm25.get_scores(query_tokens)

            # Get top-k indices
            import numpy as np
            top_indices = np.argsort(scores)[::-1][:top_k]

            # Build results
            results = []
            for idx in top_indices:
                if scores[idx] > 0:  # Only include if score > 0
                    results.append({
                        'doc_id': doc_ids[idx],
                        'page': int(pages[idx]),
                        'score': float(scores[idx]),
                        'source': 'bm25',
                        'text': corpus[idx][:500],  # Truncate for memory
                    })

            logger.debug(f"BM25 search returned {len(results)} results")
            return results

        else:
            logger.warning("BM25 index structure not recognized")
            return []

    except Exception as e:
        logger.error(f"BM25 search failed: {e}", exc_info=True)
        return []
```

**Update `search_pages_hybrid()` to use the helper:**

```python
def search_pages_hybrid(self, query: str) -> tuple[List[PageHit], List[PageHit]]:
    """Step B: Hybrid page retrieval (BM25 + Vector)."""
    logger.debug(f"Hybrid search: BM25={self.config.TOPK_BM25}, VEC={self.config.TOPK_VEC}")

    # BM25 search
    bm25_hits = self._search_pages_bm25(query, self.config.TOPK_BM25)

    # Vector search (placeholder for now)
    vec_hits = []  # Will implement in Day 2

    logger.info(f"Retrieved {len(bm25_hits)} BM25 hits, {len(vec_hits)} vector hits")

    return bm25_hits, vec_hits
```

---

## Day 2: Vector Search Implementation

### Task 2.1: Implement Vector Page Search

**File:** `app/rag/page_first_agent.py`

**Add new helper method:**

```python
def _search_pages_vector(self, query: str, top_k: int) -> List[PageHit]:
    """
    Search pages using vector similarity.

    Uses page embeddings to find semantically similar pages.

    Args:
        query: Search query
        top_k: Number of results to return

    Returns:
        List of page hits with cosine similarity scores
    """
    try:
        import numpy as np
        from pathlib import Path

        # Load page embeddings
        embeddings_path = Path("artifacts/ingestion_production/page_embeddings.npz")

        if not embeddings_path.exists():
            logger.warning(f"Page embeddings not found at {embeddings_path}")
            return []

        # Load embeddings
        data = np.load(embeddings_path, allow_pickle=True)
        embeddings = data['embeddings']  # Shape: (N, 768)
        doc_ids = data['doc_ids']
        pages = data['pages']

        logger.debug(f"Loaded {len(embeddings)} page embeddings")

        # Embed query
        if not hasattr(self, '_embedding_service'):
            from app.services.embedding_enhanced import EmbeddingService
            self._embedding_service = EmbeddingService()

        query_embedding = self._embedding_service.embed_text(query)
        query_vec = np.array(query_embedding).reshape(1, -1)

        # Compute cosine similarity
        # Normalize vectors
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        embeddings_norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10)

        # Cosine similarity = dot product of normalized vectors
        similarities = (embeddings_norm @ query_norm.T).flatten()

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        # Build results
        results = []
        for idx in top_indices:
            if similarities[idx] > 0.1:  # Minimum similarity threshold
                results.append({
                    'doc_id': str(doc_ids[idx]),
                    'page': int(pages[idx]),
                    'score': float(similarities[idx]),
                    'source': 'vector',
                    'text': '',  # Will load on demand if needed
                })

        logger.debug(f"Vector search returned {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        return []
```

**Update `search_pages_hybrid()` to use both:**

```python
def search_pages_hybrid(self, query: str) -> tuple[List[PageHit], List[PageHit]]:
    """Step B: Hybrid page retrieval (BM25 + Vector)."""
    import time
    start = time.time()

    logger.debug(f"Hybrid search: BM25={self.config.TOPK_BM25}, VEC={self.config.TOPK_VEC}")

    # BM25 search
    bm25_hits = self._search_pages_bm25(query, self.config.TOPK_BM25)

    # Vector search
    vec_hits = self._search_pages_vector(query, self.config.TOPK_VEC)

    elapsed = (time.time() - start) * 1000
    logger.info(
        f"Hybrid retrieval: {len(bm25_hits)} BM25 + {len(vec_hits)} vector "
        f"in {elapsed:.0f}ms"
    )

    return bm25_hits, vec_hits
```

---

## Day 3: Cross-Encoder Reranking

### Task 3.1: Implement `cross_encoder_rerank()`

**File:** `app/rag/page_first_agent.py`

**Replace NotImplementedError with:**

```python
def cross_encoder_rerank(
    self,
    query: str,
    pages: List[PageHit]
) -> List[PageHit]:
    """
    Step D: Cross-encoder page reranking.

    Reranks pages using hybrid scoring (BM25 + semantic if available).
    Falls back to BM25 rescoring if cross-encoder unavailable.
    """
    logger.debug(f"Reranking {len(pages)} pages, keeping top {self.config.RERANK_KEEP}")

    if not pages:
        return []

    # Load page texts
    pages_with_text = []
    for page in pages:
        if not page.get('text'):
            # Load text from PageReranker
            if self.reranker:
                try:
                    text = self.reranker.get_page_text(page['doc_id'], page['page'])
                    page['text'] = text[:2000]  # Truncate for memory
                except Exception as e:
                    logger.warning(f"Failed to load text for {page['doc_id']} p{page['page']}: {e}")
                    page['text'] = ''

        if page.get('text'):
            pages_with_text.append(page)

    logger.debug(f"Loaded text for {len(pages_with_text)}/{len(pages)} pages")

    # Rerank using hybrid scoring
    # Option 1: Use PageReranker's hybrid scoring if available
    if self.reranker and hasattr(self.reranker, 'rank_pages_for_doc'):
        # Group pages by doc_id
        by_doc = {}
        for page in pages_with_text:
            doc_id = page['doc_id']
            if doc_id not in by_doc:
                by_doc[doc_id] = []
            by_doc[doc_id].append(page)

        # Rerank each document's pages
        reranked_all = []
        for doc_id, doc_pages in by_doc.items():
            try:
                # Call PageReranker
                page_nums = [p['page'] for p in doc_pages]
                ranked = self.reranker.rank_pages_for_doc(
                    query=query,
                    doc_id=doc_id,
                    top_k=len(page_nums),  # Rerank all
                    page_candidates=page_nums
                )

                # Merge scores back
                for page, (page_num, score) in zip(doc_pages, ranked):
                    page['rerank_score'] = score
                    reranked_all.append(page)

            except Exception as e:
                logger.warning(f"Reranking failed for {doc_id}: {e}")
                # Fallback: use fused_score
                for page in doc_pages:
                    page['rerank_score'] = page.get('fused_score', 0.0)
                    reranked_all.append(page)

    else:
        # Fallback: use fused_score from RRF
        logger.warning("PageReranker unavailable, using fused_score for reranking")
        reranked_all = pages_with_text
        for page in reranked_all:
            page['rerank_score'] = page.get('fused_score', 0.0)

    # Sort by rerank_score
    reranked_all.sort(key=lambda x: x['rerank_score'], reverse=True)

    # Keep top RERANK_KEEP
    top_pages = reranked_all[:self.config.RERANK_KEEP]

    # Log diversity
    doc_ids = [p['doc_id'] for p in top_pages]
    unique_docs = len(set(doc_ids))
    logger.info(
        f"Reranked to top {len(top_pages)} pages "
        f"from {unique_docs} documents"
    )

    return top_pages
```

---

## Day 4: Integration Testing

### Test Script

Create `tests/integration/test_week1_retrieval.py`:

```python
"""Integration test for Week 1: Retrieval & Reranking"""
import sys
import time
sys.path.insert(0, '.')

from app.rag.page_first_config import PageFirstConfig
from app.rag.page_first_agent import PageFirstAgent

def test_full_retrieval_pipeline():
    """Test Steps B-C-D together"""
    print("=== Week 1 Integration Test: Retrieval & Reranking ===\n")

    # Setup
    config = PageFirstConfig.from_env()
    config.validate()
    print(f"Config: {config}\n")

    agent = PageFirstAgent(config)

    # Test query
    query = "maximum operating pressure for compressor KT-06101"
    print(f"Query: {query}\n")

    # Step B: Hybrid retrieval
    print("Step B: Hybrid retrieval...")
    start = time.time()
    bm25_hits, vec_hits = agent.search_pages_hybrid(query)
    elapsed_b = (time.time() - start) * 1000

    print(f"  BM25 hits: {len(bm25_hits)}")
    print(f"  Vector hits: {len(vec_hits)}")
    print(f"  Time: {elapsed_b:.0f}ms\n")

    assert len(bm25_hits) > 0, "BM25 should return results"

    # Step C: RRF merge
    print("Step C: RRF merge...")
    start = time.time()
    merged = agent.rrf_merge(bm25_hits, vec_hits)
    elapsed_c = (time.time() - start) * 1000

    print(f"  Merged: {len(merged)} unique pages")
    print(f"  Time: {elapsed_c:.0f}ms\n")

    assert len(merged) > 0, "RRF should return results"
    assert len(merged) <= config.MERGED_K, f"Should not exceed MERGED_K={config.MERGED_K}"

    # Show top 3 merged
    print("  Top 3 merged:")
    for i, page in enumerate(merged[:3], 1):
        print(f"    {i}. {page['doc_id'][:40]}... page {page['page']} "
              f"(fused={page['fused_score']:.4f})")
    print()

    # Step D: Rerank
    print("Step D: Cross-encoder rerank...")
    start = time.time()
    reranked = agent.cross_encoder_rerank(query, merged)
    elapsed_d = (time.time() - start) * 1000

    print(f"  Reranked: {len(reranked)} pages")
    print(f"  Time: {elapsed_d:.0f}ms\n")

    assert len(reranked) > 0, "Rerank should return results"
    assert len(reranked) <= config.RERANK_KEEP, f"Should not exceed RERANK_KEEP={config.RERANK_KEEP}"

    # Show top 3 reranked
    print("  Top 3 reranked:")
    for i, page in enumerate(reranked[:3], 1):
        print(f"    {i}. {page['doc_id'][:40]}... page {page['page']} "
              f"(rerank={page['rerank_score']:.4f})")
    print()

    # Total timing
    total_ms = elapsed_b + elapsed_c + elapsed_d
    print(f"Total retrieval+rerank: {total_ms:.0f}ms")

    assert total_ms < 2000, f"Should complete in <2s, got {total_ms:.0f}ms"

    print("\n✓ Week 1 integration test PASSED")

if __name__ == "__main__":
    test_full_retrieval_pipeline()
```

**Run test:**
```bash
python tests/integration/test_week1_retrieval.py
```

---

## Success Criteria - Week 1

| Criterion | Target | Test |
|-----------|--------|------|
| RRF merge working | Yes | Unit test passes |
| BM25 search returning results | >0 results | Integration test |
| Vector search (if embeddings available) | >0 results | Integration test |
| Reranking producing top pages | Top 8 pages | Integration test |
| Total latency (retrieval+rerank) | <2s | Integration test |
| No errors/crashes | Zero | All tests pass |

---

## Next Week Preview

**Week 2:** Steps E-F (Context building + LLM integration)
- Build page context with neighbor pages
- Implement token counting and truncation
- LLM structured output integration
- Test end-to-end: query → answer

---

**Report Status:** READY FOR IMPLEMENTATION
**Estimated Time:** 2-3 days for experienced developer
**Dependencies:** PageReranker, EmbeddingService (existing)

🚀 **Begin implementation when ready!**
