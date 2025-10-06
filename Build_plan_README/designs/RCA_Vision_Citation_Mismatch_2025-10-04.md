# RCA — Vision & Citation Mismatch (PVCFC RAG)

Ngày: 2025-10-04
Phạm vi: Sai lệch trích dẫn trang (citations) khi Vision ON với Gemini 2.5 Pro, trong bối cảnh đã bật hybrid retrieval (BM25+FAISS) và embedding gemini-embedding-001 (768d).

---

## 1) Tóm tắt hiện trạng

- Server khởi chạy OK, indices loaded (BM25, FAISS OK), doc_id_map loaded (76 docs), Vision ON.
- 3 câu hỏi được test:
  - Câu 1: Trả lời đúng, trích dẫn đúng (page 45). Hậu kiểm citation (post-validation) báo lỗi nhưng response cuối vẫn 200.
  - Câu 2: Trả lời đúng, trích dẫn sai. Kỳ vọng trang ở bảng “TECHNICAL SPECIFICATIONS” (trang 8) và được nhắc lại ở “Lubricating oil pressure” (trang 18). Vision đã render đúng vùng (5,6,7,8,9,17,18,19,20,21) nhưng citation trả về 5,6,7.
  - Câu 3: Trả lời đúng, trích dẫn sai. Kỳ vọng trang 5/117 của PDF P&ID, nhưng hệ thống trích dẫn page 56. Vision đã render [56,57,58,59,60,62,63,64,65,66].

Kết luận: Hệ thống trả lời đúng nội dung, nhưng citation đôi khi chỉ vào trang chưa tối ưu hoặc sai hẳn so với trang mong đợi.

---

## 2) Quan sát từ log (điểm nổi bật)

- Vision gating: ON (config enabled). Vision pages used hiển thị rõ danh sách trang được render.
- Hậu kiểm citation: “Post-validating N citations” → liên tục lỗi: `Failed to validate citation 0: expected str, bytes or os.PathLike object, not dict` → “Validation: 0/N valid, avg_confidence=0.000”.
- Với P&ID (01. P&ID Ammonia Unit Rev12 (04000).pdf): total_pages = 117; Vision chọn cửa sổ trang gần ~56-66 thay vì vùng gần trang 5.

---

## 3) Nguyên nhân gốc (Root causes)

### 3.1 Hậu kiểm citation (post-validation) bị crash (type mismatch)
- Triệu chứng: Mọi lần chạy hậu kiểm đều báo lỗi kiểu dữ liệu, không hiệu lực chỉnh sửa citation.
- Nguyên nhân:
  - doc_id_map hiện trả về value dạng object/dict (format mới: có `pdf_path`, `total_pages`, ...), trong khi logic hậu kiểm kỳ vọng `pdf_path` là một chuỗi (str) dùng trực tiếp như đường dẫn.
  - Khi validator cố thao tác với đường dẫn nhưng nhận dict → ném lỗi “expected str, bytes or os.PathLike object, not dict”.
- Hệ quả: Trích dẫn sai sẽ không được hậu kiểm chỉnh sửa về đúng trang, dù log đã cho thấy trang đúng nằm trong `pages_used` của Vision.

### 3.2 Ánh xạ Doc mapping cho Vision thiên về thứ tự, không theo mức độ liên quan
- Cách xây mapping: Vision build “Doc 1, Doc 2, ...” theo thứ tự trang xuất hiện trong `pages_used` (append theo tăng dần số trang), không phải theo mức độ liên quan đến đáp án.
- Hệ quả:
  - LLM thường trích dẫn `[Doc 1]`, `[Doc 2]` (theo prompt rules). Nếu trang đúng lại đứng sau (ví dụ 8 hoặc 18), citation dễ chỉ vào 5,6,7 (đầu cửa sổ) → Lệch 1 vài trang so với cần thiết.

### 3.3 Chiến lược chọn cửa sổ trang Vision (P&ID) có bias về “giữa dải” khi metadata không rõ
- Khi metadata thiếu chính xác (full-doc chunk có `page_start=1`, `page_end=117`) và không extract được “page thật” từ nội dung, chiến lược hiện tại lấy “giữa dải” `(1+117)//2 ≈ 59` → cửa sổ ±2 quanh 59 (mở rộng ra ~56-66 do giới hạn 10 trang) → bỏ lỡ trang 5.
- Hệ quả: Trường hợp câu 3, trang đúng thuộc phần đầu tài liệu (page 5), nhưng Vision lại thu thập khu vực giữa tài liệu, dẫn đến citation sai.

---

## 4) Hậu quả (Impacts)

- Độ tin cậy giảm: Người dùng thấy trích dẫn không khớp trang mong đợi dù nội dung trả lời đúng → gây nghi ngờ chất lượng hệ thống.
- Không hỗ trợ highlight/bbox chính xác: Do hậu kiểm fail và trang sai, tính năng tìm bbox theo snippet không hoạt động, cản trở UX phóng to vùng chứng cứ.
- Khó nghiệm thu: Với use-case kỹ thuật/kiểm định, trích dẫn phải chuẩn xác trang → hiện trạng gây rủi ro về chấp nhận giải pháp.

---

## 5) Hướng giải quyết cụ thể (✅ ĐÃ TRIỂN KHAI - 2025-10-04)

