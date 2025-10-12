# PVCFC RAG API — Developer Handbook (Phase 1 + Phase 2)

Tài liệu này tổng hợp, cô đọng và hướng dẫn thực thi dành cho developer, gộp toàn bộ nội dung cốt lõi của Phase 1 (Document Processing & Indexing) và Phase 2 (RAG API).

## 0. Chuẩn bị môi trường
- Python 3.11 (64-bit), venv khuyến nghị
- Windows: PowerShell scripts (`scripts/*.ps1`) đã sẵn
- Cài đặt:
  ```bash
  pip install -r requirements.txt
  ```
- .env (ví dụ quan trọng):
  ```env
  APP_ENV=local
  API_PORT=8000
  LOG_LEVEL=INFO
  LLM_PROVIDER=gemini
  LLM_LIGHT_PROVIDER=gemini
  LLM_MODEL_LIGHT=gemini-2.5-flash
  LLM_MODEL_HEAVY=gemini-2.5-pro
  GEMINI_API_KEY=...           # bắt buộc cho Phase 2
  EMBEDDING_PROVIDER=gemini    # Phase 2
  EMBEDDING_MODEL=gemini-embedding-001  # 768D, Aug 2024 release
  ```

---

## 1. Phase 1 — Document Processing & Indexing

### 1.1 Pipeline tổng quan
Extract → Normalize → Convert (Markdown) → Chunk → Index (BM25/FAISS)

- DocumentDetector (`app/rag/document_detector.py`): phân loại vector/scan/mixed
- VectorExtractor (`app/rag/extractors/vector_extractor.py`): trích xuất text + cấu trúc
- Normalizers (`app/rag/normalizers/*.py`): text/unit/tag normalization
- MarkdownConverter (`app/rag/converters/markdown_converter.py`): xuất Markdown có cấu trúc
- HierarchicalChunker (`app/rag/chunkers/hierarchical_chunker.py`): chunk thông minh
- BM25Indexer (`app/rag/indexers/bm25_indexer.py`): tạo chỉ mục từ chunks

### 1.2 Ingestion CLI (Multithread + OCR + JSONL)
Sử dụng công cụ ingest mới để xử lý thư mục PDF và tạo artifacts (Markdown, processed JSON, chunks JSON/JSONL, manifests JSONL).

```bash
# Ingest cơ bản (hierarchical chunking mặc định)
python tools/ingest.py \
  --source-dir data/raw/phase1_pilot \
  --output-dir artifacts/ingestion \
  --workers 4 \
  --chunk-size 500 \
  --chunk-overlap 50

# Bật OCR (nếu có Tesseract):
python tools/ingest.py \
  --source-dir data/raw/phase1_pilot \
  --output-dir artifacts/ingestion_ocr \
  --workers 4 \
  --enable-ocr --ocr-lang eng

# Chọn parser (auto|pymupdf|unstructured):
python tools/ingest.py \
  --source-dir data/raw/phase1_pilot \
  --output-dir artifacts/ingestion_auto \
  --parser auto

# Chọn chiến lược chunking:
#  - hierarchical (mặc định)
#  - sentence-window (dựa trên số câu/window + overlap%)
#  - small-to-big (tích luỹ từ câu nhỏ lên chunk lớn, giữ parent-child)
python tools/ingest.py \
  --source-dir data/raw/phase1_pilot \
  --output-dir artifacts/ingestion_stb \
  --chunk-strategy small-to-big \
  --chunk-size 500 --chunk-overlap 50

# sentence-window với 2 câu/window và overlap 50%
python tools/ingest.py \
  --source-dir data/raw/phase1_pilot \
  --output-dir artifacts/ingestion_sw \
  --chunk-strategy sentence-window \
  --sentence-window-size 2 \
  --chunk-overlap 50
```

Artifacts chính được tạo:
- Markdown: `.../markdown/{doc_id}.md` (+ `{doc_id}.json` chứa cấu trúc heading)
- Processed docs: `.../documents/*_processed.json`
- Chunks:
  - Per-doc JSON: `.../chunks/{doc_id}_chunks.json` (back-compat)
  - Toàn bộ JSONL: `.../chunks/chunks.jsonl` (một chunk mỗi dòng)
- Manifests JSONL:
  - `.../manifests/corpus.jsonl` (doc-level)
  - `.../manifests/checksums.jsonl` (idempotent ingest)

### 1.3 Build BM25 từ JSONL hoặc JSON
```bash
# Build từ JSONL
python tools/build_bm25_index.py \
  --chunks-jsonl artifacts/ingestion/chunks/chunks.jsonl \
  --index-dir artifacts/index/bm25

# Hoặc dùng chunks.json cũ
python tools/build_bm25_index.py \
  --use-existing-chunks \
  --chunks-dir artifacts/ingestion/chunks \
  --index-dir artifacts/index/bm25
```

### 1.4 Kiểm thử
- Unit tests: `pytest -q`
  - `tests/test_chunk_hierarchy.py` bao gồm kiểm tra:
    - Parent-child relationships trong hierarchical
    - Chiến lược `sentence-window`
    - Chiến lược `small-to-big`
- Quality: `tools/qa_extraction.py`
- Artifacts Phase 1:
  - `artifacts/index/bm25/` (BM25)
  - `artifacts/ingestion/...` (ingest outputs: markdown, documents, chunks, manifests)

