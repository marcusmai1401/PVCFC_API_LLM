# CAD-like Gate: Image-based Features Implementation Plan

**Status:** DRAFT - Awaiting Approval
**Priority:** CRITICAL (Core classification accuracy)
**Created:** 2025-11-04
**Target Accuracy:** 96-98%

---

## 1. PROBLEM STATEMENT

### Current State
The CAD-like Gate (`app/ingestion/cadlike_gate.py`) successfully detects **vector-based CAD drawings** (score 0.559 for baseline P&ID Ammonia Unit) but **completely fails on scanned CAD drawings** (0% accuracy, 8/8 false negatives).

### Root Cause
**All 8 existing features rely on vector data or extractable text:**
- `producer_keyword` (20%): Requires PDF metadata → Scanned = 0
- `geometry_density` (15%): Requires vector paths → Scanned = 0
- `short_caps_rate` (15%): Requires text extraction → Scanned = 0
- `regex_3piece_hits` (20%): Requires text → Scanned = 0
- `technical_suffix` (10%): Requires text → Scanned = 0
- `non_a4_page` (5%): ✅ Works for scanned
- `multi_rotation` (5%): Requires text structure → Scanned = 0
- `leader_pattern` (10%): Requires vector lines → Scanned = 0

**Result:** Scanned CAD drawings score 0.000-0.050 (threshold: 0.55) → 100% false negatives

### Test Results
- **Baseline (P&ID Ammonia Unit - mixed vector/scanned):** Score 0.559 ✅
- **Negative cases (NOT CAD-like):** 3/3 correct (100% TN) ✅
- **Positive cases (scanned CAD drawings):** 0/8 correct (0% TP) ❌❌❌
- **Overall accuracy:** 27.3%

### Business Impact
**CRITICAL:** Misclassification of CAD drawings → Wrong OCR strategy → Tag extraction failure → 50% of project unusable

---

## 2. CURRENT ARCHITECTURE

### File Structure
```
app/ingestion/
├── cadlike_gate.py           # Main gate class (527 lines)
│   ├── CADLikeGate.__init__()
│   ├── evaluate() → GateDecision
│   ├── _select_sample_pages()
│   ├── 8x vector-based feature methods
│   └── _check_filename_keywords()
│
config/
└── cadlike_gate.yaml          # Configuration (61 lines)
    ├── weights: {...}         # 8 features, sum=1.0
    ├── thresholds: {...}      # cadlike: 0.55, gray_zone: 0.45
    └── gray_zone_keywords: [...]
```

### Current Evaluation Flow
```python
# app/ingestion/cadlike_gate.py:78-157
def evaluate(pdf_path, doc_metadata) -> GateDecision:
    1. Open PDF with PyMuPDF
    2. Sample pages: [0,1,2,mid,last]
    3. Compute 8 vector-based features
    4. Calculate weighted score (sum of features × weights)
    5. Classify:
       - score >= 0.55 → CAD-like
       - 0.45 <= score < 0.55 + filename keywords → CAD-like (boosted)
       - score < 0.45 → NOT CAD-like
    6. Select taggy pages if CAD-like
    7. Return GateDecision
```

### Integration Points
- **Called by:** `TagExtractionOrchestrator.process_document()` (line 102)
- **Used in:** P&ID tag extraction pipeline
- **Dependencies:** PyMuPDF, YAML config
- **Singleton:** `get_cadlike_gate()` factory

---

## 3. PROPOSED SOLUTION

### High-Level Strategy
**Hybrid Detection System:**
1. **Fast Path (Vector PDFs):** Use existing 8 features (~100ms) → If score ≥ 0.55, return CAD-like
2. **Accurate Path (Scanned PDFs):** Use image-based features (~1000ms) → If vector score < 0.20, analyze image

### Image-based Feature Set (3 features)

#### Feature 1: Shape Detection (40% weight)
**Purpose:** Detect circles (valves, instruments) and rectangles (equipment boxes)

**Method:**
- Hough Circle Transform for circles (valves, connection points)
- Contour detection + polygon approximation for rectangles
- Multi-scale detection:
  - Small circles (5-20px): Symbols
  - Medium circles (20-50px): Instruments
  - Large circles (50-100px): Equipment
- Rectangle validation: aspect ratio + size filtering

**Scoring:**
```python
circle_score = min(circle_count / 100, 1.0)
rectangle_score = min(rectangle_count / 300, 1.0)
shape_score = (circle_score + rectangle_score) / 2
```

**Performance:** ~300-400ms per page

