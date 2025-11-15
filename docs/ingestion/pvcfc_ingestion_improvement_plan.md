# PVCFC Ingestion Pipeline - Improvement Plan

**Status:** 🔄 In Progress
**Created:** 2025-11-03
**Last Updated:** 2025-11-03
**Owner:** AI Research Team

---

## 📋 Executive Summary

This living document tracks the comprehensive improvement plan for PVCFC RAG's ingestion pipeline, with particular emphasis on P&ID tag extraction quality, accuracy, and reliability.

### Current State
- **Dual Pipeline Architecture**: Auto-routing between Technical Doc and P&ID pipelines
- **OCR**: Google Cloud Vision API + Real-ESRGAN 2x upscaling
- **P&ID Features**: Geometric assembly, spatial component extraction, Level 2 search
- **Known Issues**: Classification brittleness, OCR over-invocation, tag extraction failures on rotated/multi-line tags

### Goals
1. Improve P&ID tag extraction F1 by **+15-30%**
2. Reduce unnecessary OCR invocations by **60-90%**
3. Enhance classification accuracy by **+5-10% F1**
4. Increase throughput by **2-5x**
5. Establish robust error handling and telemetry

---

## 🎯 Problem Statement

### Context
PVCFC RAG requires a robust, accurate, and performant ingestion pipeline for two main document corpora:
1. **Technical Documents** (text-first): Manuals, datasheets, specifications
2. **P&ID Drawings** (graphics-first): Piping & Instrumentation Diagrams

### Identified Issues

#### 1. PDF Processing & OCR
- **Issue**: Force-OCR on all P&ID pages regardless of vector text quality
- **Impact**: Wasted compute on born-digital PDFs (60-90% unnecessary)
- **Evidence**: `pdf_processor.py:602` - `force_ocr_all_pages=is_cad_like`

#### 2. Document Classification
- **Issue**: Quick filename-based classification may misroute documents
- **Impact**: P&ID pages processed as tech docs (missing tag extraction), or vice versa
- **Evidence**: `document_classifier.py` uses simple keyword matching

#### 3. P&ID Tag Extraction
- **Issue**: Brittle to rotations, multi-line tags, diverse drawing styles
- **Impact**: Low recall on non-standard P&IDs, split tags, missed rotated labels
- **Evidence**: `geometric_assembly.py` handles 3-4 part vertical tags only

#### 4. Spatial Component Extraction
- **Issue**: Level 2 indexing unclear, limited component types
- **Impact**: Missing context for RAG retrieval
- **Evidence**: `component_extractor.py` - basic pattern matching only

#### 5. Chunking Strategy
- **Issue**: Not optimized for heterogeneous sources
- **Impact**: Suboptimal retrieval granularity
- **Evidence**: Fixed 1000 char chunks regardless of document type

#### 6. Deduplication
- **Issue**: No near-duplicate detection
- **Impact**: Redundant indexing across minor revisions
- **Evidence**: `ingest.py:624-658` - content dedup commented out

#### 7. Performance
- **Issue**: Limited parallelization and caching
- **Impact**: Low throughput on large corpora
- **Evidence**: Max 4 workers, no intermediate caching

#### 8. Error Handling
- **Issue**: Basic quarantine, no structured telemetry
- **Impact**: Difficult triage and long-term monitoring
- **Evidence**: Simple quarantine.jsonl without correlation IDs

---

## 📊 Current Architecture Analysis

### Component Inventory

#### Core Ingestion Pipeline
```
tools/ingest.py (1627 lines)
├── PDF Processing
│   ├── app/ingestion/pdf_processor.py (600 lines)
│   │   ├── PyMuPDF text extraction
│   │   ├── Google Cloud Vision OCR
│   │   ├── Real-ESRGAN enhancement
│   │   └── Geometric assembly integration
│   └── app/ingestion/document_classifier.py
│       └── Quick filename-based classification
│
├── P&ID Pipeline (conditional: ENABLE_PID_TAGS=true)
│   ├── app/ingestion/cadlike_gate.py
│   │   └── 8-feature scoring (threshold ≥0.55)
│   ├── app/ingestion/tags/orchestrator.py
│   │   └── Coordinates tag extraction pipeline
│   ├── app/ingestion/tags/tag_extractor.py
│   │   └── CODE-anchored triplet assembly
│   ├── app/ingestion/geometric_assembly.py
│   │   └── Assembles tags from OCR fragments
│   └── app/rag/spatial/component_extractor.py
│       └── Level 2 component extraction
│
├── Chunking
│   └── app/rag/chunkers/hierarchical_chunker.py
│       └── 1000 chars, 200 overlap
│
└── Output
    ├── artifacts/ingestion_production/chunks/chunks.jsonl
    ├── artifacts/ingestion_production/entities/tags.jsonl
    └── OpenSearch: pvcfc_pid_spatial_components index
```

