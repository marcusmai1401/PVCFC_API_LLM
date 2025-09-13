"""
Tests for PDF Document Detector
"""
import pytest
from pathlib import Path
from app.rag.document_detector import DocumentDetector, PDFType, detect_pdf_type


class TestDocumentDetector:
    """Test suite for DocumentDetector"""
    
    @pytest.fixture
    def detector(self):
        """Create detector instance"""
        return DocumentDetector()
    
    @pytest.fixture
    def sample_pdfs(self):
        """Get paths to sample PDFs"""
        return {
            'text': Path('data/raw/samples/sample_text.pdf'),
            'mixed': Path('data/raw/samples/sample_mixed.pdf'),
            'datasheet': Path('data/raw/samples/sample_datasheet.pdf')
        }
    
    def test_detector_initialization(self, detector):
        """Test detector initialization with default parameters"""
        assert detector.text_threshold == 0.1
        assert detector.sample_pages == 5
    
    def test_detect_text_pdf(self, detector, sample_pdfs):
        """Test detection of text-based PDF"""
        if not sample_pdfs['text'].exists():
            pytest.skip("Sample text PDF not found")
            
        result = detector.detect_pdf_type(sample_pdfs['text'])
        
        assert 'type' in result
        assert 'confidence' in result
        assert 'page_analysis' in result
        assert 'total_pages' in result
        
        # Should be detected as VECTOR since it has text
        assert result['type'] == PDFType.VECTOR
        assert result['confidence'] > 0.8
        assert result['total_pages'] == 2
        assert result['vector_pages'] > 0
    
    def test_detect_mixed_pdf(self, detector, sample_pdfs):
        """Test detection of mixed content PDF"""
        if not sample_pdfs['mixed'].exists():
            pytest.skip("Sample mixed PDF not found")
            
        result = detector.detect_pdf_type(sample_pdfs['mixed'])
        
        # Mixed PDF has both text and non-text pages
        assert result['type'] in [PDFType.VECTOR, PDFType.MIXED]
        assert result['total_pages'] == 2
    
    def test_detect_datasheet_pdf(self, detector, sample_pdfs):
        """Test detection of datasheet PDF"""
        if not sample_pdfs['datasheet'].exists():
            pytest.skip("Sample datasheet PDF not found")
            
        result = detector.detect_pdf_type(sample_pdfs['datasheet'])
        
        # Datasheet should be vector (has text)
        assert result['type'] == PDFType.VECTOR
        assert result['confidence'] > 0.8
    
    def test_page_analysis(self, detector, sample_pdfs):
        """Test page-level analysis"""
        if not sample_pdfs['text'].exists():
            pytest.skip("Sample text PDF not found")
            
        result = detector.detect_pdf_type(sample_pdfs['text'])
        page_analysis = result['page_analysis']
        
        assert len(page_analysis) > 0
        
        # Check first page
        first_page = page_analysis[0]
        assert 'page_num' in first_page
        assert 'has_text' in first_page
        assert 'text_length' in first_page
        assert 'block_count' in first_page
        assert 'image_count' in first_page
        assert 'rotation' in first_page
        assert 'width' in first_page
        assert 'height' in first_page
        
        # First page should have text
        assert first_page['has_text'] == True
        assert first_page['text_length'] > 0
    
    def test_get_pdf_metadata(self, detector, sample_pdfs):
        """Test metadata extraction"""
        if not sample_pdfs['text'].exists():
            pytest.skip("Sample text PDF not found")
            
        metadata = detector.get_pdf_metadata(sample_pdfs['text'])
        
        assert 'pages' in metadata
        assert 'file_size' in metadata
        assert 'encrypted' in metadata
        
        assert metadata['pages'] == 2
        assert metadata['file_size'] > 0
        assert metadata['encrypted'] == False
    
    def test_nonexistent_file(self, detector):
        """Test handling of nonexistent file"""
        with pytest.raises(FileNotFoundError):
            detector.detect_pdf_type('nonexistent.pdf')
    
    def test_non_pdf_file(self, detector, tmp_path):
        """Test handling of non-PDF file"""
        # Create a text file
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("This is not a PDF")
        
        with pytest.raises(ValueError, match="Not a PDF file"):
            detector.detect_pdf_type(txt_file)
    
    def test_convenience_function(self, sample_pdfs):
        """Test the convenience function detect_pdf_type"""
        if not sample_pdfs['text'].exists():
            pytest.skip("Sample text PDF not found")
            
        result = detect_pdf_type(sample_pdfs['text'])
        
        assert 'type' in result
        assert 'confidence' in result
        assert result['type'] == PDFType.VECTOR
