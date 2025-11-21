
# PVCFC RAG — README - LAST UPDATE: 21/11/2025 (v1.7.0)

Hệ thống **RAG (Retrieval-Augmented Generation)** phục vụ **tra cứu, trích xuất, và hỏi-đáp kỹ thuật** trên tập tài liệu của PVCFC, với trọng tâm là **độ tin cậy, trích nguồn đầy đủ, và thao tác nhanh** trên dữ liệu nội bộ.

> **🚀 Version 1.7.0 Highlights** (Nov 21, 2025):
> - **Gemini 3.0 Pro Preview** (most powerful model for complex diagrams)
> - **100 candidates retrieval** (2x recall improvement)
> - **20 chunks context** (2.5x LLM visibility)
> - **300s timeout** (supports long Vision processing)
> - **Enhanced prompts** (multimodal reasoning + cross-verification)

* **Use-cases chính**:

  * **Tìm & trích xuất**: nhanh chóng tìm đúng *tài liệu và **trang*** nhắc tới nội dung câu hỏi.
  * **Hỏi-đáp có trích dẫn**: trả lời ngắn gọn, **đính kèm nguồn (doc_id + page)** để kiểm chứng.
  * **💬 Hội thoại đa lượt (NEW)**: chat liên tục với ghi nhớ ngữ cảnh, tự động suy luận "nó", "thiết bị đó" từ câu hỏi trước.
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

## 3) Kiến trúc tổng thể - DUAL PIPELINE

> **⚠️ QUAN TRỌNG**: Hệ thống có **2 PIPELINE SONG SONG** tự động phân loại theo loại tài liệu:

```
                    PDF INPUT
                        │
                        ↓
                ┌───────────────┌
                │ CAD-like Gate │ ← BINARY (v1.5.0)
                │ Threshold=0.55│
                └───────┬───────┐
                        │
            ┌───────────┴────────────┐
            │                        │
      score ≥ 0.55              score < 0.55
            │                        │
            ↓                        ↓
    ╔═══════════════╗        ╔═══════════════╗
    ║ CAD-LIKE      ║        ║ NON-CAD-LIKE  ║
    ║ PIPELINE      ║        ║ PIPELINE      ║
    ║ (Extended)    ║        ║ (Standard)    ║
    ╚═══════════════╝        ╚═══════════════╝
         │                          │
         ├─ Layout + Tags               ├─ Text + Chunks
         ├─ Spatial (ALL 100%)✅       ├─ OCR (no ESRGAN)
         ├─ Bbox + Crops      ✅       └─ 1 Index
         ├─ 2 Indexes         ✅
         ├─ OCR + Real-ESRGAN ✅
         └─ Parallel Search   ✅
```

### 3.1 **Non-CAD-like Pipeline** (Standard - Mặc định)

**Áp dụng cho:** Manuals, Datasheets, Specifications, Operating Procedures

**Offline (Build):**

1. **Ingest**: đọc PDF (vector/scan), **OCR LUÔN ENABLED** (< 40 chars/page, không có Real-ESRGAN) → chuẩn hoá văn bản → **chunk** + metadata.
2. **Dedup**: `content_hash` để gộp **trùng nội dung** (đại diện: *vector > scan > size > mtime > path ngắn*).
3. **Index**:
   * **BM25**: chỉ mục từ khóa (nhẹ, dễ bảo trì).
   * **Weaviate**: vector database (embedding 768D), production-grade với gRPC.

**Online (Serve):**

1. **Query transform** (HyDE/chuẩn hoá ngôn ngữ — tuỳ chọn).
2. **Hybrid retrieval** (BM25 ∪ Weaviate) → hợp nhất + **BGE rerank**.
3. **Generation**: Text-only hoặc Multimodal (Vision) khi cần.
4. **Trả về**: **answer**, **citations (doc_id + page)**, **metadata**.

### 3.2 **CAD-like Pipeline** (Extended - Khi enable)

**Áp dụng cho:** P&ID, PFD, Instrument Drawings, ISO Diagrams

> **Enable**: Set `ENABLE_PID_TAGS=true` trong `.env`

**Offline (Build) - MỞ RỘNG:**

1. **CAD-like Gate**: **Binary classification** (CAD-like vs non-CAD-like, threshold=0.55).
2. **Page Layout Extraction**: Trích xuất **spatial layout** (bbox, font, rotation, vector drawings).
3. **Tag Extraction**: Trích xuất instrument tags (PREFIX-anchored triplet: UNIT-PREFIX-SUFFIX-VARIANT).
4. **Spatial Component Extraction**: Trích từ **ALL 100% pages** (không chỉ taggy pages), smart layout reuse.
5. **Crop Generation**: Tạo PNG crops của tag bounding boxes.
6. **Dual Indexing**:
   * **Index 1**: `rag_chunks` (BM25 + Weaviate) ← *Giống Non-CAD-like*
   * **Index 2**: `pvcfc_pid_spatial_components` (OpenSearch) ← *⭐ ALL 100% pages coverage*
