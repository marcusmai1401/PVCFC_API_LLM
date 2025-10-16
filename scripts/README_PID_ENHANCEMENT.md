# P&ID Retrieval Enhancement Scripts

Scripts để setup và test P&ID retrieval enhancements.

## 📋 Scripts Overview

### Setup Scripts

**`pid_enhancement_setup.ps1`** - Full setup automation
- Updates OpenSearch mapping
- Updates Weaviate schema
- Backfills tags to indexes

**`opensearch/update_tags_mapping.py`** - OpenSearch schema update
- Adds `tags` and `tags_raw` fields with keyword mapping
- One-time migration, no reindex required

**`weaviate/add_tags_property.py`** - Weaviate schema update
- Adds `tags` property (TEXT_ARRAY type)
- One-time schema change

**`utilities/backfill_tags.py`** - Data migration
- Updates existing chunks with tags metadata
- Lightweight update (~5-10 min for 4883 chunks)

### Testing Scripts

**`pid_enhancement_test.ps1`** - Quick smoke test
- Tests tag detection
- Tests enhanced retrieval
- Validates basic functionality

**`tests/eval_pid_retrieval.py`** - Full evaluation
- Measures Precision@5, Recall@10
- Measures latency (P50, P90, P95)
- Compares enhanced vs baseline

---

## 🚀 Quick Start

### Full Setup (One-time)

```powershell
# 1. Run full setup
.\scripts\pid_enhancement_setup.ps1

# 2. Update .env
# Add P&ID settings from env.example

# 3. Run quick test
.\scripts\pid_enhancement_test.ps1

# 4. Run full evaluation
python tests\eval_pid_retrieval.py
```

### Dry Run (Preview Only)

```powershell
.\scripts\pid_enhancement_setup.ps1 -DryRun
```

### Skip Backfill (Schema Only)

```powershell
.\scripts\pid_enhancement_setup.ps1 -SkipBackfill
```

---

## 📊 Individual Scripts

### 1. Update OpenSearch Mapping

```powershell
python scripts\opensearch\update_tags_mapping.py
```

**What it does:**
- Adds `tags` field (text + keyword)
- Adds `tags_raw` field (text + keyword)
- Uses dynamic mapping (no reindex needed)

### 2. Update Weaviate Schema

```powershell
python scripts\weaviate\add_tags_property.py
```

**What it does:**
- Adds `tags` property (TEXT_ARRAY)
- Interactive prompt if property exists

### 3. Backfill Tags

```powershell
# Preview only
python scripts\utilities\backfill_tags.py --dry-run

# Full backfill
python scripts\utilities\backfill_tags.py --batch-size 100

# Custom chunks file
python scripts\utilities\backfill_tags.py --chunks-file path\to\chunks.jsonl
```

**What it does:**
- Reads tags from `artifacts/ingestion_production/chunks/chunks.jsonl`
- Updates OpenSearch documents (partial update)
- Updates Weaviate objects (partial update)
- Progress bar with tqdm

**Performance:**
- ~100 chunks/second
- ~5-10 minutes for 4883 chunks

### 4. Evaluation

```powershell
# Enhanced retrieval
python tests\eval_pid_retrieval.py

# Baseline (no enhancement)
python tests\eval_pid_retrieval.py --no-enhancement

# Quiet mode (summary only)
python tests\eval_pid_retrieval.py --quiet

# Custom ground truth
python tests\eval_pid_retrieval.py --ground-truth path\to\queries.json
```

**Metrics:**
- Precision@5
- Recall@10
- Latency (P50, P90, P95)

**Output:**
- Console summary
- Detailed JSON: `tests/ground_truth/evaluation_results.json`

---

## 🧪 Testing

### Unit Tests

```powershell
# Test PID query enhancer
pytest tests\test_pid_query_enhancer.py -v

# Test PID tag reranker
pytest tests\test_pid_tag_reranker.py -v

# All tests
pytest tests\test_pid*.py -v
```

### Manual Testing

```python
# Test tag detection
from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer

enhancer = PIDQueryEnhancer()
result = enhancer.enhance("áp suất của E04217")
print(result)

# Expected output:
# {
#   "strategy": "tag_focused",
#   "tags": ["E04217"],
#   "query_type": "mixed",
#   "variants": {"E04217": ["E04217", "E-04217", "E 04217", "e04217"]},
#   "equipment_types": ["heat exchanger"]
# }
```

```python
# Test enhanced retrieval
from app.rag.hybrid_weaviate_opensearch_retriever import HybridWeaviateOpenSearchRetriever

retriever = HybridWeaviateOpenSearchRetriever()
results = retriever.retrieve_enhanced(
    query="E04217",
    top_k=10,
    enable_pid_enhancement=True
)

for r in results[:3]:
    print(f"Score: {r.score:.4f}, Source: {r.source}")
    print(f"Text: {r.text[:100]}...")
    print()
```

---

## 📝 Ground Truth Management

### Format

```json
{
  "query": "E04217",
  "query_type": "tag_only",
  "expected_tags": ["E04217"],
  "expected_answer_contains": [],
  "description": "Pure tag lookup"
}
```

### Adding Test Cases

Edit `tests/ground_truth/pid_queries.json`:

```json
[
  {
    "query": "YOUR_NEW_QUERY",
    "query_type": "tag_only|mixed|visual",
    "expected_tags": ["TAG1"],
    "expected_answer_contains": ["keyword1", "keyword2"],
    "description": "Description"
  }
]
```

---

## 🔧 Troubleshooting

### Schema Update Fails

```powershell
# Check OpenSearch
curl http://localhost:9200/_cat/indices

# Check Weaviate
curl http://localhost:8080/v1/schema/Chunk
```

### Backfill Fails

```powershell
# Check chunks file exists
Test-Path artifacts\ingestion_production\chunks\chunks.jsonl

# Check sample chunk has tags
Get-Content artifacts\ingestion_production\chunks\chunks.jsonl -First 1 | ConvertFrom-Json | Select-Object -ExpandProperty metadata | Select-Object tags
```

### Low Performance

```powershell
# Run with baseline (no enhancement)
python tests\eval_pid_retrieval.py --no-enhancement

# Compare results to identify bottleneck
```

---

## 📚 Documentation

- **Implementation Guide**: `docs/guides/PID_RETRIEVAL_ENHANCEMENT.md`
- **Implementation Plan**: `.cursor/plans/p-id-visual.plan.md`
- **Architecture**: `SYSTEM_ARCHITECTURE.md`

---

**Last Updated**: 2025-10-16
**Version**: 1.0
