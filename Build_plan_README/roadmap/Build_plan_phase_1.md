# PHASE 1 — INGEST & INDEX (V1)

Tài liệu pha 1 cho PVCFC RAG (V1). Mục tiêu: chuẩn hoá tài liệu PDF (vector/scan), OCR “chỉ khi cần”, dedup theo nội dung, chunking ký tự, sinh `doc_id_map.json`, và xây dựng chỉ mục BM25 + FAISS với embedding duy nhất (gemini-embedding-001). Bảo đảm RAM vận hành ≤ 12 GB.

---

## 1) Mục tiêu & Kết quả mong đợi

- Quét đệ quy `D:\Data_Raw` → xử lý PDF vector/scan, OCR nếu cần.
- Dedup theo `content_hash`, giữ 01 bản đại diện (đưa vào chunks/index), các bản trùng ghi `duplicates`.
- Chunking ký tự `size=1000`, `overlap=200` → ghi `chunks.jsonl` (atomic ghi từng file theo batch).
- Sinh `doc_id_map.json` (atomic) để map `doc_id → pdf_path` nhằm enrich citations sau này.
- Build chỉ mục BM25 + FAISS (embedding duy nhất V1: `gemini-embedding-001`).
- RAM guard: build theo batch & flush; đỉnh bộ nhớ ≤ 12 GB.

---

## 2) Phạm vi & Không phạm vi

- Có (Phase 1):
  - Ingest PDFs (vector/scan) → Markdown + Metadata → Chunking.
  - Dedup (file_hash, content_hash), Quarantine (log lý do), Manifests, `doc_id_map.json`.
  - Xây dựng BM25 + FAISS (batch embedding, cache, flush).
- Không (để Phase 2 trở đi):
  - Retrieval online, Rerank, Vision multimodal, API endpoints, Evaluation/UI.
  - Bbox bắt buộc (V1 không yêu cầu), pre-render toàn bộ pages (render on-demand ở runtime).

---

## 3) Kiến trúc xử lý (pipeline)

`Acquire PDFs → Detect (vector/scan) → Parse (PyMuPDF | OCR khi cần) → Normalize text → Markdown + Metadata → Chunking (1000/200) → Dedup (content_hash) → Manifests + doc_id_map.json → Build BM25 & FAISS`

---

## 4) Đầu vào & Thư mục dữ liệu

- Nguồn: `D:\Data_Raw` (ổ rời, quét đệ quy .pdf). Không phụ thuộc cấu trúc con.
- Khuyến nghị (tuỳ chọn) junction trên Windows để lưu trữ lớn:
  - `artifacts\ingestion   → D:\PVCFC_DATA\ingestion`
  - `artifacts\index\bm25  → D:\PVCFC_DATA\index\bm25`
  - `artifacts\index\faiss → D:\PVCFC_DATA\index\faiss`

---

## 5) OCR “chỉ khi cần”

- Điều kiện bật OCR: thiếu text vector (tổng ký tự trích < ngưỡng; ví dụ < 100 chars cho 1–2 trang đầu).
- Cấu hình: `vie+eng`, áp dụng rotate/deskew cơ bản (nếu có), min confidence hợp lý.
- Ghi log `used_ocr=true` cho tài liệu đã áp dụng OCR.

---

## 6) Trích xuất & Chuẩn hoá văn bản

- Vector PDF: PyMuPDF (blocks/spans), ưu tiên tiêu đề/cấu trúc khi khả thi.
- Scan PDF: OCR → text; xử lý hậu chuẩn hoá: lower, bỏ dấu gạch nối cuối dòng, collapse whitespace.
- Markdown: chuyển text sang Markdown giữ tiêu đề/section nếu có; metadata JSON kèm theo (không bắt buộc bbox V1).

---

## 7) Dedup theo nội dung (content_hash)

- file_hash = **SHA256(bytes)** → nhận diện **trùng file y hệt** (phục vụ manifest & đối chiếu).
- content_hash = **SHA1(normalized_text)**, với chuẩn hoá:
  1) Unicode **NFKC**;
  2) **lowercase**;
  3) Loại bỏ gạch nối cuối dòng (`-\n`, `-\r\n`);
  4) **Collapse whitespace** (kể cả xuống dòng) thành 1 khoảng trắng;
  5) `strip()` khoảng trắng đầu/cuối.
- Đại diện (deterministic): ưu tiên **vector > scan**, **file size lớn hơn**, **mtime mới hơn**, **đường dẫn ngắn hơn**.
- Chỉ **đại diện** vào chunks/index; log group `duplicates` vào báo cáo dedup.

---

## 8) Chunking (ký tự)

- Mặc định: `size=1000`, `overlap=200`. Có thể tham số hoá qua CLI.
- Bảo toàn metadata cốt lõi ở từng chunk: `doc_id`, `page` (1-based), `source_format`, `doc_type?`, `revision?`.
- Ghi `chunks.jsonl` (append theo batch; khoá file khi ghi để tránh xen kẽ dòng).

---

## 9) Metadata & doc_id

- **doc_id**: giữ như **code hiện tại** (ví dụ `DOCID_{base}_{hash}`). Không đổi quy ước trong V1.
- Trường cốt lõi (nếu có): `doc_id`, `page` hoặc `page_start/page_end` (1-based), `source_format (vector|scan)`, `file_name`, `title/author?`, `doc_type?` (nếu classifier có), `revision?`.
- `doc_id_map.json` (atomic): map `doc_id → pdf_path` để enrich `pdf_path` trong citations (không fail nếu thiếu map).

---

## 10) Manifests & Báo cáo

