# PVCFC RAG Pipeline - Accuracy Fixes Implementation Plan

**Date:** 2025-01-04
**Version:** 1.4.0 → 1.4.1
**Scope:** Fix 6 accuracy issues (C-2, C-3, H-4, H-5, M-3, M-4)
**Estimated Time:** ~5 hours total

---

## Overview

This plan addresses critical accuracy issues in the PVCFC RAG pipeline with minimal, focused fixes that prioritize correctness over complexity.

**Issues to Fix:**
1. **C-2:** Page metadata corruption in chunks (CRITICAL - breaks citations)
2. **C-3:** Confidence score underestimation (CRITICAL - user trust)
3. **H-4:** Spatial search defaults to "Ammonia" (HIGH - silent failures)
4. **H-5:** Citation regex missing [Doc X] format (HIGH - incomplete citations)
5. **M-3:** Table extraction not validated (MEDIUM - data quality)
6. **M-4:** Real-ESRGAN not applied to low DPI pages (MEDIUM - OCR quality)

**Excluded:**
- H-3: Geometric assembly tolerance (user deferred)
- M-2: BGE reranker model mismatch (needs A/B testing first, noted for future)
- M-1: Chunking overlap mid-sentence (low impact ~2-3%)
- C-1: Content deduplication (complex, deferred to future sprint)

---

## Issue C-2: Page Metadata Corruption (CRITICAL)

### Problem Statement
When chunking documents, chunks get wrong page numbers because the fallback logic uses `page_nums[0]` for all chunks, even those from later pages.

**Example:**
```
Document: 50 pages → 80 chunks
Chunk 1: page=1 ✓ CORRECT
Chunk 2: page=1 ✗ WRONG (actually from page 2)
Chunk 3: page=1 ✗ WRONG (actually from page 3)
...
```

**Impact:** ~40-60% of citations have wrong page numbers → User cannot verify answers → Trust broken.

### Current State

**File:** `app/ingestion/text_chunker.py`

**Current Logic (lines 457-517):**
```python
def chunk_document(self, document: Dict[str, Any], doc_id: Optional[str] = None):
    # Process each page
    pages = document.get("pages", [])
    for page in pages:
        page_num = page.get("page_num", 0)
        page_text = page.get("text", "")

        if page_text:
            # Chunk the page text
            page_chunks = self.chunk_text(
                text=page_text,
                doc_id=doc_id,
                metadata={
                    **doc_metadata,
                    "page": page_num,  # ✓ This is correct
                    "has_tables": bool(page_tables),
                },
                page_nums=[page_num],  # ✓ Single page passed
            )
            all_chunks.extend(page_chunks)
```

**Problem in chunk_text() (lines 161-169):**
```python
# CRITICAL FIX: Extract page number from chunk content first
content_page = extract_page_from_content(chunk_text)
if content_page is not None:
    chunk_metadata["page"] = content_page
# Fallback: If page_nums provided and page not in metadata, add it
elif page_nums and "page" not in chunk_metadata:
    chunk_metadata["page"] = page_nums[0]  # ← BUG: Always uses first page!
```

**Root Cause:** When metadata already has `"page"` from chunk_document(), this code path shouldn't execute. But if metadata is missing or overwritten, fallback uses `page_nums[0]`.

### Proposed Fix (Simple Approach)

**Strategy:** Ensure page metadata is ALWAYS passed correctly from chunk_document() and never use fallback.

**Changes to `text_chunker.py`:**

1. **In chunk_document() (line 499-508):** Remove `page_nums` parameter completely since we already pass `page` in metadata.

```python
# OLD:
page_chunks = self.chunk_text(
    text=page_text,
    doc_id=doc_id,
    metadata={
        **doc_metadata,
        "page": page_num,
        "has_tables": bool(page_tables),
    },
    page_nums=[page_num],  # ← REMOVE THIS
)

# NEW:
page_chunks = self.chunk_text(
    text=page_text,
    doc_id=doc_id,
    metadata={
        **doc_metadata,
        "page": page_num,  # Already passed, no need for page_nums
        "has_tables": bool(page_tables),
    },
    # page_nums removed
)
```

