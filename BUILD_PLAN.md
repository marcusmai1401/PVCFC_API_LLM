# PVCFC RAG (V1) — BUILD_PLAN.md

Tài liệu kế hoạch hợp nhất để triển khai PVCFC RAG phiên bản V1. Mục tiêu: chính xác, trích dẫn tin cậy theo trang (1-based), vận hành gọn nhẹ, sẵn sàng cho đánh giá/triển khai nội bộ.

---

## 1) Mở đầu (Bối cảnh & Mục tiêu V1)

- Ưu tiên độ chính xác hơn chi phí; trả lời theo ngôn ngữ câu hỏi (VI/EN).
- Citations bắt buộc (khi có bằng chứng) ở mức trang 1-based; nếu không đủ bằng chứng, phải nói “không đủ nguồn/bằng chứng”.
- Vision ưu tiên: render ảnh trang on-demand + cache để chọn đúng trang/ngữ cảnh trước khi sinh trả lời/citation. Text-only page-range scanning mặc định OFF (chỉ debug).
- Embedding duy nhất cho V1: gemini-embedding-001, dùng chung cho ingest và query (cùng không gian vector).
- Không bắt buộc bbox ở V1; UI render footnote dựa trên citations (backend chỉ trả citations[] chuẩn).
- RAM guard: xây index batch & flush; lúc query vận hành ≤ 12 GB; Vision lấy tối đa 10 trang/request.

---

## 2) ENV & Defaults

```ini
# LLM routing (nội bộ)
LLM_MODEL_HEAVY=gemini-2.5-pro         # generation
LLM_MODEL_LIGHT=gemini-2.5-flash       # query-transform / HyDE

# Embedding (duy nhất cho V1)
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001

# Retrieval defaults
MAX_CONTEXT=8
TOP_RERANK=20

# Vision & text-range flags
VISION_PAGE_SELECTOR_ENABLED=true
TEXT_RANGE_SCAN_ENABLED=false

# Degrade BM25-only fallback
RETRIEVAL_ALLOW_BM25_ONLY_FALLBACK=true
BM25_K_WHEN_DEGRADE=80
RERANK_TOP_N_WHEN_DEGRADE=50

# Rate limit & cache
RATE_LIMIT_RPM=60
RATE_LIMIT_BURST=20
RETRIEVE_CACHE_TTL_MIN=10
```

Ghi chú:
- Tên ENV giữ tương thích với code hiện tại; các biến mới là bổ sung (backward-compatible).
- Cho phép override embedding qua ENV/CLI, nhưng default và khuyến nghị là gemini-embedding-001.

---

## 3) PHASE 0 — Nền tảng & Khởi tạo (Foundation)

- Mục tiêu
  - Skeleton FastAPI, .env (pydantic-settings), logging (Loguru), health check (/healthz), Makefile, Docker skeleton, test tối thiểu.
  - Bất kỳ máy mới nào có thể: make dev → make run → /healthz trả 200.

- Phạm vi
  - Có: cấu trúc dự án, config, logging, middleware tối thiểu, README Quickstart, Dockerfile skeleton.
  - Không: ingest/index, retrieval, UI, evaluation.

- Hạng mục chính
  - Cấu trúc app (app/main.py, core/config.py, core/logging.py, api/routers/health.py).
  - .env.example; Settings gồm APP_ENV, API_PORT, LOG_LEVEL, LLM_MODEL_HEAVY/LLM_MODEL_LIGHT, EMBEDDING_*.
  - Makefile: dev, run, test, lint, smoke.
  - Dockerfile python:3.11-slim, non-root, expose 8000.

- Input/Output
  - Input: repo + Python 3.11.
  - Output: /healthz trả 200; Docker build/run OK; Quickstart chạy được.

- DoD
  - make dev → make run → /healthz 200 (status/app_env/version/commit).
  - Test tối thiểu pass; Docker build/run OK.

