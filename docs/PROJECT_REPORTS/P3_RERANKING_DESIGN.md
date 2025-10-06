# P3: 2-Tier Reranking Architecture

**Date**: 2025-10-02
**Phase**: P3 (2-Tier Reranking)
**Status**: 🔨 IN PROGRESS

---

## 📝 Overview

P3 implements a sophisticated 2-tier reranking pipeline to improve retrieval quality:

1. **Hybrid Retrieval**: BM25 (keyword) + FAISS (semantic) with score fusion
2. **Stage-1 Reranking**: Vertex AI Semantic Reranker for neural relevance scoring
3. **Stage-2 Reranking**: Task-specific domain logic (equipment tags, P&ID metadata, document type)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Query Input                              │
│                     "CO2 compressor torque"                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID RETRIEVAL                              │
│  ┌─────────────────┐           ┌──────────────────┐            │
│  │  BM25 Indexer   │           │  FAISS Indexer   │            │
│  │  (Keyword)      │           │  (Semantic)      │            │
│  └────────┬────────┘           └────────┬─────────┘            │
│           │                              │                       │
│           v                              v                       │
│  ┌─────────────────────────────────────────────────┐           │
│  │        Score Fusion (RRF or Weighted)           │           │
│  │   final_score = α·bm25 + β·faiss                │           │
│  └─────────────────────┬───────────────────────────┘           │
└────────────────────────┼───────────────────────────────────────┘
                         │
                         v (Top 100 candidates)
┌─────────────────────────────────────────────────────────────────┐
│              STAGE-1: Vertex AI Semantic Reranker               │
│                                                                  │
│  API: aiplatform.googleapis.com/v1/projects/.../models/rerank   │
│                                                                  │
│  Input:                                                          │
│    - query: "CO2 compressor torque"                             │
│    - records: [{"id": "chunk_001", "content": "..."}]          │
│                                                                  │
│  Output:                                                         │
│    - scores: [0.95, 0.87, 0.76, ...]                           │
│    - reranked_records: sorted by relevance                      │
│                                                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v (Top 50 after Stage-1)
┌─────────────────────────────────────────────────────────────────┐
│         STAGE-2: Task-Specific Domain Reranking                 │
│                                                                  │
│  Boost factors:                                                  │
│  ┌────────────────────────────────────────────────┐            │
│  │ 1. Equipment Tag Match: +0.2                    │            │
│  │    - Query has "P-101" → boost chunks with P-101│            │
│  │                                                  │            │
│  │ 2. Document Type Relevance: +0.15               │            │
│  │    - Torque query → prefer datasheet, specs     │            │
│  │                                                  │            │
│  │ 3. P&ID Diagram Boost: +0.1                     │            │
│  │    - If chunk_type == "pid"                     │            │
│  │                                                  │            │
│  │ 4. Recent Document Boost: +0.05                 │            │
│  │    - Newer documents get slight boost           │            │
│  └────────────────────────────────────────────────┘            │
│                                                                  │
│  Final Score = Stage1_score + sum(boost_factors)                │
│                                                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v (Top 10 final results)
┌─────────────────────────────────────────────────────────────────┐
│                      FINAL RESULTS                               │
│                                                                  │
│  1. [Score: 0.97] P-101 pump torque specifications...          │
│  2. [Score: 0.92] CO2 compressor C-101 torque curve...         │
│  3. [Score: 0.88] Equipment datasheet for P-101...             │
│  ...                                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Component Details

### 1. Hybrid Retriever

**Purpose**: Combine keyword (BM25) and semantic (FAISS) search

**Score Fusion Methods**:

#### Option A: Weighted Sum
```python
final_score = alpha * bm25_score + beta * faiss_score
# Default: alpha=0.5, beta=0.5
```

#### Option B: Reciprocal Rank Fusion (RRF)
```python
rrf_score = sum(1 / (k + rank_i)) for all retrievers
# k = 60 (default)
```

**Configuration**:
```python
HybridRetriever(
    bm25_indexer=bm25_indexer,
    faiss_indexer=faiss_indexer,
    bm25_weight=0.5,
    faiss_weight=0.5,
    fusion_method="weighted"  # or "rrf"
)
```

---

### 2. Stage-1: Vertex AI Semantic Reranker

**Purpose**: Neural reranking using Google's semantic understanding

**API Endpoint**:
```
POST https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/models/semantic-ranker-512@latest:predict
```

**Request Format**:
```json
{
  "query": "CO2 compressor torque",
  "records": [
    {"id": "chunk_001", "content": "P-101 pump torque specifications..."},
    {"id": "chunk_002", "content": "CO2 compressor C-101..."}
  ],
  "top_n": 50
}
```

**Response**:
```json
{
  "predictions": [
    {"id": "chunk_002", "score": 0.95},
    {"id": "chunk_001", "score": 0.87}
  ]
}
```

**Cost Estimation**:
- ~$0.001 per 1000 rerank operations
- For 100 candidates → ~$0.0001 per query

**Rate Limits**:
- 60 requests/minute
- Max 100 records per request

---

### 3. Stage-2: Task-Specific Reranking

**Purpose**: Apply domain knowledge to boost relevant results

#### Boost Factors

| Factor | Weight | Trigger | Example |
|--------|--------|---------|---------|
| Equipment Tag Match | +0.2 | Query contains tag (P-101, HX-201) | "P-101 torque" → boost chunks with P-101 |
| Document Type | +0.15 | Query intent (torque, specs, diagram) | Torque query → boost datasheets |
| P&ID Diagram | +0.1 | chunk_type == "pid" | Visual diagram chunks |
| Recent Document | +0.05 | Document age < 6 months | Newer revisions preferred |
| Header Match | +0.08 | Query matches section header | "Operating Parameters" |
| Table Content | +0.12 | chunk_type == "table" | Structured data chunks |

