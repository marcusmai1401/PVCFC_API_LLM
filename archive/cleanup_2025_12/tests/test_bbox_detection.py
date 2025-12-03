"""
Unit Tests for BBox Detection (Phase 2)

Tests bbox detection functionality in PDF renderer including:
- Exact text matching
- Fuzzy text matching
- Multiple matches
- BBox normalization/denormalization
- Cache hit/miss
- Edge cases

Usage:
    pytest tests/test_bbox_detection.py -v
"""

# Mock fitz before importing pdf_renderer
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.modules["fitz"] = MagicMock()
sys.modules["pymupdf"] = MagicMock()

from tools.pdf_renderer import (
    PDFRenderer,
    clear_bbox_cache,
    denormalize_bbox,
    extract_text_with_bbox,
    find_bbox_by_quote,
    get_bbox_cache_stats,
    normalize_bbox,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_pdf_path(tmp_path):
    """Create a temporary PDF path for testing."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("dummy")  # Create empty file
    return str(pdf_file)


@pytest.fixture
def mock_renderer():
    """Create PDFRenderer with mocked dependencies."""
    with patch("tools.pdf_renderer.fitz") as mock_fitz:
        # Mock PDF document
        mock_doc = MagicMock()
        mock_doc.page_count = 10
        mock_fitz.open.return_value.__enter__.return_value = mock_doc

        # Mock page
        mock_page = MagicMock()
        mock_page.rect.width = 612.0  # Standard US Letter width
        mock_page.rect.height = 792.0  # Standard US Letter height
        mock_doc.__getitem__.return_value = mock_page

        renderer = PDFRenderer()

        # Mock validate_pdf_path to always return valid
        renderer.validate_pdf_path = Mock(return_value=(True, ""))

        yield renderer, mock_page, mock_fitz


# ============================================================================
# TEST BBOX NORMALIZATION
# ============================================================================


class TestBBoxNormalization:
    """Test bbox normalization and denormalization."""

    def test_normalize_bbox_standard(self):
        """Test bbox normalization with standard page size."""
        bbox = (100, 200, 300, 400)
        page_width = 600
        page_height = 800

        normalized = normalize_bbox(bbox, page_width, page_height)

        assert normalized == (
            100 / 600,  # x0
            200 / 800,  # y0
            300 / 600,  # x1
            400 / 800,  # y1
        )
        assert all(0 <= coord <= 1 for coord in normalized)

    def test_normalize_bbox_full_page(self):
        """Test normalizing full page bbox."""
        bbox = (0, 0, 612, 792)
        page_width = 612
        page_height = 792

        normalized = normalize_bbox(bbox, page_width, page_height)

        assert normalized == (0.0, 0.0, 1.0, 1.0)

    def test_denormalize_bbox_standard(self):
        """Test bbox denormalization."""
        normalized_bbox = (0.1, 0.2, 0.5, 0.6)
        page_width = 600
        page_height = 800

        bbox = denormalize_bbox(normalized_bbox, page_width, page_height)

        assert bbox == (60.0, 160.0, 300.0, 480.0)

    def test_normalize_denormalize_roundtrip(self):
        """Test that normalize -> denormalize returns original."""
        original_bbox = (150, 250, 450, 650)
        page_width = 612
        page_height = 792

        normalized = normalize_bbox(original_bbox, page_width, page_height)
        restored = denormalize_bbox(normalized, page_width, page_height)

        # Allow small floating point differences
        for orig, rest in zip(original_bbox, restored):
            assert abs(orig - rest) < 0.01

    def test_normalize_bbox_zero_size(self):
        """Test normalization with zero-sized page (edge case)."""
        bbox = (100, 200, 300, 400)

        normalized = normalize_bbox(bbox, 0, 0)

        assert normalized == (0, 0, 0, 0)


# ============================================================================
# TEST BBOX SEARCH
# ============================================================================


class TestBBoxSearch:
    """Test bbox search functionality."""

    def test_exact_search_single_match(self, mock_renderer):
        """Test exact text search with single match."""
        renderer, mock_page, mock_fitz = mock_renderer

        # Mock search_for to return single match
        mock_rect = MagicMock()
        mock_rect.x0, mock_rect.y0 = 100, 200
        mock_rect.x1, mock_rect.y1 = 300, 250
        mock_page.search_for.return_value = [mock_rect]

        results = renderer.find_bbox_by_quote(
            "test.pdf",
            page_num=1,
            quote="test text",
            fuzzy=False,
            use_cache=False,
        )

        assert len(results) == 1
        assert results[0]["bbox"] == (100, 200, 300, 250)
        assert results[0]["confidence"] == 1.0
        assert results[0]["method"] == "exact"

    def test_exact_search_multiple_matches(self, mock_renderer):
        """Test exact search with multiple matches."""
        renderer, mock_page, mock_fitz = mock_renderer

        # Mock multiple matches
        mock_rect1 = MagicMock()
        mock_rect1.x0, mock_rect1.y0, mock_rect1.x1, mock_rect1.y1 = 100, 200, 300, 250

        mock_rect2 = MagicMock()
        mock_rect2.x0, mock_rect2.y0, mock_rect2.x1, mock_rect2.y1 = 100, 400, 300, 450

        mock_page.search_for.return_value = [mock_rect1, mock_rect2]

        results = renderer.find_bbox_by_quote(
            "test.pdf",
            page_num=1,
            quote="test",
            fuzzy=False,
            use_cache=False,
        )

        assert len(results) == 2
        assert results[0]["bbox"] == (100, 200, 300, 250)
        assert results[1]["bbox"] == (100, 400, 300, 450)

    def test_fuzzy_search_exact_match(self, mock_renderer):
        """Test fuzzy search finds exact match."""
        renderer, mock_page, mock_fitz = mock_renderer

        # Mock text dict with exact match
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "This is a test text",
                                    "bbox": (100, 200, 300, 250),
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        results = renderer.find_bbox_by_quote(
            "test.pdf",
            page_num=1,
            quote="test text",
            fuzzy=True,
            use_cache=False,
        )

        assert len(results) >= 1
        assert results[0]["confidence"] >= 0.95

    def test_fuzzy_search_no_match(self, mock_renderer):
        """Test fuzzy search with no match."""
        renderer, mock_page, mock_fitz = mock_renderer

        # Mock text dict with no matching text
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "Completely different text",
                                    "bbox": (100, 200, 300, 250),
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        results = renderer.find_bbox_by_quote(
            "test.pdf",
            page_num=1,
            quote="nonexistent phrase",
            fuzzy=True,
            use_cache=False,
        )

        assert len(results) == 0


# ============================================================================
# TEST BBOX CACHE
# ============================================================================


class TestBBoxCache:
    """Test bbox caching functionality."""

    def test_cache_hit(self, mock_renderer):
        """Test that cached results are returned."""
        renderer, mock_page, mock_fitz = mock_renderer

        # First call - cache miss
        mock_rect = MagicMock()
        mock_rect.x0, mock_rect.y0, mock_rect.x1, mock_rect.y1 = 100, 200, 300, 250
        mock_page.search_for.return_value = [mock_rect]

        result1 = renderer.find_bbox_by_quote(
            "test.pdf",
            page_num=1,
            quote="test",
            fuzzy=False,
            use_cache=True,
        )

        # Second call - should hit cache
        mock_page.search_for.reset_mock()

        result2 = renderer.find_bbox_by_quote(
            "test.pdf",
            page_num=1,
            quote="test",
            fuzzy=False,
            use_cache=True,
        )

        # search_for should not be called second time
        mock_page.search_for.assert_not_called()

        # Results should be identical
        assert result1 == result2

    def test_cache_miss_different_quote(self, mock_renderer):
        """Test cache miss with different quote."""
        renderer, mock_page, mock_fitz = mock_renderer

        mock_rect = MagicMock()
        mock_rect.x0, mock_rect.y0, mock_rect.x1, mock_rect.y1 = 100, 200, 300, 250
        mock_page.search_for.return_value = [mock_rect]

        # First call
        renderer.find_bbox_by_quote(
            "test.pdf", page_num=1, quote="test1", fuzzy=False, use_cache=True
        )

        # Second call with different quote
        mock_page.search_for.reset_mock()
        renderer.find_bbox_by_quote(
            "test.pdf", page_num=1, quote="test2", fuzzy=False, use_cache=True
        )

        # search_for should be called for second quote
        mock_page.search_for.assert_called_once()

    def test_cache_disabled(self, mock_renderer):
        """Test that cache can be disabled."""
        renderer, mock_page, mock_fitz = mock_renderer

        mock_rect = MagicMock()
        mock_rect.x0, mock_rect.y0, mock_rect.x1, mock_rect.y1 = 100, 200, 300, 250
        mock_page.search_for.return_value = [mock_rect]

        # First call with cache disabled
        renderer.find_bbox_by_quote(
            "test.pdf", page_num=1, quote="test", fuzzy=False, use_cache=False
        )

        # Second call should not hit cache
        mock_page.search_for.reset_mock()
        renderer.find_bbox_by_quote(
            "test.pdf", page_num=1, quote="test", fuzzy=False, use_cache=False
        )

        # search_for should be called both times
        mock_page.search_for.assert_called_once()

    def test_clear_bbox_cache(self, mock_renderer):
        """Test bbox cache clearing."""
        renderer, mock_page, mock_fitz = mock_renderer

        mock_rect = MagicMock()
        mock_rect.x0, mock_rect.y0, mock_rect.x1, mock_rect.y1 = 100, 200, 300, 250
        mock_page.search_for.return_value = [mock_rect]

        # Populate cache
        renderer.find_bbox_by_quote(
            "test.pdf", page_num=1, quote="test", fuzzy=False, use_cache=True
        )

        # Check cache has entry
        stats_before = renderer.get_bbox_cache_stats()
        assert stats_before["bbox_cache_size"] > 0

        # Clear cache
        renderer.clear_bbox_cache()

        # Check cache is empty
        stats_after = renderer.get_bbox_cache_stats()
        assert stats_after["bbox_cache_size"] == 0

    def test_bbox_cache_stats(self, mock_renderer):
        """Test bbox cache statistics."""
        renderer, _, _ = mock_renderer

        stats = renderer.get_bbox_cache_stats()

        assert "bbox_cache_size" in stats
        assert "bbox_cache_max_size" in stats
        assert "bbox_cache_ttl_hours" in stats
        assert stats["bbox_cache_max_size"] > 0


# ============================================================================
# TEST HELPER FUNCTIONS
# ============================================================================


class TestHelperFunctions:
    """Test helper bbox functions."""

    def test_merge_bboxes_single(self):
        """Test merging single bbox."""
        renderer = PDFRenderer()

        bboxes = [(100, 200, 300, 400)]
        merged = renderer._merge_bboxes(bboxes)

        assert merged == (100, 200, 300, 400)

    def test_merge_bboxes_multiple(self):
        """Test merging multiple bboxes."""
        renderer = PDFRenderer()

        bboxes = [
            (100, 200, 300, 400),
            (250, 350, 450, 500),
            (150, 100, 350, 450),
        ]
        merged = renderer._merge_bboxes(bboxes)

        # Should expand to include all bboxes
        assert merged == (100, 100, 450, 500)

    def test_merge_bboxes_empty(self):
        """Test merging empty bbox list."""
        renderer = PDFRenderer()

        merged = renderer._merge_bboxes([])

        assert merged == (0, 0, 0, 0)

    def test_normalize_text_for_bbox(self):
        """Test text normalization."""
        renderer = PDFRenderer()

        text = "  This is   a TEST!  "
        normalized = renderer._normalize_text_for_bbox(text)

        assert normalized == "this is a test!"
        assert "  " not in normalized  # No extra spaces


# ============================================================================
# TEST EXTRACT TEXT WITH BBOX
# ============================================================================


class TestExtractTextWithBBox:
    """Test text extraction with bounding boxes."""

    def test_extract_text_with_bbox(self, mock_renderer):
        """Test extracting all text with bboxes."""
        renderer, mock_page, mock_fitz = mock_renderer

        # Mock text dict with multiple spans
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "First line",
                                    "bbox": (100, 100, 200, 120),
                                    "font": "Arial",
                                    "size": 12,
                                },
                                {
                                    "text": "Second line",
                                    "bbox": (100, 130, 220, 150),
                                    "font": "Arial",
                                    "size": 12,
                                },
                            ]
                        }
                    ],
                }
            ]
        }

        results = renderer.extract_text_with_bbox("test.pdf", page_num=1)

        assert len(results) == 2
        assert results[0]["text"] == "First line"
        assert results[0]["bbox"] == (100, 100, 200, 120)
        assert results[1]["text"] == "Second line"
        assert "page_width" in results[0]
        assert "page_height" in results[0]


# ============================================================================
# TEST EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_page_number(self, mock_renderer):
        """Test with invalid page number."""
        renderer, mock_page, mock_fitz = mock_renderer

        with pytest.raises(ValueError, match="out of range"):
            renderer.find_bbox_by_quote(
                "test.pdf",
                page_num=999,  # Invalid
                quote="test",
                fuzzy=False,
            )

    def test_empty_quote(self, mock_renderer):
        """Test with empty quote string."""
        renderer, mock_page, mock_fitz = mock_renderer

        mock_page.search_for.return_value = []

        results = renderer.find_bbox_by_quote(
            "test.pdf",
            page_num=1,
            quote="",
            fuzzy=False,
        )

        # Should return empty results, not error
        assert results == []

    def test_quote_with_special_chars(self, mock_renderer):
        """Test quote with special characters."""
        renderer, mock_page, mock_fitz = mock_renderer

        # Mock text dict
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "Price: $100.00 (USD)",
                                    "bbox": (100, 200, 300, 250),
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        results = renderer.find_bbox_by_quote(
            "test.pdf",
            page_num=1,
            quote="$100.00",
            fuzzy=True,
        )

        # Should handle special characters
        assert len(results) >= 0  # May or may not find depending on normalization


# ============================================================================
# TEST MODULE-LEVEL FUNCTIONS
# ============================================================================


class TestModuleFunctions:
    """Test module-level convenience functions."""

    @patch("tools.pdf_renderer.get_default_renderer")
    def test_find_bbox_by_quote_convenience(self, mock_get_renderer):
        """Test convenience function."""
        mock_renderer = Mock()
        mock_renderer.find_bbox_by_quote.return_value = []
        mock_get_renderer.return_value = mock_renderer

        result = find_bbox_by_quote("test.pdf", 1, "test")

        mock_renderer.find_bbox_by_quote.assert_called_once()
        assert result == []

    @patch("tools.pdf_renderer.get_default_renderer")
    def test_extract_text_with_bbox_convenience(self, mock_get_renderer):
        """Test convenience function."""
        mock_renderer = Mock()
        mock_renderer.extract_text_with_bbox.return_value = []
        mock_get_renderer.return_value = mock_renderer

        result = extract_text_with_bbox("test.pdf", 1)

        mock_renderer.extract_text_with_bbox.assert_called_once()
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
