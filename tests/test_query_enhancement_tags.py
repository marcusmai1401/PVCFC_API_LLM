"""
Week 2: Query Enhancement - Tag Detection and Expansion Tests

Tests the tag detection and query expansion logic for equipment tag queries.
"""
import pytest

from app.rag.query_transform import QueryIntent, QueryTransformer


class TestTagDetection:
    """Test equipment tag detection in queries"""

    def setup_method(self):
        """Setup test fixtures"""
        self.transformer = QueryTransformer(enable_hyde=False, remove_stopwords=False)

    def test_detect_full_tag_with_prefix(self):
        """Test detection of full tag with prefix: 06-TE-0256"""
        query = "What is the alarm setting for 06-TE-0256?"
        tags = self.transformer.detect_equipment_tags(query)

        assert tags is not None, "Should detect equipment tag"
        assert "06-TE-0256" in tags, f"Should detect '06-TE-0256', got {tags}"

    def test_detect_tag_without_dashes(self):
        """Test detection of tag without separators: 06TE0256"""
        query = "Show me information about 06TE0256"
        tags = self.transformer.detect_equipment_tags(query)

        assert tags is not None, "Should detect equipment tag"
        # Should normalize to dash format
        assert "06TE0256" in tags, f"Should detect '06TE0256', got {tags}"

    def test_detect_partial_tag(self):
        """Test detection of partial tag without prefix: TE-0256"""
        query = "What is TE-0256 used for?"
        tags = self.transformer.detect_equipment_tags(query)

        assert tags is not None, "Should detect partial equipment tag"
        assert "TE-0256" in tags, f"Should detect 'TE-0256', got {tags}"

    def test_detect_tag_with_suffix(self):
        """Test detection of tag with alphabetic suffix: P-101A"""
        query = "Status of pump P-101A"
        tags = self.transformer.detect_equipment_tags(query)

        assert tags is not None, "Should detect tag with suffix"
        assert "P-101A" in tags, f"Should detect 'P-101A', got {tags}"

    def test_detect_tag_with_slash_suffix(self):
        """Test detection of tag with slash suffix: 06-TE-0256 A/B"""
        query = "Check temperature sensor 06-TE-0256 A/B status"
        tags = self.transformer.detect_equipment_tags(query)

        assert tags is not None, "Should detect tag with slash suffix"
        # Should detect the base tag part
        found = any("0256" in tag for tag in tags)
        assert found, f"Should detect tag containing '0256', got {tags}"

    def test_detect_multiple_tags(self):
        """Test detection of multiple tags in one query"""
        query = "Compare readings from TE-0255, TE-0256, and TG-0202"
        tags = self.transformer.detect_equipment_tags(query)

        assert tags is not None, "Should detect multiple tags"
        assert len(tags) >= 3, f"Should detect at least 3 tags, got {len(tags)}: {tags}"

        # Check specific tags
        assert any("0255" in t for t in tags), "Should detect TE-0255"
        assert any("0256" in t for t in tags), "Should detect TE-0256"
        assert any("0202" in t for t in tags), "Should detect TG-0202"

    def test_no_false_positives_on_numbers(self):
        """Test that plain numbers are not detected as tags"""
        query = "What is the pressure at 150 bar?"
        tags = self.transformer.detect_equipment_tags(query)

        # Should not detect "150" as a tag (no letter prefix)
        if tags:
            assert not any(
                t == "150" for t in tags
            ), "Should not detect plain numbers as tags"

    def test_no_detection_in_plain_text(self):
        """Test that queries without tags return None"""
        query = "What is the operating temperature of the compressor?"
        tags = self.transformer.detect_equipment_tags(query)

        # Query has no equipment tags
        assert (
            tags is None or len(tags) == 0
        ), "Should not detect tags in plain text query"


class TestTagExpansion:
    """Test tag query expansion with variants"""

    def setup_method(self):
        """Setup test fixtures"""
        self.transformer = QueryTransformer(enable_hyde=False, remove_stopwords=False)

    def test_expand_full_tag_variants(self):
        """Test expansion of full tag into all variants"""
        tag = "06-TE-0256"
        variants = self.transformer._generate_tag_variants(tag)

        assert (
            len(variants) >= 4
        ), f"Should generate at least 4 variants, got {len(variants)}"

        # Check expected variants
        assert "06-TE-0256" in variants, "Should include original"
        assert "06 TE 0256" in variants, "Should include space variant"
        assert "06TE0256" in variants, "Should include no-separator variant"
        assert (
            "TE-0256" in variants or "TE0256" in variants
        ), "Should include partial variant"

    def test_expand_partial_tag_variants(self):
        """Test expansion of partial tag (no prefix)"""
        tag = "TE-0256"
        variants = self.transformer._generate_tag_variants(tag)

        assert "TE-0256" in variants, "Should include original"
        assert "TE 0256" in variants, "Should include space variant"
        assert "TE0256" in variants, "Should include no-separator variant"

    def test_expand_query_with_single_tag(self):
        """Test query expansion with single detected tag"""
        normalized_query = "alarm setting 06-te-0256"
        detected_tags = ["06-TE-0256"]

        expanded = self.transformer.expand_tag_query(normalized_query, detected_tags)

        assert expanded is not None, "Should return expanded query"
        assert "06-TE-0256" in expanded, "Should include original tag"
        assert "06 TE 0256" in expanded, "Should include space variant"
        assert "06TE0256" in expanded, "Should include no-separator variant"
        assert " OR " in expanded, "Should use OR operator for variants"

    def test_expand_query_with_multiple_tags(self):
        """Test query expansion with multiple detected tags"""
        normalized_query = "compare te-0255 te-0256"
        detected_tags = ["TE-0255", "TE-0256"]

        expanded = self.transformer.expand_tag_query(normalized_query, detected_tags)

        assert expanded is not None, "Should return expanded query"

        # Should include variants of both tags
        assert "TE-0255" in expanded, "Should include first tag"
        assert "TE-0256" in expanded, "Should include second tag"
        assert "TE0255" in expanded, "Should include no-separator variant of first tag"
        assert "TE0256" in expanded, "Should include no-separator variant of second tag"

    def test_expand_query_preserves_original(self):
        """Test that expansion preserves the original query text"""
        normalized_query = "what is the alarm setting for 06-te-0256"
        detected_tags = ["06-TE-0256"]

        expanded = self.transformer.expand_tag_query(normalized_query, detected_tags)

        # Original query should be at the start
        assert expanded.startswith(
            normalized_query
        ), "Should preserve original query at start"


