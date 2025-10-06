"""
Tests for CitationValidator - CiteFix-lite

Tests cover:
1. Dataclass structures (ValidationError, ValidationResult)
2. Basic validation (doc_id, page number)
3. Text validation (fuzzy matching, keyword overlap)
4. Snippet validation
5. Confidence calculation
6. Neighbor page scanning
7. Integration with CitationRetriever

Usage:
    pytest tests/test_citation_validator.py -v
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.rag.citation_validator import (
    CitationValidator,
    ErrorSeverity,
    ValidationError,
    ValidationErrorType,
    ValidationResult,
    get_citation_validator,
)
from app.rag.snippet_extractor import Snippet

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_doc_id_map(tmp_path):
    """Create mock doc_id_map.json"""
    doc_map = {
        "test_doc_1": str(tmp_path / "doc1.pdf"),
        "test_doc_2": str(tmp_path / "doc2.pdf"),
        "test_doc_3": str(tmp_path / "doc3.pdf"),
    }

    # Create artifacts directory
    artifacts_dir = Path("artifacts/ingestion_production")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Write mock doc_id_map
    map_path = artifacts_dir / "doc_id_map.json"
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(doc_map, f)

    yield doc_map

    # Cleanup
    if map_path.exists():
        map_path.unlink()


@pytest.fixture
def mock_page_reranker():
    """Mock PageReranker for testing"""
    reranker = Mock()
    reranker.get_page_text = Mock(
        return_value="This is page 1 content with test keywords."
    )
    return reranker


@pytest.fixture
def validator(mock_doc_id_map):
    """Create CitationValidator instance with mocked dependencies"""
    validator = CitationValidator(
        validation_level=2,
        min_confidence_threshold=0.7,
        text_match_threshold=0.5,
    )

    # Override doc_id_map with mock
    validator._doc_id_map = mock_doc_id_map

    # Mock page counts
    validator._page_count_cache = {
        "test_doc_1": 10,
        "test_doc_2": 5,
        "test_doc_3": 20,
    }

    return validator


@pytest.fixture
def sample_snippets():
    """Sample snippets for testing"""
    return [
        Snippet(
            text="This is a test snippet",
            start_pos=0,
            end_pos=22,
            matched_keywords={"test", "snippet"},
            score=0.9,
        ),
        Snippet(
            text="Another snippet with keywords",
            start_pos=30,
            end_pos=59,
            matched_keywords={"keywords"},
            score=0.8,
        ),
    ]


# ============================================================================
# TEST DATACLASSES
# ============================================================================


class TestDataclasses:
    """Test ValidationError and ValidationResult dataclasses"""

    def test_validation_error_creation(self):
        """Test ValidationError creation"""
        error = ValidationError(
            error_type=ValidationErrorType.DOC_NOT_FOUND,
            message="Document not found",
            severity=ErrorSeverity.CRITICAL,
            details={"doc_id": "test_doc"},
        )

        assert error.error_type == ValidationErrorType.DOC_NOT_FOUND
        assert error.message == "Document not found"
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.details["doc_id"] == "test_doc"

    def test_validation_error_to_dict(self):
        """Test ValidationError to_dict conversion"""
        error = ValidationError(
            error_type=ValidationErrorType.TEXT_NOT_FOUND,
            message="Text not found",
            severity=ErrorSeverity.WARNING,
        )

        result = error.to_dict()
        assert result["type"] == "text_not_found"
        assert result["message"] == "Text not found"
        assert result["severity"] == "warning"

    def test_validation_result_creation(self):
        """Test ValidationResult creation"""
        result = ValidationResult(
            is_valid=True,
            confidence=0.95,
        )

        assert result.is_valid is True
        assert result.confidence == 0.95
        assert len(result.errors) == 0

    def test_validation_result_add_error(self):
        """Test adding errors to ValidationResult"""
        result = ValidationResult(is_valid=True, confidence=1.0)

        # Add warning error
        result.add_error(
            ValidationError(
                error_type=ValidationErrorType.LOW_CONFIDENCE,
                message="Low confidence",
                severity=ErrorSeverity.WARNING,
            )
        )

        assert result.is_valid is True  # Warning doesn't change validity
        assert len(result.errors) == 1

        # Add critical error
        result.add_error(
            ValidationError(
                error_type=ValidationErrorType.DOC_NOT_FOUND,
                message="Doc not found",
                severity=ErrorSeverity.CRITICAL,
            )
        )

        assert result.is_valid is False  # Critical error changes validity
        assert len(result.errors) == 2

    def test_validation_result_to_dict(self):
        """Test ValidationResult to_dict conversion"""
        result = ValidationResult(is_valid=True, confidence=0.85)
        result.checks = {"doc_exists": True, "page_valid": True}
        result.metadata = {"doc_id": "test_doc", "page": 1}

        dict_result = result.to_dict()

        assert dict_result["is_valid"] is True
        assert dict_result["confidence"] == 0.85
        assert dict_result["checks"]["doc_exists"] is True
        assert dict_result["metadata"]["doc_id"] == "test_doc"


# ============================================================================
# TEST BASIC VALIDATION
# ============================================================================


class TestBasicValidation:
    """Test basic validation methods (Level 1)"""

    def test_validate_doc_id_exists(self, validator):
        """Test doc_id validation - document exists"""
        assert validator.validate_doc_id("test_doc_1") is True
        assert validator.validate_doc_id("test_doc_2") is True

    def test_validate_doc_id_not_exists(self, validator):
        """Test doc_id validation - document doesn't exist"""
        assert validator.validate_doc_id("nonexistent_doc") is False
        assert validator.validate_doc_id("") is False

    def test_validate_page_number_valid(self, validator):
        """Test page number validation - valid page"""
        assert validator.validate_page_number("test_doc_1", 1) is True
        assert validator.validate_page_number("test_doc_1", 5) is True
        assert validator.validate_page_number("test_doc_1", 10) is True

    def test_validate_page_number_invalid(self, validator):
        """Test page number validation - invalid page"""
        # Out of range
        assert validator.validate_page_number("test_doc_1", 0) is False
        assert validator.validate_page_number("test_doc_1", 11) is False
        assert validator.validate_page_number("test_doc_1", -1) is False

        # Invalid doc
        assert validator.validate_page_number("nonexistent_doc", 1) is False

    def test_validate_basic_success(self, validator, mock_page_reranker):
        """Test basic validation with valid citation"""
        validator._page_reranker = mock_page_reranker

        result = validator.validate(
            doc_id="test_doc_1",
            page=1,
            page_text="This is page 1 content",
            snippets=[],
        )

        assert result.is_valid is True
        assert result.checks["doc_exists"] is True
        assert result.checks["page_valid"] is True

    def test_validate_doc_not_found(self, validator):
        """Test validation with non-existent document"""
        result = validator.validate(
            doc_id="nonexistent_doc",
            page=1,
            page_text="Some text",
        )

        assert result.is_valid is False
        assert result.confidence == 0.0
        assert len(result.errors) > 0
        assert result.errors[0].error_type == ValidationErrorType.DOC_NOT_FOUND

    def test_validate_invalid_page(self, validator, mock_page_reranker):
        """Test validation with invalid page number"""
        validator._page_reranker = mock_page_reranker

        result = validator.validate(
            doc_id="test_doc_1",
            page=99,  # Out of range
            page_text="Some text",
        )

        assert result.is_valid is False
        assert result.confidence < 0.5
        assert any(
            e.error_type == ValidationErrorType.INVALID_PAGE_NUMBER
            for e in result.errors
        )