7. **OCR**: Per-page threshold (< 1700 chars) + **Real-ESRGAN 2x enhancement**

**Online (Serve) - KHÁC HOÀN TOÀN:**

1. **Query Enhancement**: Phát hiện tags (04 PSAL 2207), parse components, tạo variants.
2. **Context Validation**: Multi-layer false positive prevention.
3. **Parallel Retrieval** (2 branches):
   * **Branch A**: Level 2 Spatial Search (`pvcfc_pid_spatial_components`) → Component-based clustering tìm tags với bbox
   * **Branch B**: Search `rag_chunks` index → standard chunks
4. **RRF Fusion**: Kết hợp 2 branches với adaptive weights.
5. **Tag Reranking**: Boost exact tag matches (×10.0), fuzzy matches (×2.0-3.0).
6. **Generation**: Có thể sử dụng **tag crops** cho vision citations.
7. **Trả về**: **answer** + **citations** (có `bbox` + `crop_path` nếu từ tags).
8. **P&ID Tag Location Queries (NEW)**: với `query_type="pid"` và câu hỏi dạng tag ngắn (vd: `"04 ZSH 4326/A"`), router `/ask` có thể nhận diện **truy vấn vị trí tag** và:
   * Bỏ qua LLM sinh tự do, thay vào đó dùng `PIDTagHandler` để trả về câu trả lời dạng: `"Tag 04 ZSH 4326 xuất hiện ở [Doc 1, p.89]"`.
   * Chạy một lượt truy vấn P&ID chuyên biệt (tags retriever) với `top_k` lớn hơn để **luôn bao phủ trang thực sự chứa tag** (kể cả khi BGE rerank thông thường đang ưu tiên các trang text lân cận như 85/86/102).
   * Ưu tiên các hit `source="tags"` (Level 2 spatial search); nếu spatial không tìm thấy, fallback sang **text-only tag detection** dựa trên text đã trích từ PyMuPDF từng trang P&ID (TextTagDetector Level 1, dùng full-window patterns để bắt `unit/prefix/suffix` ngay cả khi bị tách rời trong text).
   * Kết quả trả về luôn kèm citations (doc_id + page, và bbox nếu có) để UI highlight đúng trang P&ID chứa tag.

### 3.3 So sánh nhanh

| Aspect | Technical Doc | P&ID |
|--------|--------------|------|
| **Auto-detect** | score < 0.55 | score ≥ 0.55 (CAD-like Gate) |
| **Ingestion** | Text + Chunks | Text + Chunks + **Layout + Tags + Crops** |
| **Số indexes** | 1 (`rag_chunks`) | 2 (`rag_chunks` + `pvcfc_pid_spatial_components`) |
| **Retrieval** | 1 branch (chunks) | 2 branches parallel (tags + chunks) |
| **Bbox tracking** | ❌ No | ✅ **Yes** (stored in tags) |
| **Crops** | ❌ No | ✅ **Yes** (PNG images) |
| **Query routing** | Equipment boosting | Tag parsing + validation |

> **Lưu ý**: CAD-like documents **VẪN CÓ** standard chunks index → cho phép fallback sang semantic search nếu spatial search không tìm thấy kết quả.

---

## 4) Dữ liệu, OCR, Dedup & Quarantine

* **Root dữ liệu**: `D:\Data_Raw` (cố định).
* **Artifacts storage**: `D:\PVCFC_Artifacts` (production data, indexes, cache)
  * Ingestion: `D:\PVCFC_Artifacts\ingestion_production`
  * Indexes: `D:\PVCFC_Artifacts\index_production`
  * Cache: `D:\PVCFC_Artifacts\cache`
* **OCR LUÔN ENABLED**: Google Cloud Vision API. Per-page thresholds: CAD-like < 1700 chars (+ Real-ESRGAN 2x), non-CAD-like < 40 chars (không ESRGAN). Hỗ trợ `vie+eng`; Adaptive DPI (144-216).
* **Dedup**:

  * `file_hash = SHA256(file_bytes)` → trùng **file y hệt**.
  * `content_hash = SHA1(normalized_text)` → trùng **nội dung**; **chỉ đại diện** vào index.
