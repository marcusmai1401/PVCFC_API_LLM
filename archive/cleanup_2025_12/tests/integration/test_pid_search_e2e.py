"""
End-to-end integration tests for P&ID search enhancements (Level 2 Spatial Search)

Tests the complete flow from query → enhancement → spatial search

NOTE: This test suite has been updated to use Level 2 (Spatial Tag Searcher)
      instead of Level 3 (OpenSearch Tags Retriever) which has been removed.

Level 2 Limitations:
- SUFFIX-only queries are NOT supported (requires full components)
- Multi-prefix grouping is not available in Level 2
- Results are based on real-time geometric clustering
"""
import os

import pytest

from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer
from app.rag.spatial.spatial_searcher import SpatialTagSearcher


@pytest.fixture
def enhancer():
    """PID query enhancer fixture"""
    return PIDQueryEnhancer()


@pytest.fixture
def searcher():
    """Level 2 Spatial Tag Searcher fixture"""
    # Skip if OpenSearch not available
    if not os.environ.get("OPENSEARCH_ENABLED"):
        pytest.skip("OpenSearch not enabled")

    return SpatialTagSearcher(
        max_distance_mm=25.0,
        alignment_tolerance_mm=5.0,
        min_cluster_score=0.6,
    )


@pytest.mark.skip(
    reason="SUFFIX-only queries not supported in Level 2 - requires full components"
)
class TestSuffixOnlySearch:
    """Test SUFFIX-only search end-to-end

    NOTE: These tests are SKIPPED because Level 2 (Spatial Tag Searcher) does not
          support SUFFIX-only queries. Level 2 requires all three components
          (unit, prefix, suffix) for spatial clustering.

          SUFFIX-only queries will fallback to semantic search in production.
    """

    def test_suffix_5153(self, enhancer, searcher):
        """Test query '5153' returns multiple prefixes"""
        query = "5153"

        # Step 1: Enhance query
        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "suffix_search"
        assert enhanced["suffix"] == "5153"
        assert enhanced["query_type"] == "suffix_only"

        # Level 2 does NOT support suffix-only search
        # This would fallback to semantic search in production

    def test_suffix_501(self, enhancer, searcher):
        """Test query '501' (3 digits)"""
        query = "501"

        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "suffix_search"
        assert enhanced["suffix"] == "501"

        # Level 2 does NOT support suffix-only search


class TestComponentSearch:
    """Test component-based search with Level 2 Spatial Search"""

    def test_unit_and_suffix(self, enhancer, searcher):
        """Test query '04 5153' - partial components"""
        query = "04 5153"

        # Enhance
        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "component_search"
        assert enhanced["components"]["unit"] == "04"
        assert enhanced["components"]["suffix"] == "5153"

        # Level 2 spatial search requires all components
        # This would use empty string for prefix
        results = searcher.search(
            unit="04", prefix="", suffix="5153", doc_id="Ammonia"  # Empty prefix
        )

        # Results are SearchResult objects from Level 2
        assert isinstance(results, list)

    def test_prefix_and_suffix(self, enhancer, searcher):
        """Test query 'PAHH 5153' - partial components"""
        query = "PAHH 5153"

        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "component_search"
        assert enhanced["components"]["prefix"] == "PAHH"
        assert enhanced["components"]["suffix"] == "5153"

        # Level 2 spatial search
        results = searcher.search(
            unit="", prefix="PAHH", suffix="5153", doc_id="Ammonia"  # Empty unit
        )

        assert isinstance(results, list)

    def test_full_tag_components(self, enhancer, searcher):
        """Test full tag '04 PAHH 5153' - complete components"""
        query = "04 PAHH 5153"

        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "component_search"
        assert enhanced["components"]["unit"] == "04"
        assert enhanced["components"]["prefix"] == "PAHH"
        assert enhanced["components"]["suffix"] == "5153"

        # Level 2 spatial search with full components
        results = searcher.search(
            unit="04", prefix="PAHH", suffix="5153", doc_id="Ammonia"
        )

        assert isinstance(results, list)

        # Check results structure (SearchResult objects)
        for result in results:
            assert hasattr(result, "page")
            assert hasattr(result, "score")
            assert hasattr(result, "bbox")
            assert hasattr(result, "metadata")