#### Configuration Files
- `.env` - Feature flags (ENABLE_PID_TAGS, GOOGLE_APPLICATION_CREDENTIALS)
- `config/cadlike_gate.yaml` - CAD-like Gate thresholds
- `config/tag_grammar.yaml` - Tag patterns

### Data Flow

#### Technical Doc Pipeline
```
PDF Input
  ↓
Quick Classification (filename-based)
  ↓ (score < 0.55)
PyMuPDF Text Extraction
  ↓
OCR Decision (vector text < 100 chars?)
  ↓ (if needed)
Google Vision OCR + Real-ESRGAN
  ↓
Hierarchical Chunking (1000/200)
  ↓
Output: chunks.jsonl
  ↓
Index: rag_chunks (BM25 + Weaviate)
```

#### P&ID Pipeline (Extended)
```
PDF Input
  ↓
Quick Classification (filename-based)
  ↓ (score ≥ 0.55)
CADLikeGate Evaluation (8 features)
  ↓ (if CAD-like)
Force OCR All Pages
  ↓
Real-ESRGAN 2x Enhancement
  ↓
Google Vision OCR
  ↓
Geometric Assembly (3-4 part vertical tags)
  ↓
Page Layout Extraction
  ↓
Tag Extraction (CODE-anchored)
  ↓
Spatial Component Extraction
  ↓
Chunking + Tag Indexing
  ↓
Output: chunks.jsonl + tags.jsonl
  ↓
Index: rag_chunks + pvcfc_pid_spatial_components
```

### Key Algorithms

#### 1. CAD-like Gate (8 Features)
**Location**: `app/ingestion/cadlike_gate.py`

Features with weights:
1. Producer keywords (AutoCAD, AVEVA, etc.) - weight unknown
2. Geometry density (vector paths/lines) - weight unknown
3. Short CAPS rate (2-4 letter tokens) - weight unknown
4. 3-piece tag regex hits - weight unknown
5. Technical suffixes (A/B/C, 2oo3) - weight unknown
6. Large page size (A1/A0) - weight unknown
7. Rotated text spans - weight unknown
8. Leader patterns - weight unknown

**Threshold**: score ≥ 0.55 → P&ID

#### 2. OCR Decision Logic
**Location**: `app/ingestion/pdf_processor.py:236-253`

```python
# Adaptive thresholds by document type
CAD_LIKE_TYPES = {"P&ID", "Drawing", "unknown"}

if document_type in CAD_LIKE_TYPES:
    OCR_CHAR_THRESHOLD = 1700  # P&ID
else:
    OCR_CHAR_THRESHOLD = 40    # Regular docs

should_ocr = enable_ocr and (
    force_ocr_all_pages or page_content.char_count < OCR_CHAR_THRESHOLD
)
```

**Issue**: Force-OCR on all P&ID pages ignores vector text quality

#### 3. Geometric Assembly
**Location**: `app/ingestion/geometric_assembly.py:203-291`

Handles:
- **3-part vertical**: `["29", "TE", "2003B"]` → `"29 TE 2003B"`
- **4-part vertical**: `["29", "TE", "2003", "B"]` → `"29 TE 2003B"`
- **Horizontal merged**: `"29TE2003B"` (single fragment)

Patterns:
```python
vertical_3part: r"^(\d{2})\s+([A-Z]{2,3})\s+(\d{4}[AB]?)$"
horizontal_3part: r"^(\d{2})[-\s]?([A-Z]{2,3})[-\s]?(\d{4}[AB]?)$"
horizontal_merged: r"^(\d{2})([A-Z]{2,3})(\d{4}[AB]?)$"
```

**Limitations**:
- No rotation handling (assumes 0°)
- No multi-line horizontal tags
- Fixed patterns (not extensible)

#### 4. Spatial Component Classification
**Location**: `app/rag/spatial/component_extractor.py:84-106`

```python
unit_pattern = r"^\d{1,2}$"              # e.g., "29", "04"
prefix_pattern = r"^[A-Z]{1,6}$"         # e.g., "TE", "PSAL"
suffix_pattern = r"^\d{3,5}[A-Z]?$"      # e.g., "2003B", "2207"
```

