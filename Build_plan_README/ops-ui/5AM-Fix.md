# 5AM-Fix — Kế hoạch đồng bộ Debug UI với API (loại trừ bài toán “trích dẫn sai trang”)

Ngày cập nhật: 2025-10-03
Phạm vi: Sửa lỗi hiển thị các tab Retrieval, Rerank, Generation, Vision Verify và điều chỉnh Citations (Enhanced) theo đúng schema response hiện tại của API. Bài toán tối ưu “trích dẫn đúng trang” sẽ tách riêng sang một RFC khác.

---

## 1) Bối cảnh & Triệu chứng

Khi chạy Query Lab (biến thể Improved – có tab “📌 Citations (Enhanced)”), giao diện hiển thị:
- Timeline/Performance vẫn có dữ liệu (đọc từ `meta.breakdown`),
- Nhưng các tab sau bị trống hoặc báo “disabled”:
  - Retrieval Results (trống),
  - Reranking Details (trống),
  - Generation Details (trống/Unknown),
  - Vision Verify (bị báo tắt).
- Ở tab Citations (Enhanced), cột Score luôn 0.000 trong khi Confidence có giá trị (ví dụ 1.000).

Logs API cho thấy pipeline vẫn hoạt động đầy đủ (retrieve, rerank, generate, vision render) và server trả về metadata tương ứng. Do đó, lỗi nằm ở UI/adapter.

---

## 2) Nguyên nhân gốc (Root Cause)

1) Sai lệch schema giữa UI và API
- UI (streamlit_app/components/query_lab_improved.py) đang đọc dữ liệu theo các khóa:
  - `meta.retrieval.*`, `meta.rerank.*`, `meta.generation.*`.
- API (/app/api/routers/ask.py) trả về dữ liệu chi tiết ở TOP-LEVEL:
  - `retrieval_details`, `reranking_details`, `generation_details`,
  - còn trong `meta` chỉ có: `breakdown`, `model_generation`, `vision_generation`, các flag/metrics khác.
=> UI không tìm thấy dữ liệu nên các tab rỗng.

2) Vision Verify kiểm tra sai cờ & sai key
- UI đang kiểm tra `st.session_state.enable_vision_verify` và đọc `meta.vision_verify`.
- API thực tế dùng:
  - `generation_details.vision_enabled` (cờ runtime),
  - `meta.vision_generation` (pages_used/pages_failed...).
=> UI kết luận nhầm là “disabled”.

3) Citations (Enhanced) – Score vs Confidence
- API citations không có trường `score`; thay vào đó có `confidence` (được clamp từ score/relevance bên trong), và có `pdf_path`.
- UI hiển thị `Score` từ `cit.get('score', 0)` => mặc định 0.000, gây hiểu lầm.

4) Không thuộc phạm vi: “trích dẫn sai trang”
- Vision page selector hiện dùng heuristic theo khoảng trang, không lọc “trang bìa/ít nội dung”. Vấn đề này sẽ xử lý trong một RFC tối ưu riêng (không can thiệp ở Fix 5AM để tránh mở rộng phạm vi).

---

## 3) Mục tiêu của Fix 5AM

- Đồng bộ UI với schema response hiện tại của API, không thay đổi contract của backend.
- Khi có dữ liệu ở `retrieval_details/reranking_details/generation_details/meta.vision_generation`, UI phải hiển thị đầy đủ.
- Vision Verify phản ánh đúng trạng thái nếu `generation_details.vision_enabled=True` hoặc có `meta.vision_generation`.
- Citations (Enhanced) hiển thị hợp lý: Score là optional; nếu không có `score` thì ẩn/ghi “N/A”, Confidence ưu tiên hiển thị.
- Giữ tương thích ngược: nếu sau này backend bổ sung thêm alias trong meta, UI vẫn hoạt động.

---

## 4) Giải pháp kiến trúc (nhỏ gọn, ít rủi ro)

Tại UI (query_lab_improved.py) bổ sung một lớp “adapter” hợp nhất dữ liệu response về dạng thống nhất cho render:

