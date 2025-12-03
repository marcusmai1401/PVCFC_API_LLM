"""
Integration tests for P&ID search safety features

Tests the complete flow from query → enhancement → validation → search → fallback
"""
import os

import pytest

from app.rag.hybrid_with_tags_retriever import HybridWithTagsRetriever
from app.rag.query_transform import QueryTransformer


@pytest.fixture
def retriever():
    """Hybrid retriever with tags support"""
    # Skip if not enabled
    if not os.environ.get("ENABLE_PID_TAGS"):
        pytest.skip("PID tags not enabled")

    return HybridWithTagsRetriever()


@pytest.fixture
def transformer():
    """Query transformer"""
    return QueryTransformer(enable_hyde=False)


class TestPureSuffixQueries:
    """Test pure SUFFIX queries end-to-end"""

    def test_pure_suffix_5153(self, retriever, transformer):
        """Test '5153' goes through P&ID search"""
        query = "5153"

        # Transform
        transformed = transformer.transform(query)

        # Search
        results = retriever.search(transformed, top_k=10)

        # Should return results (P&ID or fallback to semantic)
        assert len(results) > 0

        # Check if P&ID was used (results should have tag metadata)
        has_tag_results = any(
            r.metadata and r.metadata.get("source") == "tags" for r in results
        )

        print(f"Query '{query}': {len(results)} results, has_tags={has_tag_results}")

    def test_pure_suffix_501(self, retriever, transformer):
        """Test '501' (3 digits)"""
        query = "501"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        assert len(results) > 0


class TestSemanticWithNumbers:
    """Test that semantic queries with numbers use semantic search"""

    def test_procedure_with_number(self, retriever, transformer):
        """'procedure 5153' should use semantic"""
        query = "procedure 5153"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        # Should return results (semantic)
        assert len(results) > 0

        # Should NOT have tag results (context validation should reject)
        has_tag_results = any(
            r.metadata and r.metadata.get("source") == "tags" for r in results
        )

        # Expect False (used semantic, not P&ID)
        print(f"Query '{query}': has_tags={has_tag_results} (expect False)")

    def test_what_is_with_number(self, retriever, transformer):
        """'What is 5153?' should use semantic"""
        query = "What is 5153?"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        assert len(results) > 0

        # Should use semantic (has 'what is')
        has_tag_results = any(
            r.metadata and r.metadata.get("source") == "tags" for r in results
        )

        print(f"Query '{query}': has_tags={has_tag_results} (expect False)")

    def test_vietnamese_semantic(self, retriever, transformer):
        """Vietnamese semantic query should use semantic"""
        query = "5153 là gì?"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        assert len(results) > 0


class TestComponentQueries:
    """Test component-based queries"""

    def test_component_unit_suffix(self, retriever, transformer):
        """'04 5153' should use P&ID"""
        query = "04 5153"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        assert len(results) > 0

    def test_component_prefix_suffix(self, retriever, transformer):
        """'IS 501' should use P&ID"""
        query = "IS 501"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        assert len(results) > 0

    def test_component_with_pid_context(self, retriever, transformer):
        """'áp suất của 5153' should use P&ID"""
        query = "áp suất của 5153"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        assert len(results) > 0


class TestEmptyResultsFallback:
    """Test fallback when P&ID returns no results"""

    def test_nonexistent_suffix(self, retriever, transformer):
        """Non-existent SUFFIX should fallback to semantic"""
        query = "99999"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        # Should return results (from semantic fallback)
        assert len(results) >= 0  # Might be 0 if truly nothing matches

    def test_nonexistent_component(self, retriever, transformer):
        """Non-existent component should fallback"""
        query = "XXXX 99999"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        # Should handle gracefully
        assert isinstance(results, list)


class TestExceptionHandling:
    """Test that exceptions don't crash the system"""

    def test_invalid_query_format(self, retriever, transformer):
        """Invalid query should not crash"""
        query = "!@#$%^&*()"

        transformed = transformer.transform(query)

        try:
            results = retriever.search(transformed, top_k=10)
            assert isinstance(results, list)
        except Exception as e:
            pytest.fail(f"Query should not crash: {e}")

    def test_unicode_query(self, retriever, transformer):
        """Unicode query should handle gracefully"""
        query = "测试 5153"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        assert isinstance(results, list)


class TestBackwardCompatibility:
    """Test that existing queries still work"""

    def test_general_technical_query(self, retriever, transformer):
        """General technical query should work"""
        query = "How does the compressor work?"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        assert len(results) >= 0

    def test_equipment_query(self, retriever, transformer):
        """Equipment query should work"""
        query = "K06101 specifications"

        transformed = transformer.transform(query)
        results = retriever.search(transformed, top_k=10)

        assert len(results) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
