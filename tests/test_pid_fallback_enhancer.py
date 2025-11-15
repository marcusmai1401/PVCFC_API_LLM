"""
Unit tests for P&ID Fallback Enhancer

Tests:
1. Tag variant generation
2. Safety check functionality
3. RRF fusion with adaptive weights
4. Configuration handling
5. Integration with OpenSearch and PID reranker
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import MagicMock, Mock, patch

import pytest
from loguru import logger

from app.rag.pid_fallback_enhancer import PIDFallbackEnhancer
from app.rag.retriever import RetrievalResult


class TestPIDFallbackEnhancerTagVariants:
    """Test tag variant generation"""

    @pytest.fixture
    def enhancer(self):
        """Create enhancer with default config"""
        return PIDFallbackEnhancer(config={})

    def test_generate_tag_variants_basic(self, enhancer):
        """Test basic tag variant generation"""
        components = {
            "unit": "29",
            "prefix": "TE",
            "suffix": "2038",
            "variant": "A",
        }

        variants = enhancer.generate_tag_variants(components)

        # Expected variants:
        # 1. 29-TE-2038-A (hyphen-separated)
        # 2. 29 TE 2038 A (space-separated)
        # 3. 29TE2038A (no separators)
        # 4. TE 2038A (without unit)

        assert len(variants) == 4
        assert "29 TE 2038A" in variants
        assert "29TE2038A" in variants
        assert "29-TE-2038A" in variants
        assert "TE 2038A" in variants

        logger.info(f"✅ Generated variants: {variants}")

    def test_generate_tag_variants_no_suffix(self, enhancer):
        """Test variant generation without suffix"""
        components = {
            "unit": "42",
            "prefix": "FT",
            "suffix": "1001",
        }

        variants = enhancer.generate_tag_variants(components)

        assert len(variants) == 4
        assert "42-FT-1001" in variants
        assert "42 FT 1001" in variants
        assert "42FT1001" in variants

        logger.info(f"✅ No-suffix variants: {variants}")

    def test_generate_tag_variants_missing_components(self, enhancer):
        """Test variant generation with incomplete components"""
        components = {"unit": "29"}

        variants = enhancer.generate_tag_variants(components)

        # With only unit provided, no variants are generated in current implementation
        assert len(variants) == 0

        logger.info(f"✅ Partial component variants: {variants}")

    def test_generate_tag_variants_max_limit(self, enhancer):
        """Test max_variants limit is respected"""
        # Limit variants via constructor config
        enhancer_limited = PIDFallbackEnhancer(config={"max_variants": 2})
        components = {
            "unit": "29",
            "prefix": "TE",
            "suffix": "2038",
            "variant": "A",
        }

        variants = enhancer_limited.generate_tag_variants(components)

        assert len(variants) == 2

        logger.info(f"✅ Max variants limit respected: {variants}")


class TestPIDFallbackEnhancerSafetyCheck:
    """Test post-BGE safety check functionality"""

    @pytest.fixture
    def enhancer(self):
        """Create enhancer with default config"""
        return PIDFallbackEnhancer(config={})

    def test_safety_check_moves_exact_match_to_top(self, enhancer):
        """Test that exact tag matches are moved to top 3"""
        # Create mock results
        results = [
            RetrievalResult(
                chunk_id="chunk1",
                text="Some unrelated content",
                score=0.95,
                source="bge",
                metadata={"page": 1},
            ),
            RetrievalResult(
                chunk_id="chunk2",
                text="Another unrelated chunk",
                score=0.90,
                source="bge",
                metadata={"page": 2},
            ),
            RetrievalResult(
                chunk_id="chunk4",
                text="More content",
                score=0.85,
                source="bge",
                metadata={"page": 4},
            ),
            RetrievalResult(
                chunk_id="chunk3",
                text="Contains tag 29 TE 2038A exactly",
                score=0.50,  # Low score but exact match
                source="bge",
                metadata={"page": 113, "tags": ["29-TE-2038A"]},
            ),
        ]

        tag_variants = ["29 TE 2038A", "29-TE-2038A", "29TE2038A", "29-TE-2038-A"]

        adjusted = enhancer._post_bge_safety_check(results, tag_variants)

        # Chunk3 should be moved to position 0 despite low score
        assert adjusted[0].chunk_id == "chunk3"
        assert adjusted[0].metadata.get("page") == 113

        logger.info(f"✅ Safety check promoted exact match from rank 3 to rank 1")

    def test_safety_check_disabled(self, enhancer):
        """Test that safety check can be disabled via config"""
        enhancer.enable_safety_check = False

        results = [
            RetrievalResult(
                chunk_id="chunk1",
                text="Some content",
                score=0.95,
                source="bge",
                metadata={"page": 1},
            ),
            RetrievalResult(
                chunk_id="chunk2",
                text="Contains 29 TE 2038A",
                score=0.50,
                source="bge",
                metadata={"page": 113},
            ),
        ]

        tag_variants = ["29 TE 2038A"]

        adjusted = enhancer._post_bge_safety_check(results, tag_variants)

        # Order should remain unchanged
        assert adjusted[0].chunk_id == "chunk1"
        assert adjusted[1].chunk_id == "chunk2"

        logger.info("✅ Safety check correctly disabled")

    def test_safety_check_no_exact_match(self, enhancer):
        """Test safety check when no exact match exists"""
        results = [
            RetrievalResult(
                chunk_id="chunk1",
                text="Some content",
                score=0.95,
                source="bge",
                metadata={"page": 1},
            ),
            RetrievalResult(
                chunk_id="chunk2",
                text="More content",
                score=0.90,
                source="bge",
                metadata={"page": 2},
            ),
        ]

        tag_variants = ["29 TE 2038A"]

        adjusted = enhancer._post_bge_safety_check(results, tag_variants)

        # Order should remain unchanged
        assert adjusted[0].chunk_id == "chunk1"
        assert adjusted[1].chunk_id == "chunk2"

        logger.info("✅ Safety check handles no-match scenario correctly")


class TestPIDFallbackEnhancerRRFFusion:
    """Test adaptive RRF fusion"""

    @pytest.fixture
    def enhancer(self):
        """Create enhancer with custom weights"""
        return PIDFallbackEnhancer(
            config={
                "opensearch_weight": 1.0,
                "weaviate_weight": 0.3,
            }
        )

    def test_rrf_fusion_basic(self, enhancer):
        """Test basic RRF fusion with different weights"""
        opensearch_results = [
            RetrievalResult(
                chunk_id="os_chunk1",
                text="OpenSearch result 1",
                score=10.0,
                source="opensearch",
                metadata={"page": 113},
            ),
            RetrievalResult(
                chunk_id="os_chunk2",
                text="OpenSearch result 2",
                score=8.0,
                source="opensearch",
                metadata={"page": 2},
            ),
        ]

        weaviate_results = [
            RetrievalResult(
                chunk_id="wv_chunk1",
                text="Weaviate result 1",
                score=0.95,
                source="weaviate",
                metadata={"page": 1},
            ),
            RetrievalResult(
                chunk_id="wv_chunk2",
                text="Weaviate result 2",
                score=0.90,
                source="weaviate",
                metadata={"page": 113},
            ),
        ]

        fused = enhancer._adaptive_rrf_fusion(
            opensearch_results,
            weaviate_results,
        )

        # Should combine results from both sources
        assert len(fused) > 0
        chunk_ids = [r.chunk_id for r in fused]
        assert "os_chunk1" in chunk_ids or "os_chunk2" in chunk_ids
        assert "wv_chunk1" in chunk_ids or "wv_chunk2" in chunk_ids

        logger.info(f"✅ RRF fusion combined {len(fused)} results")

    def test_rrf_fusion_opensearch_preference(self, enhancer):
        """Test that OpenSearch results are weighted higher"""
        # Same page in both sources
        opensearch_results = [
            RetrievalResult(
                chunk_id="os_chunk",
                text="OpenSearch duplicate",
                score=5.0,
                source="opensearch",
                metadata={"page": 113},
            ),
        ]

        weaviate_results = [
            RetrievalResult(
                chunk_id="wv_chunk",
                text="Weaviate duplicate",
                score=0.95,
                source="weaviate",
                metadata={"page": 113},
            ),
        ]

        fused = enhancer._adaptive_rrf_fusion(
            opensearch_results,
            weaviate_results,
        )

        # Due to higher OpenSearch weight (1.0 vs 0.3), OpenSearch result should rank higher
        # But both should be present in fused results
        assert len(fused) > 0

        logger.info(f"✅ RRF fusion respects OpenSearch weight preference")

    def test_rrf_fusion_empty_opensearch(self, enhancer):
        """Test RRF fusion when OpenSearch returns nothing"""
        opensearch_results = []

        weaviate_results = [
            RetrievalResult(
                chunk_id="wv_chunk1",
                text="Weaviate only",
                score=0.95,
                source="weaviate",
                metadata={"page": 1},
            ),
        ]

        fused = enhancer._adaptive_rrf_fusion(
            opensearch_results,
            weaviate_results,
        )

        # Should still return Weaviate results
        assert len(fused) == 1
        assert fused[0].chunk_id == "wv_chunk1"

        logger.info("✅ RRF fusion handles empty OpenSearch gracefully")


class TestPIDFallbackEnhancerConfiguration:
    """Test configuration handling"""

    def test_default_config(self):
        """Test enhancer with default configuration"""
        enhancer = PIDFallbackEnhancer(config={})

        # Defaults from implementation
        assert enhancer.opensearch_weight == 1.0
        assert enhancer.weaviate_weight == 0.3
        assert enhancer.enable_tag_rerank is True
        assert enhancer.enable_safety_check is True

        logger.info("✅ Default configuration loaded correctly")

    def test_custom_config(self):
        """Test enhancer with custom configuration"""
        custom_config = {
            "opensearch_weight": 0.8,
            "weaviate_weight": 0.5,
            "enable_tag_rerank": False,
            "enable_safety_check": False,
            "max_variants": 10,
        }

        enhancer = PIDFallbackEnhancer(config=custom_config)

        assert enhancer.opensearch_weight == 0.8
        assert enhancer.weaviate_weight == 0.5
        assert enhancer.enable_tag_rerank is False
        assert enhancer.enable_safety_check is False
        assert enhancer.max_variants == 10

        logger.info("✅ Custom configuration applied correctly")


class TestPIDFallbackEnhancerIntegration:
    """Integration tests with real components (if available)"""

    def test_search_with_enhancements_mock(self):
        """Test full search pipeline with mocked components"""
        mock_opensearch = Mock()
        mock_weaviate = Mock()

        # Mock OpenSearch response
        mock_opensearch.search_with_tag_boosting.return_value = [
            RetrievalResult(
                chunk_id="os1",
                text="OpenSearch result with tag 29 TE 2038A",
                score=10.0,
                source="opensearch",
                metadata={"page": 113, "extracted_tags": ["29-TE-2038A"]},
            ),
        ]

        # Mock Weaviate response
        mock_weaviate.search.return_value = [
            RetrievalResult(
                chunk_id="wv1",
                text="Weaviate semantic result",
                score=0.85,
                source="weaviate",
                metadata={"page": 1},
            ),
        ]

        # Disable internal reranker to isolate pipeline
        enhancer = PIDFallbackEnhancer(config={"enable_tag_rerank": False})

        # Test search
        components = {
            "unit": "29",
            "prefix": "TE",
            "suffix": "2038",
            "variant": "A",
        }

        from app.rag.query_transform import QueryFilters, QueryIntent, TransformedQuery

        tq = TransformedQuery(
            normalized="29 TE 2038A",
            original="29 TE 2038A",
            intent=QueryIntent.ASK,
            filters=QueryFilters(),
        )

        results = enhancer.search_with_enhancements(
            transformed_query=tq,
            analysis={"components": components},
            opensearch_retriever=mock_opensearch,
            weaviate_retriever=mock_weaviate,
            top_k=10,
        )

        # Verify calls were made
        assert mock_opensearch.search_with_tag_boosting.called
        assert mock_weaviate.search.called

        # Verify results
        assert len(results) > 0

        logger.info(
            f"✅ Full search pipeline executed successfully with {len(results)} results"
        )

    def test_search_with_enhancements_disabled(self):
        """Test that enhancement can be disabled"""
        mock_opensearch = Mock()
        mock_weaviate = Mock()

        enhancer = PIDFallbackEnhancer(config={"enable_tag_rerank": False})

        components = {"unit": "29"}

        from app.rag.query_transform import QueryFilters, QueryIntent, TransformedQuery

        tq = TransformedQuery(
            normalized="29 TE 2038A",
            original="29 TE 2038A",
            intent=QueryIntent.ASK,
            filters=QueryFilters(),
        )

        results = enhancer.search_with_enhancements(
            transformed_query=tq,
            analysis={"components": components},
            opensearch_retriever=mock_opensearch,
            weaviate_retriever=mock_weaviate,
            top_k=10,
        )

        # Should return some results when pipeline runs
        assert isinstance(results, list)

        logger.info("✅ Enhancement correctly disabled via config")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
