# Sửa lỗi: Truy vấn tiếng Việt không có trích dẫn (citations) trong RAG

Ngày: 2025-09-21
Người thực hiện: Agent Mode

Mục tiêu: Khắc phục việc truy vấn tiếng Việt (VD: “Áp suất vận hành của KT06101 là bao nhiêu?”) không trả về trích dẫn dù document có chứa câu trả lời, trong khi truy vấn tiếng Anh cùng nội dung lại có citation.

---

1) Triệu chứng

- Khi hỏi tiếng Anh (EN): Hệ thống trả về trả lời ngắn + có citations (VD: Data Sheet for CO2 Compressor Steam Turbine.rev0E.pdf, Page 1)
- Khi hỏi tiếng Việt (VI): Hệ thống trả về câu trả lời chung chung, không có citations; đôi khi context_used rỗng
- Kết quả thử nghiệm qua test_fix_indoc.py cho thấy:
  - EN: Citations count = 1
  - VI: Citations count = 0 (trước khi fix), hoặc nhiều khi answer preview báo lỗi từ LLM và không kèm citations

2) Phân tích nguyên nhân gốc (Root Cause)

Có hai nguyên nhân chính liên quan đến pipeline:

- Reranker cross-encoder gây rỗng kết quả với truy vấn không phải tiếng Anh:
  - Trong Reranker, khi sử dụng cross-encoder cho tiếng Việt, điểm số có thể trở thành NaN hoặc rất thấp. Bước lọc theo score_threshold sau reranking làm rỗng danh sách kết quả.
  - Hệ quả: context_used = [] và generator không có document mapping để trích xuất [Doc X] -> citations, fallback citations theo top reranked docs cũng không có dữ liệu để bám vào.

- Generator sử dụng original query (tiếng Việt) cho prompt trong khi context là tiếng Anh:
  - QueryTransform đã dịch truy vấn VI -> EN để retrieve, nhưng generator lại dùng query.original (tiếng Việt) trong prompt. Điều này làm mô hình khó liên hệ context (EN) với câu hỏi (VI), dẫn đến trả lời chung và không gắn [Doc X].

Ngoài ra có yếu tố vận hành:

- Server từng chạy với uvicorn --reload tạo tiến trình con ngoài venv, gây hành vi không nhất quán (đặc biệt ở các thư viện ML). Chuyển sang chạy một tiến trình ổn định giúp loại bỏ một biến số.

3) Các thay đổi đã thực hiện

3.1. Điều chỉnh lựa chọn phương thức rerank theo ngôn ngữ (tránh cross-encoder cho non-EN)

- File: app/api/routers/ask.py
- Thay vì luôn khởi tạo Reranker() mặc định (cross-encoder), hệ thống sẽ:
  - Nếu request.language == 'en' => dùng method = 'cross_encoder'
  - Ngược lại => dùng method = 'score' (heuristic theo term-match), tránh NaN và giữ nguyên kết quả BM25/FAISS
- Thay đổi quan trọng (trích đoạn):

```python
# Trước
reranker = Reranker()

# Sau
from app.rag.reranker import RerankConfig
rerank_method = 'cross_encoder' if request.language == 'en' else 'score'
reranker = Reranker(config=RerankConfig(method=rerank_method, top_k=request.max_context))
```

Tác dụng: Đảm bảo tiếng Việt vẫn giữ được danh sách kết quả sau retrieval, cho phép fallback citations hoạt động.

3.2. Đồng bộ ngôn ngữ ở bước sinh câu trả lời để trích dẫn đúng

- File: app/rag/generator.py
- Trước đây generator sử dụng query.original (có thể là tiếng Việt) để tạo prompt trong khi context là EN. Đã điều chỉnh để:
  - Dùng query.normalized (đã dịch sang EN trong QueryTransform) để bám khớp nội dung context.
  - Đồng thời thêm phương thức `_generate_ask_answer_bilingual(english_query, original_query, context, ...)` để:
    - Prompt tiếng Anh dựa trên english_query + context EN giúp model tìm đúng thông tin và chèn [Doc X].
    - Nếu language == 'vi', yêu cầu model trả lời bằng tiếng Việt nhưng giữ nguyên định dạng citation [Doc X].
- Thay đổi chính:
  - Thêm generation_query = query.normalized (khi có translated_from)
  - Thêm response_language = query.language
  - Tạo `_generate_ask_answer_bilingual(...)` và dùng cho intent ASK/EXPLAIN/REPORT/DEFAULT để thống nhất hành vi song ngữ

3.3. Bật fallback citations luôn khi có kết quả rerank

- File: app/api/routers/ask.py (đã có sẵn logic fallback)
- Xác nhận nhánh fallback citations: nếu LLM không chèn inline [Doc X], hệ thống sẽ thêm citations dựa trên top reranked_results (tối đa 5), với page mặc định 1 nếu thiếu.
- Việc chuyển rerank non-EN sang “score” đảm bảo reranked_results không rỗng, nên fallback citations hoạt động.

3.4. Cải thiện tiện ích debug và khởi động server

- Scripts tiện ích:
  - test_vietnamese_debug.py: Sửa endpoint /healthz và /ask, dùng execution_mode hợp lệ (light_only), đảm bảo Content-Type UTF-8 khi gửi tiếng Việt.
  - debug_retrieval_vi.py: Script nội bộ kiểm tra QueryTransform(language=vi) và kết quả retriever.search để đối chiếu VI vs EN.
