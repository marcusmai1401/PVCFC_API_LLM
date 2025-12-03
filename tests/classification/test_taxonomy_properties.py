"""
Property-based tests for Document Taxonomy

**Feature: intelligent-classification-deep-search**

Tests:
- Property 1: Taxonomy Category Validation
- Property 2: Category-DocType Mapping Consistency
"""
import pytest
from hypothesis import given, strategies as st, settings

from app.classification.taxonomy import (
    DocumentCategory,
    DocumentTaxonomy,
    ClassificationStatus,
    ClassificationMethod,
    get_taxonomy,
)
from app.classification.classifier import ClassificationResult


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

# Strategy for generating invalid categories
invalid_category_strategy = st.text(min_size=1, max_size=50).filter(
    lambda x: x not in [c.value for c in DocumentCategory]
)

# Strategy for generating confidence scores
confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for generating classification status
status_strategy = st.sampled_from([s.value for s in ClassificationStatus])

# Strategy for generating classification method
method_strategy = st.sampled_from([m.value for m in ClassificationMethod])

# Strategy for generating dominant content
dominant_content_strategy = st.sampled_from(["text", "drawing", "mixed", "unknown"])


def get_valid_doc_type_for_category(category: str) -> st.SearchStrategy[str]:
    """Get strategy for valid doc_types for a given category"""
    taxonomy = get_taxonomy()
    doc_types = taxonomy.get_doc_types_for_category(category)
    if doc_types:
        return st.sampled_from(doc_types)
    return st.just("Unknown")


# Strategy for generating valid category-doctype pairs
@st.composite
def valid_category_doctype_pair(draw):
    """Generate a valid (category, doc_type) pair"""
    taxonomy = get_taxonomy()
    category = draw(valid_category_strategy)
    doc_types = taxonomy.get_doc_types_for_category(category)
    doc_type = draw(st.sampled_from(doc_types)) if doc_types else "Unknown"
    return (category, doc_type)


# Strategy for generating ClassificationResult objects
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


# =============================================================================
# Property 1: Taxonomy Category Validation
# =============================================================================

class TestProperty1TaxonomyCategoryValidation:
    """
    **Feature: intelligent-classification-deep-search, Property 1: Taxonomy Category Validation**
    
    *For any* classification result, the category field SHALL be one of exactly 5 values:
    ENGINEERING_DESIGN, VENDOR_EQUIPMENT, OPERATIONS_MAINTENANCE, SAFETY_MANAGEMENT, or UNCATEGORIZED.
    
    **Validates: Requirements 1.1**
    """
    
    VALID_CATEGORIES = {
        DocumentCategory.ENGINEERING_DESIGN.value,
        DocumentCategory.VENDOR_EQUIPMENT.value,
        DocumentCategory.OPERATIONS_MAINTENANCE.value,
        DocumentCategory.SAFETY_MANAGEMENT.value,
        DocumentCategory.UNCATEGORIZED.value,
    }
    
    @given(result=classification_result_strategy())
    @settings(max_examples=100)
    def test_classification_result_has_valid_category(self, result: ClassificationResult):
        """
        Property: Any ClassificationResult must have a category from the valid set
        """
        assert result.category in self.VALID_CATEGORIES, (
            f"Category '{result.category}' is not in valid categories: {self.VALID_CATEGORIES}"
        )
    
    def test_taxonomy_has_exactly_5_categories(self):
        """
        Property: Taxonomy must have exactly 5 categories
        """
        taxonomy = get_taxonomy()
        categories = taxonomy.get_all_categories()
        
        assert len(categories) == 5, (
            f"Expected 5 categories, got {len(categories)}: {categories}"
        )
        assert set(categories) == self.VALID_CATEGORIES, (
            f"Categories mismatch. Expected: {self.VALID_CATEGORIES}, Got: {set(categories)}"
        )
    
    @given(category=valid_category_strategy)
    @settings(max_examples=100)
    def test_valid_category_is_recognized(self, category: str):
        """
        Property: Any valid category must be recognized by taxonomy
        """
        taxonomy = get_taxonomy()
        assert taxonomy.is_valid_category(category), (
            f"Valid category '{category}' not recognized by taxonomy"
        )
    
    @given(category=invalid_category_strategy)
    @settings(max_examples=100)
    def test_invalid_category_is_rejected(self, category: str):
        """
        Property: Any invalid category must be rejected by taxonomy
        """
        taxonomy = get_taxonomy()
        assert not taxonomy.is_valid_category(category), (
            f"Invalid category '{category}' was incorrectly accepted"
        )


# =============================================================================
# Property 2: Category-DocType Mapping Consistency
# =============================================================================