**Limitations**:
- Simple regex only
- No context-aware classification
- Excludes Vietnamese words (hardcoded list)

---

## 🎯 Proposed Improvements

### Priority Matrix

| Improvement | Impact | Effort | Priority | Sprint |
|-------------|--------|--------|----------|--------|
| CAD-like Gate enhancement | High | Medium | 🔴 P0 | Sprint 1 |
| Adaptive OCR cascade | High | Medium | 🔴 P0 | Sprint 1 |
| Tag extraction revamp | High | Medium | 🔴 P0 | Sprint 2 |
| Rotation handling | High | Medium | 🟡 P1 | Sprint 2 |
| Spatial graph assembly | High | High | 🟡 P1 | Sprint 3 |
| Disk caching | Medium | Low | 🟢 P2 | Sprint 4 |
| Structured telemetry | Medium | Medium | 🟢 P2 | Sprint 4 |
| Near-duplicate detection | Medium | High | 🔵 P3 | Future |

### Detailed Proposals

#### 1. Enhanced CAD-like Gate
**Status**: 🔜 Planned

**Changes**:
- Calibrate thresholds on labeled dataset
- Add feature importance analysis
- Implement confidence scores per feature
- Add page-level voting for doc-level label

**Expected Benefits**:
- +5-10% classification F1
- Reduced misroutes → less wasted compute

**Implementation**:
```python
# Proposed: app/ingestion/classifier/cad_gate_enhanced.py

def cad_like_score_v2(page_layout: PageLayout) -> Dict[str, float]:
    """Enhanced CAD-like scoring with feature breakdown"""
    scores = {
        'producer': check_producer_keywords(page_layout.metadata),
        'geometry_density': calculate_line_density(page_layout.drawings),
        'caps_rate': calculate_caps_ratio(page_layout.spans),
        'tag_regex_hits': count_tag_patterns(page_layout.spans),
        'technical_suffixes': detect_suffixes(page_layout.spans),
        'page_size': classify_page_size(page_layout.page_width, page_layout.page_height),
        'rotated_text': count_rotated_spans(page_layout.spans),
        'leaders': detect_leader_lines(page_layout.drawings)
    }

    # Calibrated weights (to be tuned on dataset)
    weights = {
        'producer': 0.15,
        'geometry_density': 0.20,
        'caps_rate': 0.10,
        'tag_regex_hits': 0.20,
        'technical_suffixes': 0.10,
        'page_size': 0.05,
        'rotated_text': 0.10,
        'leaders': 0.10
    }

    final_score = sum(scores[k] * weights[k] for k in scores)
    return {'score': final_score, 'features': scores}
```

#### 2. Adaptive OCR Cascade
**Status**: 🔜 Planned

**Changes**:
- Multi-signal OCR gate (not just char count)
- Per-page decision (not force-all)
- Confidence-based fallback chain

**Expected Benefits**:
- Reduce OCR invocations by 60-90% on born-digital PDFs
- +10% OCR confidence on scanned pages

**Implementation**:
```python
# Proposed: app/ingestion/pdf/ocr_gate.py

def needs_ocr_adaptive(page: fitz.Page, doc_type: str) -> Tuple[bool, str]:
    """Multi-signal OCR decision"""

    # Extract features
    vector_text = page.get_text()
    char_count = len(vector_text)
    drawings = page.get_drawings()
    images = page.get_images(full=True)

    # Feature scoring
    has_vector_text = char_count > 100
    has_graphics = len(drawings) + len(images) > 0
    text_quality = estimate_text_quality(vector_text)  # Check for garbled text

    # Decision tree
    if not has_vector_text and has_graphics:
        return True, "no_vector_text"

    if doc_type in {"P&ID", "Drawing"} and char_count < 1700:
        if text_quality < 0.7:  # Low quality vector text
            return True, "low_quality_vector"
        if has_graphics:  # Likely has embedded labels
            return True, "cad_with_graphics"

    if char_count < 40:
        return True, "scanned_page"

    return False, "sufficient_vector_text"
```

#### 3. Tag Extraction Revamp
**Status**: 🔜 Planned

**Changes**:
- Extensible pattern library
- Rotation handling (0/90/180/270°)
- Multi-line horizontal tags
- Confidence scoring per tag

**Expected Benefits**:
- +15-30% F1 on tag extraction
- Robust to rotated and multi-line tags

