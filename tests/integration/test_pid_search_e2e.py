"""
End-to-end integration tests for P&ID search enhancements

Tests the complete flow from query → enhancement → search → formatting
"""
import os

import pytest

from app.rag.formatters.pid_response_formatter import (
    format_component_search_response,
    format_pid_search_response,
)
from app.rag.indexers.opensearch_tags_retriever import OpenSearchTagsRetriever
from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer


@pytest.fixture
def enhancer():
    """PID query enhancer fixture"""
    return PIDQueryEnhancer()


@pytest.fixture
def retriever():
    """OpenSearch tags retriever fixture"""
    # Skip if OpenSearch not available
    if not os.environ.get("OPENSEARCH_ENABLED"):
        pytest.skip("OpenSearch not enabled")

    return OpenSearchTagsRetriever()


class TestSuffixOnlySearch:
    """Test SUFFIX-only search end-to-end"""

    def test_suffix_5153(self, enhancer, retriever):
        """Test query '5153' returns multiple prefixes"""
        query = "5153"

        # Step 1: Enhance query
        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "suffix_search"
        assert enhanced["suffix"] == "5153"
        assert enhanced["query_type"] == "suffix_only"

        # Step 2: Search
        grouped_results = retriever.search_by_suffix("5153")

        assert grouped_results["total_tags"] > 0

        # Step 3: Format response
        formatted = format_pid_search_response(query, grouped_results)

        assert formatted["query"] == "5153"
        assert formatted["total_tags"] > 0

        # Check for multi-prefix warning if applicable
        if formatted["has_ambiguity"]:
            assert "clarification" in formatted
            assert len(formatted["found_prefixes"]) > 1

    def test_suffix_501(self, enhancer, retriever):
        """Test query '501' (3 digits)"""
        query = "501"

        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "suffix_search"
        assert enhanced["suffix"] == "501"


class TestComponentSearch:
    """Test component-based search end-to-end"""

    def test_unit_and_suffix(self, enhancer, retriever):
        """Test query '04 5153'"""
        query = "04 5153"

        # Enhance
        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "component_search"
        assert enhanced["components"]["unit"] == "04"
        assert enhanced["components"]["suffix"] == "5153"

        # Search
        results = retriever.search_by_components(unit="04", suffix="5153")

        assert isinstance(results, list)

        # All results should have unit=04 and suffix=5153
        for result in results:
            assert result.get("unit") == "04"
            assert result.get("suffix") == "5153"

    def test_prefix_and_suffix(self, enhancer, retriever):
        """Test query 'PAHH 5153'"""
        query = "PAHH 5153"

        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "component_search"
        assert enhanced["components"]["prefix"] == "PAHH"
        assert enhanced["components"]["suffix"] == "5153"

        # Search
        results = retriever.search_by_components(prefix="PAHH", suffix="5153")

        # All results should match
        for result in results:
            assert result.get("prefix") == "PAHH"
            assert result.get("suffix") == "5153"

    def test_full_tag_components(self, enhancer, retriever):
        """Test full tag '04 PAHH 5153'"""
        query = "04 PAHH 5153"

        enhanced = enhancer.enhance(query)

        assert enhanced["strategy"] == "component_search"
        assert enhanced["components"]["unit"] == "04"
        assert enhanced["components"]["prefix"] == "PAHH"
        assert enhanced["components"]["suffix"] == "5153"

        # Search
        results = retriever.search_by_components(
            unit="04", prefix="PAHH", suffix="5153"
        )

        # Should return exact matches
        for result in results:
            assert result.get("unit") == "04"
            assert result.get("prefix") == "PAHH"
            assert result.get("suffix") == "5153"


class TestMultiPrefixHandling:
    """Test multi-prefix grouping and warnings"""

    def test_multi_prefix_grouping(self, retriever):
        """Test that multi-prefix results are grouped correctly"""
        # Search for a suffix that has multiple prefixes
        grouped_results = retriever.search_by_suffix("5153")

        if grouped_results["total_tags"] > 0:
            # Check grouping structure
            assert "groups" in grouped_results
            assert "has_ambiguity" in grouped_results

            for group in grouped_results["groups"]:
                assert "suffix" in group
                assert "prefixes" in group
                assert "tags" in group
                assert "pages" in group
                assert "co_located" in group

                # If multi-prefix, should have warning
                if len(group["prefixes"]) > 1:
                    assert group["warning"] is not None
                    assert grouped_results["has_ambiguity"] is True

    def test_formatted_response_with_ambiguity(self, retriever):
        """Test formatted response for ambiguous query"""
        query = "5153"
        grouped_results = retriever.search_by_suffix(query)

        formatted = format_pid_search_response(query, grouped_results)

        if formatted["has_ambiguity"]:
            # Should have clarification
            assert "clarification" in formatted
            assert "found_prefixes" in formatted
            assert "suggestion" in formatted

            # Prefixes should be unique
            prefixes = formatted["found_prefixes"]
            assert len(prefixes) == len(set(prefixes))


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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
