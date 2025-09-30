# KẾ HOẠCH HOÀN THIỆN PHASE 2 — CHI TIẾT TỪNG BƯỚC

**Ngày lập kế hoạch**: 2025-09-30
**Mục tiêu**: Đạt 100% DoD theo `Build_plan_README/Build_plan_phase_2.md`
**Thời gian ước tính**: 4-6 giờ (chia 6 tasks)

---

## 📋 Tổng quan

Từ báo cáo kiểm tra Phase 2, còn **~15%** công việc để đạt 100%. Kế hoạch này chia thành **6 tasks chính**, thực hiện tuần tự theo độ ưu tiên.

---

## TASK 1: Bổ sung ENV Variables Phase 2 ✅ CRITICAL

**Thời gian**: 30 phút
**Độ ưu tiên**: ⭐⭐⭐ (Cao nhất)
**Phụ thuộc**: Không

### Mục tiêu
Bổ sung đầy đủ các biến môi trường Phase 2 vào `.env` và `app/core/config.py` để đồng bộ với Build Plan.

### Các biến cần bổ sung

#### 1.1. Retrieval & Context
```ini
# Số đoạn context tối đa đưa vào LLM
MAX_CONTEXT=8

# Số candidates sau rerank (trước khi chọn MAX_CONTEXT)
TOP_RERANK=20
```

#### 1.2. Vision & Text Range Scan
```ini
# Bật Vision page selector (multimodal generation)
VISION_PAGE_SELECTOR_ENABLED=true

# Tắt text-only page range scan (ưu tiên Vision)
TEXT_RANGE_SCAN_ENABLED=false
```

#### 1.3. Degrade Mode
```ini
# Cho phép fallback BM25-only khi embedding/mạng lỗi
RETRIEVAL_ALLOW_BM25_ONLY_FALLBACK=true

# Tăng k BM25 khi degrade
BM25_K_WHEN_DEGRADE=80

# Tăng top rerank khi degrade
RERANK_TOP_N_WHEN_DEGRADE=50
```

#### 1.4. Cache & Performance
```ini
# TTL cho retrieve/rerank cache (phút)
RETRIEVE_CACHE_TTL_MIN=10
```

### Các bước thực hiện

**Bước 1.1**: Cập nhật `.env`
- Mở file `.env`
- Thêm các biến trên vào phần "Phase 2 Configuration" (tạo mới nếu chưa có)
- Save file

**Bước 1.2**: Cập nhật `app/core/config.py`
- Mở file `app/core/config.py`
- Thêm các field vào class `Settings`:
  ```python
  # Phase 2 - Retrieval & Context
  max_context: int = Field(default=8, description="Maximum context chunks for generation")
  top_rerank: int = Field(default=20, description="Top candidates after reranking")

  # Phase 2 - Vision & Text Range
  vision_page_selector_enabled: bool = Field(default=True, description="Enable Vision page selector")
  text_range_scan_enabled: bool = Field(default=False, description="Enable text-only page range scan")

  # Phase 2 - Degrade Mode
  retrieval_allow_bm25_only_fallback: bool = Field(default=True, description="Allow BM25-only fallback")
  bm25_k_when_degrade: int = Field(default=80, description="BM25 k when in degrade mode")
  rerank_top_n_when_degrade: int = Field(default=50, description="Rerank top N when in degrade mode")

  # Phase 2 - Cache
  retrieve_cache_ttl_min: int = Field(default=10, description="Retrieve cache TTL in minutes")
  ```

**Bước 1.3**: Test config loading
```powershell
# Verify settings load correctly
python -c "from app.core.config import settings; print(f'MAX_CONTEXT={settings.max_context}, VISION={settings.vision_page_selector_enabled}')"
```

### Acceptance Criteria (DoD)
- [ ] Tất cả 8 biến ENV mới có trong `.env`
- [ ] Tất cả 8 field mới có trong `Settings` class
- [ ] Test command chạy không lỗi và hiển thị giá trị đúng
- [ ] Git commit: "feat(config): Add Phase 2 ENV variables"

---

## TASK 2: Implement/Verify Degrade BM25-only Fallback 🔍 HIGH

**Thời gian**: 1.5 giờ
**Độ ưu tiên**: ⭐⭐⭐ (Cao)
**Phụ thuộc**: TASK 1 (cần ENV variables)