- Rủi ro
  - Sai khác OS: cung cấp hướng dẫn riêng cho Windows PowerShell; Docker skeleton đảm bảo đồng nhất.

---

## 4) PHASE 1 — Ingest & Index (V1)

- Input: `D:\Data_Raw` (quét đệ quy tất cả PDF).

- OCR “chỉ khi cần”
  - Nếu không có text vector (ít/không text trích được), bật OCR `vie+eng`.
  - DPI/OCR nâng cao chỉ khi cần; log rõ used_ocr.

- Dedup theo content_hash (giữ 01 đại diện)
  - file_hash = SHA256(bytes file) → phát hiện trùng file y hệt.
  - content_hash = SHA1(text chuẩn hoá): Unicode NFKC → lowercase → collapse whitespace → bỏ gạch nối cuối dòng (`-\n`, `-\r\n`) → strip.
  - Tiêu chí chọn đại diện (deterministic): vector > scan → file size lớn hơn → mtime mới hơn → đường dẫn ngắn hơn.
  - Chỉ đại diện được chunk & index; các bản trùng ghi vào duplicates (report).

- Quarantine (log, không di chuyển file)
  - Ghi `{output_dir}/quarantine.jsonl`, mỗi dòng JSON: file, reason_code (corrupt|password|ocr_failed|read_error), detail, run_id, ts.
  - Build index bỏ qua các file quarantine.

- Chunking (ký tự)
  - size=1000, overlap=200; có thể tham số hoá.

- Embedding duy nhất (V1)
  - EMBEDDING_PROVIDER=gemini; EMBEDDING_MODEL=gemini-embedding-001.
  - Dùng cùng một model cho ingest và query để giữ cùng không gian vector (tránh sai lớp vector).

- doc_id & doc_id_map
  - Giữ doc_id như code (ví dụ `DOCID_{base}_{hash}`).
  - Page numbering 1-based.
  - Xuất `doc_id_map.json` (atomic) để có thể enrich `pdf_path` trong replies.

- On-demand page render + cache
  - Không pre-render toàn bộ.
  - Render trang on-demand; cache (ví dụ `artifacts\cache\pdf_pages`) để tăng tốc preview/vision.

- Artifacts
  - `artifacts/ingestion/(documents|markdown|chunks|manifests|doc_id_map.json)`
  - `artifacts/index/(bm25|faiss)`

- RAM guard (build)
  - Batch embed & flush, không giữ toàn bộ embeddings trong RAM.
  - Giới hạn đỉnh sử dụng bộ nhớ để vận hành ≤ 12 GB.