# ============================================================================
# TEST TEXT VALIDATION
# ============================================================================


class TestTextValidation:
    """Test text validation methods (Level 2)"""

    def test_normalize_text(self, validator):
        """Test text normalization"""
        text1 = "  This   is   SOME   text!  "
        text2 = "this is some text!"

        norm1 = validator._normalize_text(text1)
        norm2 = validator._normalize_text(text2)

        assert norm1 == norm2
        # Note: '!' is preserved as it's in the keep list [.,;:!?-]
        assert norm1 == "this is some text!"

    def test_fuzzy_match_exact(self, validator):
        """Test fuzzy matching - exact match"""
        text1 = "This is a test"
        text2 = "This is a test"

        similarity = validator._fuzzy_match(text1, text2)
        assert similarity == 1.0

    def test_fuzzy_match_similar(self, validator):
        """Test fuzzy matching - similar text"""
        text1 = "This is a test"
        text2 = "This is a test with more content"

        similarity = validator._fuzzy_match(text1, text2)
        assert similarity > 0.5

    def test_fuzzy_match_different(self, validator):
        """Test fuzzy matching - different text"""
        text1 = "This is a test"
        text2 = "Completely different content here"

        similarity = validator._fuzzy_match(text1, text2)
        assert similarity < 0.3

    def test_keyword_overlap_high(self, validator):
        """Test keyword overlap - high overlap"""
        text1 = "operating pressure temperature"
        text2 = "The operating pressure and temperature are important"

        overlap = validator._keyword_overlap(text1, text2)
        assert overlap > 0.5

    def test_keyword_overlap_low(self, validator):
        """Test keyword overlap - low overlap"""
        text1 = "operating pressure temperature"
        text2 = "Some completely different content"

        overlap = validator._keyword_overlap(text1, text2)
        assert overlap < 0.3

    def test_validate_page_text_exact_match(self, validator):
        """Test page text validation - exact substring match"""
        cited_text = "This is page 1 content"
        actual_text = "This is page 1 content with more text here"

        confidence = validator.validate_page_text(
            doc_id="test_doc_1",
            page=1,
            cited_page_text=cited_text,
            actual_page_text=actual_text,
        )

        assert confidence == 1.0

    def test_validate_page_text_fuzzy_match(self, validator):
        """Test page text validation - fuzzy match"""
        cited_text = "This is page 1 content with keywords"
        actual_text = "This is page 1 content with test keywords"

        confidence = validator.validate_page_text(
            doc_id="test_doc_1",
            page=1,
            cited_page_text=cited_text,
            actual_page_text=actual_text,
        )

        assert 0.5 < confidence < 1.0

    def test_validate_page_text_no_match(self, validator):
        """Test page text validation - no match"""
        cited_text = "This is completely different content"
        actual_text = "Nothing similar here at all"

        confidence = validator.validate_page_text(
            doc_id="test_doc_1",
            page=1,
            cited_page_text=cited_text,
            actual_page_text=actual_text,
        )

        assert confidence < 0.5


