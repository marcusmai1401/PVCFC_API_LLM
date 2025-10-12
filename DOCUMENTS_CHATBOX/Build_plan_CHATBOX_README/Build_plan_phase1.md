## Build Plan — Phase 1: Baseline RAG (BM25 + FAISS)

### Goals
- Establish baseline retrieval and Q&A using offline BM25 (rank-bm25) and FAISS vectors.
- Produce ingestion artifacts (chunks.jsonl, doc_id_map.json) and local indices.

### Source of Truth
- `../../Build_plan_README/build_plan_BM25_Opensearch.md` (BM25 concepts)
- `app/ingestion/*`, `app/storage/*`
- `../../docs/ingestion_versioning_integration.md`

### Prerequisites
- Phase 0 completed
- `USE_HYBRID_MODERN=false` in `.env` (baseline mode)

### Steps
1) Run ingestion (vector + OCR as needed)
```powershell
# Example (adjust paths via tools/ingest.py help)
python tools/ingest.py --source-dir data/raw --output-dir artifacts/ingestion_test_final --workers 4 --enable-ocr
```

2) Generate baseline indices
```powershell
# Build offline BM25 + FAISS (legacy path)
python tools/ops/build_production_indices.py --input artifacts/ingestion_test_final --output artifacts/index_production
```

3) Configure app for baseline
```ini
USE_HYBRID_MODERN=false
WEAVIATE_ENABLED=false
```

4) Smoke test retrieval
```powershell
.\launchers\start_api.ps1
$body = @{ query = "Áp suất tối đa K06101"; language = "vi"; max_context = 5 } | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8000/api/ask" -Method POST -Body $body -ContentType "application/json"
```

### Validation
- Retrieval returns non-empty results with BM25+FAISS
- Latency < 2s (p95) for short queries

### KPIs (Phase Exit)
- chunks produced and deduplicated
- FAISS + BM25 artifacts under `artifacts/index_production`
- Baseline Q&A works without hybrid dependencies

### Troubleshooting
- Empty results → verify `artifacts/ingestion_*` paths and indexes exist
- High latency first call → FAISS warm-up; try again

### Deliverables
- `artifacts/ingestion_*/chunks.jsonl`, `doc_id_map.json`
- `artifacts/index_production/bm25/*`, `faiss/*`

### References
- `../../docs/ingestion_versioning_integration.md`
- `../../Build_plan_README/build_plan_BM25_Opensearch.md`