### Mục tiêu
Đảm bảo retriever có thể fallback sang BM25-only khi FAISS/embedding lỗi, và ghi đầy đủ meta/log.

### Các bước thực hiện

**Bước 2.1**: Kiểm tra code hiện tại trong `app/rag/retriever.py`
- Đọc method `search()` hoặc `retrieve()`
- Tìm xem có try-except xung quanh FAISS call không
- Kiểm tra có log degrade_mode không

**Bước 2.2**: Implement degrade logic (nếu chưa có)

Thêm vào `HybridRetriever` class:

```python
def search(
    self,
    query: TransformedQuery,
    k: Optional[int] = None,
    degrade_mode: bool = False
) -> List[RetrievalResult]:
    """
    Hybrid search with BM25-only fallback on FAISS errors
    """
    from app.core.config import settings

    # Load degrade settings
    allow_fallback = settings.retrieval_allow_bm25_only_fallback
    bm25_k = k or settings.max_context

    results = []
    faiss_failed = False
    degrade_reason = None

    # Try BM25 (always works)
    try:
        bm25_results = self.bm25_retriever.search(query.normalized, k=bm25_k)
        results.extend(bm25_results)
        logger.info(f"BM25 retrieved {len(bm25_results)} results")
    except Exception as e:
        logger.error(f"BM25 search failed: {e}")
        # Critical: BM25 should not fail
        raise

    # Try FAISS (may fail)
    try:
        faiss_results = self.faiss_retriever.search(query.normalized, k=bm25_k)
        results.extend(faiss_results)
        logger.info(f"FAISS retrieved {len(faiss_results)} results")
    except Exception as e:
        faiss_failed = True
        degrade_reason = str(e)

        if allow_fallback:
            # Degrade mode: increase BM25 k
            bm25_k_degrade = settings.bm25_k_when_degrade
            logger.warning(
                f"FAISS failed ({degrade_reason}), falling back to BM25-only "
                f"with k={bm25_k_degrade}"
            )
            try:
                # Re-fetch with higher k
                results = self.bm25_retriever.search(query.normalized, k=bm25_k_degrade)
            except Exception as e2:
                logger.error(f"BM25 fallback also failed: {e2}")
                raise
        else:
            # No fallback allowed, propagate error
            logger.error(f"FAISS failed and fallback disabled: {e}")
            raise

    # Merge and deduplicate results
    merged = self._merge_results(results)

    # Attach degrade metadata
    if faiss_failed:
        for r in merged:
            if not hasattr(r, 'metadata'):
                r.metadata = {}
            r.metadata['degrade_mode'] = True
            r.metadata['degrade_reason'] = degrade_reason

    return merged
```

**Bước 2.3**: Update `/ask` router để ghi degrade meta

Trong `app/api/routers/ask.py`, sau khi retrieve:

```python
# Check if any result has degrade_mode
degrade_mode = any(
    getattr(r, 'metadata', {}).get('degrade_mode', False)
    for r in retrieval_results
)
degrade_reason = None
if degrade_mode:
    for r in retrieval_results:
        if r.metadata.get('degrade_mode'):
            degrade_reason = r.metadata.get('degrade_reason')
            break

# Add to response meta later
meta['degrade_mode'] = degrade_mode
if degrade_reason:
    meta['degrade_reason'] = degrade_reason
```

**Bước 2.4**: Test degrade mode manually

Tạo test script `test_degrade_mode.py`:

```python
"""
Test degrade mode by temporarily disabling FAISS
"""
import os
os.environ["FAISS_INDEX_DIR"] = "/nonexistent/path"  # Force FAISS to fail

from app.core.config import settings
from app.rag.retriever import HybridRetriever

# Try to search
retriever = HybridRetriever(...)
results = retriever.search(query="test")

# Check degrade metadata
assert any(r.metadata.get('degrade_mode') for r in results)
print("✅ Degrade mode works!")
```

### Acceptance Criteria (DoD)
- [ ] Retriever có try-except xung quanh FAISS call
- [ ] Khi FAISS lỗi → fallback BM25-only với k_degrade
- [ ] Log ghi rõ "falling back to BM25-only with k=80"
- [ ] Metadata có `degrade_mode=True`, `degrade_reason`
- [ ] Test manual pass (hoặc unit test)
- [ ] Git commit: "feat(retrieval): Implement BM25-only degrade fallback"

---

## TASK 3: Bổ sung Meta Fields đầy đủ trong `/ask` Response 📊 HIGH

