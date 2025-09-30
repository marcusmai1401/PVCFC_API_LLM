"""
Unit tests for Query Transformation Module
"""
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.rag.query_transform import (
    QueryFilters,
    QueryIntent,
    QueryTransformer,
    TransformedQuery,
    transform_query,
)


class TestQueryNormalization:
    """Test query normalization functionality"""

    def test_normalize_lowercase(self):
        """Test lowercase conversion"""
        transformer = QueryTransformer()
        result = transformer.normalize_query("UPPERCASE TEXT")
        assert result == "uppercase text"

    def test_normalize_whitespace(self):
        """Test whitespace normalization"""
        transformer = QueryTransformer()
        result = transformer.normalize_query("  multiple   spaces  ")
        assert result == "multiple spaces"

    def test_normalize_special_chars(self):
        """Test special character handling"""
        transformer = QueryTransformer()
        result = transformer.normalize_query("test!@#$%^&*()")
        assert "test" in result
        assert "!" not in result
        assert "^" not in result

    def test_normalize_technical_chars_preserved(self):
        """Test that technical characters are preserved"""
        transformer = QueryTransformer()
        result = transformer.normalize_query("valve-101 @ 25.5°C")
        assert "valve-101" in result
        assert "@" in result
        assert "25.5" in result

    def test_stopwords_removal(self):
        """Test stopword removal when enabled"""
        transformer = QueryTransformer(remove_stopwords=True)
        result = transformer.normalize_query("the pressure is at maximum")
        # "the", "is", "at" should be removed
        assert "the" not in result.split()
        assert "pressure" in result
        assert "maximum" in result

    def test_stopwords_preserved_when_disabled(self):
        """Test stopwords preserved when disabled"""
        transformer = QueryTransformer(remove_stopwords=False)
        result = transformer.normalize_query("the pressure is at maximum")
        assert "the" in result
        assert "is" in result


class TestIntentDetection:
    """Test intent detection functionality"""

    def test_detect_ask_intent(self):
        """Test ASK intent detection"""
        transformer = QueryTransformer()

        queries = [
            "What is the operating pressure?",
            "What are the specifications?",
            "Maximum temperature of the system",
        ]

        for query in queries:
            normalized = transformer.normalize_query(query)
            intent = transformer.detect_intent(normalized)
            assert intent == QueryIntent.ASK

    def test_detect_locate_intent(self):
        """Test LOCATE intent detection"""
        transformer = QueryTransformer()

        queries = [
            "Where is valve V-101 located?",
            "Find pump P-201 in the diagram",
            "Page number containing KT06101",
        ]

        for query in queries:
            normalized = transformer.normalize_query(query)
            intent = transformer.detect_intent(normalized)
            assert intent == QueryIntent.LOCATE

    def test_detect_report_intent(self):
        """Test REPORT intent detection"""
        transformer = QueryTransformer()

        queries = [
            "Generate a report on system parameters",
            "Create comprehensive summary",
            "Compile all information",
        ]

        for query in queries:
            normalized = transformer.normalize_query(query)
            intent = transformer.detect_intent(normalized)
            assert intent == QueryIntent.REPORT

    def test_detect_explain_intent(self):
        """Test EXPLAIN intent detection"""
        transformer = QueryTransformer()

        queries = [
            "Explain how the system works",
            "How does the compressor operate?",
            "Why does the pressure increase?",
        ]

        for query in queries:
            normalized = transformer.normalize_query(query)
            intent = transformer.detect_intent(normalized)
            assert intent == QueryIntent.EXPLAIN

    def test_equipment_tag_defaults_to_ask(self):
        """Test that equipment tags alone default to ASK intent (Task 2.2)"""
        transformer = QueryTransformer()

        # Single equipment tag without location keywords should be ASK
        intent = transformer.detect_intent("KT06101")
        assert intent == QueryIntent.ASK, "Equipment tag alone should return ASK intent"

        intent = transformer.detect_intent("V-202")
        assert intent == QueryIntent.ASK, "Equipment tag alone should return ASK intent"

        intent = transformer.detect_intent("pump P-301A")
        assert (
            intent == QueryIntent.ASK
        ), "Equipment tag with type should return ASK intent"

    def test_equipment_tag_with_location_keywords(self):
        """Test that equipment tags with location keywords return LOCATE intent"""
        transformer = QueryTransformer()

        # Equipment tag WITH location keywords should be LOCATE
        queries_locate = [
            "where is KT06101",
            "locate V-202",
            "find pump P-301A",
            "KT06101 location",
            "position of V-202",
            "page containing P-301A",
        ]

        for query in queries_locate:
            normalized = transformer.normalize_query(query)
            intent = transformer.detect_intent(normalized)
            assert (
                intent == QueryIntent.LOCATE
            ), f"Query '{query}' with location keyword should return LOCATE"

    def test_equipment_tag_with_property_questions(self):
        """Test that equipment tags with property questions return ASK intent"""
        transformer = QueryTransformer()

        # Equipment tag with property questions should be ASK
        queries_ask = [
            "what is the pressure of KT06101",
            "KT06101 specifications",
            "V-202 operating temperature",
            "P-301A flow rate",
            "maximum pressure KT06101",
        ]

        for query in queries_ask:
            normalized = transformer.normalize_query(query)
            intent = transformer.detect_intent(normalized)
            assert (
                intent == QueryIntent.ASK
            ), f"Query '{query}' about properties should return ASK"


