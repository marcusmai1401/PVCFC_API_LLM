"""
Standalone unit tests for VectorExtractor
Creates test PDFs programmatically without external data
"""
import pytest
from pathlib import Path
import fitz  # PyMuPDF
from app.rag.extractors.vector_extractor import VectorExtractor, TextBlock


def create_test_pdf(tmp_path: Path, lines: list, filename: str = "test.pdf") -> Path:
    """
    Create a test PDF with given text lines
    
    Args:
        tmp_path: Temporary directory path
        lines: List of text lines to add
        filename: Output filename
        
    Returns:
        Path to created PDF
    """
    doc = fitz.open()
    page = doc.new_page()
    
    y_position = 72  # Start from top margin
    for line in lines:
        if isinstance(line, tuple):
            # (text, fontsize) format
            text, fontsize = line
            page.insert_text((72, y_position), text, fontsize=fontsize)
            y_position += fontsize * 1.5
        else:
            # Simple text
            page.insert_text((72, y_position), line, fontsize=12)
            y_position += 18
    
    output_path = tmp_path / filename
    doc.save(str(output_path))
    doc.close()
    
    return output_path


def create_multipage_pdf(tmp_path: Path, pages_content: list, filename: str = "multipage.pdf") -> Path:
    """
    Create a multi-page test PDF
    
    Args:
        tmp_path: Temporary directory path
        pages_content: List of page contents (each is a list of lines)
        filename: Output filename
        
    Returns:
        Path to created PDF
    """
    doc = fitz.open()
    
    for page_lines in pages_content:
        page = doc.new_page()
        y_position = 72
        
        for line in page_lines:
            if isinstance(line, tuple):
                text, fontsize = line
                page.insert_text((72, y_position), text, fontsize=fontsize)
                y_position += fontsize * 1.5
            else:
                page.insert_text((72, y_position), line, fontsize=12)
                y_position += 18
    
    output_path = tmp_path / filename
    doc.save(str(output_path))
    doc.close()
    
    return output_path


def create_rotated_pdf(tmp_path: Path, text: str, rotation: int = 90) -> Path:
    """
    Create a PDF with rotated page
    
    Args:
        tmp_path: Temporary directory path
        text: Text to add
        rotation: Rotation angle (0, 90, 180, 270)
        
    Returns:
        Path to created PDF
    """
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    page.set_rotation(rotation)
    
    output_path = tmp_path / "rotated.pdf"
    doc.save(str(output_path))
    doc.close()
    
    return output_path