Pseudo-code adapter:
```python
ui = {}

# Retrieval
ret = results.get("retrieval_details") or {}
ui["retrieval"] = {
    "bm25": ret.get("bm25", []),
    "faiss": ret.get("faiss", []),
    # Có thể thêm các tổng hợp khác nếu cần.
}

# Rerank
rr = results.get("reranking_details") or {}
ui["rerank"] = {
    "method": rr.get("method", "unknown"),
    "results": rr.get("results", []),
    "input_count": rr.get("input_count", 0),
    "output_count": rr.get("output_count", 0),
}

# Generation
meta = results.get("meta", {})
gen = results.get("generation_details") or {}
ui["generation"] = {
    "model": gen.get("model") or meta.get("model_generation", "Unknown"),
    "latency_ms": (meta.get("breakdown", {}) or {}).get("generate_ms", 0),
    "total_tokens": gen.get("total_tokens", 0),  # optional
    "estimated_cost": gen.get("estimated_cost", 0),  # optional
    "prompt_info": gen.get("prompt_info", {}),  # optional
}

# Vision
vision_meta = meta.get("vision_generation", {})
vision_enabled = gen.get("vision_enabled", False)
ui["vision"] = {
    "enabled": bool(vision_meta) or bool(vision_enabled),
    "pages_used": vision_meta.get("pages_used", []),
    "pages_failed": vision_meta.get("pages_failed", []),
}

# Citations helpers
# Khi render, Score là optional; Confidence ưu tiên.
```

Sau đó, các tab dùng `ui["retrieval"]`, `ui["rerank"]`, `ui["generation"]`, `ui["vision"]` thay vì truy cập trực tiếp `meta.retrieval/...` hoặc `meta.vision_verify`.

---

## 5) Các thay đổi cụ thể (UI)

1) Retrieval tab
- Thay đọc `meta.get("retrieval", {})` thành đọc từ adapter `ui["retrieval"]`:
  - BM25: `ui["retrieval"]["bm25"]`
  - FAISS: `ui["retrieval"]["faiss"]`
- Nếu cần hiển thị “Fused results”, có thể lấy top `reranking_details["results"]` như “kết quả hợp nhất sau rerank” (nhất quán pipeline thực tế).

2) Rerank tab
- Đọc từ `ui["rerank"]`:
  - method, input_count, output_count, và bảng `results` (Top N) với các cột doc_id, page, score, preview.

3) Generation tab
- Đọc từ `ui["generation"]`:
  - model: ưu tiên `generation_details.model`, fallback `meta.model_generation`.
  - latency: từ `meta.breakdown.generate_ms`.
  - tokens/cost/prompt_info: hiển thị nếu có, nếu không thì “N/A”/0.

4) Vision Verify tab
- Bỏ kiểm tra `st.session_state.enable_vision_verify` và `meta.vision_verify`.
- Dùng:
  - `vision_enabled = generation_details.vision_enabled`,
  - `vision_meta = meta.vision_generation`.
- Khi `vision_enabled` hoặc `vision_meta` có dữ liệu, hiển thị:
  - PDF Pages Used (len(pages_used)), Pages Failed, Success Rate = used/(used+failed), và list trang.
- Nếu không, thông báo:
  - Nếu `st.session_state.enable_vision` là True: “Vision bật nhưng query này không sử dụng Vision (chỉ dùng text).”
  - Nếu False: “Vision đang tắt trong sidebar.”

5) Citations (Enhanced)
- Điều chỉnh formatter:
  - Score: chỉ hiển thị nếu `cit.get('score')` tồn tại; nếu không, hiển thị “N/A”.
  - Confidence: `cit.get('confidence')` hoặc fallback `cit.get('relevance_score')`.
- Giữ nút “👁️ View Page” đọc `pdf_path` như hiện tại.

6) Tương thích ngược
- Với các biến thể UI khác (query_lab.py) logic đã được sửa gần đúng; adapter giúp đồng nhất cách truy cập dữ liệu và giảm rủi ro đứt gãy khi đổi schema.

---

## 6) Không thay đổi Backend trong Fix 5AM

- Không sửa /ask schema. Tránh rủi ro và không mở rộng phạm vi.
- (Tuỳ chọn tương lai) Có thể bổ sung alias trong `meta` (ví dụ `meta.retrieval`, `meta.rerank`, `meta.generation`) nếu muốn đồng bộ toàn hệ sinh thái UI cũ, nhưng KHÔNG cần cho Fix 5AM.

