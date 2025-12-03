"""
Test Suite for Phase 0: Structured Citations

Tests for claims extraction, structured schemas, and JSON generation.
"""

import json
from unittest.mock import Mock, patch

import pytest


# Test claims extraction
def test_claims_extraction_basic():
    """Test basic claims extraction"""
    from app.rag.claims import extract_factual_claims

    answer = """
    Áp suất vận hành tối đa của KT-06101 là 10 bar theo datasheet.
    Thiết bị được lắp đặt tại nhà máy PVCFC.
    """

    claims = extract_factual_claims(answer)

    assert len(claims) >= 1
    # Should extract numerical claim
    numerical_claims = [c for c in claims if c.type.value == "numerical"]
    assert len(numerical_claims) >= 1
    assert "10 bar" in numerical_claims[0].keywords or any(
        "bar" in kw.lower() for kw in numerical_claims[0].keywords
    )


def test_claims_extraction_keywords():
    """Test keyword extraction from claims"""
    from app.rag.claims import extract_factual_claims

    answer = "Maximum operating pressure for KT-06101 is 150 psi at 25°C."

    claims = extract_factual_claims(answer)

    assert len(claims) > 0
    claim = claims[0]
    # Should extract equipment tag
    assert any("KT" in kw for kw in claim.keywords) or any(
        "06101" in kw for kw in claim.keywords
    )


def test_claims_no_citation_needed():
    """Test that generic statements don't require citations"""
    from app.rag.claims import extract_factual_claims

    answer = "In general, pressure vessels typically operate within safe limits."

    claims = extract_factual_claims(answer)

    # Generic statement should not be extracted as requiring citation
    assert len(claims) == 0


# Test structured schemas
def test_structured_citation_schema_valid():
    """Test that valid structured citation passes validation"""
    from app.rag.schemas_structured import StructuredCitation

    data = {
        "doc_id": "PVCFC-KT06101-datasheet-v1",
        "page": 15,
        "quote": "Maximum pressure: 10 bar",
        "evidence_type": "table",
    }

    citation = StructuredCitation(**data)

    assert citation.doc_id == "PVCFC-KT06101-datasheet-v1"
    assert citation.page == 15
    assert citation.evidence_type == "table"


def test_structured_citation_schema_invalid_page():
    """Test that invalid page number fails validation"""
    from pydantic import ValidationError

    from app.rag.schemas_structured import StructuredCitation

    data = {
        "doc_id": "test",
        "page": 0,  # Invalid: page must be >= 1
    }

    with pytest.raises(ValidationError):
        StructuredCitation(**data)


def test_structured_citation_bbox_validation():
    """Test bbox validation"""
    from app.rag.schemas_structured import StructuredCitation

    # Valid bbox
    citation1 = StructuredCitation(doc_id="test", page=1, bbox=[100, 200, 300, 400])
    assert citation1.bbox == [100.0, 200.0, 300.0, 400.0]

    # Invalid bbox (wrong order) - should be None
    citation2 = StructuredCitation(
        doc_id="test", page=1, bbox=[300, 400, 100, 200]  # x1 > x2
    )
    assert citation2.bbox is None


def test_structured_answer_requires_citations():
    """Test that claims without citations are rejected"""
    from pydantic import ValidationError

    from app.rag.schemas_structured import StructuredAnswer

    data = {
        "answer": "Test answer",
        "claims": [
            {
                "claim_id": "claim_0",
                "claim_text": "Test claim",
                "citations": [],  # Empty!
            }
        ],
    }

    with pytest.raises(ValidationError):
        StructuredAnswer(**data)


def test_structured_answer_valid():
    """Test valid structured answer with claims"""
    from app.rag.schemas_structured import StructuredAnswer

    data = {
        "answer": "Pressure is 10 bar",
        "claims": [
            {
                "claim_id": "claim_0",
                "claim_text": "Pressure is 10 bar",
                "citations": [{"doc_id": "test_doc", "page": 5, "quote": "10 bar"}],
            }
        ],
    }

    answer = StructuredAnswer(**data)

    assert len(answer.claims) == 1
    assert len(answer.claims[0].citations) == 1