class TestFilterParsing:
    """Test filter parsing functionality"""

    def test_parse_basic_filters(self):
        """Test basic filter parsing"""
        transformer = QueryTransformer()

        filters_dict = {
            "doc_category": ["datasheet", "pid"],
            "doc_id": ["doc-001", "doc-002"],
        }

        filters = transformer.parse_filters(filters_dict)
        assert filters.doc_categories == ["datasheet", "pid"]
        assert filters.doc_ids == ["doc-001", "doc-002"]

    def test_parse_alternative_keys(self):
        """Test parsing with alternative key names"""
        transformer = QueryTransformer()

        filters_dict = {
            "doc_categories": ["om", "sop"],  # plural form
            "doc_ids": ["doc-003"],  # plural form
        }

        filters = transformer.parse_filters(filters_dict)
        assert filters.doc_categories == ["om", "sop"]
        assert filters.doc_ids == ["doc-003"]

    def test_parse_empty_filters(self):
        """Test parsing empty filters"""
        transformer = QueryTransformer()

        filters = transformer.parse_filters({})
        assert filters.doc_categories is None
        assert filters.doc_ids is None
        assert filters.metadata == {}

    def test_parse_with_metadata(self):
        """Test parsing with metadata"""
        transformer = QueryTransformer()

        filters_dict = {"metadata": {"equipment": "compressor", "priority": "high"}}

        filters = transformer.parse_filters(filters_dict)
        assert filters.metadata["equipment"] == "compressor"
        assert filters.metadata["priority"] == "high"


class TestTechnicalTermsDetection:
    """Test technical terms detection"""

    def test_detect_pressure_units(self):
        """Test detection of pressure units"""
        transformer = QueryTransformer()

        assert transformer._has_technical_terms("10 bar pressure")
        assert transformer._has_technical_terms("150 psi maximum")
        assert transformer._has_technical_terms("2.5 MPa operating")

    def test_detect_temperature_units(self):
        """Test detection of temperature units"""
        transformer = QueryTransformer()

        assert transformer._has_technical_terms("25°C ambient")
        assert transformer._has_technical_terms("100°F maximum")
        assert transformer._has_technical_terms("373 K boiling point")

    def test_detect_technical_parameters(self):
        """Test detection of technical parameters"""
        transformer = QueryTransformer()

        assert transformer._has_technical_terms("flow rate specification")
        assert transformer._has_technical_terms("pressure drop across valve")
        assert transformer._has_technical_terms("temperature sensor reading")

    def test_detect_equipment_tags(self):
        """Test detection of equipment tags"""
        transformer = QueryTransformer()

        assert transformer._has_technical_terms("KT06101 compressor")
        assert transformer._has_technical_terms("valve V-202")
        assert transformer._has_technical_terms("pump P-301A")

    def test_no_technical_terms(self):
        """Test queries without technical terms"""
        transformer = QueryTransformer()

        assert not transformer._has_technical_terms("What is this?")
        assert not transformer._has_technical_terms("Show me the document")
        assert not transformer._has_technical_terms("Find information")


