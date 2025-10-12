# Kế hoạch chỉnh sửa: Confidence, Vision-assisted Verification, UI Citations, System Status, Embedding Visualization

Tài liệu này mô tả hiện trạng, nguyên nhân, mục tiêu và kế hoạch chỉnh sửa chi tiết cho các vấn đề đã được quan sát trong hệ thống RAG (FastAPI + Streamlit), bao gồm: hiệu chỉnh Confidence, "Vision-assisted verification" luôn bật, sửa UI Citations (hiển thị trang PDF), sửa System Status (Indices), và định nghĩa phạm vi cho tính năng Embedding Visualization.


## 1) Bối cảnh và hiện trạng

- Hệ thống đã chạy ổn định với các chỉ mục BM25/FAISS (được log “Indices loaded …”).
- Pipeline retrieval hiện có thêm cơ chế Page Range Expansion và (đã được bổ sung) nạp FULL TEXT của trang PDF gốc vào context cho LLM nặng (heavy) để “quét cả trang”, thay vì chỉ dùng chunk nhỏ.
- UI đã có tab Citations (Enhanced), nút “View Page”, và ép execution_mode = production, tuy nhiên còn các điểm chưa đúng như mong muốn (chi tiết ở phần Vấn đề & nguyên nhân).


## 2) Vấn đề và nguyên nhân gốc

1. Confidence thấp dù câu trả lời đúng
   - Cách tính hiện tại dựa vào điểm retrieval/rerank (BM25/FAISS/RRF, score-based). Các điểm này có thang đo nhỏ và không phản ánh xác suất theo nghĩa “độ tin cậy”. Do đó Confidence hiển thị thấp một cách không trực quan.

2. Vision-assisted verification "luôn bật" (kỳ vọng) nhưng thực tế chưa tích hợp Vision LLM
   - UI có flag liên quan vision, nhưng pipeline sinh câu trả lời chưa đưa ảnh trang PDF vào Vision LLM để xác minh. Hiện tại ta đã “đọc full text trang”, chưa phải “nhìn trang (ảnh)”.
   - Cờ UI còn chưa thống nhất (enable_vision vs enable_vision_verify), dễ gây mơ hồ.

3. System Status cảnh báo "Indices not loaded" dù backend đã load
   - UI kiểm tra trực tiếp bằng import trong process của Streamlit (khác process API). Vì không gọi API /index-stats, nên kết luận sai ở phía UI.

4. Nút "View Page" trong Citations không hiển thị trang PDF như mong muốn
   - UI lấy sai trường: API trả về pdf_path, nhưng UI đang cố lấy metadata.source/source. Điều kiện hiển thị không thỏa nên không render trang.
   - Cách hiển thị dùng expander, chưa có popup/modal (Streamlit không native modal; cần giải pháp UX phù hợp).

5. Embedding Visualization chưa có, nhưng có flag
   - Đây là tính năng nâng cao phục vụ debug/đánh giá vector. Chưa được hiện thực; không nên bật mặc định vì tốn tài nguyên.


## 3) Mục tiêu

- M1: Confidence phản ánh trực quan hơn mức độ tin cậy của câu trả lời.
- M2: "Vision-assisted verification" có định nghĩa rõ, có thể luôn bật ở UI theo nghĩa pipeline thực sự dùng ảnh trang (nếu được bật) để xác minh.
- M3: Sửa UI Citations để luôn xem được trang PDF (inline hoặc mở tab mới), tương thích với pdf_path từ API.
- M4: Sửa System Status để phản ánh đúng trạng thái chỉ mục từ API.
- M5: Định nghĩa rõ phạm vi Embedding Visualization (để build sau, không bật mặc định).


## 4) Phạm vi và Phi phạm vi

- Trong phạm vi:
  - Hiệu chỉnh Confidence (rescale/boost theo tín hiệu phù hợp, vẫn trong giới hạn [0,1]).
  - Sửa UI Citations (dùng pdf_path; cải thiện UX xem trang; logging nút bấm).
  - Sửa System Status (đọc từ API /index-stats, /healthz).
  - Thiết kế và bước đầu tích hợp Vision-assisted verification (luồng, API, UI flag thống nhất), nhưng có thể rollout theo phase.
  - Xác định scope cho Embedding Visualization và treo cờ tắt mặc định.

- Ngoài phạm vi (giai đoạn này):
  - Thay đổi kiến trúc ingest, tái xây dựng toàn bộ index.
  - Triển khai OCR realtime mặc định cho mọi trang (chỉ xem xét sau khi có nhu cầu rõ).


## 5) Giải pháp đề xuất chi tiết

### 5.1 Sửa UI Citations: dùng pdf_path, cải thiện hiển thị

- Vấn đề: UI đang dùng `citation.metadata.source` hoặc `citation.source`, trong khi API trả về `citation.pdf_path` và `citation.page`.
- Giải pháp:
  - Thay key lấy đường dẫn: `source_path = citation.get('pdf_path')`.
  - Gọi `/api/pdf/render-page?pdf_path=...&page_num=...&dpi=150&format=png` để hiển thị ảnh.
  - UX:
    - Phương án A (mặc định): Hiển thị inline bằng expander (auto expanded), có nút Close.
    - Phương án B (tùy chọn): Thêm link “Open in new tab” trỏ trực tiếp đến URL render, thuận tiện zoom.
  - Logging: ghi sự kiện when-click-view, pdf_path, page, latency render.

