# Báo cáo hiện trạng hệ thống RAG và phương án xử lý

Ngày: 2025-09-29
Phạm vi: API RAG (FastAPI), UI Streamlit (Query Lab), pipeline embedding (Gemini 768D), chỉ mục BM25/FAISS, PDF renderer

---

## 1) Tóm tắt hiện trạng

- Đã nâng cấp embedding sang Gemini `gemini-embedding-001` với đầu ra 768D (giới hạn tối đa hiện tại).
- Đã build lại FAISS/BM25 cho 27.306 văn bản và đồng bộ index sang D:\PVCFC_DATA (qua Junction `artifacts/index/*`):
  - FAISS: faiss.index ~ 83.9 MB, texts.json ~ 6.9 MB, metadatas.json ~ 10.0 MB.
  - BM25: bm25_index.pkl ~ 5.5 MB, documents.json ~ 6.9 MB, metadata.json ~ 10.0 MB.
- API khởi động tốt, nạp chỉ mục thành công: FAISS dim=768, BM25/FAISS đều sẵn sàng; doc_id_map.json đã nạp (76 entries).
- Query Lab (UI) gọi /ask hoạt động, có trả lời và có citations trong nhiều truy vấn.
- Đã khắc phục lỗi khởi động do `.env` (biến số có comment nội dòng).

Các vấn đề còn tồn tại:
- Một số câu trả lời rỗng/ít thông tin do Gemini trả empty (flash/pro) → generator phải fallback.
- Citations hiển thị trong UI nhưng khi nhấn không mở được trang PDF (UI chưa gọi /api/pdf để render ảnh trang; không thể mở trực tiếp đường dẫn cục bộ D:\...).
- Document Citations: Page luôn = 1, Score hiển thị = 0.000 (metadata hiện tại đều page=1; lệch field score/confidence giữa API và UI).
- Debug Information đôi khi hiển thị “Query was not transformed” (transform bị bỏ qua khi dịch/HyDE lỗi).
- Các toggle “Vision verification”, “Embedding view” là placeholder, chưa có hiệu lực thực tế.

---

## 2) Kết quả tốt đáng ghi nhận

- Hạ tầng embedding + caching + build index ổn định; dung lượng index khớp lý thuyết 27.306 × 768 × 4 bytes.
- Đồng bộ index sang ổ D có backup đầy đủ, xác minh số lượng phần tử khớp 27.306 ở cả FAISS/BM25.
- PDF renderer (/api/pdf/...) đã sẵn sàng (cache khởi tạo OK).

---

## 3) Vấn đề, nguyên nhân gốc và tác động

### 3.1 .env gây lỗi khởi động (đã xử lý)
- Triệu chứng: ValueError khi ép kiểu int (do comment nội dòng). Đã làm sạch `.env` → API chạy bình thường.
- Phòng ngừa: Nên harden loader để tự bỏ comment nội dòng khi set env.

### 3.2 Câu trả lời rỗng/ít thông tin
- Nguyên nhân: Model trả empty (safety/prompt dài), thiếu system_prompt ràng buộc, temp/token chưa tối ưu, transform lỗi.
- Tác động: Chất lượng answer không ổn định; fallback generic.

### 3.3 Citations không mở được PDF
- Nguyên nhân: UI chỉ render bảng; không gọi `/api/pdf/*` để xem trang; không thể mở path cục bộ trực tiếp.
- Tác động: Không truy vết được nguồn nhanh.

### 3.4 Page=1 và Score=0.000
- Nguyên nhân: Metadata lưu `page=1` cho mọi chunk (không propagate page thật); UI đọc trường `score` nhưng API trả `confidence` là chính.
- Tác động: Không nhảy đúng trang; điểm hiển thị vô nghĩa.

### 3.5 “Query was not transformed”
- Nguyên nhân: translate/HyDE lỗi → dùng nguyên bản; chỉ là thông tin debug.

### 3.6 Vision verification / Embedding view
- Hiện là placeholder; chưa tích hợp với /api/pdf hay mô hình thị giác.

---

## 4) Phương án xử lý (kế hoạch từng bước)

Mục tiêu chung:
- Nâng chất lượng câu trả lời và trích dẫn hữu ích.
- Xem nhanh trang PDF ngay trong UI.
- Page/Score hiển thị đúng và có ý nghĩa.
- Ổn định transform để cải thiện retrieval/generation.

Bước 1 — Cải thiện UI Citations (ưu tiên)
- Thêm cột “Xem trang” trong bảng Citations (Query Lab):
  - Với mỗi citation có `pdf_path` và `page`, gọi `/api/pdf/render-page?pdf_path=...&page_num=...` và hiển thị ảnh trang (st.image) trong expander/modal.
  - Nếu chưa có `page`, tạm dùng 1; sau khi sửa metadata (Bước 3) sẽ nhảy đúng trang.
- Hiển thị cả hai: `score` và `confidence` (nếu thiếu `score` thì map từ `confidence`).
- Ép Execution Mode = `production` mặc định cho mọi truy vấn từ UI.
- Ghi chú rõ ràng cho toggle Vision/Embedding (đang phát triển) hoặc ẩn toggle để tránh hiểu nhầm.

