"""
Unit tests for tag normalization utilities
"""
import pytest

from app.utils.tag_utils import (
    extract_tags_from_text,
    find_tag_variations,
    get_equipment_type,
    is_valid_tag,
    normalize_tag,
    split_multi_line_tag,
)


class TestNormalizeTag:
    """Test tag normalization"""

    def test_normalize_basic(self):
        """Test basic normalization"""
        assert normalize_tag("06 PT001") == "06PT001"
        assert normalize_tag("PT-001") == "PT001"
        assert normalize_tag("04 FE 2046") == "04FE2046"
        assert normalize_tag("e04217") == "E04217"

    def test_normalize_with_special_chars(self):
        """Test normalization with special characters"""
        assert normalize_tag("04-FE-2046") == "04FE2046"
        assert normalize_tag("04_FE_2046") == "04FE2046"
        assert normalize_tag("04/FE/2046") == "04FE2046"
        assert normalize_tag("04\\FE\\2046") == "04FE2046"

    def test_normalize_mixed_case(self):
        """Test case conversion"""
        assert normalize_tag("kt06101") == "KT06101"
        assert normalize_tag("Kt06101") == "KT06101"
        assert normalize_tag("KT06101") == "KT06101"

    def test_normalize_empty(self):
        """Test empty input"""
        assert normalize_tag("") == ""
        assert normalize_tag(None) == ""
        assert normalize_tag("   ") == ""


class TestExtractTags:
    """Test tag extraction from text"""

    def test_extract_simple_tags(self):
        """Test extracting simple tags"""
        text = "The equipment KT06101 is connected to valve 04FE2046"
        tags = extract_tags_from_text(text)
        assert "KT06101" in tags
        assert "04FE2046" in tags

    def test_extract_with_separators(self):
        """Test extracting tags with separators"""
        text = "Check 04-FE-2046 and 06 PT 001 for pressure"
        tags = extract_tags_from_text(text)
        assert "04FE2046" in tags
        assert "06PT001" in tags

    def test_extract_mixed_case(self):
        """Test extracting mixed case tags"""
        text = "Equipment kt06101 and E04217 need maintenance"
        tags = extract_tags_from_text(text)
        assert "KT06101" in tags
        assert "E04217" in tags

    def test_extract_no_tags(self):
        """Test text with no valid tags"""
        text = "This is regular text without any equipment tags"
        tags = extract_tags_from_text(text)
        assert len(tags) == 0

    def test_extract_complex_text(self):
        """Test extracting from complex P&ID text"""
        text = """
        Unit 04 contains:
        - Flow element 04FE2046
        - Pressure transmitter 04PT2508
        - Pressure gauge 04PG4271
        - Heat exchanger E04217
        """
        tags = extract_tags_from_text(text)
        assert "04FE2046" in tags
        assert "04PT2508" in tags
        assert "04PG4271" in tags
        assert "E04217" in tags


class TestValidateTag:
    """Test tag validation"""

    def test_valid_tags(self):
        """Test valid tag formats"""
        assert is_valid_tag("KT06101") == True
        assert is_valid_tag("04FE2046") == True
        assert is_valid_tag("E04217") == True
        assert is_valid_tag("PT001") == True
        assert is_valid_tag("XV101") == True

    def test_invalid_tags(self):
        """Test invalid tag formats"""
        assert is_valid_tag("ABC") == False  # Too short
        assert is_valid_tag("1234") == False  # Only digits
        assert is_valid_tag("ABCD") == False  # Only letters
        assert is_valid_tag("AB") == False  # Too short
        assert is_valid_tag("") == False  # Empty


class TestMultiLineTag:
    """Test multi-line tag handling"""

    def test_split_tag_simple(self):
        """Test simple multi-line tag"""
        lines = ["04", "PT", "4264"]
        result = split_multi_line_tag(lines)
        assert result == "04PT4264"

    def test_split_tag_with_spaces(self):
        """Test multi-line tag with spaces"""
        lines = [" 04 ", " FE ", " 2046 "]
        result = split_multi_line_tag(lines)
        assert result == "04FE2046"

    def test_split_tag_invalid(self):
        """Test invalid multi-line input"""
        assert split_multi_line_tag([]) == None
        assert split_multi_line_tag(["Random", "Text"]) == None


class TestTagVariations:
    """Test tag variation generation"""

    def test_variations_with_unit(self):
        """Test variations for tag with unit prefix"""
        variations = find_tag_variations("04FE2046")
        assert "04FE2046" in variations
        assert "04-FE-2046" in variations
        assert "04 FE 2046" in variations
        assert "FE2046" in variations  # Without unit
        assert "fe2046" in variations  # Lowercase

    def test_variations_without_unit(self):
        """Test variations for tag without unit prefix"""
        variations = find_tag_variations("PT001")
        assert "PT001" in variations
        assert "PT-001" in variations
        assert "PT 001" in variations
        assert "pt001" in variations

    def test_variations_empty(self):
        """Test empty input"""
        variations = find_tag_variations("")
        assert len(variations) == 0


class TestEquipmentType:
    """Test equipment type identification"""

    def test_get_equipment_type(self):
        """Test equipment type recognition"""
        assert get_equipment_type("04FE2046") == "Flow Element"
        assert get_equipment_type("PT001") == "Pressure Transmitter"
        assert get_equipment_type("KT06101") == "Knockout Tank"
        assert get_equipment_type("E04217") == "Heat Exchanger"
        assert get_equipment_type("XV101") == "On/Off Valve"

    def test_unknown_equipment_type(self):
        """Test unknown equipment type"""
        assert get_equipment_type("XYZ123") == None
        assert get_equipment_type("") == None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
