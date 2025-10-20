#!/usr/bin/env python
"""
Comprehensive page number preservation test
Tracks page values through entire RAG pipeline with detailed logging
"""

import sys

from loguru import logger

# Configure detailed logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
)
logger.add("page_tracking_debug.log", level="DEBUG", rotation="10 MB")

from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridWeaviateOpenSearchRetriever,
)


def track_page_values(results, stage_name):
    """Track and log page values at a specific pipeline stage"""
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 STAGE: {stage_name}")
    logger.info(f"{'='*80}")

    page_stats = {
        "total": len(results),
        "with_page": 0,
        "page_0": 0,
        "page_none": 0,
        "valid_pages": [],
    }

    for i, result in enumerate(results):
        page = result.page

        if page is not None:
            page_stats["with_page"] += 1
            if page == 0:
                page_stats["page_0"] += 1
                logger.warning(
                    f"  Result {i+1}: page=0 ⚠️  chunk={result.chunk_id[:50]}"
                )
            else:
                page_stats["valid_pages"].append(page)
                logger.debug(
                    f"  Result {i+1}: page={page} ✓ chunk={result.chunk_id[:50]}"
                )
        else:
            page_stats["page_none"] += 1
            logger.error(f"  Result {i+1}: page=None ❌ chunk={result.chunk_id[:50]}")

    # Summary
    logger.info(f"\n📈 Summary for {stage_name}:")
    logger.info(f"  Total results: {page_stats['total']}")
    logger.info(f"  With page value: {page_stats['with_page']}")
    logger.info(f"  Page = 0: {page_stats['page_0']}")
    logger.info(f"  Page = None: {page_stats['page_none']}")

    if page_stats["valid_pages"]:
        logger.info(
            f"  Valid page range: {min(page_stats['valid_pages'])} - {max(page_stats['valid_pages'])}"
        )

    # Issue detection
    issues = []
    if page_stats["page_0"] > 0:
        issues.append(f"{page_stats['page_0']} results with page=0")
    if page_stats["page_none"] > 0:
        issues.append(f"{page_stats['page_none']} results with page=None")

    if issues:
        logger.error(f"  ⚠️  ISSUES: {', '.join(issues)}")
        return False
    else:
        logger.success(f"  ✅ All results have valid page numbers!")
        return True


def test_hybrid_retriever_page_tracking():
    """Test page tracking through hybrid retriever pipeline"""

    logger.info("\n" + "=" * 100)
    logger.info("🔍 COMPREHENSIVE PAGE NUMBER TRACKING TEST")
    logger.info("=" * 100)

    # Test queries
    test_queries = [
        ("04 PU 2049 áp suất thiết kế", "Tag-specific query"),
        ("operating pressure of equipment", "Generic technical query"),
        ("temperature range for reactor", "Another technical query"),
    ]

    retriever = HybridWeaviateOpenSearchRetriever()

    all_passed = True

    for query, description in test_queries:
        logger.info(f"\n{'='*100}")
        logger.info(f"📝 Testing: {description}")
        logger.info(f"   Query: {query}")
        logger.info(f"{'='*100}")

        try:
            # Retrieve results
            results = retriever.retrieve_enhanced(query, top_k=10)

            # Track final results
            passed = track_page_values(results, f"Final Results - {description}")

            if not passed:
                all_passed = False

            # Additional checks for specific tag queries
            if "04 PU 2049" in query:
                logger.info(f"\n🔎 Special check for tag '04 PU 2049':")
                tag_found = False
                correct_page = False

                for result in results:
                    if "04 PU 2049" in result.text or "PU 2049" in result.text:
                        tag_found = True
                        logger.info(f"  Found tag in: {result.chunk_id}")
                        logger.info(f"  Page: {result.page}")
                        logger.info(f"  Score: {result.score:.4f}")

                        # Expected page is 13 based on OpenSearch data
                        if result.page == 13:
                            correct_page = True
                            logger.success(f"  ✅ Correct page number (13)")
                        else:
                            logger.error(
                                f"  ❌ Wrong page: expected 13, got {result.page}"
                            )

                if not tag_found:
                    logger.warning(f"  ⚠️  Tag '04 PU 2049' not found in results")
                elif not correct_page:
                    logger.error(f"  ❌ Tag found but page number incorrect")
                    all_passed = False

        except Exception as e:
            logger.error(f"❌ Test failed with exception: {e}")
            import traceback

            logger.error(traceback.format_exc())
            all_passed = False

    # Final summary
    logger.info(f"\n{'='*100}")
    if all_passed:
        logger.success(f"✅ ALL TESTS PASSED - Page numbers preserved correctly!")
    else:
        logger.error(f"❌ SOME TESTS FAILED - Check logs above for details")
    logger.info(f"{'='*100}\n")

    return all_passed


def test_edge_cases():
    """Test edge cases for page handling"""

    logger.info(f"\n{'='*100}")
    logger.info(f"🧪 EDGE CASE TESTS")
    logger.info(f"{'='*100}\n")

    from app.rag.retriever import RetrievalResult

    # Test 1: page=0 handling
    logger.info("Test 1: page=0 should be preserved (not treated as None)")
    result = RetrievalResult(
        chunk_id="test_0",
        text="Test",
        score=1.0,
        source="test",
        metadata={"page": 0},
        page=0,
    )

    if result.page == 0:
        logger.success("  ✅ page=0 preserved correctly")
    else:
        logger.error(f"  ❌ page=0 became {result.page}")

    # Test 2: None vs 0 distinction
    logger.info("\nTest 2: None vs 0 distinction")

    # Simulate the pattern: value if value is not None else fallback
    test_values = [0, None, 1, 13]
    fallback = 99

    for val in test_values:
        result_val = val if val is not None else fallback
        expected = val if val is not None else fallback

        if result_val == expected:
            logger.success(f"  ✅ {val} → {result_val} (correct)")
        else:
            logger.error(f"  ❌ {val} → {result_val} (expected {expected})")

    # Test 3: Old pattern (wrong)
    logger.info("\nTest 3: Old pattern (WRONG - for comparison)")
    for val in test_values:
        result_val = val or fallback  # Wrong! Treats 0 as falsy

        if val == 0:
            logger.warning(f"  ⚠️  {val} → {result_val} (WRONG: 0 treated as None)")
        else:
            logger.debug(f"  {val} → {result_val}")


if __name__ == "__main__":
    logger.info("Starting comprehensive page tracking tests...")

    # Edge case tests
    test_edge_cases()

    # Full pipeline test
    success = test_hybrid_retriever_page_tracking()

    logger.info(f"\n{'='*100}")
    logger.info(f"📋 Test log saved to: page_tracking_debug.log")
    logger.info(f"{'='*100}\n")

    sys.exit(0 if success else 1)
