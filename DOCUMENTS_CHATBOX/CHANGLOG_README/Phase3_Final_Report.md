# PVCFC RAG API — Báo cáo Kết thúc Phase 3 (Nhật ký thay đổi)

## I. Tóm tắt điều hành
- Mục tiêu: Bàn giao Đánh giá + UI Demo + cải tiến Observability trên nền Phase 1/2, bổ sung OCR cho PDF scan, hợp nhất trải nghiệm cho lập trình viên.
- Trạng thái: HOÀN THÀNH (tập hợp tính năng Phase 3 đã triển khai và xác thực cục bộ).
- Điểm nhấn:
  - Streamlit UI kết nối trực tiếp với chỉ mục thật + chế độ Gemini Live (câu trả lời bám tài liệu).
  - Tích hợp OCR fallback; build lại chỉ mục BM25 có OCR (bao phủ PDF scan/mixed).
  - Batch evaluation (chỉ retrieval) chạy end‑to‑end; đã sửa lỗi context manager của evaluator.
  - Dùng đường dẫn chỉ mục tuyệt đối; HyDE ràng buộc (mặc định OFF trong UI); tài liệu được hợp nhất.

## II. Phạm vi & Sản phẩm bàn giao
### Trong phạm vi (đã triển khai)
- Real‑data UI demo (Streamlit) integrated with `HybridRetriever` and Gemini.
- OCR fallback in ingestion; CLI flag `--enable-ocr` in BM25 builder; cached OCR.
- Retrieval batch evaluation runner with CSV/JSON reports.
- Consolidated documentation: `docs/Phase3_Integration_Guide.md`.
- Observability continuity from Phase 2: metrics/traces/index stats.

### Ngoài phạm vi
- Production authentication/authorization and quotas (Phase 4).
- Advanced A/B framework and full ablation study; long‑running dashboards.

## III. Thay đổi theo module
### 1) UI & LLM Integration
- `streamlit_app/components/rag_demo.py`
  - Toggle “🚀 Use Real Gemini API”
  - HyDE default OFF; stable UX without light tier
- `streamlit_app/components/rag_gemini_direct.py`
  - Auto‑load indices if missing; call `HybridRetriever.search()` → build context → Gemini
  - Show retrieved docs, citations, and pipeline steps

### 2) Indices Loader
- `app/deps/indices.py`
  - Use absolute project root for `artifacts/index/{bm25,faiss}` (robust with Streamlit cwd)
  - `startup_indices()` returns readiness + statistics

### 3) OCR Ingestion & Builder
- `app/ingestion/pdf_processor.py`
  - OCR fallback (2x render; confidence filter; cache `data/staging/ocr_cache/`)
  - Post‑process OCR text (unicode, spacing, hyphen merge)
- `tools/build_bm25_index.py`
  - `--enable-ocr` flag; pass `enable_ocr=True` to `PDFProcessor`
  - Build BM25 from chunk dicts (correct `BM25Indexer.build_index()` interface)

### 4) Evaluation Runner
- `app/evaluation/batch_runner.py`
  - Fix: use `trace_span()` context manager; remove incorrect use of decorator as context
  - Retrieval‑only runs produce CSV/JSON under `artifacts/eval/`

### 5) Documentation
- `docs/Phase3_Integration_Guide.md` created (unified guide)
- Legacy Phase 3 docs consolidated and removed to reduce duplication

## IV. Hướng dẫn sử dụng — End‑to‑End
### 1) Build BM25 with OCR
```bash
python tools/build_bm25_index.py --input-dir data/raw/phase1_pilot --enable-ocr
```
Artifacts:
- Chunks: `artifacts/chunks/chunks.json`
- BM25: `artifacts/index/bm25/`

### 2) Start Backend
```bash
python -m app.main
```
Check:
- `/healthz`, `/metrics`, `/trace`, `/index-stats`

### 3) Start Streamlit UI (Demo)
```bash
cd streamlit_app
streamlit run app.py
```
In the UI:
- Enable “🚀 Use Real Gemini API”
- Choose `gemini-2.5-flash`
- Ask domain questions (e.g., CO2 compressor, ammonia P&ID)

### 4) Batch Evaluation (retrieval‑only)
```bash
python tools/run_evaluation.py artifacts/qa/golden_pseudo_v1.jsonl --no-e2e --output-dir artifacts/eval --no-html --no-individual-results
```
Outputs:
- CSV summary: `artifacts/eval/evaluation_summary_*.csv`
- JSON report: `artifacts/eval/evaluation_report_*.json`

## V. Kết quả & ghi nhận
- UI truy hồi nội dung thực từ `Data Sheet for CO2 Compressor Steam Turbine.rev0E` và các tài liệu khác.
- Sau khi rebuild với OCR, tổng số BM25 chunks ≈ 570 (từ 4 PDF), kết quả tốt cho chủ đề CO2 compressor.
- Evaluation runner: tỉ lệ thành công 100% sau khi sửa; xuất CSV/JSON thành công.

## VI. Vấn đề đã biết & hướng xử lý
- FAISS bị giới hạn nếu chưa cấu hình embeddings; fallback BM25 vẫn hoạt động.
- HyDE có thể lỗi nếu chưa cấu hình light tier; mặc định OFF trong UI.
- Cảnh báo cấu hình Streamlit với các khóa cũ; xem tài liệu sự cố để dọn dẹp cấu hình.

## VII. Khuyến nghị (hướng Phase 4)
- Add A/B experiments page to UI (HyDE on/off, rerank variations) with automatic metric logging.
- Extend evaluation to E2E (faithfulness/citation), wire to running backend.
- Security hardening: authN/Z, quotas, audit logs.
- Optional: distributed cache (Redis) and circuit breakers for stability.

## VIII. Artefact & Đường dẫn
- Indices: `artifacts/index/bm25/`, `artifacts/index/faiss/`
- Chunks: `artifacts/chunks/chunks.json`
- Evaluation: `artifacts/eval/`
- OCR cache: `data/staging/ocr_cache/`

## IX. Files Touched / Added (non‑exhaustive)
- UI: `streamlit_app/components/rag_demo.py`, `streamlit_app/components/rag_gemini_direct.py`
- Indices: `app/deps/indices.py`
- Ingestion/OCR: `app/ingestion/pdf_processor.py`, `tools/build_bm25_index.py`
- Evaluation: `app/evaluation/batch_runner.py`, `tools/run_evaluation.py`
- Docs: `docs/Phase3_Integration_Guide.md`

## X. Kết luận
Phase 3 đã bàn giao một UI demo sử dụng được, bám nguồn, với truy hồi thực tế và bao phủ OCR, kèm batch evaluation cho retrieval và độ ổn định cao hơn. Hệ thống sẵn sàng cho Phase 4: tối ưu, A/B testing và các kiểm soát ở mức production.