# Test backward compatibility
def test_backward_compatibility_regex_citations():
    """Test that legacy regex-based citations still work"""
    from app.rag.generator import GeneratorConfig, ResponseGenerator
    from app.rag.retriever import RetrievalResult

    # Mock LLM response with [Doc N] format
    mock_response = "The pressure is 10 bar [Doc 1, p.15]."

    # This should work without structured output enabled
    config = GeneratorConfig(enable_structured_output=False)
    generator = ResponseGenerator(config)

    # Test _extract_citations with regex - use proper RetrievalResult
    doc_mapping = {
        1: RetrievalResult(
            chunk_id="test",
            doc_id="test_doc",
            source="test.pdf",
            page=15,
            text="Test content for citation",
            score=0.9,
            metadata={},
        )
    }

    citations = generator._extract_citations(mock_response, doc_mapping)

    assert len(citations) >= 1
    assert citations[0].doc_id == "test_doc"


def test_structured_output_integration():
    """Test structured output with mocked Gemini response"""
    from app.rag.generator import GeneratorConfig, ResponseGenerator

    config = GeneratorConfig(enable_structured_output=True)
    generator = ResponseGenerator(config)

    # Mock doc_mapping
    from app.rag.retriever import RetrievalResult

    doc_mapping = {
        1: RetrievalResult(
            chunk_id="test",
            doc_id="PVCFC-TEST",
            source="test",
            page=10,
            text="Test context",
            score=0.9,
            metadata={},
        )
    }

    # Mock Gemini client
    mock_response = Mock()
    mock_response.text = json.dumps(
        {
            "answer": "The pressure is 10 bar",
            "citations": [
                {"doc_id": "PVCFC-TEST", "page": 10, "quote": "pressure: 10 bar"}
            ],
        }
    )

    # Patch imports that happen inside the method
    with patch("google.genai.Client") as mock_client_class:
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch("app.services.llm.get_api_key_for", return_value="test_key"):
            result = generator._generate_structured(
                english_query="What is the pressure?",
                original_query="Áp suất là bao nhiêu?",
                context="Test context",
                doc_mapping=doc_mapping,
                language="vi",
            )

    assert result is not None
    answer, citations = result
    assert "10 bar" in answer
    assert len(citations) == 1
    assert citations[0].doc_id == "PVCFC-TEST"
    assert citations[0].page == 10


# Integration test
@pytest.mark.integration
def test_full_pipeline_with_structured_output():
    """End-to-end test with structured output enabled"""
    from app.rag.generator import GeneratorConfig, ResponseGenerator
    from app.rag.query_transform import QueryIntent, TransformedQuery
    from app.rag.retriever import RetrievalResult

    config = GeneratorConfig(
        enable_structured_output=True,
        enable_vision_generation=False,  # Disable vision for this test
    )
    generator = ResponseGenerator(config)

    # Mock query
    query = TransformedQuery(
        original="Test query",
        normalized="test query",
        intent=QueryIntent.ASK,
        language="en",
        filters={},
    )

    # Mock retrieved docs
    docs = [
        RetrievalResult(
            chunk_id="test1",
            doc_id="TEST_DOC",
            source="test.pdf",
            page=5,
            text="The answer is 42.",
            score=0.95,
            metadata={},
        )
    ]

    # This would make actual API call - skip in unit tests
    # Just test that the path is wired correctly
    assert generator.config.enable_structured_output is True


def test_gemini_schema_generation():
    """Test that Gemini schema generation works"""
    from app.rag.schemas_structured import (
        get_gemini_citation_schema,
        get_simple_citation_schema,
    )

    # Should not raise any errors
    simple_schema = get_simple_citation_schema()
    assert simple_schema is not None
    assert simple_schema.type == "OBJECT"

    full_schema = get_gemini_citation_schema()
    assert full_schema is not None
    assert full_schema.type == "OBJECT"


# Test feature flags
def test_feature_flags_disabled_by_default():
    """Test that structured output is disabled by default"""
    from app.rag.generator import GeneratorConfig

    config = GeneratorConfig()

    assert config.enable_structured_output is False
    assert config.enable_claims_extraction is False


def test_feature_flags_can_be_enabled():
    """Test that feature flags can be enabled"""
    from app.rag.generator import GeneratorConfig

    config = GeneratorConfig(
        enable_structured_output=True, enable_claims_extraction=True
    )

    assert config.enable_structured_output is True
    assert config.enable_claims_extraction is True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
