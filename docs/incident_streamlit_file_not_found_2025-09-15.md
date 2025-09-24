# Báo cáo sự cố: Streamlit "File does not exist" khi chạy test_rag_demo.py

Ngày: 2025-09-15
Môi trường: Windows, PowerShell 5.1
Thư mục làm việc khi gặp lỗi: `C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\streamlit_app\streamlit_app`

## 1) Bối cảnh
- Mục tiêu: khởi chạy trang kiểm thử (mock) của RAG demo bằng Streamlit để xác nhận môi trường UI hoạt động ổn.
- Ứng dụng Streamlit nằm trong thư mục `streamlit_app`. Một số entrypoint liên quan:
  - `streamlit_app/test_rag_demo.py` (trang test, trả dữ liệu giả lập)
  - `streamlit_app/app_stable.py` (app ổn định, có nhiều trang, ưu tiên dùng)
  - `streamlit_app/app.py` (app đầy đủ, cần đủ dependency)
  - `streamlit_app/run_demo.py` (trình khởi chạy có kiểm tra dependency)

## 2) Triệu chứng
Chạy lệnh trong thư mục `streamlit_app/streamlit_app`:
```bash
streamlit run test_rag_demo.py
```
Kết quả: Streamlit báo lỗi không tìm thấy file
```
Error: Invalid value: File does not exist: test_rag_demo.py
```

## 3) Phân tích nguyên nhân
- File `test_rag_demo.py` không nằm trong thư mục hiện tại (`streamlit_app/streamlit_app`) mà nằm ở thư mục cha: `C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\streamlit_app`.
- Kiểm chứng bằng lệnh liệt kê ở thư mục cha cho thấy các file `.py` (trong đó có `test_rag_demo.py`) nằm trực tiếp dưới `streamlit_app`:
```
app.py, app_stable.py, debug_app.py, run_demo.py, run_safe.py, test_rag_demo.py, components/...
```

## 4) Cách khắc phục
Có hai cách tương đương:
- Giữ nguyên thư mục hiện tại và chạy theo đường dẫn tương đối lên một cấp:
```bash
streamlit run ../test_rag_demo.py
```
- Hoặc chuyển lên thư mục cha rồi chạy:
```bash
cd ..
streamlit run test_rag_demo.py
```

Sau khi thực hiện, Streamlit đã khởi chạy và mở ứng dụng tại `http://localhost:8501`.

## 5) Kết quả xác minh
- Giao diện hiển thị trang "Test RAG Demo".
- Nhấn nút Generate Answer sau khi nhập câu hỏi sẽ hiển thị thông báo "Query processed successfully!" cùng câu trả lời và các số liệu mô phỏng.
- Nút "Test Counter" tăng giá trị như mong đợi, xác nhận `session_state` hoạt động.
- Kết luận: môi trường Streamlit hoạt động đúng. Lưu ý đây là trang test (mock), không kết nối RAG backend thực.

## 6) Cảnh báo cấu hình Streamlit ghi nhận và khuyến nghị
Khi khởi chạy có các cảnh báo cấu hình:
- Các khóa cũ không còn hợp lệ: `server.gatherUsageStats`, `client.caching`, `client.displayEnabled`.
- Xung đột giữa `server.enableCORS=false` và `server.enableXsrfProtection=true` (Streamlit tự override CORS thành `true`).

Khuyến nghị cập nhật file cấu hình tại:
`%USERPROFILE%\.streamlit\config.toml`
- Loại bỏ (hoặc comment) các khóa đã lỗi thời nêu trên.
- Tránh đặt `server.enableCORS=false` khi `server.enableXsrfProtection=true`. Nếu không có nhu cầu CORS đặc biệt, giữ mặc định:
```
[server]
enableCORS = true
enableXsrfProtection = true
```

## 7) Tài liệu tham chiếu nhanh các entrypoint chạy app
- Chạy trang test (mock):
```bash
streamlit run ../test_rag_demo.py
```
- Chạy app ổn định nhiều trang (khuyến nghị):
```bash
streamlit run ../app_stable.py
```
- Chạy app đầy đủ (cần đủ dependency):
```bash
streamlit run ../app.py
```
- Dùng trình khởi chạy có kiểm tra dependency:
```bash
python ../run_demo.py
```

## 8) Nhật ký thao tác chính đã thực hiện
- Liệt kê file trong thư mục hiện tại và thư mục cha để xác định vị trí thật của `test_rag_demo.py`.
- Chạy `streamlit run ../test_rag_demo.py` để xác nhận khắc phục lỗi đường dẫn.
- Mở mã nguồn các file liên quan để xác nhận `test_rag_demo.py` là trang mock.
- Tư vấn chỉnh sửa `config.toml` để loại bỏ cảnh báo cấu hình.

## 9) Bước tiếp theo đề xuất
1. Chuẩn hóa file cấu hình Streamlit như mục 6 để loại bỏ cảnh báo khi chạy.
2. Sử dụng `app_stable.py` cho luồng demo ổn định. Khi cần đầy đủ tính năng thì chuyển sang `app.py` sau khi cài đủ dependency.
3. Tùy chọn: tạo script tiện ích cho Windows (ví dụ `run_app.ps1`) để chạy nhanh các chế độ trên bằng menu.
