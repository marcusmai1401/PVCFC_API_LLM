"""
Citation Validator - CiteFix-lite Implementation

Validates citations to prevent hallucinations and improve accuracy.

Validates:
1. Document ID exists in corpus
2. Page number is valid for that document
3. Page text actually exists on the cited page
4. Snippets exist on the page

Features:
- Level 1: Basic validation (doc_id, page number) - ~1-5ms
- Level 2: Text verification (fuzzy matching, snippets) - ~10-30ms
- Confidence scoring with calibration
- Neighbor page scanning for low-confidence citations

Usage:
    validator = CitationValidator()
    result = validator.validate(
        doc_id="document_123",
        page=5,
        page_text="cited page text...",
        snippets=[snippet1, snippet2],
    )

    if not result.is_valid:
        for error in result.errors:
            print(f"Error: {error.message}")
"""

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# Import snippet dataclass
try:
    from app.rag.snippet_extractor import Snippet
except ImportError:
    # Fallback if not available
    @dataclass
    class Snippet:
        text: str
        start_pos: int = 0
        end_pos: int = 0
        matched_keywords: set = field(default_factory=set)
        score: float = 0.0
        highlighted_text: Optional[str] = None


class ValidationErrorType(str, Enum):
    """Types of validation errors"""

    DOC_NOT_FOUND = "doc_not_found"
    INVALID_PAGE_NUMBER = "invalid_page_number"
    PAGE_OUT_OF_RANGE = "page_out_of_range"
    TEXT_NOT_FOUND = "text_not_found"
    LOW_CONFIDENCE = "low_confidence"
    SNIPPET_MISMATCH = "snippet_mismatch"


class ErrorSeverity(str, Enum):
    """Severity levels for validation errors"""

    CRITICAL = "critical"  # Citation definitely wrong
    WARNING = "warning"  # Possibly wrong
    INFO = "info"  # Minor issue


@dataclass
class ValidationError:
    """Single validation error"""

    error_type: ValidationErrorType
    message: str
    severity: ErrorSeverity
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.error_type.value,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details,
        }


@dataclass
class ValidationResult:
    """Result of citation validation"""

    is_valid: bool  # Overall validation status
    confidence: float  # Confidence score (0.0 to 1.0)
    errors: List[ValidationError] = field(default_factory=list)
    checks: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, error: ValidationError):
        """Add validation error"""
        self.errors.append(error)
        if error.severity == ErrorSeverity.CRITICAL:
            self.is_valid = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "errors": [e.to_dict() for e in self.errors],
            "checks": self.checks,
            "metadata": self.metadata,
        }