**Thời gian**: 1 giờ
**Độ ưu tiên**: ⭐⭐⭐ (Cao)
**Phụ thuộc**: TASK 1, TASK 2

### Mục tiêu
Response meta của `/ask` phải chứa đầy đủ các field theo DoD Phase 2.

### Các field cần bổ sung

Theo `Build_plan_phase_2.md`, meta cần có:

```json
{
  "meta": {
    // Existing (đã có)
    "latency_ms": 1430,
    "breakdown": {...},
    "k": 8,
    "execution_mode": "production",
    "trace_id": "xyz789",
    "model_generation": "gemini-2.5-pro",
    "model_query_transform": "gemini-2.5-flash",
    "embed_model": "gemini-embedding-001",

    // NEW - cần bổ sung
    "degrade_mode": false,
    "degrade_reason": null,
    "bm25_k_current": 50,
    "top_rerank_current": 20,
    "vision_page_selector_enabled": true,
    "text_range_scan_enabled": false,
    "cache_hit": false,  // Phase sau implement cache mới có

    "vision_generation": {
      "pages_used": [...],
      "pages_failed": [],
      "excerpts": []
    }
  }
}
```

### Các bước thực hiện

**Bước 3.1**: Mở `app/api/routers/ask.py`

**Bước 3.2**: Sau bước Generation, before building response, thêm meta fields:

```python
# Collect meta information
from app.core.config import settings

# Determine current k values (may be different if degrade)
bm25_k_current = settings.bm25_k_when_degrade if degrade_mode else (
    request.max_context  # hoặc k default
)
top_rerank_current = settings.rerank_top_n_when_degrade if degrade_mode else (
    settings.top_rerank
)

# Build comprehensive meta
meta = {
    "latency_ms": round(total_latency),
    "breakdown": timing_breakdown,
    "k": request.max_context,
    "execution_mode": request.execution_mode,
    "trace_id": trace_id,

    # Model info
    "model_generation": generator.config.llm_tier,  # or specific model name
    "model_query_transform": "gemini-2.5-flash",  # or from config
    "embed_model": settings.embedding_model,

    # Degrade info
    "degrade_mode": degrade_mode,
    "degrade_reason": degrade_reason if degrade_mode else None,

    # Current k values
    "bm25_k_current": bm25_k_current,
    "top_rerank_current": top_rerank_current,

    # Feature flags
    "vision_page_selector_enabled": settings.vision_page_selector_enabled,
    "text_range_scan_enabled": settings.text_range_scan_enabled,

    # Cache (placeholder for now)
    "cache_hit": False,  # TODO: implement in TASK 5

    # Vision metadata (if available)
    "vision_generation": getattr(generated_answer, 'vision_metadata', {
        "pages_used": [],
        "pages_failed": [],
        "excerpts": []
    })
}
```

**Bước 3.3**: Update AskResponse schema nếu cần

Check `app/rag/schemas.py` xem AskResponse có field `meta: Dict[str, Any]` chưa.

**Bước 3.4**: Test với curl/Postman

```powershell
$body = @{
    query = "Test query"
    language = "vi"
    max_context = 8
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/ask" `
    -Method Post `
    -ContentType 'application/json' `
    -Body $body | ConvertTo-Json -Depth 10
```

Verify response có đầy đủ meta fields.

### Acceptance Criteria (DoD)
- [ ] Response meta có tất cả 14 fields (theo danh sách trên)
- [ ] `degrade_mode` reflect đúng trạng thái
- [ ] `bm25_k_current` thay đổi khi degrade
- [ ] Feature flags (`vision_page_selector_enabled`, etc.) đọc từ settings
- [ ] Test curl/Postman verify đầy đủ fields
- [ ] Git commit: "feat(api): Add comprehensive meta fields to /ask response"

---

## TASK 4: Verify & Polish Vision Gating Logic 🖼️ MEDIUM

**Thời gian**: 45 phút
**Độ ưu tiên**: ⭐⭐ (Trung bình)
**Phụ thuộc**: TASK 1

### Mục tiêu
Đảm bảo Vision generation có logging rõ ràng và behavior đúng theo spec.

### Các bước thực hiện

**Bước 4.1**: Đọc `app/rag/generator.py` phần Vision

Tìm đoạn code quyết định Vision ON/OFF (gating).

**Bước 4.2**: Verify logging format

Theo DoD, cần log:
- Khi OFF: `"Vision gating: OFF (reason=no_docs_or_mapping)"`
- Khi ON: `"Vision gating: ON (config enabled)"`
- Khi render: `"Vision pages: used=X, failed=Y, total_limit=10; pages=[...]"`

**Bước 4.3**: Thêm/sửa logging nếu chưa có

```python
# In generator.py, trong method _generate_with_vision hoặc tương tự

