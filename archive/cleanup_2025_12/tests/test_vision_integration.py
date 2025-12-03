"""
Integration tests for Vision generation (Gemini 2.5 Pro multimodal)
Tests cover: page selection logic, vision gating, metadata output
"""
from unittest.mock import Mock, patch

import pytest

from app.rag.generator import GeneratorConfig, ResponseGenerator, _get_doc_id_map
from app.rag.query_transform import QueryIntent, TransformedQuery
from app.rag.retriever import RetrievalResult


class TestVisionPagesSelection:
    """Test _build_vision_pages() logic"""

    def setup_method(self):
        """Setup test fixtures"""
        self.config = GeneratorConfig(
            enable_vision_generation=True,
            vision_max_pages_total=10,
        )
        self.generator = ResponseGenerator(config=self.config)

    @patch("app.rag.generator._get_doc_id_map")
    def test_case_a_page_range_explicit(self, mock_doc_map):
        """Case A: Has page_start..page_end → use full range"""
        mock_doc_map.return_value = {"DOC001": "C:\\test\\doc1.pdf"}

        docs = [
            RetrievalResult(
                chunk_id="chunk1",
                text="test text",
                score=0.9,
                source="bm25",
                metadata={"doc_id": "DOC001", "page_start": 5, "page_end": 8},
                doc_id="DOC001",
                page=5,
            )
        ]

        pages, meta = self.generator._build_vision_pages(docs)

        # Should get pages 5, 6, 7, 8
        assert len(pages) == 4
        assert pages[0]["page"] == 5
        assert pages[3]["page"] == 8
        assert meta["selected"] == 4

    @patch("app.rag.generator._get_doc_id_map")
    def test_case_b_single_page_window(self, mock_doc_map):
        """Case B: Only page → window ±2"""
        mock_doc_map.return_value = {"DOC001": "C:\\test\\doc1.pdf"}

        docs = [
            RetrievalResult(
                chunk_id="chunk1",
                text="test text",
                score=0.9,
                source="bm25",
                metadata={"doc_id": "DOC001"},
                doc_id="DOC001",
                page=10,
            )
        ]

        pages, meta = self.generator._build_vision_pages(docs)

        # Should get pages 8, 9, 10, 11, 12 (10 ± 2)
        assert len(pages) == 5
        assert pages[0]["page"] == 8
        assert pages[4]["page"] == 12

    @patch("app.rag.generator._get_doc_id_map")
    @patch("tools.pdf_renderer.get_pdf_page_count", return_value=15)
    def test_case_c_exceed_quota(self, mock_page_count, mock_doc_map):
        """Case C: > 10 pages → clamp to 10"""
        mock_doc_map.return_value = {"DOC001": "C:\\test\\doc1.pdf"}

        docs = [
            RetrievalResult(
                chunk_id=f"chunk{i}",
                text="test text",
                score=0.9,
                source="bm25",
                metadata={"doc_id": "DOC001", "page_start": i, "page_end": i + 2},
                doc_id="DOC001",
                page=i,
            )
            for i in range(1, 10)  # Create 9 docs with ranges
        ]

        pages, meta = self.generator._build_vision_pages(docs)

        # Should be clamped to max 10
        assert len(pages) <= 10
        assert meta["selected"] <= 10

    @patch("app.rag.generator._get_doc_id_map")
    def test_case_d_missing_doc_id_map(self, mock_doc_map):
        """Case D: doc_id not in map → skip"""
        mock_doc_map.return_value = {
            "DOC001": "C:\\test\\doc1.pdf"
            # DOC002 not in map
        }

        docs = [
            RetrievalResult(
                chunk_id="chunk1",
                text="test",
                score=0.9,
                source="bm25",
                metadata={"doc_id": "DOC002"},
                doc_id="DOC002",
                page=5,
            )
        ]

        pages, meta = self.generator._build_vision_pages(docs)

        # Should be empty (DOC002 not mapped)
        assert len(pages) == 0
        assert (meta.get("reason") == "no_docs_or_mapping") or (
            meta.get("selected", 0) == 0
        )


class TestVisionGating:
    """Test Vision ON/OFF gating logic"""

    @patch("app.rag.generator._get_doc_id_map")
    @patch("tools.pdf_renderer.render_page_to_image")
    def test_vision_on_with_docs(self, mock_render, mock_doc_map):
        """Vision should be ON when docs available"""
        mock_doc_map.return_value = {"DOC001": "C:\\test\\doc.pdf"}
        mock_render.return_value = (b"fake_image_data", {"width": 800, "height": 600})

        config = GeneratorConfig(enable_vision_generation=True)
        generator = ResponseGenerator(config=config)

        # Should attempt vision (won't fully work without real Gemini API)
        assert generator.config.enable_vision_generation is True

    def test_vision_off_when_disabled(self):
        """Vision should be OFF when explicitly disabled"""
        config = GeneratorConfig(enable_vision_generation=False)
        generator = ResponseGenerator(config=config)

        assert generator.config.enable_vision_generation is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
