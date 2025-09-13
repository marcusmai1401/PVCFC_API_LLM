"""
Vector PDF Extractor
Trích xuất text và bounding box từ PDF vector
"""
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class TextBlock:
    """Data class for text block with position info"""
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    page_num: int
    block_num: int
    font_size: Optional[float] = None
    font_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'text': self.text,
            'bbox': list(self.bbox),
            'page_num': self.page_num,
            'block_num': self.block_num,
            'font_size': self.font_size,
            'font_name': self.font_name
        }


class VectorExtractor:
    """
    Extractor để trích xuất text và bbox từ PDF vector
    Sử dụng PyMuPDF để lấy blocks/spans với vị trí chính xác
    """
    
    def __init__(self,
                 merge_threshold: float = 10.0,
                 fix_hyphenation: bool = True):
        """
        Initialize extractor
        
        Args:
            merge_threshold: Distance threshold for merging nearby text blocks
            fix_hyphenation: Whether to fix hyphenated words
        """
        self.merge_threshold = merge_threshold
        self.fix_hyphenation = fix_hyphenation
        
    def extract_from_pdf(self, pdf_path: str | Path) -> Dict[str, Any]:
        """
        Extract text and bbox from all pages
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with extraction results
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        try:
            doc = fitz.open(str(pdf_path))
            results = {
                'file_path': str(pdf_path),
                'total_pages': len(doc),
                'pages': []
            }
            
            total_pages = len(doc)
            
            for page_num in range(total_pages):
                page = doc[page_num]
                page_data = self.extract_from_page(page, page_num)
                results['pages'].append(page_data)
            
            doc.close()
            
            # Calculate statistics
            total_blocks = sum(p['block_count'] for p in results['pages'])
            total_chars = sum(p['char_count'] for p in results['pages'])
            
            results['statistics'] = {
                'total_blocks': total_blocks,
                'total_characters': total_chars,
                'avg_blocks_per_page': total_blocks / total_pages if total_pages > 0 else 0
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Error extracting from PDF: {e}")
            raise
            
    def extract_from_page(self, page: fitz.Page, page_num: int) -> Dict[str, Any]:
        """
        Extract text blocks from a single page
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (0-based)
            
        Returns:
            Dictionary with page extraction results
        """
        # Store original rotation
        original_rotation = page.rotation
        
        # Get page dimensions
        page_rect = page.rect
        width = page_rect.width
        height = page_rect.height
        
        # Extract text blocks with detailed info
        blocks = self._extract_text_blocks(page, page_num)
        
        # Sort blocks by reading order first
        blocks = self._sort_by_reading_order(blocks)
        
        # Fix hyphenation if enabled (should be done before merging)
        if self.fix_hyphenation:
            blocks = self._fix_hyphenation(blocks)
        
        # Merge nearby blocks if needed
        if self.merge_threshold > 0:
            blocks = self._merge_nearby_blocks(blocks)
            
        # Sort again after merging
        blocks = self._sort_by_reading_order(blocks)
        
        # Extract full text
        full_text = ' '.join([b.text for b in blocks])
        
        return {
            'page_num': page_num,
            'width': width,
            'height': height,
            'rotation': original_rotation,
            'blocks': [b.to_dict() for b in blocks],
            'block_count': len(blocks),
            'char_count': len(full_text),
            'full_text': full_text
        }
        
    def _extract_text_blocks(self, page: fitz.Page, page_num: int) -> List[TextBlock]:
        """
        Extract detailed text blocks from page
        
        Args:
            page: PyMuPDF page object
            page_num: Page number
            
        Returns:
            List of TextBlock objects
        """
        blocks = []
        
        # Get text blocks with bbox
        raw_blocks = page.get_text("dict")
        
        span_index = 0  # More accurate name since we're counting spans, not blocks
        for block in raw_blocks.get("blocks", []):
            if block.get("type") != 0:  # Only text blocks
                continue
                
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                        
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    font_size = span.get("size", 0)
                    font_name = span.get("font", "")
                    
                    text_block = TextBlock(
                        text=text,
                        bbox=tuple(bbox),
                        page_num=page_num,
                        block_num=span_index,
                        font_size=font_size,
                        font_name=font_name
                    )
                    blocks.append(text_block)
                    span_index += 1
                    
        return blocks
        
    def _merge_nearby_blocks(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """
        Merge text blocks that are close to each other
        
        Args:
            blocks: List of text blocks
            
        Returns:
            List of merged text blocks
        """
        if not blocks:
            return blocks
            
        merged = []
        current = blocks[0]
        
        for next_block in blocks[1:]:
            # Check if blocks are on same line (similar y-coordinate)
            y_distance = abs(current.bbox[1] - next_block.bbox[1])
            x_distance = next_block.bbox[0] - current.bbox[2]  # Gap between blocks
            
            if y_distance < self.merge_threshold and x_distance < self.merge_threshold * 2:
                # Merge blocks
                merged_text = current.text + " " + next_block.text
                merged_bbox = (
                    min(current.bbox[0], next_block.bbox[0]),
                    min(current.bbox[1], next_block.bbox[1]),
                    max(current.bbox[2], next_block.bbox[2]),
                    max(current.bbox[3], next_block.bbox[3])
                )
                
                current = TextBlock(
                    text=merged_text,
                    bbox=merged_bbox,
                    page_num=current.page_num,
                    block_num=current.block_num,
                    font_size=current.font_size,
                    font_name=current.font_name
                )
            else:
                merged.append(current)
                current = next_block
                
        merged.append(current)
        return merged
        
    def _fix_hyphenation(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """
        Fix hyphenated words at end of lines
        
        Args:
            blocks: List of text blocks
            
        Returns:
            List with fixed hyphenation
        """
        if not blocks:
            return blocks
            
        fixed = []
        skip_next = False
        
        for i, block in enumerate(blocks):
            # Skip if this block was merged with previous
            if skip_next:
                skip_next = False
                continue
                
            text = block.text
            
            # Check if text ends with hyphen and there's a next block
            if text.endswith('-') and i < len(blocks) - 1:
                next_block = blocks[i + 1]
                
                # Check if next block is on next line (different y-coordinate)
                if abs(next_block.bbox[1] - block.bbox[1]) > self.merge_threshold:
                    # Remove hyphen and merge with first word of next block
                    words = next_block.text.split(' ', 1)
                    if words:
                        # Merge hyphenated word
                        merged_text = text[:-1] + words[0]
                        
                        # Create updated block with merged text
                        merged_block = TextBlock(
                            text=merged_text,
                            bbox=block.bbox,
                            page_num=block.page_num,
                            block_num=block.block_num,
                            font_size=block.font_size,
                            font_name=block.font_name
                        )
                        fixed.append(merged_block)
                        
                        # Handle remaining text in next block
                        if len(words) > 1:
                            # Create new block with remaining text
                            remaining_block = TextBlock(
                                text=words[1],
                                bbox=next_block.bbox,
                                page_num=next_block.page_num,
                                block_num=next_block.block_num,
                                font_size=next_block.font_size,
                                font_name=next_block.font_name
                            )
                            fixed.append(remaining_block)
                        
                        # Skip next block as we've processed it
                        skip_next = True
                        continue
            
            # Add block as-is if no hyphenation fix needed
            fixed.append(block)
                
        return fixed
        
    def _sort_by_reading_order(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """
        Sort blocks by reading order (top to bottom, left to right)
        
        Args:
            blocks: List of text blocks
            
        Returns:
            Sorted list of blocks
        """
        # Sort by y-coordinate first (top to bottom), then x-coordinate (left to right)
        return sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
        
    def extract_with_structure(self, pdf_path: str | Path) -> Dict[str, Any]:
        """
        Extract text with structural information (headings, paragraphs, etc.)
        Based on font size and style
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with structured extraction
        """
        results = self.extract_from_pdf(pdf_path)
        
        # Analyze font sizes to detect structure
        all_blocks = []
        for page in results['pages']:
            all_blocks.extend([
                TextBlock(**{k: v for k, v in b.items() if k != 'bbox'}, 
                         bbox=tuple(b['bbox']))
                for b in page['blocks']
            ])
            
        if not all_blocks:
            return results
            
        # Find common font sizes
        font_sizes = [b.font_size for b in all_blocks if b.font_size]
        if font_sizes:
            avg_size = sum(font_sizes) / len(font_sizes)
            
            # Classify blocks by structure
            for page in results['pages']:
                for block in page['blocks']:
                    if block.get('font_size'):
                        size = block['font_size']
                        if size > avg_size * 1.3:
                            block['structure_type'] = 'heading1'
                        elif size > avg_size * 1.15:
                            block['structure_type'] = 'heading2'
                        elif size > avg_size * 1.05:
                            block['structure_type'] = 'heading3'
                        else:
                            block['structure_type'] = 'paragraph'
                    else:
                        block['structure_type'] = 'unknown'
                        
        return results