Kết quả mong đợi: Nhấn “View Page” → thấy ngay ảnh trang PDF tương ứng.


### 5.2 System Status: lấy trạng thái từ API

- Vấn đề: UI check local state nên báo sai.
- Giải pháp:
  - UI gọi `GET /index-stats` và `GET /healthz` từ API để lấy dữ liệu thật.
  - Trạng thái hiển thị: BM25 loaded, FAISS loaded, số doc/chunk, dimension vector, v.v.
  - Nếu API unreachable → hiển thị cảnh báo “API không sẵn sàng”.

Kết quả mong đợi: Không còn cảnh báo giả “Indices not loaded” khi backend đã load.


### 5.3 Confidence calibration (chuẩn hóa thang điểm)

- Vấn đề: Điểm retrieval/rerank (RRF/BM25/score-based) nhỏ, không mang nghĩa xác suất.
- Giải pháp (đề xuất công thức):
  - Bước 1: Lấy tập điểm `S = {r.score | r ∈ reranked_results[:K]}`. Nếu rỗng thì confidence = 0.
  - Bước 2: Rescale theo min-max hoặc percentile:
    - `s' = (s - min(S)) / (max(S) - min(S) + ε)` để map vào [0..1].
    - Nếu `max(S)-min(S)` quá nhỏ, fallback vào trung vị/percentile mapping.
  - Bước 3: Tính `base_conf = mean(top m s')`, ví dụ m=3.
  - Bước 4: Boost theo tín hiệu:
    - Nếu `metadata.full_page == True` cho >= 1 citation → `base_conf += 0.10`.
    - Nếu `len(citations) >= 2` và các citations thống nhất về doc_id/page → `+0.05`.
    - Nếu `answer_length` vượt ngưỡng tối thiểu (ví dụ ≥ 200 ký tự) → `+0.05`.
    - Nếu pipeline dùng uncited fallback → `-0.10`.
  - Bước 5: Clamp [0, 1].

Lợi ích: Confidence phản ánh trực quan và tăng thêm khi có full_page + nhiều citation nhất quán.


### 5.4 Vision-assisted verification "luôn bật" — thiết kế

- Mục tiêu: Khi bật, hệ thống sẽ xác minh nội dung trọng điểm bằng Vision LLM trên ảnh trang PDF.
- Thiết kế cao cấp:
  1) Sau khi có câu trả lời draft + citations, lấy danh sách trang từ citations (pdf_path + page).
  2) Gọi `/api/pdf/render-page` để lấy ảnh trang (JPEG/PNG, dpi 150–200).
  3) Gọi Vision model (Gemini Vision) với prompt xác minh (ví dụ: “Trên trang này có đề cập …? Trích dẫn câu/giá trị.”).
  4) So sánh kết quả với answer; nếu lệch, thêm cảnh báo, hoặc điều chỉnh answer (CoVe vision-augmented).
  5) Ghi lại “verification report” trong meta (pages_checked, claims_verified, verification_rate, corrections).
- UI:
  - Thống nhất cờ: `enable_vision_verify` (một cờ duy nhất).
  - Nếu “luôn bật” theo yêu cầu UI: bật cờ mặc định trong UI; API có thể đọc cờ này từ payload (hoặc bật qua config) để kích hoạt bước xác minh vision.
- Lưu ý hiệu năng:
  - Giới hạn số trang xác minh (ví dụ 1–3 trang top) và dùng cache ảnh.
  - Cho phép tắt theo môi trường (local/prod) qua config.


### 5.5 Embedding Visualization — phạm vi & khi nào bật

- Phạm vi (đề xuất):
  - Trang “Embedding Viz”: cho phép chọn doc subset, nạp vectors từ FAISS, giảm chiều (UMAP/T-SNE), hiển thị scatter + hover snippet.
  - API bổ sung endpoint “/embedding/stats”, “/embedding/sample”.
- Bật mặc định? Không. Đây là tính năng debug, tốn tài nguyên.
- Khi nào bật: Khi cần phân tích chất lượng embedding/retrieval; nên có feature flag.


### 5.6 Logging, quan trắc và bảo mật

- Logging bổ sung:
  - Sự kiện bấm “View Page” + metadata (doc_id, page, latency render).
  - Metrics: số lần render-page, cache hit rate.
- Bảo mật/quyền truy cập:
  - Tránh để lộ đường dẫn nội bộ nếu publish ra ngoài (có thể hash doc_id → link nội bộ ẩn path).
  - Kiểm soát domain CORS cho Streamlit/Prod.


## 6) Lộ trình triển khai (không ước lượng thời gian)

- Phase A: UI Quick Fixes
  - Sửa Citations: dùng pdf_path → View Page hiển thị ổn.
  - System Status: dùng /index-stats, loại bỏ cảnh báo sai.

