"""
Property-based tests for Classification Pipeline with P&ID Guardrail

**Feature: intelligent-classification-deep-search**

Tests:
- Property 6: P&ID Guardrail Enforcement
- Property 7: Guardrail Execution Order
- Property 8: AI Classifier Invocation
- Property 18: Classification Failure Handling
"""
import pytest
from dataclasses import dataclass
from hypothesis import given, strategies as st, settings, assume
from pathlib import Path
from typing import Optional, List
from unittest.mock import Mock, MagicMock, patch

from app.classification.taxonomy import (
    DocumentCategory,
    ClassificationStatus,
    ClassificationMethod,
)
from app.classification.classifier import (
    ClassificationResult,
    PageAnalysis,
    DocumentClassifier,
)
from app.classification.sampler import (
    AdaptivePageSampler,
    SamplingResult,
)
from app.classification.pipeline import (
    ClassificationPipeline,
    PipelineResult,
    ClassificationFallback,
    CAD_SCORE_THRESHOLD,
    create_classification_pipeline,
)


# =============================================================================
# Mock classes for testing
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
    """Mock CADLikeGate for testing pipeline behavior"""
    
    def __init__(self, fixed_score: Optional[float] = None):
        self.fixed_score = fixed_score
        self.evaluate_called = False
        self.evaluate_call_count = 0
        self.last_pdf_path = None
        self.last_doc_metadata = None
    
    def evaluate(self, pdf_path: Path, doc_metadata: Optional[dict] = None) -> MockGateDecision:
        """Mock evaluate method"""
        self.evaluate_called = True
        self.evaluate_call_count += 1
        self.last_pdf_path = pdf_path
        self.last_doc_metadata = doc_metadata
        
        score = self.fixed_score if self.fixed_score is not None else 0.3
        is_cadlike = score >= CAD_SCORE_THRESHOLD
        
        return MockGateDecision(
            is_cadlike=is_cadlike,
            score=score,
            pages_sampled=[0, 1, 2],
            taggy_pages=[0, 1] if is_cadlike else [],
            features={"geometry_density": score},
            confidence="HIGH" if score >= 0.55 else "MEDIUM",
            detection_method="VECTOR"
        )


class MockDocumentClassifier:
    """Mock DocumentClassifier for testing pipeline behavior"""
    
    def __init__(self, fixed_result: Optional[ClassificationResult] = None):
        self.fixed_result = fixed_result
        self.classify_called = False
        self.classify_call_count = 0
        self.last_page_images = None
        self.last_filename = None
    
    def classify(
        self,
        page_images: List[bytes],
        filename: str,
        metadata: Optional[dict] = None
    ) -> ClassificationResult:
        """Mock classify method"""
        self.classify_called = True
        self.classify_call_count += 1
        self.last_page_images = page_images
        self.last_filename = filename
        
        if self.fixed_result:
            return self.fixed_result
        
        return ClassificationResult(
            category=DocumentCategory.VENDOR_EQUIPMENT.value,
            doc_type="Datasheet",
            confidence=0.85,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="text",
            page_analysis=[],
            reasoning="Mock classification",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )



class MockAdaptivePageSampler:
    """Mock AdaptivePageSampler for testing"""
    
    def __init__(self, fixed_result: Optional[SamplingResult] = None):
        self.fixed_result = fixed_result
        self.sample_called = False
        self.sample_call_count = 0
    
    def sample(self, pdf_path: Path) -> SamplingResult:
        """Mock sample method"""
        self.sample_called = True
        self.sample_call_count += 1
        
        if self.fixed_result:
            return self.fixed_result
        
        return SamplingResult(
            total_pages=10,
            sampled_pages=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            strategy="all",
            page_images=[b"fake_image"] * 10
        )


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Strategy for CAD scores that trigger guardrail (>= 0.55)
high_cad_score_strategy = st.floats(
    min_value=CAD_SCORE_THRESHOLD, 
    max_value=1.0, 
    allow_nan=False
)

# Strategy for CAD scores that don't trigger guardrail (< 0.55)
low_cad_score_strategy = st.floats(
    min_value=0.0, 
    max_value=CAD_SCORE_THRESHOLD - 0.001, 
    allow_nan=False
)