class TestHyDEGeneration:
    """Test HyDE generation functionality"""

    @patch("app.rag.query_transform.get_llm_client")
    def test_hyde_generation_success(self, mock_get_client):
        """Test successful HyDE generation"""
        # Mock LLM client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = """The CO2 compressor operates at a maximum pressure of 25 bar with inlet conditions of 1.5 bar and 35°C.
The compressor is a centrifugal type with three stages of compression and intercooling between stages."""
        mock_client.generate.return_value = mock_response
        mock_get_client.return_value = mock_client

        transformer = QueryTransformer(enable_hyde=True, hyde_count=2)
        hyde_queries = transformer.generate_hyde(
            "What is the operating pressure of the CO2 compressor?",
            QueryIntent.ASK,
            "en",
        )

        assert len(hyde_queries) > 0
        assert "compressor" in hyde_queries[0].lower()

    @patch("app.rag.query_transform.get_llm_client")
    def test_hyde_generation_failure_handling(self, mock_get_client):
        """Test HyDE generation failure handling"""
        # Mock LLM client to raise exception
        mock_get_client.side_effect = Exception("LLM API error")

        transformer = QueryTransformer(enable_hyde=True)
        hyde_queries = transformer.generate_hyde("Test query", QueryIntent.ASK, "en")

        # Should return empty list on failure
        assert hyde_queries == []

    def test_hyde_disabled(self):
        """Test that HyDE is skipped when disabled"""
        transformer = QueryTransformer(enable_hyde=False)

        result = transformer.transform("What is the pressure?")
        assert result.hyde_queries is None


class TestFullTransformation:
    """Test complete transformation pipeline"""

    def test_basic_transformation(self):
        """Test basic query transformation"""
        result = transform_query(
            "What is the MAXIMUM pressure of KT06101?", enable_hyde=False
        )

        assert result.original == "What is the MAXIMUM pressure of KT06101?"
        assert "maximum" in result.normalized.lower()
        assert "kt06101" in result.normalized.lower()
        # Equipment tag present but no location keyword -> intent should be ASK (Task 2.2)
        assert result.intent == QueryIntent.ASK
        assert result.metadata["has_technical_terms"] == True
        assert result.metadata["word_count"] == 7

    def test_transformation_with_filters(self):
        """Test transformation with filters"""
        filters = {"doc_category": ["datasheet"], "doc_id": ["doc-001"]}

        result = transform_query(
            "Where is valve V-202?", filters=filters, enable_hyde=False
        )

        assert result.intent == QueryIntent.LOCATE
        assert result.filters.doc_categories == ["datasheet"]
        assert result.filters.doc_ids == ["doc-001"]

    @patch("app.rag.query_transform.get_llm_client")
    def test_transformation_with_hyde(self, mock_get_client):
        """Test transformation with HyDE enabled"""
        # Mock LLM client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = "Hypothetical document content"
        mock_client.generate.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = transform_query("Explain the cooling system", enable_hyde=True)

        assert result.intent == QueryIntent.EXPLAIN
        assert result.hyde_queries is not None


class TestPerformance:
    """Test performance characteristics"""

    def test_transformation_speed(self):
        """Test that transformation is fast enough"""
        import time

        transformer = QueryTransformer(enable_hyde=False)

        start = time.time()
        for _ in range(100):
            transformer.transform("What is the operating pressure?")
        elapsed = time.time() - start

        # Should process 100 queries in less than 1 second
        assert elapsed < 1.0

        # Average should be less than 10ms per query
        avg_time = (elapsed / 100) * 1000
        assert avg_time < 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