class TestVectorExtractorStandalone:
    """Standalone tests for VectorExtractor without external dependencies"""
    
    def test_simple_extraction(self, tmp_path):
        """Test basic text extraction from simple PDF"""
        # Create test PDF
        pdf_path = create_test_pdf(tmp_path, [
            "Hello World",
            "This is a test PDF",
            "Created with PyMuPDF"
        ])
        
        # Extract text
        extractor = VectorExtractor()
        result = extractor.extract_from_pdf(pdf_path)
        
        # Verify results
        assert result['total_pages'] == 1
        assert len(result['pages']) == 1
        
        page_data = result['pages'][0]
        assert page_data['page_num'] == 0
        assert "Hello World" in page_data['full_text']
        assert "test PDF" in page_data['full_text']
        assert page_data['block_count'] > 0
    
    def test_hyphenation_handling(self, tmp_path):
        """Test hyphenation fix functionality"""
        # Create PDF with hyphenated text
        pdf_path = create_test_pdf(tmp_path, [
            "This is a hyphen-",
            "ated word example",
            "Another line here"
        ])
        
        # Extract with hyphenation fix
        extractor = VectorExtractor(fix_hyphenation=True)
        result = extractor.extract_from_pdf(pdf_path)
        
        page_text = result['pages'][0]['full_text']
        
        # Should merge hyphenated word
        assert "hyphenated" in page_text or "hyphen-ated" in page_text
        assert page_text.count('-') <= 1  # At most one hyphen (if not merged)
    
    def test_merge_nearby_blocks(self, tmp_path):
        """Test merging of nearby text blocks"""
        # Create PDF with closely spaced text
        pdf_path = create_test_pdf(tmp_path, [
            "First part",
            "Second part",
            "Third part"
        ])
        
        # Extract without merging
        extractor_no_merge = VectorExtractor(merge_threshold=0)
        result_no_merge = extractor_no_merge.extract_from_pdf(pdf_path)
        
        # Extract with merging
        extractor_merge = VectorExtractor(merge_threshold=50)
        result_merge = extractor_merge.extract_from_pdf(pdf_path)
        
        # With high merge threshold, should have fewer blocks
        blocks_no_merge = result_no_merge['pages'][0]['block_count']
        blocks_merge = result_merge['pages'][0]['block_count']
        
        assert blocks_no_merge >= blocks_merge
        
        # Text content should be the same
        text_no_merge = result_no_merge['pages'][0]['full_text']
        text_merge = result_merge['pages'][0]['full_text']
        
        # Both should contain all parts
        for part in ["First part", "Second part", "Third part"]:
            assert part in text_no_merge
            assert part in text_merge
    
    def test_rotation_preserved(self, tmp_path):
        """Test that rotation information is preserved"""
        # Create rotated PDF
        pdf_path = create_rotated_pdf(tmp_path, "Rotated text", rotation=90)
        
        # Extract
        extractor = VectorExtractor()
        result = extractor.extract_from_pdf(pdf_path)
        
        # Check rotation is preserved
        page_data = result['pages'][0]
        assert 'rotation' in page_data
        assert page_data['rotation'] == 90
    
    def test_font_information_extraction(self, tmp_path):
        """Test extraction of font size and name"""
        # Create PDF with different font sizes
        pdf_path = create_test_pdf(tmp_path, [
            ("Large Heading", 20),
            ("Medium Subheading", 14),
            ("Normal text content", 11),
            ("Small footnote", 8)
        ])
        
        # Extract
        extractor = VectorExtractor()
        result = extractor.extract_from_pdf(pdf_path)
        
        blocks = result['pages'][0]['blocks']
        
        # Check font sizes are captured
        font_sizes = [b['font_size'] for b in blocks if b.get('font_size')]
        assert len(font_sizes) > 0
        
        # Should have different font sizes
        assert max(font_sizes) >= 20
        assert min(font_sizes) <= 11
    
    def test_multipage_extraction(self, tmp_path):
        """Test extraction from multi-page PDF"""
        # Create multi-page PDF
        pdf_path = create_multipage_pdf(tmp_path, [
            ["Page 1 Title", "Page 1 content here"],
            ["Page 2 Title", "Page 2 content here"],
            ["Page 3 Title", "Page 3 content here"]
        ])
        
        # Extract
        extractor = VectorExtractor()
        result = extractor.extract_from_pdf(pdf_path)
        
        # Verify page count
        assert result['total_pages'] == 3
        assert len(result['pages']) == 3
        
        # Check each page
        for i in range(3):
            page_data = result['pages'][i]
            assert page_data['page_num'] == i
            assert f"Page {i+1} Title" in page_data['full_text']
            assert f"Page {i+1} content" in page_data['full_text']
    
    def test_empty_pdf(self, tmp_path):
        """Test handling of empty PDF"""
        # Create empty PDF
        doc = fitz.open()
        doc.new_page()  # Add one blank page
        pdf_path = tmp_path / "empty.pdf"
        doc.save(str(pdf_path))
        doc.close()
        
        # Extract
        extractor = VectorExtractor()
        result = extractor.extract_from_pdf(pdf_path)
        
        # Should handle gracefully
        assert result['total_pages'] == 1
        assert result['pages'][0]['block_count'] == 0
        assert result['pages'][0]['full_text'] == ""
    
    def test_reading_order_sorting(self, tmp_path):
        """Test that blocks are sorted in reading order"""
        # Create PDF with specific layout
        doc = fitz.open()
        page = doc.new_page()
        
        # Add text in non-sequential order
        page.insert_text((72, 200), "Middle text", fontsize=12)
        page.insert_text((72, 100), "Top text", fontsize=12)
        page.insert_text((72, 300), "Bottom text", fontsize=12)
        
        pdf_path = tmp_path / "unordered.pdf"
        doc.save(str(pdf_path))
        doc.close()
        
        # Extract
        extractor = VectorExtractor()
        result = extractor.extract_from_pdf(pdf_path)
        
        blocks = result['pages'][0]['blocks']
        
        # Blocks should be sorted by Y coordinate (reading order)
        y_coords = [b['bbox'][1] for b in blocks]
        assert y_coords == sorted(y_coords)
    
    def test_bbox_extraction(self, tmp_path):
        """Test that bounding boxes are correctly extracted"""
        # Create PDF with known positions
        doc = fitz.open()
        page = doc.new_page()
        
        # Add text at specific positions
        page.insert_text((100, 150), "Text at (100, 150)", fontsize=12)
        page.insert_text((200, 250), "Text at (200, 250)", fontsize=12)
        
        pdf_path = tmp_path / "positioned.pdf"
        doc.save(str(pdf_path))
        doc.close()
        
        # Extract
        extractor = VectorExtractor()
        result = extractor.extract_from_pdf(pdf_path)
        
        blocks = result['pages'][0]['blocks']
        
        # Check bounding boxes
        for block in blocks:
            bbox = block['bbox']
            assert len(bbox) == 4  # x0, y0, x1, y1
            assert bbox[0] < bbox[2]  # x0 < x1
            assert bbox[1] < bbox[3]  # y0 < y1
            
            # Check approximate positions
            if "100, 150" in block['text']:
                assert 95 <= bbox[0] <= 105  # x near 100
                assert 135 <= bbox[1] <= 155  # y near 150 (with font metrics tolerance)
    
    def test_statistics_calculation(self, tmp_path):
        """Test that statistics are correctly calculated"""
        # Create multi-page PDF
        pdf_path = create_multipage_pdf(tmp_path, [
            ["Page 1 has", "multiple blocks", "of text"],
            ["Page 2 also has", "several blocks"],
            ["Page 3 content"]
        ])
        
        # Extract
        extractor = VectorExtractor()
        result = extractor.extract_from_pdf(pdf_path)
        
        stats = result['statistics']
        
        # Check statistics
        assert stats['total_blocks'] > 0
        assert stats['total_characters'] > 0
        assert stats['avg_blocks_per_page'] > 0
        
        # Verify calculation
        total_blocks = sum(p['block_count'] for p in result['pages'])
        assert stats['total_blocks'] == total_blocks
        
        total_chars = sum(p['char_count'] for p in result['pages'])
        assert stats['total_characters'] == total_chars
    
    def test_textblock_dataclass(self):
        """Test TextBlock dataclass functionality"""
        # Create TextBlock
        block = TextBlock(
            text="Sample text",
            bbox=(10, 20, 100, 40),
            page_num=0,
            block_num=1,
            font_size=12.0,
            font_name="Helvetica"
        )
        
        # Test to_dict
        block_dict = block.to_dict()
        
        assert block_dict['text'] == "Sample text"
        assert block_dict['bbox'] == [10, 20, 100, 40]
        assert block_dict['page_num'] == 0
        assert block_dict['block_num'] == 1
        assert block_dict['font_size'] == 12.0
        assert block_dict['font_name'] == "Helvetica"
    
    def test_nonexistent_file(self):
        """Test handling of non-existent file"""
        extractor = VectorExtractor()
        
        with pytest.raises(FileNotFoundError):
            extractor.extract_from_pdf("nonexistent_file.pdf")
    
    def test_custom_merge_threshold(self, tmp_path):
        """Test different merge threshold values"""
        # Create PDF with spaced text
        doc = fitz.open()
        page = doc.new_page()
        
        # Add text with different spacing
        page.insert_text((72, 100), "First", fontsize=12)
        page.insert_text((120, 100), "Second", fontsize=12)  # Same line, 48 pts apart
        page.insert_text((72, 150), "Third", fontsize=12)   # Different line
        
        pdf_path = tmp_path / "spaced.pdf"
        doc.save(str(pdf_path))
        doc.close()
        
        # Test with small threshold (no merge)
        extractor_small = VectorExtractor(merge_threshold=5)
        result_small = extractor_small.extract_from_pdf(pdf_path)
        
        # Test with large threshold (should merge same-line text)
        extractor_large = VectorExtractor(merge_threshold=100)
        result_large = extractor_large.extract_from_pdf(pdf_path)
        
        # Large threshold should result in fewer blocks
        assert result_small['pages'][0]['block_count'] >= result_large['pages'][0]['block_count']