if not retrieved_docs:
    logger.info("Vision gating: OFF (reason=no_retrieved_docs)")
    return self._generate_text_only(...)

doc_id_map = _get_doc_id_map()
if not doc_id_map:
    logger.info("Vision gating: OFF (reason=no_doc_id_mapping)")
    return self._generate_text_only(...)

if not self.config.enable_vision_generation:
    logger.info("Vision gating: OFF (reason=config_disabled)")
    return self._generate_text_only(...)

logger.info("Vision gating: ON (config enabled)")

# ... render pages ...

logger.info(
    f"Vision pages: used={len(pages_used)}, failed={len(pages_failed)}, "
    f"total_limit={VISION_MAX_PAGES}, pages={[p['page'] for p in pages_used]}"
)
```

**Bước 4.4**: Test với/không có doc_id_map.json

```powershell
# Test 1: Có doc_id_map.json (Vision ON)
# Normal API call → check log

# Test 2: Rename doc_id_map.json tạm thời (Vision OFF)
Rename-Item artifacts/ingestion/doc_id_map.json doc_id_map.json.bak
# API call → verify log "Vision gating: OFF (reason=no_doc_id_mapping)"
# Restore
Rename-Item artifacts/ingestion/doc_id_map.json.bak doc_id_map.json
```

**Bước 4.5**: Verify cache pages directory

Check xem có `artifacts/cache/pdf_pages/` được tạo khi render không.

### Acceptance Criteria (DoD)
- [ ] Log "Vision gating: ON/OFF" với reason rõ ràng
- [ ] Log "Vision pages: used=..., failed=..." khi render
- [ ] Test với doc_id_map.json missing → Vision OFF
- [ ] Test với doc_id_map.json present + enable_vision_generation=true → Vision ON
- [ ] Cache directory được tạo khi render pages
- [ ] Git commit: "chore(generator): Polish Vision gating logs"

---

## TASK 5: Implement Retrieval Cache Layer 🗄️ MEDIUM

**Thời gian**: 2 giờ
**Độ ưu tiên**: ⭐⭐ (Trung bình - có thể defer)
**Phụ thuộc**: TASK 1

### Mục tiêu
Cache kết quả retrieval + rerank để giảm latency cho queries trùng lặp.

### Strategy
Dùng `cachetools.TTLCache` (đã có trong requirements) hoặc Redis (nếu có).

### Các bước thực hiện

**Bước 5.1**: Tạo cache manager

Tạo file mới `app/core/cache_manager.py`:

```python
"""
Cache manager for retrieval results
"""
import hashlib
import json
from typing import Any, Optional
from cachetools import TTLCache
from loguru import logger

