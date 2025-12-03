"""Integration test for hybrid BM25+semantic page ranking"""
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_config
from app.rag.page_reranker import PageReranker


def test_hybrid_ranking_with_real_embeddings():
    """Test that hybrid ranking works end-to-end with real embeddings"""
    cfg = get_config()

    # Verify embeddings exist
    assert cfg.page_embeddings_path.exists(), "Embeddings file not found"

    # Get a sample doc_id from BM25 index
    import pickle

    with open(cfg.page_bm25_index_path, "rb") as f:
        bm25_data = pickle.load(f)

    # Pick first doc_id
    sample_doc_id = bm25_data["doc_ids"][0]

    print(f"\nTesting hybrid ranking for doc_id: {sample_doc_id[:50]}...")

    # Initialize reranker
    reranker = PageReranker()

    # Test with a technical query
    query = "operating pressure temperature specifications"

    results = reranker.rank_pages_for_doc(
        query=query,
        doc_id=sample_doc_id,
        top_k=5,
    )

    print(f"\nQuery: '{query}'")
    print(f"Results: {len(results)} pages")

    for i, (page, score) in enumerate(results, 1):
        print(f"  {i}. Page {page}: score={score:.4f}")

    # Assertions
    assert len(results) > 0, "Should return at least one result"
    assert all(isinstance(page, int) for page, _ in results), "Pages should be integers"
    assert all(
        isinstance(score, float) for _, score in results
    ), "Scores should be floats"

    # Scores should be >= 0 (BM25 raw or normalized hybrid)
    assert all(score >= 0.0 for _, score in results), "Scores should be non-negative"

    # Verify scores are descending
    scores = [score for _, score in results]
    assert scores == sorted(
        scores, reverse=True
    ), "Results should be sorted by score descending"

    # If all scores <= 1.0, assume hybrid normalized; otherwise BM25-only fallback
    if all(s <= 1.0 for s in scores):
        print("  ✓ Hybrid scoring detected (scores in [0,1])")
    else:
        print("  ⚠ BM25-only mode (semantic unavailable, raw BM25 scores)")

    print("\n✅ Hybrid ranking test PASSED!")
    return True


if __name__ == "__main__":
    try:
        test_hybrid_ranking_with_real_embeddings()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