#### Feature 2: Line Detection (30% weight)
**Purpose:** Detect piping, connections, dimension lines

**Method:**
- Canny edge detection
- Hough Line Transform (HoughLinesP)
- Filter long lines (>100 pixels)
- Count density

**Scoring:**
```python
line_score = min(long_lines / 500, 1.0)
```

**Performance:** ~200-300ms per page

#### Feature 3: Edge Density (30% weight)
**Purpose:** Measure drawing complexity

**Method:**
- Canny edge detection (threshold1=50, threshold2=150)
- Calculate edge pixel ratio

**Scoring:**
```python
edge_score = edge_pixels / total_pixels
normalized = min(edge_score / 0.25, 1.0)  # Cap at 25% edges
```

**Performance:** ~50-100ms per page

### Combined Scoring System

```python
# Vector-based score (existing)
vector_score = sum(weights[k] * features[k] for k in 8 features)

# Image-based score (new)
image_score = (
    0.40 * shape_score +
    0.30 * line_score +
    0.30 * edge_score
)

# Decision logic
if vector_score >= 0.55:
    return CAD-like (confidence=HIGH, method=VECTOR)
elif vector_score < 0.20:
    # Likely scanned PDF
    if image_score >= 0.80:
        return CAD-like (confidence=HIGH, method=IMAGE)
    elif 0.65 <= image_score < 0.80:
        # Gray zone - filename tie-breaker
        if has_cad_filename_keywords():
            return CAD-like (confidence=MEDIUM, method=HYBRID)
        else:
            return NOT CAD-like
    else:
        return NOT CAD-like (confidence=HIGH)
else:
    # Mixed PDF (0.20 <= vector_score < 0.55)
    combined = 0.60 * vector_score + 0.40 * image_score
    if combined >= 0.55:
        return CAD-like (confidence=MEDIUM, method=HYBRID)
    else:
        return NOT CAD-like
```

### Page Sampling Strategy (Accurate Mode)

**For documents > 20 pages:**
```python
sample = [
    0, 1, 2,              # First 3 pages (title, legend, TOC)
    mid-1, mid, mid+1,    # Middle pages (core content - highest CAD features)
    last-1, last          # Last pages (notes, appendix)
]
# Total: 8 pages sampled
```

**For documents 6-20 pages:**
```python
sample = [0, 1, 2, mid, last]  # 5 pages (current)
```

**For documents ≤ 5 pages:**
```python
sample = all pages
```

### Quality Checks

**Before image processing:**
```python
def check_page_quality(pixmap):
    img = pixmap_to_numpy(pixmap)

    # Check 1: Not blank (mean brightness < 250)
    if np.mean(img) > 250:
        return False, "blank_page"

    # Check 2: Not corrupted (mean brightness > 10)
    if np.mean(img) < 10:
        return False, "corrupted_page"

    # Check 3: Has variation (std > 5)
    if np.std(img) < 5:
        return False, "no_variation"

    return True, None
```

---

## 4. IMPLEMENTATION DETAILS

### 4.1 New Methods in CADLikeGate