@pytest.mark.skip(reason="Multi-prefix grouping not available in Level 2")
class TestMultiPrefixHandling:
    """Test multi-prefix grouping and warnings

    NOTE: These tests are SKIPPED because Level 2 (Spatial Tag Searcher) does not
          provide grouped results by suffix. Level 2 returns individual SearchResult
          objects based on spatial clustering, not grouped by prefix.
    """

    def test_multi_prefix_grouping(self, searcher):
        """Test that multi-prefix results are grouped correctly"""
        # Level 2 does not support suffix-only search or grouping
        pass

    def test_formatted_response_with_ambiguity(self, searcher):
        """Test formatted response for ambiguous query"""
        # Level 2 does not support suffix-only search or grouping
        pass


class TestAnnotationHandling:
    """Test annotation handling in queries"""

    def test_query_with_annotation_matches_without(self, enhancer):
        """Test that '04 PAHH 5153' matches '04 PAHH 5153A/B/C'"""
        # Query without annotation
        query = "04 PAHH 5153"

        enhanced = enhancer.enhance(query)
        components = enhanced.get("components", {})

        # Should parse as core components only
        assert components.get("unit") == "04"
        assert components.get("prefix") == "PAHH"
        assert components.get("suffix") == "5153"

        # No annotation in components
        assert components.get("annotation", "") == ""

    def test_query_ignores_annotation(self, enhancer):
        """Test that annotation is ignored in search"""
        query = "04 PAHH 5153A/B/C"

        parsed = enhancer.tag_normalizer.parse_tag_components(query)

        # Annotation should be separated
        assert parsed["annotation"] == "A/B/C"
        assert parsed["normalized"] == "04 PAHH 5153"


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_query(self, enhancer):
        """Test empty query"""
        result = enhancer.enhance("")

        # Should fall back to semantic
        assert result["strategy"] == "semantic"

    def test_invalid_suffix_too_short(self, enhancer):
        """Test suffix too short (< 3 digits)"""
        result = enhancer.enhance("12")

        # Should NOT be detected as suffix
        assert result["strategy"] != "suffix_search"

    def test_invalid_suffix_too_long(self, enhancer):
        """Test suffix too long (> 5 digits)"""
        result = enhancer.enhance("123456")

        # Should NOT be detected as suffix
        assert result["strategy"] != "suffix_search"

    def test_partial_prefix_only(self, enhancer):
        """Test PREFIX-only query (no suffix)"""
        result = enhancer.enhance("PAHH")

        # Should be component search with prefix only
        if result["strategy"] == "component_search":
            assert result["components"]["prefix"] == "PAHH"
            assert (
                "suffix" not in result["components"]
                or not result["components"]["suffix"]
            )


class TestLevel2SpatialSearch:
    """Test Level 2 specific functionality"""

    def test_spatial_search_returns_search_results(self, searcher):
        """Test that spatial search returns SearchResult objects"""
        results = searcher.search(
            unit="04", prefix="TT", suffix="2020", doc_id="Ammonia"
        )

        assert isinstance(results, list)

        # If results exist, verify structure
        if results:
            result = results[0]
            assert hasattr(result, "page")
            assert hasattr(result, "doc_id")
            assert hasattr(result, "score")
            assert hasattr(result, "bbox")
            assert hasattr(result, "source")
            assert hasattr(result, "metadata")

    def test_spatial_search_requires_all_components(self, searcher):
        """Test that empty components are handled gracefully"""
        # Should not crash even with empty components
        results = searcher.search(unit="", prefix="", suffix="2020", doc_id="Ammonia")

        # May return empty results or partial matches
        assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
