"""
Tests for Vector PDF Extractor
"""
import pytest
from pathlib import Path
from app.rag.extractors.vector_extractor import VectorExtractor, TextBlock


class TestVectorExtractor:
    """Test suite for VectorExtractor"""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance"""
        return VectorExtractor()
    
    @pytest.fixture
    def sample_pdfs(self):
        """Get paths to sample PDFs"""
        return {
            'text': Path('data/raw/samples/sample_text.pdf'),
            'mixed': Path('data/raw/samples/sample_mixed.pdf'),
            'datasheet': Path('data/raw/samples/sample_datasheet.pdf')
        }
    
    def test_extractor_initialization(self, extractor):
        """Test extractor initialization with default parameters"""
        assert extractor.merge_threshold == 10.0
        assert extractor.fix_hyphenation == True
    
    def test_text_block_dataclass(self):
        """Test TextBlock dataclass"""
        block = TextBlock(
            text="Sample text",
            bbox=(10, 20, 100, 30),
            page_num=0,
            block_num=1,
            font_size=11.0,
            font_name="Helvetica"
        )
        
        assert block.text == "Sample text"
        assert block.bbox == (10, 20, 100, 30)
        assert block.page_num == 0
        assert block.block_num == 1
        
        # Test to_dict conversion
        block_dict = block.to_dict()
        assert block_dict['text'] == "Sample text"
        assert block_dict['bbox'] == [10, 20, 100, 30]
        assert block_dict['font_size'] == 11.0
    
    def test_extract_from_text_pdf(self, extractor, sample_pdfs):
        """Test extraction from text-based PDF"""
        if not sample_pdfs['text'].exists():
            pytest.skip("Sample text PDF not found")
            
        result = extractor.extract_from_pdf(sample_pdfs['text'])
        
        assert 'file_path' in result
        assert 'total_pages' in result
        assert 'pages' in result
        assert 'statistics' in result
        
        assert result['total_pages'] == 2
        assert len(result['pages']) == 2
        
        # Check statistics
        stats = result['statistics']
        assert 'total_blocks' in stats
        assert 'total_characters' in stats
        assert 'avg_blocks_per_page' in stats
        assert stats['total_blocks'] > 0
        assert stats['total_characters'] > 0
    
    def test_extract_page_content(self, extractor, sample_pdfs):
        """Test page-level extraction"""
        if not sample_pdfs['text'].exists():
            pytest.skip("Sample text PDF not found")
            
        result = extractor.extract_from_pdf(sample_pdfs['text'])
        first_page = result['pages'][0]
        
        assert 'page_num' in first_page
        assert 'width' in first_page
        assert 'height' in first_page
        assert 'blocks' in first_page
        assert 'block_count' in first_page
        assert 'char_count' in first_page
        assert 'full_text' in first_page
        
        # Check dimensions (A4 size)
        assert first_page['width'] == 595
        assert first_page['height'] == 842
        
        # Check blocks
        assert first_page['block_count'] > 0
        assert len(first_page['blocks']) > 0
        
        # Check first block structure
        first_block = first_page['blocks'][0]
        assert 'text' in first_block
        assert 'bbox' in first_block
        assert 'page_num' in first_block
        assert 'block_num' in first_block
    
    def test_extract_with_structure(self, extractor, sample_pdfs):
        """Test extraction with structure detection"""
        if not sample_pdfs['text'].exists():
            pytest.skip("Sample text PDF not found")
            
        result = extractor.extract_with_structure(sample_pdfs['text'])
        
        # Check that structure types are assigned
        structure_types_found = set()
        for page in result['pages']:
            for block in page['blocks']:
                if 'structure_type' in block:
                    structure_types_found.add(block['structure_type'])
        
        # Should have detected headings and paragraphs
        assert len(structure_types_found) > 0
        # Common structure types
        possible_types = {'heading1', 'heading2', 'heading3', 'paragraph', 'unknown'}
        assert structure_types_found.issubset(possible_types)
    
    def test_text_content_extraction(self, extractor, sample_pdfs):
        """Test that actual text content is extracted correctly"""
        if not sample_pdfs['text'].exists():
            pytest.skip("Sample text PDF not found")
            
        result = extractor.extract_from_pdf(sample_pdfs['text'])
        
        # Check that we extracted the expected content
        full_text = ' '.join(page['full_text'] for page in result['pages'])
        
        # Should contain key phrases from our sample PDF
        assert "Technical Document Sample" in full_text
        assert "Equipment Specification KT06101" in full_text
        assert "Operating Parameters" in full_text
        assert "25 bar" in full_text  # Pressure value
        assert "Safety Instructions" in full_text
        assert "Maintenance Schedule" in full_text
    
    def test_datasheet_extraction(self, extractor, sample_pdfs):
        """Test extraction from datasheet PDF"""
        if not sample_pdfs['datasheet'].exists():
            pytest.skip("Sample datasheet PDF not found")
            
        result = extractor.extract_from_pdf(sample_pdfs['datasheet'])
        
        # Check that datasheet content is extracted
        full_text = result['pages'][0]['full_text']
        
        assert "DATASHEET" in full_text
        assert "KT06101" in full_text
        assert "CO2 COMPRESSOR" in full_text
        assert "Technical Specifications" in full_text
        
        # Check table-like content
        assert "Parameter" in full_text
        assert "Value" in full_text
        assert "Unit" in full_text
        assert "Centrifugal" in full_text
        assert "500" in full_text  # Capacity
        assert "m³/h" in full_text
    
    def test_reading_order_sorting(self, extractor, sample_pdfs):
        """Test that blocks are sorted in reading order"""
        if not sample_pdfs['text'].exists():
            pytest.skip("Sample text PDF not found")
            
        result = extractor.extract_from_pdf(sample_pdfs['text'])
        first_page = result['pages'][0]
        blocks = first_page['blocks']
        
        # Check that blocks are sorted top-to-bottom, left-to-right
        for i in range(1, len(blocks)):
            prev_block = blocks[i-1]
            curr_block = blocks[i]
            
            # If on same line (similar y), x should increase
            if abs(prev_block['bbox'][1] - curr_block['bbox'][1]) < 10:
                assert prev_block['bbox'][0] <= curr_block['bbox'][0]
    
    def test_nonexistent_file(self, extractor):
        """Test handling of nonexistent file"""
        with pytest.raises(FileNotFoundError):
            extractor.extract_from_pdf('nonexistent.pdf')
    
    def test_custom_parameters(self):
        """Test extractor with custom parameters"""
        extractor = VectorExtractor(
            merge_threshold=20.0,
            fix_hyphenation=False
        )
        
        assert extractor.merge_threshold == 20.0
        assert extractor.fix_hyphenation == False
