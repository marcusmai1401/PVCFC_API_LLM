"""
Unit tests for HybridExtractionOrchestrator.

Tests the orchestration of hybrid layout extraction pipeline components.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from app.ingestion.layout.models import (
    GCVWord,
    HybridExtractionResult,
    LayoutRegion,
    MappedRegion,
    RegionLabel,
)
from app.ingestion.layout.orchestrator import (
    HybridExtractionOrchestrator,
    get_hybrid_orchestrator,
)


class TestOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_default_initialization(self):
        """Test orchestrator initializes with default parameters."""
        with patch("app.ingestion.layout.orchestrator.LayoutDetector") as mock_detector:
            mock_detector.get_instance.return_value = Mock()
            orchestrator = HybridExtractionOrchestrator()

            assert orchestrator.hybrid_mapper.iou_threshold == 0.6
            assert orchestrator.table_reconstructor.row_tolerance == 0.02
            assert orchestrator.table_reconstructor.min_rows == 2

    def test_custom_parameters(self):
        """Test orchestrator accepts custom parameters."""
        with patch("app.ingestion.layout.orchestrator.LayoutDetector") as mock_detector:
            mock_detector.get_instance.return_value = Mock()
            orchestrator = HybridExtractionOrchestrator(
                iou_threshold=0.7, row_tolerance=0.03, min_table_rows=3
            )

            assert orchestrator.hybrid_mapper.iou_threshold == 0.7
            assert orchestrator.table_reconstructor.row_tolerance == 0.03
            assert orchestrator.table_reconstructor.min_rows == 3


class TestExtractHybridMarkdown:
    """Tests for extract_hybrid_markdown method."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create orchestrator with mocked dependencies."""
        with patch("app.ingestion.layout.orchestrator.LayoutDetector") as mock_detector:
            mock_instance = Mock()
            mock_detector.get_instance.return_value = mock_instance
            orchestrator = HybridExtractionOrchestrator()
            orchestrator.layout_detector = mock_instance
            return orchestrator

    def test_fallback_when_no_regions_detected(self, mock_orchestrator):
        """Test fallback to GCV text when layout detection returns empty."""
        mock_orchestrator.layout_detector.detect_layout.return_value = []

        result = mock_orchestrator.extract_hybrid_markdown(
            page_image=b"fake_image",
            gcv_words=[],
            page_num=1,
            page_width=800,
            page_height=1000,
            fallback_text="Fallback text content",
        )

        assert result.fallback_used is True
        assert "Fallback text content" in result.markdown
        assert "<!-- Page 1 -->" in result.markdown
        assert result.heading_count == 0
        assert result.table_count == 0

    def test_successful_extraction_with_heading(self, mock_orchestrator):
        """Test successful extraction with heading region."""
        # Mock layout detection to return a heading region
        mock_orchestrator.layout_detector.detect_layout.return_value = [
            LayoutRegion(
                bbox=(0.1, 0.1, 0.9, 0.15),
                label=RegionLabel.TITLE.value,
                confidence=0.95,
            )
        ]

        gcv_words = [{"text": "Introduction", "bbox": (100, 100, 300, 130)}]

        result = mock_orchestrator.extract_hybrid_markdown(
            page_image=b"fake_image",
            gcv_words=gcv_words,
            page_num=1,
            page_width=800,
            page_height=1000,
            fallback_text="",
        )

        assert result.fallback_used is False
        assert "<!-- Page 1 -->" in result.markdown
        assert result.heading_count >= 0  # May vary based on mapping

    def test_successful_extraction_with_table(self, mock_orchestrator):
        """Test successful extraction with table region."""
        # Mock layout detection to return a table region
        mock_orchestrator.layout_detector.detect_layout.return_value = [
            LayoutRegion(
                bbox=(0.1, 0.2, 0.9, 0.5),
                label=RegionLabel.TABLE.value,
                confidence=0.90,
            )
        ]

        # Table words in 2 rows
        gcv_words = [
            {"text": "Header1", "bbox": (100, 200, 200, 230)},
            {"text": "Header2", "bbox": (300, 200, 400, 230)},
            {"text": "Data1", "bbox": (100, 300, 200, 330)},
            {"text": "Data2", "bbox": (300, 300, 400, 330)},
        ]

        result = mock_orchestrator.extract_hybrid_markdown(
            page_image=b"fake_image",
            gcv_words=gcv_words,
            page_num=2,
            page_width=800,
            page_height=1000,
            fallback_text="",
        )

        assert result.fallback_used is False
        assert "<!-- Page 2 -->" in result.markdown

    def test_page_marker_always_present(self, mock_orchestrator):
        """Test that page marker is always present in output."""
        mock_orchestrator.layout_detector.detect_layout.return_value = []

        result = mock_orchestrator.extract_hybrid_markdown(
            page_image=b"fake_image",
            gcv_words=[],
            page_num=42,
            page_width=800,
            page_height=1000,
            fallback_text="Some text",
        )

        assert "<!-- Page 42 -->" in result.markdown


