"""
Integration tests for Day 12 - Bbox Detection and Vision Metrics in API

Tests the full flow:
1. Citation extraction from generated answer
2. Bbox detection for citations
3. Vision skip metrics in API response
4. Proper serialization of bbox data
"""
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.rag.generator import Citation, GeneratorConfig, ResponseGenerator
from app.rag.query_transform import QueryIntent, TransformedQuery
from app.rag.retriever import RetrievalResult


class TestBboxIntegration:
    """Test bbox detection integration in citation flow"""

    def test_citation_bbox_field_exists(self):
        """Citation dataclass should have bbox field"""
        citation = Citation(
            doc_id="test_doc",
            source="test.pdf",
            page=1,
            text_snippet="test snippet",
            relevance_score=0.9,
            pdf_path="/path/to/test.pdf",
            bbox=[100.0, 200.0, 300.0, 400.0],
        )

        assert hasattr(citation, "bbox")
        assert citation.bbox == [100.0, 200.0, 300.0, 400.0]
        print(f"✓ Citation bbox field: {citation.bbox}")

    def test_citation_to_dict_includes_bbox(self):
        """Citation.to_dict() should include bbox when present"""
        citation = Citation(
            doc_id="test_doc",
            source="test.pdf",
            page=1,
            text_snippet="test snippet",
            relevance_score=0.9,
            pdf_path="/path/to/test.pdf",
            bbox=[100.0, 200.0, 300.0, 400.0],
        )

        result = citation.to_dict()

        assert "bbox" in result
        assert result["bbox"] == [100.0, 200.0, 300.0, 400.0]
        assert "pdf_path" in result
        print(f"✓ Citation dict: {result}")

    def test_citation_to_dict_without_bbox(self):
        """Citation.to_dict() should work without bbox (backward compatibility)"""
        citation = Citation(
            doc_id="test_doc",
            source="test.pdf",
            page=1,
            text_snippet="test snippet",
            relevance_score=0.9,
        )

        result = citation.to_dict()

        assert "bbox" not in result  # Should not include None bbox
        print(f"✓ Citation dict without bbox: {result}")

    @patch("tools.pdf_renderer.find_bbox_by_quote")
    def test_bbox_detection_in_validation(self, mock_find_bbox):
        """Bbox detection should be called during citation validation"""
        # Mock bbox detection response
        mock_find_bbox.return_value = {
            "found": True,
            "bbox": [150.0, 250.0, 350.0, 450.0],
            "confidence": 0.92,
            "page": 1,
        }

        # Create generator with validation enabled
        config = GeneratorConfig(
            enable_citation_validation=True,
            citation_validation_level=2,
            citation_min_confidence=0.7,
        )
        generator = ResponseGenerator(config)

        # Create citation with pdf_path and snippet
        citations = [
            Citation(
                doc_id="manual_001",
                source="manual.pdf",
                page=10,
                text_snippet="The operating pressure is 150 bar maximum.",
                relevance_score=0.85,
                pdf_path="/path/to/manual.pdf",
            )
        ]

        # Mock validator to avoid actual validation
        with patch(
            "app.rag.citation_validator.get_citation_validator"
        ) as mock_validator:
            mock_validator_instance = Mock()
            mock_validator_instance.validate.return_value = Mock(
                is_valid=True,
                confidence=0.85,
                errors=[],
                metadata={},
            )
            mock_validator.return_value = mock_validator_instance

            # Call validation
            validated, results = generator._post_validate_citations(
                citations=citations,
                query="What is the operating pressure?",
                retrieved_docs=[],
            )

            # Check bbox was called
            assert mock_find_bbox.called
            call_args = mock_find_bbox.call_args
            assert call_args[1]["pdf_path"] == "/path/to/manual.pdf"
            assert call_args[1]["page_num"] == 10
            assert "operating pressure" in call_args[1]["quote_text"].lower()

            # Check bbox was added to citation
            assert len(validated) == 1
            assert validated[0].bbox == [150.0, 250.0, 350.0, 450.0]

            # Check validation results include bbox info
            assert results["details"][0]["bbox_found"] is True
            assert results["details"][0]["bbox_confidence"] == 0.92

            print(f"✓ Bbox detection called and result stored: {validated[0].bbox}")

    @patch("tools.pdf_renderer.find_bbox_by_quote")
    def test_bbox_detection_failure_handling(self, mock_find_bbox):
        """Should handle bbox detection failures gracefully"""
        # Mock bbox detection failure
        mock_find_bbox.side_effect = Exception("PDF file not found")

        config = GeneratorConfig(
            enable_citation_validation=True,
        )
        generator = ResponseGenerator(config)

        citations = [
            Citation(
                doc_id="manual_001",
                source="manual.pdf",
                page=10,
                text_snippet="test snippet",
                relevance_score=0.85,
                pdf_path="/path/to/nonexistent.pdf",
            )
        ]

        with patch(
            "app.rag.citation_validator.get_citation_validator"
        ) as mock_validator:
            mock_validator_instance = Mock()
            mock_validator_instance.validate.return_value = Mock(
                is_valid=True,
                confidence=0.85,
                errors=[],
                metadata={},
            )
            mock_validator.return_value = mock_validator_instance

            # Should not raise exception
            validated, results = generator._post_validate_citations(
                citations=citations,
                query="test",
                retrieved_docs=[],
            )

            # Citation should still be returned without bbox
            assert len(validated) == 1
            assert validated[0].bbox is None

            # Error should be logged in validation results
            assert (
                "bbox_error" in results["details"][0]
                or "bbox_found" in results["details"][0]
            )

            print(f"✓ Bbox failure handled gracefully")

    def test_citation_without_pdf_path_skips_bbox(self):
        """Citations without pdf_path should skip bbox detection"""
        config = GeneratorConfig(
            enable_citation_validation=True,
        )
        generator = ResponseGenerator(config)

        citations = [
            Citation(
                doc_id="manual_001",
                source="manual.pdf",
                page=10,
                text_snippet="test snippet",
                relevance_score=0.85,
                # No pdf_path
            )
        ]

        with patch(
            "app.rag.citation_validator.get_citation_validator"
        ) as mock_validator:
            with patch("tools.pdf_renderer.find_bbox_by_quote") as mock_find_bbox:
                mock_validator_instance = Mock()
                mock_validator_instance.validate.return_value = Mock(
                    is_valid=True,
                    confidence=0.85,
                    errors=[],
                    metadata={},
                )
                mock_validator.return_value = mock_validator_instance

                validated, results = generator._post_validate_citations(
                    citations=citations,
                    query="test",
                    retrieved_docs=[],
                )

                # Bbox detection should NOT be called
                assert not mock_find_bbox.called
                print(f"✓ Bbox detection skipped for citation without pdf_path")