2. **In chunk_text() (lines 161-169):** Simplify logic - trust metadata["page"] always, remove fallback to page_nums[0].

```python
# OLD:
content_page = extract_page_from_content(chunk_text)
if content_page is not None:
    chunk_metadata["page"] = content_page
    logger.debug(f"Extracted page {content_page} from chunk content")
elif page_nums and "page" not in chunk_metadata:
    chunk_metadata["page"] = page_nums[0]  # ← REMOVE THIS FALLBACK

# NEW:
# If page not in metadata, extract from content markers as fallback
if "page" not in chunk_metadata:
    content_page = extract_page_from_content(chunk_text)
    if content_page is not None:
        chunk_metadata["page"] = content_page
        logger.debug(f"Extracted page {content_page} from chunk content")
    else:
        # Final fallback: page 1
        chunk_metadata["page"] = 1
        logger.warning(f"No page metadata found for chunk, defaulting to page 1")
# Page already in metadata, trust it
```

3. **Update chunk_text() signature (line 119):** Remove `page_nums` parameter.

```python
# OLD:
def chunk_text(
    self,
    text: str,
    doc_id: str,
    metadata: Optional[Dict] = None,
    page_nums: Optional[List[int]] = None,  # ← REMOVE
) -> List[TextChunk]:

# NEW:
def chunk_text(
    self,
    text: str,
    doc_id: str,
    metadata: Optional[Dict] = None,
) -> List[TextChunk]:
```

**Validation:** Add assertion that chunks have monotonically increasing page numbers (or at least non-decreasing).

```python
# In chunk_document(), after all_chunks.extend(page_chunks)
# Validate page numbers are correct
if len(all_chunks) > 1:
    prev_page = all_chunks[0].metadata.get("page", 0)
    for i, chunk in enumerate(all_chunks[1:], 1):
        curr_page = chunk.metadata.get("page", 0)
        if curr_page < prev_page:
            logger.warning(f"Page number decreased: chunk {i-1} page={prev_page} → chunk {i} page={curr_page}")
        prev_page = curr_page
```

**Files to Modify:**
- `app/ingestion/text_chunker.py` (lines 119, 161-169, 499-508, add validation)

**Testing:**
- Test chunking multi-page document (5+ pages)
- Verify all chunks have correct page numbers
- Verify no page number decreases (unless legitimate overlap)

**Estimated Time:** 2 hours (including testing)

---

## Issue C-3: Confidence Score Underestimation (CRITICAL)

### Problem Statement
Min-max rescaling maps high retrieval scores [0.85-0.91] → [0.0-1.0], causing the minimum score (0.85) to become 0.0, which drags down the average confidence to ~0.65 even though all scores are excellent.

**Example:**
```
Query: "What is pressure of tank T-101?"
Top 5 scores: [0.91, 0.90, 0.89, 0.87, 0.85] (all excellent!)
Rescaled: [1.0, 0.83, 0.67, 0.33, 0.0]
Average: 0.567 → Final confidence: 71.7% (after boosts)
SHOULD BE: ~90% (all scores > 0.85)
```

**Impact:** High-quality answers marked as "uncertain" → User distrust.

### Current State

**File:** `app/rag/generator.py`

**Current Logic (lines 157-250):**
```python
def _compute_calibrated_confidence(
    retrieval_results: List[RetrievalResult],
    citations: List["Citation"],
    answer_text: str,
    context_items: List[RetrievalResult],
    cfg: "GeneratorConfig",
    top_m: int = 5,
    length_threshold_chars: int = 200,
) -> Tuple[float, Dict[str, Any]]:
    # 1) Extract scores
    top = retrieval_results[:top_m]
    raw_scores = [best_score(x) for x in top]
    raw_scores = [s for s in raw_scores if s is not None]

    # 2) Rescale and compute base confidence
    rescaled = _rescale_scores(raw_scores)  # ← Problem: Always rescales
    base_conf = float(mean(rescaled)) if rescaled else 0.3

    # ... boosts and penalties ...
```

