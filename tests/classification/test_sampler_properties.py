"""
Property-based tests for Adaptive Page Sampler

**Feature: intelligent-classification-deep-search**

Tests:
- Property 4: Short Document Full Sampling
- Property 5: Long Document Head-Body-Tail Sampling
"""
import io
import tempfile
from pathlib import Path
from typing import List

import pytest
from hypothesis import given, strategies as st, settings, assume

from app.classification.sampler import AdaptivePageSampler, SamplingResult


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Strategy for generating page counts for short documents (1-10 pages)
short_doc_page_count = st.integers(min_value=1, max_value=10)

# Strategy for generating page counts for long documents (11-500 pages)
long_doc_page_count = st.integers(min_value=11, max_value=500)

# Strategy for generating any valid page count
any_page_count = st.integers(min_value=1, max_value=500)

# Strategy for generating DPI values
dpi_strategy = st.integers(min_value=72, max_value=300)


# =============================================================================
# Helper functions
# =============================================================================

def create_test_pdf(num_pages: int) -> Path:
    """
    Create a test PDF with specified number of pages
    
    Args:
        num_pages: Number of pages to create
        
    Returns:
        Path to temporary PDF file
    """
    import fitz  # PyMuPDF
    import uuid
    
    # Create a new PDF document
    doc = fitz.open()
    
    for i in range(num_pages):
        # Add a page with some text
        page = doc.new_page(width=612, height=792)  # Letter size
        text = f"Page {i + 1} of {num_pages}"
        page.insert_text((72, 72), text, fontsize=12)
    
    # Create temp file path manually to avoid Windows file locking issues
    temp_dir = Path(tempfile.gettempdir())
    temp_path = temp_dir / f"test_pdf_{uuid.uuid4().hex}.pdf"
    
    doc.save(str(temp_path))
    doc.close()
    
    return temp_path


def cleanup_pdf(pdf_path: Path):
    """Clean up temporary PDF file"""
    try:
        if pdf_path.exists():
            pdf_path.unlink()
    except Exception:
        pass


# =============================================================================
# Property 4: Short Document Full Sampling
# =============================================================================

