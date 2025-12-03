"""
Unit tests for Deep Search API endpoints

Tests:
- Request validation (keyword parameter)
- Response format validation
- Error responses (503, 500)
- Filter parameters

Requirements: 5.1, 9.1
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.routers.search import router, DeepSearchResponseModel, DeepSearchResultModel
from app.services.deep_search import DeepSearchResponse, DeepSearchResult, DeepSearchService


# Create test app
def create_test_app() -> FastAPI:
    """Create FastAPI app for testing"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def test_app():
    """Test app fixture"""
    return create_test_app()


@pytest.fixture
def client(test_app):
    """Test client fixture"""
    return TestClient(test_app)


@pytest.fixture
def mock_opensearch_client():
    """Mock OpenSearch client"""
    return MagicMock()


@pytest.fixture
def mock_search_response():
    """Mock search response"""
    return DeepSearchResponse(
        query="test keyword",
        total_documents=2,
        results=[
            DeepSearchResult(
                doc_id="doc1",
                filename="test1.pdf",
                category="ENGINEERING_DESIGN",
                doc_type="P&ID",
                occurrence_count=5,
                first_page=1,
                snippet="...test keyword..."
            ),
            DeepSearchResult(
                doc_id="doc2",
                filename="test2.pdf",
                category="VENDOR_EQUIPMENT",
                doc_type="Datasheet",
                occurrence_count=3,
                first_page=2,
                snippet="...test keyword..."
            )
        ],
        results_by_category={
            "ENGINEERING_DESIGN": [
                DeepSearchResult(
                    doc_id="doc1",
                    filename="test1.pdf",
                    category="ENGINEERING_DESIGN",
                    doc_type="P&ID",
                    occurrence_count=5,
                    first_page=1,
                    snippet="...test keyword..."
                )
            ],
            "VENDOR_EQUIPMENT": [
                DeepSearchResult(
                    doc_id="doc2",
                    filename="test2.pdf",
                    category="VENDOR_EQUIPMENT",
                    doc_type="Datasheet",
                    occurrence_count=3,
                    first_page=2,
                    snippet="...test keyword..."
                )
            ]
        }
    )