# Strategy for any CAD score
any_cad_score_strategy = st.floats(
    min_value=0.0, 
    max_value=1.0, 
    allow_nan=False
)

# Strategy for confidence scores
confidence_strategy = st.floats(
    min_value=0.0, 
    max_value=1.0, 
    allow_nan=False
)


# =============================================================================
# Property 6: P&ID Guardrail Enforcement
# =============================================================================

class TestProperty6PIDGuardrailEnforcement:
    """
    **Feature: intelligent-classification-deep-search, Property 6: P&ID Guardrail Enforcement**
    
    *For any* document where CADLikeGate returns CAD_score >= 0.55, the classification 
    result SHALL have category="ENGINEERING_DESIGN" and doc_type="P&ID" regardless of 
    AI classifier output.
    
    **Validates: Requirements 3.1**
    """
    
    @given(cad_score=high_cad_score_strategy)
    @settings(max_examples=100)
    def test_high_cad_score_forces_pid_classification(self, cad_score: float):
        """
        Property: CAD_score >= 0.55 must force P&ID classification
        """
        # Verify score is actually high enough
        assume(cad_score >= CAD_SCORE_THRESHOLD)
        
        # Setup mocks
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler,
            cad_score_threshold=CAD_SCORE_THRESHOLD
        )
        
        # Run classification
        result = pipeline.classify_document(
            pdf_path=Path("test.pdf"),
            doc_metadata=None
        )
        
        # Verify P&ID classification is forced
        assert result.classification.category == DocumentCategory.ENGINEERING_DESIGN.value, (
            f"Expected ENGINEERING_DESIGN for CAD_score {cad_score}, "
            f"got {result.classification.category}"
        )
        assert result.classification.doc_type == "P&ID", (
            f"Expected P&ID for CAD_score {cad_score}, "
            f"got {result.classification.doc_type}"
        )
        assert result.guardrail_triggered is True, (
            f"Guardrail should be triggered for CAD_score {cad_score}"
        )

    
    @given(cad_score=high_cad_score_strategy)
    @settings(max_examples=100)
    def test_high_cad_score_sets_method_to_cadlike_gate(self, cad_score: float):
        """
        Property: When guardrail triggers, method must be CADLIKE_GATE
        """
        assume(cad_score >= CAD_SCORE_THRESHOLD)
        
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        assert result.classification.method == ClassificationMethod.CADLIKE_GATE.value, (
            f"Expected method CADLIKE_GATE for CAD_score {cad_score}, "
            f"got {result.classification.method}"
        )
    
    @given(cad_score=high_cad_score_strategy)
    @settings(max_examples=100)
    def test_high_cad_score_confidence_equals_cad_score(self, cad_score: float):
        """
        Property: When guardrail triggers, confidence should equal CAD_score
        """
        assume(cad_score >= CAD_SCORE_THRESHOLD)
        
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        assert abs(result.classification.confidence - cad_score) < 0.001, (
            f"Expected confidence {cad_score}, got {result.classification.confidence}"
        )
    
    def test_exactly_threshold_triggers_guardrail(self):
        """
        Edge case: CAD_score exactly at threshold (0.55) should trigger guardrail
        """
        mock_gate = MockCADLikeGate(fixed_score=CAD_SCORE_THRESHOLD)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        assert result.guardrail_triggered is True
        assert result.classification.category == DocumentCategory.ENGINEERING_DESIGN.value
        assert result.classification.doc_type == "P&ID"


# =============================================================================
# Property 7: Guardrail Execution Order
# =============================================================================