**Function _rescale_scores() (lines 104-154):**
```python
def _rescale_scores(
    raw_scores: List[float],
    method: str = "minmax",
    pct_low: float = 5.0,
    pct_high: float = 95.0,
) -> List[float]:
    if not raw_scores:
        return []
    if len(raw_scores) == 1:
        return [0.5]

    arr = raw_scores[:]
    min_v = min(arr)
    max_v = max(arr)
    range_v = max_v - min_v

    # Min-max rescaling
    if range_v > MINMAX_EPS:
        return [(s - min_v) / range_v for s in raw_scores]  # ← Always maps min→0, max→1

    # Fallback: percentile window
    # ...
```

### Proposed Fix (Simple Bypass)

**Strategy:** If all top scores are already high (≥ 0.80), skip rescaling and use raw scores directly.

**Changes to `generator.py`:**

**In _compute_calibrated_confidence() (after line 196):**

```python
# OLD:
rescaled = _rescale_scores(raw_scores)
base_conf = float(mean(rescaled)) if rescaled else 0.3

# NEW:
# If all scores are high, skip rescaling (trust raw scores)
if raw_scores and min(raw_scores) >= 0.80:
    base_conf = float(mean(raw_scores))
    components["base"] = round(base_conf, 4)
    components["note"] = "High-quality retrieval, no rescaling applied"
    logger.debug(f"High scores detected (min={min(raw_scores):.3f}), using raw average: {base_conf:.3f}")
else:
    # Standard rescaling for lower/mixed scores
    rescaled = _rescale_scores(raw_scores)
    base_conf = float(mean(rescaled)) if rescaled else 0.3
    components["rescaled_top_scores"] = rescaled
```

**Threshold Rationale:**
- 0.80 is a high absolute score (BM25 + Vector + Rerank)
- If minimum score ≥ 0.80, all top-5 are high quality
- Rescaling would artificially create 0.0-1.0 spread, harming confidence

**Files to Modify:**
- `app/rag/generator.py` (lines 196-207, add bypass logic)

**Testing:**
- Test with query that gets high scores (0.85+)
- Verify confidence ≥ 0.85 (not 0.65-0.75)
- Test with mixed scores (0.3-0.7) to ensure rescaling still works

**Estimated Time:** 30 minutes

---

## Issue H-4: Spatial Search Defaults to "Ammonia" (HIGH)

### Problem Statement
When user doesn't specify `doc_id` for spatial search, code defaults to "Ammonia" and continues → Silent failure if tag exists in different document.

**Example:**
```
User query: "Where is valve 29 PSV 2001A?"
User selects: query_type = "P&ID"
User does NOT select: specific document

Code: doc_id = "Ammonia" (default)
Result: Not found (valve is in "Urea Plant")
→ Silent failure!
```

**Impact:** 100% of multi-document queries without doc_id get wrong results.

### Current State

**File:** `app/rag/hybrid_with_tags_retriever.py`

**Current Logic (lines 112-153):**
```python
def _extract_doc_id(self, transformed_query: TransformedQuery, **kwargs) -> str:
    # Priority 1: From request object
    request = kwargs.get("request")
    if request and hasattr(request, "doc_id") and request.doc_id:
        return request.doc_id

    # Priority 2: From filters
    if transformed_query.filters and "doc_id" in transformed_query.filters:
        doc_ids = transformed_query.filters["doc_id"]
        if doc_ids:
            return doc_ids[0]

    # Priority 3: Default (with WARNING) ← PROBLEM
    default_doc_id = "Ammonia"
    logger.warning("⚠️  doc_id not specified, defaulting to 'Ammonia'")
    return default_doc_id  # ← Continues with wrong doc_id
```

### Proposed Fix (Option B: Search All Documents)

**Strategy:** When doc_id not specified, search ALL documents and aggregate results using RRF fusion.

**Changes to `hybrid_with_tags_retriever.py`:**

1. **Add get_all_doc_ids() method to SpatialComponentIndexer:**

**File:** `app/rag/spatial/component_indexer.py` (add after line 160)

