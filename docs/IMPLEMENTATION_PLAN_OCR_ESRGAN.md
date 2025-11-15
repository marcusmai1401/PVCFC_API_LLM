# Implementation Plan: OCR & Real-ESRGAN Enhancement Strategy

## Problem Statement

Current ingestion pipeline needs to be aligned with the following requirements:

1. **OCR always enabled during ingestion** - No option to disable
2. **Conditional OCR execution per page:**
   - CAD-like documents: OCR triggered when `char_count < 1700` per page
   - Non-CAD-like documents: OCR triggered when `char_count < 40` per page
3. **Real-ESRGAN enhancement:**
   - Enabled for CAD-like documents when OCR is needed
   - ALSO enabled for low DPI pages (<120 DPI) regardless of document type
4. **Simplified document classification:**
   - Only two categories: `CAD-like` vs `non-CAD-like`
   - Remove granular types (Drawing, Manual, Datasheet, etc.)
5. **Remove double processing:**
   - Current: Process document twice (once without OCR, once with OCR)
   - Required: Process document only ONCE with OCR enabled

---

## Current State Analysis

### 1. Document Classification (`app/ingestion/document_classifier.py`)

**Current Behavior:**
- Classifies into 15+ granular types: P&ID, Drawing, Manual, Technical Data, Procedure, Report, etc.
- Used in `tools/ingest.py` line 604: `quick_doc_type, _ = classifier.classify(pdf_path)`
- Used in `tools/ingest.py` line 611: `is_cad_like = quick_doc_type in {"P&ID", "Drawing", "unknown"}`

**Issues:**
- Too many document types when only need 2 categories
- Complexity in maintaining keyword patterns for 15+ types
- `is_cad_like` logic scattered across codebase

---

### 2. OCR Strategy (`tools/ingest.py` lines 600-650)

**Current Behavior:**
```python
# Line 614-622: Try without OCR first
processor = PDFProcessor(enable_ocr=False, ...)
pdf_doc = processor.process_pdf(pdf_path)

# Line 624-650: Conditionally enable OCR
total_text = "".join(page.text for page in pdf_doc.pages)
needs_ocr = self.enable_ocr and len(total_text.strip()) < 100

if self.enable_ocr and (is_cad_like or needs_ocr):
    processor = PDFProcessor(
        enable_ocr=True,
        force_ocr_all_pages=is_cad_like,  # Force for CAD
        document_type=quick_doc_type
    )
    pdf_doc = processor.process_pdf(pdf_path)  # Re-process entire document
```

**Issues:**
- ❌ `self.enable_ocr` can be False (user-controlled via `--enable-ocr` flag)
- ❌ Document processed **twice** (once without OCR, once with OCR)
- ❌ `force_ocr_all_pages=is_cad_like` overrides per-page thresholds
- ✅ Already has document_type-based thresholds in `pdf_processor.py` (1700 vs 40)

---

### 3. Per-Page OCR Logic (`app/ingestion/pdf_processor.py` lines 237-349)

**Current Behavior:**
```python
# Lines 252-261: Threshold determination
CAD_LIKE_TYPES = {"P&ID", "Drawing", "unknown"}

if self.document_type in CAD_LIKE_TYPES:
    OCR_CHAR_THRESHOLD = 1700  # CAD-like
else:
    OCR_CHAR_THRESHOLD = 40    # Regular docs

# Lines 263-265: OCR decision
should_ocr = self.enable_ocr and (
    self.force_ocr_all_pages or
    page_content.char_count < OCR_CHAR_THRESHOLD
)
```

**Current Logic:**
- ✅ Already has 1700/40 thresholds correctly
- ❌ But `force_ocr_all_pages=True` (set for CAD-like) bypasses threshold check
- ❌ Should use threshold instead of forcing all pages

---

### 4. Real-ESRGAN Enhancement (`app/ingestion/pdf_processor.py` lines 404-596)

**Current Behavior:**
```python
# Lines 535-556: Enhancement decision
CAD_LIKE_TYPES = {"P&ID", "Drawing", "unknown"}
should_enhance = (
    self.document_type in CAD_LIKE_TYPES or
    effective_dpi < 120  # Also enhance low DPI
)

if should_enhance:
    enhanced_bytes = self._enhance_image_realesrgan(img_bytes)
else:
    enhanced_bytes = img_bytes
```

**Current Logic:**
- ✅ Real-ESRGAN applied to CAD-like documents
- ⚠️ Also applied to low DPI (<120) regardless of type
- ✅ Model uses 2x upscale (line 471)
- ✅ Has memory safety checks (line 460)

**Status:**
- ✅ **KEEP low DPI condition** - User confirmed this is useful
- ✅ Already has both CAD-like and low DPI conditions

---

## Proposed Changes

### Change 1: Use Existing CADLikeGate Scorer

**File:** `tools/ingest.py`

**Action:** Use existing `CADLikeGate` scorer instead of simple document classifier

