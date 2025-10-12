## Build Plan — Phase 2: Hybrid Modern (Weaviate + OpenSearch + RRF)

### Goals
- Migrate keyword search to OpenSearch, keep semantic in Weaviate, fuse via RRF.
- Ensure graceful degradation when one backend is unavailable.

### Source of Truth
- `../../docs/DOCS_NEW_Features/HYBRID_MODERN_FEATURE_SUMMARY.md`
- `../../reports/WEAVIATE_INFRASTRUCTURE_REPORT.md`
- `../../Build_plan_README/build_plan_BM25_Opensearch.md`
- `scripts/opensearch/*`, `scripts/phase1_index_to_weaviate.py`, `docker-compose-weaviate.yml`

### Prerequisites
- Phase 0 completed
- `.env`: `USE_HYBRID_MODERN=true`, `WEAVIATE_ENABLED=true`

### Steps
1) OpenSearch index creation and bulk insert
```powershell
# (a) Create index with BM25 similarity
python scripts/opensearch/create_index.py  # or use JSON mapping in build_plan_BM25_Opensearch.md

# (b) Bulk insert chunks
python scripts/opensearch/bulk_insert_to_opensearch.py --input artifacts/ingestion_production/chunks.jsonl --index rag_chunks
```

2) Weaviate ingestion (semantic vectors)
```powershell
python scripts/phase1_index_to_weaviate.py --input artifacts/ingestion_production/chunks.jsonl --collection Chunk --batch-size 256
```

3) Configure Hybrid Modern
```ini
USE_HYBRID_MODERN=true
WEAVIATE_RETRIEVAL_LIMIT=50
OPENSEARCH_INDEX=rag_chunks
OPENSEARCH_BM25_K1=1.2
OPENSEARCH_BM25_B=0.75
```

4) Verify hybrid flow
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/index-stats" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json
# Expect retriever_type: hybrid_modern, Weaviate healthy, OpenSearch ~4883 docs
```

### Validation
- RRF merges results; unique pages ~15 when both backends return 10 hits each
- `/api/ask` returns results even if one backend is down

### KPIs (Phase Exit)
- Weaviate + OpenSearch both populated
- p95 retrieval < 800ms; end-to-end < 2s (text-only)
- RRF de-dup works

### Troubleshooting
- OpenSearch index mismatch → re-run create_index with mapping in build_plan doc
- Weaviate vectors missing → re-run ingestion with correct batch size and API key

### References
- `../../Build_plan_README/build_plan_BM25_Opensearch.md`
- `../../reports/WEAVIATE_INFRASTRUCTURE_REPORT.md`