### 1.5 Lưu ý kỹ thuật chunking
- Hierarchical: tạo parent chunk từ heading, child chunks trong section có `parent_chunk_id`.
- Sentence-window: dựa trên số câu/window, overlap theo % số câu (ví dụ window=2, overlap=50% → step=1 câu).
- Small-to-big: tích luỹ từ câu (nhỏ) lên chunk (lớn), giữ parent-child theo heading, overlap 1 câu khi vượt ngưỡng.
- Tất cả chiến lược ghi metadata bắt buộc trên chunk: `doc_id`, `page_start`, `page_end`, `heading`, `level`, và metadata: `doc_type`, `revision`, `source_format`, `file_name`.

### 1.6 Benchmark nhanh (pilot set, chunk-size=500, overlap=50%, workers=4)
- hierarchical: total_chunks=3736, avg_char_count≈156.5, min=1, max=3485
- sentence-window (window=2): total_chunks=2818, avg_char_count≈259.4, min=8, max=2329
- small-to-big: total_chunks=3378, avg_char_count≈161.6, min=1, max=2009

Gợi ý:
- Cần nhiều chunk (chi tiết, parent-child): hierarchical/small-to-big.
- Ưu tiên mạch câu, ít chunk hơn: sentence-window.

---

## 2. Phase 2 — RAG API (Hybrid Retrieval + Rerank + Generation)

### 2.1 Kiến trúc luồng /ask
1) QueryTransformer (`app/rag/query_transform.py`): normalize + intent + optional HyDE
2) HybridRetriever (`app/rag/retriever.py`): BM25 + FAISS + RRF + expand‑parent
3) Reranker (`app/rag/reranker.py`): cross‑encoder (optional)
4) ResponseGenerator (`app/rag/generator.py`): buộc citations
5) CoVe (`app/rag/cove.py`): xác thực claim (dùng `QueryTransformer` + `retriever.search`)

### 2.2 API endpoints
- Ask: `app/api/routers/ask.py` (POST /ask)
- Locate: `app/api/routers/locate.py` (POST /locate)
- Report: `app/api/routers/report.py` (POST /report)
- Monitoring: `/metrics`, `/trace`, `/index-stats`

### 2.3 Indices loader
- `app/deps/indices.py`: dùng `create_hybrid_retriever()` để mở chỉ mục
- Yêu cầu dữ liệu chỉ mục tồn tại:
  - `artifacts/index/bm25/`
  - `artifacts/index/faiss/` (nếu dùng vector search)

### 2.4 Build chỉ mục với Gemini embeddings
```bash
# Build FAISS từ dữ liệu processed + Gemini embeddings
python tools/build_faiss_local.py --input data/processed --output artifacts/index/faiss
```

### 2.5 Cấu hình LLM & Embeddings
- LLM: `app/services/llm.py` + `app/services/llm_client.py` (Gemini new SDK `google-genai`)
- Embeddings: `app/services/embedding_enhanced.py` (`google-generativeai` `gemini-embedding-001`, 768D)

### 2.6 Middleware & Controls
- RateLimit: `app/core/rate_limit.py` (Token bucket 60 rpm, burst 20)
- Tracing: `app/core/tracing.py` (spans/tags, `/trace`)
- Metrics: `app/core/metrics.py` (Prometheus)
- Cache: `app/core/cache.py` (LRU caches cho retrieve/rerank/transform)

### 2.7 API examples (cURL)
```bash
# ASK
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Áp suất vận hành của KT06101?",
    "hyde": true,
    "max_context": 8,
    "language": "vi"
  }'

# LOCATE
curl -X POST http://localhost:8000/locate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "KT06101",
    "max_hits": 10
  }'

# REPORT
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Thông số vận hành KT06101",
    "sub_queries": ["áp suất", "nhiệt độ"],
    "format": "markdown",
    "language": "vi"
  }'

# Monitoring
curl -X GET http://localhost:8000/metrics
curl -X GET http://localhost:8000/trace
curl -X GET http://localhost:8000/index-stats
```

### 2.8 Known issues & workarounds
- Indices chưa build → search trống: chạy tools build BM25/FAISS trước khi test.
- PyMuPDF DLL (Windows): cài VC++ redistributable; `pip install --force-reinstall pymupdf==1.24.9`; ưu tiên WSL/Container.
- Cross‑encoder nặng trên Windows không GPU: cân nhắc disable/giảm `top_k`.

---

## 3. Quy trình dev tiêu chuẩn
1) Cập nhật `.env` theo provider (Gemini/OpenAI) và embeddings (Gemini `gemini-embedding-001`).
2) Build indices (BM25/FAISS).
3) Chạy server: `python -m app.main`.
4) Kiểm thử endpoints: `/ask`, `/locate`, `/report`.
5) Theo dõi `/metrics`, `/trace`, `/index-stats` để tối ưu.

## 4. Troubleshooting nhanh
- Server không start: kiểm tra port 8000, logs, `.env` và quyền PowerShell.
- 5xx từ routers: kiểm tra đã load retriever chưa (startup), indices đã tồn tại chưa.
- Latency cao: tắt HyDE, giảm `max_context`, disable cross‑encoder.
- Response thiếu citations: kiểm tra pipeline generator + CoVe warnings.

## 5. Tham chiếu nhanh
- Phase 1 summary: `CHANGLOG_README/phase1_final_report.md`
- Phase 2 summary: `CHANGLOG_README/Phase2_Final_Report.md`
- Roadmap & notes: `docs/phase2_implementation_roadmap.md`, `docs/phase2_implementation_summary.md`
- LLM config tiers & providers: `docs/llm_config_tiers.md`, `docs/provider_flexibility_guide.md`