```python
# app/ingestion/cadlike_gate.py

def _compute_image_features(self, doc, pages_to_sample):
    """Compute image-based features for scanned PDFs"""
    shape_scores = []
    line_scores = []
    edge_scores = []

    for page_idx in pages_to_sample:
        page = doc[page_idx]

        # Render page to image (300 DPI for accuracy)
        pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
        img = self._pixmap_to_numpy(pix)

        # Quality check
        is_valid, reason = self._check_page_quality(img)
        if not is_valid:
            logger.debug(f"Skipping page {page_idx}: {reason}")
            continue

        # Compute features
        shape_score = self._detect_shapes(img)
        line_score = self._detect_lines(img)
        edge_score = self._compute_edge_density(img)

        shape_scores.append(shape_score)
        line_scores.append(line_score)
        edge_scores.append(edge_score)

    # Average across valid pages
    return {
        'shape_detection': np.mean(shape_scores) if shape_scores else 0.0,
        'line_detection': np.mean(line_scores) if line_scores else 0.0,
        'edge_density': np.mean(edge_scores) if edge_scores else 0.0,
    }

def _detect_shapes(self, img):
    """Detect circles and rectangles using OpenCV"""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Detect circles
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT,
        dp=1, minDist=20,
        param1=50, param2=30,
        minRadius=5, maxRadius=100
    )
    circle_count = len(circles[0]) if circles is not None else 0

    # Detect rectangles
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    rectangles = 0
    for contour in contours:
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4:
            # Additional validation
            area = cv2.contourArea(contour)
            if 100 < area < 10000:  # Size filter
                x, y, w, h = cv2.boundingRect(approx)
                aspect_ratio = float(w) / h if h > 0 else 0
                if 0.2 < aspect_ratio < 5.0:  # Not too elongated
                    rectangles += 1

    # Normalize
    circle_score = min(circle_count / 100, 1.0)
    rectangle_score = min(rectangles / 300, 1.0)
    return (circle_score + rectangle_score) / 2

def _detect_lines(self, img):
    """Detect long straight lines using Hough Transform"""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi/180,
        threshold=50, minLineLength=30, maxLineGap=10
    )

    if lines is None:
        return 0.0

    # Count long lines
    long_lines = 0
    for line in lines:
        x1, y1, x2, y2 = line[0]
        length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
        if length > 100:
            long_lines += 1

    return min(long_lines / 500, 1.0)

def _compute_edge_density(self, img):
    """Compute Canny edge density"""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, threshold1=50, threshold2=150)

    edge_pixels = np.sum(edges > 0)
    total_pixels = edges.shape[0] * edges.shape[1]

    density = edge_pixels / total_pixels
    return min(density / 0.25, 1.0)  # Normalize to 25% cap

def _pixmap_to_numpy(self, pixmap):
    """Convert PyMuPDF pixmap to numpy array"""
    img = np.frombuffer(pixmap.samples, dtype=np.uint8)
    img = img.reshape(pixmap.height, pixmap.width, pixmap.n)
    if pixmap.n == 4:  # RGBA
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    return img

def _check_page_quality(self, img):
    """Check if page is suitable for image analysis"""
    mean_brightness = np.mean(img)
    std_dev = np.std(img)

    if mean_brightness > 250:
        return False, "blank_page"
    if mean_brightness < 10:
        return False, "corrupted_page"
    if std_dev < 5:
        return False, "no_variation"

    return True, None
```

### 4.2 Modified evaluate() Method

```python
def evaluate(self, pdf_path, doc_metadata=None):
    """Enhanced evaluation with hybrid vector + image detection"""

    doc = fitz.open(str(pdf_path))
    pages_to_sample = self._select_sample_pages(doc)

    # Step 1: Vector-based features (existing)
    vector_features = self._compute_vector_features(doc, pages_to_sample)
    vector_score = sum(self.weights[k] * vector_features[k] for k in self.weights.keys())

    # Step 2: Image-based features (new - conditional)
    image_features = {}
    image_score = 0.0
    detection_method = "VECTOR"

    if vector_score < 0.55:  # Not confidently CAD-like via vector
        logger.info(f"Vector score {vector_score:.3f} < 0.55, computing image features...")
        image_features = self._compute_image_features(doc, pages_to_sample)
        image_score = (
            0.40 * image_features['shape_detection'] +
            0.30 * image_features['line_detection'] +
            0.30 * image_features['edge_density']
        )
        logger.info(f"Image score: {image_score:.3f}")

    # Step 3: Classification logic
    is_cadlike, confidence, detection_method = self._classify_hybrid(
        vector_score, image_score, pdf_path
    )

    # Step 4: Select taggy pages
    taggy_pages = []
    if is_cadlike:
        taggy_pages = self._select_taggy_pages(doc)

    doc.close()

    return GateDecision(
        is_cadlike=is_cadlike,
        score=max(vector_score, image_score),  # Report highest score
        pages_sampled=pages_to_sample,
        taggy_pages=taggy_pages,
        features={**vector_features, **image_features},
        boosted_by_filename=(detection_method == "HYBRID"),
        confidence=confidence,
        detection_method=detection_method,
    )

def _classify_hybrid(self, vector_score, image_score, pdf_path):
    """Classify using hybrid logic"""

    # High confidence vector detection
    if vector_score >= 0.55:
        return True, "HIGH", "VECTOR"

    # Low vector score - check image features
    if vector_score < 0.20:
        if image_score >= 0.80:
            return True, "HIGH", "IMAGE"
        elif 0.65 <= image_score < 0.80:
            # Gray zone - filename tie-breaker
            if self._check_filename_keywords(pdf_path):
                return True, "MEDIUM", "HYBRID"
            else:
                return False, "MEDIUM", "IMAGE"
        else:
            return False, "HIGH", "IMAGE"

    # Mixed score - combine both
    combined = 0.60 * vector_score + 0.40 * image_score
    if combined >= 0.55:
        return True, "MEDIUM", "HYBRID"
    else:
        return False, "MEDIUM", "HYBRID"
```