**Implementation**:
```python
# Proposed: app/ingestion/pid/tag_patterns.py

TAG_PATTERNS = {
    'isa_standard': re.compile(r'\b[A-Z]{1,4}[-/]?\d{2,5}[A-Z]?\b'),
    'numeric_prefix': re.compile(r'\b[A-Z]{1,3}\d{2,5}[A-Z]{0,2}\b'),
    'dashed_variant': re.compile(r'\b\d{2,5}-[A-Z]{1,3}-\d{1,3}\b'),
    'pvcfc_custom': [
        # To be populated based on actual corpus patterns
    ]
}

def normalize_tag(s: str) -> str:
    """Normalize tag string"""
    return s.upper().replace(' ', '').replace('_', '-')

# Proposed: app/ingestion/pid/rotation_handler.py

def extract_tags_with_rotation(ocr_response, img_bgr) -> List[AssembledTag]:
    """Try multiple rotations and keep best results"""

    tags_by_angle = {}

    for angle in [0, 90, 180, 270]:
        if angle > 0:
            rotated_img = rotate_image(img_bgr, angle)
            ocr_response_rotated = ocr_engine.ocr(rotated_img)
        else:
            ocr_response_rotated = ocr_response

        tags = geometric_assembler.extract_tags(ocr_response_rotated)
        tags_by_angle[angle] = tags

    # Select best based on confidence and pattern match
    return select_best_rotation(tags_by_angle)
```

#### 4. Spatial Graph Assembly
**Status**: 🔜 Planned (Sprint 3)

**Changes**:
- Detect lines (Hough), circles (bubbles), symbols
- Build typed graph: nodes (tags, instruments, valves) + edges (connected_to, near)
- Persist as JSON per page

**Expected Benefits**:
- Context-aware retrieval
- Better chunking boundaries

**Schema**:
```json
{
  "doc_id": "Ammonia_P&ID_04000",
  "page": 113,
  "nodes": [
    {
      "id": "tag:29_TE_2003B",
      "type": "tag",
      "bbox": [1688, 525, 32, 36],
      "text": "29 TE 2003B"
    },
    {
      "id": "instrument:I-29-001",
      "type": "instrument",
      "bbox": [1670, 500, 60, 60],
      "symbol": "circle"
    }
  ],
  "edges": [
    {
      "src": "tag:29_TE_2003B",
      "dst": "instrument:I-29-001",
      "type": "labels",
      "confidence": 0.92
    }
  ]
}
```

#### 5. Performance Optimization
**Status**: 🔜 Planned (Sprint 4)

**Changes**:
- Page-level parallelization with ProcessPoolExecutor
- Disk cache for intermediates (keyed by content hash)
- Reuse OCR engines across pages

**Expected Benefits**:
- 2-5x throughput increase

**Implementation**:
```python
# Proposed: app/ingestion/core/cache.py

from diskcache import Cache

cache = Cache('artifacts/cache/ingestion')

@cache.memoize(expire=86400*7)  # 7 days
def ocr_page_cached(page_hash: str, img_bytes: bytes) -> dict:
    """Cached OCR results"""
    return perform_ocr(img_bytes)

# Proposed: app/ingestion/core/executor.py

from concurrent.futures import ProcessPoolExecutor

def process_pages_parallel(pdf_path: Path, pages: List[int], max_workers: int = None):
    """Parallel page processing"""

    if max_workers is None:
        max_workers = os.cpu_count() - 1

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_single_page, pdf_path, page_num)
            for page_num in pages
        ]

        for future in as_completed(futures):
            yield future.result()
```

---

## 📈 Success Metrics

### Primary Metrics

| Metric | Baseline | Target | Measurement Method |
|--------|----------|--------|-------------------|
| P&ID Tag F1 | TBD | +15-30% | Labeled dataset evaluation |
| Classification F1 | TBD | +5-10% | P&ID vs Tech Doc accuracy |
| OCR Invocation Rate | ~100% on P&ID | -60-90% | OCR call logging |
| Throughput (pages/min) | TBD | +2-5x | End-to-end timing |
| Cache Hit Rate | 0% | ≥50% | Re-ingestion metrics |

### Secondary Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Rotation Robustness | Recall loss <5% | 0° vs 90°/270° |
| Quarantine Rate | <1% | After fixes |
| Structured Logging | 100% pages | With stage timing |

---

## 🗓️ Implementation Plan

### Sprint 0: Baseline & Mapping (1-2 days)
**Status**: 🔜 Not Started