Bước 2 — Cải thiện Generator/API
- Thêm `system_prompt` rõ ràng: yêu cầu format trả lời, trích dẫn [Doc X, p.Y], nhấn mạnh dùng thông tin từ context.
- Giảm `temperature` xuống 0.2; tăng `max_answer_length` lên mức tối đa model cho phép (ví dụ theo giới hạn model, không vượt giới hạn API).
- Rút gọn context sau RRF (ví dụ top 3–5) để tránh prompt dài gây empty.
- Đồng bộ trường trong `AskResponse.citations`: trả cả `score` (từ `relevance_score` nếu có) và `confidence`.
- Bổ sung logging khi model trả empty (độ dài prompt, tham số cấu hình) để tối ưu lặp lại.
- Cải thiện transform fallback (dịch/HyDE): có nhánh dự phòng đơn giản khi LLM dịch/HyDE lỗi.

Bước 3 — Sửa metadata `page` và rebuild index
- Sửa pipeline build (FAISS/BM25): khi serialize metadata, đặt `page` theo ưu tiên: `page` → `page_start` → `page_nums[0]` → fallback 1.
- Đảm bảo BM25Indexer/VectorIndexer ghi `page` đúng sang JSON.
- Rebuild cho 27.306 docs; kiểm tra ngẫu nhiên ≥ 50 entries có `page` đúng.
- Đồng bộ sang D:\PVCFC_DATA (backup trước), rồi verify UI: click citation mở đúng trang.

Bước 4 — Harden `.env` loader (start_api.ps1)
- Khi nạp `.env`, loại comment nội dòng sau giá trị số để tránh lỗi parse trong tương lai.

Bước 5 — (Tuỳ chọn) Vision & Embedding view
- Cho phép thumbnail nhanh qua `/api/pdf/thumbnail` ở Citations.
- Để lại thông báo “đang phát triển” cho embedding visualization hoặc ẩn toggle cho rõ ràng.

---

## 5) Tiêu chí nghiệm thu (Acceptance Criteria)

- API `/ask`:
  - ≥ 80% truy vấn có câu trả lời không rỗng, có thông tin, có ≥ 2 citations.
  - `/index-stats` báo FAISS dim=768, vector_count ~ 27.306.
- UI Query Lab:
  - Bảng Citations có nút “Xem trang”, hiển thị đúng trang theo `pdf_path` + `page`.
  - Cột điểm hiển thị `score` (hoặc confidence) > 0 trong phần lớn trường hợp.
  - “Query was not transformed” giảm tần suất nhờ transform fallback ổn định hơn.
- Metadata:
  - Kiểm tra ngẫu nhiên ≥ 50 citations: `page` trong JSON khớp trang thực tế.

---

## 6) Rủi ro & phương án giảm thiểu

- Model tiếp tục trả empty với prompt dài/đặc thù:
  - Rút gọn context, tăng ràng buộc system_prompt, chuẩn bị fallback tuyến hai khi cần.
- PDF không render do quyền truy cập/đường dẫn:
  - Kiểm tra quyền đọc `D:\Data_Raw\...`; nếu triển khai máy khác, cân nhắc proxy hoặc UNC path.
- Rebuild index:
  - Luôn backup trước khi sync; thực hiện ngoài giờ; thêm bước verify sau sync.

---

## 7) Các hành động đã thực hiện

- Làm sạch `.env` để bỏ comment nội dòng cho biến số; khởi động API thành công.
- Đồng bộ index mới sang D:\ (backup trước khi copy) và xác minh số lượng phần tử.
- Xác nhận FAISS 768D, 27.306 văn bản; BM25 khớp số lượng.
- Ghi nhận nguyên nhân các vấn đề (LLM empty, citations UI chưa wiring, page=1 do metadata, score=0 do lệch field, transform skipped...).

---

## 8) Quyết định đã chốt

- Execution Mode mặc định: `production` cho mọi truy vấn UI.
- Hiển thị điểm trong Citations: cả `score` và `confidence`.
- Cách mở PDF: chọn cách đơn giản trước (render ảnh trang inline), linh hoạt thay đổi sau.
- Thứ tự ưu tiên: UI nhanh (Bước 1) → cải thiện generator/API (Bước 2) → sửa metadata & rebuild (Bước 3).
- Thực hiện hardening `.env` loader trong `start_api.ps1`.

---

## 9) Hành động kế tiếp (ngay)

1) Triển khai Bước 1 (UI Citations: nút “Xem trang”, hiển thị score+confidence, ép `production`).
2) Triển khai Bước 2 (generator/API: system_prompt, temp=0.2, max tokens theo giới hạn model, đồng bộ trường citations, logging).
3) Triển khai Bước 3 (sửa pipeline page, rebuild & sync, verify click citation mở đúng trang).
4) Triển khai Bước 4 (.env loader hardening) và cân nhắc Bước 5 (tuỳ chọn thumbnail/ẩn toggle).

---

## 10) Kết luận

Hệ thống đã sẵn sàng chạy end-to-end với index mới và embedding 768D. Các vấn đề còn lại chủ yếu ở trải nghiệm trích dẫn (xem trang PDF) và chất lượng câu trả lời không ổn định do model trả empty. Với các bước ưu tiên từ UI → generator/API → metadata, trải nghiệm người dùng sẽ được cải thiện rõ rệt: trích dẫn xem được ngay trong UI, trang nhảy đúng, điểm số có ý nghĩa, và câu trả lời nhất quán hơn.
