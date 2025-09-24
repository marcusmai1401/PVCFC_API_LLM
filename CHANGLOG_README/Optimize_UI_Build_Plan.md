# Kế hoạch Build UI Tối ưu hoá — PVCFC RAG Debug/Performance Frontend

Owner: PVCFC Engineering
Date: 2025-09-16
Status: Bản nháp để review
Tài liệu thiết kế liên quan:
- docs/TECH_DESIGN_DEBUG_UI.md
- docs/TECH_DESIGN_INGEST_AND_VISION.md

Mục đích
- Lập kế hoạch triển khai chi tiết một UI phục vụ debug/tối ưu hiệu suất cho hệ thống RAG (không phải production), bao gồm: popup PDF đúng trang/vị trí, report template, highlight entities, quan sát hoạt động của LLM tier nhẹ/nặng (và embedding), tích hợp nút “Ingest/OCR” một chạm, và (tuỳ chọn) Vision‑Assisted Verification.

Ngoài phạm vi (giai đoạn này)
- Không triển khai UI production cho end-users.
- Không triển khai hệ thống phân quyền/SSO.
- Không triển khai đầy đủ workflow OCR/HOCR cho mọi loại layout phức tạp (làm mức đủ dùng).

Giả định & Phụ thuộc
- API hiện có: /ask, /locate, /report, /healthz, /metrics, /index‑stats.
- Sẽ bổ sung endpoint ingest: /ingest/start, /ingest/status/{job_id}, /indices/reload (theo TECH_DESIGN_INGEST_AND_VISION.md).
- Artefact mong đợi cho UI:
  - artifacts/index/{bm25,faiss}
  - (Phase 2) artifacts/pages/{doc_id}/{page}.png (render PDF)
  - (Phase 2) artifacts/pages/{doc_id}/{page}.hocr.json (bbox từ OCR cho scan)
- LLM client trả metadata model/tokens nếu SDK hỗ trợ; nếu không có, UI phải degrade gracefully.

Mốc chính (High‑level)
- Phase 0: Thiết lập dự án & khung điều hướng
- Phase 1: Core Query Lab (timeline, retrieval/rerank/generation, citations)
- Phase 2: PDF popup & highlight chính xác (bbox/HOCR); multi‑term highlight
- Phase 3: Ingest Panel (ingest/OCR một chạm) + reload index
- Phase 4: Report Lab (render/export template)
- Phase 5: Tier Inspector (A/B light vs heavy) + tuỳ chọn embedding view
- Phase 6: Vision Verify (tùy chọn, feature‑flag)
- Phase 7: Công cụ debug nâng cao, metrics/log tailing, scenarios, presets
- Phase 8: Hardening (tối ưu hiệu năng, xử lý lỗi), Docs & bàn giao

Mô hình theo dõi
- Mỗi phase có: deliverables, tasks, acceptance criteria, risks, effort estimate (tương đối), owner.

-----------------------------------------------------------------------
Phase 0 — Setup & Navigation (1–2 days)
Deliverables
- Streamlit navigation skeleton: Home (Dashboard), Query Lab, Report Lab, Ingest, Tier Inspector, Metrics/Logs.
- Basic layout grid, theme (dev-focused, không cần brand).
Tasks
- Create or extend streamlit_app/app.py for navigation.
- Create component stubs under streamlit_app/components/:
  - query_lab.py, pdf_viewer.py, ingest_panel.py, report_lab.py, tier_inspector.py, metrics_logs.py
- Wiring to call existing API base URL (configurable via env/UI field).
Acceptance Criteria
- Có thể chuyển tab giữa các module, mỗi tab hiển thị placeholder.
- Config API base URL trong sidebar (persist session state).
Risks
- None significant.

-----------------------------------------------------------------------
Phase 1 — Core Query Lab (3–5 days)
Deliverables
- Form nhập query + knobs điều chỉnh: HyDE on/off, k_bm25, k_faiss, rrf_k, top_k context, reranker method, expand_parent, execution_mode (production/heavy_only/light_only), language.
- Kết quả phân tab: Overview (answer + warnings + confidence + breakdown), Retrieval (BM25/FAISS & fused RRF), Rerank (before/after), Generation (prompt snapshot redacted + timing), Citations, Metrics, Logs.
- Timeline latency từng bước (transform/retrieve/rerank/generate/cove nếu có) theo meta.breakdown hoặc state.timing_breakdown.
Tasks
- Giao diện form và gọi POST /ask với các tham số tương ứng.
- Render kết quả/metadata; vẽ timeline (bars hoặc table với ms).
- Retrieval view: hiển thị danh sách từ BM25, FAISS và fused list (nếu hiện API trả fused; nếu không, hiển thị kết quả sau rerank).
- Rerank view: hiển thị scores trước/sau; nếu có explanation từ reranker thì render.
- Generation view: model name, latency, token usage (nếu có), prompt snapshot (ẩn chi tiết nhạy cảm, nếu cần).
- Citations view: bảng doc_id, page, bbox (nếu có), score.
- Logs/Metrics view: hiển thị trace_id/ request_id từ headers/response meta; tạm thời parse /metrics (throttled).
Acceptance Criteria
- Chạy /ask thành công với knobs cơ bản, hiển thị đầy đủ panel/tabs và latency.
- Có thể xem danh sách citations và metadata.
- Không crash khi thiếu tokens/usage hoặc thiếu bbox.
Risks
- API không trả đủ thông tin rerank/fused; UI cần degrade."OK" bằng dữ liệu khả dụng.

