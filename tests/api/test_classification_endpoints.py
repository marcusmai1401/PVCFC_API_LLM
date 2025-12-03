"""
Unit tests for Classification API endpoints

Tests:
- POST /classification/classify - Document classification
- GET /classification/taxonomy - Taxonomy structure
- GET /classification/documents/by-category - Documents by category
- GET /classification/categories - List categories
- GET /classification/doc-types - List doc types

Requirements: 9.1, 9.2, 9.3
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.routers.classification import router
from app.classification.taxonomy import DocumentTaxonomy, get_taxonomy
from app.classification.classifier import ClassificationResult
from app.classification.pipeline import ClassificationPipeline


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
def mock_classification_result():
    """Mock classification result"""
    return ClassificationResult(
        category="ENGINEERING_DESIGN",
        doc_type="P&ID",
        confidence=0.95,
        status="classified",
        dominant_content="drawing",
        page_analysis=[],
        reasoning="High confidence P&ID detection",
        method="cadlike_gate"
    )


class TestTaxonomyEndpoint:
    """Tests for GET /classification/taxonomy endpoint"""
    
    def test_taxonomy_response_format(self, client):
        """Test taxonomy endpoint returns correct format"""
        response = client.get("/classification/taxonomy")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "categories" in data
        assert "total_categories" in data
        assert "total_doc_types" in data
        
        # Verify data types
        assert isinstance(data["categories"], list)
        assert isinstance(data["total_categories"], int)
        assert isinstance(data["total_doc_types"], int)
        
    def test_taxonomy_contains_all_categories(self, client):
        """Test taxonomy contains all 5 categories"""
        response = client.get("/classification/taxonomy")
        
        assert response.status_code == 200
        data = response.json()
        
        category_names = [cat["name"] for cat in data["categories"]]
        
        # Verify all categories present
        assert "ENGINEERING_DESIGN" in category_names
        assert "VENDOR_EQUIPMENT" in category_names
        assert "OPERATIONS_MAINTENANCE" in category_names
        assert "SAFETY_MANAGEMENT" in category_names
        assert "UNCATEGORIZED" in category_names
        
    def test_taxonomy_category_structure(self, client):
        """Test each category has required fields"""
        response = client.get("/classification/taxonomy")
        
        assert response.status_code == 200
        data = response.json()
        
        for category in data["categories"]:
            assert "name" in category
            assert "display_name" in category
            assert "doc_types" in category
            assert isinstance(category["doc_types"], list)
            
    def test_engineering_design_doc_types(self, client):
        """Test ENGINEERING_DESIGN has correct doc_types"""
        response = client.get("/classification/taxonomy")
        
        assert response.status_code == 200
        data = response.json()
        
        eng_design = next(
            (cat for cat in data["categories"] if cat["name"] == "ENGINEERING_DESIGN"),
            None
        )
        
        assert eng_design is not None
        assert "P&ID" in eng_design["doc_types"]
        assert "Drawing" in eng_design["doc_types"]
        assert "Technical Data" in eng_design["doc_types"]


class TestCategoriesEndpoint:
    """Tests for GET /classification/categories endpoint"""
    
    def test_categories_list(self, client):
        """Test categories endpoint returns list of category names"""
        response = client.get("/classification/categories")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 5  # 4 main + UNCATEGORIZED
        assert "ENGINEERING_DESIGN" in data
        assert "UNCATEGORIZED" in data


class TestDocTypesEndpoint:
    """Tests for GET /classification/doc-types endpoint"""
    
    def test_all_doc_types(self, client):
        """Test doc-types endpoint returns all doc types"""
        response = client.get("/classification/doc-types")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert "P&ID" in data
        assert "Datasheet" in data
        assert "MOC" in data
        
    def test_doc_types_filtered_by_category(self, client):
        """Test doc-types filtered by category"""
        response = client.get("/classification/doc-types?category=ENGINEERING_DESIGN")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert "P&ID" in data
        assert "Drawing" in data
        # Should not contain doc_types from other categories
        assert "Datasheet" not in data
        assert "MOC" not in data
        
    def test_invalid_category_filter(self, client):
        """Test invalid category returns 400 error"""
        response = client.get("/classification/doc-types?category=INVALID_CATEGORY")
        
        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]


class TestClassifyEndpoint:
    """Tests for POST /classification/classify endpoint"""
    
    def test_classify_requires_doc_id(self, client):
        """Test classify endpoint requires doc_id"""
        response = client.post("/classification/classify", json={})
        assert response.status_code == 422  # Validation error
        
    def test_classify_requires_pdf_path(self, client):
        """Test classify endpoint requires pdf_path when doc_id lookup not implemented"""
        response = client.post(
            "/classification/classify",
            json={"doc_id": "test_doc"}
        )
        # Should return 400 because pdf_path is required
        assert response.status_code == 400
        assert "pdf_path is required" in response.json()["detail"]
        
    def test_classify_pdf_not_found(self, client):
        """Test classify returns 404 for non-existent PDF"""
        response = client.post(
            "/classification/classify",
            json={
                "doc_id": "test_doc",
                "pdf_path": "/nonexistent/path.pdf"
            }
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        
    def test_classify_response_format(self, test_app, mock_classification_result, tmp_path):
        """Test classify returns correct response format"""
        # Create a temporary PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test content")
        
        with patch('app.api.routers.classification.get_pipeline_dependency') as mock_get_pipeline:
            mock_pipeline = MagicMock(spec=ClassificationPipeline)
            mock_pipeline.classify_with_fallback.return_value = mock_classification_result
            mock_get_pipeline.return_value = mock_pipeline
            
            client = TestClient(test_app)
            response = client.post(
                "/classification/classify",
                json={
                    "doc_id": "test_doc",
                    "pdf_path": str(pdf_file)
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert "category" in data
            assert "doc_type" in data
            assert "confidence" in data
            assert "status" in data
            assert "dominant_content" in data
            assert "method" in data
            
    def test_classify_force_reclassify(self, test_app, mock_classification_result, tmp_path):
        """Test force_reclassify parameter"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test content")
        
        with patch('app.api.routers.classification.get_pipeline_dependency') as mock_get_pipeline:
            mock_pipeline = MagicMock(spec=ClassificationPipeline)
            mock_pipeline.classify_with_fallback.return_value = mock_classification_result
            mock_get_pipeline.return_value = mock_pipeline
            
            client = TestClient(test_app)
            response = client.post(
                "/classification/classify",
                json={
                    "doc_id": "test_doc",
                    "pdf_path": str(pdf_file),
                    "force_reclassify": True
                }
            )
            
            assert response.status_code == 200


class TestDocumentsByCategoryEndpoint:
    """Tests for GET /classification/documents/by-category endpoint"""
    
    def test_documents_by_category_response_format(self, client):
        """Test documents by category returns correct format"""
        response = client.get("/classification/documents/by-category")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # Each item should have category, doc_types, total_documents
        for item in data:
            assert "category" in item
            assert "doc_types" in item
            assert "total_documents" in item
            
    def test_documents_filtered_by_category(self, client):
        """Test filtering by category"""
        response = client.get(
            "/classification/documents/by-category?category=ENGINEERING_DESIGN"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only return ENGINEERING_DESIGN category
        assert len(data) == 1
        assert data[0]["category"] == "ENGINEERING_DESIGN"
        
    def test_documents_invalid_category(self, client):
        """Test invalid category returns 400"""
        response = client.get(
            "/classification/documents/by-category?category=INVALID"
        )
        
        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]
        
    def test_documents_invalid_doc_type(self, client):
        """Test invalid doc_type returns 400"""
        response = client.get(
            "/classification/documents/by-category?doc_type=INVALID"
        )
        
        assert response.status_code == 400
        assert "Invalid doc_type" in response.json()["detail"]