**Current (lines 600-611):**
```python
from app.ingestion.document_classifier import DocumentClassifier

classifier = DocumentClassifier()
quick_doc_type, _ = classifier.classify(pdf_path)
is_cad_like = quick_doc_type in {"P&ID", "Drawing", "unknown"}
```

**Proposed:**
```python
from app.ingestion.cadlike_gate import CADLikeGate

# Initialize gate scorer (once, not per file)
if not hasattr(self, '_cadlike_gate'):
    self._cadlike_gate = CADLikeGate()

# Evaluate with multi-feature scoring
gate_decision = self._cadlike_gate.evaluate(pdf_path)
is_cad_like = gate_decision.is_cadlike  # True if score >= 0.55
```

**CADLikeGate features (already implemented):**
- ✅ Producer/Creator keywords (AutoCAD, Bentley, etc.) - 20%
- ✅ Geometry density (vector paths/lines) - 15%
- ✅ Short CAPS tokens ("PV", "FT", "04") - 15%
- ✅ 3-piece tag regex ("04 PV 5012") - 20%
- ✅ Technical suffixes (A/B/C, 2oo3) - 10%
- ✅ Large page size (A1/A0) - 5%
- ✅ Rotated text - 5%
- ✅ Leader lines - 10%
- ✅ **Hybrid detection**: Image analysis fallback for scanned CADs

**Threshold:**
- Score >= 0.55 → CAD-like ✅
- Score < 0.55 → non-CAD-like
- Gray zone [0.45-0.55): Filename boost if has "P&ID", "Drawing", etc.

**Update locations:**
- `tools/ingest.py` line 604-611: Replace DocumentClassifier with CADLikeGate
- `app/ingestion/pdf_processor.py` line 252: Keep as is (still use "CAD-like" string)

---

### Change 2: Remove OCR Enable/Disable Option

**File:** `tools/ingest.py`

**Actions:**

1. **Remove `--enable-ocr` argument** (lines 1489-1493)
2. **Force `enable_ocr=True` always** (line 1667):
   ```python
   pipeline = IngestionPipeline(
       ...
       enable_ocr=True,  # Always enabled, no flag needed
       ...
   )
   ```
3. **Remove OCR check logic** (lines 1622-1650) - No longer needed

**File:** `launchers/run_full_ingestion.ps1`

**Action:** Remove OCR flag from script (already present, just documenting):
```powershell
# Line 17: Remove this variable
# $ENABLE_OCR = $true

# Lines 68-70: Remove this block
# if ($ENABLE_OCR) {
#     $args += "--enable-ocr"
# }
```

---

### Change 3: Remove `force_ocr_all_pages` Logic

**File:** `tools/ingest.py` lines 628-650

**Current:**
```python
if self.enable_ocr and (is_cad_like or needs_ocr):
    if is_cad_like and len(total_text.strip()) >= 100:
        logger.info(f"CAD-like file detected: Applying force OCR to {pdf_path.name}")

    processor = PDFProcessor(
        enable_ocr=True,
        force_ocr_all_pages=is_cad_like,  # ← Remove this
        document_type=quick_doc_type
    )
```

**Proposed:**
```python
# Always create processor with OCR enabled, no force flag
processor = PDFProcessor(
    enable_ocr=True,
    extract_tables=self.extract_tables,
    table_min_rows=self.table_min_rows,
    table_min_cols=self.table_min_cols,
    document_type="CAD-like" if is_cad_like else "non-CAD-like"
)
pdf_doc = processor.process_pdf(pdf_path)
```

**Key changes:**
- Remove double processing (no try without OCR first)
- Remove `force_ocr_all_pages` parameter completely
- Let per-page thresholds (1700/40) control OCR
- Pass simplified document type string

---

### Change 4: Update Per-Page OCR Thresholds

**File:** `app/ingestion/pdf_processor.py` lines 237-349

**Current:**
```python
CAD_LIKE_TYPES = {"P&ID", "Drawing", "unknown"}

if self.document_type in CAD_LIKE_TYPES:
    OCR_CHAR_THRESHOLD = 1700
else:
    OCR_CHAR_THRESHOLD = 40

should_ocr = self.enable_ocr and (
    self.force_ocr_all_pages or  # ← Remove this
    page_content.char_count < OCR_CHAR_THRESHOLD
)
```

**Proposed:**
```python
# Simplified: document_type is now "CAD-like" or "non-CAD-like"
if self.document_type == "CAD-like":
    OCR_CHAR_THRESHOLD = 1700
else:  # "non-CAD-like"
    OCR_CHAR_THRESHOLD = 40

# Simple threshold check, no force override
should_ocr = self.enable_ocr and (page_content.char_count < OCR_CHAR_THRESHOLD)
```

**Remove:**
- Line 97: `force_ocr_all_pages: bool = False` parameter
- Line 110: Documentation about force_ocr_all_pages
- Line 117: `self.force_ocr_all_pages = force_ocr_all_pages`
- Lines 268-271: Force OCR logging