# ============================================================================
# TEST SNIPPET VALIDATION
# ============================================================================


class TestSnippetValidation:
    """Test snippet validation methods"""

    def test_validate_snippets_all_found(self, validator, sample_snippets):
        """Test snippet validation - all snippets found"""
        actual_text = "This is a test snippet and another snippet with keywords"

        coverage = validator.validate_snippets(sample_snippets, actual_text)

        assert coverage > 0.9

    def test_validate_snippets_partial_found(self, validator):
        """Test snippet validation - partial match"""
        snippets = [
            Snippet(
                text="found snippet",
                start_pos=0,
                end_pos=13,
                matched_keywords={"found"},
            ),
            Snippet(
                text="not found snippet",
                start_pos=0,
                end_pos=17,
                matched_keywords={"not"},
            ),
        ]
        actual_text = "This text contains found snippet but not the other one"

        coverage = validator.validate_snippets(snippets, actual_text)

        assert 0.4 < coverage < 0.6

    def test_validate_snippets_none_found(self, validator, sample_snippets):
        """Test snippet validation - no snippets found"""
        actual_text = "Completely different content here"

        coverage = validator.validate_snippets(sample_snippets, actual_text)

        assert coverage < 0.5

    def test_validate_snippets_empty(self, validator):
        """Test snippet validation - empty snippets"""
        coverage = validator.validate_snippets([], "Some text")
        assert coverage == 1.0  # No snippets = pass


# ============================================================================
# TEST CONFIDENCE CALCULATION
# ============================================================================


class TestConfidenceCalculation:
    """Test confidence scoring logic"""

    def test_calculate_confidence_perfect(self, validator):
        """Test confidence calculation - perfect checks"""
        checks = {
            "doc_exists": True,
            "page_valid": True,
            "page_text_confidence": 1.0,
            "snippet_coverage": 1.0,
        }

        confidence = validator.calculate_confidence(checks)
        assert confidence == 1.0

    def test_calculate_confidence_doc_not_found(self, validator):
        """Test confidence calculation - doc not found"""
        checks = {
            "doc_exists": False,
        }

        confidence = validator.calculate_confidence(checks)
        assert confidence == 0.0

    def test_calculate_confidence_invalid_page(self, validator):
        """Test confidence calculation - invalid page"""
        checks = {
            "doc_exists": True,
            "page_valid": False,
        }

        confidence = validator.calculate_confidence(checks)
        assert confidence < 0.5

    def test_calculate_confidence_partial(self, validator):
        """Test confidence calculation - partial match"""
        checks = {
            "doc_exists": True,
            "page_valid": True,
            "page_text_confidence": 0.7,
            "snippet_coverage": 0.8,
        }

        confidence = validator.calculate_confidence(checks)
        assert 0.5 < confidence < 0.9


# ============================================================================
# TEST NEIGHBOR PAGE SCANNING
# ============================================================================


