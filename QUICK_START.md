# 🚀 Quick Start Guide - Hybrid Modern Mode

## ✅ Setup Complete!

**Status:** Ready to launch
**Mode:** Hybrid Modern (Weaviate + OpenSearch BM25)
**Data:** 4,883 documents indexed and ready

---

## 📦 What Was Fixed

1. ✅ Added `opensearch-py==3.0.0` to `.venv`
2. ✅ Updated `requirements.txt` with Phase 5 dependencies
3. ✅ Configured `.env` with all Hybrid Modern variables
4. ✅ Verified OpenSearch index: 4,883 docs
5. ✅ Verified Weaviate collection: Chunk

---

## 🎯 Start the System

### Step 1: Start API Server

```powershell
# Đảm bảo bạn đang trong folder dự án
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"

# Start API
.\launchers\start_api.ps1
```

**Expected Output:**
```
================================================================================
MODERN HYBRID MODE - Weaviate + OpenSearch BM25
================================================================================
Initializing Hybrid Modern Retriever...
Hybrid Modern Retriever initialized: Weaviate(50) + OpenSearch(50) → RRF(k=60) → BGE(False)
  - Weaviate: healthy
  - OpenSearch: 4883 docs
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Step 2: Start UI (New Terminal)

```powershell
# Open a NEW PowerShell terminal
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"

# Activate venv (bạn đã biết cách này)
& "c:/Users/Admin/Desktop/Code - API_LLM_PVCFC/venv/Scripts/Activate.ps1"

# Start UI
.\launchers\start_ui.ps1
```

**Expected Output:**
```
[OK] API is running and healthy
  Environment: local
  LLM Provider: gemini (Ready: True)

Starting Streamlit UI...
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8502
```

---

## 🧪 Quick Test

### Test 1: Health Check

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json
```

**Expected:**
```json
{
  "status": "healthy",
  "app_env": "local",
  "llm_provider": "gemini",
  "llm_provider_ready": true
}
```

### Test 2: Index Stats

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/index-stats" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json
```

**Expected:**
```json
{
  "retriever_type": "hybrid_modern",
  "weaviate": {"status": "healthy", "collection": "Chunk"},
  "opensearch": {"num_documents": 4883, "index_name": "rag_chunks"},
  "config": {"weaviate_limit": 50, "opensearch_limit": 50}
}
```

### Test 3: Search Query

```powershell
$body = @{
  query = "Quy định về lãi suất"
  language = "vi"
  max_context = 5
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8000/api/ask" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
```

---

## 🔍 Troubleshooting

### Issue: ModuleNotFoundError for other packages

**Solution:**
```powershell
# Install from requirements.txt
& "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

### Issue: OpenSearch connection failed

**Check Docker:**
```powershell
docker ps --filter "name=opensearch"
```

**Restart if needed:**
```powershell
docker restart opensearch-node
```

### Issue: Weaviate connection failed

**Check Docker:**
```powershell
docker ps --filter "name=weaviate"
```

**Restart if needed:**
```powershell
docker restart weaviate-weaviate-1
```

### Issue: "Both backends unhealthy"

**This is a CRITICAL error.** Check:

1. Docker services running: `docker ps`
2. OpenSearch: `Invoke-WebRequest -Uri "http://localhost:9200" -UseBasicParsing`
3. Weaviate: `Invoke-WebRequest -Uri "http://localhost:8080/v1/.well-known/ready" -UseBasicParsing`

---

## 📊 What to Expect

### API Startup Time
- First run: ~5-10 seconds (loading models + connecting backends)
- Subsequent runs: ~3-5 seconds

### Search Performance
- Parallel retrieval from Weaviate + OpenSearch: ~100-300ms
- RRF fusion: ~10-20ms
- Total latency: ~200-500ms (depending on network and query complexity)

### Memory Usage
- API process: ~500MB-1GB
- Docker services:
  - OpenSearch: ~2-3GB
  - Weaviate: ~1-2GB

---

## 🎉 Next Steps

Once everything is running:

1. **Open UI**: http://localhost:8502
2. **Try a search**: "Quy định về lãi suất cho vay"
3. **Check citations**: Verify doc_id + page numbers
4. **Review logs**: Check for "hybrid_modern" in startup logs
5. **Monitor stats**: Visit http://localhost:8000/index-stats

---

## 💡 Tips

- **Deactivate venv first** if you activated the wrong one (venv vs .venv)
- **Use `.venv`** (with dot) - that's where launcher looks
- **Check logs** in terminal for any warnings about degraded mode
- **BGE reranking** is disabled by default - enable with `ENABLE_BGE_RERANK=true` if needed

---

## 📞 Support

If you see any errors, check:
1. Terminal output for detailed error messages
2. Docker logs: `docker logs opensearch-node` or `docker logs weaviate-weaviate-1`
3. `.env` file has all variables from `.env.patch`

Enjoy your Modern Hybrid RAG! 🚀