class TestProperty2CategoryDocTypeMappingConsistency:
    """
    **Feature: intelligent-classification-deep-search, Property 2: Category-DocType Mapping Consistency**
    
    *For any* classification result with a valid category, the doc_type SHALL belong to 
    the predefined list for that category (e.g., ENGINEERING_DESIGN only allows P&ID, Drawing, Technical Data).
    
    **Validates: Requirements 1.3**
    """
    
    EXPECTED_DOC_TYPES = {
        DocumentCategory.ENGINEERING_DESIGN.value: ["P&ID", "Drawing", "Technical Data"],
        DocumentCategory.VENDOR_EQUIPMENT.value: ["Datasheet", "Material Partlist", "Vendor Manual"],
        DocumentCategory.OPERATIONS_MAINTENANCE.value: [
            "Operation Instruction", "Maintenance Instruction", 
            "Maintenance History", "Inventory"
        ],
        DocumentCategory.SAFETY_MANAGEMENT.value: ["MOC", "RCA", "Pictures"],
        DocumentCategory.UNCATEGORIZED.value: ["Unknown"],
    }
    
    @given(pair=valid_category_doctype_pair())
    @settings(max_examples=100)
    def test_doc_type_belongs_to_category(self, pair: tuple):
        """
        Property: Any doc_type in a ClassificationResult must belong to its category
        """
        category, doc_type = pair
        taxonomy = get_taxonomy()
        
        valid_doc_types = taxonomy.get_doc_types_for_category(category)
        assert doc_type in valid_doc_types, (
            f"doc_type '{doc_type}' does not belong to category '{category}'. "
            f"Valid types: {valid_doc_types}"
        )
    
    @given(result=classification_result_strategy())
    @settings(max_examples=100)
    def test_classification_result_has_consistent_mapping(self, result: ClassificationResult):
        """
        Property: ClassificationResult must have consistent category-doctype mapping
        """
        taxonomy = get_taxonomy()
        
        assert taxonomy.is_valid_category_doc_type_pair(result.category, result.doc_type), (
            f"Inconsistent mapping: doc_type '{result.doc_type}' "
            f"does not belong to category '{result.category}'"
        )
    
    def test_all_categories_have_expected_doc_types(self):
        """
        Property: Each category must have exactly the expected doc_types
        """
        taxonomy = get_taxonomy()
        
        for category, expected_types in self.EXPECTED_DOC_TYPES.items():
            actual_types = taxonomy.get_doc_types_for_category(category)
            assert set(actual_types) == set(expected_types), (
                f"Category '{category}' has wrong doc_types. "
                f"Expected: {expected_types}, Got: {actual_types}"
            )
    
    @given(category=valid_category_strategy)
    @settings(max_examples=100)
    def test_get_category_for_doc_type_is_consistent(self, category: str):
        """
        Property: get_category_for_doc_type must return the correct category
        """
        taxonomy = get_taxonomy()
        doc_types = taxonomy.get_doc_types_for_category(category)
        
        for doc_type in doc_types:
            found_category = taxonomy.get_category_for_doc_type(doc_type)
            assert found_category == category, (
                f"get_category_for_doc_type('{doc_type}') returned '{found_category}', "
                f"expected '{category}'"
            )
    
    def test_no_doc_type_belongs_to_multiple_categories(self):
        """
        Property: No doc_type should belong to multiple categories
        """
        taxonomy = get_taxonomy()
        
        doc_type_to_categories = {}
        for category in taxonomy.get_all_categories():
            for doc_type in taxonomy.get_doc_types_for_category(category):
                if doc_type not in doc_type_to_categories:
                    doc_type_to_categories[doc_type] = []
                doc_type_to_categories[doc_type].append(category)
        
        for doc_type, categories in doc_type_to_categories.items():
            assert len(categories) == 1, (
                f"doc_type '{doc_type}' belongs to multiple categories: {categories}"
            )


# =============================================================================
# Additional taxonomy validation tests
# =============================================================================

class TestTaxonomyIntegrity:
    """Additional tests for taxonomy integrity"""
    
    def test_taxonomy_singleton(self):
        """Taxonomy should be a singleton"""
        t1 = get_taxonomy()
        t2 = get_taxonomy()
        assert t1 is t2, "get_taxonomy() should return the same instance"
    
    def test_all_doc_types_are_unique(self):
        """All doc_types across all categories should be unique"""
        taxonomy = get_taxonomy()
        all_types = taxonomy.get_all_doc_types()
        
        assert len(all_types) == len(set(all_types)), (
            f"Duplicate doc_types found: {all_types}"
        )
    
    def test_taxonomy_to_dict(self):
        """Taxonomy.to_dict() should return valid structure"""
        taxonomy = get_taxonomy()
        data = taxonomy.to_dict()
        
        assert "categories" in data
        assert "total_categories" in data
        assert "total_doc_types" in data
        assert data["total_categories"] == 5
        assert data["total_doc_types"] == len(taxonomy.get_all_doc_types())
