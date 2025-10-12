# ARCHITECTURE DIAGRAMS - PVCFC RAG SYSTEM

**Version**: 1.0.0
**Date**: 2025-10-12
**Purpose**: Visual architecture reference với các sơ đồ chi tiết

---

## 📋 MỤC LỤC

1. [System Overview](#1-system-overview)
2. [Component Architecture](#2-component-architecture)
3. [Data Flow Diagrams](#3-data-flow-diagrams)
4. [Sequence Diagrams](#4-sequence-diagrams)
5. [Deployment Architecture](#5-deployment-architecture)

---

## 1. SYSTEM OVERVIEW

### 1.1 High-Level Architecture (Offline + Online)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PVCFC RAG SYSTEM                              │
│                     Retrieval-Augmented Generation                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        OFFLINE PIPELINE (Build Time)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  📁 Data Source: D:\Data_Raw (PDF Corpus)                              │
│  ├─ Technical Manuals                                                   │
│  ├─ P&ID Drawings                                                       │
│  ├─ Datasheets                                                          │
│  ├─ Maintenance Procedures                                              │
│  └─ Spare Parts Catalogs                                                │
│                                                                         │
│                           ↓                                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────┐         │
│  │              PHASE 1: DOCUMENT INGESTION                  │         │
│  │                  (tools/ingest.py)                        │         │
│  ├───────────────────────────────────────────────────────────┤         │
│  │                                                           │         │
│  │  [Step 1] File Discovery                                 │         │
│  │    • Recursive scan of D:\Data_Raw                       │         │
│  │    • Filter: *.pdf                                       │         │
│  │    • Skip: quarantined, corrupted                        │         │
│  │                                                           │         │
│  │  [Step 2] PDF Parsing                                    │         │
│  │    • Primary: PyMuPDF (vector text)                      │         │
│  │    • Fallback: OCR (Tesseract/PaddleOCR)                 │         │
│  │    • Language: vie+eng, DPI: 300                         │         │
│  │                                                           │         │
│  │  [Step 3] Table Extraction                               │         │
│  │    • pdfplumber (min 2x2 cells)                          │         │
│  │    • Convert to Markdown                                 │         │
│  │    • Preserve structure                                  │         │
│  │                                                           │         │
│  │  [Step 4] Metadata Extraction                            │         │
│  │    • doc_id: SHA256(file_path)                           │         │
│  │    • equipment_id: Regex \bKT?\d{5}\b                    │         │
│  │    • doc_type: Infer from path + content                 │         │
│  │    • page_count, source_format (vector|scan)             │         │
│  │                                                           │         │
│  │  [Step 5] Text Normalization                             │         │
│  │    • Lowercase, strip whitespace                         │         │
│  │    • Remove control chars                                │         │
│  │    • content_hash: SHA1(normalized_text)                 │         │
│  │                                                           │         │
│  │  [Step 6] Chunking                                       │         │
│  │    • Strategy: Character-based                           │         │
│  │    • Size: 1000 chars                                    │         │
│  │    • Overlap: 200 chars                                  │         │
│  │    • Metadata: doc_id, page, page_start, page_end        │         │
│  │                                                           │         │
│  │  [Step 7] Deduplication                                  │         │
│  │    • Group by content_hash (SHA1)                        │         │
│  │    • Select best representative:                         │         │
│  │      Priority: vector > scan > newer > shorter_path      │         │
│  │                                                           │         │
│  └───────────────────────────────────────────────────────────┘         │
│                           ↓                                             │
│                                                                         │
│  📦 Ingestion Outputs:                                                  │
│    • chunks.jsonl (~12,500 chunks for 150 PDFs)                        │
│    • doc_id_map.json (doc_id → pdf_path mapping)                       │
│    • quarantine.jsonl (failed files)                                   │
│    • manifests/ (ingestion metadata + version tracking)                │
│                                                                         │
│                           ↓                                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────┐         │
│  │            PHASE 2: INDEXING & STORAGE                    │         │
│  │         (tools/ops/build_production_indices.py)           │         │
│  ├───────────────────────────────────────────────────────────┤         │
│  │                                                           │         │
│  │  ┌─────────────────────────────────────────────┐         │         │
│  │  │        WEAVIATE VECTOR DATABASE             │         │         │
│  │  │        (Production-Grade, gRPC)             │         │         │
│  │  ├─────────────────────────────────────────────┤         │         │
│  │  │  • Collection: PVCFCDocuments / Chunk       │         │         │
│  │  │  • Embedding: Gemini 768D                   │         │         │
│  │  │  • Batch insert with auto-batching          │         │         │
│  │  │  • Properties:                              │         │         │
│  │  │    - text (TEXT)                            │         │         │
│  │  │    - doc_id (TEXT)                          │         │         │
│  │  │    - page (INT)                             │         │         │
│  │  │    - chunk_id (TEXT)                        │         │         │
│  │  │    - metadata (OBJECT)                      │         │         │
│  │  │  • gRPC port: 50051 (faster)                │         │         │
│  │  │  • HTTP port: 8080 (admin)                  │         │         │
│  │  └─────────────────────────────────────────────┘         │         │
│  │                                                           │         │
│  │  ┌─────────────────────────────────────────────┐         │         │
│  │  │         OPENSEARCH BM25 INDEX               │         │         │
│  │  │      (Keyword Search, Remote)               │         │         │
│  │  ├─────────────────────────────────────────────┤         │         │
│  │  │  • Index: rag_chunks                        │         │         │
│  │  │  • Documents: 4,883                         │         │         │
│  │  │  • BM25 Params:                             │         │         │
│  │  │    - k1 = 1.2 (term frequency saturation)   │         │         │
│  │  │    - b = 0.75 (length normalization)        │         │         │
│  │  │  • Mappings:                                │         │         │
│  │  │    - text: TEXT (analyzed)                  │         │         │
│  │  │    - doc_id: KEYWORD                        │         │         │
│  │  │    - page: INTEGER                          │         │         │
│  │  │  • Port: 9200 (HTTP)                        │         │         │
│  │  │  • Dashboards: 5601 (UI)                    │         │         │
│  │  └─────────────────────────────────────────────┘         │         │
│  │                                                           │         │
│  │  ┌─────────────────────────────────────────────┐         │         │
│  │  │       FAISS VECTOR INDEX (Legacy)           │         │         │
│  │  │       (Local, Fallback Mode)                │         │         │
│  │  ├─────────────────────────────────────────────┤         │         │
│  │  │  • Type: IndexFlatL2 (brute-force)          │         │         │
│  │  │  • Dimension: 768D                          │         │         │
│  │  │  • File: artifacts/index_production/faiss/  │         │         │
│  │  │  • Use case: Offline dev, backup            │         │         │
│  │  └─────────────────────────────────────────────┘         │         │
│  │                                                           │         │
│  └───────────────────────────────────────────────────────────┘         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

                                  ↓

┌─────────────────────────────────────────────────────────────────────────┐
│                         ONLINE PIPELINE (Query Time)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  👤 User Query: "What is the maximum operating pressure of K06101?"    │
│                                                                         │
│                           ↓                                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────┐         │
│  │           PHASE 3: QUERY TRANSFORMATION                   │         │
│  │           (app/rag/query_transform.py)                    │         │
│  ├───────────────────────────────────────────────────────────┤         │
│  │                                                           │         │
│  │  [Step 1] Normalization                                  │         │
│  │    • Lowercase                                           │         │
│  │    • Trim whitespace                                     │         │
│  │    • Remove special chars                                │         │
│  │                                                           │         │
│  │  [Step 2] Intent Detection                               │         │
│  │    • ASK: Question-answering                             │         │
│  │    • LOCATE: Document search                             │         │
│  │    • EXPLAIN: Detailed explanation                       │         │
│  │    • REPORT: Generate report                             │         │
│  │                                                           │         │
│  │  [Step 3] Filter Extraction                              │         │
│  │    • equipment_id: K06101 (regex match)                  │         │
│  │    • doc_type: Manual, Drawing, etc.                     │         │
│  │    • vendor, year, revision (if present)                 │         │
│  │                                                           │         │
│  │  [Step 4] HyDE (Optional)                                │         │
│  │    • Generate hypothetical document                      │         │
│  │    • Embed hypothetical doc                              │         │
│  │    • Use for retrieval enhancement                       │         │
│  │                                                           │         │
│  └───────────────────────────────────────────────────────────┘         │
│                           ↓                                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────┐         │
│  │          PHASE 4: HYBRID RETRIEVAL (Parallel)             │         │
│  │  (app/rag/hybrid_weaviate_opensearch_retriever.py)       │         │
│  ├───────────────────────────────────────────────────────────┤         │
│  │                                                           │         │
│  │  ┌────────────────────┐    ┌─────────────────────┐       │         │
│  │  │  Weaviate Search   │    │  OpenSearch BM25    │       │         │
│  │  │   (Semantic)       │    │    (Keyword)        │       │         │
│  │  ├────────────────────┤    ├─────────────────────┤       │         │
│  │  │ • Embed query      │    │ • Tokenize query    │       │         │
│  │  │   → 768D vector    │    │ • BM25 scoring      │       │         │
│  │  │ • near_vector()    │    │ • Term matching     │       │         │
│  │  │ • Top 50 results   │    │ • Top 50 results    │       │         │
│  │  │ • Distance → score │    │ • Relevance score   │       │         │
│  │  └────────┬───────────┘    └──────────┬──────────┘       │         │
│  │           │                           │                  │         │
│  │           └─────────┬─────────────────┘                  │         │
│  │                     ↓                                     │         │
│  │           ┌──────────────────────┐                       │         │
│  │           │   RRF FUSION (k=60)  │                       │         │
│  │           ├──────────────────────┤                       │         │
│  │           │ score(d) = Σ (1 /    │                       │         │
│  │           │   (k + rank_i(d)))   │                       │         │
│  │           │                      │                       │         │
│  │           │ • Merge results      │                       │         │
│  │           │ • Deduplicate        │                       │         │
│  │           │ • Sort by RRF score  │                       │         │
│  │           └──────────┬───────────┘                       │         │
│  │                      ↓                                    │         │
│  │           ┌──────────────────────┐                       │         │
│  │           │  Combined Results    │                       │         │
│  │           │  (Top 50-100)        │                       │         │
│  │           └──────────────────────┘                       │         │
│  │                                                           │         │
│  └───────────────────────────────────────────────────────────┘         │
│                           ↓                                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────┐         │
│  │         PHASE 5: BGE RERANKING (Optional)                 │         │
│  │              (app/rag/reranker.py)                        │         │
│  ├───────────────────────────────────────────────────────────┤         │
│  │                                                           │         │
│  │  Model: BAAI/bge-reranker-base                           │         │
│  │  Type: CrossEncoder (bidirectional)                      │         │
│  │                                                           │         │
│  │  Process:                                                │         │
│  │    • For each (query, doc) pair:                         │         │
│  │      - Encode pair jointly                               │         │
│  │      - Predict relevance score [-∞, +∞]                  │         │
│  │      - Normalize to [0, 1]                               │         │
│  │    • Re-sort all results by rerank score                 │         │
│  │    • Select top-k (default 8)                            │         │
│  │                                                           │         │
│  │  Config:                                                 │         │
│  │    • ENABLE_BGE_RERANK=true/false                        │         │
│  │    • BGE_RERANK_CANDIDATE_LIMIT=50                       │         │
│  │    • BGE_RERANK_TOP_K=10                                 │         │
│  │    • BGE_RERANK_LEVEL=chunk (chunk|doc|page)             │         │
│  │    • BGE_RERANK_AGGREGATION=max (max|mean|top3_mean)     │         │
│  │                                                           │         │
│  │  Fallback: Score-based ranking if reranking fails        │         │
│  │                                                           │         │
│  └───────────────────────────────────────────────────────────┘         │
│                           ↓                                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────┐         │
│  │               PHASE 6: GENERATION                         │         │
│  │              (app/rag/generator.py)                       │         │
│  ├───────────────────────────────────────────────────────────┤         │
│  │                                                           │         │
│  │  Strategy Selection:                                     │         │
│  │    ┌─────────────────────┐                               │         │
│  │    │ Has PDF pages +     │                               │         │
│  │    │ enable_vision=true? │                               │         │
│  │    └──────┬──────┬───────┘                               │         │
│  │          YES    NO                                       │         │
│  │           │      │                                        │         │
│  │           ↓      ↓                                        │         │
│  │  ┌────────────┐  ┌─────────────┐                        │         │
│  │  │  VISION    │  │  TEXT-ONLY  │                        │         │
│  │  ├────────────┤  ├─────────────┤                        │         │
│  │  │ Model:     │  │ Model:      │                        │         │
│  │  │ Gemini 2.5 │  │ Gemini 2.5  │                        │         │
│  │  │ Pro        │  │ Flash       │                        │         │
│  │  │            │  │             │                        │         │
│  │  │ Input:     │  │ Input:      │                        │         │
│  │  │ • Text ctx │  │ • Text ctx  │                        │         │
│  │  │ • PDF imgs │  │ • Question  │                        │         │
│  │  │   (JPEG    │  │             │                        │         │
│  │  │   DPI=200) │  │             │                        │         │
│  │  │            │  │             │                        │         │
│  │  │ Pages:     │  │             │                        │         │
│  │  │ • Max 10   │  │             │                        │         │
│  │  │ • ±2 range │  │             │                        │         │
│  │  │ • Dedup    │  │             │                        │         │
│  │  └────────────┘  └─────────────┘                        │         │
│  │           │              │                               │         │
│  │           └──────┬───────┘                               │         │
│  │                  ↓                                        │         │
│  │        ┌──────────────────┐                              │         │
│  │        │  LLM Response    │                              │         │
│  │        │  • Answer text   │                              │         │
│  │        │  • Citations:    │                              │         │
│  │        │    [Doc N, p.X]  │                              │         │
│  │        └──────────┬───────┘                              │         │
│  │                   ↓                                       │         │
│  │        ┌──────────────────┐                              │         │
│  │        │ Citation Extract │                              │         │
│  │        │ • Parse citations│                              │         │
│  │        │ • Map to doc_ids │                              │         │
│  │        │ • Enrich w/ paths│                              │         │
│  │        └──────────┬───────┘                              │         │
│  │                   ↓                                       │         │
│  │        ┌──────────────────┐                              │         │
│  │        │ CiteFix-lite     │                              │         │
│  │        │ Validation       │                              │         │
│  │        │ • Level 1-2      │                              │         │
│  │        │ • Confidence calc│                              │         │
│  │        │ • Page neighbors │                              │         │
│  │        └──────────────────┘                              │         │
│  │                                                           │         │
│  └───────────────────────────────────────────────────────────┘         │
│                           ↓                                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────┐         │
│  │              PHASE 7: RESPONSE BUILDING                   │         │
│  │            (app/api/routers/ask.py)                       │         │
│  ├───────────────────────────────────────────────────────────┤         │
│  │                                                           │         │
│  │  {                                                        │         │
│  │    "answer": "The maximum operating pressure...",        │         │
│  │    "citations": [                                        │         │
│  │      {                                                   │         │
│  │        "doc_id": "DOCID_abc123",                         │         │
│  │        "page": 12,                                       │         │
│  │        "pdf_path": "D:\\...\\manual.pdf",                │         │
│  │        "confidence": 0.95                                │         │
│  │      }                                                   │         │
│  │    ],                                                    │         │
│  │    "confidence": 0.85,                                   │         │
│  │    "meta": {                                             │         │
│  │      "model": "gemini-2.5-pro",                          │         │
│  │      "latency_ms": 1430,                                 │         │
│  │      "breakdown": {                                      │         │
│  │        "transform_ms": 120,                              │         │
│  │        "retrieve_ms": 450,                               │         │
│  │        "rerank_ms": 280,                                 │         │
│  │        "generate_ms": 580                                │         │
│  │      },                                                  │         │
│  │      "k": 8,                                             │         │
│  │      "execution_mode": "production",                     │         │
│  │      "trace_id": "xyz789",                               │         │
│  │      "vision_generation": {                              │         │
│  │        "pages_used": [...],                              │         │
│  │        "pages_failed": []                                │         │
│  │      }                                                   │         │
│  │    }                                                     │         │
│  │  }                                                       │         │
│  │                                                           │         │
│  └───────────────────────────────────────────────────────────┘         │
│                           ↓                                             │
│                                                                         │
│  📱 Client Application (Streamlit UI / External API Consumer)          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. COMPONENT ARCHITECTURE

### 2.1 Application Layers

```
┌────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────┐           ┌─────────────────┐            │
│  │  Streamlit UI   │           │  External API   │            │
│  │  (Testing)      │           │  Consumers      │            │
│  └────────┬────────┘           └────────┬────────┘            │
│           │                             │                     │
│           └─────────────┬───────────────┘                     │
│                         │                                     │
└─────────────────────────┼─────────────────────────────────────┘
                          │
                          ↓
┌────────────────────────────────────────────────────────────────┐
│                        API LAYER                               │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  FastAPI Application (app/main.py)                             │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   /api/ask   │  │ /api/locate  │  │ /api/report  │        │
│  │              │  │              │  │              │        │
│  │ • Q&A        │  │ • Doc search │  │ • Generate   │        │
│  │ • Citations  │  │ • Page locate│  │   reports    │        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │
│         │                 │                 │                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  /healthz    │  │ /index-stats │  │   /metrics   │        │
│  │              │  │              │  │              │        │
│  │ • Health     │  │ • Index info │  │ • Prometheus │        │
│  │   checks     │  │ • Statistics │  │   metrics    │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                │
│  Middleware:                                                   │
│  • CORSMiddleware (cross-origin)                              │
│  • LoggingMiddleware (request/response logs)                  │
│  • TracingMiddleware (distributed tracing)                    │
│  • RateLimitMiddleware (rate limiting)                        │
│                                                                │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ↓
┌────────────────────────────────────────────────────────────────┐
│                      BUSINESS LOGIC LAYER                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │              RAG Pipeline (app/rag/)                 │     │
│  ├──────────────────────────────────────────────────────┤     │
│  │                                                      │     │
│  │  • query_transform.py:  Query preprocessing         │     │
│  │  • retriever.py:        Hybrid retrieval (legacy)   │     │
│  │  • weaviate_retriever.py: Weaviate retrieval        │     │
│  │  • hybrid_weaviate_opensearch_retriever.py: Modern  │     │
│  │  • reranker.py:         BGE CrossEncoder reranking  │     │
│  │  • generator.py:        Answer generation           │     │
│  │  • citation_retriever.py: Citation extraction       │     │
│  │  • citation_validator.py: CiteFix-lite validation   │     │
│  │                                                      │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │            Services (app/services/)                  │     │
│  ├──────────────────────────────────────────────────────┤     │
│  │                                                      │     │
│  │  • llm_client.py:   LLM service (Gemini/OpenAI)     │     │
│  │  • embedding.py:    Embedding service               │     │
│  │  • reranker.py:     Reranker service                │     │
│  │  • locator.py:      Document locator                │     │
│  │  • reporter.py:     Report generator                │     │
│  │                                                      │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ↓
┌────────────────────────────────────────────────────────────────┐
│                      DATA ACCESS LAYER                         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │           Indexers (app/rag/indexers/)               │     │
│  ├──────────────────────────────────────────────────────┤     │
│  │                                                      │     │
│  │  • bm25_indexer.py:  BM25 inverted index (offline)  │     │
│  │  • faiss_indexer.py: FAISS vector index (legacy)    │     │
│  │  • opensearch_bm25_retriever.py: OpenSearch client  │     │
│  │                                                      │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │            Storage (app/storage/)                    │     │
│  ├──────────────────────────────────────────────────────┤     │
│  │                                                      │     │
│  │  • version_manager.py:  Version control             │     │
│  │  • manifest_writer.py:  Manifest generation         │     │
│  │  • parquet_adapter.py:  Parquet I/O                 │     │
│  │                                                      │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ↓
┌────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │   Weaviate     │  │  OpenSearch    │  │     FAISS      │  │
│  │ Vector Database│  │  BM25 Index    │  │  (Legacy)      │  │
│  │                │  │                │  │                │  │
│  │ • Port: 8080   │  │ • Port: 9200   │  │ • Local files  │  │
│  │ • gRPC: 50051  │  │ • Docs: 4,883  │  │ • 768D vectors │  │
│  │ • Docker       │  │ • Docker       │  │                │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  │
│                                                                │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │  Gemini API    │  │  OpenAI API    │  │  File System   │  │
│  │                │  │  (Optional)    │  │                │  │
│  │ • LLM          │  │ • LLM          │  │ • chunks.jsonl │  │
│  │ • Embedding    │  │ • Embedding    │  │ • doc_id_map   │  │
│  │ • Vision       │  │                │  │ • manifests    │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. DATA FLOW DIAGRAMS

### 3.1 Ingestion Data Flow

```
[Raw PDFs] → [Parse] → [OCR?] → [Extract Tables] → [Chunk] → [Dedup] → [Outputs]
                                                                            ↓
                                                                    [chunks.jsonl]
                                                                    [doc_id_map.json]
                                                                    [quarantine.jsonl]
```

### 3.2 Indexing Data Flow

```
[chunks.jsonl] → [Read chunks]
                      ↓
          ┌───────────┴────────────┐
          │                        │
          ↓                        ↓
    [Embed chunks]          [Tokenize chunks]
          ↓                        ↓
    [Insert Weaviate]        [Insert OpenSearch]
          ↓                        ↓
    [Weaviate DB]            [OpenSearch Index]
```

### 3.3 Query Data Flow

```
[User Query]
    ↓
[Transform] (normalize, extract filters)
    ↓
[Parallel Retrieval]
    ├─ [Weaviate Search] (semantic)
    └─ [OpenSearch BM25] (keyword)
    ↓
[RRF Fusion] (merge & rank)
    ↓
[BGE Rerank] (optional, CrossEncoder)
    ↓
[Select Top-k] (default 8)
    ↓
[Generation Strategy]
    ├─ [Text-only] (Gemini Flash)
    └─ [Vision] (Gemini Pro + PDF pages)
    ↓
[Answer + Citations]
    ↓
[Post-validate] (CiteFix-lite)
    ↓
[Calculate Confidence]
    ↓
[Build Response]
    ↓
[JSON Response to Client]
```

---

## 4. SEQUENCE DIAGRAMS

### 4.1 Ask Flow (Complete Sequence)

```
┌──────┐   ┌─────┐   ┌───────┐   ┌─────────┐   ┌────────┐   ┌─────────┐
│Client│   │ API │   │ QueryTx│   │Retriever│   │Reranker│   │Generator│
└──┬───┘   └──┬──┘   └───┬───┘   └────┬────┘   └───┬────┘   └────┬────┘
   │          │          │            │            │             │
   │ POST     │          │            │            │             │
   │ /api/ask │          │            │            │             │
   ├─────────>│          │            │            │             │
   │          │          │            │            │             │
   │          │ transform│            │            │             │
   │          ├─────────>│            │            │             │
   │          │          │ normalize  │            │             │
   │          │          │ extract    │            │             │
   │          │          │ filters    │            │             │
   │          │<─────────┤            │            │             │
   │          │ query'   │            │            │             │
   │          │          │            │            │             │
   │          │ retrieve │            │            │             │
   │          ├──────────┼───────────>│            │             │
   │          │          │ parallel:  │            │             │
   │          │          │ Weaviate + │            │             │
   │          │          │ OpenSearch │            │             │
   │          │          │ RRF fusion │            │             │
   │          │<─────────┼────────────┤            │             │
   │          │ results  │            │            │             │
   │          │          │            │            │             │
   │          │ rerank   │            │            │             │
   │          ├──────────┼────────────┼───────────>│             │
   │          │          │            │ BGE Cross  │             │
   │          │          │            │ Encoder    │             │
   │          │<─────────┼────────────┼────────────┤             │
   │          │ top-k    │            │            │             │
   │          │          │            │            │             │
   │          │ generate │            │            │             │
   │          ├──────────┼────────────┼────────────┼────────────>│
   │          │          │            │            │ strategy:  │
   │          │          │            │            │ text/vision│
   │          │          │            │            │ LLM call   │
   │          │          │            │            │ extract    │
   │          │          │            │            │ citations  │
   │          │          │            │            │ validate   │
   │          │          │            │            │ confidence │
   │          │<─────────┼────────────┼────────────┼─────────────│
   │          │ answer + │            │            │             │
   │          │ citations│            │            │             │
   │          │          │            │            │             │
   │          │ build    │            │            │             │
   │          │ response │            │            │             │
   │          │          │            │            │             │
   │<─────────┤          │            │            │             │
   │ 200 JSON │          │            │            │             │
   │          │          │            │            │             │
```

### 4.2 Ingestion Flow (Simplified)

```
┌────────┐   ┌─────────┐   ┌─────────┐   ┌──────┐
│FileWalk│   │PDFParser│   │ Chunker │   │Dedup │
└───┬────┘   └────┬────┘   └────┬────┘   └──┬───┘
    │             │             │           │
    │ for each   │             │           │
    │ PDF file   │             │           │
    ├───────────>│             │           │
    │            │ parse       │           │
    │            ├────────────>│           │
    │            │ text        │ chunk     │
    │            │             ├──────────>│
    │            │             │ chunks    │ dedup
    │            │             │           ├──────>
    │            │             │           │
    │<───────────┼─────────────┼───────────┤
    │            │             │ unique    │
    │            │             │ chunks    │
    │            │             │           │
```

---

## 5. DEPLOYMENT ARCHITECTURE

### 5.1 Local Development

```
┌──────────────────────────────────────────────────────────┐
│                    Developer Machine                     │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │           Python 3.11 (.venv)                │       │
│  │  ┌─────────────────────────────────────┐    │       │
│  │  │      FastAPI Application            │    │       │
│  │  │      Port: 8000                     │    │       │
│  │  └─────────────────────────────────────┘    │       │
│  │  ┌─────────────────────────────────────┐    │       │
│  │  │      Streamlit UI                   │    │       │
│  │  │      Port: 8502                     │    │       │
│  │  └─────────────────────────────────────┘    │       │
│  └──────────────────────────────────────────────┘       │
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │         Docker Desktop                       │       │
│  │  ┌─────────────┐  ┌─────────────┐          │       │
│  │  │ Weaviate    │  │ OpenSearch  │          │       │
│  │  │ :8080,50051 │  │ :9200       │          │       │
│  │  └─────────────┘  └─────────────┘          │       │
│  └──────────────────────────────────────────────┘       │
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │         File System                          │       │
│  │  • D:\Data_Raw (PDFs)                        │       │
│  │  • artifacts/ (ingestion, indices)           │       │
│  └──────────────────────────────────────────────┘       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 5.2 Production Deployment (Server)

```
┌──────────────────────────────────────────────────────────────┐
│                    Production Server                         │
│                (Ubuntu 20.04 / Windows Server)               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │               Nginx (Reverse Proxy)                │     │
│  │               Port: 80, 443 (HTTPS)                │     │
│  └──────────────────────┬─────────────────────────────┘     │
│                         │                                    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │          FastAPI Application (systemd)             │     │
│  │          Port: 8000 (internal)                     │     │
│  │          Workers: 4 (gunicorn/uvicorn)             │     │
│  └────────────────────────────────────────────────────┘     │
│                         │                                    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │              Docker Compose Stack                  │     │
│  │  ┌──────────────────┐  ┌──────────────────┐       │     │
│  │  │   Weaviate       │  │  OpenSearch      │       │     │
│  │  │   (Persistent)   │  │  (Persistent)    │       │     │
│  │  │   :8080, :50051  │  │  :9200           │       │     │
│  │  └──────────────────┘  └──────────────────┘       │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              Prometheus + Grafana                  │     │
│  │              (Monitoring & Alerting)               │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              File System                           │     │
│  │  • /mnt/data/raw (PDFs - NAS mount)                │     │
│  │  • /opt/pvcfc-rag/artifacts (ingestion, indices)   │     │
│  │  • /var/log/pvcfc-rag (logs)                       │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                         │
                         ↓
           ┌────────────────────────────┐
           │    External Services       │
           ├────────────────────────────┤
           │  • Gemini API (Google)     │
           │  • OpenAI API (Optional)   │
           └────────────────────────────┘
```

---

## 📚 RELATED DOCUMENTATION

- [PROJECT_MASTERY_GUIDE.md](PROJECT_MASTERY_GUIDE.md) - Comprehensive project guide
- [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) - Detailed architecture description
- [README.md](../README.md) - Main project README

---

**Last Updated**: 2025-10-12
**Version**: 1.0.0
**Status**: ✅ Complete
