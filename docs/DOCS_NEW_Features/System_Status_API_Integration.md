# System Status API Integration - Technical Documentation

**Date:** 2025-09-29
**Author:** AI Assistant
**Status:** ✅ Completed & Tested

---

## 📋 Overview

Đã hoàn thành việc tích hợp **System Status Component** trong Streamlit UI với backend API endpoints, loại bỏ hoàn toàn các local imports không đáng tin cậy và thay thế bằng API-based health checks.

## 🎯 Objectives

### Đã đạt được:
- ✅ Sử dụng `/healthz` và `/index-stats` endpoints để lấy status thực tế từ backend
- ✅ Hiển thị status đáng tin cậy phản ánh runtime state của backend
- ✅ Xử lý đầy đủ trường hợp backend không available (timeout, connection error)
- ✅ Loại bỏ local imports trong component status checks
- ✅ Implement caching thông minh để giảm API calls

## 🔧 Technical Implementation

### Backend API Endpoints

#### 1. `/healthz` - Health Check
**Location:** `app/api/routers/health.py`

**Response Structure:**
```json
{
  "status": "healthy",
  "app_env": "local",
  "version": "0.2.0",
  "commit_sha": "abc123",
  "uptime_seconds": 3600,
  "uptime_human": "1h 0m 0s",
  "llm_provider": "groq",
  "llm_provider_ready": true,
  "timestamp": "2025-09-29T10:00:00Z"
}
```

**Key Metrics:**
- ✅ API availability
- ✅ LLM provider status
- ✅ Application uptime
- ✅ Environment information

#### 2. `/index-stats` - Index Statistics
**Location:** `app/main.py` → calls `IndexManager.get_index_stats()`

**Response Structure (Format 1 - Retriever Stats):**
```json
{
  "bm25_documents": 150,
  "faiss_documents": 150,
  "config": {
    "k_bm25": 10,
    "k_faiss": 10,
    "use_hyde": true
  }
}
```

**Response Structure (Format 2 - Index Manager Stats):**
```json
{
  "bm25": {
    "loaded": true,
    "doc_count": 150,
    "chunk_count": 500
  },
  "faiss": {
    "loaded": true,
    "vector_count": 500,
    "dimension": 768
  },
  "metadata": {
    "created_at": "2025-09-29T10:00:00Z",
    "source": "ingestion_v1"
  }
}
```

**Key Metrics:**
- ✅ BM25 index status & document count
- ✅ FAISS index status & vector count
- ✅ Retriever configuration
- ✅ Index metadata

### Frontend Implementation

#### File: `streamlit_app/components/system_status.py`

**Functions:**

##### 1. `fetch_health_status(api_base_url, timeout=5)`
```python
def fetch_health_status(api_base_url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Fetch health status from /healthz endpoint

    Returns:
        {
            "success": bool,
            "data": dict,  # response JSON if success
            "response_time_ms": float,
            "error": str  # error message if failed
        }
    """
```

**Error Handling:**
- ✅ `requests.exceptions.Timeout` → "Request timeout"
- ✅ `requests.exceptions.ConnectionError` → "Connection failed"
- ✅ Generic `Exception` → Error message string

##### 2. `fetch_index_stats(api_base_url, timeout=5)`
```python
def fetch_index_stats(api_base_url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Fetch index statistics from /index-stats endpoint

    Returns: Same structure as fetch_health_status()
    """
```

**Error Handling:** Same as `fetch_health_status()`

##### 3. `render_system_status(api_base_url=None)`
Main UI component rendering function.

**Features:**
- 🔄 Refresh button để update status
- 💾 Cache mechanism via `st.session_state.system_status_cache`
- 📊 Display health metrics (status, env, version, uptime)
- 📊 Display index statistics (BM25/FAISS counts)
- 🔧 Component status based on API responses (no local imports)

**Component Status Logic:**

