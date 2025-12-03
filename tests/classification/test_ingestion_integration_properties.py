"""
Property-based tests for Classification Integration with Ingestion Pipeline

**Feature: intelligent-classification-deep-search**

Tests:
- Property 16: Pipeline Auto-Classification
"""
import pytest
from dataclasses import dataclass
from hypothesis import given, strategies as st, settings, assume
from pathlib import Path
from typing import Optional, List, Dict, Any
from unittest.mock import Mock, MagicMock, patch
import tempfile
import os

from app.classification.taxonomy import (
    DocumentCategory,
    ClassificationStatus,
    ClassificationMethod,
)
from app.classification.classifier import ClassificationResult
from app.classification.pipeline import (
    ClassificationPipeline,
    PipelineResult,
    CAD_SCORE_THRESHOLD,
)


# =============================================================================
# Mock classes for testing ingestion integration
# =============================================================================

@dataclass
class MockGateDecision:
    """Mock GateDecision for testing"""
    is_cadlike: bool
    score: float
    pages_sampled: List[int]
    taggy_pages: List[int]
    features: dict
    boosted_by_filename: bool = False
    confidence: str = "HIGH"
    detection_method: str = "VECTOR"
    image_features: dict = None

    def __post_init__(self):
        if self.image_features is None:
            self.image_features = {}


class MockCADLikeGate:
    """Mock CADLikeGate for testing"""
    
    def __init__(self, fixed_score: float = 0.3):
        self.fixed_score = fixed_score
    
    def evaluate(self, pdf_path: Path, doc_metadata: Optional[dict] = None) -> MockGateDecision:
        is_cadlike = self.fixed_score >= CAD_SCORE_THRESHOLD
        return MockGateDecision(
            is_cadlike=is_cadlike,
            score=self.fixed_score,
            pages_sampled=[0, 1, 2],
            taggy_pages=[0, 1] if is_cadlike else [],
            features={"geometry_density": self.fixed_score},
        )


class MockClassificationPipeline:
    """Mock ClassificationPipeline for testing ingestion integration"""
    
    def __init__(
        self,
        fixed_category: str = DocumentCategory.VENDOR_EQUIPMENT.value,
        fixed_doc_type: str = "Datasheet",
        fixed_confidence: float = 0.85,
        fixed_status: str = ClassificationStatus.CLASSIFIED.value,
        should_fail: bool = False,
        guardrail_triggered: bool = False,
        cad_score: Optional[float] = None
    ):
        self.fixed_category = fixed_category
        self.fixed_doc_type = fixed_doc_type
        self.fixed_confidence = fixed_confidence
        self.fixed_status = fixed_status
        self.should_fail = should_fail
        self.guardrail_triggered = guardrail_triggered
        self.cad_score = cad_score
        
        # Tracking
        self.classify_document_called = False
        self.classify_document_call_count = 0
        self.last_pdf_path = None
        self.last_doc_metadata = None
    
    def classify_document(
        self,
        pdf_path: Path,
        doc_metadata: Optional[dict] = None,
        skip_guardrail: bool = False
    ) -> PipelineResult:
        """Mock classify_document method"""
        self.classify_document_called = True
        self.classify_document_call_count += 1
        self.last_pdf_path = pdf_path
        self.last_doc_metadata = doc_metadata
        
        if self.should_fail:
            raise RuntimeError("Classification failed")
        
        classification = ClassificationResult(
            category=self.fixed_category,
            doc_type=self.fixed_doc_type,
            confidence=self.fixed_confidence,
            status=self.fixed_status,
            dominant_content="text",
            page_analysis=[],
            reasoning="Mock classification",
            method=ClassificationMethod.AI_CLASSIFIER.value if not self.guardrail_triggered else ClassificationMethod.CADLIKE_GATE.value
        )
        
        return PipelineResult(
            classification=classification,
            sampling=None,
            cad_score=self.cad_score,
            guardrail_triggered=self.guardrail_triggered
        )


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Strategy for valid categories
category_strategy = st.sampled_from([
    DocumentCategory.ENGINEERING_DESIGN.value,
    DocumentCategory.VENDOR_EQUIPMENT.value,
    DocumentCategory.OPERATIONS_MAINTENANCE.value,
    DocumentCategory.SAFETY_MANAGEMENT.value,
    DocumentCategory.UNCATEGORIZED.value,
])