class TestProperty4ShortDocumentFullSampling:
    """
    **Feature: intelligent-classification-deep-search, Property 4: Short Document Full Sampling**
    
    *For any* PDF with total_pages <= 10, the sampler SHALL return sampled_pages 
    with length equal to total_pages (all pages sampled).
    
    **Validates: Requirements 2.1**
    """
    
    @given(num_pages=short_doc_page_count)
    @settings(max_examples=20, deadline=60000)  # Reduced iterations for faster CI
    def test_short_document_samples_all_pages(self, num_pages: int):
        """
        Property: For documents with <= 10 pages, all pages must be sampled
        """
        pdf_path = None
        try:
            # Create test PDF
            pdf_path = create_test_pdf(num_pages)
            
            # Sample pages
            sampler = AdaptivePageSampler(max_sample_pages=10)
            result = sampler.sample(pdf_path)
            
            # Verify all pages are sampled
            assert result.total_pages == num_pages, (
                f"Expected total_pages={num_pages}, got {result.total_pages}"
            )
            assert len(result.sampled_pages) == num_pages, (
                f"Expected {num_pages} sampled pages, got {len(result.sampled_pages)}"
            )
            assert result.strategy == "all", (
                f"Expected strategy='all', got '{result.strategy}'"
            )
            
            # Verify sampled pages are 0 to num_pages-1
            expected_pages = list(range(num_pages))
            assert result.sampled_pages == expected_pages, (
                f"Expected pages {expected_pages}, got {result.sampled_pages}"
            )
            
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    @given(num_pages=short_doc_page_count)
    @settings(max_examples=20, deadline=60000)
    def test_short_document_has_images_for_all_pages(self, num_pages: int):
        """
        Property: For short documents, page_images must have same length as sampled_pages
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(num_pages)
            
            sampler = AdaptivePageSampler(max_sample_pages=10)
            result = sampler.sample(pdf_path)
            
            # Verify images count matches sampled pages
            assert len(result.page_images) == len(result.sampled_pages), (
                f"Expected {len(result.sampled_pages)} images, got {len(result.page_images)}"
            )
            
            # Verify all images are non-empty
            for i, img in enumerate(result.page_images):
                assert len(img) > 0, f"Image for page {i} is empty"
                
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    def test_single_page_document(self):
        """
        Edge case: Single page document should sample exactly 1 page
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(1)
            
            sampler = AdaptivePageSampler(max_sample_pages=10)
            result = sampler.sample(pdf_path)
            
            assert result.total_pages == 1
            assert result.sampled_pages == [0]
            assert result.strategy == "all"
            assert len(result.page_images) == 1
            
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    def test_exactly_10_pages_document(self):
        """
        Edge case: Document with exactly 10 pages should sample all pages
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(10)
            
            sampler = AdaptivePageSampler(max_sample_pages=10)
            result = sampler.sample(pdf_path)
            
            assert result.total_pages == 10
            assert len(result.sampled_pages) == 10
            assert result.sampled_pages == list(range(10))
            assert result.strategy == "all"
            
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)


# =============================================================================
# Property 5: Long Document Head-Body-Tail Sampling
# =============================================================================

class TestProperty5LongDocumentHeadBodyTailSampling:
    """
    **Feature: intelligent-classification-deep-search, Property 5: Long Document Head-Body-Tail Sampling**
    
    *For any* PDF with total_pages > 10, the sampler SHALL return exactly 10 sampled_pages where:
    - pages 0,1,2 are included (Head)
    - pages N-2,N-1 are included (Tail)
    - 5 Body pages are evenly distributed in the middle section
    
    **Validates: Requirements 2.2, 2.3, 2.4, 2.5**
    """
    
    @given(num_pages=long_doc_page_count)
    @settings(max_examples=20, deadline=60000)
    def test_long_document_samples_exactly_10_pages(self, num_pages: int):
        """
        Property: For documents with > 10 pages, exactly 10 pages must be sampled
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(num_pages)
            
            sampler = AdaptivePageSampler(max_sample_pages=10)
            result = sampler.sample(pdf_path)
            
            assert result.total_pages == num_pages, (
                f"Expected total_pages={num_pages}, got {result.total_pages}"
            )
            assert len(result.sampled_pages) == 10, (
                f"Expected 10 sampled pages, got {len(result.sampled_pages)}"
            )
            assert result.strategy == "head_body_tail", (
                f"Expected strategy='head_body_tail', got '{result.strategy}'"
            )
            
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    @given(num_pages=long_doc_page_count)
    @settings(max_examples=20, deadline=60000)
    def test_long_document_includes_head_pages(self, num_pages: int):
        """
        Property: Head pages (0, 1, 2) must always be included for long documents
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(num_pages)
            
            sampler = AdaptivePageSampler(max_sample_pages=10, head_count=3)
            result = sampler.sample(pdf_path)
            
            # Verify head pages are included
            head_pages = [0, 1, 2]
            for page in head_pages:
                assert page in result.sampled_pages, (
                    f"Head page {page} not in sampled pages: {result.sampled_pages}"
                )
                
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    @given(num_pages=long_doc_page_count)
    @settings(max_examples=20, deadline=60000)
    def test_long_document_includes_tail_pages(self, num_pages: int):
        """
        Property: Tail pages (N-2, N-1) must always be included for long documents
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(num_pages)
            
            sampler = AdaptivePageSampler(max_sample_pages=10, tail_count=2)
            result = sampler.sample(pdf_path)
            
            # Verify tail pages are included
            tail_pages = [num_pages - 2, num_pages - 1]
            for page in tail_pages:
                assert page in result.sampled_pages, (
                    f"Tail page {page} not in sampled pages: {result.sampled_pages}"
                )
                
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    @given(num_pages=long_doc_page_count)
    @settings(max_examples=20, deadline=60000)
    def test_long_document_body_pages_in_middle_section(self, num_pages: int):
        """
        Property: Body pages must be in the middle section (between head and tail)
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(num_pages)
            
            sampler = AdaptivePageSampler(max_sample_pages=10, head_count=3, tail_count=2)
            result = sampler.sample(pdf_path)
            
            head_pages = {0, 1, 2}
            tail_pages = {num_pages - 2, num_pages - 1}
            body_pages = [p for p in result.sampled_pages if p not in head_pages and p not in tail_pages]
            
            # Verify body pages are in middle section
            body_start = 3  # After head
            body_end = num_pages - 2  # Before tail
            
            for page in body_pages:
                assert body_start <= page < body_end, (
                    f"Body page {page} is not in middle section [{body_start}, {body_end})"
                )
                
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    @given(num_pages=long_doc_page_count)
    @settings(max_examples=20, deadline=60000)
    def test_long_document_has_5_body_pages(self, num_pages: int):
        """
        Property: Long documents must have exactly 5 body pages
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(num_pages)
            
            sampler = AdaptivePageSampler(max_sample_pages=10, head_count=3, tail_count=2)
            result = sampler.sample(pdf_path)
            
            head_pages = {0, 1, 2}
            tail_pages = {num_pages - 2, num_pages - 1}
            body_pages = [p for p in result.sampled_pages if p not in head_pages and p not in tail_pages]
            
            assert len(body_pages) == 5, (
                f"Expected 5 body pages, got {len(body_pages)}: {body_pages}"
            )
            
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    @given(num_pages=long_doc_page_count)
    @settings(max_examples=20, deadline=60000)
    def test_sampled_pages_are_sorted(self, num_pages: int):
        """
        Property: Sampled pages must be in ascending order
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(num_pages)
            
            sampler = AdaptivePageSampler(max_sample_pages=10)
            result = sampler.sample(pdf_path)
            
            assert result.sampled_pages == sorted(result.sampled_pages), (
                f"Sampled pages are not sorted: {result.sampled_pages}"
            )
            
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    @given(num_pages=long_doc_page_count)
    @settings(max_examples=20, deadline=60000)
    def test_sampled_pages_are_unique(self, num_pages: int):
        """
        Property: Sampled pages must be unique (no duplicates)
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(num_pages)
            
            sampler = AdaptivePageSampler(max_sample_pages=10)
            result = sampler.sample(pdf_path)
            
            assert len(result.sampled_pages) == len(set(result.sampled_pages)), (
                f"Duplicate pages found: {result.sampled_pages}"
            )
            
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    def test_exactly_11_pages_document(self):
        """
        Edge case: Document with exactly 11 pages should use head_body_tail strategy
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(11)
            
            sampler = AdaptivePageSampler(max_sample_pages=10)
            result = sampler.sample(pdf_path)
            
            assert result.total_pages == 11
            assert len(result.sampled_pages) == 10
            assert result.strategy == "head_body_tail"
            
            # Verify head pages
            assert 0 in result.sampled_pages
            assert 1 in result.sampled_pages
            assert 2 in result.sampled_pages
            
            # Verify tail pages
            assert 9 in result.sampled_pages
            assert 10 in result.sampled_pages
            
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)
    
    def test_100_pages_document(self):
        """
        Edge case: Document with 100 pages should have evenly distributed body pages
        """
        pdf_path = None
        try:
            pdf_path = create_test_pdf(100)
            
            sampler = AdaptivePageSampler(max_sample_pages=10)
            result = sampler.sample(pdf_path)
            
            assert result.total_pages == 100
            assert len(result.sampled_pages) == 10
            assert result.strategy == "head_body_tail"
            
            # Verify head pages
            assert 0 in result.sampled_pages
            assert 1 in result.sampled_pages
            assert 2 in result.sampled_pages
            
            # Verify tail pages
            assert 98 in result.sampled_pages
            assert 99 in result.sampled_pages
            
            # Body pages should be distributed across middle section
            head_pages = {0, 1, 2}
            tail_pages = {98, 99}
            body_pages = [p for p in result.sampled_pages if p not in head_pages and p not in tail_pages]
            
            assert len(body_pages) == 5
            
            # Body pages should be roughly evenly distributed
            # Middle section is pages 3-97 (95 pages)
            # 5 body pages should be roughly at positions 3+19, 3+38, 3+57, 3+76, 3+95
            # Allow some tolerance
            for i, page in enumerate(sorted(body_pages)):
                expected_min = 3 + (i * 15)
                expected_max = 3 + ((i + 1) * 20)
                assert expected_min <= page <= expected_max, (
                    f"Body page {page} at index {i} is not in expected range [{expected_min}, {expected_max}]"
                )
                
        finally:
            if pdf_path:
                cleanup_pdf(pdf_path)


# =============================================================================
# Additional sampler tests
# =============================================================================

class TestSamplerEdgeCases:
    """Additional edge case tests for AdaptivePageSampler"""
    
    def test_file_not_found(self):
        """Sampler should raise FileNotFoundError for non-existent file"""
        sampler = AdaptivePageSampler()
        
        with pytest.raises(FileNotFoundError):
            sampler.sample(Path("/non/existent/file.pdf"))
    
    def test_sampling_result_to_dict(self):
        """SamplingResult.to_dict() should return valid structure"""
        result = SamplingResult(
            total_pages=20,
            sampled_pages=[0, 1, 2, 5, 8, 11, 14, 17, 18, 19],
            strategy="head_body_tail",
            page_images=[b"img"] * 10
        )
        
        data = result.to_dict()
        
        assert data["total_pages"] == 20
        assert data["sampled_pages"] == [0, 1, 2, 5, 8, 11, 14, 17, 18, 19]
        assert data["strategy"] == "head_body_tail"
        assert data["sample_count"] == 10
        assert data["has_images"] is True
    
    def test_get_sampling_info_short_doc(self):
        """get_sampling_info should return correct info for short documents"""
        sampler = AdaptivePageSampler(max_sample_pages=10)
        
        info = sampler.get_sampling_info(5)
        
        assert info["strategy"] == "all"
        assert info["sample_count"] == 5
        assert info["pages"] == [0, 1, 2, 3, 4]
    
    def test_get_sampling_info_long_doc(self):
        """get_sampling_info should return correct info for long documents"""
        sampler = AdaptivePageSampler(max_sample_pages=10)
        
        info = sampler.get_sampling_info(50)
        
        assert info["strategy"] == "head_body_tail"
        assert info["sample_count"] == 10
        assert info["head_pages"] == [0, 1, 2]
        assert info["tail_pages"] == [48, 49]
        assert info["body_count"] == 5