- Khởi động server trong venv, bỏ --reload để tránh tiến trình con dùng Python hệ thống.

4) Kết quả kiểm thử

- test_fix_indoc.py (sau sửa):
  - EN: Citations count = 1, Answer OK
  - VI: Citations count > 0 (fallback citations xuất hiện), Answer không rỗng, context_used có dữ liệu
- Gọi trực tiếp API /ask:
  - VI với language='vi': Nhận được answer tiếng Việt kèm citation (ít nhất từ fallback), context_used có chunk ids.
- debug_retrieval_vi.py:
  - VI và EN sau transform đều có normalized giống nhau (“what operating pressure of kt06101?”), số lượng kết quả retrieval tương đương (khoảng 52), chứng minh bước retrieve hoạt động nhất quán giữa ngôn ngữ.

5) Cách chạy và kiểm thử thủ công

- Khởi động API trong venv (khuyến nghị không dùng --reload để ổn định):
  - Windows PowerShell:
    1. `& "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC/venv/Scripts/Activate.ps1"`
    2. `& "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC/venv/Scripts/python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Kiểm tra health:
  - `GET http://127.0.0.1:8000/healthz`
- Kiểm thử nhanh tiếng Việt (ví dụ PowerShell):
  - Body:
    ```json
    { "query": "Áp suất vận hành của KT06101 là bao nhiêu?", "language": "vi", "hyde": true, "max_context": 5, "execution_mode": "light_only" }
    ```
  - Gọi: `Invoke-WebRequest -Method POST -Uri http://127.0.0.1:8000/ask -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))`

6) Sửa lỗi Gemini API 'NoneType' object is not iterable

- **Vấn đề**: Gemini API trả về response với text=None hoặc không có thuộc tính usage_metadata dẫn đến lỗi iteration
- **Giải pháp đã áp dụng**:
  - File: app/services/llm_client.py
  - Thêm kiểm tra an toàn khi truy cập response.text, response.candidates
  - Thêm try/except khi iterate qua candidates.content.parts
  - Trả về fallback message thay vì crash khi không extract được text
  - Thêm prefix "models/" vào model name khi cần
  - Xử lý an toàn usage_metadata có thể None

7) Rủi ro và giới hạn còn lại

- Cross-encoder rerank cho non-EN đang tắt (dùng “score”). Nếu muốn bật lại, cần:
  - Chọn cross-encoder hỗ trợ đa ngôn ngữ, hoặc
  - Chuẩn hóa pipeline: luôn rerank trên normalized (EN) thay vì original (VI), đồng thời đảm bảo không phát sinh NaN.
- LLM đôi khi trả về lỗi `NoneType is not iterable` từ provider (Gemini) trong các call phụ (HyDE, v.v.). Đã có retry/guard cơ bản; có thể cần bổ sung retry/backoff chắc chắn hơn.
- Generator bilingual: Hiện logic song ngữ áp dụng cho ASK/EXPLAIN/REPORT/DEFAULT; cần tiếp tục tinh chỉnh prompt để tăng tỷ lệ chèn [Doc X] inline thay vì phải dựa vào fallback.

7) Hướng cải tiến tương lai

- Reranker:
  - Bắt NaN an toàn trong cross-encoder, ép về 0.0, tránh loại toàn bộ kết quả.
  - Cho phép chọn rerank bằng EN normalized query cho mọi truy vấn, bất kể language.
- Generator:
  - Tách bạch rõ “query dùng để match context (EN)” và “ngôn ngữ trả lời (EN/VI)”.
  - Cải thiện mẫu prompt để ưu tiên “direct answer” ngắn rõ ràng trước khi vào chi tiết, tăng tỷ lệ inline [Doc X].
- Ops:
  - Chuẩn hóa cách chạy server với venv; nếu cần reload, dùng cơ chế bảo đảm child process vẫn là venv Python.

8) Phạm vi thay đổi mã nguồn

- app/api/routers/ask.py:
  - Cấu hình Reranker theo language để tránh cross-encoder với non-EN và set top_k = request.max_context
- app/rag/generator.py:
  - Dùng query.normalized (EN) cho matching context
  - Thêm `_generate_ask_answer_bilingual(...)`
  - Điều chỉnh gọi generate cho ASK/EXPLAIN/REPORT/DEFAULT sử dụng phiên bản bilingual
- Scripts debug (tiện ích phát hiện và xác nhận):
  - test_vietnamese_debug.py (sửa path endpoint, execution_mode, Content-Type)
  - debug_retrieval_vi.py (mới)

9) Kết luận

Fix tập trung vào việc:
- Giữ lại kết quả retrieval khi truy vấn tiếng Việt bằng cách vô hiệu hóa cross-encoder cho non-EN.
- Đồng bộ ngôn ngữ giữa query (EN normalized) và context ở bước generator để model có thể chèn citation [Doc X].
- Đảm bảo fallback citations luôn hoạt động nhờ có danh sách reranked_results.

Kết quả: Truy vấn tiếng Việt nay đã trả về câu trả lời kèm citations ổn định, thống nhất hơn với truy vấn tiếng Anh.