-----------------------------------------------------------------------
Phase 2 — PDF Popup & Precise Highlight (4–7 days)
Deliverables
- Click vào một citation → mở modal hiển thị đúng trang PDF (ảnh render) và overlay highlight vùng bbox; nếu thiếu bbox, fallback tìm theo snippet.
- Multi-term highlighting: panel chọn “key terms” (tags/equipment) để tô trên trang.
Tasks
- Backend/Artifacts (dependency):
  - Ingest process render trước trang PDF -> artifacts/pages/{doc_id}/{page}.png (200–300 DPI).
  - (Scan) HOCR export -> page.hocr.json.
- Frontend:
  - pdf_viewer component dùng <img> + overlay (HTML absolute divs); scale bbox PDF→pixel.
  - Fallback tìm bbox bằng PyMuPDF text search (nếu đọc file trực tiếp) hoặc precomputed mapping.
  - Multi-term highlight: sinh list terms từ query/answer và highlight.
Acceptance Criteria
- Click citation hiển thị đúng trang; nếu có bbox thì highlight chính xác; nếu không có bbox, vẫn mở đúng trang.
- Toggle bật tắt highlight theo term.
Risks
- Thiếu bbox cho scanned PDFs: cần HOCR. Nếu chưa có, chấp nhận fallback toàn trang/approx.
- Performance khi nhiều overlay: paginate/limit overlay.

-----------------------------------------------------------------------
Phase 3 — Ingest Panel (One-Click Ingest/OCR) (4–6 days)
Deliverables
- UI để upload files hoặc nhập folder path, chọn options (OCR auto/force/off, language), bấm Start Ingest.
- Bảng job status (queued/running/success/failed), % progress, stage, log tail; nút Reload Indices; hiển thị snapshot.
Tasks
- Implement UI gọi POST /ingest/start, GET /ingest/status/{job_id}, POST /indices/reload.
- Polling status, hiển thị logs_tail.
- Link đến snapshot artifacts (nếu có).
Acceptance Criteria
- Start ingest job, thấy tiến độ/percent; reload indices sau khi hoàn tất; Query Lab phản ánh index mới (/index-stats thay đổi).
Risks
- Backend ingest endpoints chưa sẵn: cần song song triển khai tối thiểu (xem TECH_DESIGN_INGEST_AND_VISION.md).
- Atomic swap trên Windows: xác định phương thức swap an toàn.

-----------------------------------------------------------------------
Phase 4 — Report Lab (Template) (3–5 days)
Deliverables
- Chọn template (Markdown/Jinja2), gọi /report, đổ dữ liệu vào template, preview và export .md (Phase 2: .docx nếu cần).
- Built-in sample template streamlit_app/templates/report_sample.md.
Tasks
- Template manager đơn giản: upload/choose template; render bằng Jinja2; preview Markdown; download.
- Mapping data từ ReportResponse vào template variables.
Acceptance Criteria
- Render được 1 báo cáo mẫu với citations; export .md thành công.
Risks
- .docx conversion cần thêm phụ thuộc (python-docx/pandoc) → lùi Phase 2.

-----------------------------------------------------------------------
Phase 5 — Tier Inspector (A/B Light vs Heavy) + Embedding View (3–6 days)
Deliverables
- Chạy cùng query 2 lần (light và heavy); hiển thị side-by-side: answer, citations, latency, model, tokens (nếu có); so sánh khác biệt.
- (Optional) Embedding view: PCA/UMAP top-20 docs với query.
Tasks
- A/B executor: phát 2 request /ask với execution_mode hoặc tier config.
- UI 2 cột + diff.
- Embedding view: gọi service embedding (nếu lộ ra sẵn) hoặc mock; vẽ scatter.
Acceptance Criteria
- A/B hiển thị rõ khác biệt latency/model/answer.
- Embedding plot hoạt động với sample dataset (nếu enable).
Risks
- Token usage/usage metadata không đồng nhất giữa providers → xử lý thiếu dữ liệu.