### 4.3 Config Updates

```yaml
# config/cadlike_gate.yaml

# Add image-based feature weights
image_weights:
  shape_detection: 0.40    # Circles + rectangles
  line_detection: 0.30     # Long lines (piping)
  edge_density: 0.30       # Overall complexity

# Image processing settings
image_processing:
  render_dpi: 300          # Accuracy mode
  min_circle_radius: 5
  max_circle_radius: 100
  min_line_length: 30
  min_rectangle_area: 100
  max_rectangle_area: 10000
  canny_threshold1: 50
  canny_threshold2: 150

# Updated thresholds
thresholds:
  cadlike: 0.55              # Primary threshold (unchanged)
  gray_zone_low: 0.45        # Gray zone start (unchanged)
  gray_zone_boost_keywords: true

  # New image-based thresholds
  image_high_confidence: 0.80   # High confidence CAD-like
  image_gray_zone: 0.65         # Gray zone with filename boost
  vector_low_threshold: 0.20    # Trigger image analysis
```

### 4.4 Enhanced GateDecision Dataclass

```python
@dataclass
class GateDecision:
    is_cadlike: bool
    score: float
    pages_sampled: List[int]
    taggy_pages: List[int]
    features: Dict[str, float]
    boosted_by_filename: bool = False

    # New fields
    confidence: str = "UNKNOWN"  # HIGH, MEDIUM, LOW
    detection_method: str = "VECTOR"  # VECTOR, IMAGE, HYBRID
    image_features: Dict[str, float] = None  # Separate image feature dict
```

---

## 5. TESTING STRATEGY

### 5.1 Unit Tests

**Test file:** `tests/test_cadlike_gate_image.py`

```python
def test_shape_detection_scanned_pid():
    """Test shape detection on scanned P&ID"""
    # Should detect 50-200 circles, 100-500 rectangles

def test_shape_detection_text_document():
    """Test shape detection on text document"""
    # Should detect 0-5 circles, 10-50 rectangles

def test_line_detection_piping_drawing():
    """Test line detection on piping arrangement"""
    # Should detect 200-1000 long lines

def test_edge_density_cad_vs_text():
    """Test edge density distinguishes CAD from text"""
    # CAD: 15-30%, Text: 2-5%

def test_hybrid_classification_logic():
    """Test all branches of classification logic"""

def test_quality_checks():
    """Test blank/corrupted page filtering"""
```

### 5.2 Integration Test

**Baseline Verification:**
```python
# Test on baseline P&ID (score should remain 0.559 ± 0.05)
baseline_path = "D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf"
decision = gate.evaluate(baseline_path)
assert decision.is_cadlike == True
assert 0.50 <= decision.score <= 0.65
```

**Scanned CAD Test:**
```python
# Test on 8 scanned CAD drawings (should now detect)
for cad_file in scanned_cad_files:
    decision = gate.evaluate(cad_file)
    assert decision.is_cadlike == True
    assert decision.detection_method in ["IMAGE", "HYBRID"]
```

**Negative Cases:**
```python
# Test on 3 non-CAD documents (should remain NOT CAD-like)
for non_cad_file in non_cad_files:
    decision = gate.evaluate(non_cad_file)
    assert decision.is_cadlike == False
```

### 5.3 Performance Benchmark

**Target:**
- Vector path: < 200ms per file
- Image path: < 1500ms per file (8 pages × ~180ms/page)
- Overall: < 2000ms worst case

**Measurement:**
```python
def benchmark_gate_performance():
    times = {'vector': [], 'image': [], 'hybrid': []}

    for file_path in test_files:
        start = time.time()
        decision = gate.evaluate(file_path)
        elapsed = time.time() - start

        times[decision.detection_method.lower()].append(elapsed)

    # Report avg, min, max for each method
```

---

## 6. ROLLOUT PLAN

### Phase 1: Development & Unit Testing (2-3 days)
1. ✅ Research complete
2. ⏳ Implement `_detect_shapes()` method
3. ⏳ Implement `_detect_lines()` method
4. ⏳ Implement `_compute_edge_density()` method
5. ⏳ Implement `_compute_image_features()` wrapper
6. ⏳ Write unit tests for each method
7. ⏳ Verify on 2-3 sample files

