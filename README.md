
# PVCFC RAG — README - UPDATE AT 5:30AM - 13/10/2025

Hệ thống **RAG (Retrieval-Augmented Generation)** phục vụ **tra cứu, trích xuất, và hỏi-đáp kỹ thuật** trên tập tài liệu của PVCFC, với trọng tâm là **độ tin cậy, trích nguồn đầy đủ, và thao tác nhanh** trên dữ liệu nội bộ.

* **Use-cases chính**:

  * **Tìm & trích xuất**: nhanh chóng tìm đúng *tài liệu và **trang*** nhắc tới nội dung câu hỏi.
  * **Hỏi-đáp có trích dẫn**: trả lời ngắn gọn, **đính kèm nguồn (doc_id + page)** để kiểm chứng.
  * **Báo cáo tự động**: sinh báo cáo từ ngôn ngữ tự nhiên (AI), có danh mục trích dẫn.
  * **Metadata từ tín hiệu/thiết bị**: suy luận **equipment_id**, **doc_type**, vendor, revision… từ ngữ cảnh và nội dung tài liệu, **thay cho thao tác thủ công**.

> **Phạm vi dữ liệu (V1)**: tập trung **PDF** (vector + scan). **Dư địa sẵn sàng** cho Office (Word/Excel/PowerPoint) — sẽ bật dần theo lộ trình. **Chưa yêu cầu bbox** (highlight từng chữ); sẽ phát triển ở giai đoạn sau.

---

## 1) Vì sao dự án này tồn tại?

* **Tài liệu phân tán & không đồng nhất**: manual, datasheet, P&ID, quy trình bảo trì… nằm ở nhiều thư mục, cấu trúc không thống nhất, có nhiều bản scan/phiên bản.
* **Tra cứu thủ công mất thời gian**: khó tìm đúng *trang* và *đoạn* cần; dễ lẫn phiên bản.
* **Nhu cầu quyết định nhanh & có chứng cứ**: kỹ sư/QA cần **câu trả lời có trích dẫn** để tin cậy và đối chiếu.

**Giải pháp**: chuẩn hoá ingest → lập chỉ mục **lai** (BM25 + Weaviate) → **hỏi-đáp có trích dẫn theo trang** (và, khi phù hợp, **multimodal** để nhìn được trang PDF), kèm **báo cáo** và **metadata** chiết xuất tự động.

---

## 2) Mục tiêu & Phạm vi (V1)

* **Quét đệ quy** toàn bộ **PDF** dưới root `D:\Data_Raw` (ổ rời), **không phụ thuộc cấu trúc thư mục**.
* **OCR khi cần** (PDF scan), ngôn ngữ `vie+eng`.
* **Dedup 100% nội dung**: trùng nội dung chỉ **01 bản đại diện** vào index; near-duplicate **giữ cả hai**.
* **Truy vấn kết hợp**: BM25 (từ khóa) ∪ Weaviate (ngữ nghĩa) + BGE rerank.
* **Câu trả lời có trích dẫn**: tối thiểu `doc_id + page` (1-based). Có `pdf_path` nếu map được.
* **Báo cáo**: tạo **bản báo cáo tạm** từ ngôn từ AI, xuất định dạng cơ bản (Markdown/Docx) — sẽ tinh chỉnh mẫu sau.
* **Metadata**: suy luận/điền **equipment_id**, **doc_type** (và trường mở rộng) dựa vào path + nội dung.
* **Giới hạn tài nguyên**: RAM ≤ **12 GB** khi build/search; batching + cache.

> **Office (docx/xlsx/pptx)**: **chưa bật** ở V1, nhưng kiến trúc đã **sẵn sàng mở rộng**.

---

## 3) Kiến trúc tổng thể

**Offline (Build):**

1. **Ingest**: đọc PDF (vector/scan), OCR khi cần → chuẩn hoá văn bản → **chunk** + metadata.
2. **Dedup**: `content_hash` để gộp **trùng nội dung** (đại diện: *vector > scan > size > mtime > path ngắn*).
3. **Index**:

   * **BM25**: chỉ mục từ khóa (nhẹ, dễ bảo trì).
   * **Weaviate**: vector database (embedding 768D), production-grade với gRPC.

**Online (Serve):**