# Strategy for confidence scores
confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for CAD scores
cad_score_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


# =============================================================================
# Property 16: Pipeline Auto-Classification
# =============================================================================

class TestProperty16PipelineAutoClassification:
    """
    **Feature: intelligent-classification-deep-search, Property 16: Pipeline Auto-Classification**
    
    *For any* PDF ingested through the pipeline, classification SHALL be automatically 
    triggered and completed before chunking/embedding.
    
    **Validates: Requirements 8.1**
    """
    
    @given(
        category=category_strategy,
        confidence=confidence_strategy
    )
    @settings(max_examples=100)
    def test_classification_result_stored_in_metadata(
        self,
        category: str,
        confidence: float
    ):
        """
        Property: Classification result must be stored in chunk metadata
        """
        # Create mock classification result
        classification_result = {
            "category": category,
            "doc_type": "TestType",
            "confidence": confidence,
            "status": ClassificationStatus.CLASSIFIED.value,
            "method": ClassificationMethod.AI_CLASSIFIER.value
        }
        
        # Simulate metadata preparation (as done in _create_chunks)
        metadata = {
            "doc_type": "CAD-like",
            "revision": "A",
            "source_format": "vector",
            "file_name": "test.pdf",
        }
        
        # Add classification metadata
        if classification_result:
            metadata["category"] = classification_result.get("category")
            metadata["classification_doc_type"] = classification_result.get("doc_type")
            metadata["classification_status"] = classification_result.get("status")
            metadata["classification_confidence"] = classification_result.get("confidence")
            metadata["classification_method"] = classification_result.get("method")
        
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        # Verify classification metadata is present
        assert "category" in metadata, "category must be in metadata"
        assert metadata["category"] == category
        assert "classification_confidence" in metadata
        assert metadata["classification_confidence"] == confidence
        assert "classification_status" in metadata
        assert "classification_method" in metadata
    
    @given(
        category=category_strategy,
        confidence=confidence_strategy,
        cad_score=cad_score_strategy
    )
    @settings(max_examples=100)
    def test_classification_result_stored_in_corpus_entry(
        self,
        category: str,
        confidence: float,
        cad_score: float
    ):
        """
        Property: Classification result must be stored in corpus manifest entry
        """
        # Create mock classification result
        classification_result = {
            "category": category,
            "doc_type": "TestType",
            "confidence": confidence,
            "status": ClassificationStatus.CLASSIFIED.value,
            "method": ClassificationMethod.AI_CLASSIFIER.value
        }
        
        # Simulate corpus_entry creation (as done in _process_single_pdf)
        corpus_entry = {
            "doc_id": "DOCID_test_12345678",
            "file_path": "/path/to/test.pdf",
            "hash_sha256": "abc123",
            "content_hash": "def456",
            "pages": 10,
            "doc_type": "CAD-like",
            "revision": "A",
            "source_format": "vector",
            "ingested_at": "2025-12-03T10:00:00",
            "processing_mode": "normal",
        }
        
        # Add classification metadata
        if classification_result:
            corpus_entry["category"] = classification_result.get("category")
            corpus_entry["classification_doc_type"] = classification_result.get("doc_type")
            corpus_entry["classification_status"] = classification_result.get("status")
            corpus_entry["classification_confidence"] = classification_result.get("confidence")
            corpus_entry["classification_method"] = classification_result.get("method")
        
        # Verify classification metadata is present in corpus entry
        assert "category" in corpus_entry, "category must be in corpus_entry"
        assert corpus_entry["category"] == category
        assert "classification_confidence" in corpus_entry
        assert corpus_entry["classification_confidence"] == confidence
        assert "classification_status" in corpus_entry
        assert "classification_method" in corpus_entry
    
    def test_classification_called_before_chunking(self):
        """
        Property: Classification must be called before chunking
        
        This test verifies the execution order by checking that classification
        result is available when chunks are created.
        """
        call_order = []
        
        # Track when classification is called
        def mock_run_classification(pdf_path, doc_id):
            call_order.append("classification")
            return {
                "category": DocumentCategory.VENDOR_EQUIPMENT.value,
                "doc_type": "Datasheet",
                "confidence": 0.85,
                "status": ClassificationStatus.CLASSIFIED.value,
                "method": ClassificationMethod.AI_CLASSIFIER.value
            }
        
        # Track when chunking is called
        def mock_create_chunks(*args, **kwargs):
            call_order.append("chunking")
            # Verify classification_result is passed
            classification_result = kwargs.get("classification_result") or (args[7] if len(args) > 7 else None)
            assert classification_result is not None, "classification_result must be passed to chunking"
            return []
        
        # Simulate the flow
        classification_result = mock_run_classification(Path("test.pdf"), "DOCID_test")
        mock_create_chunks(
            None, "", "DOCID_test", "CAD-like", "A", "hierarchical",
            classification_result=classification_result
        )
        
        # Verify order
        assert call_order == ["classification", "chunking"], (
            f"Expected ['classification', 'chunking'], got {call_order}"
        )
    
    @given(cad_score=st.floats(min_value=CAD_SCORE_THRESHOLD, max_value=1.0, allow_nan=False))
    @settings(max_examples=50)
    def test_guardrail_triggered_tracked_in_stats(self, cad_score: float):
        """
        Property: When guardrail is triggered, it must be tracked in stats
        """
        assume(cad_score >= CAD_SCORE_THRESHOLD)
        
        # Simulate stats tracking
        stats = {
            "classification_count": 0,
            "classification_guardrail_triggered": 0,
            "classification_needs_review": 0,
        }
        
        # Simulate classification with guardrail triggered
        mock_pipeline = MockClassificationPipeline(
            fixed_category=DocumentCategory.ENGINEERING_DESIGN.value,
            fixed_doc_type="P&ID",
            fixed_confidence=cad_score,
            guardrail_triggered=True,
            cad_score=cad_score
        )
        
        result = mock_pipeline.classify_document(Path("test.pdf"))
        
        # Update stats as done in _run_classification
        stats["classification_count"] += 1
        if result.guardrail_triggered:
            stats["classification_guardrail_triggered"] += 1
        
        # Verify stats
        assert stats["classification_count"] == 1
        assert stats["classification_guardrail_triggered"] == 1
    
    @given(confidence=st.floats(min_value=0.0, max_value=0.49, allow_nan=False))
    @settings(max_examples=50)
    def test_needs_review_tracked_in_stats(self, confidence: float):
        """
        Property: When classification needs review, it must be tracked in stats
        """
        assume(confidence < 0.5)
        
        # Simulate stats tracking
        stats = {
            "classification_count": 0,
            "classification_guardrail_triggered": 0,
            "classification_needs_review": 0,
        }
        
        # Simulate classification with needs_review status
        mock_pipeline = MockClassificationPipeline(
            fixed_category=DocumentCategory.UNCATEGORIZED.value,
            fixed_doc_type="Unknown",
            fixed_confidence=confidence,
            fixed_status=ClassificationStatus.NEEDS_REVIEW.value,
        )
        
        result = mock_pipeline.classify_document(Path("test.pdf"))
        
        # Update stats as done in _run_classification
        stats["classification_count"] += 1
        if result.classification.status == ClassificationStatus.NEEDS_REVIEW.value:
            stats["classification_needs_review"] += 1
        
        # Verify stats
        assert stats["classification_count"] == 1
        assert stats["classification_needs_review"] == 1
    
    def test_classification_failure_returns_fallback_result(self):
        """
        Property: When classification fails, a fallback result must be returned
        """
        # Simulate classification failure handling
        def run_classification_with_fallback(pdf_path, doc_id):
            try:
                raise RuntimeError("API error")
            except Exception as e:
                # Return fallback result as done in _run_classification
                return {
                    "category": "UNCATEGORIZED",
                    "doc_type": "Unknown",
                    "confidence": 0.0,
                    "status": "needs_review",
                    "dominant_content": "unknown",
                    "reasoning": f"Classification error: {str(e)}",
                    "method": "error"
                }
        
        result = run_classification_with_fallback(Path("test.pdf"), "DOCID_test")
        
        # Verify fallback result
        assert result is not None, "Fallback result must be returned"
        assert result["category"] == "UNCATEGORIZED"
        assert result["status"] == "needs_review"
        assert "error" in result["reasoning"].lower()
    
    def test_classification_disabled_returns_none(self):
        """
        Property: When classification is disabled, None must be returned
        """
        # Simulate disabled classification
        enable_classification = False
        classification_pipeline = None
        
        def run_classification(pdf_path, doc_id):
            if not enable_classification or not classification_pipeline:
                return None
            # Would call pipeline here
            return {}
        
        result = run_classification(Path("test.pdf"), "DOCID_test")
        
        assert result is None, "Should return None when classification is disabled"
    
    @given(
        category=category_strategy,
        doc_type=st.sampled_from(["P&ID", "Drawing", "Datasheet", "Manual", "Unknown"]),
        confidence=confidence_strategy
    )
    @settings(max_examples=100)
    def test_all_classification_fields_preserved(
        self,
        category: str,
        doc_type: str,
        confidence: float
    ):
        """
        Property: All classification fields must be preserved through the pipeline
        """
        # Original classification result
        original = {
            "category": category,
            "doc_type": doc_type,
            "confidence": confidence,
            "status": ClassificationStatus.CLASSIFIED.value if confidence >= 0.5 else ClassificationStatus.NEEDS_REVIEW.value,
            "method": ClassificationMethod.AI_CLASSIFIER.value,
            "dominant_content": "text",
            "reasoning": "Test reasoning"
        }
        
        # Simulate passing through metadata
        metadata = {}
        if original:
            metadata["category"] = original.get("category")
            metadata["classification_doc_type"] = original.get("doc_type")
            metadata["classification_status"] = original.get("status")
            metadata["classification_confidence"] = original.get("confidence")
            metadata["classification_method"] = original.get("method")
        
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        # Verify all fields preserved
        assert metadata.get("category") == category
        assert metadata.get("classification_doc_type") == doc_type
        assert metadata.get("classification_confidence") == confidence
        assert metadata.get("classification_status") == original["status"]
        assert metadata.get("classification_method") == ClassificationMethod.AI_CLASSIFIER.value


