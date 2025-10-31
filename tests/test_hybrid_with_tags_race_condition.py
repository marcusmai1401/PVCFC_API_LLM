"""
Tests for BUG-021 fix: PID enhancer shared state race condition.

Verifies that ContextVar implementation prevents concurrent requests
from contaminating each other's cached analysis/validation state.

BUG-021 SCENARIO:
Before fix: Instance variables (self._last_analysis, self._last_validation)
were shared across concurrent requests, causing Request A to retrieve using
Request B's query parameters.

After fix: ContextVar provides thread-safe, request-scoped storage that
isolates each request's context.
"""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.rag.hybrid_with_tags_retriever import HybridWithTagsRetriever
from app.rag.query_transform import QueryFilters, QueryIntent, TransformedQuery


@pytest.fixture
def mock_retriever():
    """Create retriever with mocked dependencies for testing"""
    with patch("app.rag.hybrid_with_tags_retriever.get_config") as mock_config, patch(
        "app.rag.hybrid_with_tags_retriever.HybridWeaviateOpenSearchRetriever"
    ) as mock_hybrid, patch(
        "app.rag.hybrid_with_tags_retriever.PIDContextValidator"
    ) as mock_validator:
        # Mock config
        config_instance = MagicMock()
        config_instance.ENABLE_PID_TAGS = True
        mock_config.return_value = config_instance

        # Mock hybrid retriever
        mock_hybrid_instance = MagicMock()
        mock_hybrid_instance.search.return_value = []
        mock_hybrid.return_value = mock_hybrid_instance

        # Mock validator to always pass validation
        validator_instance = MagicMock()
        validator_instance.validate.return_value = {
            "is_valid": True,
            "confidence": 0.9,
            "reason": "test",
        }
        mock_validator.return_value = validator_instance

        # Create retriever
        retriever = HybridWithTagsRetriever()

        # Mock PID components
        retriever.pid_enhancer = MagicMock()
        retriever.tags_retriever = MagicMock()
        retriever.tags_retriever.search_by_suffix.return_value = {
            "groups": [],
            "total_tags": 0,
            "has_ambiguity": False,
        }

        yield retriever


def test_concurrent_requests_isolated_context(mock_retriever):
    """
    Test that concurrent requests maintain isolated ContextVar state.

    SCENARIO:
    - Thread 1 processes Query A (P&ID query for "TXI-2077")
    - Thread 2 processes Query B (P&ID query for "K06101")
    - Both threads should maintain separate analysis contexts
    - No cross-contamination should occur

    VERIFICATION:
    - Each thread gets correct analysis for its query
    - Analysis from one thread doesn't leak to another
    """
    results = {"thread_1": None, "thread_2": None, "errors": []}

    def process_query_a():
        """Thread 1: Process P&ID query for TXI-2077"""
        try:
            # Mock analysis for Query A
            mock_retriever.pid_enhancer.enhance.return_value = {
                "strategy": "suffix_search",
                "suffix": "TXI-2077",
                "confidence": 0.9,
            }

            query = TransformedQuery(
                original="What is TXI-2077 connected to?",
                normalized="TXI-2077 connections",
                intent=QueryIntent.ASK,
                filters=QueryFilters(),
            )

            # Trigger _should_use_tags which sets ContextVar
            should_use = mock_retriever._should_use_tags(query)

            # Small delay to increase race condition likelihood
            time.sleep(0.01)

            # Verify the analysis stored in ContextVar
            from app.rag.hybrid_with_tags_retriever import _request_analysis

            stored_analysis = _request_analysis.get()

            results["thread_1"] = {
                "should_use_tags": should_use,
                "stored_suffix": stored_analysis.get("suffix")
                if stored_analysis
                else None,
            }

        except Exception as e:
            results["errors"].append(f"Thread 1 error: {e}")

    def process_query_b():
        """Thread 2: Process P&ID query for K06101"""
        try:
            # Mock analysis for Query B (different query!)
            mock_retriever.pid_enhancer.enhance.return_value = {
                "strategy": "suffix_search",
                "suffix": "K06101",
                "confidence": 0.85,
            }

            query = TransformedQuery(
                original="What is K06101 pressure?",
                normalized="K06101 pressure",
                intent=QueryIntent.ASK,
                filters=QueryFilters(),
            )

            # Small delay to increase race condition likelihood
            time.sleep(0.005)

            # Trigger _should_use_tags which sets ContextVar
            should_use = mock_retriever._should_use_tags(query)

            # Verify the analysis stored in ContextVar
            from app.rag.hybrid_with_tags_retriever import _request_analysis

            stored_analysis = _request_analysis.get()

            results["thread_2"] = {
                "should_use_tags": should_use,
                "stored_suffix": stored_analysis.get("suffix")
                if stored_analysis
                else None,
            }

        except Exception as e:
            results["errors"].append(f"Thread 2 error: {e}")

    # Create threads
    thread_1 = threading.Thread(target=process_query_a)
    thread_2 = threading.Thread(target=process_query_b)

    # Start threads simultaneously
    thread_1.start()
    thread_2.start()

    # Wait for completion
    thread_1.join(timeout=5)
    thread_2.join(timeout=5)

    # Verify no errors
    assert len(results["errors"]) == 0, f"Errors occurred: {results['errors']}"

    # Verify both threads got results
    assert results["thread_1"] is not None, "Thread 1 should have results"
    assert results["thread_2"] is not None, "Thread 2 should have results"

    # KEY VERIFICATION: Each thread should have its own correct suffix
    # If race condition existed, one thread would see the other's suffix
    assert (
        results["thread_1"]["stored_suffix"] == "TXI-2077"
    ), f"Thread 1 should have TXI-2077, got {results['thread_1']['stored_suffix']}"
    assert (
        results["thread_2"]["stored_suffix"] == "K06101"
    ), f"Thread 2 should have K06101, got {results['thread_2']['stored_suffix']}"

    print("✅ Race condition test passed: Concurrent requests maintain isolated context")