### Phase 2: Integration & Logic (1-2 days)
8. ⏳ Modify `evaluate()` method with hybrid logic
9. ⏳ Update `_classify_hybrid()` decision tree
10. ⏳ Update `GateDecision` dataclass
11. ⏳ Update YAML config
12. ⏳ Integration tests

### Phase 3: Validation (1 day)
13. ⏳ Test on baseline (verify score unchanged)
14. ⏳ Test on 8 scanned CAD files (target 7-8 correct)
15. ⏳ Test on 3 non-CAD files (target 3 correct)
16. ⏳ Performance benchmark
17. ⏳ Parameter tuning if needed

### Phase 4: Production Deployment (1 day)
18. ⏳ Final code review
19. ⏳ Update documentation
20. ⏳ Deploy to production
21. ⏳ Monitor first 100 files

**Total Estimated Time:** 5-7 days

---

## 7. RISKS & MITIGATION

### Risk 1: Performance Degradation
**Impact:** High
**Probability:** Medium
**Mitigation:**
- Only run image features when vector_score < 0.55 (estimated 30% of files)
- Cache image processing results per page
- Use optimized OpenCV operations
- Parallel page processing

### Risk 2: False Positives on Complex Documents
**Impact:** Medium
**Probability:** Low
**Mitigation:**
- High thresholds (0.80 for image-based detection)
- Shape validation (size, aspect ratio filters)
- Combine multiple features (not just one)

### Risk 3: Parameter Sensitivity
**Impact:** Medium
**Probability:** Medium
**Mitigation:**
- Extensive testing on diverse file set (20+ files)
- Document parameter tuning process
- Make parameters configurable in YAML

### Risk 4: OpenCV Dependency Issues
**Impact:** Low
**Probability:** Low
**Mitigation:**
- OpenCV already installed (v4.6.0)
- No additional dependencies needed
- Fallback to vector-only mode on import error

---

## 8. SUCCESS METRICS

### Primary Metrics
- **Overall Accuracy:** Target ≥ 96% (currently 27.3%)
- **True Positive Rate (CAD detection):** Target ≥ 95% (currently 0%)
- **True Negative Rate (Non-CAD rejection):** Target ≥ 97% (currently 100%)
- **False Positive Rate:** Target ≤ 3%

### Performance Metrics
- **Vector path latency:** < 200ms (currently ~100ms)
- **Image path latency:** < 1500ms per file
- **99th percentile:** < 2000ms

### Quality Metrics
- **Baseline stability:** Score 0.559 ± 0.05 (no regression)
- **Confidence distribution:** ≥ 80% HIGH confidence decisions
- **Method distribution:** 70% vector, 25% image, 5% hybrid

---

## 9. ROLLBACK PLAN

### Trigger Conditions
- Overall accuracy drops below 80%
- Baseline score changes > 0.10
- Performance degrades > 500ms average
- Critical bugs in production

### Rollback Steps
1. Revert `cadlike_gate.py` to previous version
2. Revert `cadlike_gate.yaml` config
3. Clear any cached results
4. Notify stakeholders
5. Root cause analysis

### Rollback Time
- Estimated: < 30 minutes
- Testing required: Yes (baseline validation)

---

## 10. OPEN QUESTIONS

1. **Q:** Should we cache image feature results per file?
   **A:** TBD - depends on re-processing frequency

2. **Q:** What resolution (DPI) for image rendering?
   **A:** Propose 300 DPI for accuracy, benchmark 150 DPI for speed

3. **Q:** Should we add telemetry for feature debugging?
   **A:** Yes - log all feature scores for first 100 files

4. **Q:** Fallback behavior if image processing fails?
   **A:** Use vector-only classification + log warning

---

## 11. REFERENCES

### Code Files
- `app/ingestion/cadlike_gate.py` - Main implementation
- `app/ingestion/tags/orchestrator.py` - Integration point (line 102)
- `config/cadlike_gate.yaml` - Configuration

### Test Data
- Baseline: `D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf`
- Test results: `test_cadlike_results.json`
- Scanned CAD files: 8 files in `D:/Data_Raw/K06101_CO2 COMPRESSOR_HITACHI/.../Drawing/`
- Non-CAD files: 3 files in `D:/Data_Raw/`

### External Resources
- OpenCV Documentation: https://docs.opencv.org/4.6.0/
- Hough Circle Transform: https://docs.opencv.org/4.6.0/dd/d1a/group__imgproc__feature.html
- Canny Edge Detection: https://docs.opencv.org/4.6.0/da/d22/tutorial_py_canny.html

---

**END OF PLAN**

_This document will be updated as implementation progresses._
