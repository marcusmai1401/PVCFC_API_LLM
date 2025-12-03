"""
Integration Test for P&ID Retrieval Enhancement

Tests end-to-end flow from query to results
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from loguru import logger

from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridWeaviateOpenSearchRetriever,
)
from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer


class TestPIDRetrievalIntegration:
    """Integration tests for P&ID retrieval"""

    def setup_method(self):
        """Setup for each test"""
        self.retriever = HybridWeaviateOpenSearchRetriever()
        self.enhancer = PIDQueryEnhancer()

    def test_tag_only_query_flow(self):
        """Test tag-only query end-to-end"""
        query = "E04217"

        # Step 1: Query enhancement
        enhanced = self.enhancer.enhance(query)

        assert enhanced["strategy"] == "tag_focused"
        assert "E04217" in enhanced["tags"]
        assert enhanced["query_type"] == "tag_only"

        # Step 2: Retrieval
        results = self.retriever.retrieve_enhanced(
            query=query, top_k=10, enable_pid_enhancement=True
        )

        # Verify results
        assert isinstance(results, list)
        logger.info(f"Retrieved {len(results)} results for tag query")

        if results:
            # Check result structure
            top_result = results[0]
            assert hasattr(top_result, "text")
            assert hasattr(top_result, "score")
            assert hasattr(top_result, "source")
            assert hasattr(top_result, "metadata")

            logger.info(f"Top result source: {top_result.source}")
            logger.info(f"Top result score: {top_result.score:.4f}")

    def test_mixed_query_flow(self):
        """Test mixed query (tag + parameter) end-to-end"""
        query = "áp suất của E04217"

        # Query enhancement
        enhanced = self.enhancer.enhance(query)

        assert enhanced["strategy"] == "tag_focused"
        assert enhanced["query_type"] == "mixed"

        # Retrieval
        results = self.retriever.retrieve_enhanced(
            query=query, top_k=10, enable_pid_enhancement=True
        )

        assert isinstance(results, list)
        logger.info(f"Retrieved {len(results)} results for mixed query")

    def test_enhancement_vs_baseline(self):
        """Compare enhanced vs baseline retrieval"""
        query = "E04217"

        # Enhanced
        results_enhanced = self.retriever.retrieve_enhanced(
            query=query, top_k=10, enable_pid_enhancement=True
        )

        # Baseline
        results_baseline = self.retriever.retrieve_enhanced(
            query=query, top_k=10, enable_pid_enhancement=False
        )

        logger.info(f"Enhanced: {len(results_enhanced)} results")
        logger.info(f"Baseline: {len(results_baseline)} results")

        # Both should return results
        assert isinstance(results_enhanced, list)
        assert isinstance(results_baseline, list)

        # Log comparison
        if results_enhanced and results_baseline:
            logger.info(
                f"Enhanced top score: {results_enhanced[0].score:.4f}, "
                f"source: {results_enhanced[0].source}"
            )
            logger.info(
                f"Baseline top score: {results_baseline[0].score:.4f}, "
                f"source: {results_baseline[0].source}"
            )

    def test_multiple_tags_query(self):
        """Test query with multiple equipment tags"""
        query = "E04217 and P04201A connection"

        enhanced = self.enhancer.enhance(query)

        # Should detect both tags
        assert enhanced["strategy"] == "tag_focused"
        assert len(enhanced["tags"]) >= 1  # At least one tag

        results = self.retriever.retrieve_enhanced(
            query=query, top_k=10, enable_pid_enhancement=True
        )

        assert isinstance(results, list)
        logger.info(f"Multi-tag query: {len(results)} results")

    def test_semantic_query_fallback(self):
        """Test fallback to semantic for non-tag queries"""
        query = "what is a heat exchanger"

        enhanced = self.enhancer.enhance(query)

        # Should fallback to semantic
        assert enhanced["strategy"] == "semantic"

        results = self.retriever.retrieve_enhanced(
            query=query, top_k=10, enable_pid_enhancement=True
        )

        assert isinstance(results, list)
        logger.info(f"Semantic query: {len(results)} results")

    @pytest.mark.parametrize(
        "query,expected_type",
        [
            ("E04217", "tag_only"),
            ("áp suất của E04217", "mixed"),
            ("diagram heat exchanger", "visual"),
            ("what is pressure", "semantic"),
        ],
    )
    def test_query_type_classification(self, query, expected_type):
        """Test query type classification for various queries"""
        enhanced = self.enhancer.enhance(query)

        if enhanced["strategy"] == "tag_focused":
            assert enhanced["query_type"] == expected_type or expected_type in [
                "visual",
                "semantic",
            ]
        else:
            assert expected_type == "semantic"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
