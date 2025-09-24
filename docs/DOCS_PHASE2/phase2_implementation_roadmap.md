# Phase 2 Implementation Roadmap - RAG Pipeline & API

## Tổng quan Phase 2
**Mục tiêu**: Xây dựng RAG Pipeline hoàn chỉnh với 3 API endpoints chính
**Timeline**: 2-3 tuần (chia thành 5 sprints nhỏ)

---

## 🎯 Sprint 1: Core RAG Components (2-3 ngày)

### 1.1 Query Transformation Module
**File**: `app/rag/query_transform.py`

```python
class QueryTransformer:
    - normalize_query(): Chuẩn hóa query
    - detect_intent(): Phát hiện ý định (ask/locate/report)
    - generate_hyde(): Tạo hypothetical documents
    - apply_filters(): Áp dụng bộ lọc doc_category/doc_id
```

**Tasks**:
- [ ] Implement query normalization (lowercase, strip, remove stopwords)
- [ ] Intent detection với rules đơn giản
- [ ] HyDE generation với Gemini 2.5 Flash (light tier)
- [ ] Filter validation và application
- [ ] Unit tests

### 1.2 Hybrid Retriever Module
**File**: `app/rag/retriever.py`

```python
class HybridRetriever:
    - search_bm25(): Tìm kiếm keyword
    - search_faiss(): Tìm kiếm semantic
    - reciprocal_rank_fusion(): RRF merge
    - expand_parent(): Mở rộng context
```

**Tasks**:
- [ ] Integrate với BM25Indexer và VectorIndexer đã có
- [ ] Implement RRF algorithm
- [ ] Parent expansion với sentence window
- [ ] Configuration cho k_bm25, k_faiss, top_rrf
- [ ] Unit tests với mock data

### 1.3 Reranker Module
**File**: `app/rag/reranker.py`

```python
class CrossEncoderReranker:
    - load_model(): Load cross-encoder model
    - rerank(): Score và rerank passages
    - get_top_k(): Lấy top K passages
```

**Tasks**:
- [ ] Setup cross-encoder/ms-marco-MiniLM-L-6-v2
- [ ] Batch scoring implementation
- [ ] Configurable top_k reranking
- [ ] Performance optimization (batch processing)
- [ ] Unit tests

---

## 🎯 Sprint 2: Generation & Citations (2-3 ngày)

### 2.1 Generator Module
**File**: `app/rag/generator.py`

```python
class RAGGenerator:
    - prepare_context(): Chuẩn bị context từ retrieved chunks
    - generate_answer(): Generate với LLM
    - extract_citations(): Parse citations từ response
    - format_response(): Format final response
```

**Tasks**:
- [ ] Context preparation với metadata
- [ ] Prompt templates cho forced citations
- [ ] Integration với LLMClientFactory
- [ ] Citation parsing và validation
- [ ] Response formatting (markdown)

### 2.2 Chain of Verification (CoVe)
**File**: `app/rag/cove.py`

```python
class ChainOfVerification:
    - extract_claims(): Trích xuất claims từ answer
    - generate_check_queries(): Tạo queries kiểm tra
    - verify_claims(): Verify với retrieval
    - adjust_answer(): Điều chỉnh câu trả lời
```

**Tasks**:
- [ ] Claim extraction logic
- [ ] Check query generation
- [ ] Quick verification với k=10
- [ ] Answer adjustment strategy
- [ ] Unit tests

### 2.3 Schemas & Data Models
**File**: `app/rag/schemas.py`

```python
# Pydantic models cho Request/Response
class AskRequest, AskResponse
class LocateRequest, LocateResponse
class ReportRequest, ReportResponse
class Citation, RetrievalResult, etc.
```

---

## 🎯 Sprint 3: API Endpoints (2-3 ngày)

### 3.1 Ask Endpoint
**File**: `app/api/routers/ask.py`

```python
@router.post("/api/v1/ask")
async def ask(request: AskRequest) -> AskResponse:
    # Full RAG pipeline
```

**Tasks**:
- [ ] Endpoint implementation
- [ ] Request validation
- [ ] Pipeline orchestration
- [ ] Error handling
- [ ] Response formatting

### 3.2 Locate Endpoint
**File**: `app/api/routers/locate.py`

```python
@router.post("/api/v1/locate")
async def locate(request: LocateRequest) -> LocateResponse:
    # Entity location in documents
```

**Tasks**:
- [ ] Endpoint implementation
- [ ] Bbox extraction logic
- [ ] Fallback for scan PDFs
- [ ] Score ranking
- [ ] Response formatting

### 3.3 Report Endpoint
**File**: `app/api/routers/report.py`

```python
@router.post("/api/v1/report")
async def report(request: ReportRequest) -> ReportResponse:
    # Multi-section report generation
```