```python
def get_all_doc_ids(self) -> List[str]:
    """Get list of all unique doc_ids in the index"""
    try:
        # Aggregation query to get unique doc_ids
        response = self.client.search(
            index=self.index_name,
            body={
                "size": 0,
                "aggs": {
                    "unique_docs": {
                        "terms": {
                            "field": "doc_id",
                            "size": 1000  # Max 1000 unique docs
                        }
                    }
                }
            }
        )

        doc_ids = [
            bucket["key"]
            for bucket in response["aggregations"]["unique_docs"]["buckets"]
        ]

        logger.debug(f"Found {len(doc_ids)} unique doc_ids in spatial index")
        return doc_ids

    except Exception as e:
        logger.error(f"Failed to get all doc_ids: {e}")
        return []
```

2. **Update _extract_doc_id() to return None instead of default:**

**File:** `app/rag/hybrid_with_tags_retriever.py` (lines 112-153)

```python
def _extract_doc_id(self, transformed_query: TransformedQuery, **kwargs) -> Optional[str]:
    """
    Extract doc_id from request context for Level 2 spatial search

    Returns:
        doc_id string if specified, None if not specified (triggers all-docs search)
    """
    # Priority 1: From request object
    request = kwargs.get("request")
    if request and hasattr(request, "doc_id") and request.doc_id:
        logger.debug(f"✓ Using doc_id from request: {request.doc_id}")
        return request.doc_id

    # Priority 2: From filters
    if transformed_query.filters and "doc_id" in transformed_query.filters:
        doc_ids = transformed_query.filters["doc_id"]
        if doc_ids:
            logger.debug(f"✓ Using doc_id from filters: {doc_ids[0]}")
            return doc_ids[0]

    # Priority 3: None (triggers all-docs search)
    logger.info("⚠️  doc_id not specified, will search all documents")
    return None  # ← Changed from "Ammonia"
```

3. **Update _search_with_tags() to handle None doc_id:**

**File:** `app/rag/hybrid_with_tags_retriever.py` (in _search_with_tags method, after line 250)

Find where spatial_searcher.search() is called, and wrap it:

```python
# OLD (example location):
spatial_results = self.spatial_searcher.search(unit, prefix, suffix, doc_id)

# NEW:
if doc_id is None:
    # Search all documents
    logger.info("Performing multi-document spatial search")
    all_doc_ids = self.spatial_searcher.indexer.get_all_doc_ids()

    if not all_doc_ids:
        logger.warning("No doc_ids found in spatial index")
        spatial_results = []
    else:
        logger.info(f"Searching {len(all_doc_ids)} documents: {all_doc_ids}")
        all_spatial_results = []

        for search_doc_id in all_doc_ids:
            try:
                results = self.spatial_searcher.search(unit, prefix, suffix, search_doc_id)
                all_spatial_results.extend(results)
            except Exception as e:
                logger.warning(f"Search failed for doc_id={search_doc_id}: {e}")
                continue

        # Sort by score and deduplicate
        all_spatial_results.sort(key=lambda r: r.score, reverse=True)
        spatial_results = all_spatial_results[:50]  # Top 50 from all docs

        logger.info(f"Multi-doc spatial search: {len(all_spatial_results)} results → top {len(spatial_results)}")
else:
    # Single document search (existing logic)
    spatial_results = self.spatial_searcher.search(unit, prefix, suffix, doc_id)
```

**Files to Modify:**
- `app/rag/spatial/component_indexer.py` (add get_all_doc_ids method)
- `app/rag/hybrid_with_tags_retriever.py` (lines 112-153, _search_with_tags logic)

**Testing:**
- Test query without doc_id → Should search all docs
- Test query with doc_id → Should search only that doc
- Verify results from correct documents

**Estimated Time:** 2 hours

---

## Issue H-5: Citation Regex Missing [Doc X] Format (HIGH)

### Problem Statement
Citation extraction regex only matches `[Doc X, p.Y]` format, missing `[Doc X]` format without page numbers.

**Example:**
```
LLM answer: "According to [Doc 1], the pressure is 150 psi [Doc 2, p.5]."
Current regex: r'\[Doc\s+(\d+),\s*p\.(\d+)\]'
Matched: [Doc 2, p.5] ✓
Missed: [Doc 1] ✗
→ Only 1 citation parsed instead of 2
```

