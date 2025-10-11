"""
Phase 4 RAG Integration Test with BGE Reranker

Tests the full RAG pipeline with BGE reranking:
1. Retrieval with/without reranking
2. Latency benchmarks
3. Relevance comparison
4. End-to-end validation
"""
import sys
import time
from pathlib import Path
from typing import Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os

from loguru import logger

from app.rag.query_transform import QueryFilters, TransformedQuery
from app.rag.retriever import HybridRetriever, HybridSearchConfig

# Set environment for testing
os.environ["ENABLE_BGE_RERANK"] = "true"
os.environ["BGE_RERANK_TOP_K"] = "10"
os.environ["BGE_RERANK_LEVEL"] = "chunk"


def test_retrieval_with_without_rerank():
    """Test 1: Compare retrieval with and without BGE reranking"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: Retrieval With/Without BGE Reranking")
    logger.info("=" * 70)

    try:
        # Initialize retriever with default indices
        retriever = HybridRetriever(
            bm25_index_dir="artifacts/index_production/bm25",
            faiss_index_dir="artifacts/index_production/faiss",
            config=HybridSearchConfig(
                k_bm25=30,
                k_faiss=30,
                top_rrf=50,  # Higher to allow reranking
            ),
        )

        query = "CO2 compressor discharge pressure control specifications"
        transformed_query = TransformedQuery(
            original=query,
            normalized=query,
            intent="technical_query",
            filters=QueryFilters(),
            hyde_queries=[],
        )

        # Test WITHOUT reranking
        logger.info("\n--- WITHOUT BGE Reranking ---")
        os.environ["ENABLE_BGE_RERANK"] = "false"

        start = time.time()
        results_no_rerank = retriever.search(transformed_query)
        time_no_rerank = time.time() - start

        logger.info(f"Results: {len(results_no_rerank)}")
        logger.info(f"Time: {time_no_rerank:.2f}s")
        logger.info("Top 5 results:")
        for i, r in enumerate(results_no_rerank[:5], 1):
            logger.info(
                f"  [{i}] Score: {r.score:.4f} | Source: {r.source} | {r.text[:80]}..."
            )

        # Test WITH reranking
        logger.info("\n--- WITH BGE Reranking ---")
        os.environ["ENABLE_BGE_RERANK"] = "true"

        start = time.time()
        results_with_rerank = retriever.search(transformed_query)
        time_with_rerank = time.time() - start

        logger.info(f"Results: {len(results_with_rerank)}")
        logger.info(f"Time: {time_with_rerank:.2f}s")
        logger.info("Top 5 results:")
        for i, r in enumerate(results_with_rerank[:5], 1):
            metadata = r.metadata or {}
            bge_score = metadata.get("bge_rerank_score", "N/A")
            logger.info(
                f"  [{i}] Score: {r.score:.4f} (BGE: {bge_score}) | Source: {r.source} | {r.text[:80]}..."
            )

        # Validation
        assert len(results_no_rerank) > 0, "No results without reranking"
        assert len(results_with_rerank) > 0, "No results with reranking"

        # Check that reranking changed the order
        top5_no_rerank = [r.chunk_id for r in results_no_rerank[:5]]
        top5_with_rerank = [r.chunk_id for r in results_with_rerank[:5]]

        if top5_no_rerank == top5_with_rerank:
            logger.warning(
                "⚠️ Reranking did not change top-5 order (may happen with very relevant results)"
            )
        else:
            logger.info("✓ Reranking changed result ordering")

        # Performance comparison
        overhead = time_with_rerank - time_no_rerank
        logger.info(f"\n📊 Performance:")
        logger.info(f"  Without rerank: {time_no_rerank:.2f}s")
        logger.info(f"  With rerank:    {time_with_rerank:.2f}s")
        logger.info(
            f"  Overhead:       {overhead:.2f}s ({overhead/time_no_rerank*100:.1f}%)"
        )

        logger.info("\n✅ TEST 1 PASSED")
        return True

    except Exception as e:
        logger.error(f"\n❌ TEST 1 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_doc_level_reranking():
    """Test 2: Document-level reranking"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Document-Level Reranking")
    logger.info("=" * 70)

    try:
        os.environ["ENABLE_BGE_RERANK"] = "true"
        os.environ["BGE_RERANK_LEVEL"] = "doc"
        os.environ["BGE_RERANK_AGGREGATION"] = "max"
        os.environ["BGE_RERANK_TOP_K"] = "5"

        retriever = HybridRetriever(
            bm25_index_dir="artifacts/index_production/bm25",
            faiss_index_dir="artifacts/index_production/faiss",
            config=HybridSearchConfig(k_bm25=30, k_faiss=30, top_rrf=40),
        )

        query = "turbine vibration analysis procedures"
        transformed_query = TransformedQuery(
            original=query,
            normalized=query,
            intent="technical_query",
            filters=QueryFilters(),
            hyde_queries=[],
        )

        start = time.time()
        results = retriever.search(transformed_query)
        elapsed = time.time() - start

        logger.info(f"Results: {len(results)}")
        logger.info(f"Time: {elapsed:.2f}s")

        # Check doc-level metadata
        unique_docs = set()
        for r in results:
            unique_docs.add(r.doc_id)
            metadata = r.metadata or {}
            if "bge_doc_score" in metadata:
                logger.info(
                    f"  Doc: {r.doc_id[:40]}... | "
                    f"Doc Score: {metadata['bge_doc_score']:.4f} | "
                    f"Source: {r.source}"
                )

        logger.info(f"\nUnique documents: {len(unique_docs)}")

        assert len(results) > 0, "No results"
        assert any(
            "bge_doc_score" in (r.metadata or {}) for r in results
        ), "Missing doc-level scores"

        logger.info("\n✅ TEST 2 PASSED")
        return True

    except Exception as e:
        logger.error(f"\n❌ TEST 2 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_page_level_reranking():
    """Test 3: Page-level reranking"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Page-Level Reranking")
    logger.info("=" * 70)

    try:
        os.environ["ENABLE_BGE_RERANK"] = "true"
        os.environ["BGE_RERANK_LEVEL"] = "page"
        os.environ["BGE_RERANK_AGGREGATION"] = "max"
        os.environ["BGE_RERANK_TOP_K"] = "10"

        retriever = HybridRetriever(
            bm25_index_dir="artifacts/index_production/bm25",
            faiss_index_dir="artifacts/index_production/faiss",
            config=HybridSearchConfig(k_bm25=30, k_faiss=30, top_rrf=40),
        )

        query = "safety shutdown emergency procedures"
        transformed_query = TransformedQuery(
            original=query,
            normalized=query,
            intent="technical_query",
            filters=QueryFilters(),
            hyde_queries=[],
        )

        start = time.time()
        results = retriever.search(transformed_query)
        elapsed = time.time() - start

        logger.info(f"Results: {len(results)}")
        logger.info(f"Time: {elapsed:.2f}s")

        # Check page-level metadata
        unique_pages = set()
        for r in results[:10]:
            unique_pages.add((r.doc_id, r.page))
            metadata = r.metadata or {}
            if "bge_page_score" in metadata:
                logger.info(
                    f"  Doc: {r.doc_id[:30]}... | Page: {r.page} | "
                    f"Page Score: {metadata['bge_page_score']:.4f}"
                )

        logger.info(f"\nUnique pages: {len(unique_pages)}")

        assert len(results) > 0, "No results"
        assert any(
            "bge_page_score" in (r.metadata or {}) for r in results
        ), "Missing page-level scores"

        logger.info("\n✅ TEST 3 PASSED")
        return True

    except Exception as e:
        logger.error(f"\n❌ TEST 3 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def benchmark_latency():
    """Test 4: Latency benchmark with different configurations"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Latency Benchmark")
    logger.info("=" * 70)

    try:
        retriever = HybridRetriever(
            bm25_index_dir="artifacts/index_production/bm25",
            faiss_index_dir="artifacts/index_production/faiss",
            config=HybridSearchConfig(k_bm25=30, k_faiss=30, top_rrf=50),
        )

        queries = [
            "compressor discharge pressure",
            "turbine vibration monitoring",
            "safety relief valve settings",
        ]

        configs = [
            ("No Rerank", {"ENABLE_BGE_RERANK": "false"}),
            (
                "Chunk Rerank",
                {"ENABLE_BGE_RERANK": "true", "BGE_RERANK_LEVEL": "chunk"},
            ),
            ("Doc Rerank", {"ENABLE_BGE_RERANK": "true", "BGE_RERANK_LEVEL": "doc"}),
        ]

        results_table = []

        for config_name, env_vars in configs:
            logger.info(f"\n--- {config_name} ---")

            # Set env
            for key, value in env_vars.items():
                os.environ[key] = value

            times = []
            for query in queries:
                transformed_query = TransformedQuery(
                    original=query,
                    normalized=query,
                    intent="technical_query",
                    filters=QueryFilters(),
                    hyde_queries=[],
                )

                start = time.time()
                results = retriever.search(transformed_query)
                elapsed = time.time() - start
                times.append(elapsed)

                logger.info(
                    f"  Query: {query[:40]}... | Time: {elapsed:.2f}s | Results: {len(results)}"
                )

            avg_time = sum(times) / len(times)
            results_table.append((config_name, avg_time, times))
            logger.info(f"  Average: {avg_time:.2f}s")

        # Summary table
        logger.info("\n📊 Benchmark Summary:")
        logger.info(
            f"{'Configuration':<15} | {'Avg Time':<10} | {'Min':<8} | {'Max':<8}"
        )
        logger.info("-" * 50)
        for config_name, avg_time, times in results_table:
            logger.info(
                f"{config_name:<15} | {avg_time:>8.2f}s | {min(times):>6.2f}s | {max(times):>6.2f}s"
            )

        logger.info("\n✅ TEST 4 PASSED")
        return True

    except Exception as e:
        logger.error(f"\n❌ TEST 4 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all Phase 4 integration tests"""
    logger.info("=" * 70)
    logger.info("PHASE 4: RAG INTEGRATION & BENCHMARK TESTS")
    logger.info("=" * 70)

    results = {
        "Test 1: Retrieval With/Without Rerank": test_retrieval_with_without_rerank(),
        "Test 2: Document-Level Reranking": test_doc_level_reranking(),
        "Test 3: Page-Level Reranking": test_page_level_reranking(),
        "Test 4: Latency Benchmark": benchmark_latency(),
    }

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)

    passed = sum(results.values())
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        logger.info(f"{status} | {test_name}")

    logger.info("\n" + "=" * 70)
    logger.info(f"RESULT: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 ALL TESTS PASSED! Phase 4 RAG integration is ready!")
    else:
        logger.warning(f"⚠️ {total - passed} test(s) failed. Review logs above.")

    logger.info("=" * 70)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
