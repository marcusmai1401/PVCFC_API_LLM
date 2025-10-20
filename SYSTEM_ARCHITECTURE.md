# SYSTEM ARCHITECTURE - PVCFC RAG SYSTEM

**Version**: 0.9.0
**Last Updated**: 2025-10-17
**Document**: Complete Pipeline & Architecture Description (Production-Ready with CAD-like Tag Extraction)

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
11. [Components Deep Dive](#11-components-deep-dive)
12. [Error Handling & Resilience](#12-error-handling--resilience)
13. [Performance & Optimization](#13-performance--optimization)

---

## 1. TỔNG QUAN HỆ THỐNG

### 1.1 Mục tiêu

Hệ thống RAG (Retrieval-Augmented Generation) phục vụ tra cứu, trích xuất và hỏi-đáp kỹ thuật trên tài liệu PVCFC với:
- ✅ **Độ tin cậy cao**: Citations có doc_id + page number
- ✅ **Multimodal**: Hỗ trợ cả text và vision (PDF pages)
- ✅ **Production-ready**: Weaviate + OpenSearch, defensive programming
- ✅ **Scalable**: Xử lý hàng nghìn tài liệu, hỗ trợ mở rộng

### 1.2 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI + Python 3.11 | API server |
| **Vector DB** | Weaviate (gRPC) | Semantic search |
| **Keyword Search** | OpenSearch (BM25) | Keyword search |
| **LLM** | Gemini 2.5 Pro/Flash | Generation |
| **Embedding** | Gemini Embedding 001 (768D) | Text vectorization |
|| **Reranker** | BGE CrossEncoder (optional, configurable) | Result reranking |
| **OCR** | PaddleOCR v2.7.3 (vie+eng, GPU-accelerated) | Scanned PDF processing |
| **UI** | Streamlit | Testing & debugging |
| **Monitoring** | Loguru + Metrics | Logging & observability |

> **Note**: BGE reranking is **OPTIONAL** and can be enabled via `ENABLE_BGE_RERANK=true` in .env. Currently **ENABLED** in production config. Adds ~100-400ms latency but improves semantic ranking accuracy.

> **Note**: Hybrid Modern mode (`USE_HYBRID_MODERN=true`) is the **default production mode**, combining Weaviate + OpenSearch for best performance.

### 1.3 Architecture Diagram

```
┌─────────────┐
│  Documents  │  (PDF files in D:\Data_Raw)
└──────┬──────┘
       │
       ↓
┌───────────────────────────────────────────────────────────────────┐
│              OFFLINE PIPELINE (Build Time)                        │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────┐    ┌──────────┐    ┌──────────────┐               │
│  │  Ingest    │ →  │  Chunk   │ →  │   Dedup      │               │
│  │ (PaddleOCR)│    │(Semantic)│    │  (content)   │               │
│  └──────┬─────┘    └──────────┘    └──────┬───────┘               │
│         │                                  │                      │
│         │ P&ID Detection                   │                      │
│         ↓                                  ↓                      │
│  ┌──────────────────────────┐   ┌──────────────┐                  │
│  │  CAD-like Gate           │   │  chunks.jsonl│                  │
│  │  (Auto-detect P&ID)      │   │              │                  │
│  └──────┬───────────────────┘   └──────┬───────┘                  │
│         │ is_cadlike=true              │                          │
│         ↓                              │                          │
│  ┌──────────────────────────┐          │                          │
│  │  Page Layout Builder     │          │                          │
│  │  • PyMuPDF vector text   │          │                          │
│  │  • OCR fallback          │          │                          │
│  │  • Vector drawings       │          │                          │
│  └──────┬───────────────────┘          │                          │
│         │                              │                          │
│         ↓                              │                          │
│  ┌──────────────────────────┐          │                          │
│  │  Tag Extractor           │          │                          │
│  │  • CODE-anchored triplet │          │                          │
│  │  • AREA-CODE-NUM-SUFFIX  │          │                          │
│  │  • Exclusion zones       │          │                          │
│  └──────┬───────────────────┘          │                          │
│         │                              │                          │
│         ↓                              ↓                          │
│  ┌──────────────┐           ┌──────────────────────────┐          │
│  │  tags.jsonl  │           │   Standard Indexing      │          │
│  │  telemetry   │           │                          │          │
│  └──────┬───────┘           └──────┬───────────────────┘          │
│         │                          │                              │
│         ↓                    ┌─────┴──────────┐                   │
│  ┌──────────────────┐        ↓                ↓                   │
│  │  OpenSearch      │  ┌──────────────┐  ┌──────────────┐         │
│  │  Index:          │  │  Weaviate    │  │  OpenSearch  │         │
│  │  pvcfc_pid_tags  │  │  Collection  │  │  Index       │         │
│  │  (Tag sidecar)   │  │  "Chunk"     │  │  "rag_chunks"│         │
│  └──────────────────┘  └──────────────┘  └──────────────┘         │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
                           │
                           ↓
┌───────────────────────────────────────────────────────────────────┐
│                 ONLINE PIPELINE (Query Time)                      │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐                                                     │
│  │  Query   │  "What is 04-PIC-2046C max pressure?"               │
│  └────┬─────┘                                                     │
│       │                                                           │
│       ↓                                                           │
│  ┌─────────────────────────────────────────┐                      │
│  │   Query Transform + P&ID Enhancement    │                      │
│  │  • Normalize, intent detection          │                      │
│  │  • Tag detection: [04-PIC-2046C]        │                      │
│  │  • Variants: [PIC2046C, 04PIC2046C, ... │                      │
│  │  • Query type: tag_focused              │                      │
│  └──────────────────┬──────────────────────┘                      │
│                     │                                             │
│                     ↓                                             │
│  ┌────────────────────────────────────────────┐                   │
│  │      HYBRID RETRIEVAL (Parallel)           │                   │
│  │                                            │                   │
│  │  ┌──────────────┐      ┌──────────────┐    │                   │
│  │  │  Weaviate    │      │  OpenSearch  │    │                   │
│  │  │  (Semantic)  │      │   (BM25)     │    │                   │
│  │  │  + Tag       │      │  + Tag       │    │                   │
│  │  │    filter    │      │    boosting  │    │                   │
│  │  └──────┬───────┘      └──────┬───────┘    │                   │
│  │         │                     │            │                   │
│  │         └──────────┬──────────┘            │                   │
│  │                    ↓                       │                   │
│  │         ┌────────────────────┐             │                   │
│  │         │   Adaptive RRF     │             │                   │
│  │         │   (Query-type      │             │                   │
│  │         │    aware weights)  │             │                   │
│  │         └──────────┬─────────┘             │                   │
│  └────────────────────┼───────────────────────┘                   │
│                       │                                           │
│                       ↓                                           │
│  ┌─────────────────────────────────────┐                          │
│  │   PID Tag Reranking (Optional)      │                          │
│  │  • Exact metadata match: ×10.0      │                          │
│  │  • Text phrase match: ×5.0          │                          │
│  │  • Fuzzy match (≥90%): ×2.0-3.0     │                          │
│  │  • Tag-parameter proximity: ×3.0    │                          │
│  └──────────────────┬──────────────────┘                          │
│                     │                                             │
│                     ↓                                             │
│  ┌───────────────────────────────────┐                            │
│  │   BGE CrossEncoder Rerank         │  (Currently ENABLED)       │
│  │   BAAI/bge-reranker-base          │                            │
│  └────────────────┬──────────────────┘                            │
│                   │                                               │
│                   ↓                                               │
│  ┌────────────────────────────────┐                               │
│  │   Top-K Reranked Results       │  (k=8 default)                │
│  └──────────────┬─────────────────┘                               │
│                 │                                                 │
│                 ↓                                                 │
│  ┌────────────────────────────────────┐                           │
│  │      GENERATION PIPELINE           │                           │
│  │                                    │                           │
│  │  ┌──────────────────────────┐      │                           │
│  │  │ Strategy: Text or Vision?│      │                           │
│  │  └────────┬────────┬────────┘      │                           │
│  │           │        │               │                           │
│  │      Text │        │ Vision        │                           │
│  │           ↓        ↓               │                           │
│  │  ┌─────────────┐  ┌─────────────┐  │                           │
│  │  │ Text Models │  │ Gemini 2.5  │  │                           │
│  │  │ Production: │  │ Pro (Vision)│  │                           │
│  │  │ 2.5 Pro     │  │ + PDF Pages │  │                           │
│  │  │ Light Mode: │  │             │  │                           │
│  │  │ 2.5 Flash   │  │             │  │                           │
│  │  └──────┬──────┘  └──────┬──────┘  │                           │
│  │         │                │         │                           │
│  │         └────────┬───────┘         │                           │
│  │                  ↓                 │                           │
│  │        ┌──────────────────┐        │                           │
│  │        │ Answer+Citation  │        │                           │
│  │        │   Extraction     │        │                           │
│  │        └────────┬─────────┘        │                           │
│  │                 ↓                  │                           │
│  │        ┌──────────────────┐        │                           │
│  │        │ Post-validation  │        │                           │
│  │        │  (CiteFix-lite)  │        │                           │
│  │        └────────┬─────────┘        │                           │
│  │                 ↓                  │                           │
│  │        ┌──────────────────┐        │                           │
│  │        │ Confidence Score │        │                           │
│  │        │   Calculation    │        │                           │
│  │        └────────┬─────────┘        │                           │
│  └─────────────────┼──────────────────┘                           │
│                    ↓                                              │
│  ┌───────────────────────────────┐                                │
│  │    BUILD API RESPONSE         │                                │
│  │  • Answer text                │                                │
│  │  • Citations (doc_id + page)  │                                │
│  │  • Confidence [0,1]           │                                │
│  │  • Metadata                   │                                │
│  │  • Timing breakdown           │                                │
│  └─────────────────┬─────────────┘                                │
│                    │                                              │
└────────────────────┼──────────────────────────────────────────────┘
                     ↓
              ┌──────────────┐
              │ JSON Response│
              └──────────────┘
```

> **P&ID Tag Extraction Note**: The system includes a complete **CAD-like Tag Extraction pipeline** (disabled by default, enable via `ENABLE_PID_TAGS=true`):
> - **Offline**: CADLikeGate (auto-detect via 8 features, S≥0.60) → PageLayoutBuilder (vector-first PyMuPDF + PP-OCRv5 fallback) → TagExtractor (CODE-anchored AREA-CODE-NUM-SUFFIX assembly) → crops/*.png (bbox evidence) → OpenSearch `pvcfc_pid_tags` sidecar index
> - **Online**: Query tag detection → Parallel retrieval (tags + chunks) → RRF fusion → Rerank → Attach crop_path for vision citations
> - **Configuration**: `config/cadlike_gate.yaml`, `config/tag_grammar.yaml`, `config/page_filters.yaml`, `config/tags_index_mapping.json`
> - **Artifacts**: `D:\PVCFC_Artifacts\` → `entities/tags.jsonl`, `page_layout/*.json`, `crops/*.png`, `logs/tag_extraction_telemetry.jsonl`
> - **Implementation**: `app/ingestion/tags/` (orchestrator, tag_extractor, crops), `app/ingestion/cadlike_gate.py`, `app/ingestion/layout/`, `app/rag/hybrid_with_tags_retriever.py`
> - **Quick Start**: See `START_HERE_CAD_TAGS.md`, `CAD_TAG_EXTRACTION_QUICKSTART.md`

---

## 2. DATA FLOW - LUỒNG DỮ LIỆU HOÀN CHỈNH

### 2.1 Build Time (Offline)

```
RAW PDF FILES
    ↓
[1] INGESTION
    • Parse PDF (PyMuPDF)
    • OCR if needed (PaddleOCR v2.7.3 GPU)
    • Extract text + metadata
    ↓
[2] CHUNKING (SEMANTIC STRATEGY)
    • Semantic chunking (respects paragraphs/sentences)
    • Size target: ~1000 chars, overlap: 200
    • Keep page metadata
    ↓
[3] DEDUPLICATION
    • content_hash = SHA1(normalized_text)
    • Keep 1 representative per hash
    ↓
[4] INDEXING
    ├── Weaviate: Vector embeddings (768D) → Collection "Chunk"
    └── OpenSearch: BM25 inverted index → Index "rag_chunks"
    ↓
[5] P&ID TAG EXTRACTION (PARALLEL, IF ENABLE_PID_TAGS=true)
    ↓
    [5.1] CAD-LIKE GATE (app/ingestion/cadlike_gate.py)
        • Sample pages: [1,2,3,mid,last] (5 pages default)
        • Compute score S = Σ(weight_i × feature_i):
          - Producer/Creator keywords (AutoCAD, Bentley, etc.)
          - Geometry density (vector paths/lines per area)
          - Short CAPS rate (2-4 letter tokens)
          - 3-piece tag regex hits (dd CC-CC ddddd)
          - Technical suffixes (A/B/C, 2oo3, -201B)
          - Large page size (A1/A0)
          - Rotated text spans
          - Leader patterns
        • Threshold: S ≥ 0.60 → CAD-like
        • Gray zone [0.45, 0.60): boost if filename has P&ID/PFD/ISO keywords
        • Select "taggy pages" (regex_hits≥3 OR code_tokens≥4)
        ↓ is_cadlike=true
    [5.2] PAGE LAYOUT EXTRACTION (app/ingestion/layout/page_layout_builder.py)
        • Vector-first: PyMuPDF text spans (bbox, font_size, rotation)
        • Vector drawings: lines, circles, rectangles, paths
        • OCR fallback: PP-OCRv5 if vector text < 100 chars
        • Normalize engineering spacing ("3.9  MPag" → "3.9 MPag")
        • Save to page_layout/page_{doc_id}_{page}.json
        ↓
    [5.3] TAG EXTRACTION (app/ingestion/tags/tag_extractor.py)
        • Token role classification:
          - AREA: ^\d{2}$
          - CODE: ^[A-Z]{2,4}$ (whitelist: PAL, PSAL, PT, PI, FIC, etc.)
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
        • Bulk upsert: entities/tags.jsonl → OpenSearch "pvcfc_pid_tags"
        • Deterministic _id: {doc_id}#{page}#{tag}
        • Log telemetry: logs/tag_extraction_telemetry.jsonl
          - cadlike_score, tags_found_total, p50/p90, ocr_ratio, warnings
        ↓
OUTPUT:
    • chunks.jsonl (deduplicated chunks)
    • doc_id_map.json (doc_id → pdf_path mapping)
    • Weaviate collection "Chunk" (vectors)
    • OpenSearch index "rag_chunks" (keywords)

    [NEW] P&ID TAG EXTRACTION OUTPUTS (if ENABLE_PID_TAGS=true):
    • entities/tags.jsonl (instrument tags with bbox)
    • page_layout/*.json (text spans + vector drawings per page)
    • crops/*.png (bbox PNG crops - if not lazy)
    • logs/tag_extraction_telemetry.jsonl (runtime metrics + warnings)
    • OpenSearch index "pvcfc_pid_tags" (tag sidecar index)
```

> **Index Directory Note**: Default config uses artifacts/index_production, but current .env overrides to data/indexes. Check your environment.

> **P&ID Artifacts Location**: P&ID tag extraction artifacts are stored in `D:\PVCFC_Artifacts\` (configured via .env `ARTIFACTS_DIR=D:\PVCFC_Artifacts`):
> - `entities/tags.jsonl`: Extracted instrument tags (1 JSON object per tag, e.g., {"doc_id": "...", "page": 5, "tag": "04 PSAL 2207", "parts": {...}, "bbox": [...], "confidence": 0.96})
> - `page_layout/*.json`: Page-level layout data (text spans with bbox/font/rotation + vector drawings)
> - `crops/*.png`: PNG crops of tag bboxes for vision citations (lazy mode: generated on-demand)
> - `logs/tag_extraction_telemetry.jsonl`: Extraction metrics per document (cadlike_score, tags_found, warnings, elapsed_sec)

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
    │   • Embed query → 768D vector
    │   • near_vector search
    │   • [NEW] Tag filter (if P&ID enabled + tags detected)
    │   • Top 50 results
    │   • Weight: varies by query type (0.3-1.0)
    │
    └── OpenSearch BM25 (keyword)
        • Tokenize query
        • BM25 scoring (k1=1.2, b=0.75)
        • [NEW] Tag boosting (if P&ID enabled):
          - Metadata exact: × 10.0
          - Text phrase: × 5.0
          - Fuzzy match: × 2.0-3.0
        • Top 50 results
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
[4] BGE RERANKING (Optional - Currently ENABLED)
    • BAAI/bge-reranker-base CrossEncoder
    • Score each (query, doc) pair
    • Re-sort by semantic relevance
    • Top-k selection (k=10 default)
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
    │   • Send to Gemini 2.5 Pro (multimodal)
    │   • Extract answer + citations
    │
    └── Text Generation
        • Context = concatenated chunks
        • Model selection by tier:
          - Production mode (default): Gemini 2.5 Pro
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

### 3.1 Input
- **Source**: `D:\Data_Raw` (recursive scan)
- **Format**: PDF (vector text or scanned images)
- **Size**: Thousands of files, various sizes

### 3.2 Processing Steps

#### Step 1: File Discovery
```python
# Recursive scan
for pdf_file in scan_directory("D:\\Data_Raw"):
    if is_valid_pdf(pdf_file):
        process_document(pdf_file)
```

#### Step 2: PDF Parsing with PaddleOCR
```python
# Try vector text first
doc = fitz.open(pdf_path)
text = extract_text(doc)

if not has_text(text):
    # Fallback to PaddleOCR (GPU-accelerated)
    text = ocr_with_paddleocr(
        pdf_path,
        lang="vie+eng",
        use_gpu=True,  # GPU support via paddlepaddle-gpu
        det_algorithm="DB",
        rec_algorithm="SVTR_LCNet"
    )
```

> **OCR Note**: System uses **PP-OCRv5 models** (detection + classification) with PaddleOCR 2.7.3 library, GPU-accelerated via paddlepaddle-gpu 2.6.2. NOT Tesseract. See `app/ingestion/paddle_ocr_config.py` for configuration.

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

### 4.1 Chunking Strategy (SEMANTIC, NOT FIXED)

```python
# Semantic chunking (respects paragraph and sentence boundaries)
# Default strategy in TextChunker class
from app.ingestion.text_chunker import TextChunker

chunker = TextChunker(
    chunk_size=1000,       # Target size in characters
    chunk_overlap=200,      # Overlap between chunks
    chunking_strategy="semantic"  # Options: "semantic", "sentence", "fixed"
)

# Semantic chunking process:
# 1. Split text by paragraphs (\n\n+)
# 2. If paragraph > chunk_size, split by sentences
# 3. Build chunks respecting boundaries
# 4. Add overlap from previous chunk
# 5. Extract page metadata from content markers (<!-- Page X -->)

chunks = chunker.chunk_text(
    text=page_text,
    doc_id=doc_id,
    metadata={"page": page_num, "doc_type": "manual"},
    page_nums=[page_num]
)
```

> **Chunking Note**: System uses **semantic chunking by default**, NOT simple fixed-size splitting. This preserves document structure and improves retrieval quality.

### 4.2 Deduplication

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

### 4.3 Weaviate Indexing

```python
# Connect to Weaviate
client = weaviate.connect_to_local(
    host="localhost",
    port=8080,
    grpc_port=50051
)

# Create collection with name "Chunk" (not "PVCFCDocuments")
collection = client.collections.create(
    name="Chunk",  # Production collection name
    vectorizer_config=None,  # Manual vectorization
    properties=[
        Property(name="text", data_type=DataType.TEXT),
        Property(name="doc_id", data_type=DataType.TEXT),
        Property(name="page", data_type=DataType.INT),
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

### 4.4 OpenSearch Indexing

```python
# Create index with BM25 parameters (NO epsilon in OpenSearch)
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
                "text": {"type": "text", "similarity": "bm25_custom"},
                "doc_id": {"type": "keyword"},
                "page": {"type": "integer"},
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
pytest tests\test_pid_query_enhancer.py -v
pytest tests\test_pid_tag_reranker.py -v
pytest tests\integration\test_pid_retrieval_integration.py -v
```

### 6.13 Graceful Degradation

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

### 7.1 Parallel Retrieval

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

> **BGE Reranking Note**: This is **OPTIONAL** and controlled by `ENABLE_BGE_RERANK` in .env. **Currently ENABLED** in production config (`ENABLE_BGE_RERANK=true`). Uses `BAAI/bge-reranker-base` model. Adds 100-400ms latency but significantly improves semantic ranking accuracy (measured: ~0.96 top scores vs ~0.06 without). Model loads on first query (~3-5s), subsequent queries fast (~0.5s rerank time).

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

## 11. COMPONENTS DEEP DIVE

### 11.1 LLM Service

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

## 12. ERROR HANDLING & RESILIENCE

### 12.1 Graceful Degradation

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

### 12.2 Validation & Logging

```python
# Always validate and log invalid states
if confidence is None or not (0 <= confidence <= 1):
    logger.error(
        f"Invalid confidence: {confidence}. "
        f"This indicates a bug. Clamping for stability."
    )
    confidence = max(0.0, min(1.0, float(confidence or 0.0)))
```

### 12.3 Retry Logic

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(ConnectionError)
)
def embed_with_retry(texts: List[str]) -> List[np.ndarray]:
    return embedding_service.embed_texts(texts)
```

### 12.4 Degrade Mode

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

## 13. PERFORMANCE & OPTIMIZATION

### 13.1 Retrieval Caching

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

### 13.2 Batching

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

### 13.3 Async Processing

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

### 13.4 Vision Citation Accuracy Improvements

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

### 13.5 Tags Endpoint (Metadata API)

**Implementation**: `app/api/routers/tags.py`

**NEW endpoint** added in P&ID enhancement for listing all equipment tags in the corpus.

**Endpoint**: `GET /tags`

**Purpose**:
- Tag auto-complete for search UI
- Tag validation before queries
- Corpus overview and statistics

**Response Example**:
```json
{
  "tags": [
    "E04217", "E04218", "E04219",
    "P04201A", "P04201B", "P04202",
    "K06101", "K06102",
    "V05301", "V05302",
    ...
  ],
  "count": 1234,
  "source": "opensearch",
  "timestamp": "2025-10-16T10:30:00Z"
}
```

**Implementation** (using OpenSearch aggregation):
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
| **Ingestion**     | ~5 docs/sec       | With PaddleOCR GPU    |
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
- **[scripts/opensearch/create_tags_index.py](scripts/opensearch/create_tags_index.py)** - Create pvcfc_pid_tags index
- **[scripts/opensearch/bulk_upsert_tags.py](scripts/opensearch/bulk_upsert_tags.py)** - Bulk load tags to index
- **[tools/test_tag_extraction.py](tools/test_tag_extraction.py)** - Test single PDF extraction

### Storage & Migration
- [STORAGE_MIGRATION_SUMMARY.md](STORAGE_MIGRATION_SUMMARY.md) - D: drive migration details
- [scripts/utilities/migrate_artifacts_to_d_drive.ps1](scripts/utilities/migrate_artifacts_to_d_drive.ps1) - Artifacts migration script
- [scripts/utilities/README_ARTIFACTS_MIGRATION.md](scripts/utilities/README_ARTIFACTS_MIGRATION.md) - Migration guide
- [ARTIFACTS_CLEANUP_RECOMMENDATIONS.md](ARTIFACTS_CLEANUP_RECOMMENDATIONS.md) - Cleanup guide