class TestTagQueryTransformation:
    """Test end-to-end tag query transformation"""

    def setup_method(self):
        """Setup test fixtures"""
        self.transformer = QueryTransformer(enable_hyde=False, remove_stopwords=False)

    def test_transform_query_with_tag(self):
        """Test full transformation of query containing equipment tag"""
        query = "What is the alarm setting for 06-TE-0256?"

        result = self.transformer.transform(query, language="en")

        assert result is not None, "Should return TransformedQuery"
        assert result.detected_tags is not None, "Should detect tags"
        assert len(result.detected_tags) > 0, "Should detect at least one tag"
        assert result.expanded_query is not None, "Should generate expanded query"

        # Check metadata
        assert (
            result.metadata["has_tags"] is True
        ), "Metadata should indicate tags present"
        assert result.metadata["tag_count"] > 0, "Metadata should count tags"

    def test_transform_query_without_tag(self):
        """Test transformation of query without equipment tags"""
        query = "What is the operating temperature of the compressor?"

        result = self.transformer.transform(query, language="en")

        assert result is not None, "Should return TransformedQuery"
        assert (
            result.detected_tags is None or len(result.detected_tags) == 0
        ), "Should not detect tags"
        assert (
            result.expanded_query is None
        ), "Should not generate expanded query for tagless query"

        # Check metadata
        assert result.metadata["has_tags"] is False, "Metadata should indicate no tags"
        assert result.metadata["tag_count"] == 0, "Metadata should show zero tags"

    def test_tag_query_intent_is_ask_not_locate(self):
        """Test that tag-only queries are classified as ASK, not LOCATE"""
        query = "06-TE-0256"

        result = self.transformer.transform(query, language="en")

        # Equipment tag without 'where/find/locate' should be ASK intent
        assert (
            result.intent == QueryIntent.ASK
        ), f"Tag query should be ASK intent, got {result.intent}"

    def test_tag_with_locate_keyword_is_locate(self):
        """Test that tag queries with location keywords are LOCATE"""
        query = "Where is 06-TE-0256 located?"

        result = self.transformer.transform(query, language="en")

        # Explicit location keyword should override and be LOCATE
        assert (
            result.intent == QueryIntent.LOCATE
        ), f"Tag query with 'where' should be LOCATE intent, got {result.intent}"

    def test_tag_with_specification_question_is_ask(self):
        """Test that tag queries asking for specs are ASK"""
        query = "What is the alarm setpoint for 06-TE-0256?"

        result = self.transformer.transform(query, language="en")

        assert (
            result.intent == QueryIntent.ASK
        ), f"Specification query should be ASK intent, got {result.intent}"
        assert result.detected_tags is not None, "Should detect equipment tag"


class TestTagDetectionEdgeCases:
    """Test edge cases and boundary conditions for tag detection"""

    def setup_method(self):
        """Setup test fixtures"""
        self.transformer = QueryTransformer(enable_hyde=False, remove_stopwords=False)

    def test_tag_at_start_of_query(self):
        """Test detection when tag is at the start"""
        query = "06-TE-0256 alarm setting"
        tags = self.transformer.detect_equipment_tags(query)

        assert tags is not None, "Should detect tag at start"
        assert any("0256" in t for t in tags), "Should detect 06-TE-0256"

    def test_tag_at_end_of_query(self):
        """Test detection when tag is at the end"""
        query = "What is the alarm setting for 06-TE-0256"
        tags = self.transformer.detect_equipment_tags(query)

        assert tags is not None, "Should detect tag at end"
        assert any("0256" in t for t in tags), "Should detect 06-TE-0256"

    def test_tag_in_mixed_case(self):
        """Test detection of tag in mixed case"""
        query = "Check sensor 06-te-0256 status"
        tags = self.transformer.detect_equipment_tags(query)

        assert tags is not None, "Should detect tag in mixed case"
        # Should normalize to uppercase
        assert any(
            "TE" in t and "0256" in t for t in tags
        ), "Should detect and normalize 06-te-0256"

    def test_common_equipment_types(self):
        """Test detection of common equipment type prefixes"""
        test_cases = [
            ("Pump P-101 status", "P-101"),
            ("Valve V-303 position", "V-303"),
            ("Heat exchanger E-404", "E-404"),
            ("Compressor K-201", "K-201"),
            ("Tank T-105", "T-105"),
        ]

        for query, expected_tag in test_cases:
            tags = self.transformer.detect_equipment_tags(query)
            assert tags is not None, f"Should detect tag in '{query}'"
            assert any(
                expected_tag in t for t in tags
            ), f"Should detect '{expected_tag}' in '{query}', got {tags}"


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