**Impact:** ~10-15% citation recall loss (especially for overview answers without specific page refs).

### Current State

**File:** `app/rag/generator.py`

**Current Logic (lines 1300-1401):**
```python
def _extract_citations(
    self, answer: str, doc_mapping: Dict[int, RetrievalResult]
) -> List[Citation]:
    """Extract citations from answer text with enhanced page number support"""
    citations = []

    # Enhanced patterns for different citation formats
    patterns = [
        # [Doc X, p.Y] or [Doc X, page Y] or [Doc X, pp. Y-Z]
        r"\[Doc\s*(\d+)(?:,\s*(?:p\.?|page|pp\.)\s*(\d+)(?:[\-–](\d+))?)?\]",
        # Simple [X] format (footnote style)
        r"\[(\d+)\](?!\w)",
    ]

    seen_citations = set()

    for pattern in patterns:
        for match in re.finditer(pattern, answer, re.IGNORECASE):
            groups = match.groups()
            doc_num = int(groups[0])

            # Extract page number if present
            page_num = None
            if len(groups) > 1 and groups[1]:
                try:
                    page_num = int(groups[1])
                except (ValueError, TypeError):
                    page_num = None

            # ... rest of citation creation ...
```

**Analysis:** First pattern already supports optional page number with `(?:...)?)` but regex is correct. Need to verify if issue exists.

**Actually, pattern IS correct:**
- `(?:,\s*(?:p\.?|page|pp\.)\s*(\d+)(?:[\-–](\d+))?)?` - The final `?` makes entire group optional
- This SHOULD match both `[Doc 1]` and `[Doc 1, p.5]`

**WAIT - Let me re-examine the pattern:**

```regex
r"\[Doc\s*(\d+)(?:,\s*(?:p\.?|page|pp\.)\s*(\d+)(?:[\-–](\d+))?)?\]"
```

Breaking down:
- `\[Doc\s*(\d+)` - Match [Doc 1] ✓
- `(?:...) ?` - Optional group for page ✓
- Inside: `,\s*(?:p\.?|page|pp\.)\s*(\d+)` - Requires comma + "p." + number

**The pattern is CORRECT and should match both formats!**

Let me check if there's a different issue...

### Investigation Results

After examining the code at lines 1300-1401, the regex pattern **already supports both formats**:
- `[Doc 1]` → Matches with groups = (1, None, None)
- `[Doc 1, p.5]` → Matches with groups = (1, 5, None)

**The code handles this correctly at lines 1330-1336:**
```python
page_num = None
if len(groups) > 1 and groups[1]:
    try:
        page_num = int(groups[1])
    except (ValueError, TypeError):
        page_num = None
```

**Conclusion:** This may not be a real issue. The regex pattern is correct.

**However**, let me verify the actual issue by testing:

```python
import re

pattern = r"\[Doc\s*(\d+)(?:,\s*(?:p\.?|page|pp\.)\s*(\d+)(?:[\-–](\d+))?)?\]"
text = "According to [Doc 1], the pressure is 150 psi [Doc 2, p.5]."

for match in re.finditer(pattern, text, re.IGNORECASE):
    print(match.groups())

# Output:
# ('1', None, None)  ✓ Matches [Doc 1]
# ('2', '5', None)   ✓ Matches [Doc 2, p.5]
```

**Pattern works correctly!**

### Revised Assessment

**H-5 may be a non-issue.** The regex already supports both formats. The audit report may have been based on assumption rather than actual code examination.

**Recommendation:** Add unit test to verify both formats are parsed correctly, then close this issue.

**Test to Add (in test file):**

```python
def test_citation_extraction_both_formats():
    """Test that both [Doc X] and [Doc X, p.Y] formats are parsed"""
    generator = Generator()

    # Mock doc_mapping
    doc_mapping = {
        1: Mock(doc_id="doc1", page=10, source="test.pdf", score=0.9, metadata={}),
        2: Mock(doc_id="doc2", page=20, source="test2.pdf", score=0.8, metadata={}),
    }

    # Answer with both formats
    answer = "According to [Doc 1], the pressure is 150 psi [Doc 2, p.5]."

    citations = generator._extract_citations(answer, doc_mapping)

    assert len(citations) == 2
    assert citations[0].doc_id == "doc1"
    assert citations[0].page in [10, None]  # May use page from doc_mapping
    assert citations[1].doc_id == "doc2"
    assert citations[1].page == 5  # Explicit page from citation
```

