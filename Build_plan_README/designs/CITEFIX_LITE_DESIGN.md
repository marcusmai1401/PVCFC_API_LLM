# CiteFix-lite Design Document

**Date**: 2025-01-03
**Status**: 📝 Design Phase
**Purpose**: Citation Validation System to prevent hallucinations and improve accuracy

---

## 🎯 OBJECTIVE

Build a **lightweight citation validator** that verifies:
1. **Doc_ID exists** in corpus
2. **Page number is valid** for that document
3. **Text actually exists** on the cited page
4. **Confidence scoring** for validation strength

---

## 🔍 VALIDATION REQUIREMENTS

### Must Validate
✅ **Doc_ID Existence**
- Verify doc_id exists in corpus
- Check against doc_id_map.json or BM25 index

✅ **Page Number Validity**
- Verify page number is within document range (1 to max_pages)
- Check actual page count from PDF metadata

✅ **Text Existence** (Critical)
- Verify that cited text/snippets actually appear on that page
- Use fuzzy matching for minor variations
- Check keyword overlap

✅ **Confidence Scoring**
- Calculate validation confidence (0.0 to 1.0)
- Based on: doc_id match, page validity, text similarity

### Optional Enhancements (Future)
- 🔮 LLM-based semantic validation
- 🔮 Cross-reference checking
- 🔮 Historical validation (track citation accuracy over time)

---

## 📊 VALIDATION LEVELS

### Level 1: Basic (Fast) ✅
- Doc_ID existence check
- Page number range check
- **Latency**: ~1-5ms per citation
- **Accuracy**: ~85%

### Level 2: Text Verification (Moderate) ✅
- Level 1 checks
- Keyword overlap checking
- Fuzzy text matching
- **Latency**: ~10-30ms per citation
- **Accuracy**: ~95%

### Level 3: Semantic (Slow) 🔮
- Level 2 checks
- LLM-based verification
- Semantic similarity checking
- **Latency**: ~100-500ms per citation
- **Accuracy**: ~98%

**Implementation**: Start with **Level 1 + Level 2**, Level 3 is future work.

---

## 🏗️ ARCHITECTURE

### Core Components

```
CitationValidator (Main Class)
├── validate(
│       doc_id: str,
│       page: int,
│       page_text: str,
│       snippets: List[Snippet],
│       query: Optional[str]
│   ) -> ValidationResult
├── validate_doc_id(doc_id: str) -> bool
├── validate_page_number(doc_id: str, page: int) -> bool
├── validate_page_text(doc_id: str, page: int, cited_page_text: str) -> float
├── validate_snippets(snippets: List[Snippet], actual_page_text: str) -> float
└── calculate_confidence(checks: Dict) -> float

ValidationResult (Dataclass)
├── is_valid: bool
├── confidence: float
├── errors: List[ValidationError]
├── checks: Dict[str, bool]
└── metadata: Dict[str, Any]

ValidationError (Dataclass)
├── error_type: ValidationErrorType
├── message: str
└── severity: ErrorSeverity

Note: Validator does NOT import CitationResult to avoid circular dependency.
Validation is called with primitive data from CitationRetriever.
```

---

## 🔧 DETAILED DESIGN

### 1. ValidationResult Dataclass

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

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
    WARNING = "warning"    # Possibly wrong
    INFO = "info"          # Minor issue

@dataclass
class ValidationError:
    """Single validation error"""
    error_type: ValidationErrorType
    message: str
    severity: ErrorSeverity
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationResult:
    """Result of citation validation"""
    is_valid: bool  # Overall validation status
    confidence: float  # Confidence score (0.0 to 1.0)
    errors: List[ValidationError] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)
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
            "errors": [
                {
                    "type": e.error_type,
                    "message": e.message,
                    "severity": e.severity,
                    "details": e.details
                }
                for e in self.errors
            ],
            "checks": self.checks,
            "metadata": self.metadata
        }
