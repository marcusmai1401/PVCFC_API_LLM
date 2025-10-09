"""End-to-end test for full Page-First RAG Agent pipeline

Tests the complete flow from question to answer with citations.
"""
import sys

sys.path.insert(0, ".")

import os
from pathlib import Path

from app.rag.page_first_agent import PageFirstAgent
from app.rag.page_first_config import PageFirstConfig


def test_full_pipeline():
    """Test complete end-to-end pipeline"""
    print("=== Full Pipeline End-to-End Test ===\n")

    # Check environment
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠ OPENAI_API_KEY not set, test will fail at LLM step")
        print("Set it with: export OPENAI_API_KEY=your_key")
        return False

    # Verify artifacts
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

    # Initialize config
    config = PageFirstConfig(
        TOPK_BM25=10,
        TOPK_VEC=10,
        MERGED_K=15,
        RERANK_KEEP=5,
        NEIGHBOR_RADIUS=1,
        CTX_MAX_TOKENS=3000,
        ANSWER_MAX_TOKENS=400,
        NLI_THRESHOLD=0.6,
        FUZZY_MIN=0.55,
    )

    print("Initializing PageFirstAgent...")
    agent = PageFirstAgent(config)
    print("✓ Agent initialized\n")

    # Test question
    test_question = "Quy định về áp suất tối đa cho turbine là gì?"
    print(f"Test Question: '{test_question}'\n")

    # Call full pipeline
    print("Running full pipeline (Steps A-G)...")
    print("-" * 60)

    result = agent.answer(test_question)

    print("-" * 60)
    print("\n=== RESULT ===\n")

    # Validate result structure
    assert "answer" in result, "Result should have 'answer'"
    assert "citations" in result, "Result should have 'citations'"
    assert "metrics" in result, "Result should have 'metrics'"
    assert "language" in result, "Result should have 'language'"
    assert "retrieval_info" in result, "Result should have 'retrieval_info'"
    print("✓ Result structure valid")

    # Print answer
    answer = result["answer"]
    print(f"\nAnswer ({len(answer)} chars):")
    print(f"  {answer[:200]}..." if len(answer) > 200 else f"  {answer}")

    # Print citations
    citations = result["citations"]
    print(f"\nCitations: {len(citations)}")
    for i, cite in enumerate(citations[:3], 1):  # Show first 3
        print(f"  {i}. Doc: {cite.get('doc_id', 'N/A')[:50]}...")
        print(f"     Page: {cite.get('page', 'N/A')}")
        print(f"     Confidence: {cite.get('confidence', 0):.3f}")
        print(f"     Fixed: {cite.get('fixed', False)}")
        quote = cite.get("quote", "")
        print(
            f"     Quote: {quote[:80]}..."
            if len(quote) > 80
            else f"     Quote: {quote}"
        )
        print()

    # Print metrics
    metrics = result["metrics"]
    print("Metrics:")
    print(f"  Groundedness: {metrics.get('groundedness_est', 0):.3f}")
    print(f"  Coverage: {metrics.get('coverage_est', 0):.3f}")
    print(f"  Latency: {metrics.get('latency_ms', 0)}ms")

    # Print retrieval info
    retrieval_info = result["retrieval_info"]
    print("\nRetrieval Info:")
    print(f"  BM25 hits: {retrieval_info.get('bm25_hits', 0)}")
    print(f"  Vector hits: {retrieval_info.get('vector_hits', 0)}")
    print(f"  Merged: {retrieval_info.get('merged_hits', 0)}")
    print(f"  Reranked: {retrieval_info.get('reranked_hits', 0)}")

    llm_usage = retrieval_info.get("llm_usage", {})
    if llm_usage:
        print(
            f"  LLM tokens: {llm_usage.get('total_tokens', 0)} (latency: {llm_usage.get('latency_ms', 0):.0f}ms)"
        )

    # Language detection
    language = result["language"]
    print(f"\nDetected Language: {language}")
    assert language in ["vi", "en"], "Language should be 'vi' or 'en'"
    print("✓ Language detection valid")

    # Quality checks
    print("\n=== Quality Checks ===")

    # Check if answer is not empty
    assert len(answer) > 0, "Answer should not be empty"
    print("✓ Answer is not empty")

    # Check if citations have required fields
    for cite in citations:
        assert "doc_id" in cite, "Citation should have doc_id"
        assert "page" in cite, "Citation should have page"
        assert "confidence" in cite, "Citation should have confidence"
    print(f"✓ All {len(citations)} citations have required fields")

    # Check if metrics are in valid ranges
    assert (
        0 <= metrics.get("groundedness_est", 0) <= 1
    ), "Groundedness should be in [0, 1]"
    assert 0 <= metrics.get("coverage_est", 0) <= 1, "Coverage should be in [0, 1]"
    assert metrics.get("latency_ms", 0) > 0, "Latency should be positive"
    print("✓ Metrics in valid ranges")

    # Check retrieval funnel
    bm25 = retrieval_info.get("bm25_hits", 0)
    vec = retrieval_info.get("vector_hits", 0)
    merged = retrieval_info.get("merged_hits", 0)
    reranked = retrieval_info.get("reranked_hits", 0)

    assert merged <= (bm25 + vec), "Merged should be <= BM25 + Vector"
    assert reranked <= merged, "Reranked should be <= Merged"
    print("✓ Retrieval funnel valid")

    print("\n" + "=" * 60)
    print("✓✓✓ Full Pipeline End-to-End Test PASSED ✓✓✓")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        test_full_pipeline()
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