**Files to Modify:**
- `tests/unit/test_generator.py` (add test)
- No code changes needed if test passes

**Estimated Time:** 30 minutes (add test + verify)

---

## Issue M-3: Table Extraction Not Validated (MEDIUM)

### Problem Statement
Tables extracted from PDFs are not validated for structure/quality before being injected into chunks. Invalid tables (missing cells, misaligned columns) may pollute context.

**Impact:** Incorrect data in retrieval context → Wrong answers for table-heavy queries.

### Current State

**File:** `app/ingestion/table_extractor.py`

**Current Logic (lines 94-149):**
```python
def extract_tables_from_page(self, page, page_num: int) -> List[TableData]:
    tables = []

    table_finder = page.find_tables(...)

    for table_index, table in enumerate(table_finder.tables):
        try:
            table_data = self._extract_table_data(table, page_num, table_index)

            # Validate table meets minimum requirements
            if self._is_valid_table(table_data):  # ← Already has validation!
                tables.append(table_data)
            else:
                logger.debug(f"Table {table_index} failed validation")
        except Exception:
            continue

    return tables
```

**Validation Logic (lines 290-320):**
```python
def _is_valid_table(self, table_data: TableData) -> bool:
    # Check minimum dimensions
    if table_data.row_count < self.min_rows:
        return False

    if table_data.col_count < self.min_cols:
        return False

    # Check if table has any content
    has_content = any(cell.strip() for row in table_data.cells for cell in row)

    if not has_content:
        return False

    return True
```

**Assessment:** Basic validation already exists (min rows/cols, content check).

**Missing Validations:**
1. Column consistency check (all rows same column count)
2. Header validation (first row should be headers)

### Proposed Fix (Enhanced Validation)

**Strategy:** Add column consistency check to existing _is_valid_table().

**Changes to `table_extractor.py`:**

**In _is_valid_table() (lines 290-320), add after content check:**

```python
def _is_valid_table(self, table_data: TableData) -> bool:
    # Check minimum dimensions
    if table_data.row_count < self.min_rows:
        logger.debug(f"Table rejected: row_count={table_data.row_count} < {self.min_rows}")
        return False

    if table_data.col_count < self.min_cols:
        logger.debug(f"Table rejected: col_count={table_data.col_count} < {self.min_cols}")
        return False

    # Check if table has any content
    has_content = any(cell.strip() for row in table_data.cells for cell in row)
    if not has_content:
        logger.debug("Table rejected: no content")
        return False

    # NEW: Check column consistency (all rows should have same column count)
    col_counts = [len(row) for row in table_data.cells]
    if len(set(col_counts)) > 1:
        logger.debug(f"Table rejected: inconsistent columns {col_counts}")
        return False

    # NEW: Check if first row looks like headers (not empty)
    if table_data.cells:
        first_row = table_data.cells[0]
        non_empty_headers = sum(1 for cell in first_row if cell.strip())
        if non_empty_headers < len(first_row) * 0.5:  # At least 50% headers non-empty
            logger.debug(f"Table rejected: weak header row ({non_empty_headers}/{len(first_row)} non-empty)")
            return False

    return True
```

**Files to Modify:**
- `app/ingestion/table_extractor.py` (lines 290-320, add validations)

**Testing:**
- Extract tables from test PDF
- Verify invalid tables (inconsistent columns, empty headers) are rejected
- Verify valid tables pass validation

**Estimated Time:** 1 hour

---

## Issue M-4: Real-ESRGAN Not Applied to Very Low DPI Pages (MEDIUM)

### Problem Statement
Real-ESRGAN upscaling is only applied for CAD-like documents during OCR, but doesn't check if page DPI is very low (< 100). Pages with 72-100 DPI may need upscaling even if document_type check passes.