**RAG Retriever:**
```python
# Based on index stats
if has_bm25 or has_faiss:
    ✅ "RAG Retriever" - Ready
    Shows: "BM25: ✓ | FAISS: ✓"
else:
    ⚠️ "RAG Retriever" - No indices loaded
```

**RAG Generator:**
```python
# Based on health check
if llm_provider_ready:
    ✅ "RAG Generator" - Ready
    Shows: "LLM: groq"
else:
    ⚠️ "RAG Generator" - LLM not ready
```

**Backend API:**
```python
if health_ok and index_ok:
    ✅ "Backend API" - Fully operational
    Shows: "Uptime: 1h 30m 15s"
elif health_ok:
    ⚠️ "Backend API" - Partial availability
else:
    ❌ "Backend API" - Disconnected
```

##### 4. `render_compact_status(api_base_url=None)`
Compact version for sidebar display.

**Returns:**
```python
{
    "api_healthy": bool,
    "indices_loaded": bool,
    "llm_ready": bool
}
```

**Display:**
- ✅/❌ API Connected
- ✅/⚠️ Indices Loaded
- ✅/⚠️ LLM Ready

## 🔄 Changes Made

### Before (Unreliable)
```python
# Component Status - Local imports (unreliable)
try:
    from app.rag.generator import ResponseGenerator
    from app.rag.retriever import HybridRetriever
    st.success("✅ RAG Components")
except ImportError:
    st.error("❌ RAG Components")
```

**Problem:**
- ❌ Only checks if modules can be imported locally
- ❌ Doesn't reflect actual backend runtime state
- ❌ UI and backend run in separate processes
- ❌ Import success ≠ backend functionality

### After (Reliable)
```python
# Component Status - API-based checks
if index_result.get("success"):
    stats_data = index_result.get("data", {})
    has_bm25 = stats_data.get("bm25_documents", 0) > 0
    has_faiss = stats_data.get("faiss_documents", 0) > 0

    if has_bm25 or has_faiss:
        st.success("✅ RAG Retriever")
        st.caption(f"BM25: {'✓' if has_bm25 else '✗'} | FAISS: {'✓' if has_faiss else '✗'}")
```

**Benefits:**
- ✅ Reflects actual backend state
- ✅ Shows real-time index loading status
- ✅ Works across different processes
- ✅ Reliable error detection

## 📊 Caching Strategy

**Cache Location:** `st.session_state.system_status_cache`

**Cache Structure:**
```python
{
    "health": {
        "success": bool,
        "data": dict,
        "response_time_ms": float
    },
    "index": {
        "success": bool,
        "data": dict,
        "response_time_ms": float
    },
    "timestamp": "2025-09-29T10:00:00"
}
```

**Cache Strategy:**
- Cache invalidated when user clicks "Refresh" button
- Cache created on first load if not exists
- Reduces unnecessary API calls
- Display last update timestamp

## 🧪 Testing

### Test Script: `test_system_status_api.py`

**Test Coverage:**
1. ✅ `/healthz` endpoint connectivity
2. ✅ `/index-stats` endpoint connectivity
3. ✅ Component status logic with both response formats
4. ✅ Backend down scenario (timeout, connection error)
5. ✅ Error message display

**Test Results:**
```
✅ Health endpoint: PASS (with backend running)
✅ Index stats endpoint: PASS (with backend running)
✅ Backend down handling: PASS
✅ Error handling: PASS
```

### Manual Testing Steps

1. **Backend Running:**
   ```bash
   python -m uvicorn app.main:app
   ```

2. **Start UI:**
   ```bash
   streamlit run streamlit_app/app.py
   ```

3. **Verify Sidebar:**
   - Should show: ✅ API Connected
   - Should show: ✅ Indices Loaded
   - Should show: ✅ LLM Ready

4. **Stop Backend:**
   - Refresh UI
   - Should show: ❌ API Disconnected
   - Should show: ⚠️ Indices Not Loaded
   - Should show: ⚠️ LLM Not Ready

