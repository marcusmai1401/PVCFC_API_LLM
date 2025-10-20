"""
Unit tests for P&ID enhancements

Tests:
- Tag pattern matching (UNIT 1-3 digits, PREFIX 2-6 letters)
- Component parsing (partial queries)
- SUFFIX-only detection
- Annotation separation
- Variant extraction
- Multi-prefix grouping
"""
import pytest

from app.rag.normalizers.tag_normalizer import TagNormalizer
from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer


class TestTagNormalizerEnhancements:
    """Test TagNormalizer with new patterns"""

    def setup_method(self):
        """Setup for each test"""
        self.normalizer = TagNormalizer()

    def test_parse_tag_with_unit(self):
        """Test parsing tag with UNIT"""
        result = self.normalizer.parse_tag_components("04 PAHH 5153")

        assert result is not None
        assert result["unit"] == "04"
        assert result["prefix"] == "PAHH"
        assert result["suffix"] == "5153"
        assert result["variant"] == ""
        assert result["annotation"] == ""

    def test_parse_tag_without_unit(self):
        """Test parsing tag without UNIT"""
        result = self.normalizer.parse_tag_components("PSAL 2207")

        assert result is not None
        assert result["unit"] == ""
        assert result["prefix"] == "PSAL"
        assert result["suffix"] == "2207"
        assert result["variant"] == ""

    def test_parse_tag_with_variant(self):
        """Test parsing tag with variant"""
        result = self.normalizer.parse_tag_components("04 ZSL 4047A")

        assert result is not None
        assert result["unit"] == "04"
        assert result["prefix"] == "ZSL"
        assert result["suffix"] == "4047"
        assert result["variant"] == "A"

    def test_parse_tag_with_annotation(self):
        """Test parsing tag with annotation"""
        result = self.normalizer.parse_tag_components("04 PAHH 5153A/B/C")

        assert result is not None
        assert result["unit"] == "04"
        assert result["prefix"] == "PAHH"
        assert result["suffix"] == "5153"
        assert result["annotation"] == "A/B/C"

    def test_parse_tag_with_voting_logic(self):
        """Test parsing tag with voting logic annotation"""
        result = self.normalizer.parse_tag_components("04 PSAL 2207 2oo3")

        assert result is not None
        assert result["prefix"] == "PSAL"
        assert result["suffix"] == "2207"
        assert result["annotation"] == "2oo3"

    def test_unit_1_digit(self):
        """Test UNIT with 1 digit"""
        result = self.normalizer.parse_tag_components("4 IS 501")

        assert result is not None
        assert result["unit"] == "4"
        assert result["prefix"] == "IS"
        assert result["suffix"] == "501"

    def test_unit_3_digits(self):
        """Test UNIT with 3 digits"""
        result = self.normalizer.parse_tag_components("120 PSAL 2207")

        assert result is not None
        assert result["unit"] == "120"
        assert result["prefix"] == "PSAL"
        assert result["suffix"] == "2207"

    def test_prefix_5_letters(self):
        """Test PREFIX with 5 letters"""
        result = self.normalizer.parse_tag_components("04 PDAHH 5145")

        assert result is not None
        assert result["prefix"] == "PDAHH"
        assert len(result["prefix"]) == 5

    def test_prefix_6_letters(self):
        """Test PREFIX with 6 letters (label case)"""
        result = self.normalizer.parse_tag_components("04 HEADER 123")

        assert result is not None
        assert result["prefix"] == "HEADER"
        assert len(result["prefix"]) == 6


