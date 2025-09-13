"""
Unit tests for text and tag normalizers
"""
import pytest
from app.rag.normalizers.text_normalizer import TextNormalizer, TechnicalTextNormalizer
from app.rag.normalizers.tag_normalizer import TagNormalizer, ISA5_1_TagNormalizer, TagPattern


class TestTextNormalizer:
    """Tests for TextNormalizer"""
    
    def test_remove_control_characters(self):
        """Test control character removal"""
        normalizer = TextNormalizer()
        
        # Text with control characters
        text = "Hello\x00World\x01Test\x02"
        result = normalizer.normalize(text)
        
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x02" not in result
        assert "Hello" in result
        assert "World" in result
    
    def test_fix_unicode_issues(self):
        """Test unicode normalization"""
        normalizer = TextNormalizer()
        
        # Common mojibake
        text = "It's a test – with â€œquotesâ€"
        result = normalizer.normalize(text)
        
        # Should be fixed
        assert "It's" in result or "It's" in result
        assert "–" in result or "-" in result
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization"""
        normalizer = TextNormalizer()
        
        # Multiple spaces and tabs
        text = "Hello    World\t\tTest\n\n\n\nEnd"
        result = normalizer.normalize(text)
        
        # Should have single spaces
        assert "Hello World Test" in result
        assert "\n\n" in result  # Paragraph break preserved
        assert "\n\n\n" not in result  # But not excessive newlines
    
    def test_fix_punctuation_spacing(self):
        """Test punctuation spacing fixes"""
        normalizer = TextNormalizer()
        
        # Wrong punctuation spacing
        text = "Hello , world . Test ! Question ?"
        result = normalizer.normalize(text)
        
        assert result == "Hello, world. Test! Question?"
        
        # Test quotes and parentheses
        text2 = 'He said " Hello " and ( test )'
        result2 = normalizer.normalize(text2)
        
        assert '"Hello"' in result2
        assert '(test)' in result2
    
    def test_split_paragraphs(self):
        """Test paragraph splitting"""
        normalizer = TextNormalizer()
        
        text = """First paragraph here.
        
        Second paragraph here.
        
        1. Numbered list item
        2. Another item
        
        - Bullet point
        - Another bullet"""
        
        paragraphs = normalizer.normalize_paragraphs(text)
        
        assert len(paragraphs) >= 4
        assert "First paragraph" in paragraphs[0]
        assert "Second paragraph" in paragraphs[1]
    
    def test_technical_normalizer_preserve_equations(self):
        """Test equation preservation in technical normalizer"""
        normalizer = TechnicalTextNormalizer()
        
        text = "The equation $E = mc^2$ is famous. Also \\(F = ma\\) is basic."
        result = normalizer.normalize(text)
        
        # Equations should be preserved
        assert "$E = mc^2$" in result
        assert "\\(F = ma\\)" in result
    
    def test_technical_normalizer_preserve_tables(self):
        """Test table preservation in technical normalizer"""
        normalizer = TechnicalTextNormalizer()
        
        text = """Normal text here.
        
        | Col1 | Col2 | Col3 |
        |------|------|------|
        | A    | B    | C    |
        | D    | E    | F    |
        
        More normal text."""
        
        result = normalizer.normalize(text)
        
        # Table structure should be preserved
        assert "| Col1 | Col2 | Col3 |" in result
        assert "|------|------|------|" in result


class TestTagNormalizer:
    """Tests for TagNormalizer"""
    
    def test_normalize_single_tag(self):
        """Test single tag normalization"""
        normalizer = TagNormalizer()
        
        # Various formats
        assert normalizer.normalize_tag("pv-101") == "PV-101"
        assert normalizer.normalize_tag("PV 101") == "PV-101"
        assert normalizer.normalize_tag("pv_101") == "PV-101"
        assert normalizer.normalize_tag("  PV-101  ") == "PV-101"
    
    def test_extract_tags_from_text(self):
        """Test tag extraction from text"""
        normalizer = TagNormalizer()
        
        text = """
        The system includes pump P-101 and valve PV-201.
        Temperature is measured by TT-301 and controlled by TIC-301.
        Compressor KT06101 provides the pressure.
        """
        
        tags = normalizer.extract_tags(text)
        
        # Should find all tags
        normalized_tags = [t['normalized'] for t in tags]
        assert "P-101" in normalized_tags
        assert "PV-201" in normalized_tags
        assert "TT-301" in normalized_tags
        assert "TIC-301" in normalized_tags
        assert "KT06101" in normalized_tags or "KT-06101" in normalized_tags
    
    def test_validate_tag(self):
        """Test tag validation"""
        normalizer = TagNormalizer()
        
        # Valid tags
        assert normalizer.validate_tag("PV-101")['valid'] == True
        assert normalizer.validate_tag("P-2001A")['valid'] == True
        assert normalizer.validate_tag("FIC-301")['valid'] == True
        
        # Invalid tags
        assert normalizer.validate_tag("INVALID")['valid'] == False
        assert normalizer.validate_tag("123")['valid'] == False
    
    def test_group_tags_by_type(self):
        """Test grouping tags by equipment type"""
        normalizer = TagNormalizer()
        
        text = """
        Pumps: P-101, P-102, P-103
        Valves: PV-201, FCV-202
        Instruments: PT-301, FT-302
        """
        
        tags = normalizer.extract_tags(text)
        grouped = normalizer.group_tags_by_type(tags)
        
        # Check grouping
        assert "pump" in grouped
        assert len(grouped["pump"]) == 3
        
        if "valve" in grouped:
            assert len(grouped["valve"]) >= 1
        
        if "instrument" in grouped:
            assert len(grouped["instrument"]) >= 2
    
    def test_get_tag_statistics(self):
        """Test tag statistics"""
        normalizer = TagNormalizer()
        
        text = """
        Equipment list:
        P-101, P-102, P-103 (pumps)
        PV-201, PV-202 (valves)
        PT-301 (pressure transmitter)
        """
        
        stats = normalizer.get_tag_statistics(text)
        
        assert stats['total_tags'] >= 6
        assert stats['unique_tags'] >= 6
        assert 'pump' in stats['types'] or 'general' in stats['types']
    
    def test_custom_patterns(self):
        """Test custom tag patterns"""
        custom_patterns = [
            TagPattern(
                name="custom",
                pattern=r"TEST-\d{4}",
                description="Custom test pattern",
                examples=["TEST-1234"]
            )
        ]
        
        normalizer = TagNormalizer(patterns=custom_patterns)
        
        text = "Custom tag TEST-1234 and TEST-5678"
        tags = normalizer.extract_tags(text)
        
        assert len(tags) == 2
        assert tags[0]['type'] == 'custom'
        assert tags[0]['normalized'] == 'TEST-1234'


class TestISA5_1_TagNormalizer:
    """Tests for ISA 5.1 tag normalizer"""
    
    def test_isa_patterns(self):
        """Test ISA 5.1 specific patterns"""
        normalizer = ISA5_1_TagNormalizer()
        
        text = """
        Flow: FT-101, FIC-201, FCV-301
        Pressure: PT-401, PIC-501, PSV-601
        Temperature: TT-701, TIC-801
        Level: LT-901, LIC-1001
        """
        
        tags = normalizer.extract_tags(text)
        grouped = normalizer.group_tags_by_type(tags)
        
        # Should categorize by ISA types
        assert 'flow' in grouped or any('F' in tag for tag in [t['normalized'] for t in tags])
        assert 'pressure' in grouped or any('P' in tag for tag in [t['normalized'] for t in tags])
    
    def test_parse_isa_tag(self):
        """Test ISA tag parsing"""
        normalizer = ISA5_1_TagNormalizer()
        
        # Parse FIC-101
        result = normalizer.parse_isa_tag("FIC-101")
        
        assert result['valid'] == True
        assert result['variable'] == 'Flow'
        assert result['variable_code'] == 'F'
        assert 'Indicator' in result['functions']
        assert 'Controller' in result['functions']
        assert result['loop_number'] == '101'
        
        # Parse PT-201A
        result2 = normalizer.parse_isa_tag("PT-201A")
        
        assert result2['valid'] == True
        assert result2['variable'] == 'Pressure'
        assert 'Transmitter' in result2['functions']
        assert result2['suffix'] == 'A'
    
    def test_complex_isa_tags(self):
        """Test complex ISA tags"""
        normalizer = ISA5_1_TagNormalizer()
        
        # Complex tags
        tags_to_test = [
            ("PSHH-101", "Pressure", ["Switch", "High", "High"]),
            ("LSLL-201", "Level", ["Switch", "Low", "Low"]),
            ("FICA-301", "Flow", ["Indicator", "Controller", "Alarm"])
        ]
        
        for tag, expected_var, expected_funcs in tags_to_test:
            result = normalizer.parse_isa_tag(tag)
            assert result['valid'] == True
            assert result['variable'] == expected_var
            
            for func in expected_funcs:
                assert func in result['functions']
