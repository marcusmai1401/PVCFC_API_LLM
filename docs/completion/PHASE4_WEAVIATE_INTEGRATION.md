# Phase 4: Weaviate Integration Guide

## ✅ Hoàn thành

Phase 4 đã được tích hợp thành công! Hệ thống hiện hỗ trợ **2 chế độ retrieval**:

1. **FAISS Mode (Legacy)** - Hybrid BM25 + FAISS vector search
2. **Weaviate Mode (Phase 4)** - Weaviate vector database với BGE reranking

---

## 🎯 Cấu trúc Code

### Files mới được tạo:
- `app/rag/weaviate_retriever.py` - WeaviateRetriever class với BGE reranking
- `PHASE4_WEAVIATE_INTEGRATION.md` - Tài liệu này

### Files đã được update:
- `app/core/config.py` - Thêm Weaviate configuration
- `app/deps/indices.py` - Hỗ trợ load cả FAISS và Weaviate
- `requirements.txt` - Thêm weaviate-client==4.9.3
- `.env.example` - Thêm Weaviate config mẫu
- `streamlit_app/components/system_status.py` - UI hiển thị Weaviate
- `streamlit_app/components/dashboard.py` - Dashboard hỗ trợ cả 2 mode

---

## ⚙️ Cấu hình

### 1. Chế độ FAISS (Mặc định)

Trong `.env`:
```bash
# Weaviate disabled - dùng FAISS legacy
WEAVIATE_ENABLED=false
```

Hệ thống sẽ load BM25 + FAISS như cũ.

### 2. Chế độ Weaviate (Phase 4)

Trong `.env`:
```bash
# Enable Weaviate mode
WEAVIATE_ENABLED=true

# Weaviate connection
WEAVIATE_HOST=localhost
WEAVIATE_PORT=8080
WEAVIATE_GRPC_PORT=50051
WEAVIATE_USE_GRPC=true

# Collection settings
WEAVIATE_COLLECTION=PVCFCDocuments
WEAVIATE_TIMEOUT=30
WEAVIATE_RETRIEVAL_LIMIT=50

# BGE Reranking (Phase 3)
ENABLE_BGE_RERANK=true
BGE_RERANK_CANDIDATE_LIMIT=50
BGE_RERANK_TOP_K=10
BGE_RERANK_LEVEL=chunk
BGE_RERANK_AGGREGATION=max
```

---

## 🚀 Cách sử dụng

### Bước 1: Cài đặt dependencies

```powershell
pip install -r requirements.txt
```

Dependencies mới:
- `weaviate-client==4.9.3` - Weaviate Python client v4 API

### Bước 2: Setup Weaviate (nếu dùng Weaviate mode)

#### Option A: Docker Compose (Khuyến nghị)

```bash
docker-compose up -d weaviate
```

#### Option B: Standalone Docker

```bash
docker run -d \
  --name weaviate \
  -p 8080:8080 \
  -p 50051:50051 \
  -e QUERY_DEFAULTS_LIMIT=25 \
  -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
  semitechnologies/weaviate:latest
```

### Bước 3: Ingest data vào Weaviate

```powershell
# Tạo script để ingest data vào Weaviate
python scripts/ingest_to_weaviate.py --pdf_dir data/pdfs
```

### Bước 4: Chạy API

```powershell
.\launchers\start_api.ps1
```

API sẽ tự động detect mode (FAISS hoặc Weaviate) dựa trên `WEAVIATE_ENABLED`.

### Bước 5: Chạy UI

```powershell
.\launchers\start_ui.ps1
```

UI sẽ hiển thị:
- **FAISS mode**: "📊 Retrieval: Hybrid BM25 + FAISS (Legacy)"
- **Weaviate mode**: "🔷 Vector Database: Weaviate (Phase 4)"

---

## 🔍 API Endpoints

### Health Check
```bash
GET http://localhost:8000/health
```

Response (Weaviate mode):
```json
{
  "status": "healthy",
  "retriever_type": "weaviate",
  "weaviate_health": {
    "status": "healthy",
    "ready": true,
    "collection": "PVCFCDocuments"
  }
}
```

