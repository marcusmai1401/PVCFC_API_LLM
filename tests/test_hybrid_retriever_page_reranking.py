"""
Unit Tests for HybridRetriever Page Reranking Integration

Tests the integration of CitationRetriever page-level reranking into HybridRetriever.
"""

from typing import List
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.rag.retriever import HybridRetriever, HybridSearchConfig, RetrievalResult


class TestHybridRetrieverPageReranking:
    """Test page reranking integration in HybridRetriever"""

    @pytest.fixture
    def mock_citation_result(self):
        """Create a mock CitationResult"""
        from app.rag.citation_retriever import CitationResult
        from app.rag.snippet_extractor import Snippet

        snippet = Snippet(
            text="operating pressure",
            start_pos=10,
            end_pos=28,
            matched_keywords={"operating", "pressure"},
            score=0.95,
            highlighted_text="**operating pressure**",
        )

        return CitationResult(
            doc_id="doc_123",
            page=5,
            score=0.85,
            page_text="The operating pressure is 150 PSI at normal conditions.",
            snippets=[snippet],
            metadata={"doc_name": "Test Manual"},
            rank=1,
        )

    @pytest.fixture
    def retriever_instance(self):
        """Create HybridRetriever instance with page reranking enabled"""
        config = HybridSearchConfig(
            enable_page_reranking=True,
            enable_page_range_expansion=False,  # Should be disabled by mutual exclusion
            top_k_pages_per_doc=3,
            max_snippets_per_page=2,
        )
        return HybridRetriever(config=config)

    def test_config_mutual_exclusion(self):
        """Test that page_reranking and page_range_expansion are mutually exclusive"""
        config = HybridSearchConfig(
            enable_page_reranking=True,
            enable_page_range_expansion=True,  # Both enabled
        )

        retriever = HybridRetriever(config=config)

        # page_range_expansion should be disabled
        assert retriever.config.enable_page_reranking is True
        assert retriever.config.enable_page_range_expansion is False

    def test_extract_doc_ids_from_results(self, retriever_instance):
        """Test extraction of unique doc_ids from results"""
        results = [
            RetrievalResult(
                chunk_id="c1",
                text="text1",
                score=0.9,
                source="bm25",
                metadata={},
                doc_id="doc_A",
            ),
            RetrievalResult(
                chunk_id="c2",
                text="text2",
                score=0.8,
                source="bm25",
                metadata={},
                doc_id="doc_B",
            ),
            RetrievalResult(
                chunk_id="c3",
                text="text3",
                score=0.7,
                source="faiss",
                metadata={},
                doc_id="doc_A",  # Duplicate
            ),
            RetrievalResult(
                chunk_id="c4",
                text="text4",
                score=0.6,
                source="faiss",
                metadata={},
                doc_id="doc_C",
            ),
        ]

        doc_ids = retriever_instance._extract_doc_ids_from_results(results, top_n=10)

        # Should return unique doc_ids in order of first appearance
        assert doc_ids == ["doc_A", "doc_B", "doc_C"]

    def test_extract_doc_ids_respects_top_n(self, retriever_instance):
        """Test that extraction respects top_n limit"""
        results = [
            RetrievalResult(
                chunk_id=f"c{i}",
                text=f"text{i}",
                score=1.0 - i * 0.1,
                source="bm25",
                metadata={},
                doc_id=f"doc_{i}",
            )
            for i in range(10)
        ]

        doc_ids = retriever_instance._extract_doc_ids_from_results(results, top_n=3)

        assert len(doc_ids) == 3
        assert doc_ids == ["doc_0", "doc_1", "doc_2"]

    def test_extract_doc_ids_handles_none(self, retriever_instance):
        """Test extraction handles None doc_ids"""
        results = [
            RetrievalResult(
                chunk_id="c1",
                text="text1",
                score=0.9,
                source="bm25",
                metadata={},
                doc_id="doc_A",
            ),
            RetrievalResult(
                chunk_id="c2",
                text="text2",
                score=0.8,
                source="bm25",
                metadata={},
                doc_id=None,  # None doc_id
            ),
            RetrievalResult(
                chunk_id="c3",
                text="text3",
                score=0.7,
                source="faiss",
                metadata={},
                doc_id="doc_B",
            ),
        ]

        doc_ids = retriever_instance._extract_doc_ids_from_results(results, top_n=10)

        # Should skip None doc_ids
        assert doc_ids == ["doc_A", "doc_B"]

    def test_citations_to_retrieval_results_conversion(
        self, retriever_instance, mock_citation_result
    ):
        """Test conversion from CitationResult to RetrievalResult"""
        citations = [mock_citation_result]

        results = retriever_instance._citations_to_retrieval_results(citations)

        assert len(results) == 1
        result = results[0]

        # Check basic fields
        assert result.chunk_id == "page_doc_123_5"
        assert result.text == mock_citation_result.page_text
        assert result.score == 0.85
        assert result.source == "page_reranked"
        assert result.doc_id == "doc_123"
        assert result.page == 5
        assert result.bbox is None
        assert result.parent_id is None

        # Check metadata
        assert result.metadata["page_level_result"] is True
        assert result.metadata["citation_rank"] == 1
        assert result.metadata["page"] == 5
        assert result.metadata["doc_name"] == "Test Manual"

        # Check snippets in metadata
        assert "snippets" in result.metadata
        assert len(result.metadata["snippets"]) == 1
        snippet = result.metadata["snippets"][0]
        assert snippet["text"] == "operating pressure"
        assert snippet["highlighted"] == "**operating pressure**"
        assert snippet["score"] == 0.95

    def test_citations_to_retrieval_results_empty_snippets(self, retriever_instance):
        """Test conversion with no snippets"""
        from app.rag.citation_retriever import CitationResult

        citation = CitationResult(
            doc_id="doc_456",
            page=10,
            score=0.75,
            page_text="Some page text without snippets.",
            snippets=[],  # No snippets
            metadata={"doc_name": "Other Doc"},
            rank=2,
        )

        results = retriever_instance._citations_to_retrieval_results([citation])

        assert len(results) == 1
        result = results[0]

        # Snippets should be empty list in metadata
        assert "snippets" in result.metadata
        assert result.metadata["snippets"] == []

    def test_citations_to_retrieval_results_multiple(self, retriever_instance):
        """Test conversion with multiple citations"""
        from app.rag.citation_retriever import CitationResult

        citations = [
            CitationResult(
                doc_id=f"doc_{i}",
                page=i + 1,
                score=1.0 - i * 0.1,
                page_text=f"Page text {i}",
                snippets=[],
                metadata={},
                rank=i + 1,
            )
            for i in range(5)
        ]

        results = retriever_instance._citations_to_retrieval_results(citations)

        assert len(results) == 5

        # Check ordering preserved
        for i, result in enumerate(results):
            assert result.doc_id == f"doc_{i}"
            assert result.page == i + 1
            assert result.score == 1.0 - i * 0.1
            assert result.metadata["citation_rank"] == i + 1

    @patch("app.rag.citation_retriever.get_citation_retriever")
    def test_rerank_at_page_level_integration(
        self, mock_get_retriever, retriever_instance, mock_citation_result
    ):
        """Test _rerank_at_page_level calls CitationRetriever correctly"""
        # Mock CitationRetriever
        mock_retriever = MagicMock()
        mock_retriever.search_with_citations.return_value = [mock_citation_result]
        mock_get_retriever.return_value = mock_retriever

        config = retriever_instance.config
        citations = retriever_instance._rerank_at_page_level(
            query="test query", doc_ids=["doc_123", "doc_456"], config=config
        )

        # Verify CitationRetriever was called
        mock_get_retriever.assert_called_once()
        mock_retriever.search_with_citations.assert_called_once()

        # Check call arguments
        call_args = mock_retriever.search_with_citations.call_args
        assert call_args.kwargs["query"] == "test query"
        assert call_args.kwargs["doc_ids"] == ["doc_123", "doc_456"]

        # Check SearchConfig passed
        search_config = call_args.kwargs["config_override"]
        assert search_config.top_k_docs == 2  # len(doc_ids)
        assert search_config.top_k_pages_per_doc == config.top_k_pages_per_doc
        assert search_config.max_snippets_per_page == config.max_snippets_per_page

        # Check return value
        assert citations == [mock_citation_result]

    def test_config_fields_exist(self):
        """Test that all page reranking config fields exist with correct defaults"""
        config = HybridSearchConfig()

        # Check new fields exist
        assert hasattr(config, "enable_page_reranking")
        assert hasattr(config, "top_k_docs_for_page_rerank")
        assert hasattr(config, "top_k_pages_per_doc")
        assert hasattr(config, "max_snippets_per_page")
        assert hasattr(config, "page_reranking_min_score")

        # Check defaults
        assert config.enable_page_reranking is False  # Default OFF
        assert config.top_k_docs_for_page_rerank is None
        assert config.top_k_pages_per_doc == 3
        assert config.max_snippets_per_page == 3
        assert config.page_reranking_min_score == 0.0

    def test_backward_compatibility_default_config(self):
        """Test that default config maintains backward compatibility"""
        config = HybridSearchConfig()
        retriever = HybridRetriever(config=config)

        # Page reranking should be OFF by default
        assert retriever.config.enable_page_reranking is False

        # Page range expansion should still work
        assert retriever.config.enable_page_range_expansion is True