* **Quarantine (log, không di chuyển file)**: `{ARTIFACTS_DIR}/ingestion_production/quarantine.jsonl` ghi `corrupt|password|ocr_failed|read_error`.
* **doc_id_map.json**: `{ARTIFACTS_DIR}/ingestion_production/doc_id_map.json` ánh xạ `doc_id → pdf_path` để **enrich citation** và **render trang**.

---

## 5) Chunking & Metadata

* **Chunking Strategy (Phase 3)**: Parent-Child Hierarchical Chunking
  * **Parent Chunks**: Large semantic blocks for LLM context
    * Size: `parent_chunk_size=1800` chars
    * Overlap: `parent_overlap=200` chars
    * Purpose: Complete semantic context for generation
  * **Child Chunks**: Small dense blocks for precise retrieval
    * Size: `child_chunk_size=400` chars
    * Overlap: `child_overlap=50` chars
    * Purpose: Precise keyword/semantic matching
  * **How it works**:
    * Retrieval searches child chunks (high precision)
    * Generation receives parent text (complete context)
    * Parent text stored directly in child metadata (no joins)
  * **Implementation**: `ParentChildChunker` class in `app/ingestion/text_chunker.py`
* **Metadata tối thiểu**: `doc_id`, `page / page_start / page_end`, `source_format (vector|scan)`.
* **Phase 3 Metadata**: `parent_text`, `parent_id`, `chunk_type`, `is_parent`, `parent_index`, `parent_char_count`
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
  * **Status**: Currently **ENABLED** in production (`ENABLE_BGE_RERANK=true`)
  * Multi-level support: chunk, document, page
  * Aggregation methods: max, mean, top3_mean
  * Performance: Adds ~100-500ms latency, significantly improves ranking accuracy
  * First query: ~3-5s (model loading), subsequent queries: ~0.5s rerank time

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

* **Retrieval k**: Configurable qua request parameter `max_context` (default=**20**, max=30). Hybrid search lấy nhiều candidates từ BM25 và Weaviate, sau đó rerank và chọn top-k.

* **Retrieval Optimization (v1.7.0)**:
  * **Weaviate limit**: **100 candidates** (increased from 50)
  * **OpenSearch limit**: **100 candidates** (increased from 50)
  * **Total candidates pool**: 200 (from dual sources)

* **BGE Reranking** (BAAI/bge-reranker-base):
  * **Status**: Currently **ENABLED** (`ENABLE_BGE_RERANK=true` in production .env)
  * **Model**: BAAI/bge-reranker-base (auto-downloaded on first query)
  * **Cấu hình (v1.7.0)**:
    - `BGE_RERANK_CANDIDATE_LIMIT=100`: Số candidates trước khi rerank (increased)
    - `BGE_RERANK_TOP_K=20`: Số kết quả cuối cùng (increased)
    - `MAX_CONTEXT=20`: Context chunks gửi tới LLM (2.5x increase)
    - `TOP_RERANK=30`: Safety buffer ≥ MAX_CONTEXT
    - `BGE_RERANK_LEVEL=chunk`: Rerank level (chunk/doc/page)
    - `BGE_RERANK_AGGREGATION=max`: Phương pháp tổng hợp (max/mean/top3_mean)
  * **Performance**: First query ~45-60s (model loading), subsequent ~2-5s total
  * **Accuracy**: Top rerank scores 0.90-0.96 for highly relevant results
  * **Fallback**: Nếu rerank thất bại, sử dụng score-based ranking
  * **Expected Impact**: +100% recall on diagram-heavy documents

* **Legacy Reranking** (khi BGE tắt):
  * Cross-encoder (`ms-marco-MiniLM-L-6-v2`) cho **EN**
  * Score-based rerank cho **VI** (tránh NaN)

* **Citations**: trả về tối thiểu `doc_id + page (1-based)`. Có `pdf_path` nếu map được từ `doc_id_map.json`.
* **Tìm đúng trang**: metadata giữ `page / page_start / page_end` từ ingest → pipeline trả ra trang **được tham chiếu** (không cần bbox ở V1).

---

## 8) Generation (LLM tiers & Multimodal Vision)

* **Heavy (LLM)**: `gemini-3-pro-preview` (Gemini 3.0 Pro Preview - **most powerful**, multimodal).
* **Light (LLM)**: `gemini-2.5-flash` (fast responses, 65K output tokens).
* **Vision Model**: `gemini-3-pro-preview` (same as Heavy, superior visual understanding).
* **Configuration** (v1.7.0):
  * Max output tokens: **8192** (4x increase from 2048)
  * Vision Always-On: **true** (bypass smart gating)
  * Context: **20 chunks** (2.5x increase from 8)
  * Vision pages: **30 max** (up from 24)
