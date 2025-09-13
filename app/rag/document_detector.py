"""
PDF Document Detector
Phát hiện loại PDF: vector, scan, hoặc mixed
"""
import fitz  # PyMuPDF
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


class PDFType(Enum):
    """Enum for PDF document types"""
    VECTOR = "vector"
    SCAN = "scan"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DocumentDetector:
    """
    Detector để phân loại PDF là vector hay scan
    Dựa trên PyMuPDF để kiểm tra text spans trong document
    """
    
    def __init__(self, 
                 text_threshold: float = 0.1,
                 sample_pages: int = 5):
        """
        Initialize detector
        
        Args:
            text_threshold: Tỉ lệ text/page để xác định là vector (default 10%)
            sample_pages: Số trang mẫu để kiểm tra (default 5)
        """
        self.text_threshold = text_threshold
        self.sample_pages = sample_pages
    
    def detect_pdf_type(self, pdf_path: str | Path) -> Dict[str, Any]:
        """
        Detect PDF type by analyzing text content
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with detection results:
            - type: PDFType enum
            - confidence: float (0-1)
            - page_analysis: list of page info
            - total_pages: int
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if not pdf_path.suffix.lower() == '.pdf':
            raise ValueError(f"Not a PDF file: {pdf_path}")
        
        try:
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            
            # Analyze sample pages
            pages_to_check = min(self.sample_pages, total_pages)
            page_analysis = []
            
            vector_pages = 0
            scan_pages = 0
            
            for page_num in range(pages_to_check):
                page = doc[page_num]
                page_info = self._analyze_page(page, page_num)
                page_analysis.append(page_info)
                
                if page_info['has_text']:
                    vector_pages += 1
                else:
                    scan_pages += 1
            
            doc.close()
            
            # Determine PDF type
            pdf_type, confidence = self._determine_type(
                vector_pages, scan_pages, pages_to_check
            )
            
            return {
                'type': pdf_type,
                'confidence': confidence,
                'page_analysis': page_analysis,
                'total_pages': total_pages,
                'vector_pages': vector_pages,
                'scan_pages': scan_pages,
                'sample_size': pages_to_check
            }
            
        except Exception as e:
            logger.error(f"Error detecting PDF type: {e}")
            return {
                'type': PDFType.UNKNOWN,
                'confidence': 0.0,
                'error': str(e),
                'total_pages': 0
            }
    
    def _analyze_page(self, page: fitz.Page, page_num: int) -> Dict[str, Any]:
        """
        Analyze a single page for text content
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (0-based)
            
        Returns:
            Dictionary with page analysis
        """
        text = page.get_text()
        text_length = len(text.strip())
        
        # Get text blocks with positions
        blocks = page.get_text("blocks")
        text_blocks = [b for b in blocks if b[6] == 0]  # type 0 = text
        
        # Check for images (potential scanned content)
        image_list = page.get_images()
        
        # Calculate metrics
        has_text = text_length > 50  # At least 50 characters
        block_count = len(text_blocks)
        image_count = len(image_list)
        
        # Check if page is rotated
        rotation = page.rotation
        
        return {
            'page_num': page_num,
            'has_text': has_text,
            'text_length': text_length,
            'block_count': block_count,
            'image_count': image_count,
            'rotation': rotation,
            'width': page.rect.width,
            'height': page.rect.height
        }
    
    def _determine_type(self, 
                        vector_pages: int, 
                        scan_pages: int,
                        total_checked: int) -> tuple[PDFType, float]:
        """
        Determine PDF type based on page analysis
        
        Args:
            vector_pages: Number of pages with text
            scan_pages: Number of pages without text
            total_checked: Total pages analyzed
            
        Returns:
            Tuple of (PDFType, confidence)
        """
        if total_checked == 0:
            return PDFType.UNKNOWN, 0.0
        
        vector_ratio = vector_pages / total_checked
        
        if vector_ratio >= 0.9:
            # 90% or more pages have text -> VECTOR
            return PDFType.VECTOR, vector_ratio
        elif vector_ratio <= 0.1:
            # 10% or less pages have text -> SCAN
            return PDFType.SCAN, 1.0 - vector_ratio
        else:
            # Mixed content
            return PDFType.MIXED, 0.5 + abs(0.5 - vector_ratio)
    
    def get_pdf_metadata(self, pdf_path: str | Path) -> Dict[str, Any]:
        """
        Extract basic metadata from PDF
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with metadata
        """
        pdf_path = Path(pdf_path)
        
        try:
            doc = fitz.open(str(pdf_path))
            metadata = doc.metadata
            
            result = {
                'title': metadata.get('title', ''),
                'author': metadata.get('author', ''),
                'subject': metadata.get('subject', ''),
                'keywords': metadata.get('keywords', ''),
                'creator': metadata.get('creator', ''),
                'producer': metadata.get('producer', ''),
                'creation_date': metadata.get('creationDate', ''),
                'modification_date': metadata.get('modDate', ''),
                'pages': len(doc),
                'encrypted': doc.is_encrypted,
                'file_size': pdf_path.stat().st_size if pdf_path.exists() else 0
            }
            
            doc.close()
            return result
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {'error': str(e)}


# Convenience function
def detect_pdf_type(pdf_path: str | Path, **kwargs) -> Dict[str, Any]:
    """
    Quick function to detect PDF type
    
    Args:
        pdf_path: Path to PDF file
        **kwargs: Additional arguments for DocumentDetector
        
    Returns:
        Detection results dictionary
    """
    detector = DocumentDetector(**kwargs)
    return detector.detect_pdf_type(pdf_path)