1. **Query transform** (HyDE/chuẩn hoá ngôn ngữ — tuỳ chọn).
2. **Hybrid retrieval** (BM25 ∪ Weaviate) → hợp nhất + **BGE rerank**.
3. **Generation**:

   * **Text-only** (mặc định).
   * **Multimodal (Vision)** khi **có trang PDF liên quan** (kết hợp **văn bản + ảnh trang** để tăng độ chính xác theo ngữ cảnh).
4. **Trả về**: **answer**, **citations (doc_id + page)**, **metadata**, và **báo cáo** nếu yêu cầu.

---

## 4) Dữ liệu, OCR, Dedup & Quarantine

* **Root dữ liệu**: `D:\Data_Raw` (cố định).
* **OCR**: chỉ bật khi không có text vector; `vie+eng`; DPI 300 (tự tăng 400–600 với trang nhỏ/mờ).
* **Dedup**:

  * `file_hash = SHA256(file_bytes)` → trùng **file y hệt**.
  * `content_hash = SHA1(normalized_text)` → trùng **nội dung**; **chỉ đại diện** vào index.
* **Quarantine (log, không di chuyển file)**: `{output_dir}/quarantine.jsonl` ghi `corrupt|password|ocr_failed|read_error`.
  - Ví dụ với `--output-dir artifacts/ingestion`: `artifacts/ingestion/quarantine.jsonl`
* **doc_id_map.json**: `{output_dir}/doc_id_map.json` ánh xạ `doc_id → pdf_path` để **enrich citation** và **render trang**.

---

## 5) Chunking & Metadata