class TestNeighborPageScanning:
    """Test neighbor page scanning feature"""

    def test_scan_neighbor_pages_better_match_found(
        self, validator, mock_page_reranker
    ):
        """Test neighbor scanning - finds better match"""
        validator._page_reranker = mock_page_reranker

        # Mock different page texts
        def get_page_text_mock(doc_id, page):
            if page == 1:
                return "This is page 1 content"
            elif page == 2:
                return "This is the correct content we're looking for"
            elif page == 3:
                return "This is page 3 content"
            return ""

        validator._page_reranker.get_page_text = Mock(side_effect=get_page_text_mock)

        result = validator._scan_neighbor_pages(
            doc_id="test_doc_1",
            page=1,
            cited_text="This is the correct content we're looking for",
            actual_text="This is page 1 content",
        )

        assert result is not None
        assert result["page"] == 2
        assert result["confidence"] > 0.7

    def test_scan_neighbor_pages_no_better_match(self, validator, mock_page_reranker):
        """Test neighbor scanning - no better match"""
        validator._page_reranker = mock_page_reranker

        # All pages have low confidence
        validator._page_reranker.get_page_text = Mock(return_value="Different content")

        result = validator._scan_neighbor_pages(
            doc_id="test_doc_1",
            page=1,
            cited_text="This is the cited text",
            actual_text="This is page 1 content",
        )

        # Should return None or a result with low confidence
        if result:
            assert result["confidence"] < 0.9


# ============================================================================
# TEST INTEGRATION
# ============================================================================


class TestIntegration:
    """Test integration with CitationRetriever"""

    def test_full_validation_flow_valid(
        self, validator, mock_page_reranker, sample_snippets
    ):
        """Test full validation flow - valid citation"""
        validator._page_reranker = mock_page_reranker

        result = validator.validate(
            doc_id="test_doc_1",
            page=1,
            page_text="This is page 1 content with test keywords",
            snippets=sample_snippets,
            query="test keywords",
        )

        assert result.is_valid is True
        assert result.confidence > 0.5
        assert "doc_exists" in result.checks
        assert "page_valid" in result.checks
        assert result.metadata["doc_id"] == "test_doc_1"
        assert result.metadata["page"] == 1

    def test_full_validation_flow_invalid(self, validator):
        """Test full validation flow - invalid citation"""
        result = validator.validate(
            doc_id="nonexistent_doc",
            page=1,
            page_text="Some text",
        )

        assert result.is_valid is False
        assert result.confidence == 0.0
        assert len(result.errors) > 0

    def test_validation_with_low_confidence(self, validator, mock_page_reranker):
        """Test validation with low confidence triggers warnings"""
        validator._page_reranker = mock_page_reranker
        validator._page_reranker.get_page_text = Mock(
            return_value="Completely different text"
        )

        result = validator.validate(
            doc_id="test_doc_1",
            page=1,
            page_text="This is the cited text that doesn't match",
        )

        # Should have warnings
        assert any(
            e.error_type == ValidationErrorType.TEXT_NOT_FOUND for e in result.errors
        )
        assert result.confidence < 0.7


# ============================================================================
# TEST SINGLETON
# ============================================================================


class TestSingleton:
    """Test singleton getter function"""

    def test_get_citation_validator_singleton(self):
        """Test get_citation_validator returns singleton"""
        # Reset singleton
        import app.rag.citation_validator
        from app.rag.citation_validator import _validator_instance

        app.rag.citation_validator._validator_instance = None

        validator1 = get_citation_validator()
        validator2 = get_citation_validator()

        assert validator1 is validator2


# ============================================================================
# TEST EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_validate_empty_page_text(self, validator, mock_page_reranker):
        """Test validation with empty page text"""
        validator._page_reranker = mock_page_reranker

        result = validator.validate(
            doc_id="test_doc_1",
            page=1,
            page_text="",  # Empty
        )

        # Should still be valid at basic level
        assert result.checks["doc_exists"] is True
        assert result.checks["page_valid"] is True

    def test_validate_very_long_text(self, validator, mock_page_reranker):
        """Test validation with very long text"""
        validator._page_reranker = mock_page_reranker

        long_text = "test " * 10000  # Very long text

        result = validator.validate(
            doc_id="test_doc_1",
            page=1,
            page_text=long_text,
        )

        # Should handle without crashing
        assert isinstance(result, ValidationResult)

    def test_validate_special_characters(self, validator):
        """Test validation with special characters"""
        text_with_special = "Text with émojis 🎉 and spëcial chârs"

        normalized = validator._normalize_text(text_with_special)

        # Should handle gracefully
        assert isinstance(normalized, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