```

---

### 2. CitationValidator Class

```python
class CitationValidator:
    """
    Validates citations to prevent hallucinations

    Validates:
    - Doc_ID existence in corpus
    - Page number validity
    - Text/snippet existence on page
    """

    def __init__(
        self,
        validation_level: int = 2,  # 1=basic, 2=text, 3=semantic
        min_confidence_threshold: float = 0.7,
        text_match_threshold: float = 0.5,
    ):
        """
        Initialize validator

        Args:
            validation_level: Validation depth (1, 2, or 3)
            min_confidence_threshold: Minimum confidence to pass
            text_match_threshold: Minimum text similarity to pass
        """
        self.validation_level = validation_level
        self.min_confidence_threshold = min_confidence_threshold
        self.text_match_threshold = text_match_threshold

        # Load resources
        self._doc_id_map = self._load_doc_id_map()
        self._page_reranker = None  # Lazy load

    def validate(
        self,
        doc_id: str,
        page: int,
        page_text: str,
        snippets: List[Snippet] = None,
        query: Optional[str] = None,
    ) -> ValidationResult:
        """
        Main validation method (does NOT take CitationResult to avoid circular import)

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
            result.add_error(ValidationError(
                error_type=ValidationErrorType.DOC_NOT_FOUND,
                message=f"Document '{doc_id}' not found in corpus",
                severity=ErrorSeverity.CRITICAL,
                details={"doc_id": doc_id}
            ))
            result.confidence = 0.0
            result.checks = checks
            return result  # Early exit

        # Level 1: Page number check
        page_valid = self.validate_page_number(doc_id, page)
        checks["page_valid"] = page_valid

        if not page_valid:
            result.add_error(ValidationError(
                error_type=ValidationErrorType.INVALID_PAGE_NUMBER,
                message=f"Page {page} is invalid for document '{doc_id}'",
                severity=ErrorSeverity.CRITICAL,
                details={"page": page, "doc_id": doc_id}
            ))
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
                result.add_error(ValidationError(
                    error_type=ValidationErrorType.TEXT_NOT_FOUND,
                    message=f"Cited page text does not match actual page content",
                    severity=ErrorSeverity.WARNING,
                    details={"page_text_confidence": page_text_confidence}
                ))

            result.confidence *= page_text_confidence

        # Level 2: Snippet validation (if snippets provided)
        if self.validation_level >= 2 and snippets and actual_page_text:
            snippet_coverage = self.validate_snippets(snippets, actual_page_text)
            checks["snippets_valid"] = snippet_coverage > 0.5
            checks["snippet_coverage"] = snippet_coverage

            if snippet_coverage < 0.5:
                result.add_error(ValidationError(
                    error_type=ValidationErrorType.SNIPPET_MISMATCH,
                    message=f"Only {snippet_coverage:.0%} of snippets found on page",
                    severity=ErrorSeverity.WARNING,
                    details={"snippet_coverage": snippet_coverage, "snippet_count": len(snippets)}
                ))

            result.confidence *= (0.5 + snippet_coverage * 0.5)  # Boost based on coverage

        # Calculate final confidence
        result.confidence = self.calculate_confidence(checks)

        # Apply threshold
        if result.confidence < self.min_confidence_threshold:
            result.add_error(ValidationError(
                error_type=ValidationErrorType.LOW_CONFIDENCE,
                message=f"Validation confidence {result.confidence:.2%} below threshold",
                severity=ErrorSeverity.WARNING,
                details={"confidence": result.confidence, "threshold": self.min_confidence_threshold}
            ))

        result.checks = checks
        result.metadata = {
            "validation_level": self.validation_level,
            "doc_id": doc_id,
            "page": page,
            "snippet_count": len(snippets)
        }

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
        valid_count = 0

        for snippet in snippets:
            snippet_text = self._normalize_text(snippet.text)

            # Check if snippet exists in page (exact or fuzzy)
            if snippet_text in actual_normalized:
                valid_count += 1
            elif self._fuzzy_match(snippet_text, actual_normalized) > 0.8:
                valid_count += 0.8  # Partial credit for fuzzy match

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
            confidence *= (0.7 + checks["snippet_coverage"] * 0.3)

        return confidence

    def _load_doc_id_map(self) -> Dict[str, str]:
        """Load document ID to path mapping"""
        try:
            import json
            from pathlib import Path

            map_path = Path("artifacts/ingestion/doc_id_map.json")
            if map_path.exists():
                with open(map_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load doc_id_map: {e}")

        return {}

    def _get_page_count(self, doc_id: str) -> Optional[int]:
        """Get page count for document (with caching)"""
        # Check cache first
        if not hasattr(self, '_page_count_cache'):
            self._page_count_cache = {}

        if doc_id in self._page_count_cache:
            return self._page_count_cache[doc_id]

        # Get PDF path
        pdf_path = self._doc_id_map.get(doc_id)
        if not pdf_path or not Path(pdf_path).exists():
            return None

        # Load page count
        try:
            import fitz
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()

            # Cache it
            self._page_count_cache[doc_id] = page_count
            return page_count
        except Exception as e:
            logger.error(f"Failed to get page count: {e}")
            return None

    def _load_page_text(self, doc_id: str, page: int) -> str:
        """Load text for specific page"""
        if self._page_reranker is None:
            from app.rag.page_reranker import get_page_reranker
            self._page_reranker = get_page_reranker()

        try:
            return self._page_reranker.get_page_text(doc_id, page)
        except Exception as e:
            logger.error(f"Failed to load page text: {e}")
            return ""

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        import re
        # Lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove punctuation (optional)
        # text = re.sub(r'[^\w\s]', '', text)
        return text.strip()

    def _fuzzy_match(self, text1: str, text2: str, threshold: float = 0.5) -> float:
        """
        Fuzzy string matching

        Returns similarity score (0.0 to 1.0)
        """
        try:
            from difflib import SequenceMatcher

            # For long texts, sample to avoid performance issues
            if len(text1) > 1000:
                text1 = text1[:1000]
            if len(text2) > 5000:
                # Search for text1 in chunks of text2
                best_match = 0.0
                chunk_size = 1500
                for i in range(0, len(text2), chunk_size // 2):
                    chunk = text2[i:i + chunk_size]
                    similarity = SequenceMatcher(None, text1, chunk).ratio()
                    best_match = max(best_match, similarity)
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
            import re
            words1 = set(re.findall(r'\b\w{4,}\b', text1.lower()))
            words2 = set(re.findall(r'\b\w{4,}\b', text2.lower()))

            if not words1:
                return 0.0

            overlap = len(words1 & words2)
            return overlap / len(words1)

        except Exception as e:
            logger.error(f"Keyword overlap failed: {e}")
            return 0.0
```

---

## 🔗 INTEGRATION POINTS

### 1. CitationResult - NO CHANGES NEEDED

**Important**: We do NOT modify CitationResult dataclass to avoid circular imports.

Instead, validation results are stored in `citation.metadata['validation']`:

```python
# After validation in CitationRetriever:
citation.metadata['validation'] = validation_result.to_dict()

# Access validation:
if 'validation' in citation.metadata:
    is_valid = citation.metadata['validation']['is_valid']
    confidence = citation.metadata['validation']['confidence']
    errors = citation.metadata['validation']['errors']
```

**Benefits**:
- ✅ No circular import (CitationValidator doesn't import CitationResult)
- ✅ Backward compatible (existing code unaffected)
- ✅ Easy serialization (already a dict)
- ✅ Optional (only present if validation enabled)

---

### 2. Add to SearchConfig

```python
@dataclass
class SearchConfig:
    # Existing fields...

    # NEW: Validation settings
    enable_validation: bool = False  # Feature flag
    validation_level: int = 2  # 1=basic, 2=text, 3=semantic
    min_confidence_threshold: float = 0.7
    filter_invalid_citations: bool = False  # Remove invalid citations
```

---

### 3. Integrate into CitationRetriever

```python
class CitationRetriever:
    def __init__(self, ...):
        # Existing initialization
        self.validator = None  # Lazy load

    def search_with_citations(self, ...) -> List[CitationResult]:
        # Existing search logic
        citations = ...

        # NEW: Optional validation
        if config.enable_validation:
            citations = self._validate_citations(citations, config)

        return citations

    def _validate_citations(
        self,
        citations: List[CitationResult],
        config: SearchConfig
    ) -> List[CitationResult]:
        """Validate citations and attach results to metadata"""
        if self.validator is None:
            from app.rag.citation_validator import CitationValidator
            self.validator = CitationValidator(
                validation_level=config.validation_level,
                min_confidence_threshold=config.min_confidence_threshold
            )

        validated_citations = []

        for citation in citations:
            # Validate (pass primitives, not CitationResult)
            validation_result = self.validator.validate(
                doc_id=citation.doc_id,
                page=citation.page,
                page_text=citation.page_text,
                snippets=citation.snippets,
                query=None,  # Could pass query if available
            )

            # Store validation in metadata (not as field)
            citation.metadata['validation'] = validation_result.to_dict()

            # Filter if configured
            if config.filter_invalid_citations and not validation_result.is_valid:
                logger.warning(
                    f"Filtered invalid citation: {citation.doc_id} page {citation.page}, "
                    f"confidence={validation_result.confidence:.2%}"
                )
                continue

            validated_citations.append(citation)

        logger.info(
            f"Validated {len(citations)} citations, "
            f"{len(validated_citations)} passed (filtered: {len(citations) - len(validated_citations)})"
        )

        return validated_citations
```

---

## 📁 FILE STRUCTURE

```
app/rag/
├── citation_validator.py (NEW)
│   ├── ValidationErrorType (enum)
│   ├── ErrorSeverity (enum)
│   ├── ValidationError (dataclass)
│   ├── ValidationResult (dataclass)
│   └── CitationValidator (class)
│
├── citation_retriever.py (MODIFIED)
│   ├── CitationResult (extended with validation_result)
│   ├── SearchConfig (extended with validation settings)
│   └── CitationRetriever._validate_citations() (NEW method)
│
tests/
└── test_citation_validator.py (NEW)
    ├── test_validate_doc_id
    ├── test_validate_page_number
    ├── test_validate_text_existence
    ├── test_validation_confidence
    └── test_integration
```

---

## 🧪 TESTING STRATEGY

### Unit Tests
1. **test_validate_doc_id**: Valid/invalid doc_ids
2. **test_validate_page_number**: Valid/out-of-range pages
3. **test_validate_text_existence**: Exact match, fuzzy match, no match
4. **test_confidence_calculation**: Various check combinations
5. **test_error_handling**: Missing files, corrupt data

### Integration Tests
1. **test_validation_integration**: Full flow with CitationRetriever
2. **test_filter_invalid**: Verify filtering works
3. **test_backward_compatibility**: Existing code still works

### Real Data Tests
1. **test_with_real_citations**: Use actual query results
2. **test_performance**: Measure validation latency
3. **test_accuracy**: Manual verification of validation results

---

## 📊 EXPECTED METRICS

### Performance
- **Level 1 (basic)**: ~1-5ms per citation
- **Level 2 (text)**: ~10-30ms per citation
- **Batch of 10 citations**: ~50-300ms total

### Accuracy (Expected)
- **False Positive Rate**: <5% (valid citations marked invalid)
- **False Negative Rate**: <10% (invalid citations marked valid)
- **Overall Accuracy**: >90%

---

## ✅ ACCEPTANCE CRITERIA

1. ✅ CitationValidator class implemented with all methods
2. ✅ ValidationResult properly structured with errors
3. ✅ Integration into CitationRetriever with feature flag
4. ✅ Unit tests achieving >90% coverage
5. ✅ Performance within acceptable limits (<50ms per citation)
6. ✅ Backward compatibility maintained
7. ✅ Documentation complete

---

## 🚀 IMPLEMENTATION PLAN

### Phase 1: Core Implementation (1-1.5 hours)
1. Create citation_validator.py with dataclasses
2. Implement CitationValidator class
3. Add basic validation methods

### Phase 2: Integration (30 minutes)
1. Extend CitationResult
2. Update SearchConfig
3. Integrate into CitationRetriever

### Phase 3: Testing (30-45 minutes)
1. Write unit tests
2. Write integration tests
3. Test with real data

### Phase 4: Documentation (15 minutes)
1. Update docstrings
2. Create usage examples
3. Document validation rules

**Total Estimated Time**: 2-3 hours

---

## 📚 REFERENCES

- **Similar Systems**: CiteFix (research paper), FactScore
- **Dependencies**: PyMuPDF (fitz), difflib (fuzzy matching)
- **Related Modules**: page_reranker.py, citation_retriever.py

---

**Status**: ✅ Design Complete - Ready for Implementation
**Next Step**: Implement CitationValidator class