class TestDeepSearchEndpoint:
    """Tests for GET /search/documents endpoint"""
    
    def test_keyword_required(self, client):
        """Test that keyword parameter is required"""
        response = client.get("/search/documents")
        assert response.status_code == 422  # Validation error
        
    def test_keyword_min_length(self, client):
        """Test keyword minimum length validation"""
        response = client.get("/search/documents?keyword=")
        assert response.status_code == 422
        
    def test_keyword_max_length(self, client):
        """Test keyword maximum length validation"""
        long_keyword = "a" * 201
        response = client.get(f"/search/documents?keyword={long_keyword}")
        assert response.status_code == 422
        
    def test_max_results_validation(self, client):
        """Test max_results parameter validation"""
        # Below minimum
        response = client.get("/search/documents?keyword=test&max_results=0")
        assert response.status_code == 422
        
        # Above maximum
        response = client.get("/search/documents?keyword=test&max_results=10001")
        assert response.status_code == 422

    def test_successful_search_response_format(self, test_app, mock_search_response):
        """Test successful search returns correct response format"""
        # Setup mock
        with patch('app.api.routers.search.get_deep_search_service') as mock_get_service:
            mock_service = MagicMock(spec=DeepSearchService)
            mock_service.search.return_value = mock_search_response
            mock_get_service.return_value = mock_service
            
            client = TestClient(test_app)
            response = client.get("/search/documents?keyword=test")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert "query" in data
            assert "total_documents" in data
            assert "results" in data
            assert "results_by_category" in data
            
            # Verify data types
            assert isinstance(data["query"], str)
            assert isinstance(data["total_documents"], int)
            assert isinstance(data["results"], list)
            assert isinstance(data["results_by_category"], dict)
            
    def test_search_result_fields(self, test_app, mock_search_response):
        """Test search result contains all required fields"""
        with patch('app.api.routers.search.get_deep_search_service') as mock_get_service:
            mock_service = MagicMock(spec=DeepSearchService)
            mock_service.search.return_value = mock_search_response
            mock_get_service.return_value = mock_service
            
            client = TestClient(test_app)
            response = client.get("/search/documents?keyword=test")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check first result has all required fields
            if data["results"]:
                result = data["results"][0]
                assert "doc_id" in result
                assert "filename" in result
                assert "category" in result
                assert "doc_type" in result
                assert "occurrence_count" in result
                assert "first_page" in result
                # snippet is optional
                
    def test_category_filter_passed_to_service(self, test_app, mock_search_response):
        """Test category filter is passed to service"""
        with patch('app.api.routers.search.get_deep_search_service') as mock_get_service:
            mock_service = MagicMock(spec=DeepSearchService)
            mock_service.search.return_value = mock_search_response
            mock_get_service.return_value = mock_service
            
            client = TestClient(test_app)
            response = client.get(
                "/search/documents?keyword=test&category=ENGINEERING_DESIGN"
            )
            
            assert response.status_code == 200
            mock_service.search.assert_called_once()
            call_kwargs = mock_service.search.call_args[1]
            assert call_kwargs["category_filter"] == "ENGINEERING_DESIGN"
            
    def test_doc_type_filter_passed_to_service(self, test_app, mock_search_response):
        """Test doc_type filter is passed to service"""
        with patch('app.api.routers.search.get_deep_search_service') as mock_get_service:
            mock_service = MagicMock(spec=DeepSearchService)
            mock_service.search.return_value = mock_search_response
            mock_get_service.return_value = mock_service
            
            client = TestClient(test_app)
            response = client.get(
                "/search/documents?keyword=test&doc_type=P%26ID"
            )
            
            assert response.status_code == 200
            mock_service.search.assert_called_once()
            call_kwargs = mock_service.search.call_args[1]
            assert call_kwargs["doc_type_filter"] == "P&ID"
            
    def test_service_unavailable_error(self, test_app):
        """Test 503 error when service is unavailable"""
        with patch('app.api.routers.search.get_deep_search_service') as mock_get_service:
            mock_service = MagicMock(spec=DeepSearchService)
            mock_service.search.side_effect = RuntimeError("OpenSearch not configured")
            mock_get_service.return_value = mock_service
            
            client = TestClient(test_app)
            response = client.get("/search/documents?keyword=test")
            
            assert response.status_code == 503
            assert "unavailable" in response.json()["detail"].lower()
            
    def test_internal_error(self, test_app):
        """Test 500 error on internal failure"""
        with patch('app.api.routers.search.get_deep_search_service') as mock_get_service:
            mock_service = MagicMock(spec=DeepSearchService)
            mock_service.search.side_effect = Exception("Unexpected error")
            mock_get_service.return_value = mock_service
            
            client = TestClient(test_app)
            response = client.get("/search/documents?keyword=test")
            
            assert response.status_code == 500
            assert "failed" in response.json()["detail"].lower()
            
    def test_results_grouped_by_category(self, test_app, mock_search_response):
        """Test results are properly grouped by category"""
        with patch('app.api.routers.search.get_deep_search_service') as mock_get_service:
            mock_service = MagicMock(spec=DeepSearchService)
            mock_service.search.return_value = mock_search_response
            mock_get_service.return_value = mock_service
            
            client = TestClient(test_app)
            response = client.get("/search/documents?keyword=test")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify grouping
            assert "ENGINEERING_DESIGN" in data["results_by_category"]
            assert "VENDOR_EQUIPMENT" in data["results_by_category"]
            
            # Verify each group has correct category
            for cat, results in data["results_by_category"].items():
                for result in results:
                    assert result["category"] == cat
