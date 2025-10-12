## Build Plan — Phase 0: Foundation & Environment

### Goals
- Prepare local environment (Windows 10/11) to run PVCFC RAG in Hybrid Modern or Baseline mode.
- Configure .env with required variables; install dependencies; start core services; smoke-test API.

### Prerequisites
- Windows 10/11, PowerShell
- Python 3.11 (venv recommended)
- Docker Desktop (WSL2 backend enabled)
- API keys as needed: GEMINI_API_KEY (required for embeddings/LLM), optional OPENAI_API_KEY

### Source of Truth
- `../../README.md`, `../../QUICK_START.md`
- `../../docs/QUICK_TEST_GUIDE.md`
- `../../CHANGLOG_README/TASK1_ENV_Variables_Report.md`

### Setup Steps
1) Create .env from template and fill required keys
```powershell
Copy-Item env.example .env -Force
notepad .env
```

Minimum variables to validate both Baseline and Hybrid Modern:
```ini
# Execution
APP_ENV=local
API_PORT=8000
LOG_LEVEL=INFO

# LLM
LLM_PROVIDER=gemini
LLM_MODEL_LIGHT=gemini-2.5-flash
LLM_MODEL_HEAVY=gemini-2.5-pro
GEMINI_API_KEY=AIza...  # replace

# Retrieval modes
USE_HYBRID_MODERN=true

# Weaviate
WEAVIATE_ENABLED=true
WEAVIATE_HOST=localhost
WEAVIATE_PORT=8080
WEAVIATE_GRPC_PORT=50051
WEAVIATE_USE_GRPC=true
WEAVIATE_COLLECTION=Chunk

# OpenSearch
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=rag_chunks
OPENSEARCH_BM25_K1=1.2
OPENSEARCH_BM25_B=0.75
OPENSEARCH_TIMEOUT=10
```

2) Install dependencies
```powershell
python -m venv venv
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3) Start infrastructure (Weaviate + OpenSearch)
```powershell
# Weaviate stack
docker compose -f docker-compose-weaviate.yml up -d

# App + OpenSearch (if included in docker-compose.yml)
docker compose up -d
```

4) Start API and UI
```powershell
# API
.\launchers\start_api.ps1

# UI (new terminal)
.\launchers\start_ui.ps1
```

### Validation
- Health: `Invoke-WebRequest http://localhost:8000/healthz`
- Index stats: `Invoke-WebRequest http://localhost:8000/index-stats`
  - Expect: `retriever_type = "hybrid_modern"`, Weaviate healthy, OpenSearch ~4883 docs (if indexed)

### KPIs (Phase Exit)
- API up and healthy
- Hybrid Modern enabled without runtime errors
- Basic ask call returns 200

### Troubleshooting
- Connection refused → Ensure Docker services running (`docker ps`), check ports 8000/8080/9200
- Missing GEMINI key → set `GEMINI_API_KEY` in `.env`
- SSL/grpc issues → set `WEAVIATE_USE_GRPC=true`, verify ports

### Deliverables
- Working local stack
- `.env` fully populated for chosen mode

### References
- `../../docs/QUICK_TEST_GUIDE.md`
- `../../CHANGLOG_README/TASK1_ENV_Variables_Report.md`