class TestProperty7GuardrailExecutionOrder:
    """
    **Feature: intelligent-classification-deep-search, Property 7: Guardrail Execution Order**
    
    *For any* document classification, CADLikeGate SHALL be evaluated first, and if 
    CAD_score >= 0.55, the AI classifier SHALL NOT be invoked.
    
    **Validates: Requirements 3.2, 3.3**
    """
    
    @given(cad_score=high_cad_score_strategy)
    @settings(max_examples=100)
    def test_ai_classifier_not_called_when_guardrail_triggers(self, cad_score: float):
        """
        Property: AI classifier must NOT be called when CAD_score >= 0.55
        """
        assume(cad_score >= CAD_SCORE_THRESHOLD)
        
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        pipeline.classify_document(Path("test.pdf"))
        
        # Verify gate was called
        assert mock_gate.evaluate_called is True, "CADLikeGate should be called"
        
        # Verify classifier was NOT called
        assert mock_classifier.classify_called is False, (
            f"AI classifier should NOT be called when CAD_score={cad_score} >= {CAD_SCORE_THRESHOLD}"
        )

    
    @given(cad_score=high_cad_score_strategy)
    @settings(max_examples=100)
    def test_sampler_not_called_when_guardrail_triggers(self, cad_score: float):
        """
        Property: Page sampler must NOT be called when guardrail triggers
        """
        assume(cad_score >= CAD_SCORE_THRESHOLD)
        
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        # Verify sampler was NOT called (no need to sample when guardrail triggers)
        assert mock_sampler.sample_called is False, (
            f"Sampler should NOT be called when guardrail triggers (CAD_score={cad_score})"
        )
        
        # Verify sampling result is None
        assert result.sampling is None, "Sampling result should be None when guardrail triggers"
    
    @given(cad_score=any_cad_score_strategy)
    @settings(max_examples=100)
    def test_gate_always_called_first(self, cad_score: float):
        """
        Property: CADLikeGate must always be called first (when available)
        """
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        pipeline.classify_document(Path("test.pdf"))
        
        # Gate should always be called
        assert mock_gate.evaluate_called is True, "CADLikeGate should always be called first"
        assert mock_gate.evaluate_call_count == 1, "CADLikeGate should be called exactly once"
    
    def test_gate_called_before_classifier(self):
        """
        Property: Gate must be evaluated before classifier is invoked
        """
        call_order = []
        
        class OrderTrackingGate(MockCADLikeGate):
            def evaluate(self, pdf_path, doc_metadata=None):
                call_order.append("gate")
                return super().evaluate(pdf_path, doc_metadata)
        
        class OrderTrackingClassifier(MockDocumentClassifier):
            def classify(self, page_images, filename, metadata=None):
                call_order.append("classifier")
                return super().classify(page_images, filename, metadata)
        
        class OrderTrackingSampler(MockAdaptivePageSampler):
            def sample(self, pdf_path):
                call_order.append("sampler")
                return super().sample(pdf_path)
        
        mock_gate = OrderTrackingGate(fixed_score=0.3)  # Low score to trigger classifier
        mock_classifier = OrderTrackingClassifier()
        mock_sampler = OrderTrackingSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        pipeline.classify_document(Path("test.pdf"))
        
        # Verify order: gate -> sampler -> classifier
        assert call_order[0] == "gate", "Gate must be called first"
        assert "sampler" in call_order, "Sampler should be called"
        assert "classifier" in call_order, "Classifier should be called"
        assert call_order.index("gate") < call_order.index("sampler"), (
            "Gate must be called before sampler"
        )
        assert call_order.index("sampler") < call_order.index("classifier"), (
            "Sampler must be called before classifier"
        )


# =============================================================================
# Property 8: AI Classifier Invocation
# =============================================================================