class TestPIDQueryEnhancer:
    """Test PIDQueryEnhancer with new features"""

    def setup_method(self):
        """Setup for each test"""
        self.enhancer = PIDQueryEnhancer()

    def test_detect_suffix_only(self):
        """Test SUFFIX-only query detection"""
        result = self.enhancer.enhance("5153")

        assert result["strategy"] == "suffix_search"
        assert result["suffix"] == "5153"
        assert result["query_type"] == "suffix_only"
        assert "warning" in result

    def test_detect_suffix_3_digits(self):
        """Test 3-digit SUFFIX"""
        result = self.enhancer.enhance("501")

        assert result["strategy"] == "suffix_search"
        assert result["suffix"] == "501"

    def test_detect_suffix_5_digits(self):
        """Test 5-digit SUFFIX"""
        result = self.enhancer.enhance("22076")

        assert result["strategy"] == "suffix_search"
        assert result["suffix"] == "22076"

    def test_component_query_unit_suffix(self):
        """Test component query with UNIT + SUFFIX"""
        result = self.enhancer.enhance("04 5153")

        assert result["strategy"] == "component_search"
        assert result["components"]["unit"] == "04"
        assert result["components"]["suffix"] == "5153"

    def test_component_query_prefix_suffix(self):
        """Test component query with PREFIX + SUFFIX"""
        result = self.enhancer.enhance("PAHH 5153")

        assert result["strategy"] == "component_search"
        assert result["components"]["prefix"] == "PAHH"
        assert result["components"]["suffix"] == "5153"

    def test_component_query_full_tag(self):
        """Test full tag as component query"""
        result = self.enhancer.enhance("04 PAHH 5153")

        assert result["strategy"] == "component_search"
        assert result["components"]["unit"] == "04"
        assert result["components"]["prefix"] == "PAHH"
        assert result["components"]["suffix"] == "5153"

    def test_component_query_unit_prefix(self):
        """Test component query with UNIT + PREFIX only"""
        result = self.enhancer.enhance("04 PAHH")

        assert result["strategy"] == "component_search"
        assert result["components"]["unit"] == "04"
        assert result["components"]["prefix"] == "PAHH"

    def test_non_suffix_query(self):
        """Test query that is NOT suffix-only (too short)"""
        result = self.enhancer.enhance("12")

        # Should NOT be detected as suffix (< 3 digits)
        assert result["strategy"] != "suffix_search"

    def test_non_suffix_query_too_long(self):
        """Test query that is NOT suffix-only (too long)"""
        result = self.enhancer.enhance("123456")

        # Should NOT be detected as suffix (> 5 digits)
        assert result["strategy"] != "suffix_search"


class TestAnnotationSeparation:
    """Test annotation separation logic"""

    def setup_method(self):
        """Setup for each test"""
        self.normalizer = TagNormalizer()

    def test_separate_ab(self):
        """Test A/B annotation separation"""
        result = self.normalizer.parse_tag_components("04 PSAL 2207 A/B")

        assert result["suffix"] == "2207"
        assert result["annotation"] == "A/B"
        assert "A/B" not in result["normalized"]

    def test_separate_abc(self):
        """Test A/B/C annotation separation"""
        result = self.normalizer.parse_tag_components("04 PAHH 5153A/B/C")

        assert result["suffix"] == "5153"
        assert result["annotation"] == "A/B/C"
        assert result["normalized"] == "04 PAHH 5153"

    def test_separate_voting_logic(self):
        """Test voting logic annotation separation"""
        result = self.normalizer.parse_tag_components("04 PSAL 2207 2oo3")

        assert result["suffix"] == "2207"
        assert result["annotation"] == "2oo3"
        assert "2oo3" not in result["normalized"]

    def test_no_annotation(self):
        """Test tag without annotation"""
        result = self.normalizer.parse_tag_components("04 IS 501")

        assert result["suffix"] == "501"
        assert result["annotation"] == ""
        assert result["normalized"] == "04 IS 501"


class TestVariantExtraction:
    """Test variant extraction"""

    def setup_method(self):
        """Setup"""
        self.normalizer = TagNormalizer()

    def test_variant_a(self):
        """Test variant A"""
        result = self.normalizer.parse_tag_components("04 ZSL 4047A")

        assert result["suffix"] == "4047"
        assert result["variant"] == "A"

    def test_variant_b(self):
        """Test variant B"""
        result = self.normalizer.parse_tag_components("04 PSAL 2207B")

        assert result["suffix"] == "2207"
        assert result["variant"] == "B"

    def test_no_variant(self):
        """Test tag without variant"""
        result = self.normalizer.parse_tag_components("04 IS 501")

        assert result["suffix"] == "501"
        assert result["variant"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