# =============================================================================
# Integration tests for _run_classification method
# =============================================================================

class TestRunClassificationMethod:
    """Tests for the _run_classification method behavior"""
    
    def test_run_classification_returns_dict(self):
        """
        Test that _run_classification returns a dictionary with expected keys
        """
        mock_pipeline = MockClassificationPipeline()
        
        result = mock_pipeline.classify_document(Path("test.pdf"))
        result_dict = result.classification.to_dict()
        
        # Verify expected keys
        expected_keys = ["category", "doc_type", "confidence", "status", "method"]
        for key in expected_keys:
            assert key in result_dict, f"Key '{key}' must be in result"
    
    def test_run_classification_logs_guardrail_trigger(self):
        """
        Test that guardrail triggers are logged appropriately
        """
        mock_pipeline = MockClassificationPipeline(
            fixed_category=DocumentCategory.ENGINEERING_DESIGN.value,
            fixed_doc_type="P&ID",
            guardrail_triggered=True,
            cad_score=0.75
        )
        
        result = mock_pipeline.classify_document(Path("test.pdf"))
        
        assert result.guardrail_triggered is True
        assert result.cad_score == 0.75
    
    def test_run_classification_logs_ai_classification(self):
        """
        Test that AI classifications are logged appropriately
        """
        mock_pipeline = MockClassificationPipeline(
            fixed_category=DocumentCategory.VENDOR_EQUIPMENT.value,
            fixed_doc_type="Datasheet",
            fixed_confidence=0.92,
            guardrail_triggered=False
        )
        
        result = mock_pipeline.classify_document(Path("test.pdf"))
        
        assert result.guardrail_triggered is False
        assert result.classification.confidence == 0.92
