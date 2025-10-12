# FAQ & QUICK REFERENCE - PVCFC RAG SYSTEM

**Version**: 1.0.0
**Date**: 2025-10-12
**Purpose**: Câu hỏi thường gặp và tham chiếu nhanh

---

## 📋 MỤC LỤC

1. [Quick Reference](#1-quick-reference)
2. [FAQ - General](#2-faq---general)
3. [FAQ - Installation & Setup](#3-faq---installation--setup)
4. [FAQ - Data Ingestion](#4-faq---data-ingestion)
5. [FAQ - Query & Search](#5-faq---query--search)
6. [FAQ - Performance](#6-faq---performance)
7. [FAQ - Troubleshooting](#7-faq---troubleshooting)
8. [Cheat Sheet](#8-cheat-sheet)

---

## 1. QUICK REFERENCE

### 1.1 Essential Commands

```powershell
# Start Docker services
docker-compose up -d
docker-compose -f docker-compose-weaviate.yml up -d

# Start API
.\launchers\start_api.ps1

# Start UI
.\launchers\start_ui.ps1

# Health check
curl http://localhost:8000/healthz

# Index stats
curl http://localhost:8000/index-stats

# Test query
curl -X POST http://localhost:8000/api/ask -H "Content-Type: application/json" -d '{"query": "test"}'
```

### 1.2 Important File Locations

| File/Directory | Location | Purpose |
|----------------|----------|---------|
| **Environment Config** | `.env` | Environment variables |
| **Chunks** | `artifacts/ingestion_production/chunks.jsonl` | Deduplicated text chunks |
| **Doc ID Map** | `artifacts/ingestion_production/doc_id_map.json` | doc_id → pdf_path mapping |
| **Logs** | `artifacts/logs/pvcfc-rag_*.log` | Application logs |
| **Weaviate Data** | Docker volume | Vector embeddings |
| **OpenSearch Data** | Docker volume | BM25 inverted index |

### 1.3 Default Ports

| Service | Port | URL |
|---------|------|-----|
| **API** | 8000 | http://localhost:8000 |
| **UI** | 8502 | http://localhost:8502 |
| **Weaviate HTTP** | 8080 | http://localhost:8080 |
| **Weaviate gRPC** | 50051 | localhost:50051 |
| **OpenSearch** | 9200 | http://localhost:9200 |
| **OpenSearch Dashboards** | 5601 | http://localhost:5601 |

### 1.4 Key Environment Variables

```ini
# Essential
APP_ENV=local|dev|prod
GEMINI_API_KEY=your_key
USE_HYBRID_MODERN=true|false

# Retrieval
WEAVIATE_ENABLED=true
WEAVIATE_COLLECTION=Chunk
OPENSEARCH_HOST=localhost
OPENSEARCH_INDEX=rag_chunks

# Reranking
ENABLE_BGE_RERANK=false
BGE_RERANK_TOP_K=10

# Vision
VISION_MAX_PAGES_TOTAL=10
PDF_RENDER_DPI=200
```

---

## 2. FAQ - GENERAL

### Q: Dự án này làm gì?

**A**: Hệ thống RAG (Retrieval-Augmented Generation) để hỏi-đáp kỹ thuật trên tài liệu PVCFC với:
- Tìm kiếm ngữ nghĩa + từ khóa (hybrid)
- Trả lời có trích dẫn (doc_id + page number)
- Hỗ trợ vision (multimodal) cho bảng/hình vẽ
- Production-ready với Weaviate + OpenSearch

### Q: Tech stack chính là gì?

**A**:
- **Backend**: FastAPI + Python 3.11
- **Vector DB**: Weaviate (gRPC)
- **Keyword Search**: OpenSearch (BM25)
- **LLM**: Gemini 2.5 Pro/Flash
- **Embedding**: Gemini Embedding (768D)
- **Reranker**: BGE CrossEncoder (optional)
- **OCR**: Tesseract/PaddleOCR

### Q: Hệ thống hỗ trợ định dạng file nào?

**A**:
- **V1 (hiện tại)**: PDF (vector text hoặc scanned)
- **Future**: Office docs (docx, xlsx, pptx) - kiến trúc đã sẵn sàng

### Q: Dữ liệu được lưu ở đâu?

**A**:
- **Raw PDFs**: `D:\Data_Raw` (ổ rời)
- **Chunks**: `artifacts/ingestion_production/chunks.jsonl`
- **Vectors**: Weaviate Docker volume
- **BM25 Index**: OpenSearch Docker volume
- **Legacy**: FAISS files in `artifacts/index_production/faiss/`

---

## 3. FAQ - INSTALLATION & SETUP

### Q: Python version nào được hỗ trợ?

**A**: Python 3.11 (required). Không test với Python 3.12+.

### Q: Cần Docker không?

**A**: Có, cần Docker Desktop (Windows) hoặc Docker Engine (Linux) cho:
- Weaviate vector database
- OpenSearch BM25 index

### Q: Cần API key nào?

**A**:
- **Gemini API key** (required): Từ https://makersuite.google.com/app/apikey
- **OpenAI API key** (optional): Nếu dùng OpenAI models

### Q: Cài đặt mất bao lâu?

**A**:
- **Setup môi trường**: 10-15 phút
- **Ingestion (150 PDFs)**: 10-30 phút (tùy có OCR không)
- **Indexing**: 5-15 phút
- **Total**: ~30-60 phút cho first-time setup

### Q: RAM tối thiểu cần bao nhiêu?

**A**:
- **Development**: 8GB RAM (tight)
- **Recommended**: 16GB RAM
- **Production**: 32GB RAM (ideal)

RAM breakdown:
- API: ~500MB-1GB
- Docker (Weaviate + OpenSearch): ~3-5GB
- Ingestion pipeline: ~2-4GB peak

---

## 4. FAQ - DATA INGESTION

### Q: Ingestion pipeline làm gì?

**A**: Process PDFs thành chunks với metadata:
1. Parse PDF (PyMuPDF)
2. OCR nếu cần (Tesseract/PaddleOCR)
3. Extract tables (pdfplumber)
4. Chunk text (1000 chars, overlap 200)
5. Dedup by content_hash (SHA1)
6. Generate metadata (doc_id, equipment_id, doc_type)

### Q: Làm sao để chỉ ingest PDFs mới?

**A**: Sử dụng incremental ingestion:
```powershell
python tools/ingest.py \
  --source-dir "D:\\Data_Raw_New" \
  --output-dir "artifacts\\ingestion_v1.1" \
  --create-version \
  --version-id "v1.1_incremental"
```

### Q: OCR có tự động không?

**A**: Có, OCR tự động kích hoạt khi:
- PDF không có extractable text (scanned PDF)
- Hoặc text extraction thất bại

Cấu hình: `--enable-ocr --ocr-lang "vie+eng"`

### Q: Làm sao để skip OCR (faster ingestion)?

**A**: Bỏ flag `--enable-ocr`:
```powershell
python tools/ingest.py \
  --source-dir "D:\\Data_Raw" \
  --output-dir "artifacts\\ingestion" \
  # No --enable-ocr flag
```

### Q: Deduplication hoạt động như thế nào?

**A**:
- **file_hash** (SHA256): Detect exact file duplicates
- **content_hash** (SHA1 of normalized text): Detect content duplicates
- Chỉ giữ 1 representative per content_hash
- Priority: vector > scan > newer > shorter_path

### Q: Quarantine file là gì?

**A**: `quarantine.jsonl` ghi lại các files thất bại:
- Corrupt PDF
- Password-protected PDF
- OCR failed
- Read error

Không di chuyển files, chỉ log lại để review.

### Q: Equipment ID được extract như thế nào?

**A**: Regex pattern: `\bKT?\d{5}\b`
- Matches: `K06101`, `KT06101`, `K12345`
- Extracts từ file path và content
- Lưu trong metadata

---

## 5. FAQ - QUERY & SEARCH

### Q: Hybrid retrieval là gì?

**A**: Kết hợp 2 phương pháp:
- **Semantic search** (Weaviate): Tìm theo ý nghĩa (embeddings)
- **Keyword search** (OpenSearch BM25): Tìm theo từ khóa exact match
- **RRF Fusion**: Merge và rank kết quả từ cả 2

### Q: Khi nào nên dùng vision generation?

**A**: Dùng khi:
- Query về bảng, biểu đồ, hình vẽ, P&ID diagrams
- Cần thông tin visual context
- Set `enable_vision_generation: true`

Trade-offs:
- ✅ Higher accuracy for visual content
- ❌ Slower (render PDF pages)
- ❌ More expensive (Gemini 2.5 Pro)

### Q: Citations có độ tin cậy như thế nào?

**A**: Mỗi citation có:
- **doc_id**: Document identifier
- **page**: Page number (1-based)
- **confidence**: [0, 1] - từ retrieval + validation
- **pdf_path**: Path to source PDF (if available)

CiteFix-lite validation (Level 1-2) đảm bảo:
- Document exists
- Page number valid
- Text matches page content

### Q: Làm sao để filter kết quả?

**A**: Dùng `filters` trong request:
```json
{
  "query": "maintenance procedure",
  "filters": {
    "equipment_id": "K06101",
    "doc_type": "Maintenance"
  }
}
```

### Q: Max context là gì?

**A**: `max_context` là số chunks sử dụng cho generation:
- Default: 8 chunks
- Min: 1, Max: 20
- Trade-off: More context → better answer, but slower & more expensive

### Q: Reranking có cần thiết không?

**A**:
- **BGE Reranking** (optional): Improve relevance ~5-15%
- Trade-off: Adds 100-400ms latency
- Recommended: Enable for production, disable for dev/testing
- Config: `ENABLE_BGE_RERANK=true`

---

## 6. FAQ - PERFORMANCE

### Q: Query latency bao lâu?

**A**: Typical latency (p50):
- **Transform**: 50-150ms
- **Retrieval**: 200-500ms (hybrid parallel)
- **Rerank**: 100-400ms (if enabled)
- **Generation**: 300-1000ms (LLM call)
- **Total**: 500-2000ms

### Q: Làm sao để tăng tốc query?

**A**:
1. **Disable BGE rerank**: `ENABLE_BGE_RERANK=false` (save 100-400ms)
2. **Reduce max_context**: 5 instead of 8 (save 20-50ms generation)
3. **Use text-only**: Disable vision (save 200-500ms render)
4. **Cache embeddings**: Query embedding cached (LRU)

### Q: Ingestion có thể parallel không?

**A**: Có, dùng `--workers`:
```powershell
python tools/ingest.py --workers 4  # 4 parallel workers
```
Recommended: workers = CPU cores (but watch RAM usage)

### Q: Index size bao lớn?

**A**: For 150 PDFs (~12,500 chunks):
- **Chunks JSONL**: ~50-100MB
- **Weaviate vectors**: ~200-400MB
- **OpenSearch index**: ~100-200MB
- **Total**: ~400-700MB

### Q: Có caching không?

**A**: Có:
- **Query embeddings**: LRU cache (maxsize=1000)
- **Retrieval results**: TTL cache (5 minutes, maxsize=100)
- **LLM responses**: No caching (always fresh)

---

## 7. FAQ - TROUBLESHOOTING

### Q: API không start được - "Both backends unhealthy"

**A**: Check Docker services:
```powershell
docker ps

# Should see:
# - opensearch-node
# - weaviate-weaviate-1

# Test manually:
curl http://localhost:9200
curl http://localhost:8080/v1/.well-known/ready

# Restart if needed:
docker restart opensearch-node
docker restart weaviate-weaviate-1
```

### Q: Query không trả về kết quả

**A**: Debug steps:
1. Check index stats: `curl http://localhost:8000/index-stats`
2. Check if keyword exists: Search in `chunks.jsonl`
3. Test Weaviate: `python scripts/weaviate/test_weaviate_search.py "query"`
4. Test OpenSearch: `curl http://localhost:9200/rag_chunks/_search?q=query`
5. Check logs: `tail -f artifacts/logs/pvcfc-rag_*.log`

### Q: Confidence score là negative/None - 422 error

**A**:
- **Fixed in v0.6.1**: Defensive clamping
- **Workaround**:
  - Upgrade to v0.6.1+: `git pull && pip install -r requirements.txt --upgrade`
  - Or disable BGE rerank: `ENABLE_BGE_RERANK=false`

### Q: Vision generation fails - "No such file"

**A**: Fix doc_id_map paths:
```powershell
python scripts/utilities/fix_doc_id_map.py \
  --doc-id-map "artifacts/ingestion_production/doc_id_map.json" \
  --pdf-root "D:\\Data_Raw"
```

### Q: Weaviate out of memory

**A**:
- Increase Docker memory: Docker Desktop → Settings → Resources → Memory (4GB+)
- Or reduce batch size: Edit `scripts/phase1_index_to_weaviate.py` → batch_size=100

### Q: OpenSearch index full

**A**: Cleanup:
```powershell
# Delete old index
curl -X DELETE http://localhost:9200/rag_chunks

# Re-create
python scripts/opensearch/create_rag_chunks_index.py
python scripts/opensearch/bulk_insert_to_opensearch.py
```

### Q: Logs quá lớn

**A**: Log rotation:
```powershell
# Manual cleanup (keep last 30 days)
Get-ChildItem "artifacts/logs/*.log" |
  Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} |
  Remove-Item -Force
```

---

## 8. CHEAT SHEET

### 8.1 Most Common Commands

```powershell
# ===== DOCKER =====
# Start all
docker-compose up -d && docker-compose -f docker-compose-weaviate.yml up -d

# Stop all
docker-compose down && docker-compose -f docker-compose-weaviate.yml down

# Check status
docker ps

# Logs
docker logs opensearch-node
docker logs weaviate-weaviate-1

# ===== INGESTION =====
# Full ingestion
python tools/ingest.py \
  --source-dir "D:\\Data_Raw" \
  --output-dir "artifacts\\ingestion_production" \
  --workers 4 \
  --enable-ocr --ocr-lang "vie+eng" \
  --extract-tables \
  --create-version --version-id "v1.0_prod"

# Incremental
python tools/ingest.py \
  --source-dir "D:\\Data_Raw_New" \
  --output-dir "artifacts\\ingestion_v1.1" \
  --create-version --version-id "v1.1_incremental"

# ===== INDEXING =====
# Weaviate
python scripts/phase1_index_to_weaviate.py

# OpenSearch
python scripts/opensearch/create_rag_chunks_index.py
python scripts/opensearch/bulk_insert_to_opensearch.py

# Legacy (FAISS + BM25)
python tools/ops/build_production_indices.py

# ===== API =====
# Start API
.\launchers\start_api.ps1

# Start UI
.\launchers\start_ui.ps1

# Health check
curl http://localhost:8000/healthz

# Index stats
curl http://localhost:8000/index-stats

# ===== QUERY =====
# Simple Q&A
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{"query": "test", "language": "vi", "max_context": 8}'

# With vision
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{"query": "test", "enable_vision_generation": true}'

# With filters
curl -X POST http://localhost:8000/api/ask `
  -H "Content-Type: application/json" `
  -d '{"query": "test", "filters": {"equipment_id": "K06101"}}'

# ===== TESTING =====
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v
python tests/test_hybrid_modern.py

# Smoke tests
python scripts/phase4_rag_integration_test.py

# ===== MAINTENANCE =====
# Backup
Compress-Archive -Path "artifacts\ingestion_production" -DestinationPath "backup_$(Get-Date -Format 'yyyyMMdd').zip"

# Version list
python -c "from app.storage.version_manager import VersionManager; vm = VersionManager('artifacts'); print(vm.list_versions())"

# Rollback
python tools/ops/create_version.py --restore --version-id "v1.0_prod" --target-dir "artifacts/ingestion_production"

# Logs
tail -f artifacts/logs/pvcfc-rag_*.log
Get-Content -Path "artifacts\logs\pvcfc-rag_*.log" -Wait
```

### 8.2 Environment Variables Quick Reference

```ini
# ===== ESSENTIAL =====
APP_ENV=local                      # local|dev|prod
GEMINI_API_KEY=AIza...             # Your Gemini API key

# ===== LLM =====
LLM_PROVIDER=gemini                # gemini|openai|none
LLM_MODEL_HEAVY=gemini-2.5-pro     # For vision/complex queries
LLM_MODEL_LIGHT=gemini-2.5-flash   # For simple queries

# ===== EMBEDDING =====
EMBEDDING_PROVIDER=gemini          # gemini|openai|local
EMBEDDING_MODEL=gemini-embedding-001
EMBED_BATCH_SIZE=256
EMBED_CONCURRENCY=8

# ===== RETRIEVAL MODE =====
USE_HYBRID_MODERN=true             # true: Weaviate+OpenSearch, false: FAISS+BM25

# ===== WEAVIATE =====
WEAVIATE_ENABLED=true
WEAVIATE_HOST=localhost
WEAVIATE_PORT=8080
WEAVIATE_GRPC_PORT=50051
WEAVIATE_USE_GRPC=true
WEAVIATE_COLLECTION=Chunk
WEAVIATE_RETRIEVAL_LIMIT=50

# ===== OPENSEARCH =====
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=rag_chunks
OPENSEARCH_BM25_K1=1.2
OPENSEARCH_BM25_B=0.75

# ===== RERANKING =====
ENABLE_BGE_RERANK=false            # true: Enable BGE CrossEncoder
BGE_RERANK_TOP_K=10
BGE_RERANK_LEVEL=chunk             # chunk|doc|page

# ===== VISION =====
VISION_MAX_PAGES_TOTAL=10
PDF_RENDER_DPI=200
```

### 8.3 File Locations Quick Reference

```
artifacts/
├── ingestion_production/
│   ├── chunks.jsonl                 # Deduplicated chunks
│   ├── doc_id_map.json              # doc_id → pdf_path mapping
│   ├── quarantine.jsonl             # Failed files
│   └── manifests/                   # Ingestion metadata
├── index_production/
│   ├── bm25/                        # BM25 index (legacy)
│   └── faiss/                       # FAISS index (legacy)
├── versions/
│   └── v1.0_prod/                   # Version snapshots
└── logs/
    └── pvcfc-rag_2025-10-12.log     # Application logs

.env                                  # Environment variables
```

### 8.4 Port Quick Reference

```
8000  - API (FastAPI)
8502  - UI (Streamlit)
8080  - Weaviate HTTP
50051 - Weaviate gRPC
9200  - OpenSearch HTTP
5601  - OpenSearch Dashboards
```

### 8.5 Useful Python One-liners

```python
# Check chunks count
python -c "import jsonlines; print(sum(1 for _ in jsonlines.open('artifacts/ingestion_production/chunks.jsonl')))"

# Check doc_id_map
python -c "import json; doc_map = json.load(open('artifacts/ingestion_production/doc_id_map.json')); print(f'Total docs: {len(doc_map)}')"

# List versions
python -c "from app.storage.version_manager import VersionManager; vm = VersionManager('artifacts'); [print(v['version_id'], v['description']) for v in vm.list_versions()]"

# Test embedding
python -c "from app.services.embedding import EmbeddingService; from app.core.config import settings; service = EmbeddingService(settings); vec = service.embed_texts(['test'])[0]; print(f'Dim: {len(vec)}')"

# Check Weaviate stats
python -c "import weaviate; client = weaviate.connect_to_local(); coll = client.collections.get('Chunk'); print(f'Objects: {coll.aggregate.over_all(total_count=True).total_count}'); client.close()"
```

---

## 📚 RELATED DOCUMENTATION

- [PROJECT_MASTERY_GUIDE.md](PROJECT_MASTERY_GUIDE.md) - Comprehensive project guide
- [WORKFLOW_EXAMPLES.md](WORKFLOW_EXAMPLES.md) - Detailed workflow examples
- [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) - Visual architecture
- [MODULE_CATALOG.md](MODULE_CATALOG.md) - Module details

---

## 🔗 USEFUL LINKS

- **Main README**: [../README.md](../README.md)
- **Quick Start**: [../QUICK_START.md](../QUICK_START.md)
- **System Architecture**: [../SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md)
- **Weaviate Setup**: [guides/WEAVIATE_SETUP_GUIDE.md](guides/WEAVIATE_SETUP_GUIDE.md)
- **Manual Testing**: [guides/MANUAL_TESTING_CHECKLIST.md](guides/MANUAL_TESTING_CHECKLIST.md)

---

**Last Updated**: 2025-10-12
**Version**: 1.0.0
**Status**: ✅ Complete

**💡 Pro Tips**:
- Bookmark this page for quick reference
- Use Ctrl+F to search for specific topics
- Check logs first when troubleshooting
- Always backup before major changes
- Test on small dataset before production ingestion
