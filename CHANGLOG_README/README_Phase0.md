# PVCFC RAG API - Phase 0 Foundation

**Hệ thống API Truy vấn Tài liệu Kỹ thuật PVCFC**

Đây là Phase 0 (Foundation) - thiết lập nền tảng cho dự án API RAG (Retrieval-Augmented Generation) để truy xuất và phân tích tri thức từ tài liệu kỹ thuật PVCFC.

Status: Phase 0 đã hoàn thành 100% và không yêu cầu bất kỳ API key nào. Ứng dụng mặc định chạy với LLM_PROVIDER=none.

## Quickstart (5 phút)

### Bước 1: Clone và Setup Environment

```bash
# Clone repository (nếu chưa có)
git clone <repository-url>
cd Code-API_LLM_PVCFC

# Tạo virtual environment và cài dependencies
# Linux/macOS:
make dev

# Windows:
.\scripts\dev.ps1
```

### Bước 2: Cấu hình Environment

```bash
# Copy file cấu hình mẫu
cp env.example .env

# Chỉnh sửa .env theo nhu cầu (tùy chọn)
# Mặc định sẽ chạy với LLM_PROVIDER=none (không cần API key)
```

### Bước 3: Chạy Server

```bash
# Linux/macOS:
make run

# Windows:
.\scripts\run.ps1
```

### Bước 4: Kiểm tra Health

Mở trình duyệt và truy cập:
- **Health Check:** http://localhost:8000/healthz
- **API Docs:** http://localhost:8000/docs (chỉ trong dev mode)

### Bước 5: Chạy Tests

```bash
# Linux/macOS:
make test

# Windows:
.\scripts\test.ps1
```

**Hoàn thành!** Bạn đã có foundation app chạy thành công.

### Bước 6 (tuỳ chọn): Smoke Test

Smoke test kiểm tra nhanh health endpoint, cấu hình, và (nếu có) kết nối LLM. Lưu ý: cần server đang chạy thì bài test health mới PASS.

```powershell
# Terminal 1: chạy server (Windows)
.\scripts\run.ps1

# Terminal 2: chạy smoke test (Windows)
.\venv\Scripts\python.exe tools\smoke_test.py
```

```bash
# Terminal 1: chạy server (Linux/macOS)
make run

# Terminal 2: chạy smoke test (Linux/macOS)
python tools/smoke_test.py
```

Nếu server chưa chạy, smoke test sẽ báo FAIL ở health_endpoint; đây là hành vi mong đợi.

## Cấu trúc Dự án

```
Code-API_LLM_PVCFC/
├── app/                    # Application code
│   ├── api/routers/       # FastAPI routers
│   │   └── health.py      # Health check endpoint
│   ├── core/              # Core utilities
│   │   ├── config.py      # Cấu hình với pydantic-settings
│   │   └── logging.py     # Logging setup với loguru
│   ├── rag/               # RAG components (Phase 2+)
│   ├── services/          # Business logic (Phase 2+)
│   ├── deps/              # Dependency injection (Phase 1+)
│   └── main.py            # FastAPI application
├── tests/                 # Unit tests
├── scripts/               # PowerShell scripts (Windows)
├── tools/                 # CLI tools (Phase 1+)
├── data/                  # Data directories (Phase 1+)
├── artifacts/             # Build artifacts (Phase 1+)
├── logs/                  # Application logs
├── requirements.txt       # Python dependencies
├── Dockerfile            # Production container
├── Makefile              # Development commands (Linux/macOS)
└── README_Phase0.md      # This file
```

## Development Commands

### Linux/macOS (Makefile)
```bash
make dev      # Setup development environment
make run      # Run development server
make test     # Run unit tests
make smoke    # Test LLM connections (nếu có API key)
make clean    # Clean cache files
```

### Windows (PowerShell Scripts)
```powershell
.\scripts\dev.ps1    # Setup development environment
.\scripts\run.ps1    # Run development server
.\scripts\test.ps1   # Run unit tests
.\scripts\smoke.ps1  # Test LLM connections (nếu có API key)
```

## Cấu hình Environment Variables

File `.env` (copy từ `env.example`):