**Tasks**:
- [ ] Complete repository inventory
- [ ] Build evaluation datasets (10-30 files each: technical + P&ID)
- [ ] Run baseline ingestion
- [ ] Capture metrics: timing, OCR calls, classification, tag extraction

**Deliverables**:
- `docs/ingestion/current_architecture.md` (this document evolved)
- `data/samples/manifests/{technical,pid}.jsonl`
- `logs/ingestion/baseline.jsonl`

### Sprint 1: Classification & OCR (3-5 days)
**Status**: 🔜 Not Started

**Tasks**:
- [ ] Implement enhanced CAD-like Gate
- [ ] Calibrate thresholds on dataset
- [ ] Implement adaptive OCR cascade
- [ ] Add rotation detection
- [ ] Add page-level caching

**Deliverables**:
- `app/ingestion/classifier/cad_gate_enhanced.py`
- `app/ingestion/pdf/ocr_gate.py`
- `app/ingestion/core/cache.py`
- Evaluation report: classification + OCR metrics vs baseline

### Sprint 2: Tag Extraction Revamp (5-7 days)
**Status**: 🔜 Not Started

**Tasks**:
- [ ] Implement extensible tag pattern library
- [ ] Add rotation handler
- [ ] Implement multi-line merge logic
- [ ] Add confidence scoring per tag
- [ ] Evaluate on labeled dataset

**Deliverables**:
- `app/ingestion/pid/tag_patterns.py`
- `app/ingestion/pid/rotation_handler.py`
- `app/ingestion/pid/tag_extractor_v2.py`
- Evaluation report: tag F1 vs baseline

### Sprint 3: Spatial Components (5-7 days)
**Status**: 🔜 Not Started

**Tasks**:
- [ ] Implement line/circle detection
- [ ] Build spatial graph (networkx)
- [ ] Define component index schema
- [ ] Implement P&ID chunker (zone/cluster)

**Deliverables**:
- `app/ingestion/pid/geometry.py`
- `app/ingestion/pid/graph.py`
- `app/ingestion/chunking/pid_chunker.py`
- Component index JSON examples

### Sprint 4: Dedup, Performance, Telemetry (3-5 days)
**Status**: 🔜 Not Started

**Tasks**:
- [ ] Implement file + content hash dedup
- [ ] Add parallel page processing
- [ ] Add structured telemetry (correlation IDs)
- [ ] Harden quarantine flows

**Deliverables**:
- `app/ingestion/dedup/pipeline.py`
- `app/ingestion/core/executor.py`
- `app/ingestion/core/logging.py`
- `app/ingestion/core/quarantine.py`
- Final evaluation report

---

## ⚠️ Risks & Mitigations

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| OCR variability across fonts/languages | High | Medium | Angle-aware OCR, adaptive binarization, fallback engines |
| P&ID diversity (symbol styles) | High | High | Heuristic-first + configurable templates, iterative pattern library |
| Performance regression | Medium | Medium | Caching, parallelization, stage-level timing, fail-fast gates |
| Grid/zone detection complexity | Medium | Low | Start cluster-based, add grid detection later |
| Near-duplicate false positives | Low | Medium | Conservative thresholds, manual review pipeline |

### Process Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Breaking existing interfaces | Medium | High | Feature flags via config, progressive rollout |
| Windows environment issues | Low | Medium | Cross-platform libraries, PowerShell-native commands |

---

## 📚 References

### Codebase
- Main ingestion: `tools/ingest.py`
- PDF processor: `app/ingestion/pdf_processor.py`
- CAD-like gate: `app/ingestion/cadlike_gate.py`
- Tag orchestrator: `app/ingestion/tags/orchestrator.py`
- Geometric assembly: `app/ingestion/geometric_assembly.py`
- Component extractor: `app/rag/spatial/component_extractor.py`

### Documentation
- `HUONG_DAN_INGESTION.md` - User guide
- `COMPLETE_PIPELINE_FLOW.md` - End-to-end flow
- `README.md` - System overview

### Configuration
- `.env` - Feature flags
- `config/cadlike_gate.yaml` - Gate thresholds
- `config/tag_grammar.yaml` - Tag patterns

---

## 📝 Change Log

### 2025-11-03
- ✅ Initial research and analysis completed
- ✅ TODO list created (27 tasks)
- ✅ Implementation plan document created
- 🔜 Next: Sprint 0 - Baseline evaluation

---

**Document Status**: 🟢 Active
**Next Review**: After Sprint 0 completion