* **Multimodal Vision (khi phù hợp)**:

  * **Điều kiện**: có documents liên quan và **map được `pdf_path`** (từ `doc_id_map.json`).
  * **Chọn trang**:
    - Nếu có cả `page_start` và `page_end` (cả 2 non-None) → lấy **full range**; swap nếu start > end.
    - Nếu chỉ có `page` → **cửa sổ ±2** (start = max(1, page-2); end = page+2).
    - Clamp theo `total_pages` nếu biết được từ PDF.
    - **Tối đa 30 trang** (increased from 10), *1-based*, **dedup** theo `(pdf_path, page)`.
  * **Render nội bộ**: JPEG @ **DPI=200**; trang lỗi → **bỏ qua** và ghi `pages_failed`.
  * **Mục tiêu**: tăng **độ chính xác** nhờ bối cảnh trực quan (layout/bảng/đơn vị), **không** là pipeline verify rời.
  * **Timeout**: Streamlit client **300 seconds** (5 minutes) - supports full Vision processing.

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

# Providers & LLM (v1.7.0 - Gemini 3.0 Pro Preview)
LLM_PROVIDER=gemini  # openai|gemini|none
LLM_TIER=light
LLM_LIGHT_PROVIDER=gemini
LLM_MODEL_HEAVY=models/gemini-3-pro-preview  # Gemini 3.0 Pro Preview (bleeding edge)
LLM_MODEL_LIGHT=models/gemini-2.5-flash      # Fast responses, 65K output
LLM_MAX_OUTPUT_TOKENS=8192  # 4x increase from 2048

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
WEAVIATE_RETRIEVAL_LIMIT=100  # v1.7.0: Increased from 50 (2x recall)

# OpenSearch retrieval limit (v1.7.0)
OPENSEARCH_RETRIEVAL_LIMIT=100  # Increased from 50

# Context & Reranking (v1.7.0 - Major Expansion)
MAX_CONTEXT=20  # Increased from 8 (2.5x LLM visibility)
TOP_RERANK=30   # Safety buffer ≥ MAX_CONTEXT

# BGE Reranking (Phase 3 - v1.7.0 Enhanced)
# Currently ENABLED in production for better semantic ranking
ENABLE_BGE_RERANK=true  # Enable BGE CrossEncoder reranking (BAAI/bge-reranker-base)
BGE_RERANK_CANDIDATE_LIMIT=100  # v1.7.0: Increased from 50
BGE_RERANK_TOP_K=20             # v1.7.0: Increased from 10
BGE_RERANK_LEVEL=chunk          # chunk|doc|page
BGE_RERANK_AGGREGATION=max      # max|mean|top3_mean

# Vision Configuration (Phase 2 - v1.7.0 Enhanced)
VISION_ALWAYS_ON=true  # Always use vision (bypass smart gating)
VISION_MODEL=models/gemini-3-pro-preview  # Same as heavy model
VISION_MAX_PAGES_TOTAL=30  # v1.7.0: Increased from 24
VISION_PAGE_SELECTOR_ENABLED=true
TEXT_RANGE_SCAN_ENABLED=false

# Streamlit Client Timeout (v1.7.0)
# Frontend timeout để support Vision AI xử lý 20-30 pages
STREAMLIT_TIMEOUT=300  # 5 minutes (increased from 60-180s)

# P&ID Tags Extraction (Dual Pipeline - Optional)
# Note: Currently ENABLED in production (.env has ENABLE_PID_TAGS=true)
# Set to false to disable P&ID auto-detect & tag extraction
ENABLE_PID_TAGS=true   # Enable P&ID pipeline (auto-detect CAD-like documents)
GATE_MODE=auto         # auto|always|never
GATE_THRESHOLD=0.55    # CAD-like score threshold (adjusted from 0.60)
GRAY_ZONE_LOW=0.45     # Gray zone lower bound
LAZY_CROP_GENERATION=true  # true: generate crops on-demand, false: at ingestion

# Artifacts directory root (production): tags, layouts, crops, telemetry, helper indexes
# On this machine: D:\PVCFC_Artifacts (configured via .env)
# Ingestion output (chunks, processed): {ARTIFACTS_DIR}\ingestion_production\
ARTIFACTS_DIR=D:\PVCFC_Artifacts

# P&ID Spatial Components (Level 2)
SPATIAL_COMPONENTS_INDEX_NAME=pvcfc_pid_spatial_components  # OpenSearch spatial components index for Level 2 search