5. **Check Main Status Page:**
   - Navigate to Configuration or dedicated status page
   - Verify all metrics display correctly
   - Check component status reflects backend state

## 🚨 Error Handling

### Timeout (> 5 seconds)
```python
{
    "success": False,
    "error": "Request timeout",
    "data": None
}
```

**UI Display:** ❌ with error message

### Connection Error (Backend not running)
```python
{
    "success": False,
    "error": "Connection failed",
    "data": None
}
```

**UI Display:** ❌ API Disconnected

### HTTP Error (Status code != 200)
```python
{
    "success": False,
    "error": "Status code: 500",
    "data": None
}
```

**UI Display:** ❌ with status code

### Generic Exception
```python
{
    "success": False,
    "error": str(exception),
    "data": None
}
```

**UI Display:** ❌ with error message

## 📈 Performance Considerations

**API Call Timing:**
- Health check timeout: 5s (configurable)
- Index stats timeout: 5s (configurable)
- Compact status timeout: 2s (faster for sidebar)

**Optimization:**
- ✅ Caching to reduce redundant calls
- ✅ Short timeout for sidebar (2s vs 5s)
- ✅ Parallel calls (not sequential)
- ✅ Non-blocking UI updates

**Recommended Settings:**
```python
# For main status page
timeout = 5  # seconds

# For sidebar/compact view
timeout = 2  # seconds

# Cache duration
# User-controlled via Refresh button
```

## 🔐 Security Considerations

**API Base URL:**
- Configurable via UI: `st.session_state.api_base_url`
- Default: `http://127.0.0.1:8000`
- Should be changed for production deployments

**Auth Token:**
- Field available: `st.session_state.auth_token`
- Not currently used in status endpoints
- Can be added via headers if needed

**CORS:**
- Backend configured for UI access
- Restrictive in production environment

## 🎯 Benefits Summary

### Reliability
- ✅ Reflects actual backend runtime state
- ✅ No false positives from local import checks
- ✅ Real-time status updates

### Maintainability
- ✅ Single source of truth (backend API)
- ✅ No duplicate status logic
- ✅ Centralized error handling

### User Experience
- ✅ Clear status indicators
- ✅ Helpful error messages
- ✅ Fast response times with caching
- ✅ Manual refresh control

### Operational
- ✅ Easy debugging (check API responses)
- ✅ Monitoring-friendly (standard endpoints)
- ✅ Production-ready error handling

## 🔮 Future Enhancements

### Possible Improvements:
1. **Auto-refresh:** Periodic background status updates
2. **Websocket:** Real-time status push from backend
3. **Detailed metrics:** Response time graphs, error rate
4. **Alert system:** Notify when backend goes down
5. **Health history:** Track uptime/downtime over time

### Not Implemented (Out of Scope):
- ❌ Authentication for status endpoints
- ❌ Rate limiting for status checks
- ❌ Status persistence/logging
- ❌ Multi-backend support

## 📝 Notes

**Key Decision:** Removed all local imports for component status checks because:
1. UI and backend run in separate processes
2. Local import success doesn't mean backend functionality
3. Can't detect backend crashes or index loading failures
4. API-based checks provide ground truth

**Backward Compatibility:**
- System status component handles both response formats from `/index-stats`
- Graceful degradation if endpoints not available

**Documentation:**
- All functions have docstrings
- Error cases documented
- Example responses provided

## ✅ Completion Checklist

- [x] Analyzed backend API endpoints (`/healthz`, `/index-stats`)
- [x] Verified UI has `api_base_url` configuration
- [x] Helper functions already exist (`fetch_health_status`, `fetch_index_stats`)
- [x] Refactored component status to use API instead of local imports
- [x] Implemented error handling for backend unavailable
- [x] Created comprehensive test script
- [x] Tested with backend down scenario
- [x] Verified error messages display correctly
- [x] Documented implementation details
- [x] Ready for production use

---

**Status:** ✅ **COMPLETED**
**Next Steps:** Deploy to production and monitor real-world behavior.