```env
# Application Configuration
APP_ENV=local              # local | dev | prod
API_PORT=8000             # Port server
LOG_LEVEL=INFO            # DEBUG | INFO | WARNING | ERROR

# LLM Provider (Phase 2+)
LLM_PROVIDER=none         # none | openai | gemini
OPENAI_API_KEY=           # OpenAI API key (nếu dùng)
GEMINI_API_KEY=           # Gemini API key (nếu dùng)

# Performance Settings
CACHE_TTL_MINUTES=10      # Cache TTL
RATE_LIMIT_PER_MINUTE=60  # Rate limiting
```

## API Endpoints

### Health Check
```http
GET /healthz
```

Response:
```json
{
  "status": "healthy",
  "app_env": "local",
  "version": "0.1.0-dev",
  "commit_sha": "unknown",
  "uptime_seconds": 123,
  "uptime_human": "2m 3s",
  "llm_provider": "none",
  "llm_provider_ready": false,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Placeholder Endpoints (Phase 2+)
- `POST /api/v1/ask` - Question answering
- `POST /api/v1/locate` - Entity location trong P&ID
- `POST /api/v1/report` - Multi-section reports

## Testing

```bash
# Chạy tất cả tests
make test           # Linux/macOS
.\scripts\test.ps1  # Windows

# Chạy specific test
pytest tests/test_health.py -v

# Test coverage
pytest --cov=app tests/
```

## Docker

### Build và Run
```bash
# Build image
docker build -t pvcfc-rag-api .

# Run container
docker run -p 8000:8000 pvcfc-rag-api

# Health check
curl http://localhost:8000/healthz
```

### Environment trong Docker
```bash
# Với custom environment
docker run -p 8000:8000 -e APP_ENV=prod -e LOG_LEVEL=WARNING pvcfc-rag-api

# Hoặc nạp từ file .env (khuyến nghị cho dev)
docker run --env-file .env -p 8000:8000 pvcfc-rag-api
```

## Quality Gates

### Pre-commit Hooks
```bash
# Cài đặt hooks
pip install pre-commit
pre-commit install

# Chạy trên tất cả files
pre-commit run --all-files
```

Hooks bao gồm:
- Code formatting (Black, isort)
- Security checks (Bandit)
- YAML/JSON validation
- Detect private keys
- Run tests

## Roadmap

### Phase 0: Foundation [Completed]
- [x] FastAPI skeleton với health endpoint
- [x] Logging và error handling
- [x] Configuration management
- [x] Docker container
- [x] Testing framework
- [x] Development tooling

### Phase 1: Document Processing (Next)
- [ ] PDF parsing (vector + scan)
- [ ] Text extraction và normalization
- [ ] Hierarchical chunking
- [ ] Search indexing (FAISS + BM25)

### Phase 2: RAG Pipeline
- [ ] Query transformation (HyDE)
- [ ] Hybrid retrieval
- [ ] Cross-encoder reranking
- [ ] LLM generation với citations

### Phase 3: Evaluation & UI
- [ ] Golden dataset
- [ ] Evaluation metrics
- [ ] Streamlit demo UI
- [ ] SME annotation tools

## Troubleshooting

### Server không start
```bash
# Kiểm tra port conflicts
netstat -tulnp | grep 8000

# Kiểm tra logs
tail -f logs/requests.jsonl
```

### Tests fail
```bash
# Chạy với verbose output
pytest -v --tb=long

# Kiểm tra dependencies
pip list | grep fastapi
```

### Import errors
# PowerShell Execution Policy (Windows)
```powershell
# Nếu gặp lỗi: running scripts is disabled on this system
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Hoặc không cần activate venv, chạy trực tiếp:
.\venv\Scripts\python.exe -m pytest -v
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
```bash
# Đảm bảo PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Hoặc chạy từ root directory
python -m pytest tests/
```

## Support

- **Documentation:** Xem các file `Build_plan_phase*.txt`
- **Architecture:** Xem `WARP.md`
- **Issues:** Tạo issue trên Git repository

## Notes

- Phase 0 này hoàn toàn **không cần API keys** để chạy
- Server sẽ start với `LLM_PROVIDER=none` mặc định
- Logs được ghi vào thư mục `logs/`
- Pre-commit hooks đảm bảo code quality
- Docker image được optimize cho production

---

**Status:** Phase 0 Foundation [Completed]
**Next:** Phase 1 Document Processing & Indexing
