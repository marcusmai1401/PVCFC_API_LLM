# CiteFix-lite Design - UPDATED SUMMARY

**Date**: 2025-01-03
**Status**: ✅ Design Reviewed & Updated
**Next**: Ready for Implementation

---

## 🔧 KEY FIXES APPLIED

### 1. ✅ Fixed Circular Import
**Problem**: Original design had CitationValidator import CitationResult, while CitationRetriever imports CitationValidator → circular dependency.

**Solution**:
- Validator uses **primitive types** only: `validate(doc_id, page, page_text, snippets, query)`
- Does NOT import CitationResult
- CitationRetriever passes data, receives ValidationResult

---

### 2. ✅ Fixed Validation Logic
**Problem**: Original `validate_text_existence()` compared `citation.page_text` with itself → always match, meaningless.

**Solution - Two-layer validation**:
```python
# Layer 1: Page text validation
validate_page_text(cited_page_text, actual_page_text_from_PDF)
→ Detects if LLM hallucinated page content

# Layer 2: Snippet validation
validate_snippets(snippets, actual_page_text_from_PDF)
→ Detects if snippets actually exist on page
→ Coverage score: ratio of valid snippets
```

**This catches**:
- LLM hallucinations
- Page reranker errors
- Snippet extractor bugs

---

### 3. ✅ Metadata Storage (No Dataclass Changes)
**Problem**: Adding `validation_result` field to CitationResult breaks backward compatibility.

**Solution**:
```python
# Store in metadata dict instead
citation.metadata['validation'] = {
    'is_valid': True,
    'confidence': 0.95,
    'errors': [...],
    'checks': {...}
}
```

**Benefits**:
- No circular import
- Backward compatible (existing code unaffected)
- Easy serialization
- Optional (only if validation enabled)

---

### 4. ✅ Performance Optimization
**Added**:
- Page count caching: `_page_count_cache[doc_id] = page_count`
- Avoids reopening PDFs repeatedly
- Chunked fuzzy matching for long texts
- Early exit on critical failures

---

## 📊 VALIDATION FLOW

```
CitationRetriever.search_with_citations()
    ↓
Create CitationResult[] (with snippets)
    ↓
IF enable_validation:
    ↓
    For each citation:
        ↓
        1. validator.validate(
              doc_id, page, page_text, snippets
           ) → ValidationResult
        ↓
        2. citation.metadata['validation'] = result.to_dict()
        ↓
        3. IF filter_invalid_citations AND not valid:
              Remove citation
    ↓
Return validated CitationResult[]
```

---

## 🎯 VALIDATION CHECKS

### Level 1: Basic (Fast ~1-5ms)
✅ **Doc ID exists** in corpus
✅ **Page number valid** (1 to page_count)

### Level 2: Text Verification (~10-30ms)
✅ **Page text matches** actual PDF content
✅ **Snippets exist** on actual page
✅ **Coverage score** (% of snippets found)

### Confidence Formula
```python
confidence = 1.0

if not doc_exists:
    return 0.0

if not page_valid:
    confidence *= 0.3

if page_text_confidence:
    confidence *= page_text_confidence

if snippet_coverage:
    confidence *= (0.7 + snippet_coverage * 0.3)

return confidence
```

---

## 🔧 API SIGNATURE

### CitationValidator.validate()
```python
def validate(
    self,
    doc_id: str,
    page: int,
    page_text: str,
    snippets: List[Snippet] = None,
    query: Optional[str] = None,
) -> ValidationResult
```

**No CitationResult dependency!**

---

## 📁 FILES TO CREATE/MODIFY

### NEW
1. `app/rag/citation_validator.py` (~500 lines)
   - ValidationErrorType (enum)
   - ErrorSeverity (enum)
   - ValidationError (dataclass)
   - ValidationResult (dataclass)
   - CitationValidator (class)

### MODIFIED
2. `app/rag/citation_retriever.py` (~30 lines added)
   - SearchConfig: add 4 validation fields
   - CitationRetriever: add `_validate_citations()` method
   - Integrate validation into `search_with_citations()`

### NEW
3. `tests/test_citation_validator.py` (~400 lines)
   - Unit tests for all validation methods
   - Integration tests with mocks
   - Real data tests

---

## ✅ ACCEPTANCE CRITERIA

1. ✅ No circular imports
2. ✅ Validates page_text against actual PDF
3. ✅ Validates snippets exist on page
4. ✅ Backward compatible (no breaking changes)
5. ✅ Feature flag (enable_validation, default OFF)
6. ✅ Performance <50ms per citation
7. ✅ Unit tests >90% coverage

---

## 🚀 READY FOR IMPLEMENTATION

**Estimated time**: 2-3 hours
- Phase 1: Create citation_validator.py (1.5h)
- Phase 2: Integrate into CitationRetriever (30min)
- Phase 3: Write tests (1h)

**Status**: ✅ Design approved, proceed with implementation!
