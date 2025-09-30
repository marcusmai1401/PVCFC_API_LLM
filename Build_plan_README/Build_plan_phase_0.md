# PHASE 0 — NỀN TẢNG & KHỞI TẠO (FOUNDATION)

Tài liệu pha 0 cho PVCFC RAG (V1). Mục tiêu: thiết lập skeleton hạ tầng dịch vụ API, chuẩn hoá cấu hình, logging, kiểm tra sức khoẻ, Docker skeleton, và các lệnh tiện ích để đội ngũ có thể “clone → chạy ngay” trong <10 phút.

---

## 1) Mục tiêu & Kết quả mong đợi

- Khởi tạo ứng dụng FastAPI tối thiểu, có `/healthz` trả 200.
- Chuẩn hoá `.env` (pydantic-settings), logging (Loguru), cấu trúc thư mục, Makefile, Docker skeleton.
- Tương thích với README và BUILD_PLAN.md; không xung đột các quyết định V1 (RAM ≤ 12 GB, citations 1-based, Vision ưu tiên, embedding duy nhất ở pha sau…).
- Ai cũng có thể: `make dev → make run → curl /healthz` thấy JSON tình trạng.

---

## 2) Phạm vi (Scope) & Không phạm vi (Out of Scope)

- Có (Phase 0):
  - Cấu trúc repo, ứng dụng FastAPI cơ bản, `/healthz`, logging chuẩn.
  - `.env.example` và Settings (pydantic-settings).
  - Makefile: dev, run, test, lint, smoke (tối thiểu).
  - Dockerfile skeleton (python:3.11-slim), non-root.
- Không (chuyển các pha sau):
  - Ingest/index (Phase 1), Hybrid retrieval/rerank/generation/vision (Phase 2), Evaluation/UI (Phase 3), tối ưu & bảo mật nâng cao (Phase 4).

---

## 3) Công nghệ & Nguyên tắc

- Ngôn ngữ & Runtime: Python 3.11.
- API: FastAPI + Uvicorn.
- Cấu hình: `pydantic-settings` (đọc `.env`), giữ tên ENV tương thích README/BUILD_PLAN.
- Logging: Loguru (mask secrets, format nhất quán; hạn chế log snippet dài chứa dữ liệu nhạy cảm).
- Test: pytest (tối thiểu cho `/healthz`).
- Docker: python:3.11-slim; non-root; expose 8000; entrypoint uvicorn.
- Không đưa logic ingest/retrieval/vision vào Phase 0.

---

## 4) Cấu trúc thư mục khởi tạo (đồng bộ repo hiện tại)

```
app/
  api/
    routers/
      health.py              # /healthz
      # (ask.py, locate.py, report.py ở pha sau)
  core/
    config.py               # pydantic-settings (Settings)
    logging.py              # setup Loguru
  main.py                   # create_app(), lifespan, include routers

tests/
  test_health.py            # test /healthz trả 200

.env.example                # mẫu cấu hình Phase 0
Makefile                    # dev, run, test, lint, smoke
Dockerfile                  # skeleton
README.md                   # Quickstart
BUILD_PLAN.md               # kế hoạch hợp nhất (V1)
```

Ghi chú: Cấu trúc có thể mở rộng thêm `core/metrics.py`, `core/rate_limit.py`, `core/tracing.py` ở pha sau; Phase 0 chỉ cần tối thiểu.

---

## 5) Cấu hình & .env (pydantic-settings)

- Mục tiêu: `.env` thân thiện, có default an toàn; thiếu key không làm app sập.
- Biến bắt buộc (tối thiểu cho Phase 0):
  - `APP_ENV=local|dev|prod (default local)`
  - `API_PORT=8000` (có thể đổi)
  - `LOG_LEVEL=INFO` (DEBUG/INFO/WARNING/ERROR)
- Biến tuỳ chọn (để sẵn cho pha sau, không yêu cầu ở Phase 0):
  - `LLM_MODEL_HEAVY`, `LLM_MODEL_LIGHT`
  - `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`

Ví dụ `.env.example` (Phase 0):

```ini
APP_ENV=local
API_PORT=8000
LOG_LEVEL=INFO

# Để sẵn cho pha sau (không bắt buộc ở Phase 0)
LLM_MODEL_HEAVY=gemini-2.5-pro
LLM_MODEL_LIGHT=gemini-2.5-flash
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
```

Nguyên tắc secrets: không commit `.env`; mask Authorization/api_key trong log.

---

## 6) Health endpoint `/healthz`

