# Hệ thống Logging cho Query Lab UI

Tài liệu này mô tả chi tiết những thay đổi đã triển khai, kiến trúc logging sự kiện cho UI (Streamlit), luồng hoạt động, cấu hình, cách sử dụng, kiểm thử, và các lưu ý bảo mật.

Cập nhật ngày: 2025-09-17

---

## 1) Mục tiêu

- Thu thập đầy đủ sự kiện tương tác của người dùng (nhập liệu, thao tác nút, chỉnh tham số).
- Ghi nhận các request/response tới API (FastAPI backend), đo thời gian và kết quả.
- Theo dõi thay đổi trạng thái và các lỗi với ngữ cảnh đầy đủ.
- Ghi log ra console (terminal) và file JSON Lines để dễ phân tích.
- Cung cấp Debug Console trong UI để xem log theo thời gian thực, lọc và xuất file.
- Ẩn (redact) thông tin nhạy cảm (API key, token, password) trước khi ghi log.

---

## 2) Tổng quan thay đổi trong codebase

Các file mới/tác động:

- Mới: `app/utils/ui_logger.py` — Module logger tổng hợp cho UI.
- Sửa: `streamlit_app/components/query_lab.py` — Tích hợp logging vào Query Lab.
- Mới: `streamlit_app/components/debug_console.py` — Debug Console xem log theo thời gian thực.
- Sửa: `streamlit_app/app.py` — Thêm menu “Debug Console”, phần Settings cho logging, và mini console.
- Mới: `scripts/view_logs.ps1` — Tiện ích PowerShell xem/tail log.
- Mới: `test_logging_system.py` — Kiểm thử hệ thống logging.

Thư mục lưu log: `logs/ui_events/`
- File JSONL theo session: `session_<SESSION_ID>.jsonl`
- File log text: `session_<SESSION_ID>.log`
- File export tổng hợp: `export_<SESSION_ID>_<TIMESTAMP>.json`

---

## 3) Kiến trúc & Logic

### 3.1 Các thành phần chính

- UIEventLogger (app/utils/ui_logger.py)
  - Sinh `session_id` cho mỗi phiên UI.
  - Cho phép tạo `run_id` cho mỗi lần chạy truy vấn (Run).
  - Ghi log:
    - Console (có màu theo mức độ) — tùy chọn.
    - File JSONL — cấu trúc chuẩn hoá theo event.
  - Bộ đệm sự kiện trong RAM (deque, có lock) để Debug Console đọc hiển thị.
  - Redaction — loại bỏ/chuyển hoá thông tin nhạy cảm khỏi payload/headers trước khi ghi log.
  - Theo dõi performance bằng `performance_key` (start/stop và tính duration).

- Query Lab (streamlit_app/components/query_lab.py)
  - Log khi thay đổi API Base URL, test kết nối.
  - Log nhập liệu query, preset, tham số (HyDE, retrieval, reranker, v.v.).
  - Log API request/response tới endpoint `/ask` (thành công/thất bại) và thời gian.
  - Log toàn bộ vòng đời “Run Query” (bắt đầu, thành công, lỗi, thời gian).

- Debug Console (streamlit_app/components/debug_console.py)
  - Hiển thị sự kiện theo thời gian thực (buffer trong RAM của logger).
  - Lọc theo loại sự kiện, mức độ severity, số lượng hiển thị.
  - Các chế độ xem: List (card), Table, Raw JSON.
  - Tìm kiếm theo từ khoá trong message/data.
  - Xuất log (export) và hiển thị thống kê session.

- Main App (streamlit_app/app.py)
  - Thêm mục điều hướng “🐛 Debug Console”.
  - Sidebar “Debug Settings”: bật/tắt Verbose Logging; hiện Mini Console.
  - Mini Console: hiển thị 5 sự kiện gần nhất ở cuối trang.

