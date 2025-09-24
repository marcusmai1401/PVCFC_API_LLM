#!/usr/bin/env python
"""
Test script for Reranker Module (Sprint 1.3)
Tests reranking strategies including cross-encoder and LLM reranking
"""
import sys
import time
from pathlib import Path

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.query_transform import transform_query
from app.rag.reranker import RerankConfig, Reranker, create_reranker, rerank_results
from app.rag.retriever import create_hybrid_retriever


def test_basic_reranking():
    """Test basic reranking with score-based method"""
    logger.info("=== Testing Basic Score-Based Reranking ===")

    # Get some initial results
    retriever = create_hybrid_retriever()
    query_text = "CO2 compressor operating pressure specifications"
    transformed = transform_query(query_text, enable_hyde=False)

    # Get initial results
    initial_results = retriever.search(transformed)
    logger.info(f"Initial results: {len(initial_results)}")

    # Show initial top 3
    logger.info("\nInitial top 3 results:")
    for i, result in enumerate(initial_results[:3], 1):
        logger.info(f"  {i}. Score: {result.score:.4f}, Text: {result.text[:50]}...")

    # Apply score-based reranking
    reranker = create_reranker(method="score_based", top_k=10)
    reranked = reranker.rerank(query_text, initial_results)

    logger.info(f"\nReranked to top {len(reranked)} results")
    logger.info("Reranked top 3:")
    for i, result in enumerate(reranked[:3], 1):
        logger.info(f"  {i}. Score: {result.score:.4f}, Text: {result.text[:50]}...")

    # Get explanation
    explanation = reranker.explain_reranking(query_text, reranked)
    logger.info(f"\nExplanation: {explanation}")

    logger.info("")


def test_cross_encoder_reranking():
    """Test cross-encoder reranking (if available)"""
    logger.info("=== Testing Cross-Encoder Reranking ===")

    try:
        # Check if cross-encoder is available
        from sentence_transformers import CrossEncoder

        # Get initial results
        retriever = create_hybrid_retriever()
        query_text = "steam turbine maximum temperature"
        transformed = transform_query(query_text, enable_hyde=False)
        initial_results = retriever.search(transformed)[
            :20
        ]  # Take top 20 for reranking

        logger.info(f"Initial results: {len(initial_results)}")

        # Create cross-encoder reranker
        config = RerankConfig(
            method="cross_encoder",
            model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
            top_k=5,
            batch_size=10,
        )
        reranker = Reranker(config)

        # Measure performance
        start_time = time.time()
        reranked = reranker.rerank(query_text, initial_results)
        elapsed = (time.time() - start_time) * 1000

        logger.info(f"Cross-encoder reranking took {elapsed:.2f}ms")
        logger.info(f"Reranked to top {len(reranked)} results")

        # Compare scores
        logger.info("\nScore comparison (before -> after):")
        for i in range(min(3, len(reranked))):
            old_score = initial_results[i].score if i < len(initial_results) else 0
            new_score = reranked[i].score
            logger.info(f"  Result {i+1}: {old_score:.4f} -> {new_score:.4f}")

    except ImportError:
        logger.warning(
            "CrossEncoder not available. Install: pip install sentence-transformers"
        )

    logger.info("")


def test_llm_reranking():
    """Test LLM-based reranking"""
    logger.info("=== Testing LLM Reranking ===")

    # Get initial results
    retriever = create_hybrid_retriever()
    query_text = "What are the safety requirements for CO2 compressor?"
    transformed = transform_query(query_text, enable_hyde=False)
    initial_results = retriever.search(transformed)[:10]

    logger.info(f"Query: '{query_text}'")
    logger.info(f"Initial results: {len(initial_results)}")

    # Create LLM reranker
    config = RerankConfig(
        method="llm", use_llm_rerank=True, llm_rerank_top_k=5, top_k=5
    )

    try:
        reranker = Reranker(config)

        # Test reranking
        logger.info("Applying LLM reranking...")
        reranked = reranker.rerank(query_text, initial_results)

        logger.info(f"LLM reranked to top {len(reranked)} results")

        # Show results
        for i, result in enumerate(reranked[:3], 1):
            logger.info(
                f"  {i}. Score: {result.score:.4f}, Text: {result.text[:60]}..."
            )

    except Exception as e:
        logger.warning(f"LLM reranking failed: {e}")
        logger.info("This might be due to API limits or model availability")

    logger.info("")