- `manifests/corpus.jsonl`: danh mục doc đã ingest (doc_id, file_path, hash, pages, doc_type, revision, source_format, ingested_at…).
- `manifests/checksums.jsonl`: hash & mtime để phát hiện thay đổi.
- `manifests/dedup_report.json`: nhóm duplicates theo `content_hash` (đại diện + danh sách bản sao) — tạo khi có duplicates.
- `quarantine.jsonl`: log file & `reason_code ∈ {corrupt|password|ocr_failed|read_error}`.

---

## 11) Artifacts & Cây thư mục

```
artifacts/
  ingestion/
    documents/               # JSON processed documents
    markdown/                # Markdown per doc (nếu tạo)
    chunks/                  # chunks.jsonl (append)
    manifests/
      corpus.jsonl
      checksums.jsonl
      dedup_report.json      # khi có duplicates
    doc_id_map.json          # map doc_id → pdf_path (atomic)
  index/
    bm25/                    # BM25 index outputs
    faiss/                   # FAISS index outputs
  cache/
    pdf_pages/               # cache ảnh trang (render on-demand)
```

Ghi chú: **Không pre-render** toàn bộ pages; cache ảnh trang theo nhu cầu runtime.

---

## 12) Build BM25 & FAISS (Embedding duy nhất V1)

- Embedding V1: **`gemini-embedding-001`** (duy nhất), **dùng chung ingest & query** để giữ cùng không gian vector.
- Cho phép override qua ENV/CLI (nhưng default & khuyến nghị là `gemini-embedding-001`).
- FAISS build theo **batch & flush** để giữ RAM ≤ 12 GB; dimension tự động từ model (không hardcode).

---

## 13) RAM Guard (hướng dẫn)

- Embed theo batch (ví dụ 10k–25k chunks/lượt tuỳ RAM); flush sau mỗi batch.
- Dùng psutil (nếu có) để quan sát memory; mục tiêu đỉnh < 6–8 GB khi build; vận hành tổng ≤ 12 GB.
- Nếu gần ngưỡng: giảm kích thước batch, bật GC giữa các batch.

---

## 14) Logging & Counters (Ingest)

- Ingest prints: `total_pdfs`, `processed`, `failed`, `duplicates_collapsed`, `quarantine_count`, `ocr_count`, `total_chunks`, `duration`, `throughput`.
- Mỗi file (log): processed/duplicate/quarantine + reason.
- Khi ghi `doc_id_map.json`, log tổng entries & atomic write.

---

## 15) Lệnh mẫu (PowerShell)

- Ingest:

```powershell
python tools\ingest.py `
  --source-dir "D:\\Data_Raw" `
  --output-dir "artifacts\\ingestion" `
  --enable-ocr `
  --ocr-lang "vie+eng" `
  --parser auto `
  --chunk-size 1000 `
  --chunk-overlap 200
```

- Build BM25:

```powershell
python tools\build_bm25_index.py `
  --chunks-jsonl "artifacts\\ingestion\\chunks\\chunks.jsonl" `
  --index-dir "artifacts\\index\\bm25"
```

- Build FAISS (embedding duy nhất V1):

```powershell
python tools\build_faiss_local.py `
  --bm25-dir "artifacts\\index\\bm25" `
  --faiss-dir "artifacts\\index\\faiss" `
  --embedding_model "gemini-embedding-001"
```

---

## 16) Định nghĩa Hoàn thành (DoD)

- 100% PDF trong `D:\Data_Raw` được xử lý **hoặc** có entry trong `quarantine.jsonl` (có mã lý do).
- Sinh `artifacts/ingestion/chunks/chunks.jsonl`, `doc_id_map.json` (atomic), `manifests/corpus.jsonl`, `manifests/checksums.jsonl`.
- Build xong **BM25** và **FAISS**; RAM build ≤ 12 GB.
- Dedup 100% nội dung hoạt động: chỉ **đại diện** xuất hiện trong chunks/index; duplicates được log rõ.

---

## 17) Rủi ro & Ứng phó

- OCR phụ thuộc OS: hướng dẫn cài Tesseract, fallback; log cảnh báo.
- PDF xấu (xoay, méo, mờ): tập trung text + normalize; chấp nhận Markdown chưa hoàn hảo; lưu JSON phụ trợ khi cần.
- Dung lượng lớn: batch embed + flush; giảm batch; giám sát RAM.
- Bảo mật: ingest chỉ vùng dữ liệu whitelisted; không gửi file ra ngoài; `.env` và logs không chứa secrets.

---

## 18) Phụ lục

### 18.1 Windows Junction (tuỳ chọn)

```powershell
New-Item -ItemType Directory -Force D:\PVCFC_DATA\ingestion | Out-Null
New-Item -ItemType Directory -Force D:\PVCFC_DATA\index\bm25 | Out-Null
New-Item -ItemType Directory -Force D:\PVCFC_DATA\index\faiss | Out-Null
New-Item -ItemType Directory -Force "artifacts\index" | Out-Null
mklink /J artifacts\ingestion   D:\PVCFC_DATA\ingestion
mklink /J artifacts\index\bm25  D:\PVCFC_DATA\index\bm25
mklink /J artifacts\index\faiss D:\PVCFC_DATA\index\faiss
```

### 18.2 Mã lý do quarantine (chuẩn)

- `corrupt` — file hỏng, không mở được
- `password` — file khoá mật khẩu
- `ocr_failed` — OCR thất bại/không trích được text
- `read_error` — lỗi I/O, timeout, hoặc thiếu quyền

### 18.3 Ghi chú tương thích

- V1 **không** yêu cầu bbox bắt buộc.
- **Không** pre-render toàn bộ pages; render on-demand + cache.
- Embedding duy nhất V1: `gemini-embedding-001` (ingest & query cùng không gian vector).
