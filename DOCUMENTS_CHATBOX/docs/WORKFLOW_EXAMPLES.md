# WORKFLOW EXAMPLES - PVCFC RAG SYSTEM

**Version**: 1.0.0
**Date**: 2025-10-12
**Purpose**: Ví dụ workflows cụ thể cho các use cases phổ biến

---

## 📋 MỤC LỤC

1. [Setup & Installation](#1-setup--installation)
2. [Data Ingestion Workflows](#2-data-ingestion-workflows)
3. [Query & Search Workflows](#3-query--search-workflows)
4. [Maintenance & Updates](#4-maintenance--updates)
5. [Troubleshooting Workflows](#5-troubleshooting-workflows)
6. [Development Workflows](#6-development-workflows)

---

## 1. SETUP & INSTALLATION

### Workflow 1.1: First Time Setup (Local Development)

**Goal**: Setup dự án lần đầu tiên trên máy local

**Prerequisites**:
- Python 3.11 installed
- Docker Desktop installed
- Git installed

**Steps**:

```powershell
# Step 1: Clone repository
cd C:\Users\Admin\Desktop
git clone <repository-url> Code-API_LLM_PVCFC
cd Code-API_LLM_PVCFC

# Step 2: Create virtual environment
py -3.11 -m venv .venv

# Step 3: Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Step 4: Install dependencies
pip install -r requirements.txt

# Step 5: Configure environment variables
cp env.example .env

# Edit .env file với Notepad++/VSCode:
# - Set GEMINI_API_KEY=your_actual_key
# - Set APP_ENV=local
# - Set USE_HYBRID_MODERN=true (hoặc false cho legacy mode)
notepad .env

# Step 6: Start Docker services
docker-compose up -d                             # OpenSearch
docker-compose -f docker-compose-weaviate.yml up -d  # Weaviate

# Step 7: Verify Docker services
docker ps
# Should see: opensearch-node, opensearch-dashboards, weaviate-weaviate-1

# Step 8: Test Docker services
curl http://localhost:9200      # OpenSearch should respond
curl http://localhost:8080/v1/.well-known/ready  # Weaviate should respond "true"

# Step 9: Verify Python environment
python -c "import fastapi; print(fastapi.__version__)"
python -c "import weaviate; print(weaviate.__version__)"
python -c "import google.genai; print('Gemini SDK OK')"

# Step 10: Check configuration
python -c "from app.core.config import settings; print(f'APP_ENV: {settings.app_env}'); print(f'LLM_PROVIDER: {settings.llm_provider}')"
```

**Expected Output**:
```
✓ Virtual environment activated
✓ All packages installed successfully
✓ Docker services running
✓ Configuration loaded
✓ Ready to ingest data!
```

**Verification**:
```powershell
# Check health (before ingestion, should fail gracefully)
curl http://localhost:8000/healthz
# Expected: Connection refused (API not started yet - that's OK!)
```

---

### Workflow 1.2: Production Server Setup

**Goal**: Setup dự án trên production server

**Prerequisites**:
- Ubuntu 20.04+ / Windows Server
- Python 3.11
- Docker & Docker Compose
- Nginx (for reverse proxy)
- SSL certificate (optional but recommended)

**Steps**:

```bash
# Step 1: Create application user
sudo useradd -m -s /bin/bash pvcfc
sudo usermod -aG docker pvcfc

# Step 2: Clone repository
sudo su - pvcfc
git clone <repository-url> /opt/pvcfc-rag
cd /opt/pvcfc-rag

# Step 3: Setup virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Step 4: Configure environment
cp env.example .env
nano .env
# Set APP_ENV=prod
# Set API keys
# Set paths

# Step 5: Create data directories
sudo mkdir -p /mnt/data/raw
sudo chown -R pvcfc:pvcfc /mnt/data

# Step 6: Mount NAS (if using network storage)
# Add to /etc/fstab:
# //nas-server/pvcfc-data /mnt/data/raw cifs credentials=/root/.smbcredentials 0 0
sudo mount -a

# Step 7: Start Docker services
cd /opt/pvcfc-rag
docker-compose up -d
docker-compose -f docker-compose-weaviate.yml up -d

# Step 8: Create systemd service for API
sudo nano /etc/systemd/system/pvcfc-rag-api.service

# Paste content:
[Unit]
Description=PVCFC RAG API
After=network.target docker.service

[Service]
Type=simple
User=pvcfc
WorkingDirectory=/opt/pvcfc-rag
Environment="PATH=/opt/pvcfc-rag/.venv/bin"
ExecStart=/opt/pvcfc-rag/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable pvcfc-rag-api
sudo systemctl start pvcfc-rag-api

# Step 9: Configure Nginx reverse proxy
sudo nano /etc/nginx/sites-available/pvcfc-rag

# Paste content:
server {
    listen 80;
    server_name api.pvcfc-rag.local;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/pvcfc-rag /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Step 10: Setup log rotation
sudo nano /etc/logrotate.d/pvcfc-rag

# Paste content:
/opt/pvcfc-rag/artifacts/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 pvcfc pvcfc
}

# Step 11: Verify
curl http://localhost/healthz
```

---

## 2. DATA INGESTION WORKFLOWS

### Workflow 2.1: Initial Data Ingestion (Production)

**Goal**: Ingest toàn bộ corpus lần đầu tiên

**Input**: PDFs in `D:\Data_Raw` (hoặc `/mnt/data/raw` on Linux)

**Steps**:

```powershell
# Step 1: Verify source data
ls D:\Data_Raw\*.pdf -Recurse | Measure-Object
# Should show: Count: 150+ PDFs

# Step 2: Run ingestion with versioning
python tools/ingest.py `
  --source-dir "D:\\Data_Raw" `
  --output-dir "artifacts\\ingestion_production" `
  --workers 4 `
  --enable-ocr `
  --ocr-lang "vie+eng" `
  --extract-tables `
  --create-version `
  --version-id "v1.0_prod" `
  --version-description "Initial production baseline - 150 PDFs" `
  --version-tags "production baseline stable"

# Expected duration: 10-30 minutes (depends on PDF count and OCR needs)

# Step 3: Verify ingestion outputs
ls artifacts\ingestion_production\

# Should see:
# - chunks.jsonl (~12,500 chunks)
# - doc_id_map.json
# - quarantine.jsonl (hopefully empty or few entries)
# - manifests/

# Step 4: Check quarantine (failed files)
cat artifacts\ingestion_production\quarantine.jsonl

# Step 5: Index to Weaviate
python scripts\phase1_index_to_weaviate.py

# Expected duration: 5-10 minutes

# Step 6: Index to OpenSearch
python scripts\opensearch\create_rag_chunks_index.py
python scripts\opensearch\bulk_insert_to_opensearch.py

# Expected duration: 2-5 minutes

# Step 7: Build legacy indices (optional, for fallback)
python tools\ops\build_production_indices.py

# Expected duration: 3-5 minutes

# Step 8: Verify indices
# Weaviate
python scripts\weaviate\test_weaviate_search.py "CO2 compressor"

# OpenSearch
curl http://localhost:9200/rag_chunks/_count
# Should return: {"count": 4883, ...}

# Step 9: Start API
.\launchers\start_api.ps1

# Step 10: Test query
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{
    "query": "What is the maximum operating pressure?",
    "language": "en",
    "max_context": 8
  }'

# Should return answer with citations!
```

**Success Criteria**:
- ✅ All PDFs processed (or documented in quarantine)
- ✅ chunks.jsonl created with expected count
- ✅ Weaviate & OpenSearch indices populated
- ✅ API responds to test query with citations

---

### Workflow 2.2: Incremental Data Update

**Goal**: Thêm PDF mới vào corpus hiện tại

**Scenario**: Có 20 PDFs mới trong `D:\Data_Raw_New`

**Steps**:

```powershell
# Step 1: Ingest new PDFs to separate directory
python tools/ingest.py `
  --source-dir "D:\\Data_Raw_New" `
  --output-dir "artifacts\\ingestion_v1.1" `
  --workers 4 `
  --enable-ocr `
  --ocr-lang "vie+eng" `
  --extract-tables `
  --create-version `
  --version-id "v1.1_incremental" `
  --version-description "Added 20 new technical specs" `
  --version-tags "production incremental"

# Step 2: Verify new chunks
cat artifacts\ingestion_v1.1\chunks.jsonl | Measure-Object -Line
# Should show new chunks count

# Step 3: Index new chunks to Weaviate (append mode)
python scripts\phase1_index_to_weaviate.py `
  --chunks-path "artifacts\\ingestion_v1.1\\chunks.jsonl" `
  --append

# Step 4: Index new chunks to OpenSearch (append mode)
python scripts\opensearch\bulk_insert_to_opensearch.py `
  --chunks-path "artifacts\\ingestion_v1.1\\chunks.jsonl"

# Step 5: Merge chunks to production directory
cat artifacts\ingestion_v1.1\chunks.jsonl >> artifacts\ingestion_production\chunks.jsonl

# Step 6: Merge doc_id_map
python scripts\utilities\merge_doc_id_maps.py `
  --source "artifacts\\ingestion_v1.1\\doc_id_map.json" `
  --target "artifacts\\ingestion_production\\doc_id_map.json"

# Step 7: Compare versions
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    print(vm.compare_versions('v1.0_prod', 'v1.1_incremental'))"

# Step 8: Restart API (hot reload should work, but restart for safety)
# Ctrl+C in API terminal, then:
.\launchers\start_api.ps1

# Step 9: Test new content
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{
    "query": "Query about content from new PDFs",
    "language": "vi",
    "max_context": 8
  }'
```

**Success Criteria**:
- ✅ New chunks indexed
- ✅ No duplicate chunks (dedup working)
- ✅ Query returns content from new PDFs
- ✅ Old content still accessible

---

### Workflow 2.3: Re-ingestion (Full Rebuild)

**Goal**: Re-ingest toàn bộ corpus (khi có bug fix hoặc schema change)

**Steps**:

```powershell
# Step 1: Backup current production artifacts
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item -Path "artifacts\ingestion_production" -Destination "artifacts\ingestion_production_backup_$timestamp" -Recurse
Copy-Item -Path "artifacts\index_production" -Destination "artifacts\index_production_backup_$timestamp" -Recurse

# Step 2: Clear current production directory
Remove-Item -Path "artifacts\ingestion_production\*" -Recurse -Force

# Step 3: Re-ingest with new version
python tools/ingest.py `
  --source-dir "D:\\Data_Raw" `
  --output-dir "artifacts\\ingestion_production" `
  --workers 4 `
  --enable-ocr `
  --ocr-lang "vie+eng" `
  --extract-tables `
  --create-version `
  --version-id "v2.0_rebuild" `
  --version-description "Full rebuild with updated chunking" `
  --version-tags "production rebuild"

# Step 4: Rebuild all indices
# Clear Weaviate collection
python -c "import weaviate; client = weaviate.connect_to_local(); client.collections.delete('Chunk'); client.close()"

# Clear OpenSearch index
curl -X DELETE http://localhost:9200/rag_chunks

# Re-index
python scripts\phase1_index_to_weaviate.py
python scripts\opensearch\create_rag_chunks_index.py
python scripts\opensearch\bulk_insert_to_opensearch.py
python tools\ops\build_production_indices.py

# Step 5: Restart API
.\launchers\start_api.ps1

# Step 6: Run smoke tests
python scripts\phase4_rag_integration_test.py

# Step 7: Compare with backup
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    print(vm.compare_versions('v1.0_prod', 'v2.0_rebuild'))"

# If satisfied with results, keep new version
# If issues found, rollback (see Workflow 4.3)
```

---

## 3. QUERY & SEARCH WORKFLOWS

### Workflow 3.1: Simple Q&A

**Goal**: Hỏi đáp đơn giản với citations

```powershell
# Vietnamese query
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{
    "query": "Áp suất vận hành tối đa của K06101 là bao nhiêu?",
    "language": "vi",
    "max_context": 8,
    "enable_vision_generation": false
  }'

# English query
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{
    "query": "What is the maximum operating pressure of K06101?",
    "language": "en",
    "max_context": 8,
    "enable_vision_generation": false
  }'

# Expected response:
{
  "answer": "The maximum operating pressure of K06101 is 150 PSI...",
  "citations": [
    {
      "doc_id": "DOCID_abc123",
      "page": 12,
      "pdf_path": "D:\\Data_Raw\\...\\manual.pdf",
      "confidence": 0.95
    }
  ],
  "confidence": 0.85,
  "meta": {
    "model": "gemini-2.5-flash",
    "latency_ms": 850,
    "k": 8,
    "trace_id": "xyz789"
  }
}
```

---

### Workflow 3.2: Q&A with Vision (Multimodal)

**Goal**: Hỏi đáp với PDF pages rendering (cho câu hỏi về bảng/hình vẽ)

```powershell
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{
    "query": "Show me the P&ID diagram for CO2 compressor system",
    "language": "en",
    "max_context": 8,
    "enable_vision_generation": true
  }'

# Expected response includes:
{
  "answer": "The P&ID diagram shows... [Doc 1, p.25]",
  "citations": [...],
  "meta": {
    "model": "gemini-2.5-pro",
    "vision_generation": {
      "pages_used": [
        {"pdf_path": "D:\\...\\drawing.pdf", "page": 25}
      ],
      "pages_failed": []
    }
  }
}
```

---

### Workflow 3.3: Filtered Search

**Goal**: Tìm kiếm với filters (equipment_id, doc_type)

```powershell
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{
    "query": "maintenance procedure",
    "language": "en",
    "max_context": 8,
    "filters": {
      "equipment_id": "K06101",
      "doc_type": "Maintenance"
    }
  }'

# Response will prioritize:
# - Documents tagged with equipment_id = K06101
# - Documents of type Maintenance
```

---

### Workflow 3.4: Document Location

**Goal**: Tìm tài liệu chứa nội dung cụ thể

```powershell
curl -X POST http://localhost:8000/api/locate `
  -H "Content-Type: application/json" `
  -d '{
    "query": "safety valve specifications",
    "max_results": 20
  }'

# Expected response:
{
  "documents": [
    {
      "doc_id": "DOCID_abc123",
      "pdf_path": "D:\\...\\manual.pdf",
      "pages": [12, 15, 18],
      "relevance_score": 0.92
    },
    ...
  ]
}
```

---

### Workflow 3.5: Report Generation

**Goal**: Tạo báo cáo formatted từ query

```powershell
curl -X POST http://localhost:8000/api/report `
  -H "Content-Type: application/json" `
  -d '{
    "query": "Summarize all maintenance procedures for K06101",
    "language": "vi",
    "format": "markdown"
  }'

# Expected response:
{
  "report": "# Báo cáo: Maintenance Procedures for K06101\n\n## Tóm tắt\n...",
  "format": "markdown",
  "citations": [...],
  "generated_at": "2025-10-12T10:30:00Z"
}

# Save report to file
curl ... > reports/k06101_maintenance.md
```

---

## 4. MAINTENANCE & UPDATES

### Workflow 4.1: Regular Health Check

**Goal**: Kiểm tra health hệ thống định kỳ

```powershell
# Daily health check script
# Save as: scripts/daily_health_check.ps1

$health = Invoke-RestMethod -Uri "http://localhost:8000/healthz"
Write-Host "Health Status: $($health.status)"

if ($health.status -ne "healthy") {
    Write-Warning "System is $($health.status)"
    # Send alert email or Slack notification
}

$stats = Invoke-RestMethod -Uri "http://localhost:8000/index-stats"
Write-Host "Retriever Type: $($stats.retriever_type)"
Write-Host "OpenSearch Docs: $($stats.opensearch.num_documents)"

# Run daily
# Schedule in Windows Task Scheduler or cron (Linux)
```

---

### Workflow 4.2: Index Maintenance

**Goal**: Maintain và optimize indices

```powershell
# Weekly index maintenance

# Step 1: Check index size
curl http://localhost:9200/_cat/indices/rag_chunks?v

# Step 2: Check Weaviate storage
curl http://localhost:8080/v1/schema/Chunk | jq '.vectorIndexConfig'

# Step 3: Optimize OpenSearch index
curl -X POST http://localhost:9200/rag_chunks/_forcemerge?max_num_segments=1

# Step 4: Backup indices (see Workflow 4.4)

# Step 5: Clear old logs
Remove-Item -Path "artifacts\logs\*.log" -Force -Confirm:$false | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) }
```

---

### Workflow 4.3: Rollback to Previous Version

**Goal**: Rollback khi có vấn đề với version mới

```powershell
# Step 1: List available versions
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    for v in vm.list_versions(): print(f'{v['version_id']}: {v['description']}')"

# Output:
# v1.0_prod: Initial production baseline
# v1.1_incremental: Added 20 new specs
# v2.0_rebuild: Full rebuild (current - problematic)

# Step 2: Restore to v1.1_incremental
python tools/ops/create_version.py `
  --restore `
  --version-id "v1.1_incremental" `
  --target-dir "artifacts\ingestion_production"

# Step 3: Rebuild indices from restored chunks
python tools\ops\build_production_indices.py
python scripts\phase1_index_to_weaviate.py
python scripts\opensearch\create_rag_chunks_index.py
python scripts\opensearch\bulk_insert_to_opensearch.py

# Step 4: Restart API
.\launchers\start_api.ps1

# Step 5: Verify
curl http://localhost:8000/index-stats
python scripts\phase4_rag_integration_test.py
```

---

### Workflow 4.4: Backup & Recovery

**Goal**: Backup toàn bộ hệ thống

```powershell
# Weekly backup script
# Save as: scripts/weekly_backup.ps1

$timestamp = Get-Date -Format "yyyyMMdd"
$backupDir = "E:\Backups\pvcfc-rag\$timestamp"

# Create backup directory
New-Item -Path $backupDir -ItemType Directory -Force

# Step 1: Backup ingestion artifacts
Compress-Archive -Path "artifacts\ingestion_production\*" `
  -DestinationPath "$backupDir\ingestion_$timestamp.zip"

# Step 2: Backup indices
Compress-Archive -Path "artifacts\index_production\*" `
  -DestinationPath "$backupDir\indices_$timestamp.zip"

# Step 3: Backup versions
Compress-Archive -Path "artifacts\versions\*" `
  -DestinationPath "$backupDir\versions_$timestamp.zip"

# Step 4: Backup Docker volumes (Weaviate)
docker exec weaviate-weaviate-1 tar -czf /tmp/weaviate_backup.tar.gz /var/lib/weaviate
docker cp weaviate-weaviate-1:/tmp/weaviate_backup.tar.gz "$backupDir\weaviate_$timestamp.tar.gz"

# Step 5: Backup OpenSearch (snapshot API)
curl -X PUT http://localhost:9200/_snapshot/my_backup/snapshot_$timestamp `
  -H "Content-Type: application/json" `
  -d '{"indices": "rag_chunks", "include_global_state": false}'

# Step 6: Backup configuration
Copy-Item -Path ".env" -Destination "$backupDir\.env.backup"

# Step 7: Generate backup report
@"
Backup Report - $timestamp
================================
Ingestion: $(ls "$backupDir\ingestion_$timestamp.zip" | Select-Object -ExpandProperty Length) bytes
Indices: $(ls "$backupDir\indices_$timestamp.zip" | Select-Object -ExpandProperty Length) bytes
Versions: $(ls "$backupDir\versions_$timestamp.zip" | Select-Object -ExpandProperty Length) bytes
Weaviate: $(ls "$backupDir\weaviate_$timestamp.tar.gz" | Select-Object -ExpandProperty Length) bytes

Status: SUCCESS
"@ | Out-File -FilePath "$backupDir\backup_report.txt"

# Step 8: Cleanup old backups (keep last 4 weeks)
Get-ChildItem "E:\Backups\pvcfc-rag" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-28) } | Remove-Item -Recurse -Force

Write-Host "Backup completed: $backupDir"
```

**Recovery**:
```powershell
# Recover from backup (when needed)
$restoreDate = "20251010"
$backupDir = "E:\Backups\pvcfc-rag\$restoreDate"

# Step 1: Stop services
docker-compose down
docker-compose -f docker-compose-weaviate.yml down

# Step 2: Restore artifacts
Expand-Archive -Path "$backupDir\ingestion_$restoreDate.zip" `
  -DestinationPath "artifacts\ingestion_production" -Force

Expand-Archive -Path "$backupDir\indices_$restoreDate.zip" `
  -DestinationPath "artifacts\index_production" -Force

Expand-Archive -Path "$backupDir\versions_$restoreDate.zip" `
  -DestinationPath "artifacts\versions" -Force

# Step 3: Restore Weaviate
docker-compose -f docker-compose-weaviate.yml up -d
# Wait for Weaviate to start
Start-Sleep -Seconds 30
docker cp "$backupDir\weaviate_$restoreDate.tar.gz" weaviate-weaviate-1:/tmp/
docker exec weaviate-weaviate-1 tar -xzf /tmp/weaviate_$restoreDate.tar.gz -C /

# Step 4: Restore OpenSearch
docker-compose up -d
# Wait for OpenSearch to start
Start-Sleep -Seconds 30
curl -X POST "http://localhost:9200/_snapshot/my_backup/snapshot_$restoreDate/_restore"

# Step 5: Restore configuration
Copy-Item -Path "$backupDir\.env.backup" -Destination ".env" -Force

# Step 6: Restart API
.\launchers\start_api.ps1

# Step 7: Verify
curl http://localhost:8000/healthz
curl http://localhost:8000/index-stats
```

---

## 5. TROUBLESHOOTING WORKFLOWS

### Workflow 5.1: Debug Query (No Results)

**Problem**: Query không trả về kết quả

**Steps**:

```powershell
# Step 1: Check API health
curl http://localhost:8000/healthz

# Step 2: Check index stats
curl http://localhost:8000/index-stats

# Step 3: Test retrieval directly
python scripts\diagnostics\deep_diagnostic.py --query "your query here"

# Expected output:
# - Retrieved chunks
# - Scores
# - Metadata

# Step 4: Check if keywords exist in corpus
python -c "
import json
chunks = [json.loads(line) for line in open('artifacts/ingestion_production/chunks.jsonl')]
matching = [c for c in chunks if 'keyword' in c['text'].lower()]
print(f'Found {len(matching)} chunks containing keyword')
"

# Step 5: Test embedding
python -c "
from app.services.embedding import EmbeddingService
from app.core.config import settings
service = EmbeddingService(settings)
vec = service.embed_texts(['your query'])[0]
print(f'Embedding dimension: {len(vec)}')
print(f'Embedding norm: {sum(x**2 for x in vec)**0.5}')
"

# Step 6: Test Weaviate directly
python scripts\weaviate\test_weaviate_search.py "your query"

# Step 7: Test OpenSearch directly
python scripts\opensearch\test_opensearch_search.py "your query"

# Step 8: Check logs for errors
tail -f artifacts\logs\pvcfc-rag_*.log | grep ERROR
```

---

### Workflow 5.2: Debug Negative Confidence

**Problem**: API returns 422 error - negative confidence

**Steps**:

```powershell
# Step 1: Check if using v0.6.1 or later (has fix)
python -c "from app.core.config import settings; print(f'Version: {settings.version}')"

# If version < 0.6.1:
git pull origin main
pip install -r requirements.txt --upgrade

# Step 2: Check reranker configuration
cat .env | Select-String "BGE_RERANK"

# Step 3: Disable BGE reranker temporarily
# Edit .env:
ENABLE_BGE_RERANK=false

# Step 4: Restart API
.\launchers\start_api.ps1

# Step 5: Test query again
curl -X POST http://localhost:8000/api/ask ...

# Step 6: Check logs for confidence calculation
tail -f artifacts\logs\pvcfc-rag_*.log | grep "confidence"

# Should see defensive clamping logs in v0.6.1+
```

---

### Workflow 5.3: Debug Vision Generation Failure

**Problem**: Vision generation fails với "No such file or directory"

**Steps**:

```powershell
# Step 1: Check doc_id_map exists
ls artifacts\ingestion_production\doc_id_map.json

# Step 2: Check doc_id_map content
python -c "
import json
doc_map = json.load(open('artifacts/ingestion_production/doc_id_map.json'))
print(f'Total docs: {len(doc_map)}')
# Check a sample
sample_doc = list(doc_map.values())[0]
print(f'Sample: {sample_doc}')
print(f'Path exists: {os.path.exists(sample_doc['pdf_path'])}')
"

# Step 3: Fix doc_id_map paths
python scripts\utilities\fix_doc_id_map.py `
  --doc-id-map "artifacts\ingestion_production\doc_id_map.json" `
  --pdf-root "D:\Data_Raw"

# Step 4: Verify PDF accessibility
python scripts\diagnostics\check_pdf_pages.py `
  --pdf-path "D:\Data_Raw\path\to\file.pdf"

# Step 5: Test vision generation
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{
    "query": "test query",
    "enable_vision_generation": true
  }'
```

---

## 6. DEVELOPMENT WORKFLOWS

### Workflow 6.1: Add New Feature (Example: New Reranker)

**Goal**: Thêm một reranker model mới

**Steps**:

```powershell
# Step 1: Create feature branch
git checkout -b feature/new-reranker

# Step 2: Create new reranker class
# Create file: app/rag/rerankers/my_new_reranker.py

class MyNewReranker:
    def __init__(self, model_name: str):
        self.model = load_model(model_name)

    def rerank(self, query: str, results: List[Result]) -> List[Result]:
        # Implementation
        pass

# Step 3: Add configuration
# Edit app/core/config.py:
class Settings(BaseSettings):
    ...
    my_reranker_enabled: bool = False
    my_reranker_model: str = "model-name"

# Step 4: Integrate into retriever
# Edit app/rag/hybrid_weaviate_opensearch_retriever.py:
if settings.my_reranker_enabled:
    from app.rag.rerankers.my_new_reranker import MyNewReranker
    reranker = MyNewReranker(settings.my_reranker_model)
    results = reranker.rerank(query, results)

# Step 5: Write tests
# Create file: tests/unit/test_my_new_reranker.py

def test_my_new_reranker():
    reranker = MyNewReranker("model-name")
    results = [...]
    reranked = reranker.rerank("query", results)
    assert len(reranked) > 0
    assert reranked[0].score >= reranked[1].score

# Step 6: Run tests
pytest tests/unit/test_my_new_reranker.py -v

# Step 7: Update documentation
# Edit docs/MODULE_CATALOG.md

# Step 8: Commit and push
git add .
git commit -m "feat: Add new reranker model"
git push origin feature/new-reranker

# Step 9: Create pull request
```

---

### Workflow 6.2: Debug with Breakpoints

**Goal**: Debug code với VS Code breakpoints

**Steps**:

```powershell
# Step 1: Open project in VS Code
code .

# Step 2: Create launch.json
# .vscode/launch.json:
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "FastAPI Debug",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "app.main:app",
                "--host", "127.0.0.1",
                "--port", "8000",
                "--reload"
            ],
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            },
            "console": "integratedTerminal"
        }
    ]
}

# Step 3: Set breakpoint in code
# Example: app/rag/generator.py, line 150

# Step 4: Start debugging (F5)

# Step 5: Send request to trigger breakpoint
curl -X POST http://localhost:8000/api/ask ...

# Step 6: Inspect variables, step through code
```

---

## 📚 RELATED DOCUMENTATION

- [PROJECT_MASTERY_GUIDE.md](PROJECT_MASTERY_GUIDE.md) - Comprehensive project guide
- [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) - Visual architecture
- [MODULE_CATALOG.md](MODULE_CATALOG.md) - Module details
- [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) - Troubleshooting reference

---

**Last Updated**: 2025-10-12
**Version**: 1.0.0
**Status**: ✅ Complete
