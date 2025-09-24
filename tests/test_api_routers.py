"""
Tests for Phase 2 API routers (ask, locate, report).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_retriever():
    """Mock retriever for testing."""
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(
        return_value={
            "chunks": [
                {
                    "chunk_id": "test_chunk_1",
                    "content": "Test content about KT06101 with operating pressure of 10 bar",
                    "doc_id": "test_doc_1",
                    "page": 1,
                    "bbox": [100, 200, 300, 400],
                }
            ],
            "scores": [0.95],
            "method": "hybrid",
        }
    )
    return retriever


class TestAskRouter:
    """Tests for /ask endpoint."""

    def test_ask_endpoint_exists(self, client):
        """Test that /ask endpoint exists."""
        response = client.post("/ask", json={"query": "Test query", "max_context": 5})
        # Should return 503 if retriever not initialized, not 404
        assert response.status_code in [503, 422, 500]

    @patch("app.api.routers.ask.get_retriever")
    @patch("app.api.routers.ask.QueryTransformer")
    @patch("app.api.routers.ask.Reranker")
    @patch("app.api.routers.ask.ResponseGenerator")
    @patch("app.api.routers.ask.ChainOfVerification")
    async def test_ask_with_mock_components(
        self,
        mock_cove_class,
        mock_generator_class,
        mock_reranker_class,
        mock_transformer_class,
        mock_get_retriever,
        client,
        mock_retriever,
    ):
        """Test /ask with mocked components."""
        # Setup mocks
        mock_get_retriever.return_value = mock_retriever

        # Create proper TransformedQuery object
        from app.rag.query_transform import QueryFilters, QueryIntent, TransformedQuery

        transformed = TransformedQuery(
            original="Test query",
            normalized="test query normalized",
            intent=QueryIntent.ASK,
            filters=QueryFilters(),
            hyde_queries=None,
            language="vi",
        )

        mock_transformer = MagicMock()
        mock_transformer.transform = MagicMock(return_value=transformed)
        mock_transformer_class.return_value = mock_transformer

        # Create proper RetrievalResult objects
        from app.rag.retriever import RetrievalResult

        reranked_results = [
            RetrievalResult(
                chunk_id="test_chunk_1",
                text="Test content about KT06101 with operating pressure of 10 bar",
                score=0.98,
                source="hybrid",
                metadata={"doc_id": "test_doc_1", "page": 1},
                doc_id="test_doc_1",
                page=1,
            )
        ]

        mock_reranker = MagicMock()
        mock_reranker.rerank = MagicMock(return_value=reranked_results)
        mock_reranker_class.return_value = mock_reranker

        # Create proper GeneratedAnswer object
        from app.rag.generator import Citation, GeneratedAnswer

        generated_answer = GeneratedAnswer(
            query="Test query",
            answer="The operating pressure is 10 bar.",
            citations=[
                Citation(
                    doc_id="test_doc_1",
                    source="test",
                    page=1,
                    text_snippet="Test content",
                    relevance_score=0.95,
                )
            ],
            confidence=0.95,
            metadata={"model": "test"},
        )

        mock_generator = MagicMock()
        mock_generator.generate = MagicMock(return_value=generated_answer)
        mock_generator_class.return_value = mock_generator

        mock_cove = MagicMock()
        mock_cove.run_verification = AsyncMock(
            return_value={
                "adjusted_answer": "The operating pressure is 10 bar.",
                "warnings": [],
                "verification_rate": 1.0,
                "checkpoints": [],
            }
        )
        mock_cove_class.return_value = mock_cove

        # Make request
        response = client.post(
            "/ask",
            json={
                "query": "What is the operating pressure?",
                "max_context": 5,
                "hyde": False,
            },
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "citations" in data
        assert "meta" in data


class TestLocateRouter:
    """Tests for /locate endpoint."""

    def test_locate_endpoint_exists(self, client):
        """Test that /locate endpoint exists."""
        response = client.post("/locate", json={"query": "KT06101", "max_hits": 10})
        # Should return 503 if retriever not initialized, not 404
        assert response.status_code in [503, 422, 500]

    @patch("app.api.routers.locate.get_retriever")
    @patch("app.services.locator.LocatorService.locate")
    async def test_locate_with_mock(
        self, mock_locate, mock_get_retriever, client, mock_retriever
    ):
        """Test /locate with mocked components."""
        # Setup mocks
        mock_get_retriever.return_value = mock_retriever
        mock_locate.return_value = {
            "hits": [
                {
                    "doc_id": "test_doc_1",
                    "page": 3,
                    "bbox": [100, 200, 300, 400],
                    "score": 0.95,
                    "snippet": "...KT06101 valve...",
                }
            ],
            "total_found": 1,
            "entity_type": "equipment",
        }

        # Make request
        response = client.post("/locate", json={"query": "KT06101", "max_hits": 10})

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "hits" in data
        assert "total_found" in data
        assert "meta" in data


class TestReportRouter:
    """Tests for /report endpoint."""

    def test_report_endpoint_exists(self, client):
        """Test that /report endpoint exists."""
        response = client.post(
            "/report",
            json={"topic": "Test topic", "sub_queries": ["Query 1", "Query 2"]},
        )
        # Should return 503 if retriever not initialized, not 404
        assert response.status_code in [503, 422, 500]

    @patch("app.api.routers.report.get_retriever")
    @patch("app.services.reporter.ReporterService.generate_report")
    async def test_report_with_mock(
        self, mock_generate_report, mock_get_retriever, client, mock_retriever
    ):
        """Test /report with mocked components."""
        # Setup mocks
        mock_get_retriever.return_value = mock_retriever
        mock_generate_report.return_value = {
            "title": "Test Report",
            "sections": [
                {"heading": "Section 1", "content": "Content 1", "citations": []}
            ],
            "summary": "Test summary",
            "total_citations": 0,
        }

        # Make request
        response = client.post(
            "/report",
            json={
                "topic": "Test topic",
                "sub_queries": ["Query 1", "Query 2"],
                "format": "markdown",
            },
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "title" in data
        assert "sections" in data
        assert "meta" in data


class TestMonitoringEndpoints:
    """Tests for monitoring endpoints."""

    def test_metrics_endpoint(self, client):
        """Test /metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        # Should return Prometheus format
        assert "text/plain" in response.headers["content-type"]

    def test_trace_endpoint(self, client):
        """Test /trace endpoint."""
        response = client.get("/trace")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "trace_id" in data

    def test_index_stats_endpoint(self, client):
        """Test /index-stats endpoint."""
        response = client.get("/index-stats")
        assert response.status_code == 200
        data = response.json()
        assert "bm25" in data
        assert "faiss" in data