- PowerShell Viewer (scripts/view_logs.ps1)
  - Xem nhanh các sự kiện gần nhất theo session.
  - Tail theo thời gian thực (`-Tail`).
  - Mở thư mục log (`-OpenDir`).

### 3.2 Mô hình Event

- EventType: `user_input`, `button_click`, `state_change`, `api_request`, `api_response`, `error`, `warning`, `info`, `debug`, `performance`, `system`.
- EventSeverity (map sang logging level): `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

Cấu trúc một event (JSONL):
```json
{
  "timestamp": "2025-09-17T01:56:48.529413",
  "session_id": "20250917_015648_257128b0",
  "run_id": "run_1_436d22",
  "event_type": "api_response",
  "severity": 20,
  "severity_name": "INFO",
  "message": "API response from /ask: 200",
  "data": {
    "endpoint": "/ask",
    "status_code": 200,
    "response": { "answer": "..." },
    "success": true,
    "elapsed_time_seconds": 1.234
  },
  "performance": {
    "key": "api_request_/ask",
    "duration_seconds": 1.234
  }
}
```

### 3.3 Redaction (ẩn thông tin nhạy cảm)

Các pattern được xử lý (case-insensitive nơi phù hợp):
- `sk-...` → `API_KEY_REDACTED`
- `Authorization: Bearer ...` → `Bearer TOKEN_REDACTED`
- `api_key: <value>` → `API_KEY_REDACTED`
- `token: <value>` → `TOKEN_REDACTED`
- `password: <value>` → `PASSWORD_REDACTED`
- `secret: <value>` → `SECRET_REDACTED`
- Chuỗi dài 40+ ký tự chữ/số → `LONG_KEY_REDACTED`

Lưu ý: Redaction chạy trên string/dict/list; hãy luôn đưa payload/headers/raw string đối tượng vào logger để được xử lý an toàn.

---

## 4) Tích hợp chi tiết

### 4.1 Query Lab

- Khởi tạo logger ở đầu hàm `render()` với tuỳ chọn `verbose` đọc từ `st.session_state.enable_verbose_logging`.
- Ghi log thay đổi API Base URL (state_change) và “Test Connection” (button + info/warning/error).
- Ghi log nhập liệu query (`text_area`), preset button, HyDE settings (`checkbox`, `number_input`).
- Khi bấm “Run Query”:
  - Tạo `run_id` mới (`logger.start_new_run()`).
  - Ghi event bắt đầu run (performance start: `query_execution`).
  - Gọi API `/ask` qua `call_ask_api()` có bọc log request/response.
  - Thành công: log kết thúc run (performance stop) + meta (latency, answer length, citations, confidence).
  - Thất bại: log error với context (run_id, message lỗi).

### 4.2 Debug Console

- Điều khiển: số lượng sự kiện, lọc loại, mức độ severity, auto-refresh.
- Actions: Refresh, Show Stats, Export Logs, Clear Console.
- Tabs: List View (card + expander data), Table View, Raw JSON.
- Mini Console: hiển thị 5 sự kiện gần nhất (màu theo severity, có icon theo event type).

---

## 5) Cách sử dụng

### 5.1 Chạy UI

- Chạy Streamlit app (ví dụ port 8501):
  ```powershell
  python -m streamlit run streamlit_app/app.py --server.port 8501
  ```
- Mở trình duyệt: `http://localhost:8501`
- Vào “🔧 Debug Settings” trong sidebar để bật “Verbose Logging” nếu cần.
- Điều hướng tới “🐛 Debug Console” để xem log.

### 5.2 Xem log bằng PowerShell

- Xem N bản ghi gần nhất của session mới nhất:
  ```powershell
  .\scripts\view_logs.ps1 -Last 50
  ```
- Tail theo thời gian thực:
  ```powershell
  .\scripts\view_logs.ps1 -Tail
  ```
- Mở thư mục log:
  ```powershell
  .\scripts\view_logs.ps1 -OpenDir
  ```

