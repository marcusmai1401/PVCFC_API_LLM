# Complete Pipeline Flow - From Raw Data to User Query

**PVCFC RAG System - End-to-End Data Flow**
**Date:** 2025-12-04
**Version:** 2.0.0 (Deep Discovery Search + Intelligent Classification + Safety Quota + Page Metadata Fix + Gemini 3.0 Pro + Retrieval Optimization + HierarchicalChunker)

---

## 📖 Mục Lục

1. [Overview](#overview)
2. [PHASE 1: Ingestion Pipeline](#phase-1-ingestion-pipeline)
3. [PHASE 2: Indexing](#phase-2-indexing)
4. [PHASE 3: Query Processing](#phase-3-query-processing)
5. [Examples](#examples)

---

## Overview

### High-Level Flow

```
┌─────────────────┐
│   RAW PDF       │  D:\Data_Raw\
│   Documents     │  (P&ID, Manuals, Datasheets)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│             INGESTION PIPELINE                          │
│  - OCR (Google Vision + Real-ESRGAN)                   │
│  - Intelligent Classification (v2.0)                    │
│  - Chunking                                             │
│  - Tag Extraction (P&ID only)                          │
│  - Component Extraction (Level 2)                       │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│             INDEXED DATA (3 SYSTEMS)                     │
│  1. Weaviate: Vector embeddings (semantic search)       │
│  2. OpenSearch rag_chunks: BM25 + category/doc_type     │
│  3. OpenSearch spatial_components: Geometric proximity   │
└────────┬─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│   USER QUERY    │  UI: RAG Search / Deep Search / Document Explorer
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌─────────────────────────────────────────────┐
│ RAG    │  │ DEEP DISCOVERY SEARCH (v2.0)                │
│ Search │  │ - Keyword-based (no LLM/vector)             │
│        │  │ - Returns ALL documents (up to 10,000)      │
│        │  │ - Filter by category/doc_type               │
└────┬───┘  └────────────────┬────────────────────────────┘
     │                       │
     ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│   ANSWER        │    │   DOCUMENT LIST │
│   + Citations   │    │   by Category   │
└─────────────────┘    └─────────────────┘
```

### NEW v2.0: Intelligent Classification Flow

```
PDF Upload
    │
    ▼
┌─────────────────────────┐
│  Adaptive Page Sampler  │  ← Head-Body-Tail (10 pages max)
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│    CADLikeGate Check    │  ← P&ID Guardrail
└─────────────────────────┘
    │
    ├── score >= 0.55 ──► ENGINEERING_DESIGN / P&ID
    │
    └── score < 0.55
            │
            ▼
    ┌─────────────────────────┐
    │  Gemini 2.5 Flash AI    │  ← Multimodal Classification
    └─────────────────────────┘
            │
            ├── confidence >= 0.5 ──► Assigned Category/DocType
            │
            └── confidence < 0.5 ──► UNCATEGORIZED + NEEDS_REVIEW
```

---

## PHASE 1: Ingestion Pipeline

### Input

**Thư mục nguồn:** `D:\Data_Raw\`
**File types:** PDF documents (P&ID drawings, Technical manuals, Datasheets)

**Ví dụ:**
- `01. P&ID Ammonia Unit Rev12 (04000).pdf` (P&ID drawing)
- `Compressor Manual ABC-123.pdf` (Technical manual)
- `Valve Datasheet KT06101.pdf` (Datasheet)

### Command

```bash
python scripts/ingest_production.py

# Or manual parameters:
python tools/ingest.py \
  --source-dir "D:\Data_Raw" \
  --output-dir "D:\PVCFC_Artifacts\ingestion_production" \
  --enable-ocr \
  --enable-pid-tags \
  --workers 4
```

> **Note**: Production script `scripts/ingest_production.py` automatically uses `D:\PVCFC_Artifacts` from `.env` (ARTIFACTS_DIR).

---

### Step 1.1: File Discovery (v1.7.1)

```
Scan D:\Data_Raw\
    ↓
For each PDF file:
    ↓
    1.1a: Calculate file hash (SHA256)
         → Dùng cho logging & báo cáo (dedup_report.json), **không skip file** theo mặc định.
    ↓
    1.1b: Store file in processing queue
```

**Example:**
- `01. P&ID Ammonia.pdf` → hash: `a3f5b2...`
- `01. P&ID Ammonia Copy.pdf` → hash: `a3f5b2...` → **VẪN ĐƯỢC PROCESS** (dedup chỉ dùng cho thống kê/offline)

**Output:** List of all PDF files to process (no ingest-time skipping in v1.7.1)

---

### Step 1.2: Quick Document Classification

**Mục đích:** Xác định loại tài liệu TRƯỚC KHI xử lý → quyết định OCR strategy

```
For each PDF:
    ↓
    Quick Classification (based on filename):
        ↓
        Check filename keywords:
        - Contains "P&ID", "PID", "PFD", "ISO" → Type: "P&ID"
        - Contains "Drawing", "DWG" → Type: "Drawing"
        - Contains "Manual", "O&M" → Type: "Manual"
        - Contains "Datasheet", "Data Sheet" → Type: "Datasheet"
        - No keywords → Type: "unknown"
        ↓
        Result: quick_doc_type
        ↓
        Determine: is_cad_like
        → is_cad_like = quick_doc_type in {"P&ID", "Drawing", "unknown"}
```

**Ví dụ:**
- `01. P&ID Ammonia Unit Rev12.pdf` → quick_doc_type: **"P&ID"** → is_cad_like: **TRUE**
- `Compressor Manual ABC.pdf` → quick_doc_type: **"Manual"** → is_cad_like: **FALSE**

**⚠️ QUAN TRỌNG:** `quick_doc_type` quyết định:
- OCR threshold (1700 vs 40 chars)
- Force OCR all pages (có/không)
- Có chạy geometric assembly không

---

### Step 1.3: Text Extraction (Two-Pass Strategy)

#### **PASS 1: Vector Text First (Fast Check)**

```
Open PDF with PyMuPDF
    ↓
For each page:
    ↓
    Extract vector text (PDF native text)
    ↓
    Count characters
    ↓
Sum total_text from all pages
```

**Ví dụ P&ID:**
- Page 1: 245 chars (title page)
- Page 113: 1376 chars (diagram with annotations)
- **Total: 15,420 chars**

**Ví dụ Manual:**
- Page 1: 2340 chars
- Page 2: 3120 chars
- **Total: 125,000 chars**

#### **PASS 2: OCR Decision & Processing**

```
Check if OCR needed:
    ↓
    Decision logic:
    ├─ If is_cad_like AND total_text >= 100:
    │   → YES, FORCE OCR on all pages
    │   → Why: CAD files have small text annotations
    │
    └─ If total_text < 100:
        → YES, OCR (scanned document)
    ↓
If OCR needed:
    ↓
    Re-process với OCR enabled:
        ↓
        For each page:
            ↓
            Extract vector text first
            ↓
            Check ADAPTIVE THRESHOLD:
            ├─ CAD-like: If chars < 1700 → Need OCR
            └─ Regular: If chars < 40 → Need OCR
            ↓
            If need OCR:
                ↓
                1. Render page to PNG (adaptive DPI: 2-3x = 144-216 DPI)
                   ↓
                2. Real-ESRGAN 2x Enhancement (if CAD-like, GPU):
                   - Load model (RealESRGAN_x4plus_anime_6B.pth)
                   - Upscale 2x (2978x2105 → 5956x4210)
                   - Time: ~19.67s on RTX 4060
                   - Output size: ~5.8MB PNG
                   ↓
                3. Google Cloud Vision OCR:
                   - Send enhanced image to API
                   - Extract text + bounding boxes (fragments)
                   - Time: ~11.89s
                   ↓
                4. Geometric Assembly (if CAD-like):
                   - Parse OCR fragments (text + bbox)
                   - Find vertical/horizontal patterns
                   - Assemble tags: "29", "SG", "2201A" → "29 SG 2201A"
                   - Time: ~0.13s
                   ↓
                5. Combine Results:
                   - Vector text + OCR text + Assembled tags
                   - Total time: ~31.69s per page
```

**Ví dụ Page 113 (P&ID):**
```
Vector extraction: 1376 chars
  ↓ (< 1700 threshold)
OCR triggered:
  ↓
  Base image: 0.57MB
  ↓ Real-ESRGAN 2x
  Enhanced image: 5.81MB (19.67s)
  ↓ Google Vision
  OCR text: 2855 chars (11.89s)
  ↓ Geometric Assembly
  Assembled tags: 5 tags (0.13s)
  ↓
  Combined: 2972 chars total
  Total time: 31.69s
```

**Ví dụ Page 5 (Manual):**
```
Vector extraction: 3240 chars
  ↓ (> 40 threshold)
OCR NOT triggered (sufficient text)
  ↓
Use vector text: 3240 chars
Total time: 0.2s
```

---

### Step 1.4: Document Processing

```
For each PDF:
    ↓
    1.4a: Generate doc_id
         → Based on filename + metadata
         → Example: "Ammonia_P&ID_04000_v12"
    ↓
    1.4b: Full Document Classification
         → Re-classify with content analysis
         → Confirm: doc_type, revision number
         → Example: type="P&ID", revision="Rev12"
    ↓
         → Use character-index mapping to assign precise page numbers
         → Fixes page 31+ offset bug
         ↓
         → Each CHILD chunk has:
            - chunk_id: unique identifier
            - text: content text - INDEXED for retrieval
            - parent_id: ID of the heading chunk
            - metadata.chunk_type: "child"
            - metadata.page: precise page number from index map
         ↓
         → Example:
            Parent: "# 2. System Description"
              → Child 1: "The system consists of..." (linked to Parent)
              → Child 2: "Key components include..." (linked to Parent)
```

**Output:**
- `{ARTIFACTS_DIR}/ingestion_production/processed/{doc_id}_processed.json` (hiện tại: `D:\PVCFC_Artifacts\ingestion_production\processed`)
- `{ARTIFACTS_DIR}/ingestion_production/chunks/{doc_id}_chunks.jsonl` (hiện tại: `D:\PVCFC_Artifacts\ingestion_production\chunks`)

---

### Step 1.5: P&ID Tag Extraction (Conditional)

**Điều kiện:** `ENABLE_PID_TAGS=true` AND document is CAD-like

```
If is_cad_like:
    ↓
    1.5a: CADLikeGate Scoring
         ↓
         Analyze document features:
         - CAD metadata (AutoCAD, AVEVA...)
         - Geometry density (vector paths/lines)
         - Short CAPS tokens (PAL, PSAL, PT...)
         - 3-piece tag regex hits (04 TT 2020)
         - Technical suffixes (A/B, 2oo3...)
         - Page size (A0/A1 large format)
         - Rotated text
         - Leader lines
         ↓
         Calculate CAD score (0.0-1.0)
         ↓
         If score >= 0.55:
            → is_cadlike = TRUE
            → Continue tag extraction
         Else:
            → Skip tag extraction
    ↓
    1.5b: Select Taggy Pages
         ↓
         Scan all pages, select pages with:
         - >= 3 tag regex hits (e.g., "29 TE 2003B")
         - OR >= 4 CODE tokens (TE, PT, FT, etc.)
         ↓
         Result: List of taggy page indices
         Example: [2, 113, 117, 125] (0-based)
    ↓
    1.5c: Build Page Layouts
         ↓
         For each taggy page:
            ↓
            Extract text spans with:
            - text content
            - bbox [x0, y0, x1, y1]
            - font_size
            - rotation_deg
            - span_id (unique)
            ↓
            Extract vector drawings:
            - Lines, circles, rectangles
            - Coordinates, color, thickness
            ↓
            Save layout:
            → D:\PVCFC_Artifacts\layout\{doc_id}_p{page}_layout.json
    ↓
    1.5d: Extract Tags
         ↓
         For each page layout:
            ↓
            TagExtractor (CODE-anchored):
            - Find AREA (unit): 2-digit numbers
            - Find CODE (prefix): 2-6 letters (TT, PSAL, FIC...)
            - Find NUM (suffix): 3-5 digits + optional letter
            ↓
            Assemble vertical triplets:
            - AREA above CODE above NUM
            - Check alignment, spacing
            - Validate patterns
            ↓
            Attach suffixes:
            - A/B/C variants
            - 2oo3 voting logic
            ↓
            Exclude legend/notes regions
            ↓
            Result: List of TagEntity objects
            Example: "29 SG 2201A" with bbox=(1688, 525, 32, 36)
    ↓
    1.5e: Save Tags
         → D:\PVCFC_Artifacts\entities\tags.jsonl

         Format per line:
         {
           "tag": "29 SG 2201A",
           "doc_id": "Ammonia_P&ID_04000",
           "page": 113,
           "bbox": [1688, 525, 32, 36],
           "parts": {
             "unit": "29",
             "prefix": "SG",
             "suffix": "2201A"
           },
           "confidence": 0.95
         }
    ↓
    1.5f: Log Telemetry
         → D:\PVCFC_Artifacts\logs\tag_extraction_telemetry.jsonl

         Contains:
         - cadlike_score: 0.87
         - is_cadlike: true
         - taggy_pages: [113, 117, 125]
         - tags_found_total: 47
         - warnings: []
```

---

### Step 1.6: Component Extraction (Level 2 - NEW)

**Mục đích:** Extract individual components để support spatial proximity search

```
If is_cad_like AND tags extracted:
    ↓
    For each taggy page:
        ↓
        1.6a: Load saved PageLayout
             → Read from D:\PVCFC_Artifacts\layout\{doc_id}_p{page}_layout.json
        ↓
        1.6b: Extract Components
             ↓
             For each text span:
                ↓
                Classify span text:
                ├─ Matches ^\d{1,2}$ → component_type: "unit"
                ├─ Matches ^[A-Z]{1,6}$ → component_type: "prefix"
                └─ Matches ^\d{3,5}[A-Z]?$ → component_type: "suffix"
                ↓
                Create Component object:
                {
                  "text": "29",
                  "component_type": "unit",
                  "bbox": [1688, 525, 10, 12],
                  "page": 113,
                  "doc_id": "Ammonia_P&ID_04000",
                  "span_id": 1234
                }
        ↓
        1.6c: Bulk Index to OpenSearch
             → Index: pvcfc_pid_spatial_components
             → Fields: doc_id, page, component, component_type, bbox, center_x, center_y
        ↓
        1.6d: Track Statistics
             → spatial_components_indexed += count
```

**Ví dụ từ Page 113:**
```
Extracted components:
- "29" (unit) x 15 occurrences → 15 component records
- "SG" (prefix) x 4 occurrences → 4 component records
- "2201A" (suffix) x 2 occurrences → 2 component records
- "TE" (prefix) x 8 occurrences → 8 component records
...
Total: 247 components indexed for page 113
```

---

### Step 1.7: Finalization

```
1.7a: Create Manifests
     ↓
     - corpus.jsonl: All chunks (1 line per chunk)
     - documents.json: All documents metadata
     ↓
1.7b: Statistics
     ↓
     Print summary:
     - Total documents processed: 25
     - Total chunks created: 6758
     - Total P&ID tags: 347
     - Total spatial components: 12,450
     - Processing time: 4.5 hours
     ↓
1.7c: Version Snapshot (optional)
     ↓
     Create backup of:
     - Indices state
     - Artifacts directory
     - Manifests
     → Version: v1.2.0_level2_ocr
```

**Output Files:**
```
{ARTIFACTS_DIR}/ingestion_production/
├── chunks/
│   ├── Ammonia_P&ID_04000_chunks.jsonl       (247 chunks)
│   └── Compressor_Manual_ABC_chunks.jsonl    (89 chunks)
├── processed/
│   ├── Ammonia_P&ID_04000_processed.json
│   └── Compressor_Manual_ABC_processed.json
├── corpus.jsonl                               (All chunks)
└── documents.json                             (All docs metadata)

{ARTIFACTS_DIR}/
├── entities/
│   └── tags.jsonl                             (All P&ID tags)
├── layout/
│   ├── Ammonia_P&ID_04000_p113_layout.json
│   └── Ammonia_P&ID_04000_p117_layout.json
└── logs/
    └── tag_extraction_telemetry.jsonl
```

---

## PHASE 2: Indexing

### Automatic Indexing (During Ingestion)

Khi ingestion chạy, data tự động được index vào 3 systems:

#### 2.1: OpenSearch - Spatial Components

```
Component extractor → Bulk index
    ↓
Index: pvcfc_pid_spatial_components
    ↓
Each component record:
{
  "doc_id": "Ammonia_P&ID_04000",
  "page": 113,
  "component": "29",
  "component_type": "unit",
  "bbox": {"x0": 1688, "y0": 525, "x1": 1698, "y1": 537},
  "center_x": 1693,
  "center_y": 531,
  "span_id": 1234
}
```

**Purpose:** Level 2 spatial proximity search
**Query method:** Find all "29" units, all "SG" prefixes, all "2201A" suffixes → cluster by proximity

#### 2.2: OpenSearch - Chunks (BM25 Keyword)

```
Chunks from ingestion → Index to rag_chunks
    ↓
Each chunk record:
{
  "chunk_id": "Ammonia_P&ID_04000_chunk_0",
  "text": "29 SG 2201A steam generator...",
  "doc_id": "Ammonia_P&ID_04000",
  "page": 113,
  "metadata": {...}
}
```

**Purpose:** Keyword search (BM25 algorithm)
**Query method:** Match keywords in text

#### 2.3: Weaviate - Vector Embeddings (Semantic)

```
Chunks → Generate embeddings → Index to Weaviate
    ↓
Each chunk:
    ↓
    Text → Gemini embedding-001
    ↓
    Vector: [768 dimensions]
    ↓
    Store in Weaviate collection "Chunk"
```

**Purpose:** Semantic similarity search
**Query method:** Vector similarity (cosine distance)

---

### Post-Ingestion Indexing (One-Time Setup)

#### 2.4: OpenSearch - P&ID Tags (Legacy, Optional)

Nếu vẫn muốn giữ Level 3 indexed tags:

```bash
python scripts/opensearch/bulk_upsert_tags.py
```

Reads `tags.jsonl` → Indexes assembled tags to `pvcfc_pid_tags`

---

## PHASE 3: Query Processing

### User Query Flow

#### Step 3.1: User Input

**UI/Frontend:**
```
User enters query: "04 TT 2020"
User selects mode: [x] P&ID Search  [ ] Technical Doc

Optional: Specify document: "Ammonia"
```

**API Request:**
```json
{
  "query": "04 TT 2020",
  "query_type": "pid",
  "doc_id": "Ammonia",
  "max_context": 50,
  "language": "vi"
}
```

---

#### Step 3.2: Query Routing

```
API receives request
    ↓
    Check request.query_type:
    ├─ "pid" → Route to HybridWithTagsRetriever (Level 2)
    └─ "technical_doc" → Route to TechnicalDocRetriever (BM25+Vector)
```

**⚠️ QUAN TRỌNG:**
- User PHẢI chọn query_type từ UI
- Hệ thống KHÔNG tự động detect
- System trust user selection 100%

---

### FLOW A: P&ID Query (Level 2 Spatial Search)

**User chọn:** `query_type="pid"`

```
Query: "04 TT 2020"
    ↓
Step A1: Parse Tag Components
    ↓
    PIDQueryEnhancer.enhance("04 TT 2020")
        ↓
        Detect strategy: "component_search"
        ↓
        Extract components:
        {
          "unit": "04",
          "prefix": "TT",
          "suffix": "2020"
        }
    ↓
Step A2: Extract doc_id
    ↓
    Priority check:
    1. request.doc_id → "Ammonia" (if user specified)
    2. filters["doc_id"][0] → (if in filters)
    3. Default → "Ammonia"
    ↓
    Result: doc_id = "Ammonia"
    ↓
Step A3: Branch A - Spatial Proximity Search (Level 2)
    ↓
    Call: SpatialTagSearcher.search(
        unit="04",
        prefix="TT",
        suffix="2020",
        doc_id="Ammonia"
    )
    ↓
    ┌─────────────────────────────────────────┐
    │  LEVEL 2 SPATIAL CLUSTERING ALGORITHM   │
    └─────────────────────────────────────────┘

    3.1: Find Candidate Pages
         ↓
         Query OpenSearch components index:
         - Find pages with component="04" AND type="unit"
         - Find pages with component="TT" AND type="prefix"
         - Find pages with component="2020" AND type="suffix"
         ↓
         Intersection: Pages that have ALL 3 components
         Example: [Page 113, Page 117]

    3.2: For Each Candidate Page (e.g., Page 113)
         ↓
         Get all component occurrences:
         - "04" units: 15 occurrences with bboxes
         - "TT" prefixes: 8 occurrences with bboxes
         - "2020" suffixes: 3 occurrences with bboxes
         ↓
         Try ALL combinations:
         - (04₁, TT₁, 2020₁)
         - (04₁, TT₁, 2020₂)
         - (04₁, TT₂, 2020₁)
         - ... (15 × 8 × 3 = 360 combinations)
         ↓
         For each combination:
            ↓
            Calculate distances (in millimeters, not pixels!):
            - d(04, TT)
            - d(TT, 2020)
            - d(04, 2020)
            ↓
            Check if valid cluster:
            ├─ All distances < 25mm? → YES
            ├─ Vertically aligned (tolerance 5mm)? → YES
            ├─ Correct sequence (04 above TT above 2020)? → YES
            └─ Calculate quality score:
                score = proximity(0.4) + alignment(0.3) + sequence(0.3)
            ↓
            If score >= 0.6:
               → Valid cluster! Add to results

    3.3: Sort Results by Score
         ↓
         Best clusters first
         ↓
         Return: List of SearchResult objects
         Example:
         [
           SearchResult(
             page=113,
             doc_id="Ammonia",
             score=0.92,
             bbox=[326, 174, 27, 38],
             metadata={"tag_text": "04 TT 2020"}
           )
         ]
    ↓
Step A4: Branch B - Chunks Search (Parallel)
    ↓
    Standard hybrid search:
    - Weaviate vector search (Top 100 results, `WEAVIATE_RETRIEVAL_LIMIT=100`)
    - OpenSearch BM25 search (Top 200 results, `OPENSEARCH_RETRIEVAL_LIMIT=200`)
    - RRF fusion + BGE rerank (Top 50 results: `BGE_RERANK_TOP_K=50`, actual context: `MAX_CONTEXT=50`)
    ↓
    Returns: Chunks mentioning "04 TT 2020" semantically
    ↓
Step A5: RRF Fusion
    ↓
    Combine Branch A (spatial tags) + Branch B (chunks)
    ↓
    Reciprocal Rank Fusion:
    - Rank A results by score
    - Rank B results by score
    - Combine: RRF_score = 1/(k + rank_A) + 1/(k + rank_B)
    ↓
    Result: Unified ranked list
    ↓
Step A6: Reranking (Optional)
    ↓
    BGE CrossEncoder reranking
    ↓
    Top `max_context` results selected (default **50**, configurable 1-100)
    ↓
Step A7: Return Results
    ↓
    Results include:
    - Spatial tag matches (with exact bbox)
    - Related chunks (with context)
    - Page numbers
    - Bounding boxes for highlighting
```

**Example Result for "04 TT 2020":**
```json
{
  "results": [
    {
      "source": "spatial_level2",
      "doc_id": "Ammonia",
      "page": 113,
      "text": "04 TT 2020 - Temperature transmitter...",
      "bbox": [326, 174, 27, 38],
      "score": 0.92,
      "citation": "Page 113"
    },
    {
      "source": "chunks",
      "doc_id": "Ammonia",
      "page": 113,
      "text": "The temperature transmitter 04 TT 2020 monitors...",
      "score": 0.78,
      "citation": "Page 113, Section 4.2"
    }
  ]
}
```

---

### FLOW A.1: P&ID Tag Location Queries (Direct Answer Mode)

Một nhánh đặc biệt dùng cho truy vấn **hỏi vị trí tag P&ID** (ví dụ: `"04 ZSH 4326/A"`, `"Tag 04 ZSH 4326 nằm ở trang nào?"`).

```text
User Query: "04 ZSH 4326/A"
Mode: P&ID Search (query_type="pid")
    ↓
1. Detection in /ask router
    - `PIDTagHandler.detect_tag_query()` bắt các câu hỏi có "tag", "thiết bị", "trang/page", "ở đâu", "located", "found"...
    - Nếu không có từ khoá vị trí nhưng query rất ngắn (≤3 token) và `PIDQueryEnhancer.enhance()` parse được {unit, prefix, suffix}, hệ thống coi đây là **tag-only location query** (ví dụ: `"04 ZSH 4326/A"`).
    ↓
2. Dedicated P&ID retrieval for tag location
    - Router `/ask` chạy lại `HybridWithTagsRetriever` (hoặc `tags_retriever`) với `top_k` lớn (≈4×`max_context`, tối thiểu ~30) và filter `doc_category=["pid"]`.
    - Mục tiêu: đảm bảo danh sách kết quả **luôn chứa các hit thực sự có tag** (ví dụ page 89), kể cả khi BGE rerank ban đầu ưu tiên các trang text lân cận (85/86/102).
    ↓
3. PIDTagHandler.create_tag_location_answer(tag_name, retrieval_results)
    - Chuẩn hoá tag: "04 ZSH 4326/A" → "04 ZSH 4326".
    - Ưu tiên thứ tự nguồn:
      3.1. Các hit `source="tags"` (Level 2 spatial search) với bbox từ `pvcfc_pid_spatial_components`.
      3.2. Các hit text nơi tag xuất hiện trong nội dung (normal hoá bỏ khoảng trắng/gạch nối: `"04ZSH4326"`).
      3.3. Nếu cả hai đều không có, dùng top result làm best guess với cảnh báo trong answer.
    - Gom nhóm theo page, chọn 1–2 page có score cao nhất (ví dụ: page 89), sinh câu trả lời dạng: "Tag 04 ZSH 4326 xuất hiện ở [Doc 1, p.89] của tài liệu ...".
    ↓
4. Direct answer (no free-form LLM generation)
    - `/ask` đóng gói answer + citations và **không** gửi prompt sang LLM, tránh trường hợp LLM nói "không tìm thấy trong context" dù đã xác định được trang.
    - `confidence` được set cố định (vd 0.95) khi có hit rõ ràng.
```

**Text-only Tag Fallback (từ text PyMuPDF):**

- Nếu Level 2 spatial search không trả về cluster nào nhưng có `doc_id` cụ thể, `HybridWithTagsRetriever` dùng `TextTagDetector` để quét `text_by_page.jsonl` (text trích từ PyMuPDF từng trang P&ID).
- TextTagDetector sử dụng **full-window patterns** với số token gap nhỏ để nhận diện các chuỗi tương đương `"04 ZSH 4326"` ngay cả khi `04`, `ZSH`, `4326` bị tách rời trên dòng.
- Các hit này được convert thành kết quả với `source="text_tag_fallback"` và được `PIDTagHandler` xử lý giống như spatial hits → vẫn trả về đúng page cho truy vấn vị trí tag.

Kết quả: các truy vấn như `"04 ZSH 4326/A"` có thể trả về **đúng page P&ID thật sự chứa tag** (ví dụ page 89) với citations ổn định, không bị trộn với các trang lân cận chỉ chứa mô tả text.

---

### FLOW B: Technical Doc Query (Semantic Search)

**User chọn:** `query_type="technical_doc"`

```
Query: "How does the ammonia synthesis process work?"
    ↓
Step B1: Query Transformation
    ↓
    - Normalize text
    - Optional: HyDE (Hypothetical Document Embeddings)
      → Generate hypothetical answer
      → Use for better semantic matching
    ↓
Step B2: Parallel Retrieval
    ↓
    Branch 1: BM25 Keyword Search
    ├─ Query OpenSearch rag_chunks index
    ├─ Match keywords: "ammonia", "synthesis", "process"
    ├─ BM25 scoring
    └─ Top 200 results (v1.7.1 - OPENSEARCH_RETRIEVAL_LIMIT=200)

    Branch 2: Vector Semantic Search
    ├─ Query → Gemini embedding (768-dim vector)
    ├─ Query Weaviate for similar vectors
    ├─ Cosine similarity scoring
    └─ Top 100 results (v1.7.0 - WEAVIATE_RETRIEVAL_LIMIT=100)
    ↓
Step B3: RRF Fusion
    ↓
    Combine BM25 + Vector results
    ↓
    RRF_score = 1/(60 + rank_BM25) + 1/(60 + rank_Vector)
    ↓
    Sort by RRF score
    ↓
Step B4: Reranking + Safety Quota
    ↓
    1) Exact Match Guardrails (Safety Quota v1.7.1)
       • Detect special codes in query (KT06101, LS006343, E-04217...)
       • Extract ALL exact-match chunks from fused results
       • Sort by original BM25/RRF score (quality-first)
       • Keep **max 20** exact matches, boost score → 1.0
       • Đưa phần dư (21+) trở lại pool cho BGE rerank (semantic cứu các chunk nội dung điểm thấp)
    ↓
    2) BGE CrossEncoder reranking
       • Input: remaining candidates (sau khi tách exact matches)
       • Candidate pool: tối đa `BGE_RERANK_CANDIDATE_LIMIT=100`
       • Output: `BGE_RERANK_TOP_K=20` semantic-best chunks
    ↓
    3) Context selection
       • Merge: 20 exact matches (max) + BGE results → total pool cắt theo `MAX_CONTEXT=50`
       • Thực tế: tối đa **50 context chunks** được gửi vào LLM (v1.7.0+)
Step B5: Return Results
    ↓
    Results: Relevant chunks from manuals/datasheets
```

**Example Result:**
```json
{
  "results": [
    {
      "source": "vector",
      "doc_id": "Ammonia_Process_Manual",
      "page": 45,
      "text": "The ammonia synthesis process utilizes...",
      "score": 0.89,
      "citation": "Ammonia Process Manual, Page 45"
    },
    {
      "source": "bm25",
      "doc_id": "Technical_Specification",
      "page": 12,
      "text": "Ammonia is synthesized through the Haber-Bosch...",
      "score": 0.82,
      "citation": "Technical Specification, Page 12"
    }
  ]
}
```

---

### Step 3.3: Answer Generation

**Chung cho cả P&ID và Technical Doc:**

```
Retrieved context chunks
    ↓
Step 3.3a: Context Preparation
    ↓
    Format context for LLM:
    """
    Context 1 (Page 113, Ammonia P&ID):
    04 TT 2020 - Temperature transmitter...

    Context 2 (Page 113, Ammonia P&ID):
    The temperature transmitter monitors inlet temperature...

    [... up to 50 contexts (MAX_CONTEXT=50, configurable)]
    """
    ↓
Step 3.3b: LLM Generation
    ↓
    Prompt template:
    """
    Based on the following context, answer the question.

    Context:
    {formatted_contexts}

    Question: {user_query}

    Answer in Vietnamese. Include citations.
    """
    ↓
    Send to Gemini 2.5 Pro (heavy tier)
    ↓
    Receive structured answer with citations
    ↓
Step 3.3c: Post-Processing
    ↓
    - Extract citations
    - Match citations to source chunks
    - Add page numbers
    - Add bounding boxes (for P&ID results)
    - Calculate confidence score
    ↓
Step 3.3d: Return Final Answer
```

**Example Final Answer:**

```json
{
  "answer": "Transmitter nhiệt độ 04 TT 2020 được sử dụng để đo nhiệt độ đầu vào của reactor tổng hợp ammonia...",
  "confidence": 0.92,
  "citations": [
    {
      "text": "04 TT 2020 - Temperature transmitter",
      "doc_id": "Ammonia",
      "page": 113,
      "bbox": [326, 174, 27, 38],
      "source": "spatial_level2"
    },
    {
      "text": "The temperature transmitter monitors...",
      "doc_id": "Ammonia",
      "page": 113,
      "source": "chunks"
    }
  ],
  "query_type": "pid",
  "search_method": "Level 2 Spatial Clustering"
}
```

---

## Examples

### Example 1: P&ID Tag Search

**User Action:**
- Query: "29 SG 2201A"
- Mode: P&ID Search
- Doc: "Ammonia" (optional)

**System Processing:**
```
1. Parse: unit=29, prefix=SG, suffix=2201A
2. Search spatial components in "Ammonia" doc
3. Find pages with all 3 components
4. Try combinations, find clusters
5. Best match: Page 113, score=0.95, bbox=[1688, 525, 32, 36]
6. Also search chunks for context
7. Fusion results
8. Generate answer: "Tag 29 SG 2201A là steam generator tại page 113..."
```

**Response time:** ~3-5 seconds
- Spatial search: ~200ms
- Chunks search: ~100ms
- Fusion + Generation: ~2-4s

---

### Example 2: Technical Question

**User Action:**
- Query: "Áp suất vận hành tối đa của compressor là bao nhiêu?"
- Mode: Technical Doc Search

**System Processing:**
```
1. Transform query (optional HyDE)
2. BM25 search: keywords "áp suất", "vận hành", "tối đa", "compressor"
3. Vector search: semantic similarity
4. RRF fusion of both
5. Rerank top candidates
6. Generate answer từ top `max_context` chunks (default **50**, up to 100 configurable)
```

**Response time:** ~2-3 seconds
- BM25: ~50ms
- Vector: ~80ms
- Fusion + Generation: ~2s

---

### Example 3: Suffix-Only Query (Limitation)

**User Action:**
- Query: "5153"
- Mode: P&ID Search

**System Processing:**
```
1. Parse: suffix=5153 (no unit, no prefix)
2. Strategy: "suffix_search"
3. ⚠️ Level 2 limitation: Cannot cluster without all components
4. Fallback to semantic search
5. Search chunks for "5153" text
6. Return semantic results
```

**⚠️ Note:** Level 2 requires full components (unit + prefix + suffix)
**Workaround:** User should provide more info: "04 TT 5153"

---

## 🔄 Complete Example End-to-End

### Scenario: Tìm thông tin về "04 TT 2020"

#### **INGESTION PHASE (One-time, đã chạy trước):**

```
File: 01. P&ID Ammonia Unit Rev12 (04000).pdf
  ↓
1. Classification: quick_doc_type="P&ID", is_cad_like=TRUE
2. Page 113: Vector text=1376 chars → OCR triggered (< 1700)
3. OCR Process:
   - Base image: 0.57MB
   - Real-ESRGAN 2x: 5.81MB (19.67s, GPU)
   - Vision OCR: 2855 chars extracted (11.89s)
   - Geometric assembly: 9 tags found (0.13s)
   - Total: 2972 chars, 31.69s
4. Chunking: 3 chunks created from page 113
5. Tag extraction:
   - Tags found: ["29 SG 2201A", "29 TE 2004A", "04 TT 2020", ...]
   - Saved to tags.jsonl
6. Component extraction:
   - Components: ["04" (unit), "TT" (prefix), "2020" (suffix), ...]
   - Indexed to spatial_components: 247 components from page 113
7. Result: Ready for search!
```

#### **QUERY PHASE (Real-time, when user asks):**

```
User Query: "04 TT 2020"
Mode: P&ID Search
  ↓
1. Parse: unit="04", prefix="TT", suffix="2020"
2. Spatial Search:
   - Query components index for "04" units in Ammonia
   - Query components index for "TT" prefixes in Ammonia
   - Query components index for "2020" suffixes in Ammonia
   - Candidate pages: [113, 117] (both have all 3)

   For Page 113:
   - Try combinations of (04, TT, 2020) components
   - Find cluster: 04 at (326, 174), TT at (328, 190), 2020 at (326, 206)
   - Distance check: ✓ < 25mm
   - Alignment check: ✓ vertically aligned
   - Sequence check: ✓ 04 above TT above 2020
   - Score: 0.92 (EXCELLENT)

   Result: Found on Page 113, bbox=[326, 174, 27, 38]

3. Chunks Search (parallel):
   - Find chunks mentioning "04", "TT", "2020"
   - Semantic context

4. Fusion:
   - Spatial result (score=0.92) + Chunk results
   - RRF fusion

5. Generate Answer:
   "Tag 04 TT 2020 là temperature transmitter nằm tại Page 113
    của P&ID Ammonia Unit. Thiết bị này đo nhiệt độ đầu vào
    của reactor tổng hợp..."

6. Return with citations and bbox for highlighting
```

**Total Time:** ~3 seconds
- Spatial search: 200ms (slower but accurate!)
- Chunks search: 100ms
- Fusion: 50ms
- Generation: 2.5s

---

## 🎯 Key Decision Points

### During Ingestion

| Decision Point | Condition | Action | Impact |
|----------------|-----------|--------|--------|
| **Use OCR?** | CAD-like OR chars < 100 | Enable OCR | Quality vs Speed |
| **Force OCR all pages?** | is_cad_like=TRUE | Force OCR | Find hidden text |
| **OCR Threshold** | quick_doc_type | 1700 (P&ID) or 40 (Regular) | Adaptive strategy |
| **Apply Real-ESRGAN?** | CAD-like AND OCR needed | 2x enhancement | +46% text quality |
| **Run Geometric Assembly?** | CAD-like AND OCR | Assemble tags | Auto-discover tags |
| **Extract Tags?** | CADLikeGate score >= 0.55 | Run TagExtractor | P&ID features |
| **Extract Components?** | Tags extracted | ComponentExtractor | Level 2 support |

### During Query

| Decision Point | Condition | Action | Impact |
|----------------|-----------|--------|--------|
| **Which Retriever?** | request.query_type | pid or technical_doc | Search strategy |
| **Which doc_id?** | request.doc_id / filters / default | Extract doc_id | Scope of search |
| **Parse Components?** | query_type="pid" | PIDQueryEnhancer | Tag detection |
| **Spatial vs Semantic?** | Components detected | Level 2 spatial | Accuracy |
| **Fallback?** | No spatial results | Semantic search | Robustness |

---

## 📊 Performance Characteristics

### Ingestion

| Document Type | Pages | Time per Page | Total Time |
|---------------|-------|---------------|------------|
| P&ID (with OCR) | 100 | ~30s | ~50 mins |
| P&ID (no OCR) | 100 | ~2s | ~3 mins |
| Manual (no OCR) | 100 | ~1s | ~2 mins |
| Manual (with OCR) | 100 | ~5s | ~8 mins |

**Bottleneck:** Real-ESRGAN enhancement (~20s/page for P&ID)

### Query

| Query Type | Search Method | Latency | Accuracy |
|------------|---------------|---------|----------|
| P&ID (Level 2) | Spatial clustering | 100-300ms | ✅✅✅ Absolute |
| P&ID (Level 3) | Indexed tags | 10-50ms | ✅✅ Good |
| Technical Doc | BM25 + Vector | 50-150ms | ✅✅ Good |

**Trade-off:** Level 2 chậm hơn nhưng chính xác tuyệt đối về geometric

---

## 🎓 Key Concepts Explained

### quick_doc_type vs CADLikeGate

**quick_doc_type** (filename-based, FAST):
- Purpose: OCR strategy decision
- When: BEFORE processing (ingestion start)
- Method: Check filename keywords
- Result: "P&ID", "Manual", "Datasheet", etc.
- **CRITICAL** for: OCR threshold, force_ocr decision

**CADLikeGate** (content-based, THOROUGH):
- Purpose: Validate if really CAD-like for tag extraction
- When: DURING tag extraction phase
- Method: 8-feature scoring (geometry, metadata, patterns...)
- Result: CAD score 0.0-1.0, is_cadlike boolean
- **CRITICAL** for: Tag extraction decision

**Both are needed!** Different purposes.

### Level 2 vs Level 3

**Level 3 (OpenSearch Indexed Tags - OLD):**
```
Pre-indexed assembled tags in database
Query: Fast lookup (10-50ms)
Limitation: Trust pre-assembled tags
```

**Level 2 (Spatial Clustering - NEW):**
```
Individual components indexed
Query: Real-time geometric validation (100-300ms)
Advantage: Absolute accuracy, geometric proof
```

**Current system:** **Level 2** (chọn accuracy over speed)

### Geometric Assembly vs Component Extraction

**Geometric Assembly** (during OCR):
- Input: OCR fragments (text + bbox)
- Process: Find patterns, assemble tags
- Output: Complete tags ("29 SG 2201A")
- When: During ingestion, OCR phase
- Purpose: Discover tags from images

**Component Extraction** (after tag extraction):
- Input: PageLayout (vector text spans + bbox)
- Process: Classify individual text as unit/prefix/suffix
- Output: Individual components with bbox
- When: During ingestion, after tag extraction
- Purpose: Support Level 2 spatial search

**Both needed:** Assembly for discovery, Components for search

---

## 🔧 Configuration Settings

### .env Critical Settings

```ini
# OCR
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\credentials.json

# P&ID Tags & Level 2
ENABLE_PID_TAGS=true

# Storage
ARTIFACTS_DIR=D:\PVCFC_Artifacts

# Infrastructure
WEAVIATE_ENABLED=true
OPENSEARCH_ENABLED=true
USE_HYBRID_MODERN=true

# Embeddings
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
EMBED_OUTPUT_DIM=768
```

### Hardcoded in Code

**OCR Thresholds** (`app/ingestion/pdf_processor.py` line 240-250):
```python
CAD_LIKE_TYPES = {"P&ID", "Drawing", "unknown"}

if document_type in CAD_LIKE_TYPES:
    OCR_CHAR_THRESHOLD = 1700  # P&ID
else:
    OCR_CHAR_THRESHOLD = 40    # Regular
```

**Real-ESRGAN** (`app/ingestion/pdf_processor.py` line 392-457):
- Model: RealESRGAN_x4plus_anime_6B.pth
- Output scale: 2x
- Tile size: 400
- Device: auto (CUDA if available)

**Spatial Search** (`app/rag/hybrid_with_tags_retriever.py` line 72-76):
- max_distance_mm: 25.0
- alignment_tolerance_mm: 5.0
- min_cluster_score: 0.6

---

## 📁 Data Storage Locations

### During Ingestion

**Temporary/Intermediate:**
- `D:\PVCFC_Artifacts\layout\` - Page layouts (JSON)
- `D:\PVCFC_Artifacts\entities\` - Extracted tags (JSONL)
- `D:\PVCFC_Artifacts\logs\` - Telemetry

**Final Outputs:**
- `artifacts/ingestion_production/chunks/` - All chunks (JSONL)
- `artifacts/ingestion_production/processed/` - Processed docs (JSON)
- `artifacts/ingestion_production/corpus.jsonl` - Master chunks file
- `artifacts/ingestion_production/documents.json` - Master docs file

### After Indexing

**OpenSearch (localhost:9200):**
- `rag_chunks` - All chunks for keyword search
- `pvcfc_pid_tags` - Assembled tags (optional, Level 3 legacy)
- `pvcfc_pid_spatial_components` - Individual components (Level 2)

**Weaviate (localhost:8080):**
- Collection `Chunk` - Vector embeddings for semantic search

**Redis (localhost:6379):**
- Conversation history
- Query cache
- Distributed cache

---

## 🎯 Summary

### Data Flow in One Sentence

**Ingestion:** PDF → OCR/Enhancement → Classification → Chunks + Tags + Components → Index to 3 systems

**Query:** User selects mode → Parse/Route → Parallel search (Spatial or Semantic) → Fusion → LLM Generate → Answer

### Key Strengths

1. **Adaptive Processing:** Different strategies for P&ID vs Technical docs
2. **Quality OCR:** Real-ESRGAN + Google Vision for P&ID
3. **Absolute Accuracy:** Level 2 geometric validation
4. **Hybrid Search:** Combines spatial, keyword, and semantic
5. **Auto-Discovery:** Geometric assembly finds all tags
6. **Robust:** Multiple fallback mechanisms

### Trade-offs

1. **Speed vs Accuracy:** Level 2 slower but geometrically accurate
2. **Cost vs Quality:** Real-ESRGAN + Vision API costs $ but better results
3. **Complexity vs Flexibility:** Rich pipeline but more moving parts

---

## ✅ Current Status

**Ingestion Pipeline:** ✅ READY
**Indexing Systems:** ✅ READY
**Query Processing:** ✅ READY
**Level 2 Migration:** ✅ COMPLETE

**Next Action:** Run dry run to verify end-to-end!

---

**Document Version:** 1.0
**Last Updated:** 2025-11-02
**Status:** ✅ Production Ready
