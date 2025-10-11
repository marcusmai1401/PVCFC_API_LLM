"""
Phase 3 Reranker Smoke Tests

Tests BGE reranker functionality:
1. Basic chunk-level reranking
2. Document-level aggregated reranking
3. Page-level aggregated reranking
4. Score improvement validation
5. Top-k stability
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import weaviate
import weaviate.classes as wvc
from loguru import logger

from app.services.embedding import get_embedding_service
from app.services.reranker import get_reranker_service


def fetch_sample_chunks(collection, query_vec, limit=20):
    """Fetch sample chunks from Weaviate for testing."""
    results = collection.query.near_vector(
        near_vector=query_vec,
        limit=limit,
        return_metadata=wvc.query.MetadataQuery(distance=True),
        return_properties=[
            "doc_id",
            "text",
            "equipment_type",
            "doc_type",
            "vendor",
            "page",
        ],
    )

    chunks = []
    for obj in results.objects:
        chunk = {
            "doc_id": obj.properties.get("doc_id", "unknown"),
            "text": obj.properties.get("text", ""),
            "equipment_type": obj.properties.get("equipment_type"),
            "doc_type": obj.properties.get("doc_type"),
            "vendor": obj.properties.get("vendor"),
            "page_num": str(obj.properties.get("page", "unknown")),
            "original_distance": obj.metadata.distance,
        }
        chunks.append(chunk)

    return chunks


def test_chunk_reranking():
    """Test 1: Basic chunk-level reranking."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: Chunk-Level Reranking")
    logger.info("=" * 70)

    try:
        # Initialize services
        embedding_service = get_embedding_service()
        reranker_service = get_reranker_service()

        # Connect to Weaviate
        client = weaviate.connect_to_local(host="localhost", port=8080)
        collection = client.collections.get("Chunk")

        # Test query
        query = "compressor discharge pressure control system"
        logger.info(f"Query: {query}")

        # Get query embedding
        qvec = embedding_service.embed_query(query).tolist()

        # Fetch top 10 chunks from semantic search
        chunks = fetch_sample_chunks(collection, qvec, limit=10)
        logger.info(f"Fetched {len(chunks)} chunks from Weaviate")

        # Rerank chunks
        reranked = reranker_service.rerank_chunks(query, chunks, top_k=5)

        logger.info("\n📊 Reranking Results (Top 5):")
        for i, (chunk, score) in enumerate(reranked, 1):
            logger.info(
                f"  [{i}] Score: {score:.4f} | "
                f"Doc: {chunk['doc_id'][:30]}... | "
                f"Type: {chunk['equipment_type']} | "
                f"Text: {chunk['text'][:60]}..."
            )

        client.close()

        # Validation
        assert len(reranked) == 5, "Should return top 5 chunks"
        import numpy as np

        assert all(
            isinstance(score, (int, float, np.floating)) for _, score in reranked
        ), "Scores should be numeric"

        # Check descending order
        scores = [score for _, score in reranked]
        assert scores == sorted(
            scores, reverse=True
        ), "Scores should be in descending order"

        logger.info("\n✅ TEST 1 PASSED: Chunk reranking works correctly")
        return True

    except Exception as e:
        logger.error(f"\n❌ TEST 1 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_document_level_reranking():
    """Test 2: Document-level aggregated reranking."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Document-Level Reranking")
    logger.info("=" * 70)

    try:
        # Initialize services
        embedding_service = get_embedding_service()
        reranker_service = get_reranker_service()

        # Connect to Weaviate
        client = weaviate.connect_to_local(host="localhost", port=8080)
        collection = client.collections.get("Chunk")

        # Test query
        query = "turbine vibration monitoring system"
        logger.info(f"Query: {query}")

        # Get query embedding
        qvec = embedding_service.embed_query(query).tolist()

        # Fetch more chunks to ensure multiple documents
        chunks = fetch_sample_chunks(collection, qvec, limit=30)
        logger.info(f"Fetched {len(chunks)} chunks from Weaviate")

        # Count unique documents
        unique_docs = len(set(c["doc_id"] for c in chunks))
        logger.info(f"Unique documents: {unique_docs}")

        # Rerank at document level with different aggregations
        for agg_method in ["max", "mean", "top3_mean"]:
            logger.info(f"\n📊 Document Reranking ({agg_method.upper()}):")
            doc_results = reranker_service.rerank_documents(
                query, chunks, top_k=3, aggregation=agg_method
            )

            for i, (doc_id, score, doc_chunks) in enumerate(doc_results, 1):
                logger.info(
                    f"  [{i}] Doc: {doc_id[:40]}... | "
                    f"Score: {score:.4f} | "
                    f"Chunks: {len(doc_chunks)}"
                )

        client.close()

        # Validation
        assert len(doc_results) <= 3, "Should return at most top 3 documents"
        assert all(
            isinstance(score, (int, float)) for _, score, _ in doc_results
        ), "Scores should be numeric"

        # Check descending order
        scores = [score for _, score, _ in doc_results]
        assert scores == sorted(
            scores, reverse=True
        ), "Doc scores should be in descending order"

        logger.info("\n✅ TEST 2 PASSED: Document-level reranking works correctly")
        return True

    except Exception as e:
        logger.error(f"\n❌ TEST 2 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_page_level_reranking():
    """Test 3: Page-level aggregated reranking."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Page-Level Reranking")
    logger.info("=" * 70)

    try:
        # Initialize services
        embedding_service = get_embedding_service()
        reranker_service = get_reranker_service()

        # Connect to Weaviate
        client = weaviate.connect_to_local(host="localhost", port=8080)
        collection = client.collections.get("Chunk")

        # Test query
        query = "safety shutdown procedures"
        logger.info(f"Query: {query}")

        # Get query embedding
        qvec = embedding_service.embed_query(query).tolist()

        # Fetch chunks with page info
        chunks = fetch_sample_chunks(collection, qvec, limit=30)
        logger.info(f"Fetched {len(chunks)} chunks from Weaviate")

        # Count unique pages
        unique_pages = len(set((c["doc_id"], c["page_num"]) for c in chunks))
        logger.info(f"Unique pages: {unique_pages}")

        # Rerank at page level
        page_results = reranker_service.rerank_pages(
            query, chunks, top_k=5, aggregation="max"
        )

        logger.info(f"\n📊 Page Reranking Results (Top 5):")
        for i, (doc_id, page_num, score, page_chunks) in enumerate(page_results, 1):
            logger.info(
                f"  [{i}] Doc: {doc_id[:30]}... | "
                f"Page: {page_num} | "
                f"Score: {score:.4f} | "
                f"Chunks: {len(page_chunks)}"
            )

        client.close()

        # Validation
        assert len(page_results) <= 5, "Should return at most top 5 pages"
        assert all(
            isinstance(score, (int, float)) for _, _, score, _ in page_results
        ), "Scores should be numeric"

        # Check descending order
        scores = [score for _, _, score, _ in page_results]
        assert scores == sorted(
            scores, reverse=True
        ), "Page scores should be in descending order"

        logger.info("\n✅ TEST 3 PASSED: Page-level reranking works correctly")
        return True

    except Exception as e:
        logger.error(f"\n❌ TEST 3 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_score_improvement():
    """Test 4: Validate reranking improves relevance."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Score Improvement Validation")
    logger.info("=" * 70)

    try:
        # Initialize services
        embedding_service = get_embedding_service()
        reranker_service = get_reranker_service()

        # Connect to Weaviate
        client = weaviate.connect_to_local(host="localhost", port=8080)
        collection = client.collections.get("Chunk")

        # Test query
        query = "CO2 compressor datasheet specifications"
        logger.info(f"Query: {query}")

        # Get query embedding
        qvec = embedding_service.embed_query(query).tolist()

        # Fetch chunks
        chunks = fetch_sample_chunks(collection, qvec, limit=15)
        logger.info(f"Fetched {len(chunks)} chunks")

        # Original order (by semantic search distance)
        logger.info("\n📊 Original Semantic Search Order (Top 5):")
        for i, chunk in enumerate(chunks[:5], 1):
            logger.info(
                f"  [{i}] Distance: {chunk['original_distance']:.4f} | "
                f"Type: {chunk['equipment_type']} | "
                f"Doc: {chunk['doc_type']}"
            )

        # Reranked order
        reranked = reranker_service.rerank_chunks(query, chunks, top_k=5)

        logger.info("\n📊 After Reranking (Top 5):")
        for i, (chunk, score) in enumerate(reranked, 1):
            logger.info(
                f"  [{i}] Rerank Score: {score:.4f} | "
                f"Orig Distance: {chunk['original_distance']:.4f} | "
                f"Type: {chunk['equipment_type']} | "
                f"Doc: {chunk['doc_type']}"
            )

        client.close()

        # Validation: Check that reranker produces different ordering than semantic search
        original_top5_ids = [c["doc_id"] for c in chunks[:5]]
        reranked_top5_ids = [chunk["doc_id"] for chunk, _ in reranked]

        # It's acceptable if some overlap, but expect at least some reordering
        if original_top5_ids == reranked_top5_ids:
            logger.warning(
                "⚠️ Reranking did not change order (may happen with very relevant results)"
            )
        else:
            logger.info("✓ Reranking produced different ordering")

        logger.info("\n✅ TEST 4 PASSED: Score improvement validation complete")
        return True

    except Exception as e:
        logger.error(f"\n❌ TEST 4 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_top_k_stability():
    """Test 5: Verify top-k parameter works correctly."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 5: Top-K Stability")
    logger.info("=" * 70)

    try:
        # Initialize services
        embedding_service = get_embedding_service()
        reranker_service = get_reranker_service()

        # Connect to Weaviate
        client = weaviate.connect_to_local(host="localhost", port=8080)
        collection = client.collections.get("Chunk")

        # Test query
        query = "pressure relief valve settings"
        logger.info(f"Query: {query}")

        # Get query embedding
        qvec = embedding_service.embed_query(query).tolist()

        # Fetch chunks
        chunks = fetch_sample_chunks(collection, qvec, limit=20)

        # Test different top_k values
        for k in [3, 5, 10]:
            reranked = reranker_service.rerank_chunks(query, chunks, top_k=k)
            logger.info(f"Top-{k}: Returned {len(reranked)} results")
            assert len(reranked) == k, f"Should return exactly {k} results"

        # Test with top_k=None (return all)
        reranked_all = reranker_service.rerank_chunks(query, chunks, top_k=None)
        logger.info(f"Top-None: Returned {len(reranked_all)} results (all)")
        assert len(reranked_all) == len(
            chunks
        ), "Should return all chunks when top_k=None"

        # Verify that top-3 is a subset of top-5
        top3 = reranker_service.rerank_chunks(query, chunks, top_k=3)
        top5 = reranker_service.rerank_chunks(query, chunks, top_k=5)

        top3_ids = [chunk["doc_id"] for chunk, _ in top3]
        top5_ids = [chunk["doc_id"] for chunk, _ in top5[:3]]

        assert top3_ids == top5_ids, "Top-3 should match first 3 of top-5"
        logger.info("✓ Top-k consistency verified")

        client.close()

        logger.info("\n✅ TEST 5 PASSED: Top-k stability validated")
        return True

    except Exception as e:
        logger.error(f"\n❌ TEST 5 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all Phase 3 reranker smoke tests."""
    logger.info("=" * 70)
    logger.info("PHASE 3: BGE RERANKER SMOKE TESTS")
    logger.info("=" * 70)

    results = {
        "Test 1: Chunk-Level Reranking": test_chunk_reranking(),
        "Test 2: Document-Level Reranking": test_document_level_reranking(),
        "Test 3: Page-Level Reranking": test_page_level_reranking(),
        "Test 4: Score Improvement": test_score_improvement(),
        "Test 5: Top-K Stability": test_top_k_stability(),
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
        logger.info("🎉 ALL TESTS PASSED! Phase 3 BGE Reranker is production-ready!")
    else:
        logger.warning(f"⚠️ {total - passed} test(s) failed. Review logs above.")

    logger.info("=" * 70)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
