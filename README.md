
# PVCFC RAG — README - UPDATE AT 00:52AM - 01/10/2025

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

**Giải pháp**: chuẩn hoá ingest → lập chỉ mục **lai** (BM25 + FAISS) → **hỏi-đáp có trích dẫn theo trang** (và, khi phù hợp, **multimodal** để nhìn được trang PDF), kèm **báo cáo** và **metadata** chiết xuất tự động.

---

## 2) Mục tiêu & Phạm vi (V1)

* **Quét đệ quy** toàn bộ **PDF** dưới root `D:\Data_Raw` (ổ rời), **không phụ thuộc cấu trúc thư mục**.
* **OCR khi cần** (PDF scan), ngôn ngữ `vie+eng`.
* **Dedup 100% nội dung**: trùng nội dung chỉ **01 bản đại diện** vào index; near-duplicate **giữ cả hai**.
* **Truy vấn kết hợp**: BM25 (từ khóa) ∪ FAISS (ngữ nghĩa) + rerank.
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
   * **FAISS**: ngữ nghĩa (embedding 768D), **cache SQLite**, batching.

**Online (Serve):**

1. **Query transform** (HyDE/chuẩn hoá ngôn ngữ — tuỳ chọn).
2. **Hybrid retrieval** (BM25 ∪ FAISS) → hợp nhất + **rerank**.
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

## 6) Indexing (BM25 & FAISS)

* **BM25**: engine nhẹ trong repo (đủ cho V1).
* **FAISS**:

  * **Embedding**: Tùy config ENV (ví dụ: `gemini-embedding-001` 768D, `intfloat/multilingual-e5-small` 384D, `text-embedding-3-large` 3072D).
  * **Dimension tự động**: Service auto-detect từ model (không cần chỉ định `EMBED_OUTPUT_DIM` thủ công).
  * **Cache**: SQLite theo `(model_id, output_dim, content_hash)` — giảm API calls, tăng tốc độ.
  * **Song song + batching**: concurrency (≈ 8 threads), batch-size (≈ 256 texts/batch) điều chỉnh theo RAM.
* **Khi mở rộng lớn**: FAISS **IVF-PQ** (nlist/nprobe) cho hàng triệu vectors — **phase sau**.

---

## 7) Truy vấn, Rerank & Trích dẫn theo trang

* **Retrieval k**: Configurable qua request parameter `max_context` (default=8, max=20). Hybrid search lấy nhiều candidates từ BM25 và FAISS, sau đó rerank và chọn top-k.
* **Rerank**: Cross-encoder (`ms-marco-MiniLM-L-6-v2`) cho **EN**; với **VI** dùng fallback **score-based rerank** để tránh lỗi NaN.
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
LLM_MODEL_HEAVY=gemini-2.5-pro
LLM_MODEL_LIGHT=gemini-2.5-flash

# Embedding (FAISS)
EMBEDDING_PROVIDER=gemini  # gemini|openai|local|none
EMBEDDING_MODEL=gemini-embedding-001  # dimension auto-detect từ model
# Batching & concurrency (optional, có default hợp lý)
EMBED_BATCH_SIZE=256  # số texts per internal batch
EMBED_CONCURRENCY=8   # số concurrent requests

# Vision (multimodal generation)
VISION_MODEL=models/gemini-2.5-pro
VISION_MAX_PAGES_TOTAL=10
PDF_RENDER_DPI=200
PDF_IMAGE_FORMAT=jpeg

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

**Build BM25**

```powershell
python tools\build_bm25_index.py `
  --chunks-jsonl "artifacts\\ingestion\\chunks\\chunks.jsonl" `
  --index-dir "artifacts\\index\\bm25"
```

**Build FAISS (cache + batching + concurrency)**

```powershell
python tools\build_faiss_local.py `
  --bm25-dir "artifacts\\index\\bm25" `
  --faiss-dir "artifacts\\index\\faiss"
```

> **Lưu ý:** `--bm25-dir` trỏ đến **BM25 index outputs** (chứa `texts.json`/`documents.json` + `metadata.json`), KHÔNG phải `artifacts\ingestion\bm25`.

**Chạy API**

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

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

### Phụ lục A — Taxonomy gợi ý (mở)

* `equipment_id`: **`\bKT?\d{5}\b`** → ví dụ **K06101**, **KT06101** (mở rộng regex nếu có hệ đánh số khác).
* `doc_type` (bộ tối thiểu, **mở rộng dần**): `Manual`, `Drawing`, `Instrument`, `Maintenance`, `Data/Spec`, `SpareParts`, `Procedure`, `Report`, `Certificate`.
* Có thể gán **nhiều thiết bị** cho một tài liệu (multi-equipment).
