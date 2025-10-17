# PID Tags Extraction Module

Auto-extract instrument tags from CAD-like PDFs with bbox evidence and sidecar indexing.

## Architecture

```
CADLikeGate → PageLayoutBuilder → TagExtractor → CropGenerator
                                        ↓
                                  tags.jsonl → OpenSearch (pvcfc_pid_tags)
                                        ↓
                                  Telemetry Logger
```

## Quick Start

### 1. Enable Feature

```ini
# .env
ENABLE_PID_TAGS=true
GATE_MODE=auto
GATE_THRESHOLD=0.60
TAGS_INDEX_NAME=pvcfc_pid_tags
```

### 2. Create Tags Index

```bash
python scripts/opensearch/create_tags_index.py --delete-if-exists
```

### 3. Test on Single PDF

```bash
python tools/test_tag_extraction.py \
  --pdf "D:\Data_Raw\sample_pid.pdf" \
  --doc-id "test_001" \
  --enable-crops
```

### 4. Bulk Process

```python
from app.ingestion.tags import TagExtractionOrchestrator

orchestrator = TagExtractionOrchestrator(lazy_crops=True)

for pdf_path in pdf_files:
    result = orchestrator.process_document(pdf_path, doc_id)
    if result:
        print(f"Extracted {result['tags_extracted']} tags")
```

### 5. Upsert to Index

```bash
python scripts/opensearch/bulk_upsert_tags.py \
  --tags-file "D:\PVCFC_Artifacts\entities\tags.jsonl" \
  --batch-size 1000
```

### 6. Run Smoke Tests

```bash
python tests/smoke_test_tags.py
```

## Configuration Files

- `config/cadlike_gate.yaml` - Gate scoring weights and thresholds
- `config/tag_grammar.yaml` - Tag patterns, CODE whitelist, assembler tolerances
- `config/page_filters.yaml` - Taggy page selection, exclusion rules
- `config/tags_index_mapping.json` - OpenSearch index mapping

## Outputs

### Artifacts (D:\PVCFC_Artifacts\)

```
page_layout/
  page_{doc_id}_{page}.json    # Layout per page (text spans + drawings)

entities/
  tags.jsonl                    # Extracted tags (one JSON object per line)
  relations.jsonl               # Optional relations (future)

crops/
  {doc_id}_p{page}_{hash}.png  # Bbox crops (if not lazy)

logs/
  tag_extraction_telemetry.jsonl  # Runtime metrics + warnings
```

### OpenSearch Index

```
Index: pvcfc_pid_tags
Documents: Tag entities with:
  - tag, area, code, num, suffix (keyword fields)
  - doc_id, page, bbox, crop_path
  - confidence, ts_ingest
```

## Telemetry & Warnings

Auto-warnings logged when:
- `is_cadlike=true` but `tags_found_total=0` → check tolerances
- `ocr_fallback_ratio > 0.20` → expect mostly vector PDFs
- `avg_triplet_score < 6.0` → tolerances too strict
- Low `p50` (<2) with high CAD score (>=0.70) → taggy page selection issue

Review: `D:\PVCFC_Artifacts\logs\tag_extraction_telemetry.jsonl`

## Tuning

### If missing tags:

1. Check telemetry warnings
2. Relax assembler tolerances in `config/tag_grammar.yaml`:
   ```yaml
   x_center_tolerance_ratio: 0.70  # Increase from 0.60
   y_gap_ratio_range: [0.6, 2.5]  # Widen range
   font_size_delta_pt: 2.0         # Increase tolerance
   pass_threshold: 5               # Lower threshold
   ```

3. Expand CODE whitelist if learning mode logs unknown codes:
   ```yaml
   code_whitelist:
     - LSAH  # Level switch alarm high
     - TSHH  # Temperature switch high-high
     # ... add from logs/unknown_codes.jsonl
   ```

### If too many false positives:

1. Strengthen exclusion zones in `config/page_filters.yaml`
2. Increase `pass_threshold` in tag_grammar.yaml
3. Review legend_excluded_hits in telemetry

## Integration with Query

Tags retrieval happens automatically at query-time if:
- `ENABLE_PID_TAGS=true`
- Query contains tag patterns (e.g., "PSAL 2207")
- Tags index exists and healthy

Query flow:
```
Query → PIDQueryEnhancer (detect tags)
         ↓
   Parallel Retrieval:
     Branch A: Tags index (exact + fuzzy)
     Branch B: Chunks (semantic + BM25)
         ↓
   RRF Fusion (k=60)
         ↓
   Rerank
         ↓
   Attach crop_path to tag results
         ↓
   Response (with vision citation if crop available)
```

## Troubleshooting

### No tags extracted despite high CAD score

```python
# Check gate decision
from app.ingestion.cadlike_gate import get_cadlike_gate
gate = get_cadlike_gate()
decision = gate.evaluate(pdf_path)
print(f"Score: {decision.score}, taggy pages: {decision.taggy_pages}")
```

### Tags index not found

```bash
# Create index
python scripts/opensearch/create_tags_index.py

# Verify
curl http://localhost:9200/pvcfc_pid_tags
```

### Crops not showing in query results

Check:
1. `crop_path` field populated in tags.jsonl?
2. Crops actually generated in D:\PVCFC_Artifacts\crops\?
3. Query results include tags source?

## API

See code documentation in:
- `app/ingestion/tags/orchestrator.py` - Main orchestrator
- `app/ingestion/cadlike_gate.py` - Gate scorer
- `app/ingestion/layout/page_layout_builder.py` - Layout extraction
- `app/ingestion/tags/tag_extractor.py` - Tag assembly logic
- `app/rag/hybrid_with_tags_retriever.py` - Query-time integration