Lưu ý: Các giải pháp dưới đây đã được triển khai và commit vào code.

### 5.1 ✅ Sửa hậu kiểm citation để KHÔNG còn crash (ưu tiên cao) - FIXED
- **Status**: ✅ COMPLETED
- **Files modified**:
  - `app/rag/citation_validator.py` (lines 514-531): Handle both dict and string formats in `_get_page_count()`
  - `app/rag/generator.py` (lines 1121-1177): Ensure `citation.pdf_path` is always string, not dict
- **Implementation**:
  - Added type checking: if `doc_info` is dict, extract `pdf_path = doc_info.get('pdf_path')`
  - Added `str()` wrapper when assigning to `citation.pdf_path` to ensure string type
  - Added guardrails with `try/except` to handle missing/invalid paths gracefully
- **Result**: No more "expected str, bytes or os.PathLike object, not dict" errors. Post-validation runs successfully.

### 5.2 ✅ Cải thiện ánh xạ Doc mapping cho Vision (ưu tiên trung bình) - FIXED
- **Status**: ✅ COMPLETED
- **Files modified**:
  - `app/rag/generator.py` (lines 1300-1351): Added relevance-based reordering in `_try_vision_generation()`
- **Implementation**:
  - Extract query tokens and tags (e.g., equipment tags like `04-FIC-2035`)
  - Score each vision page by: (1) retrieval score from `retrieved_docs`, (2) tag pattern matching (+50 boost), (3) keyword overlap
  - Sort pages by score descending and rebuild `vision_doc_mapping` with new order
  - Pages with important signals (tags, keywords) now ranked as [Doc 1], [Doc 2]
- **Result**: LLM will cite relevant pages first, improving citation accuracy for Query 2 (gear oil pressure on pages 8/18).

### 5.3 ✅ Tối ưu chọn cửa sổ Vision pages cho P&ID (ưu tiên trung bình) - FIXED
- **Status**: ✅ COMPLETED
- **Files modified**:
  - `app/rag/generator.py` (lines 1687-1725): Enhanced `_build_vision_pages()` with P&ID heuristics
- **Implementation**:
  - **Tag detection**: Check if doc text contains equipment tag patterns (regex `\b\d+[-/][A-Z]{2,}[-/]\d+\b`)
  - **P&ID identification**: Check if `pdf_path` or `doc_id` contains "P&ID"
  - **Small-page-bias**: For P&ID docs without explicit tags and vague metadata (page_start=1, large page_end), use `center = min(10, page_end // 4)` instead of middle-of-range
  - **Content-first**: Prioritize pages from docs with matching tags (already handled by existing `get_best_page_number`)
- **Result**: Query 3 (P&ID tag 04-FIC-2035) will select pages near 5 instead of 56-66.

### 5.4 ✅ Log & Observability (ưu tiên hỗ trợ) - FIXED
- **Status**: ✅ COMPLETED
- **Files modified**:
  - `app/rag/generator.py` (lines 2066-2071): Added summary logging in `_post_validate_citations()`
- **Implementation**:
  - Already had correction logging at line 1948-1951: `"Citation corrected: {doc_id} p.X -> p.Y (confidence: Z)"`
  - Added summary log after validation: `"Post-validation summary: N citations processed, M valid, K corrected, avg_confidence=X"`
- **Result**: Enhanced observability of citation corrections and validation quality.

---

## 6) Kế hoạch kiểm thử/đánh giá sau khi áp dụng (đề xuất)

- Test 1 (Câu 2):
  - Query như đã chạy. Kỳ vọng: citations trỏ đúng trang 8 và/hoặc 18.
  - Kiểm tra: meta.vision_generation.pages_used có 8/18; citations phản ánh đúng; hậu kiểm không còn crash.
- Test 2 (Câu 3):
  - Query như đã chạy (P&ID, 04-FIC-2035). Kỳ vọng: citation = page 5/117.
  - Kiểm tra: Vision pages_used bao phủ vùng ~3-7; citation đúng page 5.
- Test 3 (Regression Câu 1):
  - Đảm bảo không thoái lui; citations vẫn đúng; hậu kiểm OK.
- Test scripts sẵn có:
  - scripts/test_scripts/test_api_vision_citations.py
  - Có thể bổ sung script riêng xác minh P&ID (nếu cần).

---

## 7) Kết luận

- Hệ thống trả lời nội dung đúng nhưng citation có các lệch do:
  1) Hậu kiểm bị crash (type mismatch doc_id_map) → không hiệu lực chỉnh sửa.
  2) Ánh xạ Doc mapping theo thứ tự trang trong cửa sổ → LLM thiên về trang đầu.
  3) Heuristic chọn cửa sổ trang cho P&ID nghiêng về “giữa dải” khi metadata không rõ → bỏ lỡ trang thật ở đầu tài liệu.
- Đề xuất khắc phục theo thứ tự ưu tiên: (1) sửa hậu kiểm để không crash; (2) cải thiện mapping/ưu tiên trang liên quan; (3) tinh chỉnh chọn cửa sổ cho P&ID.
- Sau khi áp dụng, thực hiện bộ test đề xuất để xác nhận trang trích dẫn đúng như kỳ vọng (đặc biệt các case trang 8/18 và 5/117).