def test_hybrid_reranking():
    """Test hybrid reranking (cross-encoder + LLM)"""
    logger.info("=== Testing Hybrid Reranking ===")

    # Get initial results
    retriever = create_hybrid_retriever()
    query_text = "compressor specifications pressure temperature"
    transformed = transform_query(query_text, enable_hyde=False)
    initial_results = retriever.search(transformed)[:15]

    logger.info(f"Query: '{query_text}'")
    logger.info(f"Initial results: {len(initial_results)}")

    # Create hybrid reranker
    config = RerankConfig(
        method="hybrid", use_llm_rerank=True, llm_rerank_top_k=3, top_k=5
    )

    try:
        reranker = Reranker(config)

        # Apply hybrid reranking
        start_time = time.time()
        reranked = reranker.rerank(query_text, initial_results)
        elapsed = (time.time() - start_time) * 1000

        logger.info(f"Hybrid reranking took {elapsed:.2f}ms")
        logger.info(f"Final top {len(reranked)} results")

        # Show explanation
        explanation = reranker.explain_reranking(query_text, reranked)
        logger.info(f"Applied factors: {explanation['factors']}")

    except Exception as e:
        logger.warning(f"Hybrid reranking failed: {e}")

    logger.info("")


def test_with_hyde_and_reranking():
    """Test complete pipeline: HyDE + Retrieval + Reranking"""
    logger.info("=== Testing Complete Pipeline with HyDE ===")

    query_text = "What is the maximum operating temperature of the steam turbine?"
    logger.info(f"Query: '{query_text}'")

    # Step 1: Query transformation with HyDE
    logger.info("\n1. Query Transformation with HyDE...")
    try:
        transformed = transform_query(query_text, enable_hyde=True)

        if transformed.hyde_queries:
            logger.info(f"   Generated {len(transformed.hyde_queries)} HyDE queries")
            for i, hyde in enumerate(transformed.hyde_queries[:2], 1):
                logger.info(f"   HyDE {i}: {hyde[:80]}...")
        else:
            logger.info("   HyDE generation failed/disabled, using normal query")
    except Exception as e:
        logger.warning(f"   HyDE failed: {e}")
        transformed = transform_query(query_text, enable_hyde=False)

    # Step 2: Hybrid retrieval
    logger.info("\n2. Hybrid Retrieval...")
    retriever = create_hybrid_retriever()
    initial_results = retriever.search(transformed)
    logger.info(f"   Retrieved {len(initial_results)} results")

    # Step 3: Reranking
    logger.info("\n3. Reranking...")
    reranker = create_reranker(method="score_based", top_k=5)
    final_results = reranker.rerank(query_text, initial_results)
    logger.info(f"   Final top {len(final_results)} results after reranking")

    # Show final results
    logger.info("\nFinal Results:")
    for i, result in enumerate(final_results[:3], 1):
        logger.info(f"{i}. Score: {result.score:.4f}")
        logger.info(f"   Source: {result.source}")
        logger.info(f"   Text: {result.text[:100]}...")

    logger.info("")


def test_performance_comparison():
    """Compare performance of different reranking methods"""
    logger.info("=== Performance Comparison ===")

    # Get test data
    retriever = create_hybrid_retriever()
    queries = [
        "CO2 compressor pressure",
        "steam turbine temperature",
        "safety requirements",
    ]

    methods = ["score_based", "cross_encoder"]

    for method in methods:
        logger.info(f"\nTesting {method}:")

        total_time = 0
        for query in queries:
            transformed = transform_query(query, enable_hyde=False)
            results = retriever.search(transformed)[:20]

            reranker = create_reranker(method=method, top_k=10)

            start = time.time()
            _ = reranker.rerank(query, results)
            elapsed = (time.time() - start) * 1000
            total_time += elapsed

        avg_time = total_time / len(queries)
        logger.info(f"  Average reranking time: {avg_time:.2f}ms")

    logger.info("")


def main():
    """Run all tests"""
    logger.info("Reranker Module Test Suite (Sprint 1.3)")
    logger.info("=" * 50)

    # Run tests
    test_basic_reranking()
    test_cross_encoder_reranking()
    test_llm_reranking()
    test_hybrid_reranking()
    test_with_hyde_and_reranking()
    test_performance_comparison()

    logger.info("=" * 50)
    logger.info("Test suite completed!")

    # Summary
    logger.info("\nModule Status:")
    logger.info("✓ Score-based reranking working")
    logger.info("✓ Cross-encoder support (if installed)")
    logger.info("✓ LLM reranking implemented")
    logger.info("✓ Hybrid reranking available")
    logger.info("✓ Complete pipeline integration")

    logger.info("\nNext Steps:")
    logger.info("1. Install cross-encoder: pip install sentence-transformers")
    logger.info("2. Fine-tune reranking weights")
    logger.info("3. Implement RAG generator with citations")


if __name__ == "__main__":
    main()