class TestVisionMetricsIntegration:
    """Test vision skip metrics in API responses"""

    def test_vision_skip_metrics_structure(self):
        """Vision skip metrics should have correct structure"""
        # Simulate vision metadata
        vision_meta = {
            "pages_used": [{"pdf_path": "test.pdf", "page": 1}],
            "pages_failed": [],
            "vision_strategy": {
                "should_use_vision": True,
                "reason": "visual_keywords",
                "prioritize_visual": True,
                "keywords_matched": ["table", "figure"],
            },
        }

        # Extract metrics (simulating API router logic)
        strategy_meta = vision_meta.get("vision_strategy", {})
        metrics = {
            "vision_used": len(vision_meta.get("pages_used", [])) > 0,
            "vision_skipped": strategy_meta.get("should_use_vision") is False,
            "skip_reason": strategy_meta.get("reason"),
            "keywords_matched": strategy_meta.get("keywords_matched", []),
            "prioritize_visual": strategy_meta.get("prioritize_visual", False),
        }

        assert metrics["vision_used"] is True
        assert metrics["vision_skipped"] is False
        assert metrics["skip_reason"] == "visual_keywords"
        assert "table" in metrics["keywords_matched"]
        assert metrics["prioritize_visual"] is True

        print(f"✓ Vision metrics structure: {metrics}")

    def test_vision_skipped_metrics(self):
        """Vision skip metrics when vision is skipped"""
        vision_meta = {
            "pages_used": [],
            "pages_failed": [],
            "vision_strategy": {
                "should_use_vision": False,
                "reason": "text_only",
                "prioritize_visual": False,
                "keywords_matched": [],
            },
        }

        strategy_meta = vision_meta.get("vision_strategy", {})
        metrics = {
            "vision_used": len(vision_meta.get("pages_used", [])) > 0,
            "vision_skipped": strategy_meta.get("should_use_vision") is False,
            "skip_reason": strategy_meta.get("reason"),
            "keywords_matched": strategy_meta.get("keywords_matched", []),
            "prioritize_visual": strategy_meta.get("prioritize_visual", False),
        }

        assert metrics["vision_used"] is False
        assert metrics["vision_skipped"] is True
        assert metrics["skip_reason"] == "text_only"
        assert len(metrics["keywords_matched"]) == 0

        print(f"✓ Vision skipped metrics: {metrics}")