* **Chunk V1**: theo **ký tự** `size=1000`, `overlap=200` (configurable).
* **Metadata tối thiểu**: `doc_id`, `page / page_start / page_end`, `source_format (vector|scan)`.
* **Taxonomy (mở)**:

  * `equipment_id`: regex gợi ý **`\bKT?\d{5}\b`** → bắt **K06101**/**KT06101**.
  * `doc_type` (đề xuất danh sách đóng nhưng **mở rộng dần**): `Manual`, `Drawing`, `Instrument`, `Maintenance`, `Data/Spec`, `SpareParts`, `Procedure`, `Report`, `Certificate`…
  * `vendor`, `revision`, `language`, `year`… (tuỳ dữ liệu).

> **Lưu ý taxonomy**: hiện **chưa “đóng”**. Ta bắt đầu với danh sách đề xuất và **mở dần** theo dữ liệu thực tế.

---

## 6) Indexing (BM25 & Weaviate)

* **BM25**: engine nhẹ trong repo (rank-bm25), parameters: k1=1.2, b=0.75, epsilon=0.25.
  * 4,883 chunks indexed
  * Simple tokenization (lowercase + regex)
  * Fast keyword search

* **Weaviate Vector Database** (Production-grade):
  * **Embedding**: Tùy config ENV (ví dụ: `gemini-embedding-001` 768D, `intfloat/multilingual-e5-small` 384D).
  * **Dimension tự động**: Service auto-detect từ model.
  * **gRPC Support**: High-performance communication (port 50051).
  * **Health Monitoring**: Built-in health checks and statistics.
  * **Scalability**: Production-ready for millions of vectors.
  * **Docker Deployment**: Easy setup with docker-compose.

* **BGE Reranking**: BAAI/bge-reranker-base for semantic reranking
  * Multi-level support: chunk, document, page
  * Aggregation methods: max, mean, top3_mean
  * Configurable via `ENABLE_BGE_RERANK=true`

### 6.1) Hybrid Retrieval Modes (Modern vs Legacy)

- `USE_HYBRID_MODERN=true`  → Modern Hybrid: Weaviate (semantic) + OpenSearch BM25 (keyword)
  - Parallel search → RRF fusion → optional BGE rerank
  - Health checks: nếu 1 backend lỗi → chạy ở chế độ degraded (backend còn lại)
- `USE_HYBRID_MODERN=false` → Legacy Hybrid: FAISS (semantic) + Offline BM25 (keyword)

Notes:
- Weaviate-only mode không còn cần thiết: Modern Hybrid tự degrade nếu OpenSearch không khả dụng.
- Legacy dùng cho fallback thủ công khi cần.

### 6.2) OpenSearch (BM25 remote)

- Index: `rag_chunks` (hiện có 4,883 documents)
- BM25 params: `k1=1.2`, `b=0.75`
- ENV:
  - `OPENSEARCH_HOST`, `OPENSEARCH_PORT`, `OPENSEARCH_INDEX`
  - `OPENSEARCH_BM25_K1`, `OPENSEARCH_BM25_B`, `OPENSEARCH_TIMEOUT`

### 6.3) Known limitation (Weaviate filter)

- Một số phiên bản Weaviate SDK không hỗ trợ truyền `where` vào `near_vector()` → lỗi: `... got an unexpected keyword argument 'where'`.
- Hệ thống đã xử lý degrade: nếu Weaviate lỗi, vẫn dùng được OpenSearch BM25.
- Cách khắc phục chính thức: nâng cấp `weaviate-client` hoặc điều chỉnh chiến lược áp filter.

---

## 7) Truy vấn, Rerank & Trích dẫn theo trang

* **Retrieval k**: Configurable qua request parameter `max_context` (default=8, max=20). Hybrid search lấy nhiều candidates từ BM25 và Weaviate, sau đó rerank và chọn top-k.

* **BGE Reranking** (BAAI/bge-reranker-base):
  * **Khi bật**: `ENABLE_BGE_RERANK=true` trong .env
  * **Cấu hình**:
    - `BGE_RERANK_CANDIDATE_LIMIT=50`: Số candidates trước khi rerank
    - `BGE_RERANK_TOP_K=10`: Số kết quả cuối cùng
    - `BGE_RERANK_LEVEL=chunk`: Rerank level (chunk/doc/page)
    - `BGE_RERANK_AGGREGATION=max`: Phương pháp tổng hợp (max/mean/top3_mean)
  * **Fallback**: Nếu rerank thất bại, sử dụng score-based ranking

* **Legacy Reranking** (khi BGE tắt):
  * Cross-encoder (`ms-marco-MiniLM-L-6-v2`) cho **EN**
  * Score-based rerank cho **VI** (tránh NaN)

* **Citations**: trả về tối thiểu `doc_id + page (1-based)`. Có `pdf_path` nếu map được từ `doc_id_map.json`.
* **Tìm đúng trang**: metadata giữ `page / page_start / page_end` từ ingest → pipeline trả ra trang **được tham chiếu** (không cần bbox ở V1).

---

## 8) Generation (LLM tiers & Multimodal Vision)

* **Heavy (LLM)**: `gemini-2.5-pro` (multimodal).
* **Light (LLM)**: `gemini-2.5-flash` (text-only).
* **Multimodal Vision (khi phù hợp)**:

  * **Điều kiện**: có documents liên quan và **map được `pdf_path`** (từ `doc_id_map.json`).
  * **Chọn trang**:
    - Nếu có cả `page_start` và `page_end` (cả 2 non-None) → lấy **full range**; swap nếu start > end.
    - Nếu chỉ có `page` → **cửa sổ ±2** (start = max(1, page-2); end = page+2).
    - Clamp theo `total_pages` nếu biết được từ PDF.
    - **Tối đa 10 trang**, *1-based*, **dedup** theo `(pdf_path, page)`.
  * **Render nội bộ**: JPEG @ **DPI=200**; trang lỗi → **bỏ qua** và ghi `pages_failed`.
  * **Mục tiêu**: tăng **độ chính xác** nhờ bối cảnh trực quan (layout/bảng/đơn vị), **không** là pipeline verify rời.

> Nếu retrieval không có tài liệu phù hợp → **text-only**.

---

## 9) Báo cáo / Report (V1)

* **Mục tiêu**: tạo **bản báo cáo tạm** từ ngôn ngữ AI (tóm tắt/câu trả lời + **danh mục trích dẫn**).
* **Định dạng xuất**: **Markdown** (ưu tiên vì dễ xem & lưu), có thể thêm **Docx** đơn giản.
* **Nội dung**: tiêu đề, câu hỏi, câu trả lời, **các citations (doc_id + page + pdf_path nếu có)**, ngày giờ, trace_id.
* **Lộ trình**: sau này thay bằng **mẫu Word/PDF chuẩn** (theo yêu cầu của bạn/QA).

---

## 10) KPI chấp nhận (V1)

* **SME AcceptableAnswer ≥ 80%** (đánh giá thủ công trên tập golden Q/A).
* (Khuyến nghị bổ sung cho nội bộ)

  * **Citation Correctness ≥ 90%** (trang trích dẫn đúng tài liệu & vùng nội dung liên quan).
  * **Faithfulness / Context Precision** theo RAGAs (chạy nội bộ để theo dõi).

---

## 11) Cấu hình, Cài đặt & Chạy

**.env (rút gọn)**

```ini
# App config
APP_ENV=local  # local|dev|prod
API_PORT=8000
LOG_LEVEL=INFO  # DEBUG|INFO|WARNING|ERROR

# Providers & LLM
LLM_PROVIDER=gemini  # openai|gemini|none
LLM_TIER=light
LLM_LIGHT_PROVIDER=gemini
LLM_MODEL_HEAVY=gemini-2.5-pro
LLM_MODEL_LIGHT=gemini-2.5-flash

# Embedding
EMBEDDING_PROVIDER=gemini  # gemini|openai|local|none
EMBEDDING_LLM=gemini
EMBEDDING_MODEL=gemini-embedding-001  # dimension auto-detect từ model
EMBED_OUTPUT_DIM=768
EMBED_TASK=retrieval_document  # task type (NO inline comments!)
# Batching & concurrency (optional, có default hợp lý)
EMBED_BATCH_SIZE=256  # số texts per internal batch
EMBED_CONCURRENCY=8   # số concurrent requests
EMBED_MAX_TOKENS_PER_REQ=20000
EMBED_TPM_CAP=1000000
EMBED_RPM_CAP=3000

# Retrieval Modes
USE_HYBRID_MODERN=true  # true: Weaviate+OpenSearch (modern), false: FAISS+BM25 offline (legacy)
RETRIEVAL_ALLOW_BM25_ONLY_FALLBACK=true
BM25_K_WHEN_DEGRADE=80
RERANK_TOP_N_WHEN_DEGRADE=50
RETRIEVE_CACHE_TTL_MIN=10

# OpenSearch (BM25 remote)
OPENSEARCH_ENABLED=true
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=rag_chunks
OPENSEARCH_BM25_K1=1.2
OPENSEARCH_BM25_B=0.75
OPENSEARCH_TIMEOUT=10

# Weaviate Vector Database (Phase 4)
WEAVIATE_ENABLED=true  # Configure Weaviate service (mode selection uses USE_HYBRID_MODERN)
WEAVIATE_HOST=localhost
WEAVIATE_PORT=8080  # HTTP port
WEAVIATE_GRPC_PORT=50051  # gRPC port (faster)
WEAVIATE_USE_GRPC=true
WEAVIATE_COLLECTION=Chunk
WEAVIATE_RETRIEVAL_LIMIT=50

# BGE Reranking (Phase 3)
ENABLE_BGE_RERANK=false  # Enable BGE CrossEncoder reranking
BGE_RERANK_CANDIDATE_LIMIT=50
BGE_RERANK_TOP_K=10
BGE_RERANK_LEVEL=chunk  # chunk|doc|page
BGE_RERANK_AGGREGATION=max  # max|mean|top3_mean

# Vision gating (Phase 2)
VISION_PAGE_SELECTOR_ENABLED=true
TEXT_RANGE_SCAN_ENABLED=false

# API keys
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here  # nếu dùng OpenAI
```

**Cài đặt (Windows PowerShell)**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Ingest**

```powershell
python tools\ingest.py `
  --source-dir "D:\\Data_Raw" `
  --output-dir "artifacts\\ingestion" `
  --enable-ocr --ocr-lang "vie+eng" --parser auto `
  --chunk-size 1000 --chunk-overlap 200
```

**Build Production Indices**

```powershell
# Build both BM25 and FAISS/Weaviate indices
python tools\\ops\\build_production_indices.py
```

This will:
- Build BM25 index from chunks (4,883 documents)
- Build FAISS vector index (if WEAVIATE_ENABLED=false)
- Output to `artifacts/index_production/`

**OR: Setup Weaviate (Recommended for Production)**

```powershell
# 1. Start Weaviate with Docker
docker-compose -f docker-compose-weaviate.yml up -d

# 2. Ingest data to Weaviate
python scripts\\phase1_index_to_weaviate.py

# 3. Verify data
python scripts\\weaviate\\test_weaviate_search.py "CO2 compressor"
```

> **Lưu ý:** Weaviate là production-ready với gRPC support. FAISS vẫn hoạt động cho local development.

**Chạy API**

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Kiểm thử tích hợp (Hybrid Modern)

```powershell
# Yêu cầu: USE_HYBRID_MODERN=true và OpenSearch + Weaviate đang chạy
python tests\test_hybrid_modern.py
```

Kỳ vọng:
- Health checks: healthy hoặc degraded (không critical)
- Statistics: OpenSearch ~4,883 documents
- Search: kết quả từ cả Weaviate và OpenSearch (sau RRF; BGE tuỳ bật/tắt)

---

## 12) Endpoints (rút gọn)

* **POST `/api/ask`**
  **Request**:

  ```json
  {
    "query": "Áp suất vận hành tối đa của K06101?",
    "language": "vi",
    "max_context": 8,
    "enable_vision_generation": true
  }
  ```

**Response**:

```json
{
  "answer": "...",
  "citations": [{
    "doc_id": "DOCID_abc123",
    "page": 12,
    "bbox": null,
    "confidence": 0.95,
    "pdf_path": "D:\\...\\manual.pdf"
  }],
  "context_used": ["chunk_abc123", "chunk_def456"],
  "confidence": 0.82,
  "meta": {
    "model": "gemini-2.5-pro",
    "latency_ms": 1430,
    "breakdown": {
      "transform_ms": 120,
      "retrieve_ms": 450,
      "rerank_ms": 280,
      "generate_ms": 580
    },
    "k": 8,
    "execution_mode": "production",
    "trace_id": "xyz789",
    "vision_generation": {
      "pages_used": [{"pdf_path": "D:\\...\\manual.pdf", "page": 12}],
      "pages_failed": [],
      "excerpts": []
    }
  },
  "warnings": null
}
```

* **POST `/api/report`**
  Sinh báo cáo tạm (Markdown/Docx đơn giản) từ **answer + citations**.

* **POST `/api/locate`**
  Định vị trang liên quan (không yêu cầu bbox ở V1).

* **GET `/index-stats`**, **GET `/metrics`**, **GET `/trace`**.

---

## 13) Vận hành, Bảo trì & An toàn

* **Triển khai**: chạy **local trên laptop** (hiện tại). Có thể mở rộng **server nội bộ** về sau.
* **Auth**: **chưa yêu cầu** (dev). Khi mở ra mạng nội bộ → cần rate-limit và auth.
* **RAM guard**: batching & flush khi build; khi query, giảm `k_*` nếu cần.
* **Logs**: Vision gating ON/OFF, model, pages used/failed, latency breakdown.
* **Không mở trực tiếp** `D:\...` trên trình duyệt — **preview trang** qua endpoint render.
* **Chi phí**: **chưa giới hạn** ở V1 (sẽ bổ sung khi mở ra sản xuất).

---

## 14) Lộ trình mở rộng

* **Office docs**: bật ingest docx/xlsx/pptx (trích văn bản & bảng), hoặc convert → PDF → ingest.
* **BM25**: cân nhắc Pyserini/Lucene (disk-based).
* **FAISS**: IVF-PQ cho quy mô triệu vector (nlist/nprobe).
* **Chunk token-based** (350/50), bbox highlight.
* **OCR nâng cao** cho trang cực mờ (Google Vision).
* **Mẫu báo cáo chuẩn** (Word/PDF), template theo chuẩn nội bộ.

---

## 15) Tiêu chí chấp nhận (V1)

* 100% PDF trong `D:\Data_Raw` được xử lý **hoặc** có entry trong `quarantine.jsonl`.
* Sinh `chunks.jsonl`, `doc_id_map.json` (atomic), BM25 & FAISS sẵn sàng.
* Truy vấn trả về **câu trả lời có trích dẫn** (doc_id + page).
* Khi có tài liệu phù hợp → **có thể** bật multimodal (Vision) để **nâng độ chính xác**; nếu không có, chạy text-only.
* **SME AcceptableAnswer ≥ 80%** trên golden set nội bộ.

---

## 16) Cấu trúc thư mục dự án

```
Code - API_LLM_PVCFC/
├── .env, .env.example          # Configuration files
├── README.md                   # This file
├── CHANGELOG.md                # Version history
├── requirements.txt            # Python dependencies
├── docker-compose*.yml         # Docker configurations
├── Makefile                    # Build automation
│
├── app/                        # 🎯 Main application code
│   ├── api/                    # FastAPI routers and endpoints
│   ├── core/                   # Core configurations, logging, metrics
│   ├── deps/                   # Dependency injection
│   ├── ingestion/              # Document processing and ingestion
│   ├── rag/                    # RAG pipeline (retrieval, generation, reranking)
│   └── services/               # External services (LLM, embedding, vision)
│
├── streamlit_app/              # 🖥️ Streamlit UI
│   ├── app.py                  # Main Streamlit application
│   ├── components/             # UI components
│   └── pages/                  # Multi-page app pages
│
├── DOCUMENTS_CHATBOX/
│   ├── docs/                   # 📚 Documentation
│   │   ├── README.md           # Documentation index
│   │   ├── guides/             # User guides and tutorials
│   │   │   ├── WEAVIATE_SETUP_GUIDE.md
│   │   │   ├── WEAVIATE_QUICKSTART.md
│   │   │   ├── MANUAL_TESTING_CHECKLIST.md
│   │   │   └── question_example.md
│   │   ├── analysis/
│   │   ├── completion/
│   │   ├── implementation/
│   │   └── PROJECT_MASTERY_GUIDE.md
│   ├── CHANGLOG_README/
│   └── reports/
│
├── scripts/                    # 🔧 Utility scripts (NEW!)
│   ├── README.md               # Scripts index
│   ├── diagnostics/            # Diagnostic and debugging scripts
│   │   ├── check_pdf_pages.py
│   │   ├── deep_diagnostic.py
│   │   └── diagnose_pages.py
│   ├── utilities/              # General utility scripts
│   │   ├── build_indices_safe.py
│   │   ├── fix_doc_id_map.py
│   │   └── validate_reingestion.py
│   ├── weaviate/               # Weaviate-specific scripts
│   │   ├── setup_weaviate_embedded.py
│   │   └── test_weaviate_search.py
│   ├── phase1_index_to_weaviate.py  # Phase 1 ingestion
│   └── [other scripts]/        # Test scripts, examples, etc.
│
├── tools/                      # 🛠️ Build and maintenance tools
│   ├── ops/                    # Operations (production index building)
│   ├── analysis/               # Data analysis tools
│   └── benchmarks/             # Performance benchmarking
│
├── tests/                      # 🧪 Unit and integration tests
│
├── artifacts/                  # 📦 Generated artifacts
│   ├── ingestion_production/   # Ingested chunks and metadata
│   ├── index_production/       # BM25 and FAISS indices
│   │   ├── bm25/               # BM25 index files
│   │   └── faiss/              # FAISS vector index
│   └── logs/                   # Application logs
│
├── data/                       # 📁 Data (gitignored)
│   └── raw/                    # Raw PDF corpus
│
└── config/                     # ⚙️ Additional configurations
```

**Key directories:**
- **`DOCUMENTS_CHATBOX/docs/`** - All documentation organized by category (guides, analysis, completion)
- **`scripts/`** - All utility scripts organized by purpose (diagnostics, utilities, weaviate)
- **`app/`** - Main application code (FastAPI + RAG pipeline)
- **`tools/`** - Build tools and benchmarks
- **`artifacts/`** - Generated data (indices, ingestion outputs)

**Quick links:**
- 📖 Documentation: [`DOCUMENTS_CHATBOX/docs/README.md`](DOCUMENTS_CHATBOX/docs/README.md)
- 🎓 Learning Guide: [`DOCUMENTS_CHATBOX/docs/PROJECT_MASTERY_GUIDE.md`](DOCUMENTS_CHATBOX/docs/PROJECT_MASTERY_GUIDE.md)
- 🗺️ Documentation Index: [`DOCUMENTS_CHATBOX/docs/DOCUMENTATION_INDEX.md`](DOCUMENTS_CHATBOX/docs/DOCUMENTATION_INDEX.md)
- 🔧 Scripts: [`scripts/README.md`](scripts/README.md)
- 🚀 Getting Started: [`DOCUMENTS_CHATBOX/docs/guides/WEAVIATE_QUICKSTART.md`](DOCUMENTS_CHATBOX/docs/guides/WEAVIATE_QUICKSTART.md)

---

### Phụ lục A — Taxonomy gợi ý (mở)

* `equipment_id`: **`\bKT?\d{5}\b`** → ví dụ **K06101**, **KT06101** (mở rộng regex nếu có hệ đánh số khác).
* `doc_type` (bộ tối thiểu, **mở rộng dần**): `Manual`, `Drawing`, `Instrument`, `Maintenance`, `Data/Spec`, `SpareParts`, `Procedure`, `Report`, `Certificate`.
* Có thể gán **nhiều thiết bị** cho một tài liệu (multi-equipment).
