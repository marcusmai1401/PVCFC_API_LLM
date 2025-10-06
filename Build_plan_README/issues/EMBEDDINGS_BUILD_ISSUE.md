# Page Embeddings Build Issue

**Date**: 2025-01-03
**Status**: ⚠️ Blocked by dependency issue
**Impact**: Medium (can use dummy embeddings for testing)

---

## ISSUE DESCRIPTION

Cannot build production page embeddings with local provider (sentence-transformers) due to circular import error in `transformers` package.

### Error Details

```
ImportError: cannot import name 'PreTrainedModel' from 'transformers'
```

**Root Cause**: Compatibility issue between:
- `sentence-transformers` 3.0.1
- `transformers` 4.56.1

**Location**:
```python
File ".../transformers/integrations/integration_utils.py", line 44
from .. import PreTrainedModel, TrainingArguments
```

---

## CURRENT STATE

### Embeddings Status
✅ **File exists**: `artifacts/ingestion_production/page_embeddings.npz`
✅ **Size**: 253KB
✅ **Content**: 4004 pages × 16 dims
⚠️ **Provider**: `local` (unit-test)
⚠️ **Model**: `unit-test` (dummy embeddings)

### Validation
```bash
$ python rag_cli.py validate
✓ PASS Page Embeddings: 4004 pages x 16 dims
```

The dummy embeddings pass validation and are **sufficient for integration testing**.

---

## WORKAROUNDS

### Option 1: Use Dummy Embeddings for Testing ✅ CHOSEN
**Status**: ✅ Implemented
**Pros**:
- No additional work needed
- Already validated
- Good for testing integration logic
- Page reranker can handle dummy embeddings

**Cons**:
- Not production-quality results
- Lower semantic accuracy

**Decision**: Proceed with integration using dummy embeddings. Build real embeddings later.

---

### Option 2: Fix transformers Dependency
**Status**: ⏳ Future work
**Steps**:
1. Try downgrading transformers:
   ```bash
   pip install transformers==4.40.0  # Known compatible version
   ```
2. Or upgrade sentence-transformers:
   ```bash
   pip install --upgrade sentence-transformers
   ```
3. Test compatibility matrix

**Risk**: May break other dependencies (Gemini, FAISS, etc.)

---

### Option 3: Use Gemini Provider
**Status**: ⏳ Future work (requires API key)
**Command**:
```bash
# Set API key in .env
GEMINI_API_KEY=your_key_here

# Build with Gemini
python rag_cli.py build-embeddings --provider gemini --model text-embedding-004
```

**Pros**:
- No local dependency issues
- High-quality embeddings (768 dims)
- Official Google model

**Cons**:
- Requires API key
- API quota limits
- Network dependency

---

## VERIFICATION COMMANDS

### Check Current Embeddings
```bash
python -c "import numpy as np; data = np.load('artifacts/ingestion_production/page_embeddings.npz', allow_pickle=True); print('Shape:', data['embeddings'].shape); print('Provider:', data['provider'].item()); print('Model:', data['model'].item())"
```

**Expected Output**:
```
Shape: (4004, 16)
Provider: local
Model: unit-test
```

### Validate System
```bash
python rag_cli.py validate
```

**Expected**: All checks pass including page embeddings.

### Test Page Reranker with Dummy Embeddings
```python
from app.rag.page_reranker import get_page_reranker

reranker = get_page_reranker()
pages = reranker.rank_pages_for_doc(
    query="operating pressure",
    doc_id="DOCID_003_...",  # Real doc_id from index
    top_k=5
)
print(f"Found {len(pages)} pages")
```

---

## IMPACT ON INTEGRATION

### ✅ No Blocker for Integration
- Dummy embeddings work with page reranker
- Semantic scoring fallback to BM25 works
- Integration testing can proceed
- Real embeddings can be added later without code changes

### Testing Strategy
1. **Phase 1**: Integrate HybridRetriever with page reranking using dummy embeddings
2. **Phase 2**: Test with BM25-only mode (semantic disabled)
3. **Phase 3**: Fix transformers issue or use Gemini
4. **Phase 4**: Rebuild real embeddings
5. **Phase 5**: Retest with production embeddings

---

## RESOLUTION PLAN

### Immediate (Next 1-2 hours)
✅ **Proceed with integration** using dummy embeddings
✅ **Document workaround** (this file)
✅ **Test page reranking** with BM25-only mode first

### Short-term (Next day)
⏳ **Fix transformers issue**:
- Test transformers version downgrade
- Or contact repo maintainers for fix
- Or use Gemini provider

⏳ **Rebuild embeddings** with real model

### Long-term (Future)
⏳ **Add embedding health check** to validate command
⏳ **Add fallback mechanism** if embeddings fail to load
⏳ **Document production deployment** with Gemini embeddings

---

## RELATED FILES

- **Config**: `app/config/pipeline_config.py` (lines 155-166)
- **Builder**: `tools/build_page_embeddings.py`
- **Service**: `app/services/embedding_enhanced.py` (lines 131-143)
- **CLI**: `rag_cli.py` (lines 215-246)
- **Reranker**: `app/rag/page_reranker.py` (lazy loads embeddings)

---

## DECISION

**✅ Proceed with integration using dummy embeddings**

**Rationale**:
1. Dummy embeddings are sufficient for testing integration logic
2. Page reranker has BM25 fallback when semantic fails
3. Real embeddings can be added later without code changes
4. Unblocks critical integration work
5. Transformers fix is independent task

**Next Step**: Implement HybridRetriever integration as designed in `INTEGRATION_POINTS_ANALYSIS.md`.

---

**Status**: ⏳ Integration proceeds, embeddings to be fixed separately
