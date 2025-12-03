"""
Adaptive Page Sampler
Implements Head-Body-Tail sampling strategy for document classification

Strategy:
- Documents <= 10 pages: Sample all pages
- Documents > 10 pages: Head(3) + Body(5) + Tail(2) = 10 pages
"""
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Protocol

from loguru import logger


@dataclass
class SamplingResult:
    """Result of adaptive page sampling"""
    total_pages: int
    sampled_pages: List[int]  # 0-indexed page numbers
    strategy: str  # "all" | "head_body_tail"
    page_images: List[bytes] = field(default_factory=list)  # Rendered page images (PNG)
    
    @property
    def sample_count(self) -> int:
        """Number of sampled pages"""
        return len(self.sampled_pages)
    
    def to_dict(self) -> dict:
        """Convert to dictionary (without images for logging)"""
        return {
            "total_pages": self.total_pages,
            "sampled_pages": self.sampled_pages,
            "strategy": self.strategy,
            "sample_count": self.sample_count,
            "has_images": len(self.page_images) > 0
        }


class PageSamplerProtocol(Protocol):
    """Protocol for page sampler implementations"""
    
    def sample(self, pdf_path: Path) -> SamplingResult:
        """Sample pages from PDF for classification"""
        ...


class AdaptivePageSampler:
    """
    Adaptive page sampling for document classification
    
    Strategy:
    - Documents <= 10 pages: Sample all pages
    - Documents > 10 pages: Head(3) + Body(5) + Tail(2) = 10 pages
    
    Head pages (0, 1, 2): Cover page, table of contents, introduction
    Tail pages (N-2, N-1): Appendix, signatures, references
    Body pages: 5 pages evenly distributed across middle section
    """
    
    def __init__(
        self,
        max_sample_pages: int = 10,
        dpi: int = 150,
        head_count: int = 3,
        tail_count: int = 2
    ):
        """
        Initialize sampler
        
        Args:
            max_sample_pages: Maximum pages to sample (default 10)
            dpi: Resolution for rendering pages (default 150)
            head_count: Number of head pages (default 3)
            tail_count: Number of tail pages (default 2)
        """
        self.max_sample_pages = max_sample_pages
        self.dpi = dpi
        self.head_count = head_count
        self.tail_count = tail_count
        self.body_count = max_sample_pages - head_count - tail_count
    
    def sample(self, pdf_path: Path) -> SamplingResult:
        """
        Sample pages from PDF for classification
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            SamplingResult with sampled page indices and rendered images
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If PDF cannot be opened
        """
        import fitz  # PyMuPDF
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            raise ValueError(f"Cannot open PDF: {pdf_path}. Error: {e}")
        
        try:
            total_pages = len(doc)
            
            if total_pages == 0:
                logger.warning(f"PDF has 0 pages: {pdf_path}")
                return SamplingResult(
                    total_pages=0,
                    sampled_pages=[],
                    strategy="empty",
                    page_images=[]
                )
            
            # Determine sampling strategy
            if total_pages <= self.max_sample_pages:
                # Sample all pages
                sampled_pages = list(range(total_pages))
                strategy = "all"
            else:
                # Use Head-Body-Tail strategy
                sampled_pages = self._select_head_body_tail(total_pages)
                strategy = "head_body_tail"
            
            logger.info(
                f"Sampling {len(sampled_pages)}/{total_pages} pages "
                f"using '{strategy}' strategy from {pdf_path.name}"
            )
            
            # Render sampled pages to images
            page_images = self._render_pages(doc, sampled_pages)
            
            return SamplingResult(
                total_pages=total_pages,
                sampled_pages=sampled_pages,
                strategy=strategy,
                page_images=page_images
            )
        finally:
            doc.close()
    
    def _select_head_body_tail(self, total_pages: int) -> List[int]:
        """
        Select pages using Head-Body-Tail strategy
        
        Head: pages 0, 1, 2 (cover, TOC)
        Tail: pages N-2, N-1 (appendix, signatures)
        Body: 5 pages evenly distributed in middle
        
        Args:
            total_pages: Total number of pages in document
            
        Returns:
            List of 0-indexed page numbers to sample
        """
        # Head pages: first 3 pages
        head_pages = list(range(min(self.head_count, total_pages)))
        
        # Tail pages: last 2 pages
        tail_start = max(total_pages - self.tail_count, self.head_count)
        tail_pages = list(range(tail_start, total_pages))
        
        # Body pages: evenly distributed in middle section
        body_start = self.head_count
        body_end = total_pages - self.tail_count
        body_range = body_end - body_start
        
        body_pages = []
        if body_range > 0 and self.body_count > 0:
            # Calculate step to distribute body pages evenly
            if body_range <= self.body_count:
                # Not enough pages in body, take all
                body_pages = list(range(body_start, body_end))
            else:
                # Distribute evenly
                step = body_range / (self.body_count + 1)
                for i in range(1, self.body_count + 1):
                    page_idx = int(body_start + i * step)
                    if page_idx < body_end:
                        body_pages.append(page_idx)
        
        # Combine and sort
        all_pages = sorted(set(head_pages + body_pages + tail_pages))
        
        logger.debug(
            f"Head-Body-Tail selection: head={head_pages}, "
            f"body={body_pages}, tail={tail_pages}"
        )
        
        return all_pages
    
    def _render_pages(
        self,
        doc,  # fitz.Document
        page_indices: List[int]
    ) -> List[bytes]:
        """
        Render specified pages to PNG images
        
        Args:
            doc: PyMuPDF document object
            page_indices: List of page indices to render
            
        Returns:
            List of PNG image bytes
        """
        import fitz  # PyMuPDF - import here to match sample() method pattern
        
        images = []
        
        for page_idx in page_indices:
            try:
                page = doc[page_idx]
                
                # Render page to pixmap
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PNG bytes
                png_bytes = pix.tobytes("png")
                images.append(png_bytes)
                
            except Exception as e:
                logger.warning(f"Failed to render page {page_idx}: {e}")
                # Add empty placeholder to maintain index alignment
                images.append(b"")
        
        return images
    
    def get_sampling_info(self, total_pages: int) -> dict:
        """
        Get sampling information without actually sampling
        
        Args:
            total_pages: Total number of pages
            
        Returns:
            Dictionary with sampling strategy info
        """
        if total_pages <= self.max_sample_pages:
            return {
                "strategy": "all",
                "sample_count": total_pages,
                "pages": list(range(total_pages))
            }
        else:
            pages = self._select_head_body_tail(total_pages)
            return {
                "strategy": "head_body_tail",
                "sample_count": len(pages),
                "pages": pages,
                "head_pages": list(range(self.head_count)),
                "tail_pages": list(range(total_pages - self.tail_count, total_pages)),
                "body_count": self.body_count
            }
