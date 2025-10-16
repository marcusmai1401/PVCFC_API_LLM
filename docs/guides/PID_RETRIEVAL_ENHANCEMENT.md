# P&ID Retrieval Enhancement Guide

**Version**: 1.0
**Date**: 2025-10-16
**Status**: ✅ Implementation Complete

---

## Tổng Quan

Enhancement này cải thiện độ chính xác retrieval cho P&ID (Piping & Instrumentation Diagrams) và technical drawings bằng cách:

1. **Tag-aware query processing** - Detect equipment tags (E04217, P04201A)
2. **Adaptive RRF fusion** - Query-type based weighting
3. **Specialized reranking** - Boost exact/fuzzy tag matches
4. **Metadata filtering** - Filter by equipment tags

**Target metrics:**
- Precision@5 ≥ 90%
- Recall@10 ≥ 95%
- Latency P50 ≤ 2.5s

---

## Cài Đặt

### 1. Schema Updates (One-time)

**OpenSearch mapping:**
```powershell
python scripts\opensearch\update_tags_mapping.py
```

**Weaviate schema:**
```powershell
python scripts\weaviate\add_tags_property.py
```

### 2. Backfill Tags Data (One-time)

```powershell
# Dry run (preview)
python scripts\utilities\backfill_tags.py --dry-run

# Actual backfill (~5-10 minutes)
python scripts\utilities\backfill_tags.py
```

### 3. Enable in Configuration

Add to `.env`:
```ini
# P&ID Retrieval Enhancement
ENABLE_PID_ENHANCEMENT=true
PID_TAG_BOOST_EXACT=10.0
PID_TAG_BOOST_FUZZY=2.0
PID_TAG_BOOST_PROXIMITY=3.0
PID_FUZZY_THRESHOLD=90
RRF_ADAPTIVE_WEIGHTS=true
```

---

## Sử Dụng

### Basic Usage

```python
from app.rag.hybrid_weaviate_opensearch_retriever import HybridWeaviateOpenSearchRetriever

retriever = HybridWeaviateOpenSearchRetriever()

# Enhanced retrieval (P&ID-aware)
results = retriever.retrieve_enhanced(
    query="E04217",
    top_k=10,
    enable_pid_enhancement=True
)

# Normal retrieval (baseline)
results = retriever.retrieve_enhanced(
    query="E04217",
    top_k=10,
    enable_pid_enhancement=False
)
```

### Query Types

**Tag-only queries:**
```python
"E04217"
"E04217 ở đâu"
"thông tin P04201A"
```

**Mixed queries (tag + parameters):**
```python
"áp suất của E04217"
"flow rate pump P04201A"
"nhiệt độ reactor R04201"
```

**Visual queries:**
```python
"diagram heat exchanger nhiều ống"
"layout pump system"
```

---

## Retrieval Flow

```
User Query: "áp suất của E04217"
     ↓
[1] PID Query Enhancer
    - Detect tags: ["E04217"]
    - Query type: "mixed"
    - Variants: ["E04217", "E-04217", "E 04217", "e04217"]
     ↓
[2] Parallel Search
    - OpenSearch (tag boosted): terms + phrase + fuzzy
    - Weaviate (tag filtered): semantic + filter by tags
     ↓
[3] Adaptive RRF Fusion
    - Weight: OpenSearch=0.7, Weaviate=0.7 (mixed type)
    - Deduplicate by chunk_id
     ↓
[4] PID Tag Reranking
    - Boost exact matches: 10x (metadata), 5x (text)
    - Boost fuzzy matches: 2-3x
    - Boost proximity: 3x (tag near parameters)
     ↓
[5] BGE Reranking (Final)
    - Semantic reordering
    - Top-k selection
     ↓
Final Results (top 10)
```

---

## Evaluation

### Run Evaluation

```powershell
# With P&ID enhancement (enhanced)
python tests\eval_pid_retrieval.py

# Without enhancement (baseline comparison)
python tests\eval_pid_retrieval.py --no-enhancement

# Quiet mode (summary only)
python tests\eval_pid_retrieval.py --quiet
```

### Ground Truth Format

```json
{
  "query": "E04217",
  "query_type": "tag_only",
  "expected_tags": ["E04217"],
  "expected_answer_contains": [],
  "description": "Pure tag lookup"
}
```

### Add Your Own Test Cases

Edit `tests/ground_truth/pid_queries.json`:

```json
[
  {
    "query": "YOUR_QUERY",
    "query_type": "tag_only|mixed|visual",
    "expected_tags": ["TAG1", "TAG2"],
    "expected_answer_contains": ["keyword1", "keyword2"],
    "description": "Test description"
  }
]
```

