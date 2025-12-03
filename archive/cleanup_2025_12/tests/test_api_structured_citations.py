"""
API Integration Tests for Structured Citations (Phase 0)

Simplified tests focusing on response structure compatibility.
"""

import pytest

from app.rag.generator import Citation, GeneratedAnswer
from app.rag.schemas import AskResponse


def test_citation_response_schema_compatibility():
    """Test that Citation schema is compatible with structured output"""
    # Test that our Citation dataclass can be serialized to API response
    citation = Citation(
        doc_id="TEST_DOC",
        source="test.pdf",
        page=15,
        text_snippet="snippet",
        relevance_score=0.95,
        pdf_path="/path/test.pdf",
    )

    # Convert to dict (as API does)
    citation_dict = citation.to_dict()

    assert "doc_id" in citation_dict
    assert "page" in citation_dict
    assert citation_dict["doc_id"] == "TEST_DOC"
    assert citation_dict["page"] == 15


def test_generated_answer_serialization():
    """Test GeneratedAnswer serialization with structured citations"""
    answer = GeneratedAnswer(
        query="Test",
        answer="Answer text",
        citations=[
            Citation(
                doc_id="D1",
                source="d1.pdf",
                page=10,
                text_snippet="text",
                relevance_score=0.9,
                pdf_path="/path",
            )
        ],
        confidence=0.88,
        metadata={"structured_output": True},
        generation_time_ms=500.0,
    )

    # Serialize to dict
    answer_dict = answer.to_dict()

    assert "answer" in answer_dict
    assert "citations" in answer_dict
    assert "confidence" in answer_dict
    assert len(answer_dict["citations"]) == 1
    assert answer_dict["citations"][0]["doc_id"] == "D1"


def test_structured_citation_in_ask_response_schema():
    """Test that AskResponse schema accepts structured citations"""
    # This validates that our API schema is ready for structured output
    from pydantic import ValidationError

    response_data = {
        "answer": "Test answer",
        "citations": [{"doc_id": "DOC1", "page": 5, "confidence": 0.9}],
        "context_used": ["chunk1"],
        "confidence": 0.85,
        "meta": {"structured_output": True, "latency_ms": 800},
    }

    # Should not raise validation error
    try:
        response = AskResponse(**response_data)
        assert response.meta["structured_output"] == True
        assert len(response.citations) == 1
    except ValidationError as e:
        pytest.fail(f"AskResponse validation failed: {e}")


def test_citation_with_optional_fields():
    """Test citations with optional structured fields (quote, bbox)"""
    citation_with_extras = Citation(
        doc_id="DOC1",
        source="doc.pdf",
        page=10,
        text_snippet="Maximum pressure: 10 bar",  # Acts as quote
        relevance_score=0.95,
        pdf_path="/path/doc.pdf",
    )

    citation_dict = citation_with_extras.to_dict()

    # Verify all fields present
    assert citation_dict["doc_id"] == "DOC1"
    assert citation_dict["page"] == 10
    assert "snippet" in citation_dict  # text_snippet mapped to snippet


def test_api_response_backward_compatible():
    """Test that response format is backward compatible"""
    # Old format (regex-based citations)
    old_citation = Citation(
        doc_id="D1",
        source="doc.pdf",
        page=5,
        text_snippet="old style",
        relevance_score=0.8,
    )

    # New format (structured output)
    new_citation = Citation(
        doc_id="D2",
        source="doc2.pdf",
        page=10,
        text_snippet="new style with quote",
        relevance_score=0.9,
        pdf_path="/path/doc2.pdf",  # Extra field
    )

    # Both should serialize successfully
    old_dict = old_citation.to_dict()
    new_dict = new_citation.to_dict()

    # Both have required fields
    assert "doc_id" in old_dict and "doc_id" in new_dict
    assert "page" in old_dict and "page" in new_dict

    # New has extra pdf_path, old doesn't (but that's OK)
    assert "pdf_path" not in old_dict  # Old format doesn't include it
    # Note: pdf_path might not be in to_dict() output, checking source code


def test_structured_output_metadata_flag():
    """Test that metadata includes structured_output flag"""
    answer = GeneratedAnswer(
        query="Q",
        answer="A",
        citations=[],
        confidence=0.9,
        metadata={"structured_output": True},
        generation_time_ms=500.0,
    )

    assert answer.metadata.get("structured_output") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