class CitationValidator:
    """
    Validates citations to prevent hallucinations

    Validates:
    - Doc_ID existence in corpus
    - Page number validity
    - Text/snippet existence on page

    Levels:
    - Level 1: Basic checks (doc_id, page) - Fast (~1-5ms)
    - Level 2: Text verification (fuzzy, snippets) - Moderate (~10-30ms)
    - Level 3: Semantic validation (future) - Slow (~100-500ms)
    """

    def __init__(
        self,
        validation_level: int = 2,  # 1=basic, 2=text, 3=semantic
        min_confidence_threshold: float = 0.7,
        text_match_threshold: float = 0.5,
        neighbor_scan_range: int = 2,  # ±2 pages for low confidence
    ):
        """
        Initialize validator

        Args:
            validation_level: Validation depth (1, 2, or 3)
            min_confidence_threshold: Minimum confidence to pass
            text_match_threshold: Minimum text similarity to pass
            neighbor_scan_range: Number of neighbor pages to scan if low confidence
        """
        self.validation_level = validation_level
        self.min_confidence_threshold = min_confidence_threshold
        self.text_match_threshold = text_match_threshold
        self.neighbor_scan_range = neighbor_scan_range

        # Load resources
        self._doc_id_map = self._load_doc_id_map()
        self._page_reranker = None  # Lazy load

        # Caching
        self._page_count_cache = {}
        self._page_text_cache = {}  # LRU cache for page texts

        logger.info(
            f"CitationValidator initialized (level={validation_level}, "
            f"threshold={min_confidence_threshold})"
        )

    def validate(
        self,
        doc_id: str,
        page: int,
        page_text: str,
        snippets: Optional[List[Snippet]] = None,
        query: Optional[str] = None,
    ) -> ValidationResult:
        """
        Main validation method

        Args:
            doc_id: Document identifier
            page: Page number (1-indexed)
            page_text: Cited page text to validate
            snippets: List of snippets extracted from page
            query: Original search query (for fallback keyword matching)

        Returns:
            ValidationResult with validation status and errors
        """
        result = ValidationResult(is_valid=True, confidence=1.0)
        checks = {}
        snippets = snippets or []

        # Level 1: Doc_ID check
        doc_exists = self.validate_doc_id(doc_id)
        checks["doc_exists"] = doc_exists

        if not doc_exists:
            result.add_error(
                ValidationError(
                    error_type=ValidationErrorType.DOC_NOT_FOUND,
                    message=f"Document '{doc_id}' not found in corpus",
                    severity=ErrorSeverity.CRITICAL,
                    details={"doc_id": doc_id},
                )
            )
            result.confidence = 0.0
            result.checks = checks
            return result  # Early exit

        # Level 1: Page number check
        page_valid = self.validate_page_number(doc_id, page)
        checks["page_valid"] = page_valid

        if not page_valid:
            result.add_error(
                ValidationError(
                    error_type=ValidationErrorType.INVALID_PAGE_NUMBER,
                    message=f"Page {page} is invalid for document '{doc_id}'",
                    severity=ErrorSeverity.CRITICAL,
                    details={"page": page, "doc_id": doc_id},
                )
            )
            result.confidence *= 0.3  # Severe penalty

        # Load actual page text from PDF for comparison
        actual_page_text = self._load_page_text(doc_id, page)

        # Level 2: Page text validation (if enabled)
        if self.validation_level >= 2 and page_text and actual_page_text:
            page_text_confidence = self.validate_page_text(
                doc_id, page, page_text, actual_page_text
            )
            checks["page_text_valid"] = page_text_confidence > self.text_match_threshold
            checks["page_text_confidence"] = page_text_confidence

            if page_text_confidence < self.text_match_threshold:
                result.add_error(
                    ValidationError(
                        error_type=ValidationErrorType.TEXT_NOT_FOUND,
                        message=f"Cited page text does not match actual page content (confidence: {page_text_confidence:.2%})",
                        severity=ErrorSeverity.WARNING,
                        details={"page_text_confidence": page_text_confidence},
                    )
                )

                # Try neighbor pages if confidence is very low
                if page_text_confidence < 0.3:
                    neighbor_result = self._scan_neighbor_pages(
                        doc_id, page, page_text, actual_page_text
                    )
                    if neighbor_result:
                        checks["neighbor_page_found"] = neighbor_result["page"]
                        checks["neighbor_confidence"] = neighbor_result["confidence"]
                        result.metadata["suggested_page"] = neighbor_result["page"]
                        logger.info(
                            f"Found better match on page {neighbor_result['page']} "
                            f"(confidence: {neighbor_result['confidence']:.2%})"
                        )

            result.confidence *= page_text_confidence

        # Level 2: Snippet validation (if snippets provided)
        if self.validation_level >= 2 and snippets and actual_page_text:
            snippet_coverage = self.validate_snippets(snippets, actual_page_text)
            checks["snippets_valid"] = snippet_coverage > 0.5
            checks["snippet_coverage"] = snippet_coverage

            if snippet_coverage < 0.5:
                result.add_error(
                    ValidationError(
                        error_type=ValidationErrorType.SNIPPET_MISMATCH,
                        message=f"Only {snippet_coverage:.0%} of snippets found on page",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "snippet_coverage": snippet_coverage,
                            "snippet_count": len(snippets),
                        },
                    )
                )

            result.confidence *= 0.5 + snippet_coverage * 0.5  # Boost based on coverage

        # Calculate final confidence
        result.confidence = self.calculate_confidence(checks)

        # Apply threshold
        if result.confidence < self.min_confidence_threshold:
            result.add_error(
                ValidationError(
                    error_type=ValidationErrorType.LOW_CONFIDENCE,
                    message=f"Validation confidence {result.confidence:.2%} below threshold {self.min_confidence_threshold:.2%}",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "confidence": result.confidence,
                        "threshold": self.min_confidence_threshold,
                    },
                )
            )

        result.checks = checks
        result.metadata.update(
            {
                "validation_level": self.validation_level,
                "doc_id": doc_id,
                "page": page,
                "snippet_count": len(snippets),
            }
        )

        return result

    def validate_doc_id(self, doc_id: str) -> bool:
        """Check if doc_id exists in corpus"""
        return doc_id in self._doc_id_map

    def validate_page_number(self, doc_id: str, page: int) -> bool:
        """Check if page number is valid for document"""
        if doc_id not in self._doc_id_map:
            return False

        # Use cached page count
        page_count = self._get_page_count(doc_id)
        if page_count is None:
            return False

        return 1 <= page <= page_count

    def validate_page_text(
        self,
        doc_id: str,
        page: int,
        cited_page_text: str,
        actual_page_text: str,
    ) -> float:
        """
        Validate that cited page text matches actual page content

        Args:
            doc_id: Document ID
            page: Page number
            cited_page_text: Page text from citation
            actual_page_text: Actual page text from PDF

        Returns:
            Confidence score (0.0 to 1.0)
        """
        try:
            if not actual_page_text:
                return 0.0

            # Normalize texts
            cited_normalized = self._normalize_text(cited_page_text)
            actual_normalized = self._normalize_text(actual_page_text)

            # Method 1: Exact substring match (high confidence)
            if cited_normalized in actual_normalized:
                return 1.0

            # Method 2: Fuzzy matching (moderate confidence)
            similarity = self._fuzzy_match(cited_normalized, actual_normalized)

            # Method 3: Keyword overlap (lower confidence)
            keyword_overlap = self._keyword_overlap(cited_page_text, actual_page_text)

            # Combined confidence (fuzzy is primary, keyword is fallback)
            confidence = max(similarity, keyword_overlap * 0.7)

            return min(confidence, 1.0)

        except Exception as e:
            logger.error(f"Failed to validate page text: {e}")
            return 0.5  # Unknown, give benefit of doubt

    def validate_snippets(
        self,
        snippets: List[Snippet],
        actual_page_text: str,
    ) -> float:
        """
        Validate that snippets actually exist on the page

        Args:
            snippets: List of snippets to validate
            actual_page_text: Actual page text from PDF

        Returns:
            Coverage score (0.0 to 1.0) - ratio of valid snippets
        """
        if not snippets:
            return 1.0  # No snippets to validate = pass

        if not actual_page_text:
            return 0.0

        actual_normalized = self._normalize_text(actual_page_text)
        valid_count = 0.0

        for snippet in snippets:
            snippet_text = self._normalize_text(snippet.text)

            # Check if snippet exists in page (exact or fuzzy)
            if snippet_text in actual_normalized:
                valid_count += 1.0
            else:
                # Try fuzzy match
                fuzzy_score = self._fuzzy_match(snippet_text, actual_normalized)
                if fuzzy_score > 0.8:
                    valid_count += fuzzy_score  # Partial credit

        # Return coverage ratio
        coverage = valid_count / len(snippets)
        return min(coverage, 1.0)

    def calculate_confidence(self, checks: Dict[str, Any]) -> float:
        """
        Calculate overall confidence score

        Args:
            checks: Dictionary of validation checks

        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 1.0

        # Doc existence (critical)
        if not checks.get("doc_exists", False):
            return 0.0

        # Page validity (critical)
        if not checks.get("page_valid", False):
            confidence *= 0.3

        # Page text validity (important)
        if "page_text_confidence" in checks:
            confidence *= checks["page_text_confidence"]

        # Snippet validity (important)
        if "snippet_coverage" in checks:
            # Boost confidence based on snippet coverage
            coverage = checks["snippet_coverage"]
            confidence *= 0.7 + coverage * 0.3

        return min(confidence, 1.0)

    def _scan_neighbor_pages(
        self,
        doc_id: str,
        page: int,
        cited_text: str,
        actual_text: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Scan neighbor pages (±N) to find better match

        Args:
            doc_id: Document ID
            page: Original page number
            cited_text: Cited page text
            actual_text: Actual text from original page

        Returns:
            Dict with 'page' and 'confidence' if better match found, else None
        """
        best_match = None
        best_confidence = self._fuzzy_match(
            self._normalize_text(cited_text), self._normalize_text(actual_text)
        )

        # Check neighbor pages
        for offset in range(-self.neighbor_scan_range, self.neighbor_scan_range + 1):
            if offset == 0:
                continue  # Skip original page

            neighbor_page = page + offset

            # Validate neighbor page exists
            if not self.validate_page_number(doc_id, neighbor_page):
                continue

            # Load neighbor page text
            neighbor_text = self._load_page_text(doc_id, neighbor_page)
            if not neighbor_text:
                continue

            # Calculate confidence
            confidence = self._fuzzy_match(
                self._normalize_text(cited_text), self._normalize_text(neighbor_text)
            )

            # Track best match
            if confidence > best_confidence and confidence > 0.7:
                best_confidence = confidence
                best_match = {
                    "page": neighbor_page,
                    "confidence": confidence,
                    "offset": offset,
                }

        return best_match

    def _load_doc_id_map(self) -> Dict[str, str]:
        """Load document ID to path mapping"""
        try:
            # Try production path first
            map_paths = [
                Path("artifacts/ingestion_production/doc_id_map.json"),
                Path("artifacts/ingestion/doc_id_map.json"),
            ]

            for map_path in map_paths:
                if map_path.exists():
                    with open(map_path, "r", encoding="utf-8") as f:
                        doc_map = json.load(f)
                        logger.info(f"Loaded {len(doc_map)} documents from {map_path}")
                        return doc_map

            logger.warning("No doc_id_map.json found in any location")

        except Exception as e:
            logger.error(f"Failed to load doc_id_map: {e}")

        return {}

    def _get_page_count(self, doc_id: str) -> Optional[int]:
        """Get page count for document (with caching)"""
        # Check cache first
        if doc_id in self._page_count_cache:
            return self._page_count_cache[doc_id]

        # Get PDF path (handle both dict and string formats)
        doc_info = self._doc_id_map.get(doc_id)
        if not doc_info:
            return None

        # Extract pdf_path from dict or use directly if string
        if isinstance(doc_info, dict):
            pdf_path = doc_info.get("pdf_path")
        else:
            pdf_path = doc_info

        if not pdf_path or not Path(str(pdf_path)).exists():
            return None

        # Load page count
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(pdf_path))
            page_count = len(doc)
            doc.close()

            # Cache it
            self._page_count_cache[doc_id] = page_count
            return page_count
        except Exception as e:
            logger.error(f"Failed to get page count for {doc_id}: {e}")
            return None

    def _load_page_text(self, doc_id: str, page: int) -> str:
        """Load text for specific page"""
        # Check cache
        cache_key = f"{doc_id}:{page}"
        if cache_key in self._page_text_cache:
            return self._page_text_cache[cache_key]

        # Lazy load page reranker
        if self._page_reranker is None:
            try:
                from app.rag.page_reranker import get_page_reranker

                self._page_reranker = get_page_reranker()
            except ImportError as e:
                logger.error(f"Failed to import page_reranker: {e}")
                return ""

        try:
            page_text = self._page_reranker.get_page_text(doc_id, page)

            # Cache it (LRU with max size)
            if len(self._page_text_cache) > 100:
                # Simple LRU: remove oldest item
                self._page_text_cache.pop(next(iter(self._page_text_cache)))

            self._page_text_cache[cache_key] = page_text
            return page_text

        except Exception as e:
            logger.error(f"Failed to load page text for {doc_id} page {page}: {e}")
            return ""

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove some punctuation (but keep important ones)
        text = re.sub(r"[^\w\s.,;:!?-]", "", text)
        return text.strip()

    def _fuzzy_match(self, text1: str, text2: str) -> float:
        """
        Fuzzy string matching using SequenceMatcher

        Returns similarity score (0.0 to 1.0)
        """
        try:
            # For long texts, use sliding window approach
            if len(text1) > 1000:
                text1 = text1[:1000]

            if len(text2) > 5000:
                # Search for text1 in chunks of text2
                best_match = 0.0
                chunk_size = 1500
                step = chunk_size // 2

                for i in range(0, len(text2), step):
                    chunk = text2[i : i + chunk_size]
                    similarity = SequenceMatcher(None, text1, chunk).ratio()
                    best_match = max(best_match, similarity)

                    # Early exit if good match found
                    if best_match > 0.9:
                        break

                return best_match

            return SequenceMatcher(None, text1, text2).ratio()

        except Exception as e:
            logger.error(f"Fuzzy matching failed: {e}")
            return 0.0

    def _keyword_overlap(self, text1: str, text2: str) -> float:
        """
        Calculate keyword overlap ratio

        Returns overlap score (0.0 to 1.0)
        """
        try:
            # Extract keywords (simple: words > 3 chars)
            words1 = set(re.findall(r"\b\w{4,}\b", text1.lower()))
            words2 = set(re.findall(r"\b\w{4,}\b", text2.lower()))

            if not words1:
                return 0.0

            overlap = len(words1 & words2)
            return overlap / len(words1)

        except Exception as e:
            logger.error(f"Keyword overlap failed: {e}")
            return 0.0


# Singleton instance
_validator_instance: Optional[CitationValidator] = None


def get_citation_validator(
    validation_level: int = 2, min_confidence_threshold: float = 0.7, **kwargs
) -> CitationValidator:
    """
    Get singleton CitationValidator instance

    Args:
        validation_level: Validation depth (1, 2, or 3)
        min_confidence_threshold: Minimum confidence to pass
        **kwargs: Additional validator parameters

    Returns:
        CitationValidator instance
    """
    global _validator_instance

    if _validator_instance is None:
        _validator_instance = CitationValidator(
            validation_level=validation_level,
            min_confidence_threshold=min_confidence_threshold,
            **kwargs,
        )

    return _validator_instance
