# SYSTEM ARCHITECTURE - PVCFC RAG SYSTEM

**Version**: 2.1.0
**Last Updated**: 2025-12-18
**Document**: Complete Pipeline & Architecture (Gemini 3 Migration + System Prompts v2 + Deep Discovery Search + Intelligent Classification + Safety Quota + Page Metadata Fix + MAX_CONTEXT=50 + Retrieval Optimization + HierarchicalChunker + 300s Client Timeout)

---

## 📋 MỤC LỤC

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Data Flow - Luồng dữ liệu hoàn chỉnh](#2-data-flow---luồng-dữ-liệu-hoàn-chỉnh)
3. [Phase 1: Document Ingestion](#3-phase-1-document-ingestion)
4. [Phase 2: Indexing & Storage](#4-phase-2-indexing--storage)
5. [Phase 3: Query Processing](#5-phase-3-query-processing)
6. [Phase 3.5: P&ID Query Enhancement (Optional)](#6-phase-35-pid-query-enhancement-optional)
7. [Phase 4: Hybrid Retrieval](#7-phase-4-hybrid-retrieval)
8. [Phase 5: Reranking](#8-phase-5-reranking)
9. [Phase 6: Answer Generation](#9-phase-6-answer-generation)
10. [Phase 7: Response Building](#10-phase-7-response-building)
11. [Phase 8: Multi-turn Conversation Management](#11-phase-8-multi-turn-conversation-management-new)
12. [Phase 9: Deep Discovery Search (NEW v2.0)](#12-phase-9-deep-discovery-search-new-v20)
13. [Phase 10: Intelligent Classification (NEW v2.0)](#13-phase-10-intelligent-classification-new-v20)
14. [Components Deep Dive](#14-components-deep-dive)
15. [Error Handling & Resilience](#15-error-handling--resilience)
16. [Performance & Optimization](#16-performance--optimization)

---

## 📁 DATA DIRECTORIES (QUAN TRỌNG)

| Directory | Path | Purpose |
|-----------|------|---------|
| **Raw PDF Source** | `D:\Data_Raw` | Thư mục chứa các file PDF gốc để ingestion |
| **Artifacts** | `D:\PVCFC_Artifacts` | Output của ingestion (chunks, tags, crops, logs) |
| **Index Production** | `D:\PVCFC_Artifacts\index_production` | Weaviate + OpenSearch index data |

> **Note**: Các script như `batch_reclassify.py`, `ingest.py` mặc định sử dụng `D:\Data_Raw` làm source directory.

---

## 1. TỔNG QUAN HỆ THỐNG

### 1.1 Mục tiêu

Hệ thống RAG (Retrieval-Augmented Generation) phục vụ tra cứu, trích xuất và hỏi-đáp kỹ thuật trên tài liệu PVCFC với:
- ✅ **Độ tin cậy cao**: Citations có doc_id + page number
- ✅ **Multimodal**: Hỗ trợ cả text và vision (PDF pages)
- ✅ **Production-ready**: Weaviate + OpenSearch, defensive programming
- ✅ **Scalable**: Xử lý hàng nghìn tài liệu, hỗ trợ mở rộng
- ✅ **Dual Pipeline**: Tự động phân loại và xử lý P&ID vs Technical Doc
- ✅ **Deep Discovery Search (v2.0)**: Tìm TẤT CẢ documents chứa keyword - không giới hạn top_k
- ✅ **Intelligent Classification (v2.0)**: Tự động phân loại tài liệu vào 4-category taxonomy

### 1.0 Dual Pipeline Architecture (⭐ QUAN TRỌNG)

> **Hệ thống có 2 PIPELINE SONG SONG** tự động phân loại tài liệu ngay từ ingestion:

```
                         PDF INPUT
                             │
                             ↓
                    ┌────────────────┌
                    │ CAD-like Gate  │ ← BINARY CLASSIFICATION
                    │ Threshold=0.55 │
                    └────────┬───────┐
                             │
                ┌────────────┴───────────────
                │                          │
          score ≥ 0.55               score < 0.55
                │                          │
                ↓                          ↓
    ╔═══════════════════════╗    ╔═══════════════════════╗
    ║  CAD-LIKE PIPELINE    ║    ║  NON-CAD-LIKE         ║
    ║  (Extended)           ║    ║  PIPELINE (Standard)  ║
    ╚═══════════════════════╝    ╚═══════════════════════╝

    INGESTION:                    INGESTION:
    ├─ Text extraction            ├─ Text extraction
    ├─ OCR (Real-ESRGAN)⭐        ├─ OCR (no enhancement)⭐
    ├─ PageLayout (bbox+font)⭐   └─ Chunking
    ├─ TagExtractor (triplets)⭐
    ├─ Spatial (ALL 100% pages)⭐
    ├─ Crop generation (PNG) ⭐
    └─ Standard chunking

    INDEXING:                     INDEXING:
    ├─ rag_chunks (shared)        └─ rag_chunks
    └─ pvcfc_pid_spatial_components ⭐ (ALL pages)

    RETRIEVAL:                    RETRIEVAL:
    ├─ Branch A: Tags index ⭐    └─ Single branch
    ├─ Branch B: Chunks index         (BM25 + Weaviate)
    └─ RRF Fusion (2 branches)
```

**Key Differences:**

| Aspect | P&ID Pipeline | Technical Doc Pipeline |
|--------|--------------|------------------------|
| **Auto-detect** | CAD-like Gate score ≥ 0.55 | score < 0.55 |
| **Ingestion** | Text + **Layout + Tags + Crops** | Text + Chunks only |
| **Indexes** | **2**: rag_chunks + pvcfc_pid_spatial_components (Level 2) | **1**: rag_chunks |
| **Retrieval** | **2 branches** parallel | **1 branch** |
| **Bbox** | ✅ Stored in tags | ❌ Not tracked |
| **Crops** | ✅ PNG crops generated | ❌ Not generated |
| **Enable** | `ENABLE_PID_TAGS=true` | Always on |

**Critical Notes:**
- P&ID documents **ALSO HAVE** standard chunks → fallback to semantic search
- Auto-detection at ingestion is automatic via CAD-like Gate; no manual labeling required
- Both pipelines share BM25 + Weaviate foundation
- Query routing at query-time is NOT automatic. The client must explicitly select `query_type` = `pid` or `technical_doc`. Auto-route is not implemented and not planned.

### 1.2 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI + Python 3.11 | API server |
| **Vector DB** | Weaviate (gRPC) | Semantic search |
| **Keyword Search** | OpenSearch (BM25) | Keyword search |
| **LLM** | **Gemini 3 Pro / 3 Flash Preview** | Generation (Heavy/Light) with Thinking Levels |
| **Embedding** | Gemini Embedding 001 (768D) | Text vectorization |
| **Reranker** | BGE CrossEncoder (ENABLED) | Result reranking |
| **OCR** | Google Cloud Vision API + Real-ESRGAN (2x upscaling) | Scanned PDF processing with enhanced image quality |
| **Classification** | Gemini 2.5 Flash + CADLikeGate | Document auto-classification (v2.0) |
| **Deep Search** | OpenSearch Aggregation | Exhaustive keyword search (v2.0) |
| **UI** | Streamlit (300s timeout) | Testing & debugging |
| **Monitoring** | Loguru + Metrics | Logging & observability |

> **Note**: BGE reranking is **OPTIONAL** and can be enabled via `ENABLE_BGE_RERANK=true` in .env. Currently **ENABLED** in production config. Adds ~100-400ms latency but improves semantic ranking accuracy.

> **Note**: Hybrid Modern mode (`USE_HYBRID_MODERN=true`) is the **default production mode**, combining Weaviate + OpenSearch for best performance.

> ✅ **Note (Nov 11)**: OCR protobuf conflicts resolved. Upgraded to protobuf 5.29.5 (compatible with Weaviate ≥4.21.6, Google Vision, gRPC ≥5.26.1). PaddlePaddle removed as no longer needed. System now uses Google Cloud Vision API + Real-ESRGAN exclusively.

### 1.3 Architecture Diagram - Dual Pipeline

#### OFFLINE PIPELINE (Build Time) - 2 Nhánh Song Song

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    PDF DOCUMENTS (D:\Data_Raw)                           │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ↓
                    ┌────────────────────────┐
                    │   CAD-LIKE GATE        │
                    │   Score = Σ(w×f)       │
                    │   Threshold: 0.55      │
                    └────────┬───────┬───────┘
                             │       │
                   score < 0.55     score ≥ 0.55
                             │       │
        ┌────────────────────┘       └──────────────────┐
        │                                               │
        ↓                                               ↓
╔═══════════════════════════════╗       ╔═══════════════════════════════╗
║  TECHNICAL DOC PIPELINE       ║       ║     P&ID PIPELINE             ║
║  (Standard - Always On)       ║       ║  (Extended - if enabled)      ║
╚═══════════════════════════════╝       ╚═══════════════════════════════╝

┌─ TECH DOC ─────────────────┐   ┌─ P&ID ──────────────────────────────┐
│                             │   │                                     │
│ 1. PDF Parse (PyMuPDF)      │   │ 1. PDF Parse (PyMuPDF)              │
│    ↓                        │   │    ↓                                │
│ 2. OCR if needed            │   │ 2. OCR if needed                    │
│    (Google Vision+ESRGAN)   │   │    (Google Vision+ESRGAN)           │
│    ↓                        │   │    ↓                                │
│ 3. Extract Tables           │   │ 3. Extract Tables                   │
│    ↓                        │   │    ↓                                │
│ 4. Hierarchical Chunking      │   │ 4. Hierarchical Chunking            │
│    (Structure-based)⭐       │   │    (Structure-based)⭐              │
│    ↓                        │   │    ↓                                │
│ 5. Tag extraction (light)   │   │ 5. ⭐ Page Layout Builder           │
│    from text                │   │    • Bbox + font + rotation         │
│    ↓                        │   │    • Vector drawings                │
│ 6. (v1.7.1) Dedup logic available nhưng **không còn chặn ingest** (file_hash/content_hash chỉ phục vụ báo cáo) │   │    ↓                                │
│    ↓                        │   │ 6. ⭐ Tag Extractor                 │
│ OUTPUT:                     │   │    • CODE-anchored assembly         │
│ • chunks.jsonl              │   │    • Triplets: UNIT-PREFIX-SUFFIX   │
│                             │   │    • Bbox + confidence              │
│                             │   │    ↓                                │
│                             │   │ 7. ⭐ Crop Generation (lazy)        │
│                             │   │    • PNG crops of tag bboxes        │
│                             │   │    ↓                                │
│                             │   │ 8. Tag extraction (light) from text │
│                             │   │    ↓                                │
│                             │   │ 9. (v1.7.1) Dedup logic available nhưng **không chặn ingest** (file_hash chỉ dùng cho audit/offline) │
│                             │   │    ↓                                │
│                             │   │ OUTPUT:                             │
│                             │   │ • chunks.jsonl (ALSO!)              │
│                             │   │ • entities/tags.jsonl ⭐            │
│                             │   │ • page_layout/*.json ⭐             │
│                             │   │ • crops/*.png ⭐ (lazy)             │
└─────────────┬───────────────┘   └──────────────┬──────────────────────┘
              │                                  │
              │                                  │
              └──────────┬───────────────────────┘
                         │
                         ↓
        ┌────────────────────────────────────────┐
        │        INDEXING (Both Pipelines)       │
        ├────────────────────────────────────────┤
        │                                        │
        │ FROM: chunks.jsonl (Both pipelines)    │
        │   ↓                                    │
        │ ┌──────────────┐  ┌──────────────┐     │
        │ │  Weaviate    │  │  OpenSearch  │     │
        │ │  Collection  │  │  rag_chunks  │     │
        │ │  "Chunk"     │  │  (BM25)      │     │
        │ └──────────────┘  └──────────────┘     │
        │                                        │
        │ FROM: Spatial components (P&ID only)  │
        │   ↓                                    │
        │ ┌──────────────────────────┐           │
        │ │  OpenSearch              │           │
        │ │  pvcfc_pid_spatial_      │           │
        │ │  components ⭐            │           │
        │ │  (Level 2 spatial)       │           │
        │ └──────────────────────────┘           │
        └────────────────────────────────────────┘
```

#### ONLINE PIPELINE (Query Time) - 2 Chế Độ Khác Nhau

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         USER QUERY + query_type                          │
│                    (Manual Selection: pid | technical_doc)               │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                  ┌──────────────┴───────────────┐
                  │                              │
        query_type=technical_doc       query_type=pid
                  │                              │
                  ↓                              ↓
    ╔═════════════════════════╗      ╔═════════════════════════════════╗
    ║ TECHNICAL DOC RETRIEVAL ║      ║     P&ID RETRIEVAL              ║
    ║ (Single Branch)         ║      ║  (Dual Branch Parallel)         ║
    ╚═════════════════════════╝      ╚═════════════════════════════════╝

┌─ TECH DOC QUERY ───────────┐   ┌─ P&ID QUERY ────────────────────────┐
│                             │   │                                     │
│ 1. Query Transform          │   │ 1. Query Transform                  │
│    • Normalize              │   │    • Normalize                      │
│    • Equipment extraction   │   │    • ⭐ Tag detection & parsing     │
│    ↓                        │   │    • ⭐ Variants generation         │
│ 2. Single Branch Search:    │   │    ↓                                │
│    ┌─────────────────────┐  │   │ 2. Dual Branch Search (PARALLEL):  │
│    │ Weaviate + BM25     │  │   │    ┌──────────┐  ┌──────────────┐  │
│    │ (rag_chunks only)   │  │   │    │ Branch A │  │  Branch B    │  │
│    │                     │  │   │    │ Tags     │  │  Chunks      │  │
    │    │ • BM25-heavy (100)  │  │   │    │ Index ⭐ │  │  Index       │  │
    │    │ • Semantic (100)    │  │   │    └────┬─────┘  └──────┬───────┘  │
    │    │ • No tag routing    │  │   │         │               │          │
    │    └─────────┬───────────┘  │   │    OpenSearch                Weaviate+BM25   │
    │              ↓              │   │    pvcfc_pid_spatial_        rag_chunks       │
    │                            │   │    components (Level 2)                       │
    │ 3. RRF Fusion               │   │         │               │          │
│    (Standard weights)       │   │         └───────┬───────┘          │
│    ↓                        │   │                 ↓                  │
│ 4. Equipment Boost (×1.5)   │   │ 3. ⭐ Adaptive RRF Fusion           │
│    ↓                        │   │    (Query-type weights)             │
│ 5. Score-based Rerank       │   │    ↓                                │
│    (No BGE by default)      │   │ 4. ⭐ PID Tag Reranking             │
│    ↓                        │   │    • Exact: ×10, Fuzzy: ×2-3        │
│ 6. LLM Rerank (if enabled)  │   │    • Proximity: ×3                  │
│    ↓                        │   │    ↓                                │
│ RESULTS:                    │   │ 5. BGE Rerank (if enabled)          │
│ • 1 source (chunks)         │   │    ↓                                │
│ • No bbox/crops             │   │ RESULTS:                            │
│ • Pure text context         │   │ • 2 sources (tags + chunks)         │
│                             │   │ • ⭐ Bbox + crop_path (from tags)   │
│                             │   │ • Spatial context                   │
└─────────────┬───────────────┘   └──────────────┬──────────────────────┘
              │                                  │
              └──────────┬───────────────────────┘
                         │
                         ↓
              ┌──────────────────────┐
              │  GENERATION          │
              │  (Same for both)     │
              │  • Text or Vision    │
              │  • Gemini 2.5        │
              │  • Citation extract  │
              └──────────┬───────────┘
                         │
                         ↓
              ┌──────────────────────┐
              │   JSON RESPONSE      │
              └──────────────────────┘
```

> **P&ID Tag Extraction Note**: The system includes a complete **CAD-like Tag Extraction pipeline** (enabled by default via `ENABLE_PID_TAGS=true`):
> - **Offline**: CADLikeGate (auto-detect via 8 features, S≥0.55) → PageLayoutBuilder (vector-first PyMuPDF + Google Cloud Vision OCR fallback) → TagExtractor (CODE-anchored AREA-CODE-NUM-SUFFIX assembly) → Geometric Assembly for auto-discovery → Spatial Component Extractor → Index components to `pvcfc_pid_spatial_components` (Level 2)
> - **Online**: Manual `query_type` selection → If `pid`: Level 2 Spatial Search (component-based clustering) → RRF fusion with chunks → PID Tag Rerank → Attach bbox for vision citations
> - **Configuration**: `config/cadlike_gate.yaml`, `config/tag_grammar.yaml`, `config/page_filters.yaml`
> - **Artifacts**: `{ARTIFACTS_DIR}` (hiện tại: `D:\PVCFC_Artifacts`) → `entities/tags.jsonl`, `page_layout/*.json`, `crops/*.png` (optional), `logs/tag_extraction_telemetry.jsonl`
> - **Implementation**: `app/ingestion/tags/` (orchestrator, tag_extractor), `app/ingestion/cadlike_gate.py`, `app/ingestion/layout/`, `app/rag/spatial/` (Level 2), `app/rag/hybrid_with_tags_retriever.py`
> - **Quick Start**: See `START_HERE_CAD_TAGS.md`, `CAD_TAG_EXTRACTION_QUICKSTART.md`

---

## 2. DATA FLOW - LUỒNG DỮ LIỆU HOÀN CHỈNH

### 2.1 Build Time (Offline)

```
RAW PDF FILES
    ↓
[1] INGESTION
    • Parse PDF (PyMuPDF)
    • OCR if needed (Google Cloud Vision API + Real-ESRGAN)
    • Extract text + metadata
    ↓
[2] CHUNKING (HIERARCHICAL STRATEGY - PHASE 3) ⭐
    • HierarchicalChunker (app/rag/chunkers/hierarchical_chunker.py)
    • Strategies: hierarchical (default), sentence-window, small-to-big
    • Parameters: max_chunk_size=1000, min_chunk_size=100, chunk_overlap=50
    • Parent: Heading + 200 chars summary (context provider)
    • Child: Section content split by paragraphs (retrieval targets)
    • Child chunks link to parent via parent_chunk_id
    • Page-aware chunking (v1.7.1 FIX): chunk_markdown_with_pages() with index mapping
    ↓
[3] DEDUPLICATION
    • Current mode (v1.7.1): cả dedup theo file_hash **và** content-based dedup **đều đang tắt** trong ingestion online; mọi PDF (kể cả bản trùng) đều được xử lý và index.
    • Dedup logic (`_calculate_content_hash`, `content_hash_map`, `duplicate_groups`) hiện chỉ là hạ tầng cho **quan sát/audit** hoặc batch/offline scripts (ví dụ `scripts/dedupe_chunks.py`); ingestion online mặc định **không ghi** `dedup_report.json` và không dùng chúng để chặn ingest.
    • (v1.7.1 FIX): TagNormalizer moved outside loop (5000x speedup), recursion limit 50000, GPU singleton with thread locks, resource leak fixed with outer finally block
    ↓
[4] INDEXING
    ├── Weaviate: Vector embeddings (768D) → Collection "Chunk"
    └── OpenSearch: BM25 inverted index → Index "rag_chunks"
    ↓
[5] P&ID TAG EXTRACTION (PARALLEL, IF ENABLE_PID_TAGS=true)
    ↓
    [5.1] CAD-LIKE GATE (app/ingestion/cadlike_gate.py) - HYBRID DETECTION (v1.4.0)
        • Sample pages: [1,2,3,mid,last] (5 pages default)

        **PHASE 1: Vector Features (8 features - ALWAYS computed):**
        • Compute vector_score = Σ(weight_i × feature_i):
          - Producer/Creator keywords (AutoCAD, Bentley, etc.) - 0.20
          - Geometry density (vector paths/lines per area) - 0.15
          - Short CAPS rate (2-4 letter tokens) - 0.15
          - 3-piece tag regex hits (dd CC-CC ddddd) - 0.20
          - Technical suffixes (A/B/C, 2oo3, -201B) - 0.10
          - Large page size (A1/A0) - 0.05
          - Rotated text spans - 0.05
          - Leader patterns - 0.10

        **PHASE 2: Image Features (3 features - CONDITIONAL, only if vector_score < 0.55):**
        • If vector_score < 0.55: Compute image_score via:
          - Shape detection (circles + rectangles via HoughCircles/contours) - 0.40 weight
          - Line detection (long lines >100px via HoughLinesP) - 0.30 weight
          - Edge density (Canny edge detection, capped at 25%) - 0.30 weight
        • Render pages at 300 DPI for accurate analysis
        • image_score = 0.40×shapes + 0.30×lines + 0.30×edges

        **PHASE 3: Hybrid Classification (4 decision paths):**
        • Path 1 (VECTOR): vector_score ≥ 0.55 → CAD-like (HIGH confidence, skip image)
        • Path 2 (FALLBACK): No image data available → Use vector_score only
        • Path 3 (IMAGE): vector_score < 0.20 → Rely on image_score:
          - image_score ≥ 0.80 → CAD-like (HIGH confidence)
          - 0.55 ≤ image_score < 0.80 → CAD-like (MEDIUM confidence, filename boost optional)
          - image_score < 0.55 → Not CAD-like (HIGH confidence)
        • Path 4 (HYBRID): 0.20 ≤ vector_score < 0.55 → Combined:
          - combined_score = 0.60×vector_score + 0.40×image_score
          - combined_score ≥ 0.55 → CAD-like (MEDIUM confidence)

        **Result Fields:**
        • is_cadlike: boolean
        • score: final score (vector, image, or combined)
        • confidence: HIGH / MEDIUM / UNKNOWN
        • detection_method: VECTOR / IMAGE / HYBRID / ERROR
        • image_features: dict with shape/line/edge scores (if computed)

        • Select "taggy pages" (regex_hits≥3 OR code_tokens≥4)
        ↓ is_cadlike=true
    [5.2] PAGE LAYOUT EXTRACTION (app/ingestion/layout/page_layout_builder.py)
        • Vector-first: PyMuPDF text spans (bbox, font_size, rotation)
        • Vector drawings: lines, circles, rectangles, paths
        • OCR fallback: Google Cloud Vision API if vector text < threshold
        • Normalize engineering spacing ("3.9  MPag" → "3.9 MPag")
        • Save to page_layout/page_{doc_id}_{page}.json
        ↓
    [5.3] TAG EXTRACTION (app/ingestion/tags/tag_extractor.py)
        • Token role classification:
          - AREA: ^\d{2}$
          - CODE: ^[A-Z]{1,6}$ (whitelist: I, P, T, PAL, PSAL, PT, PI, FIC, etc.) ✅ Nov 11: Single-letter support
          - NUM: ^\d{3,5}[A-Z]?$
          - SUFFIX: A/B(/C)?, [1-3]oo[2-4], -?\d{3,5}[A-Z]?
        • CODE-anchored vertical triplet assembly:
          - Find CODE from whitelist
          - Search AREA above, NUM below (within tolerances)
          - Score triplet (triplet_regex, x_align, y_uniform, font_sim)
          - Pass if score ≥ 6.0
        • Suffix attachment (expand bbox by 1.0em radius)
        • Exclusion zones: LEGEND/NOTES/headers/footers
        • Save to entities/tags.jsonl (1 JSON per tag)
        ↓
    [5.4] CROP GENERATION (app/ingestion/tags/crops.py - optional, lazy default)
        • Render bbox crops to PNG (DPI=200)
        • Filename: {doc_id}_p{page}_{tag_hash}.png
        • Save to crops/ (only if LAZY_CROP_GENERATION=false)
        ↓
    [5.5] INDEXING & TELEMETRY
        • Bulk index: Spatial components → OpenSearch "pvcfc_pid_spatial_components" (Level 2)
        • Deterministic _id: {doc_id}#{page}#{tag}
        • Log telemetry: logs/tag_extraction_telemetry.jsonl
          - cadlike_score, tags_found_total, p50/p90, ocr_ratio, warnings
        ↓
OUTPUT:
    • chunks.jsonl (raw chunks, **không dedup ở ingest v1.7.1**)
    • doc_id_map.json (doc_id → pdf_path mapping)
    • Weaviate collection "Chunk" (vectors)
    • OpenSearch index "rag_chunks" (keywords)

    [NEW] P&ID TAG EXTRACTION OUTPUTS (if ENABLE_PID_TAGS=true):
    • entities/tags.jsonl (instrument tags with bbox)
    • page_layout/*.json (text spans + vector drawings per page)
    • crops/*.png (bbox PNG crops - if not lazy)
    • logs/tag_extraction_telemetry.jsonl (runtime metrics + warnings)
    • OpenSearch index "pvcfc_pid_spatial_components" (Level 2 spatial components index)
```

> **Index Directory Note**: Index root is configured via `INDEX_DIR` in `.env` (hiện tại: `D:\PVCFC_Artifacts\index_production`). Older docs có thể vẫn nhắc tới `artifacts/index_production`; hãy ưu tiên giá trị trong `.env`.

> **P&ID Artifacts Location**: Các artifact P&ID sử dụng `ARTIFACTS_DIR` làm root (hiện tại: `D:\PVCFC_Artifacts`):
> - `{ARTIFACTS_DIR}/entities/tags.jsonl`
> - `{ARTIFACTS_DIR}/layout/*.json`
> - `{ARTIFACTS_DIR}/crops/*.png` (nếu không ở lazy mode)
> - `{ARTIFACTS_DIR}/logs/tag_extraction_telemetry.jsonl`

### 2.2 Query Time (Online)

```
USER QUERY: "What is E04217 max pressure?"
    ↓
[0] CACHE CHECK (TTL: 10 min, configurable)
    • Cache key: (normalized_query, filters, max_context)
    • HIT? → Return cached results (skip to [6])
    • MISS? → Continue to [1]
    ↓
[1] QUERY TRANSFORM
    • Normalize: lowercase, spaces
    • Intent detection: ASK|LOCATE|EXPLAIN|REPORT
    • Extract filters: equipment_id, doc_type
    • [NEW] P&ID Enhancement (if ENABLE_PID_ENHANCEMENT=true):
      - Detect equipment tags (E04217, P04201A, K06101, etc.)
      - Generate tag variants (E04217, E-04217, e04217)
      - Classify query type (tag_only, mixed, visual, semantic)
      - Infer equipment type from tag prefix
    • HyDE: Generate hypothetical document (optional)
    ↓
[2] ADAPTIVE HYBRID RETRIEVAL (Parallel)
    ├── Weaviate Search (semantic)
    │   • Embed query → 768D vector (Gemini embedding-001)
    │   • near_vector search
    │   • [NEW] Tag filter (if P&ID enabled + tags detected)
    │   • Top 100 results (v1.7.0 - WEAVIATE_RETRIEVAL_LIMIT=100)
    │   • Weight: varies by query type (0.3-1.0)
    │
    └── OpenSearch BM25 (keyword)
        • Tokenize query
        • BM25 scoring (k1=1.2, b=0.75)
        • [NEW] Tag boosting (if P&ID enabled):
          - Metadata exact: × 10.0
          - Text phrase: × 5.0
          - Fuzzy match: × 2.0-3.0
        • Top 200 results (v1.7.1 - OPENSEARCH_RETRIEVAL_LIMIT=200, deep code search + header filtering)
        • Weight: varies by query type (0.3-1.0)
    ↓
[3] ADAPTIVE RRF FUSION (NEW: Query-type aware)
    • Reciprocal Rank Fusion with adaptive weights
    • tag_only: OS weight=1.0, WV weight=0.3
    • mixed: OS weight=0.7, WV weight=0.7
    • semantic: OS weight=0.5, WV weight=1.0
    • Combined ranking
    ↓
[3.5] PID TAG RERANKING (Optional - if P&ID enabled)
    • Boost exact tag matches in metadata: × 10.0
    • Boost exact tag matches in text: × 5.0
    • Boost fuzzy tag matches (≥90%): × 2.0-3.0
    • Boost tag-parameter proximity (<100 chars): × 3.0
    • Parameters: pressure, temperature, flow, bar, psi, °C, etc.
    ↓
[3.6] EXACT MATCH GUARDRAILS (v1.7.1 - Safety Quota) 🛡️
    • Detect special codes in query (equipment codes, drawing codes)
    • Extract ALL exact matches from fused results
    • Sort by original RRF/BM25 score (quality-first)
    • Truncate to Top 20 exact matches
    • Boost top 20 to score 1.0 → Place at top of results
    • Recycle dropped matches (21+) to semantic pool for BGE
    • Reserve BGE slots: top_k - len(exact_matches)
    • Example: top_k=50, 20 exact → BGE gets 30 slots
    • Prevents header/footer flooding, guarantees semantic diversity
    ↓
[4] BGE RERANKING (Optional - Currently ENABLED)
    • BAAI/bge-reranker-base CrossEncoder
    • Score each (query, doc) pair on remaining candidates (after exact match extraction)
    • Re-sort by semantic relevance
    • Top-k selection: BGE_RERANK_TOP_K=50 (v1.7.0)
    • Final context: MAX_CONTEXT=50 chunks sent to LLM (v1.7.0+)
    ↓
[4.5] CACHE UPDATE
    • Store results in cache for future identical queries
    ↓
[5] GENERATION
    ├── Strategy Decision
    │   • Has PDF pages? → Vision
    │   • Text only? → Text
    │
    ├── Vision Generation (if applicable)
    │   • Render PDF pages to JPEG (DPI=200)
    │   • Max pages: VISION_MAX_PAGES_TOTAL=30 (v1.7.0)
    │   • Send to Gemini 3.0 Pro Preview (models/gemini-3-pro-preview - bleeding edge)
    │   • Extract answer + citations
    │   • Timeout: 300s (Streamlit client supports long Vision processing)
    │
    └── Text Generation
        • Context = concatenated chunks (up to 50)
        • Model selection by tier:
          - Heavy (default production): Gemini 3.0 Pro Preview (models/gemini-3-pro-preview)
          - Light (dev/test): Gemini 2.5 Flash (models/gemini-2.5-flash)
        • Max output tokens: 8192 (LLM_MAX_OUTPUT_TOKENS)
          - Light mode: Gemini 2.5 Flash
        • Extract answer + citations
    ↓
[6] POST-PROCESSING
    • Citation validation (CiteFix-lite)
    • Confidence calculation (with defensive clamping)
    • IEEE-style conversion (optional)
    ↓
[7] RESPONSE BUILDING
    • Answer text
    • Citations: [{doc_id, page, pdf_path, confidence}]
    • Metadata: latency, model, vision_pages, degrade_mode, etc.
    • Confidence: [0, 1] (validated & clamped)
    • Warnings: degrade_mode, cache_hit, etc.
    ↓
JSON RESPONSE to Client
```

> **Confidence Clamping Note**: Due to past bugs where confidence could be None or >1, defensive clamping to [0,1] is applied. Logs errors when invalid values detected.

> **Model Selection Note**: The system uses tier-based model selection:
> - **Production mode (default)**: `execution_mode="production"` → `generator_tier="heavy"` → Uses **Gemini 2.5 Pro** for both text and vision generation
> - **Light mode**: `execution_mode="light_only"` → `generator_tier="light"` → Uses **Gemini 2.5 Flash** for text generation only
> - **Vision generation**: Always uses **Gemini 2.5 Pro** regardless of tier/mode
>
> This means in typical production usage, both text and vision use the same Gemini 2.5 Pro model for consistency and quality.

---

## 3. PHASE 1: DOCUMENT INGESTION

> **⚠️ DUAL PIPELINE**: Ingestion tự động phân loại tài liệu thành P&ID hoặc Technical Doc

### 3.1 Input
- **Source**: `D:\Data_Raw` (recursive scan)
- **Format**: PDF (vector text or scanned images)
- **Size**: Thousands of files, various sizes
- **Types**: Mixed (P&ID + Technical Docs)

### 3.2 Auto-Detection Flow (CAD-like Gate)

```python
# File: app/ingestion/tags/orchestrator.py

for pdf_file in scan_directory("D:\\Data_Raw"):
    if is_valid_pdf(pdf_file):

        # ===== AUTO-DETECT STARTS HERE =====
        if ENABLE_PID_TAGS:
            gate_decision = cadlike_gate.evaluate(pdf_file)

            if gate_decision.is_cadlike:
                # → P&ID PIPELINE
                process_as_pid(pdf_file)
            else:
                # → TECHNICAL DOC PIPELINE
                process_as_technical_doc(pdf_file)
        else:
            # P&ID disabled → all as technical doc
            process_as_technical_doc(pdf_file)
```

**8 Features Scoring:**

| Feature | Weight | Example (P&ID) | Example (Manual) |
|---------|--------|----------------|------------------|
| producer_keyword | 0.20 | AutoCAD (1.0) | MS Word (0.0) |
| geometry_density | 0.15 | High (0.85) | Low (0.05) |
| short_caps_rate | 0.15 | 25% CAPS (0.83) | 5% CAPS (0.17) |
| regex_3piece_hits | 0.20 | Many (1.0) | None (0.0) |
| technical_suffix | 0.10 | A/B/C (0.88) | None (0.0) |
| non_a4_page | 0.10 | A1 (1.0) | A4 (0.0) |
| multi_rotation | 0.05 | Rotated (0.65) | Normal (0.0) |
| leader_pattern | 0.05 | Leaders (1.0) | None (0.0) |
| **TOTAL** | **1.00** | **0.78** ≥ 0.55 ✅ | **0.12** < 0.55 ❌ |

**Decision:**
- P&ID score 0.78 → **P&ID PIPELINE** (extended)
- Manual score 0.12 → **TECH DOC PIPELINE** (standard)

### 3.3 Processing Steps (Dual Branch)

#### **Branch 1: Technical Doc Processing**

```python
# Standard pipeline (simpler)
def process_as_technical_doc(pdf_file):
    # Step 1: File Discovery
    validate_pdf(pdf_file)

    # Step 2: Text Extraction
    doc = fitz.open(pdf_file)
    text = extract_text(doc)

    # Step 3: OCR if needed
    if len(text) < 100:
        # OCR with Google Cloud Vision API + Real-ESRGAN enhancement
        text = perform_ocr_with_vision_api(pdf_file)

    # Step 4: Chunking
    chunks = hierarchical_chunker.chunk(text)

    # Step 5: Save
    save_chunks(chunks, "chunks.jsonl")

    # DONE - No tags, no layouts, no crops
```

#### **Branch 2: P&ID Processing**

```python
# Extended pipeline (complex)
def process_as_pid(pdf_file):
    # Step 1-4: Same as Technical Doc
    chunks = process_text_extraction_and_chunking(pdf_file)

    # Step 5: Page Layout Extraction ⭐
    for page in taggy_pages:
        layout = page_layout_builder.build_layout(pdf_file, page)
        # → Extract bbox, font, rotation, vector drawings
        save_layout(layout, "page_layout/{doc_id}_{page}.json")

    # Step 6: Tag Extraction ⭐
    tags = tag_extractor.extract_tags(layout)
    # → Assemble triplets (UNIT-PREFIX-SUFFIX-VARIANT)
    save_tags(tags, "entities/tags.jsonl")

    # Step 7: Crop Generation ⭐
    for tag in tags:
        crop = generate_crop(pdf_file, tag.bbox)
        save_crop(crop, f"crops/{doc_id}_p{page}_{tag}.png")

    # Step 8: Save chunks (ALSO) ⭐
    save_chunks(chunks, "chunks.jsonl")

    # DONE - Has tags + layouts + crops + chunks
```

**Key Difference:**
- Technical Doc: **4 steps** (extract → OCR → chunk → save)
- P&ID: **8 steps** (extract → OCR → chunk → **layout → tags → crops** → save)

#### Step 2: PDF Parsing with OCR (Google Cloud Vision + Real-ESRGAN)
```python
# Try vector text first
doc = fitz.open(pdf_path)
text = extract_text(doc)

if not has_text(text) or char_count < OCR_THRESHOLD:
    # Render page to image with adaptive DPI
    page_image = render_page_to_image(pdf_path, page_num, dpi=144-216)

    # Enhance with Real-ESRGAN (2x upscaling)
    enhanced_image = enhance_with_realesrgan(page_image, scale=2)

    # OCR with Google Cloud Vision API
    ocr_response = vision_client.text_detection(
        image=vision.Image(content=enhanced_image),
        image_context=vision.ImageContext(language_hints=["en", "vi"])
    )
    text = extract_text_from_vision_response(ocr_response)
```

> **OCR Note**: System uses **Google Cloud Vision API** with **Real-ESRGAN image enhancement** (2x upscaling) for improved OCR accuracy, especially for P&ID drawings. Real-ESRGAN runs on GPU (CUDA) when available. ✅ **Nov 11 fix**: Protobuf upgraded to 5.29.5 (compatible with Weaviate, Google Vision, gRPC), PaddlePaddle removed. See `app/ingestion/pdf_processor.py` for implementation.

#### Step 3: Metadata Extraction
```python
metadata = {
    "doc_id": generate_doc_id(pdf_path),
    "pdf_path": pdf_path,
    "file_name": Path(pdf_path).name,
    "source_format": "vector" or "scan",
    "equipment_id": extract_equipment_id(text),  # Regex: \bKT?\d{5}\b
    "doc_type": infer_doc_type(pdf_path, text),   # Manual, Drawing, etc.
    "total_pages": doc.page_count,
    "created_at": datetime.now()
}
```

#### Step 4: Content Normalization
```python
# Normalize for deduplication
normalized = text.lower().strip()
normalized = re.sub(r'\s+', ' ', normalized)
content_hash = hashlib.sha1(normalized.encode()).hexdigest()
```

### 3.3 Output
- **chunks.jsonl**: Raw chunks (before indexing)
- **doc_id_map.json**: `{doc_id: {pdf_path, file_name, ...}}`
- **quarantine.jsonl**: Failed/corrupted files

---

## 4. PHASE 2: INDEXING & STORAGE

### 4.1 Chunking Strategy (HIERARCHICAL - PHASE 3) ⭐

```python
# Phase 3: Structure-based Hierarchical Chunking
# Preserves document structure and context
from app.rag.chunkers.hierarchical_chunker import HierarchicalChunker

chunker = HierarchicalChunker(
    max_chunk_size=1000,        # Configurable via --chunk-size
    min_chunk_size=100,         # Chunks smaller than this are merged
    chunk_overlap=50,           # Overlap between chunks
    chunking_strategy="hierarchical",  # Options: hierarchical, sentence-window, small-to-big
    sentence_window_size=3,     # For sentence-window strategy
)

# Hierarchical process:
# 1. Parse Markdown structure (Headings #, ##)
# 2. Create Parent Chunks: heading + first 200 chars of content
# 3. Create Child Chunks: section content split by paragraphs
# 4. Link Child to Parent via parent_chunk_id
# 5. Page-Awareness: chunk_markdown_with_pages() with index mapping
# 6. Post-process: Merge small chunks with neighbors on same page

# Page-aware method (RECOMMENDED for accurate page metadata)
chunks = chunker.chunk_markdown_with_pages(
    pages=[(1, "page 1 text..."), (2, "page 2 text...")],
    doc_id=doc_id,
    metadata={"doc_type": "manual"}
)

# Each child chunk has:
# - text: content text - INDEXED for retrieval
# - parent_chunk_id: ID of the heading chunk (context)
# - metadata.chunk_type: "child" or "parent"
# - metadata.page: precise page number from index map
# - page_numbers: list of all pages covered (for multi-page chunks)
```

> **Phase 3 Chunking Note**: System uses **HierarchicalChunker** based on document structure. Parent chunks contain heading + 200 char summary for context. Child chunks contain section content split by paragraphs with configurable max_chunk_size (default 1000 chars). Method `chunk_markdown_with_pages()` ensures precise page metadata via character-index mapping.

### 4.2 Deduplication

> **Important (v1.7.1)**: Bước này minh hoạ **dedup offline** dựa trên `content_hash`. Ingestion online hiện **không chạy** bước dedup; tất cả chunks được ghi thẳng vào `chunks.jsonl`. Nếu cần dedup, hãy chạy batch/scripts riêng sử dụng logic tương tự.

```python
# Group by content_hash
hash_groups = defaultdict(list)
for chunk in chunks:
    content_hash = sha1(normalize(chunk.text))
    hash_groups[content_hash].append(chunk)

# Keep 1 representative per group
deduped_chunks = []
for hash_val, group in hash_groups.items():
    # Priority: vector > scan > newer > shorter_path
    representative = select_best(group)
    deduped_chunks.append(representative)
```

### 4.3 Weaviate Indexing (with Phase 3 Schema)

```python
# Connect to Weaviate
client = weaviate.connect_to_local(
    host="localhost",
    port=8080,
    grpc_port=50051
)

# Create collection with Phase 3 parent-child schema
collection = client.collections.create(
    name="Chunk",  # Production collection name
    vectorizer_config=None,  # Manual vectorization
    properties=[
        # Original fields
        Property(name="text", data_type=DataType.TEXT),  # Child text (indexed)
        Property(name="doc_id", data_type=DataType.TEXT),
        Property(name="page", data_type=DataType.INT),
        # Phase 3: Parent-Child fields
        Property(name="parent_text", data_type=DataType.TEXT),  # Parent text (for LLM)
        Property(name="parent_id", data_type=DataType.TEXT),
        Property(name="chunk_type", data_type=DataType.TEXT),  # "child"
        Property(name="is_parent", data_type=DataType.BOOL),  # False
        Property(name="parent_index", data_type=DataType.INT),
        Property(name="parent_char_count", data_type=DataType.INT),
        # ... more properties
    ]
)

# Batch insert
with collection.batch.dynamic() as batch:
    for chunk in chunks:
        # Embed text using Gemini
        vector = embed_text(chunk["text"])

        # Add to batch
        batch.add_object(
            properties=chunk,
            vector=vector
        )
```

> **Weaviate Collection Name**: Production uses "Chunk", configured via .env (WEAVIATE_COLLECTION=Chunk). Default in code is "PVCFCDocuments" but overridden.

### 4.4 OpenSearch Indexing (with Phase 3 Schema)

```python
# Create index with BM25 parameters + Phase 3 parent-child mapping
opensearch_client.indices.create(
    index="rag_chunks",
    body={
        "settings": {
            "index": {
                "similarity": {
                    "bm25_custom": {
                        "type": "BM25",
                        "k1": 1.2,
                        "b": 0.75
                        # Note: OpenSearch BM25 does not use epsilon parameter
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                # Original fields
                "text": {"type": "text", "similarity": "bm25_custom"},  # Child text (indexed)
                "doc_id": {"type": "keyword"},
                "page": {"type": "integer"},
                # Phase 3: Parent-Child fields
                "parent_text": {"type": "text", "index": False},  # Parent text (stored, not indexed)
                "metadata": {
                    "type": "object",
                    "properties": {
                        "parent_id": {"type": "keyword"},
                        "parent_text": {"type": "text", "index": False},
                        "chunk_type": {"type": "keyword"},
                        "is_parent": {"type": "boolean"},
                        "parent_index": {"type": "integer"},
                        "parent_char_count": {"type": "integer"}
                    }
                }
                # ... more fields
            }
        }
    }
)

# Bulk insert
for chunk in chunks:
    opensearch_client.index(
        index="rag_chunks",
        body=chunk
    )
```

> **BM25 Parameters Note**: OpenSearch BM25 only uses k1 and parameters. The epsilon parameter is specific to offline rank-bm25 library.

---
## 5. PHASE 3: QUERY PROCESSING

### 5.1 Query Transform

```python
def transform_query(query: str) -> TransformedQuery:
    # 1. Normalize
    normalized = query.lower().strip()

    # 2. Intent detection
    intent = detect_intent(query)  # ASK|LOCATE|EXPLAIN|REPORT

    # 3. Extract filters
    filters = {}

    # Equipment ID: K06101, KT06101
    match = re.search(r'\bKT?(\d{5})\b', query, re.IGNORECASE)
    if match:
        filters["equipment_id"] = match.group(0)

    # Doc type: "manual", "drawing", etc.
    for doc_type in ["manual", "drawing", "maintenance"]:
        if doc_type in query.lower():
            filters["doc_type"] = doc_type.title()

    # 4. HyDE (optional)
    hyde_docs = []
    if enable_hyde:
        # Generate hypothetical document
        hyde_prompt = f"Write a technical document that would answer: {query}"
        hyde_doc = llm_generate(hyde_prompt)
        hyde_docs = [hyde_doc]

    return TransformedQuery(
        original=query,
        normalized=normalized,
        intent=intent,
        filters=filters,
        hyde_queries=hyde_docs
    )
```

---

## 6. PHASE 3.5: P&ID QUERY ENHANCEMENT (Optional)

> **Feature Flag**: `ENABLE_PID_ENHANCEMENT=true` (default: enabled)
> **Added**: Version 0.8.0 (2025-10-16)
> **Purpose**: Specialized handling for P&ID (Piping & Instrumentation Diagram) and technical drawing queries with equipment tags

### 6.1 Overview

P&ID queries require specialized handling for equipment tags like **E04217** (heat exchanger), **P04201A** (pump), **K06101** (compressor). Standard semantic search struggles with these exact identifiers.

**Improvements**:
- **Precision@5**: ~60-70% → ≥90% (+20-30%)
- **Recall@10**: ~80% → ≥95% (+15%)
- **Latency P50**: ~1.5s → ~1.8s (+300ms acceptable tradeoff)

### 6.2 Tag Detection & Classification

**Implementation**: `app/rag/query_processing/pid_query_enhancer.py`

```python
from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer

enhancer = PIDQueryEnhancer()
analysis = enhancer.enhance("áp suất của pump P04201A")

# Output:
# {
#   "strategy": "tag_focused",
#   "tags": ["P04201A"],
#   "variants": ["P04201A", "P-04201A", "P 04201A", "p04201a"],
#   "equipment_types": ["pump"],
#   "query_type": "mixed"
# }
```

**Equipment Type Mapping**:
| Prefix | Equipment Type | Example |
|--------|---------------|---------|
| E, H | Heat Exchanger | E04217 |
| P | Pump | P04201A |
| K, C | Compressor | K06101 |
| V | Vessel | V05301 |
| T | Tank | T03102 |
| D | Drum | D02405 |
| F | Furnace | F01203 |

### 6.3 Query Type Classification

| Type | Example | Retrieval Strategy | RRF Weights (OS:WV) |
|------|---------|-------------------|---------------------|
| **tag_only** | "E04217" | Keyword-heavy | 1.0 : 0.3 |
| **mixed** | "áp suất của E04217" | Balanced | 0.7 : 0.7 |
| **visual** | "diagram nhiều ống" | Semantic-leaning | 0.4 : 0.6 |
| **semantic** | "how does it work?" | Semantic-heavy | 0.5 : 1.0 |

**Detection Logic**:
- **tag_only**: 1-3 words + contains tags
- **visual**: Contains keywords: diagram, vẽ, layout, schematic, P&ID, etc.
- **mixed**: Tags + parameter keywords (pressure, temperature, flow, bar, psi, °C, kg/h)
- **semantic**: Default fallback

### 6.4 Tag Variant Generation

Generate up to 4 variants per tag for fuzzy matching:

```python
# Input: "E04217"
# Output variants:
variants = [
    "E04217",      # Original
    "E-04217",     # Hyphen
    "E 04217",     # Space
    "e04217"       # Lowercase
]
```

Handles OCR errors and inconsistent formatting in documents.

### 6.5 Adaptive RRF Fusion

**Standard RRF**: Fixed weights for all queries
```python
score = 1/(k + rank_opensearch) + 1/(k + rank_weaviate)
```

**Adaptive RRF** (NEW): Weights adapt based on query type
```python
score = weight_os * 1/(k + rank_opensearch) + weight_wv * 1/(k + rank_weaviate)

# Weights by query type:
if query_type == "tag_only":
    weight_os, weight_wv = 1.0, 0.3   # Prioritize exact keyword match
elif query_type == "mixed":
    weight_os, weight_wv = 0.7, 0.7   # Balanced
elif query_type == "semantic":
    weight_os, weight_wv = 0.5, 1.0   # Prioritize semantic understanding
elif query_type == "visual":
    weight_os, weight_wv = 0.4, 0.6   # Lean semantic
```

**Configuration**: `RRF_ADAPTIVE_WEIGHTS=true` (default: true)

### 6.6 Tag Boosting in OpenSearch

**Implementation**: `app/rag/indexers/opensearch_bm25_retriever.py::search_with_tag_boosting()`

**Multi-level boosting strategy**:

```json
{
  "query": {
    "bool": {
      "should": [
        {
          "terms": {
            "tags.keyword": ["E04217", "E-04217", "E 04217", "e04217"],
            "boost": 10.0
          }
        },
        {
          "match_phrase": {
            "text": {
              "query": "E04217",
              "boost": 5.0
            }
          }
        },
        {
          "multi_match": {
            "query": "E04217",
            "fields": ["text", "tags"],
            "fuzziness": "AUTO",
            "boost": 2.0
          }
        }
      ]
    }
  }
}
```

**Boost factors** (configurable):
- `PID_TAG_BOOST_EXACT=10.0` - Exact match in metadata `tags` field
- Text phrase match: **× 5.0** (hardcoded, good default)
- `PID_TAG_BOOST_FUZZY=2.0` - Fuzzy match with AUTO fuzziness
- `PID_TAG_BOOST_PROXIMITY=3.0` - Tag near parameters (see 6.7)

### 6.7 PID Tag Reranking

**Implementation**: `app/rag/rerankers/pid_tag_reranker.py`

Applied **after RRF fusion, before BGE reranking**.

```python
from app.rag.rerankers.pid_tag_reranker import PIDTagReranker

reranker = PIDTagReranker(
    exact_boost=10.0,         # PID_TAG_BOOST_EXACT
    fuzzy_boost=2.0,          # PID_TAG_BOOST_FUZZY
    proximity_boost=3.0,      # PID_TAG_BOOST_PROXIMITY
    fuzzy_threshold=90        # PID_FUZZY_THRESHOLD
)

boosted_results = reranker.rerank(
    results=rrf_results,
    detected_tags=["E04217"],
    query="áp suất của E04217"
)
```

**Boosting rules**:

1. **Exact metadata match**: Score × 10.0
   - Tag found in chunk's `tags` field (exact match)

2. **Exact text match**: Score × 5.0
   - Tag found in chunk's text content (case-insensitive)

3. **Fuzzy match** (≥90% similarity): Score × 2.0-3.0
   - Using RapidFuzz library
   - Catches OCR errors: E04217 → E04127 (86% similarity, not boosted)
   - E04217 → E04217A (92% similarity, boosted)

4. **Tag-Parameter Proximity**: Score × 3.0
   - Tag appears within 100 characters of technical parameters
   - Parameters: `pressure`, `áp suất`, `temperature`, `nhiệt độ`, `flow`, `lưu lượng`, `bar`, `psi`, `°C`, `°F`, `kg/h`, `m³/h`, etc.
   - Example: "E04217 operating pressure: 15 bar" → Boosted

**Window size**: 100 characters (configurable via code)

### 6.8 Schema Requirements

**OpenSearch Index** (`rag_chunks`):
```json
{
  "mappings": {
    "properties": {
      "tags": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword"
          }
        }
      },
      "tags_raw": {
        "type": "keyword"
      }
    }
  }
}
```

**Weaviate Collection** (`Chunk`):
```python
Property(
    name="tags",
    data_type=DataType.TEXT_ARRAY,
    description="Equipment tags extracted from document"
)
```

**Migration** (one-time):
```powershell
# Automated setup script
.\scripts\pid_enhancement_setup.ps1

# Manual steps:
python scripts\opensearch\update_tags_mapping.py
python scripts\weaviate\add_tags_property.py
python scripts\utilities\backfill_tags.py  # ~5-10 minutes
```

### 6.9 Configuration

**Environment Variables** (`.env`):
```ini
# Enable/disable P&ID enhancement
ENABLE_PID_ENHANCEMENT=true

# Tag boosting factors
PID_TAG_BOOST_EXACT=10.0       # Metadata exact match
PID_TAG_BOOST_FUZZY=2.0        # Fuzzy match
PID_TAG_BOOST_PROXIMITY=3.0    # Tag-parameter proximity

# Fuzzy matching threshold (0-100)
PID_FUZZY_THRESHOLD=90

# Enable adaptive RRF weights
RRF_ADAPTIVE_WEIGHTS=true
```

### 6.10 Performance Impact

**Latency Breakdown**:
```
Component                 Baseline    With P&ID    Delta
─────────────────────────────────────────────────────────
Tag detection             -           ~10ms        +10ms
Query classification      -           ~5ms         +5ms
OpenSearch (boosted)      ~200ms      ~200ms       0ms
Weaviate (filtered)       ~300ms      ~300ms       0ms
RRF fusion (adaptive)     ~30ms       ~50ms        +20ms
PID reranking             -           ~100ms       +100ms
BGE reranking             ~500ms      ~500ms       0ms
─────────────────────────────────────────────────────────
TOTAL                     ~1.5s       ~1.8s        +~300ms
```

**Accuracy Improvement**:
| Metric | Baseline | With P&ID | Improvement |
|--------|----------|-----------|-------------|
| Precision@5 | 60-70% | ≥90% | +20-30% |
| Recall@10 | ~80% | ≥95% | +15% |

**Verdict**: 300ms latency increase is **acceptable tradeoff** for 20-30% accuracy improvement on P&ID queries.

### 6.11 Example Usage

**Example 1: Tag-only query**
```
Query: "E04217"
→ Detected: tag_only
→ Variants: E04217, E-04217, E 04217, e04217
→ RRF weights: OS=1.0, WV=0.3 (keyword-heavy)
→ Top result: Heat exchanger E04217 specifications (exact metadata match, boosted × 10.0)
```

**Example 2: Mixed query**
```
Query: "áp suất của pump P04201A"
→ Detected: mixed (tag + parameter "áp suất")
→ Tags: P04201A
→ Equipment type: pump
→ RRF weights: OS=0.7, WV=0.7 (balanced)
→ Proximity boost: chunks with "P04201A" near "pressure" keywords
→ Top result: P04201A pressure specification page
```

**Example 3: Semantic query (P&ID not triggered)**
```
Query: "làm thế nào để vận hành máy nén?"
→ Detected: semantic (no specific tags)
→ P&ID enhancement: SKIPPED
→ RRF weights: OS=0.5, WV=1.0 (semantic-heavy)
→ Standard hybrid retrieval
```

### 6.12 Evaluation & Testing

**Test Dataset**: `tests/ground_truth/pid_queries.json`
- 10 diverse P&ID test cases
- Ground truth relevance judgments
- Mixed query types (tag_only, mixed, visual)

**Evaluation Script**:
```powershell
python tests\eval_pid_retrieval.py

# Output:
# Avg Precision@5: 91.2% (target: ≥90%)
# Avg Recall@10: 96.5% (target: ≥95%)
# P50 Latency: 1823ms (target: ≤2500ms)
```

**Unit Tests**:
```powershell
pytest tests\\test_pid_query_enhancer.py -v
pytest tests\\test_pid_tag_reranker.py -v
pytest tests\\integration\\test_pid_retrieval_integration.py -v
```

### 6.13 P&ID Tag Location Mode (Text + Spatial)

**Implementation**: `app/rag/pid_tag_handler.py`, tích hợp trong router `/ask` (`app/api/routers/ask.py`).

Chế độ này xử lý các truy vấn mà mục tiêu chính là **tìm vị trí của một tag P&ID** (ví dụ: `"04 ZSH 4326/A"`, `"Tag 04 PSAL 2207 nằm ở trang nào?"`).

**Điều kiện kích hoạt (rút gọn):**
- `request.query_type == "pid"`.
- Và một trong hai:
  - Câu hỏi chứa từ khóa vị trí: `"tag"`, `"thiết bị"`, `"trang"`, `"page"`, `"ở đâu"`, `"located"`, `"found"`, ... → `PIDTagHandler.detect_tag_query()`.
  - Hoặc câu hỏi rất ngắn (≤3 token), chỉ chứa tag (vd: `"04 ZSH 4326/A"`) → `PIDQueryEnhancer.enhance()` parse được `{unit, prefix, suffix}` và đánh dấu là tag-only location query.

**Dòng chảy khi chế độ này được bật:**

1. Router `/ask` **bỏ qua** bước LLM generation chuẩn.
2. Hệ thống chạy một lượt **P&ID retrieval chuyên biệt** với `HybridWithTagsRetriever`:
   - Sử dụng `top_k` lớn (≈4×`max_context`, tối thiểu ~30) để đảm bảo danh sách kết quả **luôn chứa cả trang thực sự có tag** (vd: page 89), không chỉ các chunks text lân cận (page 85/86/102).
   - Nếu có `tags_retriever` trong `app.state` thì ưu tiên dùng; nếu không, fallback về retriever chuẩn.
3. Kết quả được đưa vào `PIDTagHandler.create_tag_location_answer(tag_name, retrieval_results, language)`:
   - Chuẩn hoá tag: ví dụ `"04 ZSH 4326/A"` → `"04 ZSH 4326"` (bỏ suffix biến thể A/B/... khi cần).
   - Ưu tiên các hit `source="tags"` (Level 2 `SpatialTagSearcher`) – đây là bằng chứng mạnh nhất về vị trí tag trên trang.
   - Nếu không có hit `source="tags"`, sử dụng **text hits**: so khớp tag với text đã trích từ PyMuPDF (per-page text), với normal hoá bỏ khoảng trắng và dấu gạch (`04ZSH4326`).
   - Nhóm theo `page`, chọn 1–2 trang có score cao nhất, sinh câu trả lời dạng: `"Tag 04 ZSH 4326 xuất hiện ở [Doc 1, p.89] của tài liệu **01. P&ID Ammonia Unit Rev12 (04000)**"`.
4. `/ask` trả về JSON với:
   - `answer`: câu trả lời vị trí tag (deterministic, không qua LLM),
   - `citations`: danh sách các `RetrievalResult` đã được chuẩn hoá `doc_id`, `page`, `pdf_path`, `bbox` (nếu có),
   - `confidence`: cố định cao (vd 0.95) khi tìm thấy hit rõ ràng.

**Text-only Tag Fallback (Level 1 - từ text PyMuPDF):**

- Được triển khai qua `TextTagDetector` dùng file `text_by_page.jsonl` (text trích từ PyMuPDF cho từng trang P&ID).
- Kịch bản:
  - Level 2 spatial search không tìm thấy đủ cụm `{unit, prefix, suffix}` với alignment hợp lệ.
  - Có `doc_id` cụ thể để giới hạn phạm vi tìm kiếm.
- Khi đó, `HybridWithTagsRetriever` gọi `text_tag_detector.find_tag_hits(...)` để quét text thuần:
  - Dùng full-window patterns và token gap nhỏ để nhận diện chuỗi tương đương `"04 ZSH 4326"` ngay cả khi `04`, `ZSH`, `4326` bị tách dòng.
  - Các kết quả này được convert thành "tag hits" với `source="text_tag_fallback"` và tham gia RRF fusion giống spatial hits.
- `PIDTagHandler` không phân biệt nguồn (spatial vs text_tag_fallback), mà chọn theo mức độ khớp tag và score, nên vẫn trả về đúng `page` cho truy vấn vị trí tag.

Kết quả: các truy vấn như `"04 ZSH 4326/A"` giờ có thể trả về **đúng trang P&ID thực sự chứa tag** (ví dụ page 89), với citations ổn định, thay vì rơi vào trang lân cận (85/86/102) hoặc câu LLM "không tìm thấy trong context".

### 6.14 Graceful Degradation

**P&ID enhancement failures are non-critical**:

```python
try:
    # Try P&ID enhancement
    enhanced = pid_enhancer.enhance(query)
except Exception as e:
    logger.warning(f"P&ID enhancement failed: {e}")
    # Fall back to standard retrieval
    enhanced = {"strategy": "semantic", "original": query}
```

**Fallback behaviors**:
- Tag detection fails → Standard query processing
- Schema missing (no `tags` field) → Skip tag boosting
- Reranker fails → Use RRF results directly

**No impact on system stability** - P&ID is purely additive.

---

## 7. PHASE 4: HYBRID RETRIEVAL

> **⚠️ DUAL PIPELINE**: Retrieval strategy khác nhau cho P&ID vs Technical Doc

### 7.0 Retrieval Strategy Selection

Query routing is manual: API requires `query_type` and routes strictly by this value.

```python
# File: app/api/routers/ask.py

# Required: user must select query_type ('pid' or 'technical_doc')
if user_query_type == 'pid':
    # → P&ID Pipeline
    retrieval_results = tags_retriever.search(transformed_query) if tags_retriever else retriever.search(transformed_query)
elif user_query_type == 'technical_doc':
    # → Technical Doc Pipeline
    retrieval_results = tech_doc_retriever.search(transformed_query) if tech_doc_retriever else retriever.search(transformed_query)
else:
    raise HTTPException(400, "Invalid query_type")
```

| Query Type | Routed To | Branches |
|-----------|-----------|----------|
| `technical_doc` | `TechnicalDocRetriever` | 1 |
| `pid` | Tags retriever or hybrid with PID enhancements | 2 (tags+chunks) |

### 7.1 Technical Doc Retrieval (Single Branch)

**File:** `app/rag/technical_doc_retriever.py`

```python
async def search_technical_doc(query: str, k: int = 10):
    # Step 1: Extract equipment models
    equipment = extract_equipment_models(query)  # ["HCD025"]

    # Step 2: Boost query
    enhanced_query = boost_with_variants(query, equipment)
    # "HCD025" → "HCD025 HCD-025 hcd025 HCD025 ..."

    # Step 3: Single branch hybrid search
    weaviate_task = asyncio.create_task(weaviate_search(enhanced_query))
    opensearch_task = asyncio.create_task(opensearch_search(enhanced_query))

    weaviate_results, opensearch_results = await asyncio.gather(
        weaviate_task, opensearch_task
    )

    # Step 4: RRF fusion
    fused = rrf_fusion(weaviate_results, opensearch_results)

    # Step 5: Equipment boost
    boosted = boost_equipment_matches(fused, equipment)  # ×1.5

    return boosted[:k]
```

**Characteristics:**
- ✅ 1 branch (chunks only from `rag_chunks`)
- ✅ Equipment model boosting
- ✅ BM25-heavy config (opensearch_limit=100)
- ❌ No tags index
- ❌ No bbox/crops

### 7.2 P&ID Retrieval (Dual Branch) ⭐

**File:** `app/rag/hybrid_with_tags_retriever.py`

```python
async def search_pid(query: str, k: int = 10):
    # Step 1: Parse tag components
    analysis = pid_enhancer.enhance(query)
    # "04 PSAL 2207" → {unit:"04", prefix:"PSAL", suffix:"2207"}

    # Step 2: Context validation (false positive prevention)
    if not validator.validate(query, analysis.strategy):
        # Fallback to semantic
        return standard_hybrid_search(query, k)

    # Step 3: PARALLEL SEARCH (2 branches)

    # Branch A: Tags index ⭐
    tags_task = asyncio.create_task(
        tags_retriever.search_by_components(
            unit="04",
            prefix="PSAL",
            suffix="2207"
        )
    )

    # Branch B: Chunks index
    chunks_task = asyncio.create_task(
        hybrid_search(query, k=50)  # BM25 + Weaviate
    )

    tags_results, chunks_results = await asyncio.gather(
        tags_task, chunks_task
    )

    # Step 4: RRF Fusion (merge 2 branches)
    fused = rrf_fusion(
        tags_results=tags_results,    # From Level 2 spatial search (pvcfc_pid_spatial_components)
        chunks_results=chunks_results  # From rag_chunks
    )

    # Step 5: Attach crop paths ⭐
    for result in fused:
        if result.source == "tags":
            result.crop_path = result.metadata["crop_path"]
            result.bbox = result.metadata["bbox"]

    return fused[:k]
```

**Characteristics:**
- ✅ 2 branches parallel (tags + chunks)
- ✅ Tag parsing and validation
- ✅ Bbox + crops attached
- ✅ Adaptive RRF weights
- ✅ Fallback to semantic if no tags found

### 7.3 Standard Hybrid (Baseline)

```python
async def hybrid_search(query: str, k: int = 50):
    # Parallel execution
    weaviate_task = asyncio.create_task(
        weaviate_search(query, limit=k)
    )
    opensearch_task = asyncio.create_task(
        opensearch_search(query, size=k)
    )

    # Wait for both
    weaviate_results, opensearch_results = await asyncio.gather(
        weaviate_task,
        opensearch_task,
        return_exceptions=True
    )

    # Handle failures gracefully
    if isinstance(weaviate_results, Exception):
        logger.warning("Weaviate failed, using OpenSearch only")
        weaviate_results = []

    if isinstance(opensearch_results, Exception):
        logger.warning("OpenSearch failed, using Weaviate only")
        opensearch_results = []

    return weaviate_results, opensearch_results
```

**Comparison:**

| Aspect | Technical Doc | P&ID | Standard |
|--------|--------------|------|----------|
| **Branches** | 1 (chunks) | 2 (tags+chunks) | 1 (chunks) |
| **Query Enhancement** | Equipment boost | Tag parsing | None |
| **Validation** | None | Multi-layer | None |
| **Sources** | rag_chunks | pvcfc_pid_spatial_components (Level 2) + rag_chunks | rag_chunks |
| **Bbox/Crops** | ❌ | ✅ | ❌ |

### 7.2 Weaviate Search

```python
def weaviate_search(query: str, limit: int) -> List[Result]:
    # 1. Embed query
    query_vector = embed_text(query)

    # 2. Vector search
    response = collection.query.near_vector(
        near_vector=query_vector,
        limit=limit,
        return_metadata=["distance"]
    )

    # 3. Convert to results
    results = []
    for obj in response.objects:
        results.append(Result(
            chunk_id=obj.properties["chunk_id"],
            text=obj.properties["text"],
            doc_id=obj.properties["doc_id"],
            page=obj.properties["page"],
            score=1 - obj.metadata.distance,  # Convert distance to score
            source="weaviate"
        ))

    return results
```

### 7.3 OpenSearch BM25 Search

```python
def opensearch_search(query: str, size: int) -> List[Result]:
    # 1. Tokenize query
    tokens = query.lower().split()

    # 2. BM25 search
    response = opensearch_client.search(
        index="rag_chunks",
        body={
            "query": {
                "match": {
                    "text": {
                        "query": query,
                        "operator": "or"
                    }
                }
            },
            "size": size
        }
    )

    # 3. Convert to results
    results = []
    for hit in response["hits"]["hits"]:
        results.append(Result(
            chunk_id=hit["_source"]["chunk_id"],
            text=hit["_source"]["text"],
            doc_id=hit["_source"]["doc_id"],
            page=hit["_source"]["page"],
            score=hit["_score"],
            source="opensearch"
        ))

    return results
```

### 7.4 RRF Fusion

```python
def reciprocal_rank_fusion(
    weaviate_results: List[Result],
    opensearch_results: List[Result],
    k: int = 60
) -> List[Result]:
    \"\"\"
    RRF formula: score(d) = Σ (1 / (k + rank_i(d)))
    where rank_i(d) is the rank of document d in retriever i
    \"\"\"
    rrf_scores = defaultdict(float)

    # Add Weaviate scores
    for rank, result in enumerate(weaviate_results):
        rrf_scores[result.chunk_id] += 1 / (k + rank + 1)

    # Add OpenSearch scores
    for rank, result in enumerate(opensearch_results):
        rrf_scores[result.chunk_id] += 1 / (k + rank + 1)

    # Merge and deduplicate
    merged_results = {}
    for result in weaviate_results + opensearch_results:
        if result.chunk_id not in merged_results:
            merged_results[result.chunk_id] = result
            result.fused_score = rrf_scores[result.chunk_id]

    # Sort by RRF score
    sorted_results = sorted(
        merged_results.values(),
        key=lambda r: r.fused_score,
        reverse=True
    )

    return sorted_results
```

### 7.5 Phase 3: Text Extraction for LLM Context ⭐

**File:** `app/rag/retriever.py` (helper function)

```python
def extract_text_with_parent_fallback(
    chunk_or_hit: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Phase 3 helper: Extract text for LLM context.

    Retrieval searches child chunks (section content, configurable size),
    but generation should use parent text (heading + summary, more context).

    Priority:
    1. Top-level 'parent_text' (OpenSearch)
    2. metadata['parent_text'] (Weaviate)
    3. Fallback to 'text' (child chunk)
    """
    # 1. Check top-level parent_text (OpenSearch)
    parent_text = chunk_or_hit.get("parent_text")
    if parent_text and isinstance(parent_text, str) and len(parent_text.strip()) > 0:
        return parent_text

    # 2. Check metadata.parent_text (Weaviate)
    if metadata is None:
        metadata = chunk_or_hit.get("metadata", {})

    if metadata:
        parent_text = metadata.get("parent_text")
        if parent_text and isinstance(parent_text, str) and len(parent_text.strip()) > 0:
            return parent_text

    # 3. Fallback to child text
    return chunk_or_hit.get("text", "")
```

**Integration Points:**
- `app/rag/weaviate_retriever.py`: Lines 17, 542
- `app/rag/hybrid_weaviate_opensearch_retriever.py`: Lines 23, 460, 495

**Usage Example:**
```python
# In retrieval pipeline
retrieved_chunks = retriever.search(query, k=10)

# Build context for LLM
context_blocks = []
for chunk in retrieved_chunks:
    # Extract parent text for generation (not child text)
    text_for_llm = extract_text_with_parent_fallback(chunk)
    context_blocks.append(text_for_llm)

full_context = "\n\n".join(context_blocks)
```

**Impact:**
- ✅ LLM receives complete semantic context (parent heading + summary)
- ✅ No context fragmentation
- ✅ Retrieval still uses precise child chunks (section content)
- ✅ No performance degradation (no joins)

---

## 8. PHASE 5: RERANKING

### 8.1 BGE CrossEncoder Reranking (Optional - Currently ENABLED)

```python
def bge_rerank(
    query: str,
    results: List[Result],
    top_k: int = 10
) -> List[Result]:
    # 1. Load model (cached)
    model = CrossEncoder("BAAI/bge-reranker-base")

    # 2. Prepare pairs
    pairs = [[query, result.text] for result in results]

    # 3. Score all pairs
    scores = model.predict(pairs)

    # 4. Attach scores
    for result, score in zip(results, scores):
        result.rerank_score = float(score)

    # 5. Sort by rerank score
    reranked = sorted(
        results,
        key=lambda r: r.rerank_score,
        reverse=True
    )

    # 6. Return top-k
    return reranked[:top_k]
```

> **BGE Reranking Note**: This is **OPTIONAL** and controlled by `ENABLE_BGE_RERANK` in .env. Default is OFF in code; enable via `ENABLE_BGE_RERANK=true`. Adds ~100-400ms latency and improves semantic ranking accuracy. Model loads on first query (~3-5s), then ~0.5s per rerank.

### 8.2 Fallback: Score-based Reranking

```python
def score_based_rerank(results: List[Result], top_k: int) -> List[Result]:
    # Sort by original scores (fusion or retrieval)
    sorted_results = sorted(
        results,
        key=lambda r: r.fused_score if hasattr(r, 'fused_score') else r.score,
        reverse=True
    )
    return sorted_results[:top_k]
```

---

## 9. PHASE 6: ANSWER GENERATION

### 9.1 Strategy Selection

```python
def select_generation_strategy(
    query: str,
    retrieved_docs: List[Result],
    config: GeneratorConfig
) -> str:
    # Check if vision is enabled
    if not config.enable_vision_generation:
        return "text"

    # Check if we have PDF pages available
    has_pdf_pages = any(
        doc.pdf_path and doc.page
        for doc in retrieved_docs
    )

    if not has_pdf_pages:
        return "text"

    # Check for visual keywords
    visual_keywords = ["table", "figure", "diagram", "chart", "P&ID"]
    has_visual_intent = any(
        keyword in query.lower()
        for keyword in visual_keywords
    )

    if has_visual_intent:
        return "vision"

    # Default to text for simple queries
    return "text"
```

### 9.2 Vision Generation (Multimodal)

```python
def vision_generation(
    query: str,
    retrieved_docs: List[Result],
    doc_id_map: Dict
) -> Tuple[str, List[Citation]]:
    # 1. Select pages to render
    pages_to_render = select_vision_pages(
        retrieved_docs,
        max_pages=10
    )

    # 2. Render PDF pages to images (with page watermark if enabled)
    # Page watermark: "P. XX" label added directly on image for LLM visibility
    rendered_pages = []
    for pdf_path, page_num in pages_to_render:
        try:
            image = render_pdf_page(
                pdf_path=pdf_path,
                page=page_num,
                dpi=200,
                format="jpeg"
                # Watermark added internally if VISION_ENABLE_PAGE_WATERMARK=true
            )
            rendered_pages.append({
                "pdf_path": pdf_path,
                "page": page_num,
                "image": image
            })
        except Exception as e:
            logger.warning(f"Failed to render page {page_num}: {e}")

    # 3. Build vision prompt
    prompt = f\"\"\"
Based on the provided PDF pages, answer the following question:

Question: {query}

Instructions:
- Provide a detailed answer based on the visual content
- Include page-specific citations in format: [Doc N, p.X]
- Focus on tables, diagrams, and specific values visible in the pages

Answer:
\"\"\"

    # 4. Call Gemini Vision API
    # Note: Vision generation ALWAYS uses Gemini 2.5 Pro regardless of tier/mode
    # Model names are auto-prefixed with "models/" by llm_client
    response = gemini_client.generate_content(
        model="gemini-2.5-pro",  # Vision always uses Pro (hardcoded)
        contents=[
            prompt,
            *[page["image"] for page in rendered_pages]
        ]
    )

    # 5. Extract answer and citations
    answer = response.text
    citations = extract_citations(answer, rendered_pages)

    return answer, citations
```

> **Model Name Format Note**: When configuring in .env, use simple names like gemini-2.5-pro. The LLM client automatically adds "models/" prefix internally.

> **Page Watermark Feature (NEW - Version 0.9.0)**: Vision generation now adds page number watermarks ("P. XX") directly on rendered images to solve citation accuracy issues. Previously, the multimodal LLM only saw page mappings at prompt start (e.g., "Doc 1, p.71") but forgot them due to attention decay when viewing images later. With watermarks visible on every image, citation accuracy improved from **80-85% → 100%** in testing. Feature is enabled by default via `VISION_ENABLE_PAGE_WATERMARK=true`. See [VISION_CITATION_ACCURACY.md](VISION_CITATION_ACCURACY.md) for technical details.

### 9.3 Text Generation

```python
def text_generation(
    query: str,
    retrieved_docs: List[Result],
    execution_mode: str = "production"  # default to production
) -> Tuple[str, List[Citation]]:
    # 1. Select model based on execution mode (tier-based)
    # Production mode (default) uses heavy tier -> Gemini 2.5 Pro
    # Light mode uses light tier -> Gemini 2.5 Flash
    if execution_mode == "production":
        generator_tier = "heavy"
        text_model = "gemini-2.5-pro"
    else:  # light_only
        generator_tier = "light"
        text_model = "gemini-2.5-flash"

    # 2. Build context
    context_parts = []
    doc_mapping = {}

    for i, doc in enumerate(retrieved_docs, 1):
        page_info = f" (Page {doc.page})" if doc.page else ""
        context_parts.append(f"[Doc {i}]{page_info} {doc.text}")
        doc_mapping[i] = doc

    context = "\\n---\\n".join(context_parts)

    # 3. Build prompt
    prompt = f\"\"\"
Based on the following context documents, answer the question.

Context:
{context}

Question: {query}

Instructions:
- Provide a concise, accurate answer
- Include citations in format: [Doc N, p.X]
- Only use information from the provided context

Answer:
\"\"\"

    # 4. Call Gemini with selected model
    response = gemini_client.generate_content(
        model=text_model,  # Uses gemini-2.5-pro in production, gemini-2.5-flash in light mode
        contents=prompt
    )

    # 4. Extract answer and citations
    answer = response.text
    citations = extract_citations(answer, doc_mapping)

    return answer, citations
```

### 9.4 Citation Extraction

```python
def extract_citations(
    answer: str,
    doc_mapping: Dict
) -> List[Citation]:
    # Pattern: [Doc X, p.Y] or [Doc X]
    pattern = r'\[Doc\s+(\d+)(?:,\s*pp?\.?\s*([\d\-]+))?\]'

    citations = []
    for match in re.finditer(pattern, answer):
        doc_num = int(match.group(1))
        page_str = match.group(2)

        if doc_num in doc_mapping:
            doc = doc_mapping[doc_num]

            # Parse page number
            if page_str:
                if '-' in page_str:
                    # Range: 5-7
                    start, end = map(int, page_str.split('-'))
                    pages = list(range(start, end + 1))
                else:
                    pages = [int(page_str)]
            else:
                pages = [doc.page] if doc.page else []

            # Create citation for each page
            for page in pages:
                citations.append(Citation(
                    doc_id=doc.doc_id,
                    page=page,
                    pdf_path=doc.pdf_path,
                    source="llm",
                    relevance_score=1.0
                ))

    return citations
```

### 9.5 Post-Validation (CiteFix-lite)

```python
def post_validate_citations(
    citations: List[Citation],
    query: str,
    retrieved_docs: List[Result]
) -> Tuple[List[Citation], Dict]:
    validator = CitationValidator(
        doc_id_map=load_doc_id_map(),
        neighbor_scan=2  # Check ±2 pages
    )

    validated_citations = []
    stats = {"valid": 0, "corrected": 0, "invalid": 0}

    for citation in citations:
        # Validate citation
        result = validator.validate(
            citation=citation,
            query=query,
            context_docs=retrieved_docs
        )

        if result.is_valid:
            validated_citations.append(citation)
            stats["valid"] += 1
        elif result.corrected_page:
            # Use corrected page
            citation.page = result.corrected_page
            validated_citations.append(citation)
            stats["corrected"] += 1
        else:
            stats["invalid"] += 1
            # Optionally keep or discard

    return validated_citations, stats
```

### 9.6 Confidence Calculation

```python
def calculate_confidence(
    answer: str,
    citations: List[Citation],
    retrieved_docs: List[Result]
) -> float:
    \"\"\"
    Calculate confidence score with defensive programming

    Note: Defensive clamping is applied due to historical bugs where
    confidence could be None or exceed [0,1] range. All invalid values
    are logged as errors for bug tracking.
    \"\"\"
    # Base confidence from retrieval scores
    if retrieved_docs:
        # DEFENSIVE: Handle None scores
        avg_score = sum(
            max(0, (doc.score or 0))
            for doc in retrieved_docs[:3]
        ) / min(3, len(retrieved_docs))
        base_confidence = min(avg_score * 2, 1.0)
    else:
        base_confidence = 0.0

    # Boost for citations
    if citations:
        citation_boost = min(len(citations) * 0.1, 0.3)
        base_confidence = min(base_confidence + citation_boost, 1.0)

    # Penalty for short answer
    if len(answer) < 50:
        base_confidence *= 0.7

    # Penalty for uncertainty markers
    uncertainty_phrases = ["not sure", "unclear", "might be"]
    if any(phrase in answer.lower() for phrase in uncertainty_phrases):
        base_confidence *= 0.8

    # DEFENSIVE: Final clamp to [0, 1]
    return max(0.0, min(1.0, base_confidence))
```

---

## 10. PHASE 7: RESPONSE BUILDING

### 10.1 Build API Response

```python
def build_response(
    query: str,
    answer: str,
    citations: List[Citation],
    confidence: float,
    metadata: Dict,
    timing: Dict
) -> AskResponse:
    # VALIDATION: Ensure confidence is valid
    final_confidence = confidence
    if final_confidence is None or not (0 <= final_confidence <= 1):
        logger.error(
            f"Invalid confidence value: {final_confidence}. "
            f"Clamping to valid range."
        )
        final_confidence = max(0.0, min(1.0, float(final_confidence or 0.0)))

    # Build citation list for response
    citations_list = []
    for cit in citations:
        # Clamp citation confidence too
        cit_conf = cit.relevance_score
        if cit_conf is not None:
            cit_conf = max(0.0, min(1.0, float(cit_conf)))

        citations_list.append({
            "doc_id": cit.doc_id,
            "page": cit.page or 1,
            "pdf_path": cit.pdf_path,
            "confidence": cit_conf,
            "bbox": cit.bbox
        })

    # Build metadata
    meta = {
        "model": metadata.get("model", "gemini-2.5-pro"),
        "latency_ms": round(timing["total"]),
        "breakdown": {
            "transform_ms": round(timing["transform"]),
            "retrieve_ms": round(timing["retrieve"]),
            "rerank_ms": round(timing["rerank"]),
            "generate_ms": round(timing["generate"])
        },
        "k": metadata.get("k", 8),
        "execution_mode": metadata.get("execution_mode", "production"),
        "trace_id": metadata.get("trace_id"),
        "vision_generation": metadata.get("vision_generation")
    }

    # Return response
    return AskResponse(
        answer=answer,
        citations=citations_list,
        confidence=final_confidence,
        meta=meta,
        warnings=metadata.get("warnings")
    )
```

---

## 11. PHASE 8: MULTI-TURN CONVERSATION MANAGEMENT (NEW)

> **Feature Status**: Implemented in v0.9.0
> **Documentation**: See [docs/MULTI_TURN_CHAT_GUIDE.md](docs/MULTI_TURN_CHAT_GUIDE.md)

### 11.1 Overview

The system supports **multi-turn conversations** where users can ask follow-up questions with context from previous turns. The conversation manager automatically:
- Tracks conversation history across multiple API calls
- Resolves pronouns and references ("it", "that equipment", "the same page")
- Summarizes long conversations to manage token budgets
- Persists conversations in Redis with configurable TTL

**Use Cases:**
```
User: What is the operating pressure of E04217?
AI: The operating pressure of E04217 is 15 bar...

User: What about its temperature range?  ← "its" resolves to E04217
AI: The temperature range for E04217 is 80-120°C...

User: Show me the diagram from that document  ← "that document" resolves to previous citation
```

### 11.2 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     User Query                          │
│              + conversation_id (optional)               │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
            ┌────────────────────────┐
            │ Conversation Manager   │
            │ (app.core.conversation)│
            └────────┬───────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
   New conversation?         Existing?
        │                         │
        ↓                         ↓
   Create conv_id          Load history from Redis
   Store in Redis          ↓
        │                  Apply summarization if needed
        │                  ↓
        └──────────────────┴───────────────┐
                                           ↓
                              ┌────────────────────────┐
                              │ Context Enrichment     │
                              │ - Add conversation     │
                              │   history to prompt    │
                              │ - Resolve references   │
                              └────────┬───────────────┘
                                       ↓
                              ┌────────────────────────┐
                              │ Standard RAG Pipeline  │
                              │ (Transform → Retrieve  │
                              │  → Generate)           │
                              └────────┬───────────────┘
                                       ↓
                              ┌────────────────────────┐
                              │ Save Turn to Redis     │
                              │ - User query           │
                              │ - AI response          │
                              │ - Metadata             │
                              └────────────────────────┘
```

### 11.3 Implementation

**Conversation Schema:**
```python
@dataclass
class ConversationTurn:
    """Single turn in a conversation"""
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class Conversation:
    """Complete conversation with history"""
    id: str
    user_id: Optional[str]
    language: str
    turns: List[ConversationTurn]
    created_at: datetime
    updated_at: datetime
    summary: Optional[str] = None  # Summarized context for long conversations
```

**Conversation Manager API:**
```python
class ConversationManager:
    """Manages multi-turn conversations with Redis persistence"""

    def __init__(self, redis_client, summarizer):
        self.redis = redis_client
        self.summarizer = summarizer
        self.ttl_hours = 24  # CONVERSATION_TTL_HOURS
        self.max_turns = 50  # MAX_TURNS_PER_CONVERSATION

    def create_conversation(self, user_id: Optional[str], language: str) -> str:
        """Create new conversation and return conversation_id"""
        conv_id = f"conv_{uuid.uuid4().hex[:16]}"
        conversation = Conversation(
            id=conv_id,
            user_id=user_id,
            language=language,
            turns=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self._save(conversation)
        return conv_id

    def add_turn(self, conv_id: str, role: str, content: str, metadata: Dict):
        """Add turn to conversation"""
        conversation = self._load(conv_id)
        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata
        )
        conversation.turns.append(turn)
        conversation.updated_at = datetime.now()

        # Summarize if threshold reached
        if len(conversation.turns) % SUMMARIZE_EVERY_N_TURNS == 0:
            conversation = self.summarizer.summarize(conversation)

        self._save(conversation)

    def get_history(self, conv_id: str, last_n: int = 10) -> List[ConversationTurn]:
        """Get recent conversation history"""
        conversation = self._load(conv_id)
        return conversation.turns[-last_n:]
```

### 11.4 Context Enrichment

**Adding conversation history to prompts:**
```python
def enrich_prompt_with_conversation(
    query: str,
    conversation_history: List[ConversationTurn],
    retrieved_context: List[Result]
) -> str:
    """Build prompt with conversation context"""

    # Build conversation context
    history_text = ""
    for turn in conversation_history[-5:]:  # Last 5 turns
        if turn.role == "user":
            history_text += f"User: {turn.content}\n"
        else:
            history_text += f"Assistant: {turn.content}\n"

    # Build full prompt
    prompt = f"""
Previous conversation:
{history_text}

Current question: {query}

Retrieved context:
{format_context(retrieved_context)}

Instructions:
- Use the conversation history to resolve pronouns and references
- If the user refers to "it", "that", "the same", identify what they mean from previous turns
- Provide a natural response that acknowledges the conversation flow

Answer:
"""
    return prompt
```

### 11.5 Summarization Strategy

**Automatic summarization** to manage token budgets:

```python
class ConversationSummarizer:
    """Summarize long conversations to fit token budgets"""

    def summarize(self, conversation: Conversation) -> Conversation:
        """Summarize conversation keeping key information"""

        # Extract key entities and topics from turns
        entities = self._extract_entities(conversation.turns)
        topics = self._extract_topics(conversation.turns)

        # Build summary prompt
        prompt = f"""
Summarize this technical conversation concisely:

Conversation:
{format_turns(conversation.turns)}

Extract:
1. Key equipment/documents mentioned: {entities}
2. Main topics discussed: {topics}
3. Important conclusions or answers

Summary (max 200 words):
"""

        summary = llm_client.generate(prompt)
        conversation.summary = summary

        # Keep only recent turns (e.g., last 10) + summary
        conversation.turns = conversation.turns[-10:]

        return conversation
```

### 11.6 Configuration

**Environment Variables** (`.env`):
```ini
# Conversation Memory (Multi-turn Chat)
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=

# Conversation retention and limits
CONVERSATION_TTL_HOURS=24
MAX_TURNS_PER_CONVERSATION=50
MAX_CONVERSATION_CONTEXT_TOKENS=8000

# Summarization policy (summarize every N turns)
SUMMARIZE_EVERY_N_TURNS=8

# Optional: Use provider's native chat session
ENABLE_PROVIDER_SESSION=false
```

### 11.7 API Integration

**Request with conversation_id:**
```json
POST /ask
{
  "query": "What about its temperature?",
  "conversation_id": "conv_abc123def456",
  "user_id": "user_001",
  "language": "vi",
  "query_type": "technical_doc"
}
```

**Response includes conversation metadata:**
```json
{
  "answer": "The temperature range for E04217 is 80-120°C...",
  "citations": [...],
  "confidence": 0.87,
  "meta": {
    "conversation_id": "conv_abc123def456",
    "turn_number": 3,
    "context_tokens_used": 1234,
    "summarized": false
  }
}
```

### 11.8 Implementation Files

**Core Components:**
- `app/core/conversation/conversation_manager.py` - Main manager
- `app/core/conversation/conversation_summarizer.py` - Summarization logic
- `app/core/conversation/schemas.py` - Data models
- `app/api/routers/ask.py:77-180` - API integration

**Tests:**
- `tests/test_conversation_manager.py` - Unit tests
- `tests/test_conversation_summarizer.py` - Summarization tests
- `tests/test_conversation_integration.py` - E2E tests

### 11.9 Metrics & Monitoring

**Prometheus Metrics:**
```python
# Conversation creation
conversation_created = Counter(
    'conversation_created_total',
    'Total conversations created',
    ['language']
)

# Turn tracking
conversation_turns = Counter(
    'conversation_turns_total',
    'Total conversation turns',
    ['conversation_id']
)

# Summarization tracking
conversation_summarized = Counter(
    'conversation_summarized_total',
    'Conversations summarized'
)
```

### 11.10 Performance Impact

**Latency Overhead:**
```
Without conversation: Transform(50ms) + Retrieve(500ms) + Generate(1000ms) = 1550ms
With conversation:    Load history(20ms) + Enrich(10ms) + [same pipeline] = 1580ms

Overhead: ~30ms per query (negligible)
```

**Storage:**
- Average conversation: ~5KB (10 turns, no summarization)
- With summarization: ~2KB (summary + 10 recent turns)
- Redis memory: 1000 active conversations ≈ 5MB

### 11.11 Limitations & Future Work

**Current Limitations:**
- No cross-session memory (sessions expire after TTL)
- Summarization is LLM-based (not extractive)
- No conversation branching or forking
- No conversation search/analytics

**Future Enhancements:**
- Cross-reference detection across conversations
- Conversation analytics dashboard
- Export conversation to report
- Voice input integration

---

## 12. COMPONENTS DEEP DIVE

### 12.1 LLM Service

```python
class LLMClient:
    def __init__(self, provider: str, model: str):
        self.provider = provider  # "gemini" or "openai"
        self.model = model

        if provider == "gemini":
            self.client = genai.GenerativeModel(model)
        elif provider == "openai":
            self.client = openai.ChatCompletion

    def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048
    ) -> LLMResponse:
        if self.provider == "gemini":
            response = self.client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            )
            return LLMResponse(
                content=response.text,
                model=self.model,
                finish_reason="stop"
            )
        # ... OpenAI implementation
```

### 11.2 Embedding Service

```python
class EmbeddingService:
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.dimension = self._get_dimension(model)

    def embed_texts(
        self,
        texts: List[str],
        batch_size: int = 256
    ) -> List[np.ndarray]:
        \"\"\"Batch embed texts with rate limiting\"\"\"
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Rate limiting
            time.sleep(0.1)

            # Embed batch
            if self.provider == "gemini":
                result = genai.embed_content(
                    model=self.model,
                    content=batch,
                    task_type="retrieval_document"
                )
                batch_embeddings = result['embedding']

            embeddings.extend(batch_embeddings)

        return embeddings

    def _get_dimension(self, model: str) -> int:
        \"\"\"Auto-detect embedding dimension\"\"\"
        if "gemini-embedding-001" in model:
            return 768
        elif "e5-small" in model:
            return 384
        else:
            # Probe by embedding a test string
            test_emb = self.embed_texts(["test"])[0]
            return len(test_emb)
```

### 11.3 PDF Renderer

```python
def render_pdf_page(
    pdf_path: str,
    page: int,
    dpi: int = 200,
    format: str = "jpeg"
) -> bytes:
    \"\"\"Render a PDF page to image bytes with optional page watermark\"\"\"
    import fitz  # PyMuPDF
    from PIL import Image, ImageDraw, ImageFont

    # Open PDF
    doc = fitz.open(pdf_path)

    # Get page (0-indexed)
    page_obj = doc[page - 1]

    # Render to pixmap
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page_obj.get_pixmap(matrix=mat)

    # Convert to PIL Image for watermark processing
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # Add page watermark if enabled (VISION_ENABLE_PAGE_WATERMARK=true)
    if os.getenv("VISION_ENABLE_PAGE_WATERMARK", "true").lower() == "true":
        img = _add_page_watermark(img, page)

    # Convert to bytes
    buffer = BytesIO()
    if format == "jpeg":
        img.save(buffer, format="JPEG", quality=90)
    elif format == "png":
        img.save(buffer, format="PNG")

    doc.close()

    return buffer.getvalue()


def _add_page_watermark(img: Image.Image, page_num: int) -> Image.Image:
    \"\"\"Add page number watermark to top-left corner

    Watermark design:
    - Position: Top-left corner (less P&ID label conflicts)
    - Size: Adaptive tiers (28-96px based on image height, targeting 2.5-3%)
    - Style: Yellow background (#FFFF00) + black text + white outline
    - Font: Bold Arial/DejaVu with fallbacks
    - Text: "P. {page_num}"

    Returns original image if watermarking fails (graceful degradation).
    \"\"\"
    try:
        draw = ImageDraw.Draw(img)

        # Adaptive font sizing based on image height
        height = img.height
        WATERMARK_SIZE_TIERS = [
            (1000, 28),   # Small images
            (1500, 40),   # Medium
            (2000, 56),   # Large (optimal for 2400px P&ID)
            (3000, 72),   # Very large
            (float('inf'), 96)  # Max
        ]

        font_size = next(size for threshold, size in WATERMARK_SIZE_TIERS if height < threshold)

        # Load font with fallbacks
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)  # Arial Bold (Windows)
        except:
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)  # Linux
            except:
                font = ImageFont.load_default()

        # Prepare watermark text
        text = f"P. {page_num}"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Position: top-left with padding
        padding = int(font_size * 0.5)
        x = padding
        y = padding

        # Draw yellow background rectangle
        bg_rect = [
            x - padding // 2,
            y - padding // 2,
            x + text_width + padding // 2,
            y + text_height + padding // 2
        ]
        draw.rectangle(bg_rect, fill=(255, 255, 0), outline=(0, 0, 0), width=2)

        # Draw white outline for text (8 surrounding positions)
        outline_color = (255, 255, 255)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

        # Draw black text
        draw.text((x, y), text, font=font, fill=(0, 0, 0))

        return img

    except Exception as e:
        logger.warning(f"Failed to add page watermark: {e}. Using original image.")
        return img  # Graceful degradation
```

> **Watermark Implementation Note**: The page watermark feature is implemented in `tools/pdf_renderer.py`. Configuration:
> - `VISION_ENABLE_PAGE_WATERMARK=true` (default: enabled)
> - `VISION_WATERMARK_POSITION=top-left` (configurable, default: top-left)
> - `VISION_WATERMARK_SIZE_MULTIPLIER=1.0` (fine-tuning, default: 1.0)
>
> Cache invalidation: Cache keys include `_v2` suffix to invalidate old non-watermarked images.
>
> **Performance Impact**: +5-10ms per page render (negligible, <1% overhead). Total latency increase: ~50ms for 10-page vision queries.

---

## 13. ERROR HANDLING & RESILIENCE

### 13.1 Graceful Degradation

```python
# Hybrid retrieval with fallback
try:
    weaviate_results = weaviate_search(query)
except Exception as e:
    logger.warning(f"Weaviate failed: {e}. Using OpenSearch only.")
    weaviate_results = []

try:
    opensearch_results = opensearch_search(query)
except Exception as e:
    logger.warning(f"OpenSearch failed: {e}. Using Weaviate only.")
    opensearch_results = []

if not weaviate_results and not opensearch_results:
    raise RuntimeError("All retrieval backends failed")
```

### 13.2 Validation & Logging

```python
# Always validate and log invalid states
if confidence is None or not (0 <= confidence <= 1):
    logger.error(
        f"Invalid confidence: {confidence}. "
        f"This indicates a bug. Clamping for stability."
    )
    confidence = max(0.0, min(1.0, float(confidence or 0.0)))
```

### 13.3 Retry Logic

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(ConnectionError)
)
def embed_with_retry(texts: List[str]) -> List[np.ndarray]:
    return embedding_service.embed_texts(texts)
```

### 13.4 Degrade Mode

When one retrieval backend fails, the system operates in **degrade mode** instead of failing completely.

**Detection** (`app/api/routers/ask.py`):
```python
# Check for degrade mode from retrieval results
degrade_mode = any(
    result.metadata.get("degrade_mode", False)
    if result.metadata else False
    for result in retrieval_results
)

degrade_reason = None
if degrade_mode:
    for result in retrieval_results:
        if result.metadata and result.metadata.get("degrade_mode"):
            degrade_reason = result.metadata.get("degrade_reason")
            break
    logger.warning(f"Operating in degrade mode: {degrade_reason}")
```

**Behavior Changes**:

1. **Continue with available backend**:
   - Weaviate fails → Use OpenSearch only
   - OpenSearch fails → Use Weaviate only
   - Both fail → Return error (critical failure)

2. **Increase rerank candidates**:
   ```python
   # Normal mode: rerank_top_k = 10
   # Degrade mode: rerank_top_k = 50
   rerank_top_k = (
       settings.rerank_top_n_when_degrade  # 50
       if degrade_mode
       else settings.top_rerank  # 10
   )
   ```
   **Rationale**: With only one backend, we need more candidates for reranking to maintain quality.

3. **Add warning to response**:
   ```json
   {
     "answer": "...",
     "meta": {
       "degrade_mode": true,
       "degrade_reason": "Weaviate connection timeout",
       "retrieval_backend": "opensearch_only"
     },
     "warnings": ["Operating in degraded mode: using OpenSearch only"]
   }
   ```

**Configuration** (`.env`):
```ini
# Allow fallback to BM25-only when Weaviate unavailable
RETRIEVAL_ALLOW_BM25_ONLY_FALLBACK=true

# Increased candidates when degraded
BM25_K_WHEN_DEGRADE=80          # Retrieve more candidates
RERANK_TOP_N_WHEN_DEGRADE=50    # Rerank more candidates
```

**Health Check Integration** (`app/rag/hybrid_weaviate_opensearch_retriever.py`):
```python
def health_check(self) -> Dict[str, Any]:
    health = {
        "retriever_type": "hybrid_modern",
        "components": {},
        "overall_status": "healthy",
    }

    # Check Weaviate
    weaviate_health = self.weaviate_retriever.health_check()
    health["components"]["weaviate"] = weaviate_health

    # Check OpenSearch
    opensearch_healthy = self.opensearch_retriever.health_check()
    health["components"]["opensearch"] = {
        "status": "healthy" if opensearch_healthy else "unhealthy"
    }

    # Determine overall status
    weaviate_ok = health["components"]["weaviate"]["status"] == "healthy"
    opensearch_ok = health["components"]["opensearch"]["status"] == "healthy"

    if not weaviate_ok and not opensearch_ok:
        health["overall_status"] = "critical"  # Both failed
    elif not weaviate_ok or not opensearch_ok:
        health["overall_status"] = "degraded"  # One failed
    else:
        health["overall_status"] = "healthy"   # Both OK

    return health
```

**Example Response** (degrade mode):
```json
{
  "query": "E04217 pressure",
  "answer": "...",
  "citations": [...],
  "confidence": 0.78,
  "meta": {
    "model": "gemini-2.5-pro",
    "latency_ms": 2150,
    "k": 8,
    "degrade_mode": true,
    "degrade_reason": "Weaviate health check failed: connection timeout",
    "retrieval_backend": "opensearch_only",
    "rerank_top_k": 50
  },
  "warnings": [
    "System operating in degraded mode: using OpenSearch BM25 only. Semantic search temporarily unavailable."
  ]
}
```

**Impact on Quality**:
- **Weaviate-only**: Loses keyword precision, still good for semantic queries
- **OpenSearch-only**: Loses semantic understanding, still good for exact term queries
- **Both**: Both failure modes preserve basic functionality while alerting users to degraded state

**Monitoring**:
- Log all degrade mode activations
- Track duration of degraded state
- Alert if degraded for > 5 minutes

---

## 14. PERFORMANCE & OPTIMIZATION

### 14.1 Retrieval Caching

**Implementation**: `app/core/cache_manager.py` + `app/api/routers/ask.py`

The system caches retrieval + rerank results to **dramatically reduce latency** for identical queries.

**Cache Flow**:
```python
# Step 1: Check cache BEFORE retrieval
from app.core.cache_manager import get_retrieval_cache

cache = get_retrieval_cache()
cache_key_data = (
    transformed_query.normalized,  # Normalized query text
    request.filters.dict() if request.filters else None,  # Filters
    request.max_context  # k value
)

cached_results = cache.get(*cache_key_data)

if cached_results is not None:
    # CACHE HIT - Skip retrieval & reranking entirely
    logger.info("Cache HIT - skipping retrieval & rerank")
    reranked_results = cached_results
    retrieve_time = 0
    rerank_time = 0
else:
    # CACHE MISS - Perform full pipeline
    retrieval_results = retriever.search(transformed_query)
    reranked_results = reranker.rerank(query, retrieval_results)

    # Update cache for next time
    cache.set(
        cache_key_data[0],  # query
        reranked_results,    # results
        cache_key_data[1],  # filters
        cache_key_data[2]   # k
    )
```

**Cache Configuration** (`.env`):
```ini
RETRIEVE_CACHE_TTL_MIN=10  # Cache TTL in minutes
```

**Performance Impact**:
```
First query:  Transform(50ms) + Retrieve(500ms) + Rerank(300ms) + Generate(1000ms) = 1850ms
Repeat query: Transform(50ms) + Cache(0ms) + Generate(1000ms) = 1050ms
Speedup: 43% faster (800ms saved)
```

**Cache Hit Rate**:
- Expected: 15-30% for typical workloads
- Higher for FAQ-style queries
- Lower for exploratory/ad-hoc queries

**Cache Invalidation**:
- TTL-based (expires after 10 minutes)
- Manual invalidation not currently implemented
- Future: Invalidate on index updates

**LRU Cache for Embeddings**:
```python
@lru_cache(maxsize=1000)
def embed_query_cached(query: str) -> np.ndarray:
    """Cache query embeddings (immutable)"""
    return embedding_service.embed_texts([query])[0]
```

### 14.2 Batching

```python
# Batch embedding for efficiency
def embed_documents_batched(
    docs: List[str],
    batch_size: int = 256
) -> List[np.ndarray]:
    embeddings = []
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        batch_embeddings = embedding_service.embed_texts(batch)
        embeddings.extend(batch_embeddings)
    return embeddings
```

### 14.3 Async Processing

```python
# Parallel retrieval
async def parallel_retrieve(query: str):
    weaviate_task = asyncio.create_task(weaviate_search(query))
    opensearch_task = asyncio.create_task(opensearch_search(query))

    weaviate_results, opensearch_results = await asyncio.gather(
        weaviate_task,
        opensearch_task,
        return_exceptions=True
    )

    return weaviate_results, opensearch_results
```

### 14.4 Vision Citation Accuracy Improvements

**Problem**: Multimodal LLMs (Gemini 2.5 Pro) returned correct answers but cited wrong page numbers (e.g., answering "MYLP 04504 is STATUS" but citing pages 60-62 instead of page 71).

**Root Cause**: Information asymmetry between text and vision modalities:
- Text prompt includes page mappings: "(Doc 1, p.71), (Doc 2, p.60), ..."
- Vision images contain NO page metadata
- LLM forgets text mappings due to attention decay when viewing images
- Result: LLM sees correct answer on image but cites wrong page from memory

**Solution**: **Page Number Watermarking**
- Add visible "P. XX" label directly on rendered PDF images
- LLM can now see page numbers while viewing images
- Adaptive sizing: 28-96px based on image height (targeting 2.5-3% of height)
- Position: Top-left corner (minimizes P&ID diagram conflicts)
- Style: Yellow background + black text + white outline (maximum visibility)
- Graceful degradation: Returns original image if watermarking fails

**Results**:
- **Citation Accuracy**: 80-85% → **100%** (tested on 5 E2E cases)
- **Performance Impact**: +5-10ms per page render (negligible)
- **No content occlusion**: Watermark position tested on P&ID diagrams
- **Cache invalidation**: Cache version bumped to `_v2` to clear old images

**Configuration** (`.env`):
```ini
# Enable page watermark (default: true)
VISION_ENABLE_PAGE_WATERMARK=true

# Watermark position (default: top-left)
VISION_WATERMARK_POSITION=top-left

# Size multiplier for fine-tuning (default: 1.0)
VISION_WATERMARK_SIZE_MULTIPLIER=1.0
```

**Implementation**: `tools/pdf_renderer.py::_add_page_watermark()`

**Documentation**: See [VISION_CITATION_ACCURACY.md](VISION_CITATION_ACCURACY.md) for detailed technical analysis.

**Testing**: `scripts/test_watermark_visual.py` (visual inspection), `scripts/test_vision_citation_accuracy.py` (E2E accuracy)

---

### 14.5 Tags Endpoint (Metadata API)

**Implementation**: `app/api/routers/tags.py`

**NEW endpoint** added in P&ID enhancement for listing all equipment tags in the corpus.

**Endpoint**: `GET /tags`

**Purpose**:
- Tag auto-complete for search UI
- Tag validation before queries
- Corpus overview and statistics

**Response Example** (current implementation):
```json
{
  "tags": [
    "E04217", "E04218", "E04219",
    "P04201A", "P04201B", "P04202"
  ],
  "count": 1234
}
```

**Implementation** (using OpenSearch aggregation on `rag_chunks.tags.keyword`):
```python
@router.get("/tags")
async def list_all_tags(
    http_request: Request,
    limit: int = Query(10000, description="Max tags to return")
):
    """List all unique equipment tags in the corpus"""

    # Get OpenSearch client from app state
    if not hasattr(http_request.app.state, "opensearch_client"):
        raise HTTPException(503, "OpenSearch not available")

    client = http_request.app.state.opensearch_client

    # Aggregation query
    response = client.search(
        index="rag_chunks",
        body={
            "size": 0,  # No documents, just aggregations
            "aggs": {
                "unique_tags": {
                    "terms": {
                        "field": "tags.keyword",  # Use keyword field for exact match
                        "size": limit,
                        "order": {"_key": "asc"}  # Alphabetical order
                    }
                }
            }
        }
    )

    # Extract tags from aggregation
    buckets = response["aggregations"]["unique_tags"]["buckets"]
    tags = [bucket["key"] for bucket in buckets]

    return {
        "tags": tags,
        "count": len(tags),
        "source": "opensearch",
        "timestamp": datetime.now().isoformat()
    }
```

**Use Cases**:

1. **Search UI Auto-complete**:
   ```javascript
   // Frontend: Fetch tags for autocomplete
   const response = await fetch('/tags');
   const { tags } = await response.json();

   // Use in autocomplete widget
   autocomplete.setOptions(tags);
   ```

2. **Query Validation**:
   ```python
   # Validate tag exists before search
   all_tags = requests.get("/tags").json()["tags"]
   if user_tag not in all_tags:
       suggest_similar(user_tag, all_tags)
   ```

3. **Corpus Statistics**:
   ```python
   # Get tag distribution
   GET /tags?limit=10000
   # Analyze: How many tags per equipment type?
   # E: 245, P: 189, K: 67, etc.
   ```

**Performance**:
- Cached by OpenSearch
- Typical response time: 50-200ms
- No index scan (uses aggregation cache)

**Future Enhancements**:
- Filter by equipment type: `GET /tags?type=pump`
- Pagination for large corpora
- Tag metadata (frequency, last seen, documents count)

---

## 📊 PERFORMANCE METRICS

| Metric            | Value             | Notes                 |
|-------------------|-------------------|-----------------------|
| **Ingestion**     | ~3-5 docs/sec     | With Google Cloud Vision API + Real-ESRGAN (GPU when available) |
| **Indexing**      | ~1000 docs/min    | Weaviate + OpenSearch |
| **Query Latency** | 500-2000ms        | Depends on reranking  |
|| ** - Transform**  | 50-150ms          | Query processing      |
|| ** - Retrieval**  | 200-500ms         | Hybrid search         |
|| ** - Rerank**     | 100-400ms         | BGE if enabled        |
|| ** - Generation** | 300-1000ms        | LLM call              |
|| ** - Vision Rendering** | +5-10ms/page | Page watermark overhead |
| **Throughput**    | 20-50 QPS         | Single instance       |
| **Memory Usage**  | 4-8GB             | Runtime               |
| Vector Dimension  | 768D              | Gemini embedding      |

> **⚠️ Performance Metrics Note**: These metrics were measured with **FAISS + offline BM25**. With modern **Hybrid Modern mode (Weaviate gRPC + OpenSearch + BGE Reranking enabled)**, performance characteristics are different:
> - **First query with BGE**: ~45-60s (model loading overhead)
> - **Subsequent queries**: ~2-5s total (retrieve ~1s + rerank ~0.5s + generate ~1-3s)
> - **BGE rerank overhead**: ~100-500ms depending on candidate count
> - **Top rerank scores**: 0.90-0.96 for highly relevant results
>
> **CAD-like Tag Extraction Performance** (if ENABLE_PID_TAGS=true):
> - **Gate evaluation**: < 300ms per file (sampling 5 pages)
> - **Layout extraction**: ~500ms per taggy page (vector-first)
> - **Tag extraction**: ~500ms per taggy page (CODE-anchored assembly)
> - **Crop generation**: ~50ms per tag (if enabled, lazy default)
> - **Total ingestion overhead**: +1-2s per taggy page (10 pages = ~12-15s)
> - **Query-time overhead**: +300-500ms for tag queries (parallel retrieval + RRF fusion)
> - **Storage**: ~3-8GB total (layouts ~500MB, tags ~100MB, crops ~2-5GB if not lazy)
>
> Recommend measuring in your specific environment.

---

## 🔗 RELATED DOCUMENTATION

### Core Documentation
- [README.md](README.md) - Quick start guide
- [CHANGELOG.md](CHANGELOG.md) - Version history and release notes
- [PID_IMPLEMENTATION_COMPLETE.md](PID_IMPLEMENTATION_COMPLETE.md) - P&ID enhancement implementation guide
- **[VISION_CITATION_ACCURACY.md](VISION_CITATION_ACCURACY.md)** - Vision citation accuracy improvements & page watermark feature (NEW)

### CAD-like Tag Extraction (NEW - v0.9.0)
- **[START_HERE_CAD_TAGS.md](START_HERE_CAD_TAGS.md)** - Quick start (3 commands)
- [CAD_TAG_EXTRACTION_QUICKSTART.md](CAD_TAG_EXTRACTION_QUICKSTART.md) - Complete setup guide
- [CAD_TAG_EXTRACTION_QUICK_REFERENCE.md](CAD_TAG_EXTRACTION_QUICK_REFERENCE.md) - 1-page cheat sheet
- [CAD_TAG_EXTRACTION_IMPLEMENTATION_SUMMARY.md](CAD_TAG_EXTRACTION_IMPLEMENTATION_SUMMARY.md) - Technical details
- [DEPLOYMENT_CHECKLIST_CAD_TAGS.md](DEPLOYMENT_CHECKLIST_CAD_TAGS.md) - Testing & deployment
- [PVCFC_CADlike_Tag_Extraction_Handoff.md](PVCFC_CADlike_Tag_Extraction_Handoff.md) - Original specification
- [Review_AI.md](Review_AI.md) - Implementation review & feasibility analysis
- [app/ingestion/tags/README.md](app/ingestion/tags/README.md) - Module API documentation

### Setup & Configuration
- [WEAVIATE_SETUP_GUIDE.md](DOCUMENTS_CHATBOX/docs/guides/WEAVIATE_SETUP_GUIDE.md) - Weaviate database setup
- [PID_RETRIEVAL_ENHANCEMENT.md](docs/guides/PID_RETRIEVAL_ENHANCEMENT.md) - P&ID enhancement user guide
- [env.example](env.example) - Environment variables reference
- [config/cadlike_gate.yaml](config/cadlike_gate.yaml) - CAD gate configuration
- [config/tag_grammar.yaml](config/tag_grammar.yaml) - Tag patterns & assembler tolerances
- [config/page_filters.yaml](config/page_filters.yaml) - Taggy page selection & exclusions

### Implementation Details
- [CONFIDENCE_DEFENSIVE_IMPROVEMENTS.md](DOCUMENTS_CHATBOX/docs/implementation/CONFIDENCE_DEFENSIVE_IMPROVEMENTS.md) - Defensive programming details
- [IMPLEMENTATION_GUIDE_PID.md](IMPLEMENTATION_GUIDE_PID.md) - P&ID deployment guide
- [PID_ENHANCEMENT_SUMMARY.md](PID_ENHANCEMENT_SUMMARY.md) - P&ID technical summary

### Testing & Evaluation
- [MANUAL_TESTING_CHECKLIST.md](DOCUMENTS_CHATBOX/docs/guides/MANUAL_TESTING_CHECKLIST.md) - Manual testing guide
- [tests/eval_pid_retrieval.py](tests/eval_pid_retrieval.py) - P&ID evaluation script
- [tests/ground_truth/pid_queries.json](tests/ground_truth/pid_queries.json) - P&ID test cases
- **[tests/smoke_test_tags.py](tests/smoke_test_tags.py)** - CAD tags smoke tests (12 queries)
- **[test_imports_cad_tags.py](test_imports_cad_tags.py)** - Verify tag extraction modules
- **[scripts/test_watermark_visual.py](scripts/test_watermark_visual.py)** - Vision watermark visual verification (NEW)
- **[scripts/test_vision_citation_accuracy.py](scripts/test_vision_citation_accuracy.py)** - Vision citation accuracy E2E tests (NEW)

### Scripts & Tools
- [scripts/README_PID_ENHANCEMENT.md](scripts/README_PID_ENHANCEMENT.md) - P&ID scripts guide
- [scripts/pid_enhancement_setup.ps1](scripts/pid_enhancement_setup.ps1) - Automated setup
- [scripts/pid_enhancement_test.ps1](scripts/pid_enhancement_test.ps1) - Quick testing
- **[scripts/opensearch/create_spatial_components_index.py](scripts/opensearch/create_spatial_components_index.py)** - Create pvcfc_pid_spatial_components index (Level 2)
- **Note**: Level 3 scripts (`create_tags_index.py`, `bulk_upsert_tags.py`) have been removed. Components are automatically indexed during ingestion.
- **[tools/test_tag_extraction.py](tools/test_tag_extraction.py)** - Test single PDF extraction

### Storage & Migration
- [STORAGE_MIGRATION_SUMMARY.md](STORAGE_MIGRATION_SUMMARY.md) - D: drive migration details
- [scripts/utilities/migrate_artifacts_to_d_drive.ps1](scripts/utilities/migrate_artifacts_to_d_drive.ps1) - Artifacts migration script
- [scripts/utilities/README_ARTIFACTS_MIGRATION.md](scripts/utilities/README_ARTIFACTS_MIGRATION.md) - Migration guide
- [ARTIFACTS_CLEANUP_RECOMMENDATIONS.md](ARTIFACTS_CLEANUP_RECOMMENDATIONS.md) - Cleanup guide


---

## 12. PHASE 9: DEEP DISCOVERY SEARCH (NEW v2.0)

### 12.1 Tổng quan

Deep Discovery Search là tính năng tìm kiếm keyword toàn diện, khác với RAG search:

| Đặc điểm | RAG Search | Deep Discovery Search |
|----------|------------|----------------------|
| Phương pháp | Vector similarity + BM25 | Keyword match only |
| Giới hạn kết quả | top_k (10-50) | Tất cả documents (max 10,000) |
| Sử dụng LLM | Có | Không |
| Mục đích | Trả lời câu hỏi | Tìm tất cả tài liệu chứa keyword |

### 12.2 API Endpoint

```
GET /api/search/documents
```

**Parameters:**
- `keyword` (required): Từ khóa tìm kiếm (1-200 ký tự)
- `category` (optional): Lọc theo category
- `doc_type` (optional): Lọc theo loại tài liệu
- `max_results` (optional): Số lượng tối đa (default: 1000, max: 10000)

### 12.3 OpenSearch Query Structure

```json
{
  "size": 0,
  "query": {
    "bool": {
      "must": [{"match": {"text": {"query": "KT06101", "operator": "and"}}}],
      "filter": [{"term": {"category": "VENDOR_EQUIPMENT"}}]
    }
  },
  "aggs": {
    "unique_documents": {
      "terms": {"field": "doc_id", "size": 10000},
      "aggs": {
        "doc_info": {"top_hits": {"size": 1, "_source": ["doc_id", "file_name", "category", "doc_type", "page", "text"]}},
        "occurrence_count": {"value_count": {"field": "_id"}}
      }
    }
  }
}
```

### 12.4 Files

- `app/services/deep_search.py` - DeepSearchService implementation
- `app/api/routers/search.py` - API endpoint (prefix: `/api/search`)

---

## 13. PHASE 10: INTELLIGENT CLASSIFICATION (NEW v2.0)

### 13.1 Document Taxonomy (4-Category System)

```
├── ENGINEERING_DESIGN
│   ├── P&ID
│   ├── Drawing
│   └── Technical Data
│
├── VENDOR_EQUIPMENT
│   ├── Datasheet
│   ├── Material Partlist
│   └── Vendor Manual
│
├── OPERATIONS_MAINTENANCE
│   ├── Operation Instruction
│   ├── Maintenance Instruction
│   ├── Maintenance History
│   └── Inventory
│
├── SAFETY_MANAGEMENT
│   ├── MOC
│   ├── RCA
│   └── Pictures
│
└── UNCATEGORIZED
    └── Unknown
```

### 13.2 Classification Pipeline

```
PDF Upload
    │
    ▼
┌─────────────────────────┐
│  Adaptive Page Sampler  │  ← Lấy mẫu 10 trang (Head-Body-Tail)
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│    CADLikeGate Check    │  ← Guardrail cho P&ID
└─────────────────────────┘
    │
    ├── CAD_score >= 0.55 ──► Force P&ID Classification
    │
    └── CAD_score < 0.55
            │
            ▼
    ┌─────────────────────────┐
    │  Gemini 2.5 Flash AI    │  ← Multimodal classification
    └─────────────────────────┘
            │
            ├── confidence >= 0.5 ──► Store Classification
            │
            └── confidence < 0.5 ──► UNCATEGORIZED + NEEDS_REVIEW
```

### 13.3 Adaptive Page Sampling

| Số trang PDF | Strategy | Pages sampled |
|--------------|----------|---------------|
| ≤ 10 pages | All | Tất cả trang |
| > 10 pages | Head-Body-Tail | 10 trang |

**Head-Body-Tail Strategy:**
- **Head (3 pages)**: Trang 1, 2, 3 - Cover, TOC
- **Body (5 pages)**: 5 trang phân bố đều ở giữa
- **Tail (2 pages)**: Trang N-1, N - Appendix, signatures

### 13.4 Metadata Schema

**OpenSearch rag_chunks Index:**
- `category` (keyword): ENGINEERING_DESIGN, VENDOR_EQUIPMENT, etc.
- `doc_type` (keyword): P&ID, Datasheet, Vendor Manual, etc.
- `classification_status` (keyword): classified, needs_review, pending
- `classification_confidence` (float): 0.0 - 1.0
- `classification_method` (keyword): cadlike_gate, ai_classifier, manual

### 13.5 Batch Re-classification

**Script:** `scripts/utilities/batch_reclassify.py`

```powershell
python scripts/utilities/batch_reclassify.py
```

**Results (77 documents):**
- P&ID via CADLikeGate: 39 documents
- AI Classified: 38 documents
- Failures: 0
- Chunks updated: 6,470

### 13.6 Files

- `app/classification/taxonomy.py` - DocumentTaxonomy class
- `app/classification/sampler.py` - AdaptivePageSampler
- `app/classification/classifier.py` - DocumentClassifier (Gemini AI)
- `app/classification/pipeline.py` - ClassificationPipeline
- `app/api/routers/classification.py` - Classification API endpoints
- `scripts/utilities/batch_reclassify.py` - Batch re-classification script

---
