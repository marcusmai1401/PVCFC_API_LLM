"""
Classification Pipeline
Integrates CADLikeGate guardrail with AI Classifier

Flow:
1. Run CADLikeGate first
2. If CAD_score >= 0.55: Force P&ID classification
3. Else: Run AI classification with Gemini
4. If confidence < 0.5: Mark as UNCATEGORIZED + NEEDS_REVIEW
"""
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol, TypeVar

from loguru import logger

from app.classification.classifier import ClassificationResult, DocumentClassifier
from app.classification.sampler import AdaptivePageSampler, SamplingResult
from app.classification.taxonomy import (
    ClassificationMethod,
    ClassificationStatus,
    DocumentCategory,
)


T = TypeVar("T")


# CAD score threshold for P&ID force-assignment
CAD_SCORE_THRESHOLD = 0.55

# Retry configuration
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_RETRY_BACKOFF = 2.0  # exponential backoff multiplier


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_RETRY_DELAY,
    backoff_multiplier: float = DEFAULT_RETRY_BACKOFF,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> T:
    """
    Retry a function with exponential backoff
    
    Args:
        func: Function to retry (no arguments)
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback called on each retry with (exception, attempt)
        
    Returns:
        Result of successful function call
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            
            if attempt < max_retries:
                if on_retry:
                    on_retry(e, attempt + 1)
                else:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                time.sleep(delay)
                delay *= backoff_multiplier
            else:
                logger.error(f"All {max_retries + 1} attempts failed. Last error: {e}")
    
    raise last_exception


@dataclass
class PipelineResult:
    """Extended result with pipeline metadata"""
    classification: ClassificationResult
    sampling: Optional[SamplingResult] = None
    cad_score: Optional[float] = None
    guardrail_triggered: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "classification": self.classification.to_dict(),
            "sampling": self.sampling.to_dict() if self.sampling else None,
            "cad_score": self.cad_score,
            "guardrail_triggered": self.guardrail_triggered
        }


class CADLikeGateProtocol(Protocol):
    """Protocol for CADLikeGate interface
    
    This protocol matches the actual CADLikeGate class in app/ingestion/cadlike_gate.py
    The evaluate() method returns a GateDecision with score and is_cadlike fields.
    """
    
    def evaluate(self, pdf_path: Path, doc_metadata: Optional[dict] = None):
        """
        Evaluate if a PDF is CAD-like
        
        Args:
            pdf_path: Path to PDF file
            doc_metadata: Optional pre-extracted metadata
            
        Returns:
            GateDecision with score, is_cadlike, and other fields
        """
        ...


class ClassificationPipeline:
    """
    Integrated classification pipeline with P&ID guardrail
    
    Flow:
    1. Run CADLikeGate first
    2. If CAD_score >= 0.55: Force P&ID classification
    3. Else: Run AI classification with Gemini
    4. If confidence < 0.5: Mark as UNCATEGORIZED + NEEDS_REVIEW
    """
    
    def __init__(
        self,
        cadlike_gate: Optional[CADLikeGateProtocol] = None,
        classifier: Optional[DocumentClassifier] = None,
        sampler: Optional[AdaptivePageSampler] = None,
        cad_score_threshold: float = CAD_SCORE_THRESHOLD
    ):
        """
        Initialize pipeline
        
        Args:
            cadlike_gate: CADLikeGate instance for P&ID detection
            classifier: DocumentClassifier instance for AI classification
            sampler: AdaptivePageSampler instance for page sampling
            cad_score_threshold: Threshold for P&ID force-assignment (default 0.55)
        """
        self.cadlike_gate = cadlike_gate
        self.classifier = classifier or DocumentClassifier()
        self.sampler = sampler or AdaptivePageSampler()
        self.cad_score_threshold = cad_score_threshold
    
    def classify_document(
        self,
        pdf_path: Path,
        doc_metadata: Optional[dict] = None,
        skip_guardrail: bool = False
    ) -> PipelineResult:
        """
        Run full classification pipeline
        
        Args:
            pdf_path: Path to PDF file
            doc_metadata: Optional pre-extracted metadata
            skip_guardrail: Skip CADLikeGate check (for testing)
            
        Returns:
            PipelineResult with classification and metadata
        """
        pdf_path = Path(pdf_path)
        filename = pdf_path.name
        
        logger.info(f"Starting classification pipeline for: {filename}")
        
        cad_score = None
        guardrail_triggered = False
        
        # Step 1: Run CADLikeGate guardrail (if available and not skipped)
        if self.cadlike_gate and not skip_guardrail:
            try:
                cad_score = self._run_guardrail(pdf_path, doc_metadata)
                
                if cad_score >= self.cad_score_threshold:
                    logger.info(
                        f"P&ID guardrail triggered: CAD_score={cad_score:.3f} >= {self.cad_score_threshold}"
                    )
                    guardrail_triggered = True
                    
                    # Force P&ID classification
                    classification = ClassificationResult(
                        category=DocumentCategory.ENGINEERING_DESIGN.value,
                        doc_type="P&ID",
                        confidence=cad_score,
                        status=ClassificationStatus.CLASSIFIED.value,
                        dominant_content="drawing",
                        page_analysis=[],
                        reasoning=f"P&ID detected by CADLikeGate (score={cad_score:.3f})",
                        method=ClassificationMethod.CADLIKE_GATE.value
                    )
                    
                    return PipelineResult(
                        classification=classification,
                        sampling=None,
                        cad_score=cad_score,
                        guardrail_triggered=True
                    )
                    
            except Exception as e:
                logger.warning(f"CADLikeGate failed, proceeding to AI classifier: {e}")
                cad_score = None
        
        # Step 2: Sample pages for AI classification
        try:
            sampling_result = self.sampler.sample(pdf_path)
            logger.info(
                f"Sampled {sampling_result.sample_count}/{sampling_result.total_pages} pages "
                f"using '{sampling_result.strategy}' strategy"
            )
        except Exception as e:
            logger.error(f"Page sampling failed: {e}")
            return PipelineResult(
                classification=ClassificationResult.create_uncategorized(
                    reasoning=f"Page sampling failed: {str(e)}"
                ),
                sampling=None,
                cad_score=cad_score,
                guardrail_triggered=False
            )
        
        # Step 3: Run AI classification with retry logic
        classification = self._classify_with_retry(
            page_images=sampling_result.page_images,
            filename=filename,
            metadata=doc_metadata
        )
        
        return PipelineResult(
            classification=classification,
            sampling=sampling_result,
            cad_score=cad_score,
            guardrail_triggered=guardrail_triggered
        )
    
    def _run_guardrail(self, pdf_path: Path, doc_metadata: Optional[dict] = None) -> float:
        """
        Run CADLikeGate guardrail
        
        Args:
            pdf_path: Path to PDF file
            doc_metadata: Optional pre-extracted metadata
            
        Returns:
            CAD score (0.0-1.0)
        """
        if not self.cadlike_gate:
            return 0.0
        
        # Call evaluate() which returns GateDecision with score field
        decision = self.cadlike_gate.evaluate(pdf_path, doc_metadata)
        return decision.score
    
    def _classify_with_retry(
        self,
        page_images: list,
        filename: str,
        metadata: Optional[dict] = None,
        max_retries: int = DEFAULT_MAX_RETRIES
    ) -> ClassificationResult:
        """
        Run AI classification with retry logic for API failures
        
        Args:
            page_images: List of page images (PNG bytes)
            filename: Original filename
            metadata: Optional metadata
            max_retries: Maximum retry attempts (default 2)
            
        Returns:
            ClassificationResult (never raises, returns UNCATEGORIZED on failure)
        """
        def do_classify():
            return self.classifier.classify(
                page_images=page_images,
                filename=filename,
                metadata=metadata
            )
        
        def on_retry(e: Exception, attempt: int):
            logger.warning(
                f"AI classification attempt {attempt} failed for {filename}: {e}. "
                f"Retrying..."
            )
        
        try:
            classification = retry_with_backoff(
                func=do_classify,
                max_retries=max_retries,
                initial_delay=DEFAULT_RETRY_DELAY,
                backoff_multiplier=DEFAULT_RETRY_BACKOFF,
                on_retry=on_retry
            )
            
            logger.info(
                f"AI classification result: {classification.category}/{classification.doc_type} "
                f"(confidence={classification.confidence:.2f})"
            )
            
            return classification
            
        except Exception as e:
            logger.error(f"AI classification failed after {max_retries + 1} attempts: {e}")
            return ClassificationResult.create_uncategorized(
                reasoning=f"AI classification failed after retries: {str(e)}"
            )
    
    def classify_with_fallback(
        self,
        pdf_path: Path,
        doc_metadata: Optional[dict] = None
    ) -> ClassificationResult:
        """
        Convenience method that returns just the ClassificationResult
        with automatic fallback handling
        
        Args:
            pdf_path: Path to PDF file
            doc_metadata: Optional metadata
            
        Returns:
            ClassificationResult (never raises exception)
        """
        try:
            result = self.classify_document(pdf_path, doc_metadata)
            return result.classification
        except Exception as e:
            logger.error(f"Pipeline failed completely: {e}")
            return ClassificationResult.create_uncategorized(
                reasoning=f"Pipeline error: {str(e)}"
            )


class ClassificationFallback:
    """
    Fallback strategies for classification failures
    """
    
    @staticmethod
    def on_gemini_failure(pdf_path: Path, error: Exception) -> ClassificationResult:
        """Fallback when Gemini API fails"""
        return ClassificationResult(
            category=DocumentCategory.UNCATEGORIZED.value,
            doc_type="Unknown",
            confidence=0.0,
            status=ClassificationStatus.NEEDS_REVIEW.value,
            dominant_content="unknown",
            page_analysis=[],
            reasoning=f"Classification failed: {str(error)}",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )
    
    @staticmethod
    def on_low_confidence(
        result: ClassificationResult,
        threshold: float = 0.5
    ) -> ClassificationResult:
        """Override low confidence results"""
        if result.confidence < threshold:
            return ClassificationResult(
                category=DocumentCategory.UNCATEGORIZED.value,
                doc_type="Unknown",
                confidence=result.confidence,
                status=ClassificationStatus.NEEDS_REVIEW.value,
                dominant_content=result.dominant_content,
                page_analysis=result.page_analysis,
                reasoning=f"Low confidence ({result.confidence:.2f}): {result.reasoning}",
                method=result.method
            )
        return result
    
    @staticmethod
    def on_sampling_failure(pdf_path: Path, error: Exception) -> ClassificationResult:
        """Fallback when page sampling fails"""
        return ClassificationResult(
            category=DocumentCategory.UNCATEGORIZED.value,
            doc_type="Unknown",
            confidence=0.0,
            status=ClassificationStatus.NEEDS_REVIEW.value,
            dominant_content="unknown",
            page_analysis=[],
            reasoning=f"Page sampling failed: {str(error)}",
            method=ClassificationMethod.AI_CLASSIFIER.value
        )


# =============================================================================
# Factory functions for creating pipeline instances
# =============================================================================

# Singleton instance
_pipeline_instance: Optional[ClassificationPipeline] = None


def get_classification_pipeline(
    use_cadlike_gate: bool = True,
    cad_score_threshold: float = CAD_SCORE_THRESHOLD
) -> ClassificationPipeline:
    """
    Get singleton ClassificationPipeline instance with CADLikeGate integration
    
    Args:
        use_cadlike_gate: Whether to use CADLikeGate guardrail (default True)
        cad_score_threshold: Threshold for P&ID force-assignment (default 0.55)
        
    Returns:
        ClassificationPipeline instance
    """
    global _pipeline_instance
    
    if _pipeline_instance is None:
        cadlike_gate = None
        
        if use_cadlike_gate:
            try:
                from app.ingestion.cadlike_gate import get_cadlike_gate
                cadlike_gate = get_cadlike_gate()
                logger.info("CADLikeGate guardrail enabled for classification pipeline")
            except ImportError as e:
                logger.warning(f"Could not import CADLikeGate: {e}")
            except Exception as e:
                logger.warning(f"Could not initialize CADLikeGate: {e}")
        
        _pipeline_instance = ClassificationPipeline(
            cadlike_gate=cadlike_gate,
            classifier=DocumentClassifier(),
            sampler=AdaptivePageSampler(),
            cad_score_threshold=cad_score_threshold
        )
    
    return _pipeline_instance


def create_classification_pipeline(
    cadlike_gate=None,
    classifier: Optional[DocumentClassifier] = None,
    sampler: Optional[AdaptivePageSampler] = None,
    cad_score_threshold: float = CAD_SCORE_THRESHOLD,
    use_default_cadlike_gate: bool = False
) -> ClassificationPipeline:
    """
    Create a new ClassificationPipeline instance (not singleton)
    
    Use this for testing or when you need a custom configuration.
    
    Args:
        cadlike_gate: Custom CADLikeGate instance (optional)
        classifier: Custom DocumentClassifier instance (optional)
        sampler: Custom AdaptivePageSampler instance (optional)
        cad_score_threshold: Threshold for P&ID force-assignment (default 0.55)
        use_default_cadlike_gate: If True and cadlike_gate is None, use default CADLikeGate
        
    Returns:
        New ClassificationPipeline instance
    """
    if cadlike_gate is None and use_default_cadlike_gate:
        try:
            from app.ingestion.cadlike_gate import get_cadlike_gate
            cadlike_gate = get_cadlike_gate()
        except Exception as e:
            logger.warning(f"Could not initialize default CADLikeGate: {e}")
    
    return ClassificationPipeline(
        cadlike_gate=cadlike_gate,
        classifier=classifier or DocumentClassifier(),
        sampler=sampler or AdaptivePageSampler(),
        cad_score_threshold=cad_score_threshold
    )


def reset_pipeline_singleton():
    """Reset the singleton pipeline instance (useful for testing)"""
    global _pipeline_instance
    _pipeline_instance = None