class TestPageRerankingE2EMock:
    """End-to-end mock tests for page reranking flow"""

    @patch("app.rag.citation_retriever.get_citation_retriever")
    def test_search_with_page_reranking_enabled(self, mock_get_retriever):
        """Test full search flow with page reranking enabled"""
        from app.rag.citation_retriever import CitationResult
        from app.rag.query_transform import QueryFilters, TransformedQuery

        # Setup mock citation retriever
        mock_retriever = MagicMock()
        citation = CitationResult(
            doc_id="doc_test",
            page=1,
            score=0.9,
            page_text="Test page text with relevant content.",
            snippets=[],
            metadata={"doc_name": "Test Doc"},
            rank=1,
        )
        mock_retriever.search_with_citations.return_value = [citation]
        mock_get_retriever.return_value = mock_retriever

        # Create retriever with page reranking
        config = HybridSearchConfig(
            enable_page_reranking=True,
            top_rrf=5,
        )
        retriever = HybridRetriever(config=config)

        # Mock BM25 indexer (minimal setup)
        retriever.bm25_indexer = MagicMock()
        retriever.bm25_indexer.search.return_value = [
            {
                "chunk_id": "chunk_1",
                "text": "test chunk",
                "score": 0.8,
                "metadata": {"doc_id": "doc_test", "page": 1},
            }
        ]

        # Create test query
        query = TransformedQuery(
            original="test query",
            normalized="test query",
            intent="search",
            filters=QueryFilters(),
            hyde_queries=[],
        )

        # Execute search
        results = retriever.search(query, config_override=config)

        # Verify results are page-level
        assert len(results) == 1
        result = results[0]

        assert result.source == "page_reranked"
        assert result.doc_id == "doc_test"
        assert result.page == 1
        assert result.metadata["page_level_result"] is True
        assert result.text == "Test page text with relevant content."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