class RetrievalCache:
    """LRU cache with TTL for retrieval results"""

    def __init__(self, maxsize: int = 1000, ttl: int = 600):
        """
        Args:
            maxsize: Maximum cache entries
            ttl: Time-to-live in seconds (default 10 minutes)
        """
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        logger.info(f"RetrievalCache initialized: maxsize={maxsize}, ttl={ttl}s")

    def _make_key(self, query: str, filters: dict = None, k: int = 8) -> str:
        """Generate cache key from query + filters + k"""
        key_dict = {
            "query": query.strip().lower(),
            "filters": filters or {},
            "k": k
        }
        key_str = json.dumps(key_dict, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    def get(self, query: str, filters: dict = None, k: int = 8) -> Optional[Any]:
        """Get cached results"""
        key = self._make_key(query, filters, k)
        result = self.cache.get(key)
        if result:
            logger.debug(f"Cache HIT for key={key}")
        return result

    def set(self, query: str, results: Any, filters: dict = None, k: int = 8):
        """Set cache results"""
        key = self._make_key(query, filters, k)
        self.cache[key] = results
        logger.debug(f"Cache SET for key={key}, size={len(self.cache)}")

    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        logger.info("Cache cleared")

# Global cache instance
_retrieval_cache: Optional[RetrievalCache] = None

def get_retrieval_cache() -> RetrievalCache:
    """Get or create global retrieval cache"""
    global _retrieval_cache
    if _retrieval_cache is None:
        from app.core.config import settings
        ttl_seconds = settings.retrieve_cache_ttl_min * 60
        _retrieval_cache = RetrievalCache(maxsize=1000, ttl=ttl_seconds)
    return _retrieval_cache
```

**Bước 5.2**: Integrate cache vào `/ask` router

Trong `app/api/routers/ask.py`, sau query transform:

```python
# Try cache first
from app.core.cache_manager import get_retrieval_cache

cache = get_retrieval_cache()
cache_key_data = (
    transformed_query.normalized,
    request.filters.dict() if request.filters else {},
    request.max_context
)

cached_results = cache.get(*cache_key_data)
cache_hit = cached_results is not None

if cache_hit:
    logger.info(f"[{trace_id}] Cache HIT - skipping retrieval")
    reranked_results = cached_results
    retrieve_time = 0
    rerank_time = 0
else:
    # Normal retrieval + rerank
    retrieve_start = time.time()
    retrieval_results = retriever.search(transformed_query)
    retrieve_time = (time.time() - retrieve_start) * 1000

    rerank_start = time.time()
    reranked_results = reranker.rerank(query=request.query, results=retrieval_results)
    reranked_results = reranked_results[:request.max_context]
    rerank_time = (time.time() - rerank_start) * 1000

    # Cache results
    cache.set(*cache_key_data, results=reranked_results)
    logger.info(f"[{trace_id}] Cache MISS - cached {len(reranked_results)} results")
```

**Bước 5.3**: Add cache_hit to meta

```python
meta['cache_hit'] = cache_hit
```

**Bước 5.4**: Test cache behavior

```powershell
# Call 1: Cache MISS
Invoke-RestMethod ... # Check log "Cache MISS"

# Call 2: Same query → Cache HIT
Invoke-RestMethod ... # Check log "Cache HIT", faster latency
```

### Acceptance Criteria (DoD)
- [ ] `RetrievalCache` class hoạt động với TTL
- [ ] `/ask` check cache trước khi retrieve
- [ ] Cache key dựa trên query + filters + k
- [ ] Meta có `cache_hit: true/false`
- [ ] Test 2 calls liên tiếp → lần 2 cache hit
- [ ] Git commit: "feat(cache): Implement retrieval cache with TTL"

**GHI CHÚ**: Task này có thể defer nếu time ngắn. Không ảnh hưởng core functionality.

---

## TASK 6: Add Rate-Limit Headers & Final Polish 🎨 LOW

**Thời gian**: 30 phút
**Độ ưu tiên**: ⭐ (Thấp - nice to have)
**Phụ thuộc**: Không

### Mục tiêu
Thêm `X-RateLimit-*` headers vào response (tuỳ chọn theo DoD).

### Các bước thực hiện

**Bước 6.1**: Mở `app/core/rate_limit.py`

**Bước 6.2**: Update middleware để thêm headers

```python
# In RateLimitMiddleware.dispatch()

# After checking rate limit, add headers to response
response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
response.headers["X-RateLimit-Remaining"] = str(remaining_requests)
response.headers["X-RateLimit-Reset"] = str(int(reset_time))
```

**Bước 6.3**: Test headers

```powershell
$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/ask" -Method Post -Body ...
$response.Headers
# Verify có X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
```

### Acceptance Criteria (DoD)
- [ ] Response có header `X-RateLimit-Limit`
- [ ] Response có header `X-RateLimit-Remaining`
- [ ] Response có header `X-RateLimit-Reset` (timestamp)
- [ ] Test curl verify headers present
- [ ] Git commit: "feat(rate-limit): Add X-RateLimit-* response headers"

---

## 📝 CHECKLIST TỔNG HỢP (Phase 2 - 100% DoD)

Sau khi hoàn thành 6 tasks trên, verify:

### Core Functionality
- [x] Pipeline RAG hoàn chỉnh (QueryTransform → Retrieve → Rerank → Generate)
- [x] Hybrid Retrieval (BM25 + FAISS)
- [x] Rerank: CE cho EN, score fallback cho VI
- [x] Generation: multi-intent (ASK/EXPLAIN/LOCATE/REPORT)
- [x] Vision multimodal generation
- [x] Citations 1-based với doc_id + page

### ENV & Config
- [ ] Tất cả ENV variables Phase 2 có trong `.env` (TASK 1)
- [ ] Settings class load đầy đủ config (TASK 1)

### Degrade & Resilience
- [ ] Degrade BM25-only hoạt động khi FAISS lỗi (TASK 2)
- [ ] Meta ghi `degrade_mode`, `degrade_reason` (TASK 2)
- [ ] k tăng lên theo `BM25_K_WHEN_DEGRADE` (TASK 2)

### Telemetry & Observability
- [ ] Meta response đầy đủ 14+ fields (TASK 3)
- [ ] Timing breakdown (transform/retrieve/rerank/generate)
- [ ] Vision gating logs rõ ràng (TASK 4)
- [ ] Logging mask secrets, giới hạn snippet dài

### Cache & Performance
- [ ] Retrieval cache với TTL (TASK 5 - optional)
- [ ] Meta có `cache_hit` flag (TASK 5 - optional)

### API Polish
- [ ] Rate-limit headers (TASK 6 - optional)
- [ ] Trace-ID trong mọi request
- [ ] Error handling đầy đủ

### Testing
- [ ] Test manual với query VI → rerank fallback
- [ ] Test degrade mode (FAISS disabled)
- [ ] Test Vision ON/OFF
- [ ] Test cache hit/miss (if implemented)

---

## 🚀 EXECUTION ROADMAP

### Session 1 (Today - 2 giờ)
1. ✅ TASK 1: ENV Variables (30 min) — **BẮT ĐẦU TỪ ĐÂY**
2. ✅ TASK 2: Degrade Fallback (1.5 giờ)

### Session 2 (Tomorrow - 2 giờ)
3. ✅ TASK 3: Meta Fields (1 giờ)
4. ✅ TASK 4: Vision Logging (45 min)

### Session 3 (Optional - 2.5 giờ)
5. ⚪ TASK 5: Cache Layer (2 giờ) — defer nếu time ngắn
6. ⚪ TASK 6: Rate-Limit Headers (30 min) — nice to have

---

## 📊 PROGRESS TRACKING

| Task | Status | Time Spent | Notes |
|------|--------|------------|-------|
| TASK 1: ENV Variables | ⬜ TODO | 0/30 min | |
| TASK 2: Degrade Fallback | ⬜ TODO | 0/90 min | |
| TASK 3: Meta Fields | ⬜ TODO | 0/60 min | |
| TASK 4: Vision Logging | ⬜ TODO | 0/45 min | |
| TASK 5: Cache Layer | ⬜ TODO | 0/120 min | Optional |
| TASK 6: Rate-Limit Headers | ⬜ TODO | 0/30 min | Optional |

**Legend**: ⬜ TODO | 🟦 IN PROGRESS | ✅ DONE | ⚪ SKIPPED

---

## 🎯 FINAL DELIVERABLES

Khi hoàn thành, bạn sẽ có:

1. ✅ **File cập nhật**:
   - `.env` (đầy đủ Phase 2 vars)
   - `app/core/config.py` (Settings class mới)
   - `app/rag/retriever.py` (degrade logic)
   - `app/api/routers/ask.py` (meta fields đầy đủ)
   - `app/rag/generator.py` (Vision logging polish)
   - `app/core/cache_manager.py` (NEW - cache layer)
   - `app/core/rate_limit.py` (headers)

2. ✅ **Test results**:
   - Manual test degrade mode
   - Manual test Vision ON/OFF
   - Manual test cache hit/miss
   - Curl/Postman collection với full meta response

3. ✅ **Documentation**:
   - `CHANGLOG_README/Phase2_Final_Report.md` (tạo sau khi xong)
   - Git commits rõ ràng cho từng task

4. ✅ **Validation**:
   - Phase 2 checklist 100% ✅
   - DoD Build_plan_phase_2.md satisfied
   - Ready for production

---

## 💡 TIPS & BEST PRACTICES

- **Commit thường xuyên**: Mỗi task xong → 1 commit rõ ràng
- **Test ngay**: Đừng chờ đến cuối mới test
- **Log everything**: Degrade events, Vision gating, cache hits → đều cần log
- **Fallback gracefully**: Mọi lỗi đều có fallback, không crash API
- **Document decisions**: Nếu skip task nào, ghi lý do vào doc

---

**SẴN SÀNG BẮT ĐẦU?** 🚀

Chúng ta sẽ bắt đầu với **TASK 1: Bổ sung ENV Variables** — foundation cho tất cả tasks còn lại!