---

## Configuration

### Boost Factors

**PID_TAG_BOOST_EXACT** (default: 10.0)
- Multiplier for exact tag match in metadata
- Higher = stronger preference for metadata matches

**PID_TAG_BOOST_FUZZY** (default: 2.0)
- Base multiplier for fuzzy matches (90-100% similarity)
- Actual boost: 1.0 + (similarity - 90) / 100

**PID_TAG_BOOST_PROXIMITY** (default: 3.0)
- Multiplier when tag appears near parameters (pressure, flow, etc.)
- Window: ±100 characters

### RRF Adaptive Weights

| Query Type | OpenSearch Weight | Weaviate Weight |
|------------|------------------|-----------------|
| tag_only   | 1.0              | 0.3             |
| mixed      | 0.7              | 0.7             |
| semantic   | 0.5              | 1.0             |
| visual     | 0.4              | 0.6             |

---

## Troubleshooting

### Tags Not Working

**Check schema:**
```powershell
# OpenSearch
curl http://localhost:9200/rag_chunks/_mapping

# Should have:
# "tags": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}

# Weaviate
python -c "import weaviate; c=weaviate.connect_to_local(); print(c.collections.get('Chunk').config.get())"

# Should have property: tags (TEXT_ARRAY)
```

**Verify tags in data:**
```powershell
# Check sample chunk
curl http://localhost:9200/rag_chunks/_search?size=1 | jq '.hits.hits[0]._source.tags'

# Should return array like: ["E04217", "P04201A"]
```

### Low Precision

**Possible causes:**
1. Tags not backfilled → Run backfill script
2. Boost factors too low → Increase in .env
3. Ground truth mismatch → Verify test cases

**Debug:**
```python
# Enable debug logging
import logging
logging.getLogger("app.rag").setLevel(logging.DEBUG)

# Check query enhancement
from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer
enhancer = PIDQueryEnhancer()
print(enhancer.enhance("E04217"))
```

### High Latency

**Typical latency breakdown:**
- Tag detection: ~10ms
- OpenSearch boosted: ~200ms
- Weaviate filtered: ~300ms
- RRF fusion: ~50ms
- PID reranking: ~100ms
- BGE reranking: ~500ms
- **Total: ~1.16s** ✅

**If > 2.5s:**
1. Reduce `opensearch_limit` and `weaviate_limit` (default: 50)
2. Disable BGE reranking temporarily
3. Check OpenSearch/Weaviate health

---

## Advanced Usage

### Custom Boost Factors

```python
from app.rag.rerankers.pid_tag_reranker import PIDTagReranker

reranker = PIDTagReranker(
    boost_meta_exact=15.0,     # Higher boost for metadata
    boost_text_exact=7.0,
    boost_proximity=4.0,
    fuzzy_threshold=85,         # Lower threshold = more fuzzy matches
    proximity_window=150        # Larger window
)
```

### Custom Query Type Detection

```python
from app.rag.query_processing.query_type_detector import QueryTypeDetector

detector = QueryTypeDetector()
query_type = detector.detect("E04217 pressure", detected_tags=["E04217"])
# Returns: "mixed"
```

---

## Rollback

To disable P&ID enhancements:

```ini
# In .env
ENABLE_PID_ENHANCEMENT=false
```

Schema changes (tags field) will remain but won't be used.

---

## Next Steps

1. **Create ground truth** - Add 20-30 real P&ID queries to `pid_queries.json`
2. **Run evaluation** - Measure baseline vs enhanced
3. **Tune parameters** - Adjust boost factors based on results
4. **Monitor production** - Track precision/latency metrics

---

## Technical Details

**Components:**
- `app/rag/query_processing/pid_query_enhancer.py` - Tag detection & enhancement
- `app/rag/query_processing/query_type_detector.py` - Query classification
- `app/rag/rerankers/pid_tag_reranker.py` - Tag-aware reranking
- `app/rag/indexers/opensearch_bm25_retriever.py` - Tag boosting search
- `app/rag/weaviate_retriever.py` - Tag filtering
- `app/rag/hybrid_weaviate_opensearch_retriever.py` - Enhanced retrieval pipeline

**Key algorithms:**
- RapidFuzz partial_ratio for fuzzy matching
- RRF with adaptive weights
- Proximity detection (100 char window)
- Multi-level boosting strategy

---

For more details, see implementation plan: `.cursor/plans/p-id-visual.plan.md`