class TestProperty8AIClassifierInvocation:
    """
    **Feature: intelligent-classification-deep-search, Property 8: AI Classifier Invocation**
    
    *For any* document where CADLikeGate returns CAD_score < 0.55, the AI classifier 
    (Gemini 2.5 Flash) SHALL be invoked for classification.
    
    **Validates: Requirements 4.1**
    """
    
    @given(cad_score=low_cad_score_strategy)
    @settings(max_examples=100)
    def test_ai_classifier_called_when_guardrail_not_triggered(self, cad_score: float):
        """
        Property: AI classifier must be called when CAD_score < 0.55
        """
        assume(cad_score < CAD_SCORE_THRESHOLD)
        
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        pipeline.classify_document(Path("test.pdf"))
        
        # Verify classifier was called
        assert mock_classifier.classify_called is True, (
            f"AI classifier should be called when CAD_score={cad_score} < {CAD_SCORE_THRESHOLD}"
        )

    
    @given(cad_score=low_cad_score_strategy)
    @settings(max_examples=100)
    def test_sampler_called_when_guardrail_not_triggered(self, cad_score: float):
        """
        Property: Page sampler must be called when CAD_score < 0.55
        """
        assume(cad_score < CAD_SCORE_THRESHOLD)
        
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        # Verify sampler was called
        assert mock_sampler.sample_called is True, (
            f"Sampler should be called when CAD_score={cad_score} < {CAD_SCORE_THRESHOLD}"
        )
        
        # Verify sampling result is present
        assert result.sampling is not None, "Sampling result should be present"
    
    @given(cad_score=low_cad_score_strategy)
    @settings(max_examples=100)
    def test_guardrail_not_triggered_flag(self, cad_score: float):
        """
        Property: guardrail_triggered must be False when CAD_score < 0.55
        """
        assume(cad_score < CAD_SCORE_THRESHOLD)
        
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        assert result.guardrail_triggered is False, (
            f"guardrail_triggered should be False for CAD_score={cad_score}"
        )
    
    @given(cad_score=low_cad_score_strategy)
    @settings(max_examples=100)
    def test_ai_classifier_result_used_when_guardrail_not_triggered(self, cad_score: float):
        """
        Property: AI classifier result must be used when guardrail doesn't trigger
        """
        assume(cad_score < CAD_SCORE_THRESHOLD)
        
        expected_result = ClassificationResult(
            category=DocumentCategory.OPERATIONS_MAINTENANCE.value,
            doc_type="Maintenance Instruction",
            confidence=0.92,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="text",
            page_analysis=[],
            reasoning="AI classification result",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        mock_gate = MockCADLikeGate(fixed_score=cad_score)
        mock_classifier = MockDocumentClassifier(fixed_result=expected_result)
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        # Verify AI classifier result is used
        assert result.classification.category == expected_result.category
        assert result.classification.doc_type == expected_result.doc_type
        assert result.classification.method == ClassificationMethod.AI_CLASSIFIER.value
    
    def test_no_gate_always_uses_ai_classifier(self):
        """
        Edge case: When no CADLikeGate is provided, AI classifier should always be used
        """
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=None,  # No gate
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        assert mock_classifier.classify_called is True, (
            "AI classifier should be called when no gate is provided"
        )
        assert result.guardrail_triggered is False
        assert result.cad_score is None
    
    def test_just_below_threshold_uses_ai_classifier(self):
        """
        Edge case: CAD_score just below threshold (0.549) should use AI classifier
        """
        mock_gate = MockCADLikeGate(fixed_score=0.549)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        assert mock_classifier.classify_called is True
        assert result.guardrail_triggered is False



# =============================================================================
# Property 18: Classification Failure Handling
# =============================================================================

class TestProperty18ClassificationFailureHandling:
    """
    **Feature: intelligent-classification-deep-search, Property 18: Classification Failure Handling**
    
    *For any* document where classification throws an exception, the document SHALL be 
    marked with status="needs_review" and ingestion SHALL continue without blocking.
    
    **Validates: Requirements 8.4**
    """
    
    def test_gate_failure_continues_to_ai_classifier(self):
        """
        Property: When CADLikeGate fails, pipeline should continue to AI classifier
        """
        class FailingGate:
            def evaluate(self, pdf_path, doc_metadata=None):
                raise RuntimeError("Gate evaluation failed")
        
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=FailingGate(),
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        # Should continue to AI classifier
        assert mock_classifier.classify_called is True, (
            "AI classifier should be called when gate fails"
        )
        # CAD score should be None due to failure
        assert result.cad_score is None
    
    def test_sampler_failure_returns_uncategorized(self):
        """
        Property: When sampler fails, result should be UNCATEGORIZED with NEEDS_REVIEW
        """
        class FailingSampler:
            def sample(self, pdf_path):
                raise RuntimeError("Sampling failed")
        
        mock_gate = MockCADLikeGate(fixed_score=0.3)  # Low score to trigger sampler
        mock_classifier = MockDocumentClassifier()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=FailingSampler()
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        # Should return UNCATEGORIZED with NEEDS_REVIEW
        assert result.classification.category == DocumentCategory.UNCATEGORIZED.value
        assert result.classification.status == ClassificationStatus.NEEDS_REVIEW.value
        assert "sampling failed" in result.classification.reasoning.lower()
    
    def test_classifier_failure_returns_uncategorized(self):
        """
        Property: When AI classifier fails, result should be UNCATEGORIZED with NEEDS_REVIEW
        """
        class FailingClassifier:
            def classify(self, page_images, filename, metadata=None):
                raise RuntimeError("Classification failed")
        
        mock_gate = MockCADLikeGate(fixed_score=0.3)
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=FailingClassifier(),
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        # Should return UNCATEGORIZED with NEEDS_REVIEW
        assert result.classification.category == DocumentCategory.UNCATEGORIZED.value
        assert result.classification.status == ClassificationStatus.NEEDS_REVIEW.value
    
    def test_classify_with_fallback_never_raises(self):
        """
        Property: classify_with_fallback() should never raise exception
        """
        class TotallyBrokenGate:
            def evaluate(self, pdf_path, doc_metadata=None):
                raise RuntimeError("Gate broken")
        
        class TotallyBrokenSampler:
            def sample(self, pdf_path):
                raise RuntimeError("Sampler broken")
        
        class TotallyBrokenClassifier:
            def classify(self, page_images, filename, metadata=None):
                raise RuntimeError("Classifier broken")
        
        pipeline = ClassificationPipeline(
            cadlike_gate=TotallyBrokenGate(),
            classifier=TotallyBrokenClassifier(),
            sampler=TotallyBrokenSampler()
        )
        
        # Should not raise, should return UNCATEGORIZED
        result = pipeline.classify_with_fallback(Path("test.pdf"))
        
        assert result.category == DocumentCategory.UNCATEGORIZED.value
        assert result.status == ClassificationStatus.NEEDS_REVIEW.value
    
    def test_error_message_preserved_in_reasoning(self):
        """
        Property: Error message should be preserved in reasoning field
        
        Note: Using simple test instead of property-based test to avoid
        retry delays causing Hypothesis deadline issues.
        """
        error_msg = "Test API error message"
        
        class FailingClassifier:
            def __init__(self, msg):
                self.msg = msg
            
            def classify(self, page_images, filename, metadata=None):
                raise RuntimeError(self.msg)
        
        mock_gate = MockCADLikeGate(fixed_score=0.3)
        mock_sampler = MockAdaptivePageSampler()
        
        # Create pipeline without retry to avoid delays
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=FailingClassifier(error_msg),
            sampler=mock_sampler
        )
        
        # Use classify_with_fallback which handles errors gracefully
        result = pipeline.classify_with_fallback(Path("test.pdf"))
        
        # Error message should be in reasoning
        assert result.reasoning is not None
        assert "error" in result.reasoning.lower() or error_msg in result.reasoning