-----------------------------------------------------------------------
Phase 6 — Vision-Assisted Verification (Optional, Feature-Flag) (5–8 days)
Deliverables
- Panel Vision Verify trong Query Lab hiển thị claims được kiểm tra, trang đã đọc lại (image), chỉnh sửa/caveat được áp dụng, verification_rate.
- Config toggle: verification_mode=never/auto/always; high_accuracy flag.
Tasks
- Backend dependency: bổ sung render page images và (nếu bật) gọi LLM multimodal theo thiết kế (TECH_DESIGN_INGEST_AND_VISION.md).
- UI: hiển thị kết quả vision verify; nếu có correction, highlight phần thay đổi.
- Caching indicators (page reuse).
Acceptance Criteria
- Khi bật always, UI cho thấy ít nhất 1 trang được verify và điều chỉnh output (nếu phát hiện sai khác).
- Khi vision lỗi, cảnh báo và fallback về text-only.
Risks
- Latency/cost tăng; thêm throttle/caps trong UI (max_pages, max_claims).

-----------------------------------------------------------------------
Phase 7 — Advanced Debug Tools & Presets (3–5 days)
Deliverables
- Scenario recording/replay; so sánh 2 run (latency/quality/citations).
- Presets: Cost-optimized / Accuracy-optimized / Debug-verbose.
- Cache controls: xem cache hit-rate (nếu có endpoint), nút clear cache.
Tasks
- Lưu/lấy cấu hình run dưới streamlit_app/data/scenarios/.
- Preset buttons set multiple knobs.
- (Optional) Thêm /cache-stats endpoint phía API để UI đọc.
Acceptance Criteria
- Lưu mở scenario; apply preset; clear cache (nếu có endpoint) và thấy metric thay đổi.
Risks
- Cần thêm endpoint hỗ trợ.

-----------------------------------------------------------------------
Phase 8 — Hardening, Docs & Handover (2–4 days)
Deliverables
- Tối ưu hiệu năng UI (lazy load, throttle, pagination overlay, limit highlights).
- Error handling, empty state handling đầy đủ.
- Cập nhật docs: README debug UI, quick start, known issues.
Tasks
- Profiling đơn giản, tối ưu render nặng (PDF overlay, charts).
- Bổ sung docs trong streamlit_app/README.md và docs/.
Acceptance Criteria
- UI mượt ở dataset mẫu; không crash khi thiếu dữ liệu/bbox; có hướng dẫn rõ ràng.

-----------------------------------------------------------------------
Cross-Cutting Requirements
- Feature flags: Vision Verify, Embedding view (bật/tắt nhanh trong UI).
- Observability: Hiển thị trace_id; parse một số metrics Prometheus chính (request/latency/citation).
- Security (vì là dev UI): tuỳ chọn token header để gọi ingest/reload nếu backend yêu cầu.
- Windows-friendly paths: đảm bảo đọc file artifacts/pages/... ổn định.

Acceptance Criteria (Global Summary)
- Có thể chạy quy trình hỏi đáp với knobs, xem đầy đủ pipeline breakdown và citations.
- Click citation mở đúng trang (và highlight nếu có bbox/HOCR).
- Ingest “một chạm” chạy end-to-end, reload index, UI phản ánh thay đổi.
- Tạo report từ template mẫu và export .md.
- A/B tier light vs heavy hiển thị rõ sự khác biệt latency/chất lượng.
- (Optional) Vision verify hoạt động khi bật flag, điều chỉnh output khi phát hiện sai khác.

Risks & Mitigations
- Bbox thiếu/không chính xác: bổ sung HOCR; fallback full-page; cảnh báo người dùng.
- Latency cao với vision: giới hạn số trang/claims, cache images, preset Auto chỉ chạy khi confidence thấp.
- Độ phức tạp UI tăng: chia phases, giữ scope gọn từng PR, thêm preset để test nhanh.
- Ingest atomic swap Windows: thử nghiệm và nếu cần tạm pause ngắn khi swap; rollback snapshot khi lỗi.

Effort Estimate (rough)
- Phase 0: 1–2d
- Phase 1: 3–5d
- Phase 2: 4–7d
- Phase 3: 4–6d
- Phase 4: 3–5d
- Phase 5: 3–6d
- Phase 6: 5–8d (optional)
- Phase 7: 3–5d
- Phase 8: 2–4d

Owners (suggested)
- UI Lead: Streamlit components & UX
- Backend Support: Ingest endpoints, page rendering, HOCR, vision client
- QA/SME: Template/report validation, highlight accuracy acceptance

References
- docs/TECH_DESIGN_DEBUG_UI.md — chi tiết kiến trúc/flow UI
- docs/TECH_DESIGN_INGEST_AND_VISION.md — ingest/OCR & vision verification design
- app/main.py, app/deps/indices.py — index lifecycle
- app/core/* — metrics/logging/tracing/rate limit
- app/rag/* — pipeline modules
- tools/* — ingest/index build utilities
