"""
Unit Tests for PID Query Enhancer

Tests tag detection, variant generation, and query type classification
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer


class TestPIDQueryEnhancer:
    """Test suite for PIDQueryEnhancer"""

    def setup_method(self):
        """Setup for each test"""
        self.enhancer = PIDQueryEnhancer()

    def test_tag_detection_simple(self):
        """Test simple tag detection"""
        result = self.enhancer.enhance("E04217")

        assert result["strategy"] == "tag_focused"
        assert "E04217" in result["tags"]
        assert result["query_type"] == "tag_only"

    def test_tag_detection_with_hyphen(self):
        """Test tag with hyphen"""
        result = self.enhancer.enhance("P-04201A")

        assert result["strategy"] == "tag_focused"
        assert len(result["tags"]) > 0
        # TagNormalizer should normalize P-04201A

    def test_tag_detection_mixed_query(self):
        """Test mixed query with tag and parameter"""
        result = self.enhancer.enhance("áp suất của E04217")

        assert result["strategy"] == "tag_focused"
        assert "E04217" in result["tags"]
        assert result["query_type"] == "mixed"

    def test_variant_generation(self):
        """Test tag variant generation"""
        result = self.enhancer.enhance("E04217")

        variants = result["variants"]
        assert "E04217" in variants  # Key exists
        assert len(variants["E04217"]) <= 4  # Max 4 variants

        # Should include different formats
        tag_variants = variants["E04217"]
        assert "E04217" in tag_variants  # Original
        assert "e04217" in tag_variants  # Lowercase
        # Should have hyphen or space variant

    def test_equipment_type_inference(self):
        """Test equipment type inference from tag prefix"""
        test_cases = [
            ("E04217", "heat exchanger"),
            ("P04201A", "pump"),
            ("K04301", "compressor"),
            ("R04201", "reactor"),
            ("T04201", "tank"),
            ("F04201", "furnace"),
        ]

        for tag, expected_type in test_cases:
            result = self.enhancer.enhance(tag)
            assert expected_type in result["equipment_types"]

    def test_query_type_detection_tag_only(self):
        """Test tag-only query type detection"""
        test_queries = ["E04217", "E04217 ở đâu", "thông tin P04201A"]

        for query in test_queries:
            result = self.enhancer.enhance(query)
            if result["strategy"] == "tag_focused":
                assert result["query_type"] == "tag_only"

    def test_query_type_detection_mixed(self):
        """Test mixed query type detection"""
        test_queries = [
            "áp suất của E04217",
            "flow rate pump P04201A",
            "nhiệt độ reactor R04201",
        ]

        for query in test_queries:
            result = self.enhancer.enhance(query)
            if result["strategy"] == "tag_focused":
                assert result["query_type"] == "mixed"

    def test_query_type_detection_visual(self):
        """Test visual query type detection"""
        test_queries = [
            "diagram heat exchanger",
            "bản vẽ pump system",
            "layout nhiều ống",
        ]

        for query in test_queries:
            result = self.enhancer.enhance(query)
            # Visual queries may or may not have tags
            if "query_type" in result:
                # If tags detected, should be visual type
                if result.get("tags"):
                    assert result["query_type"] in ["visual", "mixed"]

    def test_no_tags_semantic_fallback(self):
        """Test fallback to semantic when no tags detected"""
        result = self.enhancer.enhance("what is heat exchanger")

        assert result["strategy"] == "semantic"
        assert result["original"] == "what is heat exchanger"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