# API keys
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here  # nếu dùng OpenAI
```

**Cài đặt (Windows PowerShell)**

```powershell
# Tạo môi trường ảo (single environment - PaddleOCR removed Nov 11)
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Note: Protobuf 5.29.5 compatible with all services (Weaviate, Google Vision, gRPC)

# Cấu hình Google Cloud Vision API
# Đặt biến môi trường GOOGLE_APPLICATION_CREDENTIALS trỏ đến service account key
$env:GOOGLE_APPLICATION_CREDENTIALS = "path\to\your\service-account-key.json"
```

**Ingest**

```powershell
# .venv đang active
# Khuyến nghị: dùng cùng ARTIFACTS_DIR với production pipeline
python tools\\ingest.py `
  --source-dir "D:\\Data_Raw" `
  --output-dir "D:\\PVCFC_Artifacts\\ingestion_production" `
  --enable-ocr `
  --workers 2 `
  --enable-pid-tags

# Output:
# - chunks.jsonl (5,000+)
# - entities/tags.jsonl (200+) - Geometric Assembly tags
# - page_layout/*.json - Spatial layout data
# - Spatial components extracted và sẵn sàng cho indexing
```

**Build Production Indices**

```powershell
# .venv đang active

# 1. Create OpenSearch indexes
python scripts\\opensearch\\create_rag_chunks_index.py --delete-if-exists
python scripts\\opensearch\\create_spatial_components_index.py --delete-if-exists

# 2. Index chunks to OpenSearch + Weaviate (35-40 phút)
python scripts\\utilities\\index_production_chunks.py

# 3. Index P&ID spatial components (Level 2)
# Components được tự động extract và index trong ingestion, nhưng có thể re-index:
python tools\\ingest.py `
  --source-dir "D:\\Data_Raw" `
  --output-dir "D:\\PVCFC_Artifacts\\ingestion_production" `
  --enable-pid-tags `
  --skip-chunking  # Chỉ extract components (nếu cần)
```

**Kết quả:**
- OpenSearch rag_chunks: ~10,000 documents
- Weaviate Chunk: ~10,000 objects
- OpenSearch pvcfc_pid_spatial_components: ~thousands of components (unit/prefix/suffix) for Level 2 spatial search

**Chạy API** (Cùng .venv)

```powershell
# .venv đang active
.\launchers\start_api.ps1
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

* **POST `/ask`** (note: endpoint path is `/ask`, not `/api/ask`)
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

* **POST `/report`**
  Sinh báo cáo tạm (Markdown/Docx đơn giản) từ **answer + citations**.

* **POST `/locate`**
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
- **`docs/guides/`** - Operational guides and runbooks for this repo (Quick Start, Pre-Launch, Design UI, Vision strategy)
- **`DOCUMENTS_CHATBOX/docs/`** - Long-form project documentation (architecture, broader project guides)
- **`scripts/`** - All utility scripts organized by purpose (diagnostics, utilities, weaviate)
- **`app/`** - Main application code (FastAPI + RAG pipeline)
- **`tools/`** - Build tools and benchmarks
- **`artifacts/`** - Generated data (indices, ingestion outputs)

**Quick links:**
- 📖 Documentation index (long-form): [`DOCUMENTS_CHATBOX/docs/README.md`](DOCUMENTS_CHATBOX/docs/README.md)
- 📚 Operational guides index: [`docs/guides/README.md`](docs/guides/README.md)
- 🔧 Scripts: [`scripts/README.md`](scripts/README.md)
- 🚀 Getting Started: [`docs/guides/QUICK_START.md`](docs/guides/QUICK_START.md)
- ✅ Pre-launch checklist: [`docs/guides/PRE_LAUNCH_CHECKLIST.md`](docs/guides/PRE_LAUNCH_CHECKLIST.md)
- 💬 **NEW** Multi-turn Chat Guide: [`docs/MULTI_TURN_CHAT_GUIDE.md`](docs/MULTI_TURN_CHAT_GUIDE.md)

---

### Phụ lục A — Taxonomy gợi ý (mở)

* `equipment_id`: **`\bKT?\d{5}\b`** → ví dụ **K06101**, **KT06101** (mở rộng regex nếu có hệ đánh số khác).
* `doc_type` (bộ tối thiểu, **mở rộng dần**): `Manual`, `Drawing`, `Instrument`, `Maintenance`, `Data/Spec`, `SpareParts`, `Procedure`, `Report`, `Certificate`.
* Có thể gán **nhiều thiết bị** cho một tài liệu (multi-equipment).