**Tasks**:
- [ ] Endpoint implementation
- [ ] Sub-query processing
- [ ] Section generation
- [ ] Citation aggregation
- [ ] Response formatting

---

## 🎯 Sprint 4: Infrastructure & Quality (2 ngày)

### 4.1 Caching Layer
**File**: `app/core/cache.py`

```python
class CacheManager:
    - LRU cache với TTL
    - Key generation (query + filters)
    - Cache invalidation
```

### 4.2 Rate Limiting
**File**: `app/core/rate_limit.py`

```python
class RateLimiter:
    - Token bucket algorithm
    - Per-tenant/per-IP limiting
    - Headers management
```

### 4.3 Metrics & Monitoring
**Files**: `app/core/metrics.py`, `app/core/tracing.py`

```python
# Prometheus metrics
# OpenTelemetry tracing
# Latency breakdown
```

### 4.4 Error Handling
- Timeout management
- Fallback strategies
- Circuit breaker pattern
- Graceful degradation

---

## 🎯 Sprint 5: Testing & Documentation (2 ngày)

### 5.1 Unit Tests
- [ ] Test query transformation
- [ ] Test retrieval với mock indices
- [ ] Test reranking logic
- [ ] Test generation với mock LLM
- [ ] Test API endpoints

### 5.2 Integration Tests
- [ ] End-to-end pipeline test
- [ ] API integration tests
- [ ] Performance tests
- [ ] Load tests (30 RPS)

### 5.3 Documentation
- [ ] API documentation (OpenAPI)
- [ ] Usage examples
- [ ] Configuration guide
- [ ] Deployment guide

---

## 📋 Definition of Done (DoD)

### Functional Requirements
- ✅ `/ask` endpoint: Returns answers with valid citations
- ✅ `/locate` endpoint: Finds entities with bbox/page
- ✅ `/report` endpoint: Generates multi-section reports
- ✅ HyDE improves recall by >10%
- ✅ CoVe reduces hallucinations
- ✅ Citations present in 100% responses

### Performance Requirements
- ✅ p95 latency < 8 seconds
- ✅ Cache hit rate > 30%
- ✅ Support 60 requests/minute
- ✅ Graceful degradation on overload

### Quality Requirements
- ✅ Unit test coverage > 80%
- ✅ Integration tests pass
- ✅ Error handling for all edge cases
- ✅ Comprehensive logging/metrics

---

## 🚀 Implementation Order (Recommended)

### Week 1: Core Pipeline
1. **Day 1-2**: Query Transform + Retriever
2. **Day 3-4**: Reranker + Generator
3. **Day 5**: CoVe + Schemas

### Week 2: APIs & Infrastructure
1. **Day 1-2**: API Endpoints
2. **Day 3**: Caching + Rate Limiting
3. **Day 4**: Metrics + Error Handling
4. **Day 5**: Testing + Documentation

---

## 🛠 Tech Stack Phase 2

### New Dependencies
```txt
# Reranking
sentence-transformers==3.0.1
transformers==4.44.2
torch==2.4.1

# Caching & Rate Limiting
cachetools==5.4.0
redis==5.0.8 (optional)

# Monitoring
prometheus-client==0.20.0
opentelemetry-api==1.26.0
opentelemetry-sdk==1.26.0

# Testing
pytest-asyncio==0.23.8
httpx==0.27.2
locust==2.31.0 (for load testing)
```

---

## 📝 First Steps (Today)

### Step 1: Setup Sprint 1 Structure
```bash
# Create module files
mkdir -p app/rag
touch app/rag/query_transform.py
touch app/rag/retriever.py
touch app/rag/reranker.py
touch app/rag/schemas.py
```

### Step 2: Install Dependencies
```bash
pip install sentence-transformers transformers torch
pip install cachetools prometheus-client
```

### Step 3: Start with Query Transformer
Begin with the simplest component to build momentum:
1. Implement basic query normalization
2. Add HyDE generation with Gemini
3. Test with real queries

### Step 4: Daily Progress Tracking
- Morning: Plan tasks for the day
- Implement & test incrementally
- Evening: Review & commit progress
- Update this roadmap with completion status

---

## 🎯 Success Criteria

### Minimum Viable Product (MVP)
- Basic `/ask` endpoint working
- Returns answers with citations
- Uses hybrid search (BM25 + FAISS)
- Basic error handling

### Production Ready
- All 3 endpoints functional
- Caching & rate limiting
- Comprehensive testing
- Performance optimized
- Monitoring in place

---

## 💡 Tips for Success

1. **Start Simple**: Get basic pipeline working first
2. **Test Early**: Write tests as you go
3. **Iterate**: Improve quality incrementally
4. **Monitor**: Add logging/metrics from start
5. **Document**: Keep notes on decisions

---

**Next Action**: Let's start with Sprint 1.1 - Query Transformation Module!
