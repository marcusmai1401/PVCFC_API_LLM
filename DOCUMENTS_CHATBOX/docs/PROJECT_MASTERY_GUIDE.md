# PROJECT MASTERY GUIDE - PVCFC RAG SYSTEM

**Version**: 1.0.0
**Date**: 2025-10-12
**Purpose**: Hướng dẫn toàn diện để nắm vững dự án từ A→Z
**Target Audience**: Developers, DevOps, Technical Leads

---

## 📋 MỤC LỤC

1. [Tổng quan dự án](#1-tổng-quan-dự-án)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Tech Stack & Dependencies](#3-tech-stack--dependencies)
4. [Data Flow - Pipeline hoàn chỉnh](#4-data-flow---pipeline-hoàn-chỉnh)
5. [Cấu trúc thư mục](#5-cấu-trúc-thư-mục)
6. [Modules chính](#6-modules-chính)
7. [Cấu hình & Environment](#7-cấu-hình--environment)
8. [Workflows quan trọng](#8-workflows-quan-trọng)
9. [Testing & Evaluation](#9-testing--evaluation)
10. [Deployment & Operations](#10-deployment--operations)
11. [Troubleshooting](#11-troubleshooting)
12. [Roadmap & Future Work](#12-roadmap--future-work)

---

## 1. TỔNG QUAN DỰ ÁN

### 1.1 Mục tiêu

Hệ thống **RAG (Retrieval-Augmented Generation)** phục vụ tra cứu, trích xuất và hỏi-đáp kỹ thuật trên tài liệu PVCFC với:

- ✅ **Độ tin cậy cao**: Citations có doc_id + page number (1-based)
- ✅ **Multimodal**: Hỗ trợ cả text và vision (PDF pages)
- ✅ **Production-ready**: Weaviate + OpenSearch, defensive programming
- ✅ **Scalable**: Xử lý hàng nghìn tài liệu, hỗ trợ mở rộng

### 1.2 Use Cases Chính

1. **Tìm & Trích xuất**: Nhanh chóng tìm đúng tài liệu và trang nhắc tới nội dung câu hỏi
2. **Hỏi-đáp có trích dẫn**: Trả lời ngắn gọn, đính kèm nguồn (doc_id + page) để kiểm chứng
3. **Báo cáo tự động**: Sinh báo cáo từ ngôn ngữ tự nhiên (AI), có danh mục trích dẫn
4. **Metadata tự động**: Suy luận equipment_id, doc_type, vendor từ ngữ cảnh và nội dung

### 1.3 Phạm vi Dữ liệu (V1)

- **Nguồn**: `D:\Data_Raw` (ổ rời)
- **Format**: PDF (vector text hoặc scanned images)
- **Số lượng**: Hàng nghìn PDFs
- **Xử lý**: OCR khi cần (vie+eng), dedup 100% nội dung
- **Office**: Chưa bật ở V1, nhưng kiến trúc đã sẵn sàng mở rộng

### 1.4 Các Giai đoạn Phát triển

- **Phase 0** (2025-09-15): Initial setup, config management
- **Phase 1** (2025-10-05): Core RAG pipeline (ingestion, indexing, basic Q&A)
- **Phase 2** (2025-10-08): Enhanced retrieval (hybrid BM25+FAISS, vision, HyDE)
- **Phase 3** (2025-10-09): BGE CrossEncoder reranking, IEEE citation
- **Phase 4** (2025-10-10): Weaviate integration (production vector DB)
- **Phase 5** (2025-10-11): OpenSearch BM25, Hybrid Modern mode
- **Phase 6** (2025-10-11): Defensive improvements, confidence validation

---

## 2. KIẾN TRÚC HỆ THỐNG

### 2.1 Architecture Diagram (High-Level)

```
┌─────────────────────────────────────────────────────────────────┐
│                        OFFLINE PIPELINE                          │
│                     (Build Time / Ingestion)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  D:\Data_Raw (PDFs)                                             │
│       ↓                                                         │
│  [1] INGESTION (tools/ingest.py)                                │
│       • Parse PDF (PyMuPDF)                                     │
│       • OCR (Tesseract/PaddleOCR) if needed                     │
│       • Extract tables (pdfplumber)                             │
│       • Chunking (1000 chars, overlap 200)                      │
│       • Dedup (content_hash SHA1)                               │
│       ↓                                                         │
│  [2] OUTPUTS                                                    │
│       • chunks.jsonl (deduplicated chunks)                      │
│       • doc_id_map.json (doc_id → pdf_path)                     │
│       • quarantine.jsonl (failed files)                         │
│       • manifests/ (ingestion metadata)                         │
│       ↓                                                         │
│  [3] INDEXING                                                   │
│       • Weaviate: Vector embeddings (768D, Gemini)              │
│       • OpenSearch: BM25 inverted index (k1=1.2, b=0.75)        │
│       • FAISS (legacy): Vector index (backup mode)              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                         ONLINE PIPELINE                          │
│                      (Query Time / Serving)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  USER QUERY: "What is K06101 max pressure?"                     │
│       ↓                                                         │
│  [1] QUERY TRANSFORM (app/rag/query_transform.py)               │
│       • Normalize: lowercase, spaces                            │
│       • Intent detection: ASK|LOCATE|EXPLAIN|REPORT             │
│       • Extract filters: equipment_id, doc_type                 │
│       • HyDE (optional): Generate hypothetical document         │
│       ↓                                                         │
│  [2] HYBRID RETRIEVAL (Parallel)                                │
│       ┌────────────────────────────────────┐                   │
│       │ Modern Mode (USE_HYBRID_MODERN=true)                    │
│       ├────────────────────────────────────┤                   │
│       │  • Weaviate Search (semantic)      │                   │
│       │    - Embed query → 768D vector     │                   │
│       │    - near_vector search            │                   │
│       │    - Top 50 results                │                   │
│       │                                    │                   │
│       │  • OpenSearch BM25 (keyword)       │                   │
│       │    - Tokenize query                │                   │
│       │    - BM25 scoring                  │                   │
│       │    - Top 50 results                │                   │
│       │                                    │                   │
│       │  • RRF Fusion (k=60)               │                   │
│       │    - Merge scores from both        │                   │
│       │    - Combined ranking              │                   │
│       └────────────────────────────────────┘                   │
│       ↓                                                         │
│  [3] BGE RERANKING (Optional)                                   │
│       • CrossEncoder (BAAI/bge-reranker-base)                   │
│       • Score each (query, doc) pair                            │
│       • Re-sort by semantic relevance                           │
│       • Top-k selection (k=8)                                   │
│       ↓                                                         │
│  [4] GENERATION STRATEGY                                        │
│       ┌─────────────────┬──────────────────┐                   │
│       │ Text-only       │ Vision (Multimodal)                  │
│       ├─────────────────┼──────────────────┤                   │
│       │ • Gemini Flash  │ • Gemini 2.5 Pro │                   │
│       │ • Context: text │ • Context: text  │                   │
│       │   chunks        │   + PDF pages    │                   │
│       │                 │   (DPI=200 JPEG) │                   │
│       └─────────────────┴──────────────────┘                   │
│       ↓                                                         │
│  [5] POST-PROCESSING                                            │
│       • Citation extraction ([Doc N, p.X])                      │
│       • Citation validation (CiteFix-lite)                      │
│       • Confidence calculation [0,1]                            │
│       • IEEE-style conversion (optional)                        │
│       ↓                                                         │
│  [6] RESPONSE                                                   │
│       • Answer text                                             │
│       • Citations: [{doc_id, page, pdf_path, confidence}]       │
│       • Metadata: latency, model, vision_pages, trace_id        │
│       • Confidence: [0, 1] (validated & clamped)                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Map

| Layer | Component | Technology | Purpose |
|-------|-----------|-----------|---------|
| **API** | FastAPI | Python 3.11 | REST endpoints |
| **UI** | Streamlit | Streamlit | Testing & debugging |
| **Vector DB** | Weaviate | Docker + gRPC | Semantic search |
| **Keyword Search** | OpenSearch | Docker | BM25 keyword search |
| **LLM** | Gemini 2.5 | Google API | Pro (vision), Flash (text) |
| **Embedding** | Gemini Embedding | Google API | 768D vectors |
| **Reranker** | BGE CrossEncoder | HuggingFace | Semantic reranking |
| **OCR** | Tesseract/Paddle | Local | Scanned PDF processing |
| **Storage** | JSON/JSONL | Local files | Chunks, manifests, doc_id_map |

---

## 3. TECH STACK & DEPENDENCIES

### 3.1 Core Dependencies

```txt
# API & Framework
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
python-dotenv==1.0.1

# LLM & Embeddings
google-genai>=1.36.0          # Gemini (structured output)
openai==1.3.0                 # Optional OpenAI support

# Document Processing
pymupdf==1.26.4               # PDF parsing
pdfplumber==0.11.4            # Table extraction
paddleocr==2.7.3              # OCR (production)
paddlepaddle-gpu==2.6.2       # OCR backend

# Vector Search & Retrieval
weaviate-client>=4.17.0       # Weaviate vector DB
opensearch-py==3.0.0          # OpenSearch BM25
faiss-cpu==1.8.0.post1        # FAISS (legacy)
rank-bm25==0.2.2              # Offline BM25

# ML & Embeddings
sentence-transformers==3.0.1  # Local embeddings
transformers==4.36.0          # CrossEncoder reranking
torch==2.1.0                  # PyTorch backend

# Utilities
numpy==1.26.4
pandas==2.2.2
loguru==0.7.2
tenacity==8.2.3              # Retry logic
```

### 3.2 Docker Services

- **Weaviate**: `docker-compose-weaviate.yml` (port 8080, gRPC 50051)
- **OpenSearch**: `docker-compose.yml` (port 9200, Dashboards 5601)

### 3.3 Python Version

- **Required**: Python 3.11
- **Virtual Environment**: `.venv` (recommended)

---

## 4. DATA FLOW - PIPELINE HOÀN CHỈNH

### 4.1 Build Time (Offline)

```
RAW PDF FILES (D:\Data_Raw)
    ↓
[1] INGESTION
    Command: python tools/ingest.py \
               --source-dir D:\Data_Raw \
               --output-dir artifacts/ingestion_production \
               --workers 4 \
               --enable-ocr --ocr-lang "vie+eng" \
               --extract-tables

    Process:
    • Parse PDF (vector text prioritized)
    • OCR if no extractable text (DPI 300, auto-scale)
    • Extract tables (min 2x2)
    • Normalize text
    • content_hash = SHA1(normalized_text)

    Output:
    • chunks.jsonl (~12,500 chunks for 150 PDFs)
    • doc_id_map.json (doc_id → pdf_path mapping)
    • quarantine.jsonl (failed files)
    ↓
[2] INDEXING
    Command: python tools/ops/build_production_indices.py

    Process:
    • Embed chunks → 768D vectors (Gemini)
    • Insert to Weaviate collection
    • Insert to OpenSearch index (BM25)

    Output:
    • Weaviate collection: "PVCFCDocuments" or "Chunk"
    • OpenSearch index: "rag_chunks" (4,883 docs)
```

### 4.2 Query Time (Online)

```
USER QUERY: "Áp suất vận hành tối đa của K06101?"
    ↓
[1] QUERY TRANSFORM (50-150ms)
    • Normalize: lowercase, whitespace
    • Extract equipment_id: K06101
    • Intent: ASK
    • Language: vi
    ↓
[2] HYBRID RETRIEVAL (200-500ms)
    Parallel:
    ├─ Weaviate: embed query → near_vector → top 50
    └─ OpenSearch: tokenize → BM25 → top 50

    RRF Fusion (k=60):
    • score(d) = Σ (1 / (60 + rank_i(d)))
    • Merge & deduplicate
    ↓
[3] BGE RERANKING (100-400ms, if enabled)
    • CrossEncoder score each (query, doc) pair
    • Re-sort by score
    • Select top-k (default 8)
    ↓
[4] GENERATION (300-1000ms)
    Strategy:
    • Has PDF pages? → Vision (Gemini 2.5 Pro + JPEG pages)
    • Text only → Text (Gemini 2.5 Flash)

    Prompt:
    • Context: top-k chunks (or pages for vision)
    • Question: {query}
    • Instruction: Answer with citations [Doc N, p.X]
    ↓
[5] POST-PROCESSING (10-50ms)
    • Extract citations from answer
    • Validate citations (CiteFix-lite)
    • Calculate confidence [0, 1]
    • Clamp negative scores
    ↓
[6] RESPONSE
    {
      "answer": "...",
      "citations": [{doc_id, page, pdf_path, confidence}],
      "confidence": 0.85,
      "meta": {latency_ms, model, trace_id, ...}
    }
```

---

## 5. CẤU TRÚC THƯ MỤC

```
Code - API_LLM_PVCFC/
├── app/                        # 🎯 Main application code
│   ├── api/                    # FastAPI routers & endpoints
│   │   ├── routers/            # ask, locate, report, health, config
│   │   └── endpoints/          # pdf_renderer
│   ├── core/                   # Core configs, logging, metrics, tracing
│   ├── deps/                   # Dependency injection (indices)
│   ├── ingestion/              # Document processing & ingestion
│   │   ├── chunkers/           # Text chunking strategies
│   │   ├── pdf_processor.py    # PDF parsing + OCR
│   │   ├── table_extractor.py  # Table extraction
│   │   └── dedup.py            # Content deduplication
│   ├── rag/                    # RAG pipeline components
│   │   ├── retriever.py        # HybridRetriever (legacy FAISS+BM25)
│   │   ├── weaviate_retriever.py        # WeaviateRetriever
│   │   ├── hybrid_weaviate_opensearch_retriever.py  # Modern Hybrid
│   │   ├── generator.py        # Answer generation
│   │   ├── reranker.py         # BGE CrossEncoder reranking
│   │   ├── citation_retriever.py        # Citation extraction & ranking
│   │   ├── citation_validator.py        # CiteFix-lite validation
│   │   ├── query_transform.py  # Query normalization & filters
│   │   └── indexers/           # BM25, FAISS, OpenSearch indexers
│   ├── services/               # External services (LLM, embedding)
│   │   ├── llm_client.py       # LLM service (Gemini/OpenAI)
│   │   ├── embedding.py        # Embedding service
│   │   └── reranker.py         # Reranker service
│   ├── storage/                # Version management & manifests
│   └── utils/                  # Utilities (text, page, tags)
│
├── streamlit_app/              # 🖥️ Streamlit UI
│   ├── app.py                  # Main UI entry
│   ├── components/             # UI components (query_lab, system_status)
│   └── pages/                  # Multi-page app
│
├── docs/                       # 📚 Documentation
│   ├── README.md               # Documentation index
│   ├── guides/                 # User guides (Weaviate setup, testing)
│   ├── analysis/               # Technical analysis & RCA
│   ├── completion/             # Phase completion reports
│   ├── implementation/         # Implementation summaries
│   ├── DOCS_COMMON/            # Common docs (FAQ, glossary)
│   ├── DOCS_NEW_Features/      # New feature docs
│   ├── DOCS_PHASE1-4/          # Phase-specific docs
│   └── PROJECT_MASTERY_GUIDE.md  # ⭐ This file
│
├── scripts/                    # 🔧 Utility scripts
│   ├── README.md               # Scripts index
│   ├── diagnostics/            # Diagnostic scripts (check pages, PDFs)
│   ├── opensearch/             # OpenSearch scripts (indexing, testing)
│   ├── weaviate/               # Weaviate scripts (setup, search)
│   ├── test_scripts/           # Test & validation scripts
│   └── utilities/              # General utilities (build indices, fix doc_id_map)
│
├── tools/                      # 🛠️ Build & maintenance tools
│   ├── ingest.py               # Main ingestion pipeline
│   ├── ops/                    # Operations tools
│   │   ├── build_production_indices.py  # Build BM25 + FAISS
│   │   ├── run_production_ingest.py     # Production ingestion
│   │   └── create_version.py   # Post-ingestion versioning
│   ├── analysis/               # Data analysis tools
│   └── benchmarks/             # Performance benchmarking
│
├── tests/                      # 🧪 Unit & integration tests
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── test_hybrid_modern.py   # Hybrid Modern mode tests
│
├── artifacts/                  # 📦 Generated artifacts (gitignored)
│   ├── ingestion_production/   # Production ingested chunks
│   │   ├── chunks.jsonl
│   │   ├── doc_id_map.json
│   │   └── manifests/
│   ├── index_production/       # Production indices
│   │   ├── bm25/
│   │   └── faiss/
│   ├── versions/               # Version snapshots
│   └── logs/                   # Application logs
│
├── data/                       # 📁 Data (gitignored)
│   ├── raw/                    # Raw PDF corpus (D:\Data_Raw symlink)
│   └── test/                   # Test data
│
├── config/                     # ⚙️ Configurations
│   └── hyde_config.yaml        # HyDE configuration
│
├── launchers/                  # 🚀 Launcher scripts
│   ├── start_api.ps1           # Start API server
│   ├── start_ui.ps1            # Start Streamlit UI
│   └── README.md               # Launcher guide
│
├── Build_plan_README/          # 📋 Build plans & roadmaps
│   ├── INDEX.md                # Central index
│   ├── completed/              # Completed features
│   ├── designs/                # Active designs
│   ├── issues/                 # Blocking issues
│   ├── roadmap/                # Phase plans
│   └── ops-ui/                 # UI fixes & notes
│
├── CHANGLOG_README/            # 📝 Changelog & reports
│   ├── Phase*.md               # Phase completion reports
│   └── Critical_Fixes_Report.md
│
├── .env                        # 🔒 Environment variables (gitignored)
├── requirements.txt            # 📦 Python dependencies
├── docker-compose.yml          # 🐳 Docker (OpenSearch)
├── docker-compose-weaviate.yml # 🐳 Docker (Weaviate)
├── README.md                   # 📖 Main README
├── QUICK_START.md              # 🚀 Quick start guide
├── SYSTEM_ARCHITECTURE.md      # 🏗️ System architecture
├── CHANGELOG.md                # 📜 Version history
└── PRE_LAUNCH_CHECKLIST.md     # ✅ Pre-launch checklist
```

---

## 6. MODULES CHÍNH

### 6.1 Ingestion Pipeline (`app/ingestion/`)

**Purpose**: Xử lý PDF raw → chunks có metadata

**Key Files**:
- `pdf_processor.py`: Parse PDF, extract text/images, OCR
- `table_extractor.py`: Extract tables từ PDF
- `chunkers/text_chunker.py`: Split text → chunks (1000 chars, overlap 200)
- `dedup.py`: Content deduplication (SHA1 hash)

**Command**:
```bash
python tools/ingest.py \
  --source-dir D:\Data_Raw \
  --output-dir artifacts/ingestion_production \
  --workers 4 \
  --enable-ocr --ocr-lang "vie+eng" \
  --extract-tables \
  --create-version \
  --version-id v1.0 \
  --version-description "Production baseline"
```

**Output**:
- `chunks.jsonl`: Deduplicated chunks
- `doc_id_map.json`: doc_id → pdf_path mapping
- `quarantine.jsonl`: Failed files
- `manifests/`: Ingestion metadata

### 6.2 Indexing (`app/rag/indexers/`)

**Purpose**: Build search indices từ chunks

**Key Files**:
- `bm25_indexer.py`: Build BM25 inverted index (offline)
- `faiss_indexer.py`: Build FAISS vector index (legacy)
- `opensearch_bm25_retriever.py`: OpenSearch BM25 client

**Weaviate Indexing** (Recommended):
```bash
# 1. Start Weaviate
docker-compose -f docker-compose-weaviate.yml up -d

# 2. Ingest to Weaviate
python scripts/phase1_index_to_weaviate.py

# 3. Verify
python scripts/weaviate/test_weaviate_search.py "CO2 compressor"
```

**OpenSearch Indexing**:
```bash
# 1. Start OpenSearch
docker-compose up -d

# 2. Create index
python scripts/opensearch/create_rag_chunks_index.py

# 3. Bulk insert
python scripts/opensearch/bulk_insert_to_opensearch.py

# 4. Test
python scripts/opensearch/test_opensearch_search.py "CO2 compressor"
```

### 6.3 Retrieval (`app/rag/`)

**Purpose**: Search & rank relevant documents

**Key Files**:
- `retriever.py`: HybridRetriever (legacy FAISS + BM25)
- `weaviate_retriever.py`: WeaviateRetriever (Phase 4)
- `hybrid_weaviate_opensearch_retriever.py`: Modern Hybrid (Phase 5)
- `reranker.py`: BGE CrossEncoder reranking
- `query_transform.py`: Query normalization & filters

**Mode Selection** (`.env`):
```ini
# Modern Hybrid (Weaviate + OpenSearch)
USE_HYBRID_MODERN=true

# Legacy Hybrid (FAISS + BM25 offline)
USE_HYBRID_MODERN=false
```

**Retrieval Flow**:
1. Transform query (normalize, extract filters)
2. Parallel search (Weaviate + OpenSearch)
3. RRF fusion (k=60)
4. BGE reranking (optional, if `ENABLE_BGE_RERANK=true`)
5. Return top-k (default 8)

### 6.4 Generation (`app/rag/generator.py`)

**Purpose**: Generate answer + citations từ retrieved docs

**Key Features**:
- **Strategy Selection**: Text-only vs Vision (multimodal)
- **Text Generation**: Gemini 2.5 Flash (fast, cost-effective)
- **Vision Generation**: Gemini 2.5 Pro (multimodal, higher accuracy)
- **Citation Extraction**: Parse `[Doc N, p.X]` patterns
- **Post-Validation**: CiteFix-lite validation

**Vision Generation**:
- Condition: Has PDF pages & `enable_vision_generation=true`
- Render pages: JPEG @ DPI=200, max 10 pages
- Prompt: Context = text + images
- Output: Answer + citations với pdf_path + page

### 6.5 Citation Handling (`app/rag/`)

**Purpose**: Extract, validate, and format citations

**Key Files**:
- `citation_retriever.py`: Extract & rank citations
- `citation_validator.py`: CiteFix-lite validation (Level 1-3)
- `snippet_extractor.py`: Extract relevant text snippets

**Validation Levels**:
- **Level 1**: Basic (doc_exists + page_valid) - ~1-5ms
- **Level 2**: Full (+ text verification) - ~10-30ms
- **Level 3**: Semantic (+ NLI entailment) - ~100-500ms (future)

**IEEE Citation** (UI feature):
- Convert `[Doc N, p.X]` → `[n]` numbered references
- Interactive References section
- Clickable PDF page links

### 6.6 Services (`app/services/`)

**Purpose**: External API clients (LLM, Embedding)

**Key Files**:
- `llm_client.py`: LLM service (Gemini/OpenAI)
- `embedding.py`: Embedding service (Gemini/Local)
- `reranker.py`: Reranker service (BGE)

**LLM Tiers**:
- **Heavy**: `gemini-2.5-pro` (multimodal, high quality)
- **Light**: `gemini-2.5-flash` (text-only, fast & cheap)

**Embedding**:
- **Provider**: Gemini (`gemini-embedding-001`, 768D)
- **Batch Size**: 256 texts per batch
- **Concurrency**: 8 concurrent requests

---

## 7. CẤU HÌNH & ENVIRONMENT

### 7.1 Environment Variables (`.env`)

**Quan trọng**: Copy từ `env.example` và điền giá trị thực

```ini
# ===== Application =====
APP_ENV=local                   # local|dev|prod
API_PORT=8000
LOG_LEVEL=INFO

# ===== LLM Provider =====
LLM_PROVIDER=gemini             # gemini|openai|none
LLM_MODEL_HEAVY=gemini-2.5-pro
LLM_MODEL_LIGHT=gemini-2.5-flash

# ===== Embedding =====
EMBEDDING_PROVIDER=gemini       # gemini|openai|local|none
EMBEDDING_MODEL=gemini-embedding-001  # 768D auto-detect
EMBED_TASK=retrieval_document   # NO inline comments!
EMBED_BATCH_SIZE=256
EMBED_CONCURRENCY=8

# ===== Retrieval Modes =====
USE_HYBRID_MODERN=true          # true: Weaviate+OpenSearch, false: FAISS+BM25

# ===== OpenSearch (BM25 remote) =====
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=rag_chunks
OPENSEARCH_BM25_K1=1.2
OPENSEARCH_BM25_B=0.75
OPENSEARCH_TIMEOUT=10

# ===== Weaviate Vector Database =====
WEAVIATE_ENABLED=true
WEAVIATE_HOST=localhost
WEAVIATE_PORT=8080              # HTTP
WEAVIATE_GRPC_PORT=50051        # gRPC (faster)
WEAVIATE_USE_GRPC=true
WEAVIATE_COLLECTION=PVCFCDocuments  # or "Chunk"
WEAVIATE_RETRIEVAL_LIMIT=50

# ===== BGE Reranking (Phase 3) =====
ENABLE_BGE_RERANK=false         # Enable BGE CrossEncoder
BGE_RERANK_CANDIDATE_LIMIT=50
BGE_RERANK_TOP_K=10
BGE_RERANK_LEVEL=chunk          # chunk|doc|page
BGE_RERANK_AGGREGATION=max      # max|mean|top3_mean

# ===== Vision (Multimodal) =====
VISION_MODEL=models/gemini-2.5-pro
VISION_MAX_PAGES_TOTAL=10
PDF_RENDER_DPI=200
PDF_IMAGE_FORMAT=jpeg

# ===== API Keys =====
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here  # Optional
```

### 7.2 Cấu hình Quan trọng

**Chunking** (`tools/ingest.py`):
```python
--chunk-size 1000        # Characters per chunk
--chunk-overlap 200      # Overlap between chunks
```

**BM25 Parameters**:
```python
k1 = 1.2                 # Term frequency saturation
b = 0.75                 # Length normalization
epsilon = 0.25           # IDF floor
```

**RRF Fusion**:
```python
k = 60                   # RRF constant
score(d) = Σ (1 / (k + rank_i(d)))
```

**Vision Generation**:
```python
max_pages = 10           # Max pages to render
dpi = 200                # JPEG quality
format = "jpeg"          # Image format
```

---

## 8. WORKFLOWS QUAN TRỌNG

### 8.1 Workflow 1: Ingestion → Indexing → Query (E2E)

```bash
# Step 1: Ingest PDFs
python tools/ingest.py \
  --source-dir D:\Data_Raw \
  --output-dir artifacts/ingestion_production \
  --workers 4 \
  --enable-ocr --ocr-lang "vie+eng" \
  --extract-tables \
  --create-version \
  --version-id v1.0_prod \
  --version-description "Production baseline - 150 PDFs"

# Step 2: Start Docker services
docker-compose up -d                             # OpenSearch
docker-compose -f docker-compose-weaviate.yml up -d  # Weaviate

# Step 3: Index to Weaviate
python scripts/phase1_index_to_weaviate.py

# Step 4: Index to OpenSearch
python scripts/opensearch/create_rag_chunks_index.py
python scripts/opensearch/bulk_insert_to_opensearch.py

# Step 5: Build legacy indices (optional, for fallback)
python tools/ops/build_production_indices.py

# Step 6: Configure .env
# Ensure USE_HYBRID_MODERN=true, WEAVIATE_ENABLED=true

# Step 7: Start API
.\launchers\start_api.ps1

# Step 8: Start UI (new terminal)
.\launchers\start_ui.ps1

# Step 9: Test query
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Áp suất vận hành tối đa của K06101?",
    "language": "vi",
    "max_context": 8,
    "enable_vision_generation": true
  }'
```

### 8.2 Workflow 2: Update Data (Incremental)

```bash
# Step 1: Ingest new PDFs
python tools/ingest.py \
  --source-dir D:\Data_Raw_New \
  --output-dir artifacts/ingestion_v1.1 \
  --create-version \
  --version-id v1.1_incremental \
  --version-description "Added 20 new technical specs"

# Step 2: Re-index (append mode)
python scripts/phase1_index_to_weaviate.py \
  --chunks-path artifacts/ingestion_v1.1/chunks.jsonl \
  --append

python scripts/opensearch/bulk_insert_to_opensearch.py \
  --chunks-path artifacts/ingestion_v1.1/chunks.jsonl

# Step 3: Compare versions
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    print(vm.compare_versions('v1.0_prod', 'v1.1_incremental'))"

# Step 4: Restart API (hot reload should pick up new index)
```

### 8.3 Workflow 3: Rollback to Previous Version

```bash
# Step 1: List versions
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    print(vm.list_versions())"

# Step 2: Rollback ingestion artifacts
python tools/ops/create_version.py \
  --restore \
  --version-id v1.0_prod \
  --target-dir artifacts/ingestion_production

# Step 3: Re-build indices from restored chunks
python tools/ops/build_production_indices.py

# Step 4: Restart API
```

### 8.4 Workflow 4: Debug Query (Step-by-step)

```bash
# Step 1: Check health
curl http://localhost:8000/healthz

# Step 2: Check index stats
curl http://localhost:8000/index-stats

# Step 3: Test retrieval only (no generation)
python scripts/diagnostics/deep_diagnostic.py --query "K06101"

# Step 4: Test with debug logging
# Edit .env: LOG_LEVEL=DEBUG
.\launchers\start_api.ps1

# Step 5: Query với trace
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "...", "language": "vi"}' \
  -D - | grep X-Trace-ID

# Step 6: Check trace
curl http://localhost:8000/trace

# Step 7: View logs
.\scripts\view_logs.ps1
```

---

## 9. TESTING & EVALUATION

### 9.1 Test Levels

**Unit Tests** (`tests/unit/`):
- `test_version_manager.py`: Version management
- `test_citation_validator.py`: CiteFix-lite
- `test_text_chunker.py`: Chunking logic

**Integration Tests** (`tests/integration/`):
- `test_ingestion_versioning.py`: Ingestion + versioning
- `test_hybrid_modern.py`: Hybrid Modern retrieval

**E2E Tests** (`tests/`):
- `test_e2e_ask_flow.py`: Full ask flow
- `test_vision_generation.py`: Vision generation

### 9.2 Run Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/unit/test_citation_validator.py -v

# Specific test function
pytest tests/unit/test_citation_validator.py::test_basic_validation -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

### 9.3 Integration Test: Hybrid Modern

```bash
# Prerequisites: Docker services running
docker ps  # Should see weaviate, opensearch

# Run test
python tests/test_hybrid_modern.py

# Expected output:
# ✅ Test 1: HybridModernRetriever creation
# ✅ Test 2: Health checks (healthy or degraded)
# ✅ Test 3: Statistics (OpenSearch ~4,883 docs)
# ✅ Test 4: Search results (from both backends)
# ✅ Test 5: RRF fusion
# ✅ Test 6: BGE rerank (if enabled)
```

### 9.4 Smoke Tests

```bash
# Phase 0: Basic setup
python scripts/test_scripts/smoke_test_phase0.py

# Phase 1: Ingestion + indexing
python scripts/phase1_smoke_test.py

# Phase 2: Semantic search
python scripts/phase2_semantic_smoke_test.py

# Phase 3: BGE reranking
python scripts/phase3_reranker_smoke_test.py

# Phase 4: RAG integration
python scripts/phase4_rag_integration_test.py
```

### 9.5 Evaluation Metrics

**Retrieval Metrics**:
- Precision@k
- Recall@k
- MRR (Mean Reciprocal Rank)
- nDCG@k (Normalized Discounted Cumulative Gain)

**Generation Metrics**:
- Faithfulness (answer faithful to context)
- Context Precision (relevant context retrieved)
- Citation Correctness (page citations accurate)
- SME Acceptable Answer (≥80% target)

**Performance Metrics**:
- Latency (p50, p95, p99)
- Throughput (QPS)
- Memory usage
- CPU usage

**Run Evaluation**:
```bash
# Golden set evaluation
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py

# Batch evaluation
python app/evaluation/batch_runner.py \
  --questions data/evaluation/golden_queries.json \
  --output results/evaluation/results.json

# Generate report
python app/evaluation/report_generator.py \
  --results results/evaluation/results.json \
  --output reports/evaluation_report.md
```

---

## 10. DEPLOYMENT & OPERATIONS

### 10.1 Local Development

```bash
# 1. Setup
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Configure
cp env.example .env
# Edit .env with your API keys

# 3. Start Docker
docker-compose up -d
docker-compose -f docker-compose-weaviate.yml up -d

# 4. Start API
.\launchers\start_api.ps1

# 5. Start UI
.\launchers\start_ui.ps1
```

### 10.2 Production Deployment (Server)

**Prerequisites**:
- Ubuntu 20.04+ / Windows Server
- Python 3.11
- Docker & Docker Compose
- 16GB+ RAM
- 100GB+ storage

**Steps**:
```bash
# 1. Clone repo
git clone https://github.com/your-org/pvcfc-rag.git
cd pvcfc-rag

# 2. Setup venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp env.example .env
# Edit .env: APP_ENV=prod, API keys, paths

# 4. Ingest data
python tools/ops/run_production_ingest.py

# 5. Build indices
docker-compose up -d
docker-compose -f docker-compose-weaviate.yml up -d
python scripts/phase1_index_to_weaviate.py
python scripts/opensearch/create_rag_chunks_index.py
python scripts/opensearch/bulk_insert_to_opensearch.py

# 6. Start API (systemd service recommended)
# Create /etc/systemd/system/pvcfc-rag-api.service
[Unit]
Description=PVCFC RAG API
After=network.target docker.service

[Service]
Type=simple
User=pvcfc
WorkingDirectory=/opt/pvcfc-rag
Environment="PATH=/opt/pvcfc-rag/.venv/bin"
ExecStart=/opt/pvcfc-rag/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target

# Enable & start
sudo systemctl enable pvcfc-rag-api
sudo systemctl start pvcfc-rag-api
```

### 10.3 Docker Deployment (API + Services)

**Dockerfile** (Create if needed):
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY app/ app/
COPY artifacts/ artifacts/
COPY .env .env

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Docker Compose** (Full stack):
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=prod
    depends_on:
      - opensearch
      - weaviate
    volumes:
      - ./artifacts:/app/artifacts
      - ./data:/app/data

  opensearch:
    image: opensearchproject/opensearch:2.12.0
    ports:
      - "9200:9200"
    environment:
      - discovery.type=single-node
      - OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g

  weaviate:
    image: semitechnologies/weaviate:1.24.1
    ports:
      - "8080:8080"
      - "50051:50051"
    environment:
      - ENABLE_MODULES=text2vec-contextionary
```

### 10.4 Monitoring & Observability

**Metrics Endpoint**:
```bash
curl http://localhost:8000/metrics
```

**Prometheus Integration** (`prometheus.yml`):
```yaml
scrape_configs:
  - job_name: 'pvcfc-rag-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

**Key Metrics**:
- `rag_query_latency_seconds`: Query latency histogram
- `rag_query_total`: Total queries counter
- `rag_retrieval_latency_seconds`: Retrieval latency
- `rag_generation_latency_seconds`: Generation latency
- `rag_confidence_score`: Confidence score histogram

**Logs** (Loguru):
```python
# Location: artifacts/logs/pvcfc-rag_{date}.log
# Format: JSON structured logs
# Retention: 30 days, rotation 100MB
```

**Tracing**:
```bash
# Check current trace
curl http://localhost:8000/trace
```

### 10.5 Backup & Recovery

**Backup Strategy**:
```bash
# 1. Backup ingestion artifacts
tar -czf backup_ingestion_$(date +%Y%m%d).tar.gz artifacts/ingestion_production/

# 2. Backup indices
tar -czf backup_indices_$(date +%Y%m%d).tar.gz artifacts/index_production/

# 3. Backup versions
tar -czf backup_versions_$(date +%Y%m%d).tar.gz artifacts/versions/

# 4. Backup Docker volumes (Weaviate, OpenSearch)
docker exec weaviate-weaviate-1 tar -czf /tmp/weaviate_backup.tar.gz /var/lib/weaviate
docker cp weaviate-weaviate-1:/tmp/weaviate_backup.tar.gz ./backup_weaviate_$(date +%Y%m%d).tar.gz
```

**Recovery**:
```bash
# 1. Restore artifacts
tar -xzf backup_ingestion_20251010.tar.gz -C artifacts/

# 2. Rebuild indices
python tools/ops/build_production_indices.py

# 3. Re-index to Weaviate/OpenSearch
python scripts/phase1_index_to_weaviate.py
python scripts/opensearch/bulk_insert_to_opensearch.py

# 4. Restart API
sudo systemctl restart pvcfc-rag-api
```

---

## 11. TROUBLESHOOTING

### 11.1 Common Issues

#### Issue 1: API fails to start - "Both backends unhealthy"

**Symptoms**:
```
ERROR: Both Weaviate and OpenSearch are unhealthy
```

**Diagnosis**:
```bash
# Check Docker services
docker ps

# Test OpenSearch
curl http://localhost:9200

# Test Weaviate
curl http://localhost:8080/v1/.well-known/ready
```

**Solutions**:
```bash
# Restart Docker services
docker restart opensearch-node
docker restart weaviate-weaviate-1

# Check logs
docker logs opensearch-node
docker logs weaviate-weaviate-1

# Rebuild indices if corrupted
python tools/ops/build_production_indices.py
```

#### Issue 2: Negative confidence score (422 error)

**Symptoms**:
```json
{
  "error": "Validation Error",
  "detail": "confidence must be between 0 and 1"
}
```

**Diagnosis**:
```bash
# Check logs for ERROR messages
tail -f artifacts/logs/pvcfc-rag_*.log | grep "confidence"
```

**Solutions**:
- **Fixed in v0.6.1**: Defensive clamping in `app/rag/generator.py`
- **Workaround**: Set `ENABLE_BGE_RERANK=false` to disable reranker

#### Issue 3: Vision generation fails

**Symptoms**:
```
WARNING: Failed to render page 5: [Errno 2] No such file or directory
```

**Diagnosis**:
```bash
# Check doc_id_map.json exists
ls artifacts/ingestion_production/doc_id_map.json

# Check PDF path in doc_id_map
python -c "import json; print(json.load(open('artifacts/ingestion_production/doc_id_map.json')))"
```

**Solutions**:
```bash
# Fix doc_id_map paths
python scripts/utilities/fix_doc_id_map.py \
  --doc-id-map artifacts/ingestion_production/doc_id_map.json \
  --pdf-root D:\Data_Raw

# Disable vision if PDFs not accessible
# Edit request: "enable_vision_generation": false
```

#### Issue 4: OpenSearch index not found

**Symptoms**:
```
opensearchpy.exceptions.NotFoundError: index_not_found_exception
```

**Solutions**:
```bash
# Create index
python scripts/opensearch/create_rag_chunks_index.py

# Bulk insert
python scripts/opensearch/bulk_insert_to_opensearch.py

# Verify
curl http://localhost:9200/rag_chunks/_count
```

#### Issue 5: Weaviate collection empty

**Symptoms**:
```
INFO: Weaviate collection has 0 objects
```

**Solutions**:
```bash
# Re-ingest to Weaviate
python scripts/phase1_index_to_weaviate.py

# Verify
python scripts/weaviate/test_weaviate_search.py "test query"
```

### 11.2 Debug Tools

**Deep Diagnostic**:
```bash
python scripts/diagnostics/deep_diagnostic.py --query "K06101"
```

**Check PDF Pages**:
```bash
python scripts/diagnostics/check_pdf_pages.py --pdf-path "path/to/file.pdf"
```

**Verify Ingestion**:
```bash
python scripts/utilities/validate_reingestion.py \
  --chunks artifacts/ingestion_production/chunks.jsonl
```

**Test Retrieval Only**:
```bash
python scripts/debug_retrieval.py --query "test query" --max-results 10
```

### 11.3 Performance Debugging

**Profile Query**:
```python
import cProfile
import pstats

def profile_query(query):
    profiler = cProfile.Profile()
    profiler.enable()

    # Run query
    response = requests.post("http://localhost:8000/api/ask", json={"query": query})

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)

profile_query("What is K06101 max pressure?")
```

**Memory Profiling**:
```bash
pip install memory_profiler

python -m memory_profiler app/main.py
```

**Check Index Size**:
```bash
# Weaviate
curl http://localhost:8080/v1/schema/Chunk | jq '.vectorIndexConfig'

# OpenSearch
curl http://localhost:9200/_cat/indices/rag_chunks?v
```

---

## 12. ROADMAP & FUTURE WORK

### 12.1 Completed Features (v0.6.1)

- ✅ Core RAG pipeline (ingestion, indexing, Q&A)
- ✅ Hybrid retrieval (BM25 + Vector)
- ✅ Modern Hybrid (Weaviate + OpenSearch)
- ✅ BGE CrossEncoder reranking
- ✅ Vision generation (multimodal)
- ✅ CiteFix-lite validation (Level 1-2)
- ✅ IEEE citation formatting
- ✅ Version management
- ✅ Defensive confidence handling

### 12.2 In Progress

- 🟡 Performance benchmarks
- 🟡 Page rank caching
- 🟡 Semantic validation (CiteFix-lite Level 3)

### 12.3 Future Enhancements

**Phase 6: Advanced Features**
- [ ] Office docs support (docx, xlsx, pptx)
- [ ] Bbox highlighting (exact text location)
- [ ] Token-based chunking (350/50)
- [ ] Advanced OCR (Google Vision for low-quality scans)
- [ ] Report templates (Word/PDF with branding)

**Phase 7: Scalability**
- [ ] Index versioning & rollback
- [ ] Incremental updates (delta ingestion)
- [ ] Multi-tenant support
- [ ] Distributed inference (multiple API instances)
- [ ] CDN for PDF rendering

**Phase 8: User Experience**
- [ ] Web UI (replace Streamlit)
- [ ] User feedback loop
- [ ] Query suggestions & autocomplete
- [ ] Document upload via UI
- [ ] Export to multiple formats (Word, PDF, HTML)

**Phase 9: Intelligence**
- [ ] Query expansion & rewriting
- [ ] Multi-hop reasoning
- [ ] Claim verification with references
- [ ] Automated report generation workflows
- [ ] Learning from user feedback (RLHF)

### 12.4 Technical Debt

1. **Generator Legacy Path**: Reduce regex `[Doc N]` reliance when structured output is ON
2. **Embeddings Optimization**: Cache query embeddings, benchmark Gemini vs local models
3. **BM25 Scale**: Consider Pyserini/Lucene for disk-based indexing
4. **FAISS Scale**: IVF-PQ for million-vector scale
5. **Test Coverage**: Increase unit test coverage to >80%

---

## 📚 APPENDIX

### A. Taxonomy & Conventions

**Equipment ID Regex**: `\bKT?\d{5}\b` → Matches `K06101`, `KT06101`

**Doc Types** (expandable):
- Manual
- Drawing
- Instrument
- Maintenance
- Data/Spec
- SpareParts
- Procedure
- Report
- Certificate

**Language Codes**:
- `vi`: Vietnamese
- `en`: English

**Citation Format**:
- Traditional: `[Doc N, p.X]`
- IEEE: `[n]` with numbered references

### B. Key Directories

- **Production Artifacts**: `artifacts/ingestion_production/`, `artifacts/index_production/`
- **Backup Artifacts**: `artifacts/ingestion_production_backup_*/`
- **Test Data**: `data/test/`, `test_docs/`
- **Logs**: `artifacts/logs/`, `logs/`

### C. Glossary

- **RAG**: Retrieval-Augmented Generation
- **BM25**: Best Matching 25 (keyword ranking algorithm)
- **RRF**: Reciprocal Rank Fusion
- **BGE**: BAAI General Embedding (reranking model)
- **HyDE**: Hypothetical Document Embeddings
- **CiteFix-lite**: Citation validation system
- **doc_id**: Unique document identifier (SHA256 hash)
- **content_hash**: Normalized text hash (SHA1)
- **1-based page**: Page numbers start from 1 (not 0)

### D. Contact & Support

- **Project Lead**: [Your Name]
- **Repository**: [GitHub URL]
- **Documentation**: `docs/README.md`
- **Issue Tracker**: [GitHub Issues]

---

**🎉 Chúc bạn thành công trong việc nắm vững dự án!**

**Last Updated**: 2025-10-12
**Version**: 1.0.0
**Status**: ✅ Complete & Production-Ready