### 5.3 Xuất log trong UI

- Vào “🐛 Debug Console” → bấm “💾 Export Logs” → file export được lưu tại `logs/ui_events/export_<SESSION_ID>_<TIMESTAMP>.json`.

---

## 6) Kiểm thử đã thực hiện

- Script: `test_logging_system.py`
  - Khởi tạo logger (verbose) → OK.
  - Tạo run → OK.
  - Log các loại event (user_input, button, api_request, api_response, state_change, warning, error) → OK.
  - Thống kê session (số event, errors, warnings, breakdown theo event type) → OK.
  - Kiểm tra redaction nhạy cảm (`sk-...`, Bearer token, v.v.) → OK.
  - Export session → OK.
  - Tạo đầy đủ file JSONL/log/export trong `logs/ui_events/` → OK.

- PowerShell viewer: `scripts/view_logs.ps1 -Last 10` → hiển thị đúng bảng và thống kê session.

---

## 7) Cấu hình & Mở rộng

- Verbose logging: `st.session_state.enable_verbose_logging` (bật/tắt trong UI).
- Redaction patterns: sửa/điều chỉnh trong `UIEventLogger.sensitive_patterns`.
- Tạo event type mới: thêm vào `EventType` và dùng `logger.log_event()` với `event_type` mới.
- Thêm điểm log mới trong UI: gọi `log_streamlit_widget()` cho widget tương ứng hoặc trực tiếp dùng `logger.log_*()`.
- Tách file log theo dung lượng/ngày: hiện tại dùng JSONL theo session; có thể bổ sung file rotation nếu cần.

---

## 8) Lưu ý bảo mật

- TUYỆT ĐỐI không ghi thẳng secret vào command/output.
- Logger đã mặc định ẩn các thông tin nhạy cảm thường gặp (API key/token/password/secret, Bearer token, chuỗi dài 40+).
- Khi thêm trường mới vào payload/headers, luôn đảm bảo không chứa secret dạng raw.

---

## 9) Checklist xác minh

- [x] `logs/ui_events/` được tạo, có `session_*.jsonl`, `session_*.log`.
- [x] Debug Console hiển thị sự kiện theo thời gian thực, có lọc/tìm kiếm.
- [x] `Run Query` có log bắt đầu/kết thúc và đo thời gian.
- [x] API request/response được log kèm status và preview nội dung.
- [x] Redaction hoạt động với `sk-...`, Bearer token, password, secret.
- [x] Export logs hoạt động, file export tạo thành công.

---

## 10) Hạn chế & hướng phát triển

- Chưa có cơ chế rotate file theo dung lượng/ngày (hiện log theo session). Có thể tích hợp `RotatingFileHandler`.
- Redaction dựa trên regex phổ biến; hãy bổ sung pattern đặc thù nếu hệ thống có dạng secret khác.
- Có thể ghi thêm trace_id để liên kết với phía backend nếu cần correlation end-to-end.
- Mở rộng log sang các component UI khác (annotation, evaluation) theo pattern tương tự.

---

## 11) Tài liệu tham khảo nhanh API Logger

- Khởi tạo: `logger = get_logger(verbose=False)`
- Sự kiện người dùng: `logger.log_user_input(field, value, metadata)`
- Click nút: `logger.log_button_click(name, metadata)`
- Request API: `logger.log_api_request(endpoint, method, payload, headers)`
- Response API: `logger.log_api_response(endpoint, status_code, response_data, elapsed_time)`
- Lỗi: `logger.log_error(message, exception, context)`
- Thay đổi trạng thái: `logger.log_state_change(key, old, new)`
- Performance: dùng `performance_key` trong `log_event()` (gọi 2 lần để start/stop)
- Export: `logger.export_session_logs()`

---

Hệ thống logging hiện đã được tích hợp hoàn chỉnh, sẵn sàng hỗ trợ debug và truy vết toàn bộ tương tác trong Query Lab.