#### Implementation Logic

```python
def stage2_rerank(results, query, config):
    boosted_results = []

    for result in results:
        boost = 0.0

        # Equipment tag match
        query_tags = extract_equipment_tags(query)
        chunk_tags = result['metadata'].get('equipment_tags', [])
        if any(tag in chunk_tags for tag in query_tags):
            boost += 0.2

        # Document type relevance
        query_intent = classify_query_intent(query)
        doc_type = result['metadata'].get('doc_type')
        if is_relevant_doc_type(query_intent, doc_type):
            boost += 0.15

        # P&ID diagram boost
        if result['metadata'].get('chunk_type') == 'pid':
            boost += 0.1

        # Recent document
        doc_age_months = get_document_age(result['metadata'])
        if doc_age_months < 6:
            boost += 0.05

        # Header match
        headers = result['metadata'].get('headers', [])
        if any(keyword in h.lower() for h in headers for keyword in query.lower().split()):
            boost += 0.08

        # Table content
        if result['metadata'].get('chunk_type') == 'table':
            boost += 0.12

        # Final score
        final_score = result['stage1_score'] + boost
        boosted_results.append({
            **result,
            'final_score': final_score,
            'boost': boost
        })

    # Sort by final score
    boosted_results.sort(key=lambda x: x['final_score'], reverse=True)
    return boosted_results
```

---

## 📊 Expected Performance

### Baseline (BM25 only)
- Precision@10: ~0.65
- Recall@50: ~0.70

### Hybrid (BM25 + FAISS)
- Precision@10: ~0.75 (+15%)
- Recall@50: ~0.82 (+17%)

### With Stage-1 Reranking
- Precision@10: ~0.85 (+31%)
- Recall@50: ~0.88 (+26%)

### With Stage-2 Reranking
- Precision@10: ~0.92 (+42%)
- Recall@50: ~0.90 (+29%)

---

## 🔄 Query Flow

### Example Query: "P-101 pump torque curve"

#### Step 1: Hybrid Retrieval
```
BM25 Results (top 50):
  1. "P-101 pump specifications" (score: 12.5)
  2. "Torque curve analysis" (score: 10.2)
  ...

FAISS Results (top 50):
  1. "Pump torque characteristics" (score: 0.89)
  2. "P-101 equipment data" (score: 0.85)
  ...

Fused Results (top 100):
  1. "P-101 pump specifications" (combined: 0.92)
  2. "P-101 equipment data" (combined: 0.88)
  ...
```

#### Step 2: Stage-1 Reranking (Vertex AI)
```
Input: Top 100 candidates
Output: Reranked by semantic relevance

Reranked Results:
  1. "P-101 torque curve specifications" (score: 0.95)
  2. "Pump P-101 operating parameters" (score: 0.87)
  3. "Torque measurement data P-101" (score: 0.82)
  ...
```

#### Step 3: Stage-2 Reranking (Domain Logic)
```
Apply boosts:
  1. "P-101 torque curve specifications"
     Stage-1: 0.95
     + Equipment tag match (P-101): +0.2
     + Doc type (datasheet): +0.15
     = Final: 1.30

  2. "Pump P-101 operating parameters"
     Stage-1: 0.87
     + Equipment tag match: +0.2
     + Header match: +0.08
     = Final: 1.15

Final Top 10:
  1. [1.30] P-101 torque curve specifications
  2. [1.15] Pump P-101 operating parameters
  3. [1.08] Torque measurement data P-101
  ...
```

---

## 🎯 Implementation Plan

### Phase 1: Hybrid Retriever ✅ (Already exists in versioned_retriever.py)
- [x] Combine BM25 + FAISS scores
- [x] Weighted sum fusion
- [ ] RRF fusion (optional enhancement)

### Phase 2: Stage-1 Reranker
- [ ] Vertex AI API client
- [ ] Request batching for rate limits
- [ ] Error handling and retry logic
- [ ] Cost tracking

### Phase 3: Stage-2 Reranker
- [ ] Equipment tag boost
- [ ] Document type classification
- [ ] Query intent detection
- [ ] Boost factor tuning

### Phase 4: Integration & Testing
- [ ] End-to-end pipeline
- [ ] Performance benchmarks
- [ ] A/B testing framework

---

## 🔐 Configuration

### Environment Variables
```bash
# Vertex AI
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
VERTEX_AI_MODEL=semantic-ranker-512@latest

# Reranking Config
STAGE1_TOP_K=50
STAGE2_TOP_K=10
BM25_WEIGHT=0.5
FAISS_WEIGHT=0.5

# Boost Factors
EQUIPMENT_TAG_BOOST=0.2
DOC_TYPE_BOOST=0.15
PID_BOOST=0.1
RECENT_DOC_BOOST=0.05
```

### Config File (config/reranking.yaml)
```yaml
hybrid_retrieval:
  bm25_weight: 0.5
  faiss_weight: 0.5
  fusion_method: weighted  # or rrf
  initial_top_k: 100

stage1_reranking:
  enabled: true
  provider: vertex_ai
  model: semantic-ranker-512@latest
  top_k: 50
  batch_size: 100
  timeout_seconds: 30

stage2_reranking:
  enabled: true
  boost_factors:
    equipment_tag_match: 0.2
    doc_type_relevance: 0.15
    pid_diagram: 0.1
    recent_document: 0.05
    header_match: 0.08
    table_content: 0.12
  top_k: 10
```

---

**Status**: 🔨 Design Complete
**Ready for**: Implementation
**Owner**: Agent Mode (Warp AI)