**Impact:** OCR accuracy drops for very low DPI scanned P&IDs.

### Current State

**File:** `app/ingestion/pdf_processor.py`

**Current Logic (lines 459-520):**
```python
def _perform_ocr(self, page):
    # ... Vision API client init ...

    # Determine zoom factor based on page size
    if page_width < 600 or page_height < 800:
        zoom = 3  # ~216 DPI
    elif page_width > 1200 or page_height > 1600:
        zoom = 2  # ~144 DPI
    else:
        zoom = 2.5  # ~180 DPI

    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    img_bytes = pix.pil_tobytes(format="PNG")

    # Apply Real-ESRGAN ONLY for CAD-like documents
    CAD_LIKE_TYPES = {"P&ID", "Drawing", "unknown"}
    if self.document_type in CAD_LIKE_TYPES:
        enhanced_bytes = self._enhance_image_realesrgan(img_bytes)
    else:
        enhanced_bytes = img_bytes

    # ... OCR with enhanced_bytes ...
```

**Analysis:** Zoom factor is determined by page size (pts), not DPI. A very low DPI page (72 DPI) could still have large page size (1200+ pts).

**Issue:** No explicit DPI check. Need to detect actual page DPI and force higher rendering if too low.

### Proposed Fix (Add DPI Check)

**Strategy:** Detect page DPI, and if < 120 DPI, force render at 2x DPI (minimum 240 DPI).

**Changes to `pdf_processor.py`:**

**Add _get_page_dpi() helper method (after line 390):**

```python
def _get_page_dpi(self, page) -> float:
    """
    Estimate page DPI based on page dimensions

    PDF pages are measured in points (1/72 inch).
    If page is letter size (8.5x11 inch = 612x792 pts) and rendered at 72 DPI,
    the image is 612x792 pixels → 72 DPI.

    Default assumption: 72 DPI for PDF pages unless explicitly stored in metadata.
    """
    # Try to get DPI from page metadata (rarely available)
    try:
        # PyMuPDF doesn't store DPI metadata, assume 72 DPI as standard
        # Pages are vector by default, only scanned pages have "real" DPI
        # For safety, assume 72 DPI (PDF standard) unless proven otherwise
        return 72.0
    except Exception:
        return 72.0  # Default PDF DPI
```

**Note:** PDF pages are vector by default (no inherent DPI). DPI only matters when rendering to raster (pixmap). For scanned PDFs, the embedded image has DPI, but PyMuPDF doesn't expose it easily.

**Revised Strategy:** Instead of checking page DPI (not reliable), check **rendered pixmap size** vs **page size** to determine effective DPI, and upscale if too low.

**Better Implementation:**

**In _perform_ocr() (after line 488, before img_bytes = ...):**

```python
# Convert to PNG bytes
img_bytes = pix.pil_tobytes(format="PNG")

# Check effective DPI of rendered image
page_width_pts = page.rect.width
page_height_pts = page.rect.height
pixmap_width_px = pix.width
pixmap_height_px = pix.height

# Calculate effective DPI
effective_dpi_x = (pixmap_width_px / page_width_pts) * 72  # 72 pts per inch
effective_dpi_y = (pixmap_height_px / page_height_pts) * 72
effective_dpi = min(effective_dpi_x, effective_dpi_y)

logger.debug(f"Page rendered at {effective_dpi:.1f} DPI ({pixmap_width_px}x{pixmap_height_px} px)")

# Apply Real-ESRGAN if:
# 1. CAD-like document (existing logic)
# 2. OR very low DPI (< 120) regardless of document type
CAD_LIKE_TYPES = {"P&ID", "Drawing", "unknown"}
should_enhance = (
    self.document_type in CAD_LIKE_TYPES or
    effective_dpi < 120
)

if should_enhance:
    if effective_dpi < 120:
        logger.info(f"Low DPI detected ({effective_dpi:.1f}), applying Real-ESRGAN")
    enhanced_bytes = self._enhance_image_realesrgan(img_bytes)
else:
    enhanced_bytes = img_bytes
```