# =============================================================================
# ClassificationFallback tests
# =============================================================================

class TestClassificationFallback:
    """Tests for ClassificationFallback helper class"""
    
    @given(confidence=st.floats(min_value=0.0, max_value=0.49, allow_nan=False))
    @settings(max_examples=50)
    def test_on_low_confidence_triggers_fallback(self, confidence: float):
        """
        Property: on_low_confidence should convert low confidence results to UNCATEGORIZED
        """
        original = ClassificationResult(
            category=DocumentCategory.ENGINEERING_DESIGN.value,
            doc_type="Drawing",
            confidence=confidence,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="drawing",
            page_analysis=[],
            reasoning="Original",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        result = ClassificationFallback.on_low_confidence(original, threshold=0.5)
        
        assert result.category == DocumentCategory.UNCATEGORIZED.value
        assert result.status == ClassificationStatus.NEEDS_REVIEW.value
        assert result.confidence == confidence  # Preserved
    
    @given(confidence=st.floats(min_value=0.5, max_value=1.0, allow_nan=False))
    @settings(max_examples=50)
    def test_on_low_confidence_preserves_high_confidence(self, confidence: float):
        """
        Property: on_low_confidence should preserve high confidence results
        """
        original = ClassificationResult(
            category=DocumentCategory.VENDOR_EQUIPMENT.value,
            doc_type="Datasheet",
            confidence=confidence,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="text",
            page_analysis=[],
            reasoning="Original",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        result = ClassificationFallback.on_low_confidence(original, threshold=0.5)
        
        assert result.category == original.category
        assert result.doc_type == original.doc_type
        assert result.status == original.status
    
    def test_on_gemini_failure_returns_uncategorized(self):
        """
        Property: on_gemini_failure should return UNCATEGORIZED with error info
        """
        error = RuntimeError("API timeout")
        result = ClassificationFallback.on_gemini_failure(Path("test.pdf"), error)
        
        assert result.category == DocumentCategory.UNCATEGORIZED.value
        assert result.status == ClassificationStatus.NEEDS_REVIEW.value
        assert result.confidence == 0.0
        assert "API timeout" in result.reasoning
    
    def test_on_sampling_failure_returns_uncategorized(self):
        """
        Property: on_sampling_failure should return UNCATEGORIZED with error info
        """
        error = ValueError("Cannot open PDF")
        result = ClassificationFallback.on_sampling_failure(Path("test.pdf"), error)
        
        assert result.category == DocumentCategory.UNCATEGORIZED.value
        assert result.status == ClassificationStatus.NEEDS_REVIEW.value
        assert "Cannot open PDF" in result.reasoning


# =============================================================================
# PipelineResult tests
# =============================================================================

class TestPipelineResult:
    """Tests for PipelineResult dataclass"""
    
    def test_to_dict_includes_all_fields(self):
        """
        Property: to_dict() should include all pipeline result fields
        """
        classification = ClassificationResult(
            category=DocumentCategory.ENGINEERING_DESIGN.value,
            doc_type="P&ID",
            confidence=0.85,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="drawing",
            page_analysis=[],
            reasoning="Test",
            method=ClassificationMethod.CADLIKE_GATE.value
        )
        
        sampling = SamplingResult(
            total_pages=10,
            sampled_pages=[0, 1, 2],
            strategy="head_body_tail",
            page_images=[]
        )
        
        result = PipelineResult(
            classification=classification,
            sampling=sampling,
            cad_score=0.75,
            guardrail_triggered=True
        )
        
        data = result.to_dict()
        
        assert "classification" in data
        assert "sampling" in data
        assert "cad_score" in data
        assert "guardrail_triggered" in data
        assert data["cad_score"] == 0.75
        assert data["guardrail_triggered"] is True
    
    def test_to_dict_handles_none_sampling(self):
        """
        Property: to_dict() should handle None sampling gracefully
        """
        classification = ClassificationResult.create_uncategorized()
        
        result = PipelineResult(
            classification=classification,
            sampling=None,
            cad_score=None,
            guardrail_triggered=False
        )
        
        data = result.to_dict()
        
        assert data["sampling"] is None
        assert data["cad_score"] is None


# =============================================================================
# Integration tests
# =============================================================================

class TestPipelineIntegration:
    """Integration tests for the full pipeline"""
    
    def test_full_pipeline_with_high_cad_score(self):
        """
        Integration: Full pipeline with high CAD score should force P&ID
        """
        mock_gate = MockCADLikeGate(fixed_score=0.85)
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test_pid.pdf"))
        
        # Verify full result
        assert result.guardrail_triggered is True
        assert result.cad_score == 0.85
        assert result.classification.category == DocumentCategory.ENGINEERING_DESIGN.value
        assert result.classification.doc_type == "P&ID"
        assert result.classification.method == ClassificationMethod.CADLIKE_GATE.value
        assert result.sampling is None
        
        # Verify classifier was not called
        assert mock_classifier.classify_called is False
    
    def test_full_pipeline_with_low_cad_score(self):
        """
        Integration: Full pipeline with low CAD score should use AI classifier
        """
        expected_classification = ClassificationResult(
            category=DocumentCategory.VENDOR_EQUIPMENT.value,
            doc_type="Vendor Manual",
            confidence=0.88,
            status=ClassificationStatus.CLASSIFIED.value,
            dominant_content="text",
            page_analysis=[],
            reasoning="AI classified as vendor manual",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
        
        mock_gate = MockCADLikeGate(fixed_score=0.25)
        mock_classifier = MockDocumentClassifier(fixed_result=expected_classification)
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test_manual.pdf"))
        
        # Verify full result
        assert result.guardrail_triggered is False
        assert result.cad_score == 0.25
        assert result.classification.category == DocumentCategory.VENDOR_EQUIPMENT.value
        assert result.classification.doc_type == "Vendor Manual"
        assert result.sampling is not None
        
        # Verify classifier was called
        assert mock_classifier.classify_called is True
    
    def test_skip_guardrail_flag(self):
        """
        Integration: skip_guardrail=True should bypass CADLikeGate
        """
        mock_gate = MockCADLikeGate(fixed_score=0.95)  # Would trigger guardrail
        mock_classifier = MockDocumentClassifier()
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=mock_classifier,
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(
            Path("test.pdf"),
            skip_guardrail=True
        )
        
        # Gate should not be called
        assert mock_gate.evaluate_called is False
        
        # Classifier should be called
        assert mock_classifier.classify_called is True
        
        # Result should be from classifier
        assert result.guardrail_triggered is False
        assert result.cad_score is None



# =============================================================================
# Retry logic tests
# =============================================================================

class TestRetryLogic:
    """Tests for retry logic in classification pipeline"""
    
    def test_retry_succeeds_on_second_attempt(self):
        """
        Property: Retry should succeed if second attempt works
        """
        attempt_count = [0]
        
        class RetryableClassifier:
            def classify(self, page_images, filename, metadata=None):
                attempt_count[0] += 1
                if attempt_count[0] == 1:
                    raise RuntimeError("First attempt failed")
                return ClassificationResult(
                    category=DocumentCategory.VENDOR_EQUIPMENT.value,
                    doc_type="Datasheet",
                    confidence=0.9,
                    status=ClassificationStatus.CLASSIFIED.value,
                    dominant_content="text",
                    page_analysis=[],
                    reasoning="Success on retry",
                    method=ClassificationMethod.AI_CLASSIFIER.value
                )
        
        mock_gate = MockCADLikeGate(fixed_score=0.3)
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=RetryableClassifier(),
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        assert attempt_count[0] == 2, "Should have made 2 attempts"
        assert result.classification.category == DocumentCategory.VENDOR_EQUIPMENT.value
        assert result.classification.doc_type == "Datasheet"
    
    def test_retry_exhausted_returns_uncategorized(self):
        """
        Property: When all retries fail, should return UNCATEGORIZED
        """
        attempt_count = [0]
        
        class AlwaysFailingClassifier:
            def classify(self, page_images, filename, metadata=None):
                attempt_count[0] += 1
                raise RuntimeError(f"Attempt {attempt_count[0]} failed")
        
        mock_gate = MockCADLikeGate(fixed_score=0.3)
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=AlwaysFailingClassifier(),
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        # Default max_retries is 2, so 3 total attempts
        assert attempt_count[0] == 3, "Should have made 3 attempts (1 + 2 retries)"
        assert result.classification.category == DocumentCategory.UNCATEGORIZED.value
        assert result.classification.status == ClassificationStatus.NEEDS_REVIEW.value
        assert "retries" in result.classification.reasoning.lower()
    
    def test_retry_succeeds_on_third_attempt(self):
        """
        Property: Retry should succeed if third attempt works
        """
        attempt_count = [0]
        
        class RetryableClassifier:
            def classify(self, page_images, filename, metadata=None):
                attempt_count[0] += 1
                if attempt_count[0] < 3:
                    raise RuntimeError(f"Attempt {attempt_count[0]} failed")
                return ClassificationResult(
                    category=DocumentCategory.SAFETY_MANAGEMENT.value,
                    doc_type="MOC",
                    confidence=0.85,
                    status=ClassificationStatus.CLASSIFIED.value,
                    dominant_content="text",
                    page_analysis=[],
                    reasoning="Success on third attempt",
                    method=ClassificationMethod.AI_CLASSIFIER.value
                )
        
        mock_gate = MockCADLikeGate(fixed_score=0.3)
        mock_sampler = MockAdaptivePageSampler()
        
        pipeline = ClassificationPipeline(
            cadlike_gate=mock_gate,
            classifier=RetryableClassifier(),
            sampler=mock_sampler
        )
        
        result = pipeline.classify_document(Path("test.pdf"))
        
        assert attempt_count[0] == 3, "Should have made 3 attempts"
        assert result.classification.category == DocumentCategory.SAFETY_MANAGEMENT.value
