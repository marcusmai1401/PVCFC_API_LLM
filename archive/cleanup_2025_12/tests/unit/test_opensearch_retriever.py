"""
Unit tests for OpenSearchBM25Retriever

Tests the OpenSearch BM25 retriever integration.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from app.rag.indexers.opensearch_bm25_retriever import (
    OpenSearchBM25Retriever,
    create_opensearch_retriever,
)


@pytest.fixture
def mock_opensearch_client():
    """Mock OpenSearch client"""
    client = MagicMock()

    # Mock info() for connection test
    client.info.return_value = {"version": {"number": "3.2.0"}}

    # Mock search() response
    client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_score": 10.5,
                    "_source": {
                        "chunk_id": "chunk_001",
                        "doc_id": "doc_001",
                        "text": "Test document about CO2 compressor",
                        "page": 1,
                        "page_start": 1,
                        "page_end": 1,
                        "heading": "Introduction",
                        "title": "CO2 Compressor Manual",
                        "level": 1,
                        "doc_type": "Manual",
                    },
                },
                {
                    "_score": 8.3,
                    "_source": {
                        "chunk_id": "chunk_002",
                        "doc_id": "doc_001",
                        "text": "Compressor specifications and performance curves",
                        "page": 2,
                        "page_start": 2,
                        "page_end": 2,
                        "heading": "Specifications",
                        "title": "CO2 Compressor Manual",
                        "level": 1,
                        "doc_type": "Manual",
                    },
                },
            ]
        }
    }

    # Mock count() response
    client.count.return_value = {"count": 4883}

    # Mock indices.stats() response
    client.indices.stats.return_value = {
        "indices": {
            "rag_chunks": {
                "total": {"store": {"size_in_bytes": 6815744, "size": "6.5mb"}}
            }
        }
    }

    # Mock indices.exists() response
    client.indices.exists.return_value = True

    # Mock cluster.health() response
    client.cluster.health.return_value = {"status": "green"}

    return client


@pytest.fixture
def retriever(mock_opensearch_client):
    """Create retriever with mocked client"""
    with patch(
        "app.rag.indexers.opensearch_bm25_retriever.OpenSearch",
        return_value=mock_opensearch_client,
    ):
        retriever = OpenSearchBM25Retriever(
            host="localhost", port=9200, index_name="rag_chunks"
        )
        # Force client creation
        _ = retriever.client
        return retriever


def test_initialization():
    """Test retriever initialization"""
    retriever = OpenSearchBM25Retriever(
        host="testhost", port=9300, index_name="test_index", k1=1.5, b=0.8
    )

    assert retriever.host == "testhost"
    assert retriever.port == 9300
    assert retriever.index_name == "test_index"
    assert retriever.k1 == 1.5
    assert retriever.b == 0.8


def test_search(retriever):
    """Test search functionality"""
    results = retriever.search("CO2 compressor", top_k=10)

    assert len(results) == 2
    assert results[0]["text"] == "Test document about CO2 compressor"
    assert results[0]["score"] == 10.5
    assert results[0]["metadata"]["chunk_id"] == "chunk_001"
    assert results[0]["metadata"]["page"] == 1
    assert results[0]["rank"] == 1

    assert results[1]["score"] == 8.3
    assert results[1]["metadata"]["doc_id"] == "doc_001"
    assert results[1]["rank"] == 2


def test_search_with_min_score(retriever):
    """Test search with minimum score threshold"""
    results = retriever.search("CO2 compressor", top_k=10, min_score=9.0)

    # Only first result should pass (score 10.5 > 9.0)
    assert len(results) == 1
    assert results[0]["score"] == 10.5


def test_batch_search(retriever):
    """Test batch search functionality"""
    queries = ["CO2 compressor", "torque specifications"]
    results = retriever.batch_search(queries, top_k=5)

    assert isinstance(results, dict)
    assert len(results) == 2
    assert "CO2 compressor" in results
    assert "torque specifications" in results
    assert len(results["CO2 compressor"]) == 2


def test_get_statistics(retriever):
    """Test statistics retrieval"""
    stats = retriever.get_statistics()

    assert stats["num_documents"] == 4883
    assert stats["index_name"] == "rag_chunks"
    assert stats["store_size"] == 6815744
    assert stats["store_size_human"] == "6.5mb"
    assert stats["backend"] == "opensearch"
    assert stats["bm25_params"]["k1"] == 1.2
    assert stats["bm25_params"]["b"] == 0.75


def test_health_check(retriever):
    """Test health check functionality"""
    result = retriever.health_check()

    assert result is True
    retriever.client.info.assert_called()
    retriever.client.indices.exists.assert_called_with(index="rag_chunks")
    retriever.client.cluster.health.assert_called_with(index="rag_chunks")


def test_health_check_index_not_exists(retriever):
    """Test health check when index doesn't exist"""
    retriever.client.indices.exists.return_value = False

    result = retriever.health_check()
    assert result is False


def test_health_check_red_status(retriever):
    """Test health check when cluster status is red"""
    retriever.client.cluster.health.return_value = {"status": "red"}

    result = retriever.health_check()
    assert result is False


def test_search_error_handling(retriever):
    """Test graceful error handling on search failure"""
    retriever.client.search.side_effect = Exception("Connection timeout")

    results = retriever.search("test query")

    # Should return empty list on error
    assert results == []


def test_create_opensearch_retriever():
    """Test factory function"""
    # Patch settings at the config level
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.opensearch_host = "custom_host"
        mock_settings.opensearch_port = 9300
        mock_settings.opensearch_index = "custom_index"

        with patch("app.rag.indexers.opensearch_bm25_retriever.OpenSearch"):
            retriever = create_opensearch_retriever()

            assert retriever.host == "custom_host"
            assert retriever.port == 9300
            assert retriever.index_name == "custom_index"


def test_compatibility_properties(retriever):
    """Test compatibility properties for BM25Indexer interface"""
    # documents property should return empty list with warning
    docs = retriever.documents
    assert docs == []

    # metadata property should return empty list with warning
    meta = retriever.metadata
    assert meta == []


def test_load_index_noop(retriever):
    """Test load_index is a no-op for OpenSearch"""
    # Should not raise error, just log warning
    retriever.load_index("/some/path")
    # No assertion needed, just verify it doesn't crash


def test_tokenize_noop(retriever):
    """Test _tokenize is a no-op for OpenSearch"""
    tokens = retriever._tokenize("test text")
    assert tokens == []


def test_search_query_building(retriever, mock_opensearch_client):
    """Test that search builds correct OpenSearch query"""
    retriever.search("test query", top_k=15)

    # Verify search was called with correct structure
    call_args = mock_opensearch_client.search.call_args
    assert call_args[1]["index"] == "rag_chunks"

    body = call_args[1]["body"]
    assert body["size"] == 15
    assert body["query"]["multi_match"]["query"] == "test query"
    assert body["query"]["multi_match"]["fields"] == ["text^3", "heading^2", "title"]
    assert body["query"]["multi_match"]["type"] == "best_fields"
    assert body["query"]["multi_match"]["operator"] == "or"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