- Phase B: Confidence Calibration
  - Implement rescale + boosts (+full_page, +nhiều citations, +độ dài answer, -uncited fallback).
  - Thêm flag “confidence_mode=calibrated” (để dễ rollback).

- Phase C: Vision-assisted Verification (Always-on ở UI)
  - Thống nhất cờ UI + payload.
  - Triển khai bước gọi Vision LLM sau generation với ảnh trang từ render-page.
  - Ghi kết quả xác minh vào meta, hiển thị tab “Vision Verify”.

- Phase D: Embedding Visualization
  - Thiết kế endpoints, UI tab riêng, flag tắt mặc định.

- Phase E: Tối ưu & Hardening
  - Cache ảnh, rate limit render-page, bảo mật đường dẫn PDF (nếu cần ẩn path thật).


## 7) Tiêu chí nghiệm thu

- UI Citations:
  - Nhấn “View Page” → thấy ảnh trang PDF trong 1–2 giây với dpi 150, đúng trang.
  - Có nút “Open in new tab” (tuỳ chọn) hoạt động.

- System Status:
  - Khi API đã load indices, UI hiển thị “BM25/FAISS loaded” (đọc từ /index-stats).

- Confidence:
  - Trên các truy vấn đã biết câu trả lời đúng, Confidence hiển thị >= 0.7 (có full_page + 2 citations) trong đa số trường hợp.
  - Không còn case nội dung tốt nhưng Confidence < 0.3 mà không có lý do rõ.

- Vision verify:
  - Khi bật, meta có “pages_checked”, “claims_verified”, “verification_rate”.
  - Nếu tắt, không phát sinh chi phí Vision.

- Embedding Viz:
  - Trang hiển thị scatter với sample vectors, thao tác mượt ở subset nhỏ (demo).


## 8) Rủi ro & phương án giảm thiểu

- R1: Vision LLM trả về rỗng/không ổn định → fallback sang text-only; log cảnh báo.
- R2: Tăng context (full page) làm thời gian generate lâu hơn → giới hạn per_doc_max_chars, giảm số trang (top-N).
- R3: Lộ đường dẫn nội bộ D:\Data_Raw → có thể ẩn path trong UI (chỉ hiện doc_id + tên file), vẫn giữ pdf_path nội bộ để render.
- R4: Confidence quá cao/thấp sau calibrate → đặt flag để rollback nhanh sang mode cũ.


## 9) Các thay đổi cấu hình (nếu cần)

- UI flags: `enable_vision_verify` (duy nhất), `enable_embedding_viz` (mặc định false).
- API:
  - Thêm tùy chọn `confidence_mode: calibrated|legacy`.
  - Thêm query `open_in_new_tab` ở UI (không bắt buộc API).


## 10) Công việc cụ thể (backlog kỹ thuật)

- UI Citations
  - [x] Sửa key lấy đường dẫn: dùng `citation.pdf_path`
  - [x] Hiển thị ảnh trang bằng expander (expanded=True) + nút "Open in new tab"
  - [x] Logging sự kiện View Page

- System Status
  - [x] Đổi kiểm tra sang gọi `/index-stats` + `/healthz`
  - [x] Hiển thị số liệu doc/chunk/dimension

- Confidence Calibration
  - [x] Implement rescale min-max/percentile theo batch kết quả
  - [x] Boost theo `full_page`, `n_citations`, `answer_len`, penalty khi fallback
  - [x] Clamp [0,1], thêm flag `confidence_mode`

- Vision-assisted Verification
  - [ ] Thống nhất cờ `enable_vision_verify` từ UI → API
  - [ ] Từ citations → render ảnh trang bằng `/api/pdf/render-page`
  - [ ] Gọi Vision LLM để xác minh các claim chính
  - [ ] Ghi kết quả vào meta + hiển thị tab Vision Verify
  - [ ] Giới hạn số trang, cache ảnh, flag bật/tắt theo env

- Embedding Visualization
  - [ ] Thiết kế endpoints `/embedding/stats`, `/embedding/sample`
  - [ ] Trang UI demo nhỏ (subset vectors), flag tắt mặc định

- Hardening
  - [ ] Rate limit render-page, cache ảnh ổn định
  - [ ] Ẩn path nội bộ trong UI (nếu cần)


## 11) Câu hỏi mở (cần xác nhận)

- Vision “luôn bật”: Áp dụng cho mọi truy vấn hay chỉ queries có citations? -> chỉ các citations top-N
- DPI ảnh trang bao nhiêu là đủ? -> 200
- Giới hạn số claim cần xác minh mỗi truy vấn? 3 claim trở lênlên
- Có cần bật OCR realtime cho trang ít text? (Đề xuất: chưa, chỉ khi có nhu cầu, sẽ phát triển sau)


## 12) Kết luận

- Các vấn đề được nhận diện rõ nguyên nhân và có kế hoạch xử lý theo phase.
- Ưu tiên triển khai sớm UI Citations và System Status (nhanh, ít rủi ro), tiếp theo Confidence Calibration, rồi Vision-assisted Verification. Embedding Visualization để sau và bật bằng feature flag.
