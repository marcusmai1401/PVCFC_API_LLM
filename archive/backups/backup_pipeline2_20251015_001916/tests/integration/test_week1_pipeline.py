"""Integration test for Week 1 pipeline: Retrieval + Reranking (Steps B, C, D)

Tests the full pipeline from query input through reranking output using real artifacts.
"""
import sys

sys.path.insert(0, ".")

import os
from pathlib import Path

from app.rag.page_first_agent import PageFirstAgent
from app.rag.page_first_config import PageFirstConfig


def test_week1_pipeline():
    """Test full Week 1 pipeline with real artifacts"""
    print("=== Week 1 Pipeline Integration Test ===\n")

    # Verify artifacts exist
    artifacts_dir = Path("artifacts/ingestion_production")
    required_files = [
        "text_by_page.jsonl",
        "page_bm25_index.pkl",
        "page_embeddings.npz",
        "page_metadata.json",
        "doc_id_map.json",
    ]

    print("Checking artifacts...")
    for fname in required_files:
        fpath = artifacts_dir / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Required artifact missing: {fpath}")
        print(f"  ✓ {fname}")
    print()

    # Initialize config with test parameters
    config = PageFirstConfig(
        TOPK_BM25=10,
        TOPK_VEC=10,
        MERGED_K=15,
        RERANK_KEEP=5,
        NEIGHBOR_RADIUS=1,
        CTX_MAX_TOKENS=3000,
        ANSWER_MAX_TOKENS=400,
        NLI_THRESHOLD=0.6,
        FUZZY_MIN=0.7,
    )

    print("Initializing PageFirstAgent...")
    agent = PageFirstAgent(config)
    print("✓ Agent initialized\n")

    # Test query
    test_query = "Quy định về bảo hiểm xã hội là gì?"
    print(f"Test Query: '{test_query}'\n")

    # Step A: Normalize query
    print("Step A: Normalizing query...")
    normalized_query = agent.normalize_query(test_query)
    print(f"  Normalized: '{normalized_query}'")
    assert normalized_query, "Normalized query should not be empty"
    print("  ✓ Query normalized\n")

    # Step B: Retrieve pages (BM25 + Vector)
    print("Step B: Retrieving pages...")
    bm25_hits, vec_hits = agent.search_pages_hybrid(normalized_query)
    print(f"  BM25 hits: {len(bm25_hits)}")
    print(f"  Vector hits: {len(vec_hits)}")

    assert (
        len(bm25_hits) > 0 or len(vec_hits) > 0
    ), "At least one retrieval method should return results"
    if len(bm25_hits) > 0:
        assert (
            len(bm25_hits) <= config.TOPK_BM25
        ), "BM25 results should respect TOPK_BM25"
        print(f"  ✓ BM25 retrieval working")
    if len(vec_hits) > 0:
        assert (
            len(vec_hits) <= config.TOPK_VEC
        ), "Vector results should respect TOPK_VEC"
        print(f"  ✓ Vector retrieval working")

    # Check structure (if we have results)
    if len(bm25_hits) > 0:
        for hit in bm25_hits[:1]:
            assert "doc_id" in hit, "Hit should have doc_id"
            assert "page" in hit, "Hit should have page"
            assert "score" in hit, "Hit should have score"
            assert "text" in hit, "Hit should have text"

    print()

    # Step C: RRF Merge
    print("Step C: Merging with RRF...")
    merged_hits = agent.rrf_merge(bm25_hits, vec_hits)
    print(f"  Merged: {len(merged_hits)} unique pages")

    assert len(merged_hits) > 0, "Merged should have results"
    assert len(merged_hits) <= config.MERGED_K, "Merged should respect MERGED_K"

    # Check deduplication
    keys = [(h["doc_id"], h["page"]) for h in merged_hits]
    assert len(keys) == len(set(keys)), "No duplicate pages"

    # Check fused_score
    assert "fused_score" in merged_hits[0], "Should have fused_score"
    scores = [h["fused_score"] for h in merged_hits]
    assert scores == sorted(scores, reverse=True), "Should be sorted descending"

    print(f"  Top 3 merged pages:")
    for i, hit in enumerate(merged_hits[:3], 1):
        print(
            f"    {i}. {hit['doc_id']} p{hit['page']} "
            f"(fused={hit['fused_score']:.4f})"
        )
    print("  ✓ RRF merge working\n")

    # Step D: Rerank
    print("Step D: Reranking with cross-encoder...")
    reranked_hits = agent.cross_encoder_rerank(normalized_query, merged_hits)
    print(f"  Reranked: {len(reranked_hits)} pages")

    assert len(reranked_hits) > 0, "Reranked should have results"
    assert (
        len(reranked_hits) <= config.RERANK_KEEP
    ), "Reranked should respect RERANK_KEEP"

    # Check rerank_score
    assert "rerank_score" in reranked_hits[0], "Should have rerank_score"
    rerank_scores = [h["rerank_score"] for h in reranked_hits]
    assert rerank_scores == sorted(
        rerank_scores, reverse=True
    ), "Should be sorted by rerank_score descending"

    print(f"  Top 3 reranked pages:")
    for i, hit in enumerate(reranked_hits[:3], 1):
        print(
            f"    {i}. {hit['doc_id']} p{hit['page']} "
            f"(rerank={hit['rerank_score']:.4f})"
        )
    print("  ✓ Reranking working\n")

    # Verify quality
    print("Quality checks:")

    # Check text content exists
    for hit in reranked_hits:
        assert len(hit["text"]) > 0, "Text should not be empty"
        assert isinstance(hit["text"], str), "Text should be string"
    print("  ✓ All pages have valid text content")

    # Check score ranges
    for hit in reranked_hits:
        # Rerank scores can be negative (cross-encoder logits)
        assert isinstance(hit["rerank_score"], float), "Rerank score should be float"
    print("  ✓ All scores have valid types")

    # Check uniqueness in final output
    final_keys = [(h["doc_id"], h["page"]) for h in reranked_hits]
    assert len(final_keys) == len(
        set(final_keys)
    ), "Final output should have no duplicates"
    print("  ✓ No duplicate pages in final output")

    print("\n" + "=" * 60)
    print("✓✓✓ Week 1 Pipeline Integration Test PASSED ✓✓✓")
    print("=" * 60)
    print("\nPipeline Summary:")
    print(f"  Query: '{test_query}'")
    print(f"  BM25 hits: {len(bm25_hits)}")
    print(f"  Vector hits: {len(vec_hits)}")
    print(f"  Merged (RRF): {len(merged_hits)}")
    print(f"  Reranked (Final): {len(reranked_hits)}")
    print("\nTop 5 Final Pages:")
    for i, hit in enumerate(reranked_hits[:5], 1):
        preview = hit["text"][:100].replace("\n", " ")
        print(f"  {i}. {hit['doc_id']} page {hit['page']}")
        print(f"     Score: {hit['rerank_score']:.4f}")
        print(f"     Preview: {preview}...")
        print()

    return True


if __name__ == "__main__":
    try:
        test_week1_pipeline()
    except AssertionError as e:
        print(f"\n✗ Test FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