**Files to Modify:**
- `app/ingestion/pdf_processor.py` (lines 488-502, add DPI check logic)

**Testing:**
- Test with low DPI scanned PDF (< 120 DPI)
- Verify Real-ESRGAN is applied
- Test with normal DPI PDF (150+ DPI)
- Verify Real-ESRGAN is NOT applied (unless CAD-like)

**Estimated Time:** 30 minutes

---

## Testing Plan

### Phase 1: Unit Tests (2 hours)
1. **C-2:** Test chunking multi-page doc, verify page metadata
2. **C-3:** Test confidence calculation with high scores (0.85+)
3. **H-4:** Test spatial search with/without doc_id
4. **H-5:** Test citation extraction both formats (add test, verify passes)
5. **M-3:** Test table validation with invalid/valid tables
6. **M-4:** Test DPI detection and Real-ESRGAN triggering

### Phase 2: Integration Tests (1 hour)
1. Run full ingestion on 10-document subset
2. Verify:
   - Page numbers correct in chunks
   - Tables validated properly
   - Low DPI pages get Real-ESRGAN

### Phase 3: End-to-End Validation (1 hour)
1. Run 20 test queries (10 technical, 10 P&ID)
2. Measure:
   - Citation accuracy (page numbers)
   - Confidence scores (high queries should get 0.85+)
   - Multi-doc spatial search results

---

## Rollout Plan

### Step 1: Implementation (3-4 hours)
Fix issues in order:
1. C-3 (30 min) - Easiest, immediate impact
2. H-5 (30 min) - Add test, verify working
3. M-4 (30 min) - Simple DPI check
4. M-3 (1 hour) - Enhanced validation
5. H-4 (2 hours) - Multi-doc search logic
6. C-2 (2 hours) - Most complex, test thoroughly

### Step 2: Testing (2 hours)
Run all unit and integration tests

### Step 3: Deploy (1 hour)
1. Backup current code
2. Deploy changes to staging
3. Run smoke tests
4. Deploy to production

**Total Time:** ~5-7 hours

---

## Success Criteria

### Critical (Must Pass)
- ✅ C-2: 95%+ chunks have correct page numbers
- ✅ C-3: High-score queries (min ≥ 0.80) get confidence ≥ 0.85
- ✅ H-4: Multi-doc spatial search returns results from all docs
- ✅ M-3: Invalid tables rejected (0 false positives)

### High Priority (Should Pass)
- ✅ H-5: Both citation formats parsed (verified by test)
- ✅ M-4: Low DPI pages (<120) get Real-ESRGAN

### Metrics to Track
- Citation page accuracy: Target 95%+ (up from ~60%)
- Confidence calibration: High queries ≥ 0.85 (up from 0.65-0.75)
- Spatial search success rate: 100% for multi-doc queries
- Table extraction precision: ≥ 95% (reject invalid tables)

---

## Deferred Issues (Future Sprint)

### C-1: Content Deduplication (98% threshold too strict)
**Complexity:** Medium-High (2-3 hours)
**Impact:** +10-15% reduction in indexed chunks
**Reason for deferral:** Requires SequenceMatcher implementation + extensive testing with duplicate detection

### M-1: Chunking Overlap Mid-Sentence
**Complexity:** Low (1-2 hours)
**Impact:** +2-3% retrieval accuracy (minor)
**Reason for deferral:** Low impact, not worth effort now

### M-2: BGE Reranker Model Mismatch
**Complexity:** High (2 hours A/B test + 2 days fine-tuning)
**Impact:** ±0-5% accuracy (unknown direction)
**Reason for deferral:** Needs A/B testing first to determine if actual issue

### H-3: Geometric Assembly Tolerance
**Complexity:** Medium (2-3 hours)
**Impact:** +10-15% tag extraction recall
**Reason for deferral:** User deferred (not needed now)

---

## Approval Checklist

- [ ] User reviewed and approved fix approaches
- [ ] Estimated time acceptable (5-7 hours)
- [ ] Testing plan adequate (unit + integration + E2E)
- [ ] Success criteria clear and measurable
- [ ] Ready to proceed with implementation

**Please review and approve to begin implementation.**
