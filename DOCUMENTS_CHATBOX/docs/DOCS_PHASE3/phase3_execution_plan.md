# Phase 3 — Execution Plan (Không cần golden 120 QA ngay)

Tài liệu này chuyển hóa chiến lược Phase 3 thành các workstream nhỏ, có tiêu chí xong (DoD), đầu ra, và thứ tự thực thi. Mục tiêu: đánh giá, demo UI, giám sát — tiến triển được ngay cả khi chưa có 120 QA đầy đủ.

## 1) Logging, Metrics, Tracing (Observability First)
- Mục tiêu: có thể đo lường chất lượng/hiệu năng ngay trên traffic thử nghiệm.
- Việc cần làm:
  1. Logging JSONL chi tiết: đảm bảo mỗi request ghi `timing_by_stage`, `params`, `citations`, `errors` vào `logs/requests.jsonl` (đã có, chỉ need review fields).
  2. Metrics Prometheus: xác nhận counters/histograms cho latency theo bước, citation count, cove verification rate, cache hits, error types. Bổ sung metric “citation_rate”, “verification_rate”.
  3. Tracing: xác nhận middleware hoạt động, export trace JSON tại `/trace`. Thêm tag `execution_mode`, `tier`, `hyde_on`.
- DoD:
  - `/metrics` có đủ latency breakdown; log có trace_id và citations; `/trace` hoạt động.
- Đầu ra:
  - Ví dụ dashboard sơ bộ (grafana/mock) hoặc bảng Prometheus metrics dump để lập biểu đồ.

## 2) Pseudo‑Golden Bootstrapping (40–60 QA)
- Mục tiêu: tạo bộ QA tạm (có doc_hints) để chạy đánh giá.
- Việc cần làm:
  1. `tools/generate_synthetic_qa.py`:
     - Sinh câu hỏi từ tài liệu (datasheet/om/pid) theo template lookup/locate/report/negative/ambiguous.
     - Dùng LLM light để đề xuất câu hỏi + doc_hints.
  2. Lọc tự động: chỉ giữ QA mà retriever đưa `doc_hints` vào top‑5.
  3. Spot‑check thủ công 20 QA để hiệu chỉnh template/heuristics.
- DoD:
  - Có 50±10 QA hợp lệ (JSONL), trong đó ≥15 negative/ambiguous.
- Đầu ra:
  - `artifacts/qa/golden_pseudo_v1.jsonl` (có id, query, doc_hints, expected_citations? nếu có).

## 3) Evaluation Runners (Batch)
- Mục tiêu: đánh giá retrieval và e2e mà không cần golden hoàn chỉnh.
- Việc cần làm:
  1. `tools/eval_retrieval.py`: chạy retriever theo pseudo‑golden, tính Recall@k, MRR@k, nDCG@k; lưu CSV/JSON.
  2. `tools/eval_e2e.py`: chạy full pipeline (HyDE on/off; k khác nhau), tính: citation rate, CoVe verification rate, length checks, latency tổng và breakdown.
  3. `docs/phase3_report_template.md`: template báo cáo kết quả + biểu đồ.
- DoD:
  - Có bảng kết quả theo doc_category/type/difficulty; có biểu đồ latency/citation/recall.
- Đầu ra:
  - `artifacts/eval/phase3_batch_results.{csv,json}`; `artifacts/eval/phase3_report.md`.

## 4) Streamlit Demo & Annotation (UI)
- Mục tiêu: cho SMEs xem và góp ý — không cần backend phức tạp.
- Việc cần làm:
  1. `streamlit_app/app.py`:
     - Trang Search: nhập query, tùy chọn HyDE/k/rrf/expand‑parent/execution_mode; hiển thị answer + citations + top hits + latency breakdown.
     - Click‑to‑cite: preview PDF (PyMuPDF) + overlay bbox; fallback text window với scan.
     - Telemetry: ghi lại session vào `logs/ui_sessions.jsonl`.
  2. Annotation panel: Correct/Partial/Incorrect; Citation OK?; Notes ⇒ lưu `artifacts/annotation/annotations.jsonl`.
  3. Trang Experiments: A/B hai cấu hình (ví dụ HyDE on/off), hiển thị bảng so sánh metrics.
- DoD:
  - Chạy được demo, ghi sessions + annotations; xem lại được session.
- Đầu ra:
  - `streamlit_app/` folder + hướng dẫn chạy (`make demo`).

## 5) Hard‑Case Mining & Pseudo‑Golden v2
- Mục tiêu: từ logs thực tế, trích câu hỏi khó → cập nhật QA set.
- Việc cần làm:
  1. `tools/mine_hardcases.py`:
     - Tìm request có CoVe verification thấp, citation không đầy đủ, latency cao, hoặc top‑hits lệch doc_hints.
  2. Sinh đề xuất câu hỏi cải tiến/clarify và cập nhật `golden_pseudo_v2.jsonl`.
- DoD:
  - Có danh sách ≥ 20 hard cases; cập nhật pseudo‑golden v2.
- Đầu ra:
  - `artifacts/qa/golden_pseudo_v2.jsonl`; `artifacts/qa/hardcases.jsonl`.

## 6) Pre‑flight Checklist (Go‑Live cho Demo)
- [ ] `.env` đầy đủ (GEMINI_API_KEY, EMBEDDING_MODEL=text-embedding-004…).
- [ ] BM25/FAISS đã build (thư mục artifacts tồn tại).
- [ ] `/metrics`, `/trace`, `/index-stats` hoạt động.
- [ ] Smoke test endpoints `/ask`, `/locate`, `/report`.
- [ ] Chạy `tools/eval_retrieval.py` & `tools/eval_e2e.py` với pseudo‑golden.
- [ ] Streamlit demo chạy, lưu được sessions/annotations.

## 7) Ưu tiên & Thứ tự thực thi (2–3 tuần)
1. Observability (1–2 ngày)
2. Synthetic QA + lọc (2–4 ngày)
3. Eval runners + report template (2–3 ngày)
4. Streamlit demo + annotation (4–6 ngày)
5. Mining hard cases + pseudo‑golden v2 (2–3 ngày)
6. Buffer/bugfix/retrospective (1–2 ngày)

## 8) Rủi ro & Giảm thiểu
- Thiếu dữ liệu: dùng synthetic + mining từ logs; giữ tỷ lệ negative/ambiguous.
- Latency cao: tắt HyDE trong demo, giảm `max_context`, dùng light‑only khi cần.
- Citation lệch: ép format citations; nếu CoVe thấp → cảnh báo trong answer.

## 9) Đầu việc tạo file/code (danh sách tạo mới)
- tools/generate_synthetic_qa.py
- tools/eval_retrieval.py
- tools/eval_e2e.py
- tools/mine_hardcases.py
- streamlit_app/app.py
- docs/phase3_report_template.md