- Trả JSON gồm: `status`, `app_env`, `version`, `commit_sha`, `uptime_sec` (ước tính), `llm_provider_ready?` (tuỳ chọn; Phase 0 có thể luôn `false`).
- Code gợi ý: dùng `lifespan` để đánh dấu `start_time`; tính uptime từ `start_time`.

Ví dụ response:

```json
{
  "status": "ok",
  "app_env": "local",
  "version": "0.1.0-dev",
  "commit_sha": "abcdef12",
  "uptime_sec": 123,
  "llm_provider_ready": false
}
```

---

## 7) Logging (Loguru)

- Yêu cầu: format đồng nhất; không lộ secrets; log mức INFO mặc định; DEBUG bật khi `APP_ENV=local`.
- Middleware log request/response tối thiểu: method, path, latency; mask header Authorization.
- Ghi chú: Không log nội dung prompt/data nhạy cảm ở Phase 0.

---

## 8) Makefile (tiện ích)

Gợi ý mục tiêu:

```
make dev        # tạo venv, cài requirements
make run        # uvicorn app.main:app --host 127.0.0.1 --port $(API_PORT)
make test       # pytest -q
make lint       # ruff/flake8 (tùy chọn) + mypy nếu dùng
make smoke      # gọi nhanh /healthz (smoke)
```

Lưu ý Windows PowerShell: có thể dùng script `.ps1` hoặc gọi trực tiếp các lệnh tương đương.

---

## 9) Docker skeleton

- Dockerfile (gợi ý): python:3.11-slim; copy requirements → install → copy app; tạo user non-root; expose 8000; entrypoint uvicorn.
- Liveness/readiness: ở pha sau có thể trỏ `/healthz`.

Ví dụ run:

```powershell
docker build -t pvcfc-rag:phase0 .
docker run -p 8000:8000 --rm pvcfc-rag:phase0
```

---

## 10) Kiểm thử & Kiểm tra thủ công

- Unit test: `tests/test_health.py` → assert `/healthz` 200 + fields cơ bản.
- Smoke test: `curl http://127.0.0.1:8000/healthz` → xem JSON.
- Kiểm tra log: có `Startup completed`, `PVCFC RAG API starting...`, không lộ secrets.

---

## 11) Định nghĩa Hoàn thành (DoD)

- `/healthz` trả 200 với JSON: `status`, `app_env`, `version`, `commit_sha`, `uptime_sec`.
- `.env.example` đầy đủ tối thiểu; thiếu key không làm app crash.
- Logging chuẩn, mask secrets; middleware log latency theo route.
- Makefile và Dockerfile chạy được trên máy mới clone.
- README Quickstart giúp người mới chạy được trong <10 phút.

---

## 12) Rủi ro & Ứng phó

- Sai khác môi trường (Windows/macOS/Linux): hướng dẫn PowerShell; khuyến nghị Docker.
- Thư viện hệ điều hành (OCR/Tesseract) chưa cần ở Phase 0 (ghi chú ở README, sẽ dùng ở Phase 1).
- Nhầm lẫn secrets: `.gitignore` chặn `.env`; pre-commit (tuỳ chọn) bật detect-private-key.

---

## 13) Quickstart (Windows PowerShell)

```powershell
# 1) Tạo và kích hoạt virtualenv
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Cài dependencies
pip install -r requirements.txt

# 3) Tạo .env
Copy-Item .env.example .env

# 4) Chạy API
python app\main.py
# hoặc
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 5) Kiểm tra
Invoke-WebRequest http://127.0.0.1:8000/healthz | Select-Object -Expand Content
```

---

## 14) Ghi chú tương thích README & BUILD_PLAN

- Phase 0 không chứa ingest/index/retrieval/vision. Các quyết định V1 (Vision ưu tiên, citations 1-based, embedding duy nhất, RAM ≤ 12 GB) được thực thi từ Phase 1–2.
- Tiers (heavy/light) chỉ dùng nội bộ để routing trong Phase 2; Phase 0 chỉ khai báo ENV để sẵn sàng.

---

## 15) Phụ lục (tuỳ chọn)

### 15.1 Pre-commit (khuyến nghị)

- Cài `pre-commit` và bật hooks cơ bản: trailing-whitespace, end-of-file-fixer, detect-private-key, black/isort (tuỳ chọn).

### 15.2 Mẫu requirements tối thiểu (Phase 0)

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
pydantic-settings==2.5.2
python-dotenv==1.0.1
httpx==0.27.2
loguru==0.7.2
pytest==8.3.2
pytest-asyncio==0.23.8
```