- Lệnh mẫu (PowerShell)
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
  - Build FAISS:
    ```powershell
    python tools\build_faiss_local.py `
      --bm25-dir "artifacts\\index\\bm25" `
      --faiss-dir "artifacts\\index\\faiss" `
      --embedding_model "gemini-embedding-001"
    ```

- DoD
  - 100% PDF xử lý hoặc có entry trong quarantine.jsonl.
  - Sinh `chunks.jsonl` và `doc_id_map.json` (atomic); BM25 + FAISS sẵn sàng.
  - RAM build trong ngưỡng; logs ghi counters (ocr_count, duplicates_collapsed, quarantine_count).

---

## 5) PHASE 2 — Retrieval & API (Hybrid + Rerank + Vision + Citations)

- Luồng xử lý
  - Query Transform (Gemini 2.5 Flash): normalize, HyDE (tùy chọn), paraphrase.
  - Hybrid Retrieval (BM25 + FAISS) → hợp nhất → Rerank (Cross-Encoder cho EN; fallback score/hybrid cho VI).
  - Generation (Gemini 2.5 Pro): sinh câu trả lời dựa trên context + Vision khi có trang phù hợp.
  - Citations (bắt buộc khi có bằng chứng): doc_id + page (1-based); UI render footnote.

- Vision page selector (mặc định ON)
  - Render ảnh trang on-demand + cache.
  - Chọn trang:
    - Nếu có cả `page_start` và `page_end` (non-None) → lấy full range; swap nếu start > end.
    - Nếu chỉ có `page` → cửa sổ ±2 (start=max(1, page-2); end=page+2).
    - Clamp theo tổng số trang; tối đa 10 trang; 1-based; dedup theo (pdf_path, page).
  - Text-only page-range scanning: OFF mặc định (chỉ bật khi flag debug).

- Degrade BM25-only (không rebuild) khi lỗi embedding/mạng
  - Cho phép fallback: `RETRIEVAL_ALLOW_BM25_ONLY_FALLBACK=true`.
  - Khi degrade:
    - meta.degrade_mode=true
    - meta.degrade_reason: (network_error|embedding_timeout|quota|…)
    - Tăng `BM25_K_WHEN_DEGRADE=80`, `RERANK_TOP_N_WHEN_DEGRADE=50`.

- API
  - POST /ask: Q&A chi tiết; auto-language; citations bắt buộc khi có bằng chứng; nếu không đủ nguồn → nói rõ “không đủ bằng chứng”.
  - POST /locate: chỉ dùng khi người dùng thật sự hỏi vị trí/trang.
  - POST /report: xuất markdown; citations ở cuối.

- Telemetry/meta bắt buộc trả về
  - `model_generation`, `model_query_transform`, `embed_model`
  - `degrade_mode` (bool), `degrade_reason` (string?)
  - `bm25_k_current`, `top_rerank_current`
  - `vision_page_selector_enabled`, `text_range_scan_enabled`
  - `timing_by_stage` (transform/retrieve/rerank/generate), `cache_hit` (retrieve/rerank)

- Rate-limit & cache
  - Token bucket: 60 rpm (burst 20), per-IP/tenant; header rate-limit phù hợp.
  - Cache LRU: TTL 10 phút cho retrieve/rerank (không cache answer nhạy cảm).

- DoD
  - /ask luôn có citations 1-based (hoặc từ chối có lý); Vision hoạt động: pages_used ≤ 10; degrade hoạt động khi lỗi embedding; RAM vận hành trong ngưỡng; meta/telemetry đầy đủ trường.

---

## 6) PHASE 3 — Evaluation, UI Demo & Observability (V1)

- Golden set
  - ≥ 120 QA (có negative cases), bao phủ datasheet/P&ID/SOP/OM, nhiều loại câu hỏi (lookup, locate, quy trình, phủ định).
  - Lưu JSONL + version/changelog.

- Mục tiêu định lượng (gợi ý)
  - Retrieval: Recall@10 ≥ 80% tổng thể.
  - Answer: Faithfulness ≥ 0.8; Citation precision ≥ 95%, recall ≥ 90%.
  - Latency p95 < 8s (không tính hàng đợi provider).

- Streamlit UI (demo SME)
  - Hiển thị answer markdown + danh sách citations; UI render footnote từ citations.
  - Preview ảnh trang từ cache/render (không yêu cầu bbox).
  - Tab “Developer/Debug” cho k/HyDE/flags; export session logs.

- Logs & metrics
  - logs/requests.jsonl, logs/ui_sessions.jsonl; Prometheus/OTel; biểu đồ latency/cache-hit/lỗi.

- DoD
  - Batch eval xuất `artifacts/eval/phase3_report.md` + CSV/JSON; UI demo ok; telemetry hiển thị flags (vision/text-range/degrade) và breakdown thời gian.

---

## 7) PHASE 4 — Tối ưu, Bảo mật & Chuyển giao

- Ablation/A-B
  - Tối ưu tham số: k (MAX_CONTEXT), TOP_RERANK, HyDE, prompts; tiết kiệm tokens (nén context, giảm MAX_CONTEXT khi rerank score cao).

- Security
  - Secrets manager; SBOM (cyclonedx); image scan (Trivy); pip-audit; secret scan (gitleaks/detect-secrets) ở pre-commit/CI.
  - Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy; rate-limit; input validation; log retention 90 ngày; non-root.

- CI/CD & Handover
  - Lint/test → build → scan → push → deploy (compose/helm); release notes/changelog.
  - Backup/restore index (artifacts/index + manifests).
  - Runbook vận hành; tài liệu đào tạo.

- DoD
  - Tối ưu đạt mục tiêu latency/cost, không giảm chất lượng; compose/CI/CD chạy ổn; dashboards/alerts hoạt động; runbook/training hoàn tất.

---

## 8) Acceptance checklist tổng hợp

- [ ] Ingest & Index
  - [ ] Quét `D:\Data_Raw` đệ quy; OCR “chỉ khi cần”.
  - [ ] Dedup theo content_hash; chỉ đại diện vào chunks/index; duplicates được log.
  - [ ] Sinh `chunks.jsonl`, `doc_id_map.json` (atomic); quarantine.jsonl đầy đủ lý do.
  - [ ] Embedding duy nhất: gemini-embedding-001 (ingest & query).
  - [ ] RAM build ≤ 12 GB (batch & flush).

- [ ] Retrieval & API
  - [ ] Hybrid BM25+FAISS → Rerank (CE EN / score VI).
  - [ ] Vision page selector ON; text-range OFF (trừ debug).
  - [ ] Vision pages_used ≤ 10; 1-based; dedup; clamp theo tổng trang.
  - [ ] /ask trả lời đúng ngôn ngữ; citations 1-based (hoặc từ chối có lý).
  - [ ] Degrade BM25-only khi lỗi embedding: meta.degrade_mode=true + reason; `BM25_K_WHEN_DEGRADE`, `RERANK_TOP_N_WHEN_DEGRADE` áp dụng.
  - [ ] Meta/telemetry đầy đủ: model_generation/model_query_transform/embed_model; flags; bm25_k_current/top_rerank_current; timing_by_stage; cache_hit.
  - [ ] Rate-limit 60 rpm (burst 20); cache TTL 10 phút cho retrieve/rerank.

- [ ] Evaluation & UI
  - [ ] Golden set ≥ 120 QA (có negative).
  - [ ] Recall@10 ≥ 80%; Faithfulness ≥ 0.8; Citation precision ≥ 95%, recall ≥ 90%.
  - [ ] UI demo: answer + citations; UI render footnote từ citations; preview ảnh trang.
  - [ ] Latency p95 < 8s (không tính hàng đợi provider).

- [ ] Security & Handover
  - [ ] SBOM + Trivy + pip-audit pass; secrets masked; rate-limit & headers.
  - [ ] CI/CD chuẩn; backup/restore index; runbook & training hoàn tất.

---

## 9) Phụ lục

### 9.1 Windows Junction (mklink /J)

```powershell
New-Item -ItemType Directory -Force D:\PVCFC_DATA\ingestion | Out-Null
New-Item -ItemType Directory -Force D:\PVCFC_DATA\index\bm25 | Out-Null
New-Item -ItemType Directory -Force D:\PVCFC_DATA\index\faiss | Out-Null
New-Item -ItemType Directory -Force "artifacts\index" | Out-Null

mklink /J artifacts\ingestion   D:\PVCFC_DATA\ingestion
mklink /J artifacts\index\bm25  D:\PVCFC_DATA\index\bm25
mklink /J artifacts\index\faiss D:\PVCFC_DATA\index\faiss
```

### 9.2 Mã lý do quarantine

- `corrupt` — file hỏng, không mở được
- `password` — file khóa mật khẩu
- `ocr_failed` — OCR thất bại/không trích được text
- `read_error` — lỗi I/O, timeout, hoặc thiếu quyền

### 9.3 Ví dụ lệnh PowerShell (tham khảo)

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

Kết thúc tài liệu.
