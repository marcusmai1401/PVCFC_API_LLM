# Embedding Model Configuration Note

**Date**: 2025-10-04
**Current Model**: `gemini-embedding-001` (768 dimensions)

---

## ✅ Current Configuration

### Model Details
- **Provider**: Google AI Studio (Gemini)
- **Model**: `gemini-embedding-001` (alias: `models/embedding-001`)
- **Released**: August 2024
- **Output Dimension**: 768 (fixed, not configurable)
- **Task Types**:
  - `RETRIEVAL_DOCUMENT` (for indexing)
  - `RETRIEVAL_QUERY` (for search)

### Environment Settings (.env)
```ini
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
EMBED_OUTPUT_DIM=768
EMBED_BATCH_SIZE=256
EMBED_CONCURRENCY=8
```

---

## 📋 Usage in System

### 1. **Building Embeddings** (Offline)
When building page embeddings or FAISS indices:
- Uses: `gemini-embedding-001`
- Task type: `RETRIEVAL_DOCUMENT`
- Dimension: 768

### 2. **Query Embeddings** (Runtime)
When user submits a query:
- Uses: `gemini-embedding-001` (same model from `.env`)
- Task type: `RETRIEVAL_QUERY`
- Dimension: 768

### 3. **Code Implementation**
- Service: `app/services/embedding_enhanced.py`
- Model resolution: `MODEL_ALIASES` dictionary
- Settings: Reads from `settings.embedding_model` (from `.env`)

---

## ⚠️ Important Notes

### Model Aliases
The following aliases are supported in code:
```python
MODEL_ALIASES = {
    "gemini-embedding-001": "models/embedding-001",  # ✅ CURRENT
    "embedding-001": "models/embedding-001",
    "text-embedding-004": "models/text-embedding-004",  # Older model
}
```

### Why NOT text-embedding-004?
- `text-embedding-004` is an **older model** (pre-Aug 2024)
- `gemini-embedding-001` is the **newer, recommended model** (Aug 2024)
- Both output 768 dimensions
- We use `gemini-embedding-001` for better quality

### Dimension Clarification
- **Correct**: 768 dimensions (fixed)
- **Incorrect**: ~~1536 dimensions~~ (this was a documentation error)
- The 1536D is for OpenAI's `text-embedding-3-large`, NOT Gemini models

---

## 🔍 Verification

### Check Current Model in Logs
When embedding service starts, you'll see:
```
Initialized Gemini embedding model: models/embedding-001 (resolved from gemini-embedding-001), output_dim=768
```

### Confirm Model Usage
Both document embedding and query embedding use the SAME model:
- ✅ Document embedding: `gemini-embedding-001` with task=`RETRIEVAL_DOCUMENT`
- ✅ Query embedding: `gemini-embedding-001` with task=`RETRIEVAL_QUERY`

---

## 📌 Summary

**Current Status**: ✅ Correctly configured
- Model: `gemini-embedding-001` (768D)
- Usage: Consistent across all embedding operations
- Settings: Defined in `.env`

**No Action Required**: System is properly configured.