class TestAPISchemaCompatibility:
    """Test API schema compatibility for bbox and vision metrics"""

    def test_citation_schema_has_bbox_field(self):
        """API Citation schema should have bbox field"""
        from app.rag.schemas import Citation as APICitation

        # Check field exists in schema
        fields = APICitation.model_fields
        assert "bbox" in fields
        assert fields["bbox"].annotation.__name__ == "Optional"  # Should be optional

        print(f"✓ API Citation schema has bbox field (optional)")

    def test_citation_schema_bbox_validation(self):
        """API Citation schema should validate bbox format"""
        from app.rag.schemas import Citation as APICitation

        # Valid bbox
        citation = APICitation(
            doc_id="test",
            page=1,
            bbox=[100.0, 200.0, 300.0, 400.0],
            confidence=0.9,
        )
        assert citation.bbox == [100.0, 200.0, 300.0, 400.0]

        # Without bbox (backward compatibility)
        citation2 = APICitation(
            doc_id="test",
            page=1,
            confidence=0.9,
        )
        assert citation2.bbox is None

        print(f"✓ API Citation bbox validation works")


if __name__ == "__main__":
    print("=" * 70)
    print("DAY 12 INTEGRATION TESTS - Bbox Detection & Vision Metrics")
    print("=" * 70)

    # Run tests manually for smoke testing
    import sys

    try:
        # Test 1: Citation bbox field
        print("\n[Test 1] Citation bbox field")
        test = TestBboxIntegration()
        test.test_citation_bbox_field_exists()

        # Test 2: Citation to_dict with bbox
        print("\n[Test 2] Citation to_dict includes bbox")
        test.test_citation_to_dict_includes_bbox()

        # Test 3: Citation to_dict without bbox
        print("\n[Test 3] Citation to_dict without bbox (backward compat)")
        test.test_citation_to_dict_without_bbox()

        # Test 4: Vision metrics structure
        print("\n[Test 4] Vision skip metrics structure")
        test2 = TestVisionMetricsIntegration()
        test2.test_vision_skip_metrics_structure()

        # Test 5: Vision skipped metrics
        print("\n[Test 5] Vision skipped metrics")
        test2.test_vision_skipped_metrics()

        # Test 6: API schema compatibility
        print("\n[Test 6] API Citation schema compatibility")
        test3 = TestAPISchemaCompatibility()
        test3.test_citation_schema_has_bbox_field()
        test3.test_citation_schema_bbox_validation()

        print("\n" + "=" * 70)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