---

## 7) Kế hoạch kiểm thử (Test Plan)

Use-case: câu hỏi có vision pages (log đã xác nhận render 10 trang) và có retrieval/rerank.

- Retrieval tab
  - Kỳ vọng: Hiển thị số lượng BM25/FAISS > 0 (theo `retrieval_details`), hiển thị vài dòng top với score.
- Rerank tab
  - Kỳ vọng: “Method: score|cross_encoder”, Input/Output có số > 0, bảng Top N có doc_id/page/score.
- Generation tab
  - Kỳ vọng: Model ≠ Unknown (lấy từ `generation_details.model` hoặc `meta.model_generation`), Latency khớp `meta.breakdown.generate_ms`.
- Vision Verify tab
  - Kỳ vọng: Nếu log có “Vision pages: used>0”, tab hiển thị “Vision Generation Used” với số trang và danh sách trang; không còn cảnh báo “disabled”.
- Citations (Enhanced)
  - Kỳ vọng: Cột Score hiển thị “N/A” nếu thiếu trường `score`, Confidence hiển thị giá trị.

Regression
- Timeline/Performance không đổi.
- Raw Data tab vẫn hiển thị payload gốc để so chiếu.

---

## 8) Tiêu chí chấp nhận (Acceptance Criteria)

- Không còn tab Retrieval/Rerank/Generation rỗng khi API có dữ liệu tương ứng.
- Vision Verify hiển thị trạng thái dùng/không dùng chính xác, không sai cờ.
- Citations (Enhanced) không còn gây hiểu lầm về `Score` (hiển thị N/A nếu không có), ưu tiên Confidence.
- Không phát sinh lỗi mới ở các biến thể UI khác.

---

## 9) Ước lượng effort & trình tự triển khai

- Phát triển & review: 1.0–1.5 giờ
  1) Thêm adapter hợp nhất response (query_lab_improved.py) – 10–15 phút
  2) Sửa các tab sử dụng adapter – 20–30 phút
  3) Điều chỉnh Citations (Enhanced) – 10 phút
  4) Kiểm thử thủ công end-to-end – 20–30 phút
- Rollback: Chỉ cần revert file query_lab_improved.py (1 commit).

---

## 10) Phụ lục A — Bảng ánh xạ khóa dữ liệu

| UI (mới – dùng adapter)        | API hiện tại                          |
|---------------------------------|----------------------------------------|
| ui.retrieval.bm25               | results.retrieval_details.bm25         |
| ui.retrieval.faiss              | results.retrieval_details.faiss        |
| ui.rerank.method                | results.reranking_details.method       |
| ui.rerank.results               | results.reranking_details.results      |
| ui.generation.model             | results.generation_details.model OR meta.model_generation |
| ui.generation.latency_ms        | meta.breakdown.generate_ms             |
| ui.vision.enabled               | generation_details.vision_enabled OR meta.vision_generation |
| ui.vision.pages_used/failed     | meta.vision_generation.pages_used/failed |
| citations.confidence            | citations[].confidence (API)           |
| citations.score (optional)      | citations[].score (không phải lúc nào cũng có) |

---

## 11) Phụ lục B — Định hướng tối ưu “trích dẫn đúng trang” (Out-of-Scope cho Fix 5AM)

Sẽ có RFC riêng, nhưng định hướng:
- Lọc “trang bìa/ít nội dung”: dựa vào tỉ lệ vùng trắng, số ký tự OCR, hoặc mật độ vector OCR.
- Ưu tiên trang có cue từ khóa: áp dụng scoring dựa trên n-gram/term trong câu hỏi và ngữ cảnh text.
- Ràng buộc trích dẫn: Khi LLM trích dẫn, bắt buộc phải nằm trong tập trang đã render (vision_doc_mapping) và có mức tin cậy tối thiểu.
- Hỗ trợ backoff: nếu vision không khớp, rơi về text-only nhưng đánh dấu cảnh báo UI.

Tài liệu này chỉ mô tả Fix 5AM (đồng bộ UI–API) để khôi phục khả năng debug nhanh; phần tối ưu trích dẫn sẽ triển khai sau để tránh rủi ro mở rộng phạm vi.