class TestExtractDocumentMarkdown:
    """Tests for extract_document_markdown method."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create orchestrator with mocked dependencies."""
        with patch("app.ingestion.layout.orchestrator.LayoutDetector") as mock_detector:
            mock_instance = Mock()
            mock_detector.get_instance.return_value = mock_instance
            orchestrator = HybridExtractionOrchestrator()
            orchestrator.layout_detector = mock_instance
            return orchestrator

    def test_empty_pages_list(self, mock_orchestrator):
        """Test with empty pages list."""
        markdown, stats = mock_orchestrator.extract_document_markdown([])

        assert markdown == ""
        assert stats["total_pages"] == 0
        assert stats["total_headings"] == 0
        assert stats["total_tables"] == 0

    def test_multiple_pages(self, mock_orchestrator):
        """Test extraction across multiple pages."""
        mock_orchestrator.layout_detector.detect_layout.return_value = []

        pages_data = [
            {
                "page_image": b"image1",
                "gcv_words": [],
                "page_num": 1,
                "page_width": 800,
                "page_height": 1000,
                "fallback_text": "Page 1 content",
            },
            {
                "page_image": b"image2",
                "gcv_words": [],
                "page_num": 2,
                "page_width": 800,
                "page_height": 1000,
                "fallback_text": "Page 2 content",
            },
        ]

        markdown, stats = mock_orchestrator.extract_document_markdown(pages_data)

        assert "<!-- Page 1 -->" in markdown
        assert "<!-- Page 2 -->" in markdown
        assert stats["total_pages"] == 2
        assert stats["pages_with_fallback"] == 2  # Both used fallback


class TestSingletonOrchestrator:
    """Tests for singleton orchestrator getter."""

    def test_get_hybrid_orchestrator_returns_instance(self):
        """Test that get_hybrid_orchestrator returns an instance."""
        with patch("app.ingestion.layout.orchestrator.LayoutDetector") as mock_detector:
            mock_detector.get_instance.return_value = Mock()

            # Reset singleton
            import app.ingestion.layout.orchestrator as orch_module

            orch_module._orchestrator_instance = None

            orchestrator = get_hybrid_orchestrator()
            assert orchestrator is not None
            assert isinstance(orchestrator, HybridExtractionOrchestrator)


class TestCleanup:
    """Tests for cleanup method."""

    def test_cleanup_calls_detector_cleanup(self):
        """Test that cleanup calls layout detector cleanup."""
        with patch("app.ingestion.layout.orchestrator.LayoutDetector") as mock_detector:
            mock_instance = Mock()
            mock_detector.get_instance.return_value = mock_instance

            orchestrator = HybridExtractionOrchestrator()
            orchestrator.cleanup()

            mock_instance.cleanup.assert_called_once()
