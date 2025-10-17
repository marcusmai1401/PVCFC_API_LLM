"""Unit test for RRF merge functionality"""
import sys

sys.path.insert(0, ".")

from app.rag.page_first_agent import PageFirstAgent
from app.rag.page_first_config import PageFirstConfig


def test_rrf_merge():
    """Test RRF merging with mock hits"""
    print("=== Testing RRF Merge ===\n")

    config = PageFirstConfig(MERGED_K=5, RERANK_KEEP=5)
    agent = PageFirstAgent(config)

    # Mock BM25 hits
    bm25_hits = [
        {"doc_id": "doc1", "page": 1, "score": 10.0, "text": "text1"},
        {"doc_id": "doc1", "page": 2, "score": 8.0, "text": "text2"},
        {"doc_id": "doc2", "page": 1, "score": 7.0, "text": "text3"},
    ]

    # Mock vector hits (some overlap)
    vec_hits = [
        {"doc_id": "doc1", "page": 1, "score": 0.95, "text": "text1"},  # Overlap
        {"doc_id": "doc3", "page": 1, "score": 0.90, "text": "text4"},
        {"doc_id": "doc2", "page": 2, "score": 0.85, "text": "text5"},
    ]

    # Merge
    print(f"BM25 hits: {len(bm25_hits)}")
    print(f"Vector hits: {len(vec_hits)}")

    merged = agent.rrf_merge(bm25_hits, vec_hits)

    print(f"\nMerged: {len(merged)} unique pages")
    print("\nTop merged pages:")
    for i, page in enumerate(merged, 1):
        print(
            f"  {i}. {page['doc_id']} page {page['page']} "
            f"(fused={page['fused_score']:.4f}, "
            f"bm25={page.get('bm25_score', 0):.2f}, "
            f"vec={page.get('vec_score', 0):.2f})"
        )

    # Assertions
    assert len(merged) <= 5, "Should respect MERGED_K limit"
    print("\n✓ Respects MERGED_K limit")

    assert (
        merged[0]["doc_id"] == "doc1"
    ), "Doc1 Page1 should rank highest (in both lists)"
    assert merged[0]["page"] == 1
    print("✓ Doc1 Page1 ranks highest (appears in both lists)")

    assert "fused_score" in merged[0], "Should have fused_score"
    assert merged[0]["fused_score"] > 0, "Fused score should be positive"
    print("✓ Has valid fused_score")

    # Check deduplication
    keys = [(h["doc_id"], h["page"]) for h in merged]
    assert len(keys) == len(set(keys)), "Should have no duplicate (doc_id, page)"
    print("✓ No duplicate pages")

    # Check descending order
    scores = [m["fused_score"] for m in merged]
    assert scores == sorted(
        scores, reverse=True
    ), "Should be sorted by score descending"
    print("✓ Sorted by fused_score descending")

    print("\n✓✓✓ All RRF merge tests PASSED ✓✓✓")
    return True


if __name__ == "__main__":
    try:
        test_rrf_merge()
    except AssertionError as e:
        print(f"\n✗ Test FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
