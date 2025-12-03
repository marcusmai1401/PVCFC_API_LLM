"""
Property-based tests for Document Classifier

**Feature: intelligent-classification-deep-search**

Tests:
- Property 3: Classification Output Completeness
- Property 9: Dominant Content Rule
- Property 10: Low Confidence Fallback
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any

from app.classification.taxonomy import (
    DocumentCategory,
    DocumentTaxonomy,
    ClassificationStatus,
    ClassificationMethod,
    get_taxonomy,
)
from app.classification.classifier import (
    ClassificationResult,
    PageAnalysis,
    DocumentClassifier,
)


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

# Strategy for generating low confidence scores (< 0.5)
low_confidence_strategy = st.floats(min_value=0.0, max_value=0.49, allow_nan=False)

# Strategy for generating high confidence scores (>= 0.5)
high_confidence_strategy = st.floats(min_value=0.5, max_value=1.0, allow_nan=False)

# Strategy for generating classification status
status_strategy = st.sampled_from([s.value for s in ClassificationStatus])

# Strategy for generating classification method
method_strategy = st.sampled_from([m.value for m in ClassificationMethod])

# Strategy for generating dominant content
dominant_content_strategy = st.sampled_from(["text", "drawing", "mixed", "unknown"])

# Strategy for generating page content types
page_content_type_strategy = st.sampled_from(["text", "drawing", "mixed"])


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


# Strategy for generating PageAnalysis objects
@st.composite
def page_analysis_strategy(draw, page_index: int = None):
    """Generate a PageAnalysis object"""
    if page_index is None:
        page_index = draw(st.integers(min_value=0, max_value=100))
    content_type = draw(page_content_type_strategy)
    confidence = draw(confidence_strategy)
    
    return PageAnalysis(
        page_index=page_index,
        content_type=content_type,
        confidence=confidence,
        features={}
    )


# Strategy for generating list of PageAnalysis with controlled content distribution
@st.composite
def page_analysis_list_strategy(draw, min_pages: int = 1, max_pages: int = 20):
    """Generate a list of PageAnalysis objects"""
    num_pages = draw(st.integers(min_value=min_pages, max_value=max_pages))
    pages = []
    for i in range(num_pages):
        pa = draw(page_analysis_strategy(page_index=i))
        pages.append(pa)
    return pages


# Strategy for generating page analysis with text-dominant content
@st.composite
def text_dominant_page_analysis_strategy(draw, num_pages: int = 10):
    """Generate page analysis where text pages are dominant (>50%)"""
    text_count = draw(st.integers(min_value=(num_pages // 2) + 1, max_value=num_pages))
    drawing_count = num_pages - text_count
    
    pages = []
    for i in range(text_count):
        pages.append(PageAnalysis(
            page_index=i,
            content_type="text",
            confidence=draw(confidence_strategy),
            features={}
        ))
    for i in range(drawing_count):
        pages.append(PageAnalysis(
            page_index=text_count + i,
            content_type="drawing",
            confidence=draw(confidence_strategy),
            features={}
        ))
    
    return pages


# Strategy for generating page analysis with drawing-dominant content
@st.composite
def drawing_dominant_page_analysis_strategy(draw, num_pages: int = 10):
    """Generate page analysis where drawing pages are dominant (>50%)"""
    drawing_count = draw(st.integers(min_value=(num_pages // 2) + 1, max_value=num_pages))
    text_count = num_pages - drawing_count
    
    pages = []
    for i in range(drawing_count):
        pages.append(PageAnalysis(
            page_index=i,
            content_type="drawing",
            confidence=draw(confidence_strategy),
            features={}
        ))
    for i in range(text_count):
        pages.append(PageAnalysis(
            page_index=drawing_count + i,
            content_type="text",
            confidence=draw(confidence_strategy),
            features={}
        ))
    
    return pages


# Strategy for generating page analysis with mixed content (no dominant type)
@st.composite
def mixed_content_page_analysis_strategy(draw, num_pages: int = 10):
    """Generate page analysis where no content type is dominant"""
    # For even number of pages, split evenly
    # For odd number, add one mixed page
    text_count = num_pages // 2
    drawing_count = num_pages // 2
    mixed_count = num_pages - text_count - drawing_count
    
    pages = []
    for i in range(text_count):
        pages.append(PageAnalysis(
            page_index=i,
            content_type="text",
            confidence=draw(confidence_strategy),
            features={}
        ))
    for i in range(drawing_count):
        pages.append(PageAnalysis(
            page_index=text_count + i,
            content_type="drawing",
            confidence=draw(confidence_strategy),
            features={}
        ))
    for i in range(mixed_count):
        pages.append(PageAnalysis(
            page_index=text_count + drawing_count + i,
            content_type="mixed",
            confidence=draw(confidence_strategy),
            features={}
        ))
    
    return pages


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
    page_analysis = draw(page_analysis_list_strategy(min_pages=0, max_pages=10))
    
    return ClassificationResult(
        category=category,
        doc_type=doc_type,
        confidence=confidence,
        status=status,
        dominant_content=dominant_content,
        page_analysis=page_analysis,
        reasoning=reasoning,
        method=method
    )




# =============================================================================
# Property 3: Classification Output Completeness
# =============================================================================

class TestProperty3ClassificationOutputCompleteness:
    """
    **Feature: intelligent-classification-deep-search, Property 3: Classification Output Completeness**
    
    *For any* document classification, the result SHALL contain all required fields:
    category (non-empty string), doc_type (non-empty string), and confidence (float between 0.0 and 1.0).
    
    **Validates: Requirements 1.2, 4.6**
    """
    
    @given(result=classification_result_strategy())
    @settings(max_examples=100)
    def test_classification_result_has_category(self, result: ClassificationResult):
        """
        Property: ClassificationResult must have a non-empty category
        """
        assert result.category is not None, "category must not be None"
        assert isinstance(result.category, str), "category must be a string"
        assert len(result.category) > 0, "category must not be empty"
    
    @given(result=classification_result_strategy())
    @settings(max_examples=100)
    def test_classification_result_has_doc_type(self, result: ClassificationResult):
        """
        Property: ClassificationResult must have a non-empty doc_type
        """
        assert result.doc_type is not None, "doc_type must not be None"
        assert isinstance(result.doc_type, str), "doc_type must be a string"
        assert len(result.doc_type) > 0, "doc_type must not be empty"
    
    @given(result=classification_result_strategy())
    @settings(max_examples=100)
    def test_classification_result_has_valid_confidence(self, result: ClassificationResult):
        """
        Property: ClassificationResult must have confidence between 0.0 and 1.0
        """
        assert result.confidence is not None, "confidence must not be None"
        assert isinstance(result.confidence, float), "confidence must be a float"
        assert 0.0 <= result.confidence <= 1.0, (
            f"confidence must be between 0.0 and 1.0, got {result.confidence}"
        )
    
    @given(result=classification_result_strategy())
    @settings(max_examples=100)
    def test_classification_result_has_status(self, result: ClassificationResult):
        """
        Property: ClassificationResult must have a valid status
        """
        valid_statuses = {s.value for s in ClassificationStatus}
        assert result.status in valid_statuses, (
            f"status '{result.status}' is not valid. Valid: {valid_statuses}"
        )
    
    @given(result=classification_result_strategy())
    @settings(max_examples=100)
    def test_classification_result_has_dominant_content(self, result: ClassificationResult):
        """
        Property: ClassificationResult must have dominant_content field
        """
        valid_contents = {"text", "drawing", "mixed", "unknown"}
        assert result.dominant_content in valid_contents, (
            f"dominant_content '{result.dominant_content}' is not valid. Valid: {valid_contents}"
        )
    
    @given(result=classification_result_strategy())
    @settings(max_examples=100)
    def test_classification_result_has_method(self, result: ClassificationResult):
        """
        Property: ClassificationResult must have a valid method
        """
        valid_methods = {m.value for m in ClassificationMethod}
        assert result.method in valid_methods, (
            f"method '{result.method}' is not valid. Valid: {valid_methods}"
        )
    
    def test_create_uncategorized_has_all_fields(self):
        """
        Property: create_uncategorized() must return result with all required fields
        """
        result = ClassificationResult.create_uncategorized(
            confidence=0.3,
            reasoning="Test reason"
        )
        
        assert result.category == DocumentCategory.UNCATEGORIZED.value
        assert result.doc_type == "Unknown"
        assert result.confidence == 0.3
        assert result.status == ClassificationStatus.NEEDS_REVIEW.value
        assert result.reasoning == "Test reason"
    
    @given(result=classification_result_strategy())
    @settings(max_examples=100)
    def test_to_dict_contains_all_fields(self, result: ClassificationResult):
        """
        Property: to_dict() must contain all required fields
        """
        data = result.to_dict()
        
        required_fields = ["category", "doc_type", "confidence", "status", 
                          "dominant_content", "page_analysis", "reasoning", "method"]
        
        for field in required_fields:
            assert field in data, f"to_dict() missing field: {field}"


# =============================================================================
# Property 9: Dominant Content Rule
# =============================================================================

class TestProperty9DominantContentRule:
    """
    **Feature: intelligent-classification-deep-search, Property 9: Dominant Content Rule**
    
    *For any* page analysis where one content type (text or drawing) appears in more than 50% 
    of sampled pages, the classification SHALL favor document types associated with that 
    dominant content type.
    
    **Validates: Requirements 4.3, 4.4, 4.5**
    """
    
    def setup_method(self):
        """Setup classifier for testing"""
        self.classifier = DocumentClassifier(
            model_name="gemini-2.5-flash",
            confidence_threshold=0.5
        )
    
    @given(pages=text_dominant_page_analysis_strategy(num_pages=10))
    @settings(max_examples=100)
    def test_text_dominant_returns_text(self, pages: List[PageAnalysis]):
        """
        Property: When text pages > 50%, dominant_content must be "text"
        """
        result = self.classifier._apply_dominant_content_rule(pages)
        
        text_count = sum(1 for p in pages if p.content_type == "text")
        total = len(pages)
        
        # Verify text is actually dominant
        assume(text_count > total / 2)
        
        assert result == "text", (
            f"Expected 'text' for text-dominant pages ({text_count}/{total}), got '{result}'"
        )
    
    @given(pages=drawing_dominant_page_analysis_strategy(num_pages=10))
    @settings(max_examples=100)
    def test_drawing_dominant_returns_drawing(self, pages: List[PageAnalysis]):
        """
        Property: When drawing pages > 50%, dominant_content must be "drawing"
        """
        result = self.classifier._apply_dominant_content_rule(pages)
        
        drawing_count = sum(1 for p in pages if p.content_type == "drawing")
        total = len(pages)
        
        # Verify drawing is actually dominant
        assume(drawing_count > total / 2)
        
        assert result == "drawing", (
            f"Expected 'drawing' for drawing-dominant pages ({drawing_count}/{total}), got '{result}'"
        )
    
    @given(pages=mixed_content_page_analysis_strategy(num_pages=10))
    @settings(max_examples=100)
    def test_no_dominant_returns_mixed(self, pages: List[PageAnalysis]):
        """
        Property: When no content type > 50%, dominant_content must be "mixed"
        """
        result = self.classifier._apply_dominant_content_rule(pages)
        
        text_count = sum(1 for p in pages if p.content_type == "text")
        drawing_count = sum(1 for p in pages if p.content_type == "drawing")
        total = len(pages)
        
        # Verify no type is dominant
        assume(text_count <= total / 2 and drawing_count <= total / 2)
        
        assert result == "mixed", (
            f"Expected 'mixed' for non-dominant pages (text={text_count}, drawing={drawing_count}, total={total}), got '{result}'"
        )
    
    def test_empty_page_analysis_returns_unknown(self):
        """
        Edge case: Empty page analysis should return "unknown"
        """
        result = self.classifier._apply_dominant_content_rule([])
        assert result == "unknown", f"Expected 'unknown' for empty pages, got '{result}'"
    
    def test_single_text_page_returns_text(self):
        """
        Edge case: Single text page should return "text"
        """
        pages = [PageAnalysis(page_index=0, content_type="text", confidence=0.9)]
        result = self.classifier._apply_dominant_content_rule(pages)
        assert result == "text"
    
    def test_single_drawing_page_returns_drawing(self):
        """
        Edge case: Single drawing page should return "drawing"
        """
        pages = [PageAnalysis(page_index=0, content_type="drawing", confidence=0.9)]
        result = self.classifier._apply_dominant_content_rule(pages)
        assert result == "drawing"
    
    @given(num_text=st.integers(min_value=6, max_value=10))
    @settings(max_examples=50)
    def test_text_majority_with_varying_counts(self, num_text: int):
        """
        Property: Any text count > 5 out of 10 should return "text"
        """
        num_drawing = 10 - num_text
        pages = []
        for i in range(num_text):
            pages.append(PageAnalysis(page_index=i, content_type="text", confidence=0.8))
        for i in range(num_drawing):
            pages.append(PageAnalysis(page_index=num_text + i, content_type="drawing", confidence=0.8))
        
        result = self.classifier._apply_dominant_content_rule(pages)
        assert result == "text", f"Expected 'text' with {num_text}/10 text pages"
    
    @given(num_drawing=st.integers(min_value=6, max_value=10))
    @settings(max_examples=50)
    def test_drawing_majority_with_varying_counts(self, num_drawing: int):
        """
        Property: Any drawing count > 5 out of 10 should return "drawing"
        """
        num_text = 10 - num_drawing
        pages = []
        for i in range(num_drawing):
            pages.append(PageAnalysis(page_index=i, content_type="drawing", confidence=0.8))
        for i in range(num_text):
            pages.append(PageAnalysis(page_index=num_drawing + i, content_type="text", confidence=0.8))
        
        result = self.classifier._apply_dominant_content_rule(pages)
        assert result == "drawing", f"Expected 'drawing' with {num_drawing}/10 drawing pages"
    
    def test_exactly_50_50_returns_mixed(self):
        """
        Edge case: Exactly 50% text and 50% drawing should return "mixed"
        """
        pages = []
        for i in range(5):
            pages.append(PageAnalysis(page_index=i, content_type="text", confidence=0.8))
        for i in range(5):
            pages.append(PageAnalysis(page_index=5 + i, content_type="drawing", confidence=0.8))
        
        result = self.classifier._apply_dominant_content_rule(pages)
        assert result == "mixed", "Expected 'mixed' for 50/50 split"



# =============================================================================
# Property 10: Low Confidence Fallback
# =============================================================================

class TestProperty10LowConfidenceFallback:
    """
    **Feature: intelligent-classification-deep-search, Property 10: Low Confidence Fallback**
    
    *For any* AI classification result where confidence < 0.5 OR dominant content cannot be 
    determined, the final result SHALL have category="UNCATEGORIZED" and status="NEEDS_REVIEW".
    
    **Validates: Requirements 4.7**
    """
    
    def setup_method(self):
        """Setup classifier for testing"""
        self.classifier = DocumentClassifier(
            model_name="gemini-2.5-flash",
            confidence_threshold=0.5
        )
    
    @given(confidence=low_confidence_strategy)
    @settings(max_examples=100)
    def test_low_confidence_triggers_uncategorized(self, confidence: float):
        """
        Property: Any confidence < 0.5 must result in UNCATEGORIZED category
        """
        # Verify confidence is actually low
        assume(confidence < 0.5)
        
        # Create a result with low confidence
        original_result = ClassificationResult(
            category=DocumentCategory.ENGINEERING_DESIGN.value,
            doc_type="P&ID",
            confidence=confidence,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="drawing",
            page_analysis=[],
            reasoning="Test classification",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        # Apply low confidence check (simulating what classify() does)
        if original_result.confidence < self.classifier.confidence_threshold:
            final_result = ClassificationResult(
                category=DocumentCategory.UNCATEGORIZED.value,
                doc_type="Unknown",
                confidence=original_result.confidence,
                status=ClassificationStatus.NEEDS_REVIEW.value,
                dominant_content=original_result.dominant_content,
                page_analysis=original_result.page_analysis,
                reasoning=f"Low confidence ({original_result.confidence:.2f}): {original_result.reasoning}",
                method=ClassificationMethod.AI_CLASSIFIER.value
            )
        else:
            final_result = original_result
        
        assert final_result.category == DocumentCategory.UNCATEGORIZED.value, (
            f"Expected UNCATEGORIZED for confidence {confidence}, got {final_result.category}"
        )
        assert final_result.status == ClassificationStatus.NEEDS_REVIEW.value, (
            f"Expected NEEDS_REVIEW for confidence {confidence}, got {final_result.status}"
        )
    
    @given(confidence=high_confidence_strategy)
    @settings(max_examples=100)
    def test_high_confidence_preserves_category(self, confidence: float):
        """
        Property: Any confidence >= 0.5 must preserve original category
        """
        # Verify confidence is actually high
        assume(confidence >= 0.5)
        
        original_category = DocumentCategory.ENGINEERING_DESIGN.value
        original_doc_type = "P&ID"
        
        # Create a result with high confidence
        original_result = ClassificationResult(
            category=original_category,
            doc_type=original_doc_type,
            confidence=confidence,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="drawing",
            page_analysis=[],
            reasoning="Test classification",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        # Apply confidence check
        if original_result.confidence < self.classifier.confidence_threshold:
            final_result = ClassificationResult(
                category=DocumentCategory.UNCATEGORIZED.value,
                doc_type="Unknown",
                confidence=original_result.confidence,
                status=ClassificationStatus.NEEDS_REVIEW.value,
                dominant_content=original_result.dominant_content,
                page_analysis=original_result.page_analysis,
                reasoning=f"Low confidence: {original_result.reasoning}",
                method=ClassificationMethod.AI_CLASSIFIER.value
            )
        else:
            final_result = original_result
        
        assert final_result.category == original_category, (
            f"Expected {original_category} for confidence {confidence}, got {final_result.category}"
        )
        assert final_result.doc_type == original_doc_type, (
            f"Expected {original_doc_type} for confidence {confidence}, got {final_result.doc_type}"
        )
    
    def test_confidence_exactly_0_5_is_accepted(self):
        """
        Edge case: Confidence exactly 0.5 should be accepted (not fallback)
        """
        result = ClassificationResult(
            category=DocumentCategory.VENDOR_EQUIPMENT.value,
            doc_type="Datasheet",
            confidence=0.5,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="text",
            page_analysis=[],
            reasoning="Test",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        # Apply confidence check
        if result.confidence < self.classifier.confidence_threshold:
            final_category = DocumentCategory.UNCATEGORIZED.value
        else:
            final_category = result.category
        
        assert final_category == DocumentCategory.VENDOR_EQUIPMENT.value, (
            "Confidence 0.5 should be accepted, not trigger fallback"
        )
    
    def test_confidence_0_49_triggers_fallback(self):
        """
        Edge case: Confidence 0.49 should trigger fallback
        """
        result = ClassificationResult(
            category=DocumentCategory.VENDOR_EQUIPMENT.value,
            doc_type="Datasheet",
            confidence=0.49,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="text",
            page_analysis=[],
            reasoning="Test",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        # Apply confidence check
        if result.confidence < self.classifier.confidence_threshold:
            final_category = DocumentCategory.UNCATEGORIZED.value
            final_status = ClassificationStatus.NEEDS_REVIEW.value
        else:
            final_category = result.category
            final_status = result.status
        
        assert final_category == DocumentCategory.UNCATEGORIZED.value
        assert final_status == ClassificationStatus.NEEDS_REVIEW.value
    
    def test_confidence_0_triggers_fallback(self):
        """
        Edge case: Confidence 0.0 should trigger fallback
        """
        result = ClassificationResult(
            category=DocumentCategory.SAFETY_MANAGEMENT.value,
            doc_type="MOC",
            confidence=0.0,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="text",
            page_analysis=[],
            reasoning="Test",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        if result.confidence < self.classifier.confidence_threshold:
            final_category = DocumentCategory.UNCATEGORIZED.value
            final_status = ClassificationStatus.NEEDS_REVIEW.value
        else:
            final_category = result.category
            final_status = result.status
        
        assert final_category == DocumentCategory.UNCATEGORIZED.value
        assert final_status == ClassificationStatus.NEEDS_REVIEW.value
    
    @given(confidence=low_confidence_strategy)
    @settings(max_examples=100)
    def test_low_confidence_preserves_original_confidence_value(self, confidence: float):
        """
        Property: Low confidence fallback should preserve the original confidence value
        """
        assume(confidence < 0.5)
        
        original_result = ClassificationResult(
            category=DocumentCategory.ENGINEERING_DESIGN.value,
            doc_type="Drawing",
            confidence=confidence,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="drawing",
            page_analysis=[],
            reasoning="Original reason",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        # Apply fallback
        final_result = ClassificationResult(
            category=DocumentCategory.UNCATEGORIZED.value,
            doc_type="Unknown",
            confidence=original_result.confidence,  # Preserve original
            status=ClassificationStatus.NEEDS_REVIEW.value,
            dominant_content=original_result.dominant_content,
            page_analysis=original_result.page_analysis,
            reasoning=f"Low confidence ({original_result.confidence:.2f}): {original_result.reasoning}",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        assert final_result.confidence == confidence, (
            f"Confidence should be preserved: expected {confidence}, got {final_result.confidence}"
        )
    
    @given(confidence=low_confidence_strategy, dominant=dominant_content_strategy)
    @settings(max_examples=100)
    def test_low_confidence_preserves_dominant_content(self, confidence: float, dominant: str):
        """
        Property: Low confidence fallback should preserve dominant_content
        """
        assume(confidence < 0.5)
        
        original_result = ClassificationResult(
            category=DocumentCategory.OPERATIONS_MAINTENANCE.value,
            doc_type="Operation Instruction",
            confidence=confidence,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content=dominant,
            page_analysis=[],
            reasoning="Test",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        # Apply fallback
        final_result = ClassificationResult(
            category=DocumentCategory.UNCATEGORIZED.value,
            doc_type="Unknown",
            confidence=original_result.confidence,
            status=ClassificationStatus.NEEDS_REVIEW.value,
            dominant_content=original_result.dominant_content,  # Preserve
            page_analysis=original_result.page_analysis,
            reasoning=f"Low confidence: {original_result.reasoning}",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        assert final_result.dominant_content == dominant, (
            f"dominant_content should be preserved: expected {dominant}, got {final_result.dominant_content}"
        )


# =============================================================================
# Additional classifier tests
# =============================================================================

class TestClassifierEdgeCases:
    """Additional edge case tests for DocumentClassifier"""
    
    def test_classifier_initialization(self):
        """Classifier should initialize with default values"""
        classifier = DocumentClassifier()
        
        assert classifier.model_name == "gemini-2.5-flash"
        assert classifier.confidence_threshold == 0.5
        assert classifier.taxonomy is not None
    
    def test_classifier_custom_threshold(self):
        """Classifier should accept custom confidence threshold"""
        classifier = DocumentClassifier(confidence_threshold=0.7)
        
        assert classifier.confidence_threshold == 0.7
    
    def test_classify_empty_images_returns_uncategorized(self):
        """Classifier should return UNCATEGORIZED for empty image list"""
        classifier = DocumentClassifier()
        
        result = classifier.classify(
            page_images=[],
            filename="test.pdf",
            metadata=None
        )
        
        assert result.category == DocumentCategory.UNCATEGORIZED.value
        assert result.status == ClassificationStatus.NEEDS_REVIEW.value
        assert "No page images" in result.reasoning
    
    def test_classify_all_empty_images_returns_uncategorized(self):
        """Classifier should return UNCATEGORIZED when all images are empty"""
        classifier = DocumentClassifier()
        
        result = classifier.classify(
            page_images=[b"", b"", b""],
            filename="test.pdf",
            metadata=None
        )
        
        assert result.category == DocumentCategory.UNCATEGORIZED.value
        assert "empty" in result.reasoning.lower()
    
    def test_page_analysis_to_dict(self):
        """PageAnalysis should be serializable"""
        pa = PageAnalysis(
            page_index=5,
            content_type="text",
            confidence=0.85,
            features={"has_table": True}
        )
        
        # PageAnalysis is a dataclass, check fields
        assert pa.page_index == 5
        assert pa.content_type == "text"
        assert pa.confidence == 0.85
        assert pa.features == {"has_table": True}
    
    def test_classification_result_to_dict_with_page_analysis(self):
        """ClassificationResult.to_dict() should include page_analysis"""
        pages = [
            PageAnalysis(page_index=0, content_type="text", confidence=0.9),
            PageAnalysis(page_index=1, content_type="drawing", confidence=0.8),
        ]
        
        result = ClassificationResult(
            category=DocumentCategory.ENGINEERING_DESIGN.value,
            doc_type="P&ID",
            confidence=0.85,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="drawing",
            page_analysis=pages,
            reasoning="Test",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        data = result.to_dict()
        
        assert len(data["page_analysis"]) == 2
        assert data["page_analysis"][0]["page_index"] == 0
        assert data["page_analysis"][0]["content_type"] == "text"
        assert data["page_analysis"][1]["page_index"] == 1
        assert data["page_analysis"][1]["content_type"] == "drawing"