---

### Change 5: Update Real-ESRGAN Logic (Keep Low DPI)

**File:** `app/ingestion/pdf_processor.py` lines 535-556

**Current:**
```python
CAD_LIKE_TYPES = {"P&ID", "Drawing", "unknown"}
should_enhance = (
    self.document_type in CAD_LIKE_TYPES or
    effective_dpi < 120  # Keep this!
)
```

**Proposed:**
```python
# Real-ESRGAN for CAD-like OR low DPI pages
should_enhance = (
    self.document_type == "CAD-like" or
    effective_dpi < 120  # ✅ KEEP - helps with poor quality scans
)

if should_enhance:
    if effective_dpi < 120:
        logger.info(
            f"Low DPI detected ({effective_dpi:.1f} < 120), applying Real-ESRGAN"
        )
    else:
        logger.debug(f"Applying Real-ESRGAN for CAD-like document")
    enhanced_bytes = self._enhance_image_realesrgan(img_bytes)
else:
    enhanced_bytes = img_bytes
    logger.debug(
        f"Skipped Real-ESRGAN (DPI={effective_dpi:.1f}, type={self.document_type})"
    )
```

**Changes:**
- ✅ Keep low DPI condition (effective_dpi < 120)
- Change CAD_LIKE_TYPES check to simple string comparison
- Update logging to be clearer

---

## Implementation Steps

### Step 1: Update Document Classifier
- [ ] Add `is_cad_like()` method to `DocumentClassifier`
- [ ] Update `tools/ingest.py` line 611 to use new method
- [ ] Remove unused granular type logic (optional cleanup)

### Step 2: Remove OCR Flag
- [ ] Remove `--enable-ocr` argument from argparse
- [ ] Force `enable_ocr=True` in pipeline initialization
- [ ] Update launcher script to remove OCR flag
- [ ] Remove OCR availability checks (lines 1622-1650)

### Step 3: Simplify PDF Processor
- [ ] Remove `force_ocr_all_pages` parameter from `__init__`
- [ ] Update `_process_page_with_ocr` to use thresholds only
- [ ] Change `document_type` to accept "CAD-like" / "non-CAD-like"
- [ ] Update Real-ESRGAN condition to CAD-like only

### Step 4: Remove Double Processing
- [ ] Delete lines 614-626 in `tools/ingest.py` (try without OCR)
- [ ] Keep only single PDFProcessor instantiation
- [ ] Remove `needs_ocr` variable

### Step 5: Testing
- [ ] Test CAD-like file (P&ID) → OCR on pages with <1700 chars
- [ ] Test non-CAD-like file (Manual) → OCR on pages with <40 chars
- [ ] Verify Real-ESRGAN only runs for CAD-like
- [ ] Check ingestion completes without errors

---

## Files to Modify

1. **`app/ingestion/document_classifier.py`**
   - Add `is_cad_like()` method

2. **`tools/ingest.py`**
   - Remove `--enable-ocr` argument (line ~1489)
   - Force `enable_ocr=True` (line ~1667)
   - Remove OCR checks (lines 1622-1650)
   - Remove double processing (lines 614-626)
   - Simplify processor instantiation (lines 641-650)
   - Update `is_cad_like` usage (line 611)

3. **`app/ingestion/pdf_processor.py`**
   - Remove `force_ocr_all_pages` parameter (lines 97, 110, 117)
   - Update threshold logic (lines 252-265)
   - Simplify Real-ESRGAN condition (lines 535-556)
   - Change document_type to binary string

4. **`launchers/run_full_ingestion.ps1`**
   - Remove `$ENABLE_OCR` variable
   - Remove OCR flag from command args

---

## Expected Behavior After Changes

### Ingestion Flow:
1. **Classify document** → CAD-like or non-CAD-like
2. **Create processor** with OCR always enabled
3. **Process each page:**
   - Extract vector text first
   - Check char_count against threshold (1700 or 40)
   - If below threshold → Run OCR
   - If CAD-like + OCR needed → Apply Real-ESRGAN
4. **Save results**

### Outcomes:
- ✅ OCR always available, no flag needed
- ✅ Per-page conditional OCR based on char thresholds
- ✅ Real-ESRGAN only for CAD-like documents needing OCR
- ✅ No double processing of documents
- ✅ Simplified classification (2 types instead of 15)

---

## Risk Assessment

**Low Risk:**
- Binary classification simpler than granular types
- Threshold logic already exists and works
- Real-ESRGAN restriction reduces unnecessary computation

**Medium Risk:**
- Removing double processing - need to verify no dependencies on vector-only pass

**Mitigation:**
- Test with sample CAD-like and non-CAD-like files
- Verify quarantine logic still works
- Check P&ID tag extraction still functions

---

## Notes

- Current code already has correct 1700/40 thresholds
- Real-ESRGAN code is robust with memory checks
- Main issue is `force_ocr_all_pages` bypassing thresholds
- Simplifying to 2 document types reduces maintenance