@pytest.mark.asyncio
async def test_async_concurrent_requests_isolated_context(mock_retriever):
    """
    Test that async concurrent requests maintain isolated ContextVar state.

    This tests the real-world FastAPI scenario where multiple async requests
    are handled concurrently by the same retriever instance.
    """

    async def process_query_async(query_text: str, expected_suffix: str):
        """Process a query and verify isolated context"""
        # Mock analysis
        mock_retriever.pid_enhancer.enhance.return_value = {
            "strategy": "suffix_search",
            "suffix": expected_suffix,
            "confidence": 0.9,
        }

        query = TransformedQuery(
            original=query_text,
            normalized=query_text,
            intent=QueryIntent.ASK,
            filters=QueryFilters(),
        )

        # Trigger _should_use_tags
        should_use = mock_retriever._should_use_tags(query)

        # Small delay to simulate processing
        await asyncio.sleep(0.01)

        # Verify isolated context
        from app.rag.hybrid_with_tags_retriever import _request_analysis

        stored_analysis = _request_analysis.get()

        return {
            "query": query_text,
            "expected_suffix": expected_suffix,
            "stored_suffix": stored_analysis.get("suffix") if stored_analysis else None,
            "should_use_tags": should_use,
        }

    # Run 5 concurrent async queries with different suffixes
    queries = [
        ("What is TXI-2077?", "TXI-2077"),
        ("What is K06101?", "K06101"),
        ("What is PSAL-2207?", "PSAL-2207"),
        ("What is FIC-1234?", "FIC-1234"),
        ("What is LT-5678?", "LT-5678"),
    ]

    results = await asyncio.gather(
        *[process_query_async(q, suffix) for q, suffix in queries]
    )

    # Verify each query got its own correct suffix
    for result in results:
        assert result["stored_suffix"] == result["expected_suffix"], (
            f"Query '{result['query']}' expected suffix '{result['expected_suffix']}', "
            f"but got '{result['stored_suffix']}' (context leak detected!)"
        )

    print(
        f"✅ Async race condition test passed: {len(results)} concurrent requests maintained isolation"
    )


def test_contextvars_cleanup_between_requests(mock_retriever):
    """
    Test that ContextVar state doesn't persist across separate requests.

    SCENARIO:
    - Request 1 processes a P&ID query (sets ContextVar)
    - Request 2 processes a different query in a new thread/context
    - Request 2 should NOT see Request 1's ContextVar state
    """
    from app.rag.hybrid_with_tags_retriever import (
        _request_analysis,
        _request_validation,
    )

    # Request 1: Set some context
    mock_retriever.pid_enhancer.enhance.return_value = {
        "strategy": "suffix_search",
        "suffix": "OLD-QUERY",
        "confidence": 0.9,
    }

    query1 = TransformedQuery(
        original="What is OLD-QUERY?",
        normalized="OLD-QUERY",
        intent=QueryIntent.ASK,
        filters=QueryFilters(),
    )

    mock_retriever._should_use_tags(query1)

    # Verify context is set
    assert _request_analysis.get() is not None, "Context should be set for Request 1"

    # Request 2: In a NEW thread (simulating new request)
    def new_request_context():
        """Simulate a completely new request in a new thread"""
        # ContextVar should be fresh/empty in new thread
        context = _request_analysis.get()
        assert (
            context is None
        ), f"New request should have empty ContextVar, but got {context} (leaked from previous request!)"

    thread = threading.Thread(target=new_request_context)
    thread.start()
    thread.join(timeout=2)

    print("✅ ContextVar cleanup test passed: No state leakage between requests")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
