# Phase3_Integration_Guide

## 1) Mục tiêu và phạm vi
- Chuẩn hóa triển khai Phase 3 (Evaluation + UI demo + OCR) trên nền Phase 1/2 đã hoàn tất.
- Tài liệu này hợp nhất và thay thế các ghi chú rời: Gemini integration, UI dùng dữ liệu thật, OCR fallback, hướng dẫn chạy và đánh giá.

Nội dung bao gồm:
- Tích hợp UI Streamlit với indices thật và Gemini (Live mode)
- OCR fallback cho PDF scan/mixed và rebuild index
- Chạy batch evaluation (retrieval-only) và sinh báo cáo
- Troubleshooting và checklist đi live demo

---

## 2) Điều kiện tiên quyết
- Python 3.11 (64-bit), venv khuyến nghị
- Đã cài requirements:
```bash
pip install -r requirements.txt
```
- `.env` tối thiểu:
```env
APP_ENV=local
API_PORT=8000
LOG_LEVEL=INFO
LLM_PROVIDER=gemini
LLM_LIGHT_PROVIDER=gemini
LLM_MODEL_LIGHT=gemini-2.5-flash
LLM_MODEL_HEAVY=gemini-2.5-pro
GEMINI_API_KEY=...
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=text-embedding-004
```

---

## 3) Build chỉ mục với OCR (bao phủ PDF scan/mixed)
Phase 3 bổ sung OCR fallback để các trang scan có thể được index và tìm kiếm.

- Công cụ build (đã cập nhật): `tools/build_bm25_index.py`
- OCR fallback class: `app/ingestion/pdf_processor.py` (enable_ocr, cache, confidence filter)

Thực thi:
```bash
# Build lại BM25 với OCR bật
python tools/build_bm25_index.py --input-dir data/raw/phase1_pilot --enable-ocr
```
Kết quả mong đợi:
- Chunks được lưu tại: `artifacts/chunks/chunks.json`
- Chỉ mục BM25: `artifacts/index/bm25/`
- Log test search hiển thị hit mạnh cho từ khóa (ví dụ "CO2 compressor").

Ghi chú:
- Đường dẫn index dùng tuyệt đối theo project root (đã cập nhật): `app/deps/indices.py`
- OCR cache: `data/staging/ocr_cache/` (tự tạo, tránh OCR lặp)

---

## 4) Khởi chạy Backend (FastAPI)
```bash
python -m app.main
```
Endpoints kiểm tra nhanh:
- Health: GET `http://localhost:8000/healthz`
- Metrics: GET `/metrics`
- Trace: GET `/trace`
- Index stats: GET `/index-stats`

Lưu ý: App startup sẽ gọi `startup_indices()` để load retriever từ `artifacts/index/{bm25,faiss}`.

---

## 5) Khởi chạy UI Streamlit (Demo RAG)
```bash
cd streamlit_app
streamlit run app.py
```
Trong UI (trang "🔍 RAG Demo"):
- Bật toggle "🚀 Use Real Gemini API"
- Chọn model Gemini (ví dụ: `gemini-2.5-flash`)
- Nhập câu hỏi và nhấn "🚀 Generate Answer"

Triển khai nội bộ:
- Component: `streamlit_app/components/rag_demo.py`
- Tích hợp LLM: `streamlit_app/components/rag_gemini_direct.py`
  - Tự động load retriever nếu chưa có (`get_index_manager().load_indices()`)
  - Gọi `HybridRetriever.search()` → build context → gọi Gemini sinh trả lời
- Citations và Retrieved Documents hiển thị theo dữ liệu thật từ index

---

## 6) Cách hoạt động (chi tiết kỹ thuật)
- Loader: `app/deps/indices.py`
  - Xác định `project_root`
  - Index paths tuyệt đối: `artifacts/index/bm25`, `artifacts/index/faiss`
  - Tạo retriever qua `create_hybrid_retriever(...)`
- Retriever: `app/rag/retriever.py`
  - BM25 + FAISS + RRF + expand-parent
- Query transform: `app/rag/query_transform.py` (HyDE mặc định OFF trong UI để ổn định)
- Generator (Gemini): `app/rag/generator.py` và client `app/services/llm_client.py`
- OCR fallback: `app/ingestion/pdf_processor.py` (2x render, confidence > min, cache, post-process)

---

## 7) Batch Evaluation (retrieval-only)
Chạy evaluation trên pseudo-golden để thu hồi số liệu nhanh:
```bash
# retrieval-only, không e2e
python tools/run_evaluation.py artifacts/qa/golden_pseudo_v1.jsonl --no-e2e --output-dir artifacts/eval --no-html --no-individual-results
```
Đầu ra:
- CSV summary: `artifacts/eval/evaluation_summary_*.csv`
- JSON report: `artifacts/eval/evaluation_report_*.json`

Chỉ số chính (ví dụ):
- Recall@5 / Recall@10, Precision@5
- Success rate (tỷ lệ bài không lỗi)

---

## 8) Báo cáo và template
- Mẫu báo cáo nhanh: Phase3_Batch_Evaluation_Report_Template (đã chuẩn hóa header).
- Có thể copy phần bảng từ CSV sang báo cáo, kèm biểu đồ khi cần.

---

## 9) Troubleshooting
- UI hiển thị No Results:
  - Kiểm tra `artifacts/index/bm25` tồn tại
  - Đảm bảo `app/deps/indices.py` đang dùng đường dẫn tuyệt đối
  - Rebuild index với `--enable-ocr`
- FAISS trả 0:
  - Thiết lập `EMBEDDING_PROVIDER` và model, hoặc dùng BM25-only
- HyDE cảnh báo:
  - Để OFF mặc định trong UI, hoặc cấu hình light tier đầy đủ
- Streamlit "File does not exist":
  - Chạy từ thư mục `streamlit_app/` và đúng file `app.py`

---

## 10) Checklist đi live demo (Phase 3)
- [.env] Đầy đủ GEMINI/EMBEDDING
- [Indices] BM25/FAISS đã build (BM25 có OCR nếu có scan/mixed)
- [Backend] `/metrics`, `/trace`, `/index-stats` OK
- [Runners] Chạy retrieval-only report trên pseudo-golden
- [UI] Demo hoạt động, hiển thị citations và retrieved docs

---

## 11) Tham chiếu file chính
- `tools/build_bm25_index.py` — build index + OCR
- `app/ingestion/pdf_processor.py` — OCR fallback & cache
- `app/deps/indices.py` — absolute index paths, retriever loader
- `app/rag/retriever.py` — hybrid search (BM25/FAISS/RRF)
- `streamlit_app/components/rag_demo.py` — UI demo
- `streamlit_app/components/rag_gemini_direct.py` — LLM integration (Gemini)
- `tools/run_evaluation.py` — batch evaluation CLI

---

## 12) Lệnh nhanh (cheat sheet)
```bash
# 1) Rebuild BM25 (có OCR)
python tools/build_bm25_index.py --input-dir data/raw/phase1_pilot --enable-ocr

# 2) Khởi động backend
python -m app.main

# 3) Khởi động UI demo
cd streamlit_app
streamlit run app.py

# 4) Evaluation retrieval-only
cd ..
python tools/run_evaluation.py artifacts/qa/golden_pseudo_v1.jsonl --no-e2e --output-dir artifacts/eval --no-html --no-individual-results
```

---

## 13) Ghi chú
- Tài liệu này hợp nhất các nội dung Phase 3 trước đây (Gemini integration, UI dùng dữ liệu thật, OCR, report template). Các bản lẻ cũ đã được thay thế bởi hướng dẫn hợp nhất này.