### Index Stats
```bash
GET http://localhost:8000/index/stats
```

Response (Weaviate mode):
```json
{
  "retriever_type": "weaviate",
  "weaviate": {
    "loaded": true,
    "collection": "PVCFCDocuments",
    "ready": true
  }
}
```

### Ask Question (Unchanged)
```bash
POST http://localhost:8000/ask
Content-Type: application/json

{
  "query": "Giải thích về chuyển đổi số",
  "language": "vi",
  "max_context": 8
}
```

API tự động routing đến đúng retriever (FAISS hoặc Weaviate).

---

## 🧪 Testing

### Test Weaviate Connection

```powershell
# Test health check
curl http://localhost:8000/health

# Test index stats
curl http://localhost:8000/index/stats
```

### Test End-to-End RAG

```powershell
# Query qua API
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Test query", "language": "vi"}'
```

---

## 📊 Architecture

### Weaviate Mode Flow:

```
User Query
    ↓
QueryTransformer
    ↓
EmbeddingService (vectorize query)
    ↓
WeaviateRetriever
    ├─ near_vector search (semantic)
    ├─ metadata filtering
    └─ retrieve top 50 candidates
    ↓
BGE Reranker (if enabled)
    ├─ chunk-level reranking
    ├─ doc-level aggregation
    └─ page-level aggregation
    ↓
Top K results (default: 10)
    ↓
ResponseGenerator (LLM)
    ↓
Final Answer with Citations
```

### FAISS Mode Flow (Legacy):

```
User Query
    ↓
QueryTransformer (+ HyDE)
    ↓
HybridRetriever
    ├─ BM25 keyword search
    ├─ FAISS semantic search
    └─ RRF fusion
    ↓
BGE Reranker (if enabled)
    ↓
ResponseGenerator
    ↓
Answer
```

---

## 🆚 So sánh FAISS vs Weaviate

| Feature | FAISS Mode | Weaviate Mode |
|---------|-----------|---------------|
| **Search** | Hybrid (BM25 + FAISS) | Pure semantic (near_vector) |
| **Scalability** | Limited (in-memory) | High (distributed) |
| **Metadata Filter** | Post-search filtering | Native Weaviate filters |
| **CRUD** | Rebuild index | Real-time updates |
| **Deployment** | Simple (file-based) | Requires Docker/K8s |
| **Performance** | Fast (small datasets) | Fast (large datasets) |
| **BGE Rerank** | ✅ Supported | ✅ Supported |

---

## 🛠️ Troubleshooting

### Lỗi: "Failed to connect to Weaviate"

**Nguyên nhân**: Weaviate chưa chạy hoặc sai config

**Giải pháp**:
```bash
# Check Weaviate đang chạy
docker ps | grep weaviate

# Check logs
docker logs weaviate

# Restart Weaviate
docker restart weaviate
```

### Lỗi: "Collection not found"

**Nguyên nhân**: Collection chưa được tạo trong Weaviate

**Giải pháp**:
```bash
# Chạy script tạo collection
python scripts/create_weaviate_collection.py
```

### Lỗi: "Retriever not initialized"

**Nguyên nhân**: API chưa load xong retriever

**Giải pháp**:
```bash
# Check API logs
tail -f logs/api.log

# Restart API
.\launchers\start_api.ps1
```

---

## 📝 TODO (Future)

- [ ] Script tự động ingest data vào Weaviate
- [ ] Benchmark FAISS vs Weaviate performance
- [ ] Multi-tenancy support trong Weaviate
- [ ] Weaviate backup/restore scripts
- [ ] Monitoring dashboard cho Weaviate metrics

---

## 🎉 Kết luận

Phase 4 đã hoàn thành tích hợp Weaviate với:

✅ WeaviateRetriever class hoàn chỉnh
✅ BGE reranking integration
✅ Graceful fallback handling
✅ UI support cho cả 2 modes
✅ Configuration management
✅ Documentation đầy đủ

**Sẵn sàng để test!** 🚀

```powershell
# Start API
.\launchers\start_api.ps1

# Start UI (tab mới)
.\launchers\start_ui.ps1
```
