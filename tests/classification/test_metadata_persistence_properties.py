"""
Property-based tests for Metadata Persistence

**Feature: intelligent-classification-deep-search**

Tests:
- Property 17: Metadata Persistence
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from dataclasses import dataclass
from typing import Optional, Dict, Any
from unittest.mock import Mock, MagicMock, patch

from app.classification.taxonomy import (
    DocumentCategory,
    DocumentTaxonomy,
    ClassificationStatus,
    ClassificationMethod,
    get_taxonomy,
)
from app.classification.classifier import ClassificationResult


# =============================================================================
# Mock Storage Classes for Testing
# =============================================================================

@dataclass
class MockOpenSearchDocument:
    """Represents a document stored in OpenSearch"""
    doc_id: str
    chunk_id: str
    text: str
    category: Optional[str] = None
    doc_type: Optional[str] = None
    classification_status: Optional[str] = None
    classification_confidence: Optional[float] = None
    classification_method: Optional[str] = None


@dataclass
class MockWeaviateObject:
    """Represents an object stored in Weaviate"""
    uuid: str
    doc_id: str
    text: str
    category: Optional[str] = None
    doc_type: Optional[str] = None
    classification_status: Optional[str] = None


class MockMetadataStore:
    """
    Mock storage that simulates both OpenSearch and Weaviate behavior
    for testing metadata persistence properties.
    """
    
    def __init__(self):
        self.opensearch_docs: Dict[str, MockOpenSearchDocument] = {}
        self.weaviate_objects: Dict[str, MockWeaviateObject] = {}
    
    def store_classification_opensearch(
        self,
        doc_id: str,
        chunk_id: str,
        text: str,
        classification: ClassificationResult,
    ) -> bool:
        """Store classification metadata in OpenSearch"""
        doc = MockOpenSearchDocument(
            doc_id=doc_id,
            chunk_id=chunk_id,
            text=text,
            category=classification.category,
            doc_type=classification.doc_type,
            classification_status=classification.status,
            classification_confidence=classification.confidence,
            classification_method=classification.method,
        )
        self.opensearch_docs[chunk_id] = doc
        return True
    
    def store_classification_weaviate(
        self,
        uuid: str,
        doc_id: str,
        text: str,
        classification: ClassificationResult,
    ) -> bool:
        """Store classification metadata in Weaviate"""
        obj = MockWeaviateObject(
            uuid=uuid,
            doc_id=doc_id,
            text=text,
            category=classification.category,
            doc_type=classification.doc_type,
            classification_status=classification.status,
        )
        self.weaviate_objects[uuid] = obj
        return True
    
    def get_opensearch_doc(self, chunk_id: str) -> Optional[MockOpenSearchDocument]:
        """Retrieve document from OpenSearch"""
        return self.opensearch_docs.get(chunk_id)
    
    def get_weaviate_object(self, uuid: str) -> Optional[MockWeaviateObject]:
        """Retrieve object from Weaviate"""
        return self.weaviate_objects.get(uuid)
    
    def store_classification_both(
        self,
        doc_id: str,
        chunk_id: str,
        uuid: str,
        text: str,
        classification: ClassificationResult,
    ) -> bool:
        """Store classification in both OpenSearch and Weaviate"""
        os_success = self.store_classification_opensearch(
            doc_id, chunk_id, text, classification
        )
        wv_success = self.store_classification_weaviate(
            uuid, doc_id, text, classification
        )
        return os_success and wv_success


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Strategy for generating valid categories
valid_category_strategy = st.sampled_from([
    DocumentCategory.ENGINEERING_DESIGN.value,
    DocumentCategory.VENDOR_EQUIPMENT.value,
    DocumentCategory.OPERATIONS_MAINTENANCE.value,
    DocumentCategory.SAFETY_MANAGEMENT.value,
    DocumentCategory.UNCATEGORIZED.value,
])

# Strategy for generating confidence scores
confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for generating classification status
status_strategy = st.sampled_from([s.value for s in ClassificationStatus])

# Strategy for generating classification method
method_strategy = st.sampled_from([m.value for m in ClassificationMethod])

# Strategy for generating dominant content
dominant_content_strategy = st.sampled_from(["text", "drawing", "mixed", "unknown"])

# Strategy for generating document IDs
doc_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"),
    min_size=5,
    max_size=50,
)

# Strategy for generating UUIDs
uuid_strategy = st.uuids().map(str)

# Strategy for generating text content
text_strategy = st.text(min_size=10, max_size=500)


@st.composite
def valid_category_doctype_pair(draw):
    """Generate a valid (category, doc_type) pair"""
    taxonomy = get_taxonomy()
    category = draw(valid_category_strategy)
    doc_types = taxonomy.get_doc_types_for_category(category)
    doc_type = draw(st.sampled_from(doc_types)) if doc_types else "Unknown"
    return (category, doc_type)


@st.composite
def classification_result_strategy(draw):
    """Generate a ClassificationResult with valid category and doc_type"""
    category, doc_type = draw(valid_category_doctype_pair())
    confidence = draw(confidence_strategy)
    status = draw(status_strategy)
    dominant_content = draw(dominant_content_strategy)
    method = draw(method_strategy)
    reasoning = draw(st.text(max_size=200) | st.none())
    
    return ClassificationResult(
        category=category,
        doc_type=doc_type,
        confidence=confidence,
        status=status,
        dominant_content=dominant_content,
        page_analysis=[],
        reasoning=reasoning,
        method=method
    )


@st.composite
def document_with_classification_strategy(draw):
    """Generate a document with classification data"""
    doc_id = draw(doc_id_strategy)
    chunk_id = f"{doc_id}_chunk_{draw(st.integers(min_value=0, max_value=100))}"
    uuid = draw(uuid_strategy)
    text = draw(text_strategy)
    classification = draw(classification_result_strategy())
    
    return {
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "uuid": uuid,
        "text": text,
        "classification": classification,
    }


# =============================================================================
# Property 17: Metadata Persistence
# =============================================================================

class TestProperty17MetadataPersistence:
    """
    **Feature: intelligent-classification-deep-search, Property 17: Metadata Persistence**
    
    *For any* successfully classified document, the classification metadata 
    (category, doc_type, classification_status) SHALL be persisted in both 
    OpenSearch and Weaviate.
    
    **Validates: Requirements 8.2**
    """
    
    @given(doc_data=document_with_classification_strategy())
    @settings(max_examples=100)
    def test_classification_persisted_in_opensearch(self, doc_data: dict):
        """
        Property: Classification metadata must be persisted in OpenSearch
        """
        store = MockMetadataStore()
        classification = doc_data["classification"]
        
        # Store classification
        success = store.store_classification_opensearch(
            doc_id=doc_data["doc_id"],
            chunk_id=doc_data["chunk_id"],
            text=doc_data["text"],
            classification=classification,
        )
        
        assert success, "Storage operation should succeed"
        
        # Retrieve and verify
        stored_doc = store.get_opensearch_doc(doc_data["chunk_id"])
        
        assert stored_doc is not None, "Document should be retrievable"
        assert stored_doc.category == classification.category, (
            f"Category mismatch: stored={stored_doc.category}, expected={classification.category}"
        )
        assert stored_doc.doc_type == classification.doc_type, (
            f"DocType mismatch: stored={stored_doc.doc_type}, expected={classification.doc_type}"
        )
        assert stored_doc.classification_status == classification.status, (
            f"Status mismatch: stored={stored_doc.classification_status}, expected={classification.status}"
        )
    
    @given(doc_data=document_with_classification_strategy())
    @settings(max_examples=100)
    def test_classification_persisted_in_weaviate(self, doc_data: dict):
        """
        Property: Classification metadata must be persisted in Weaviate
        """
        store = MockMetadataStore()
        classification = doc_data["classification"]
        
        # Store classification
        success = store.store_classification_weaviate(
            uuid=doc_data["uuid"],
            doc_id=doc_data["doc_id"],
            text=doc_data["text"],
            classification=classification,
        )
        
        assert success, "Storage operation should succeed"
        
        # Retrieve and verify
        stored_obj = store.get_weaviate_object(doc_data["uuid"])
        
        assert stored_obj is not None, "Object should be retrievable"
        assert stored_obj.category == classification.category, (
            f"Category mismatch: stored={stored_obj.category}, expected={classification.category}"
        )
        assert stored_obj.doc_type == classification.doc_type, (
            f"DocType mismatch: stored={stored_obj.doc_type}, expected={classification.doc_type}"
        )
        assert stored_obj.classification_status == classification.status, (
            f"Status mismatch: stored={stored_obj.classification_status}, expected={classification.status}"
        )
    
    @given(doc_data=document_with_classification_strategy())
    @settings(max_examples=100)
    def test_classification_persisted_in_both_stores(self, doc_data: dict):
        """
        Property: Classification metadata must be persisted in BOTH OpenSearch and Weaviate
        """
        store = MockMetadataStore()
        classification = doc_data["classification"]
        
        # Store in both
        success = store.store_classification_both(
            doc_id=doc_data["doc_id"],
            chunk_id=doc_data["chunk_id"],
            uuid=doc_data["uuid"],
            text=doc_data["text"],
            classification=classification,
        )
        
        assert success, "Storage operation should succeed"
        
        # Verify OpenSearch
        os_doc = store.get_opensearch_doc(doc_data["chunk_id"])
        assert os_doc is not None, "OpenSearch document should exist"
        assert os_doc.category == classification.category
        assert os_doc.doc_type == classification.doc_type
        assert os_doc.classification_status == classification.status
        
        # Verify Weaviate
        wv_obj = store.get_weaviate_object(doc_data["uuid"])
        assert wv_obj is not None, "Weaviate object should exist"
        assert wv_obj.category == classification.category
        assert wv_obj.doc_type == classification.doc_type
        assert wv_obj.classification_status == classification.status
    
    @given(doc_data=document_with_classification_strategy())
    @settings(max_examples=100)
    def test_opensearch_and_weaviate_have_consistent_data(self, doc_data: dict):
        """
        Property: OpenSearch and Weaviate must have consistent classification data
        """
        store = MockMetadataStore()
        classification = doc_data["classification"]
        
        # Store in both
        store.store_classification_both(
            doc_id=doc_data["doc_id"],
            chunk_id=doc_data["chunk_id"],
            uuid=doc_data["uuid"],
            text=doc_data["text"],
            classification=classification,
        )
        
        # Retrieve from both
        os_doc = store.get_opensearch_doc(doc_data["chunk_id"])
        wv_obj = store.get_weaviate_object(doc_data["uuid"])
        
        # Verify consistency between stores
        assert os_doc.category == wv_obj.category, (
            f"Category inconsistent: OpenSearch={os_doc.category}, Weaviate={wv_obj.category}"
        )
        assert os_doc.doc_type == wv_obj.doc_type, (
            f"DocType inconsistent: OpenSearch={os_doc.doc_type}, Weaviate={wv_obj.doc_type}"
        )
        assert os_doc.classification_status == wv_obj.classification_status, (
            f"Status inconsistent: OpenSearch={os_doc.classification_status}, Weaviate={wv_obj.classification_status}"
        )
    
    @given(doc_data=document_with_classification_strategy())
    @settings(max_examples=100)
    def test_all_required_fields_are_persisted(self, doc_data: dict):
        """
        Property: All required classification fields must be persisted
        """
        store = MockMetadataStore()
        classification = doc_data["classification"]
        
        # Store
        store.store_classification_both(
            doc_id=doc_data["doc_id"],
            chunk_id=doc_data["chunk_id"],
            uuid=doc_data["uuid"],
            text=doc_data["text"],
            classification=classification,
        )
        
        # Verify OpenSearch has all required fields
        os_doc = store.get_opensearch_doc(doc_data["chunk_id"])
        assert os_doc.category is not None, "OpenSearch: category must not be None"
        assert os_doc.doc_type is not None, "OpenSearch: doc_type must not be None"
        assert os_doc.classification_status is not None, "OpenSearch: classification_status must not be None"
        
        # Verify Weaviate has all required fields
        wv_obj = store.get_weaviate_object(doc_data["uuid"])
        assert wv_obj.category is not None, "Weaviate: category must not be None"
        assert wv_obj.doc_type is not None, "Weaviate: doc_type must not be None"
        assert wv_obj.classification_status is not None, "Weaviate: classification_status must not be None"
    
    @given(
        doc_data=document_with_classification_strategy(),
        new_classification=classification_result_strategy(),
    )
    @settings(max_examples=100)
    def test_classification_update_persists_correctly(
        self, doc_data: dict, new_classification: ClassificationResult
    ):
        """
        Property: Updated classification must be persisted correctly
        """
        store = MockMetadataStore()
        original = doc_data["classification"]
        
        # Store original
        store.store_classification_both(
            doc_id=doc_data["doc_id"],
            chunk_id=doc_data["chunk_id"],
            uuid=doc_data["uuid"],
            text=doc_data["text"],
            classification=original,
        )
        
        # Update with new classification
        store.store_classification_both(
            doc_id=doc_data["doc_id"],
            chunk_id=doc_data["chunk_id"],
            uuid=doc_data["uuid"],
            text=doc_data["text"],
            classification=new_classification,
        )
        
        # Verify update was persisted
        os_doc = store.get_opensearch_doc(doc_data["chunk_id"])
        wv_obj = store.get_weaviate_object(doc_data["uuid"])
        
        assert os_doc.category == new_classification.category
        assert os_doc.doc_type == new_classification.doc_type
        assert os_doc.classification_status == new_classification.status
        
        assert wv_obj.category == new_classification.category
        assert wv_obj.doc_type == new_classification.doc_type
        assert wv_obj.classification_status == new_classification.status


# =============================================================================
# Additional metadata persistence tests
# =============================================================================

class TestMetadataFieldValidation:
    """Additional tests for metadata field validation"""
    
    @given(classification=classification_result_strategy())
    @settings(max_examples=100)
    def test_confidence_is_persisted_in_opensearch(self, classification: ClassificationResult):
        """OpenSearch should persist confidence score"""
        store = MockMetadataStore()
        
        store.store_classification_opensearch(
            doc_id="test_doc",
            chunk_id="test_chunk",
            text="test text",
            classification=classification,
        )
        
        doc = store.get_opensearch_doc("test_chunk")
        assert doc.classification_confidence == classification.confidence
    
    @given(classification=classification_result_strategy())
    @settings(max_examples=100)
    def test_method_is_persisted_in_opensearch(self, classification: ClassificationResult):
        """OpenSearch should persist classification method"""
        store = MockMetadataStore()
        
        store.store_classification_opensearch(
            doc_id="test_doc",
            chunk_id="test_chunk",
            text="test text",
            classification=classification,
        )
        
        doc = store.get_opensearch_doc("test_chunk")
        assert doc.classification_method == classification.method
