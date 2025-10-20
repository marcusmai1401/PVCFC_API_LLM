# P&ID Search Enhancement - Migration Guide

## Overview

This migration updates the P&ID tag extraction and search system with improved schema and capabilities:

### Key Changes

**Schema Updates:**
- `area` → `unit` (1-3 digits instead of 2)
- `code` → `prefix` (2-6 letters instead of 2-4)
- `num` → `suffix` (digits only, no letters)
- **NEW**: `variant` field (A/B/C single letter)
- **NEW**: `annotation` field (A/B/C, 1oo2 patterns)

**New Capabilities:**
- SUFFIX-only search (e.g., "5153")
- Component-based search (e.g., "04 5153", "PAHH 5153")
- Multi-prefix grouping and ambiguity warnings
- Annotation separation from core tags

## Migration Process

### Prerequisites

1. **Backup before migration:**
   ```bash
   python scripts/migration/backup_pid_data.py
   ```
   - Creates backup in `artifacts/migration_backup/`
   - Backs up: tags index data, mapping, doc_id_map.json

2. **Verify environment:**
   ```bash
   # Ensure OpenSearch is running
   curl http://localhost:9200/_cluster/health

   # Check ENABLE_PID_TAGS is true
   grep ENABLE_PID_TAGS .env
   ```

### Step-by-Step Migration

#### Step 1: Backup (CRITICAL!)

```bash
python scripts/migration/backup_pid_data.py
```

**Output:**
- `artifacts/migration_backup/tags_backup_YYYYMMDD_HHMMSS.jsonl`
- `artifacts/migration_backup/tags_mapping_YYYYMMDD_HHMMSS.json`
- `artifacts/migration_backup/doc_id_map_YYYYMMDD_HHMMSS.json`
- `artifacts/migration_backup/backup_manifest.json`

#### Step 2: Re-extract Tags with New Schema

```bash
python scripts/migration/reextract_tags.py
```

**Process:**
- Loads all documents from doc_id_map.json
- Re-runs CADLikeGate to identify P&ID documents
- Extracts tags using updated TagExtractor (UNIT/PREFIX/SUFFIX/VARIANT/ANNOTATION)
- Saves to `artifacts/migration/tags_new_schema.jsonl`

**Output:**
- `artifacts/migration/tags_new_schema.jsonl`
- `artifacts/migration/reextraction_stats.json`

**Expected time:** ~10-30 minutes depending on corpus size

#### Step 3: Re-index to OpenSearch

```bash
python scripts/migration/reindex_tags.py
```

**Process:**
- Deletes old index `pvcfc_pid_tags`
- Creates new index with updated mapping from `config/tags_index_mapping.json`
- Bulk inserts from `tags_new_schema.jsonl`
- Verifies document count

**Output:**
- New index: `pvcfc_pid_tags` (with updated schema)

**Expected time:** ~2-5 minutes

#### Step 4: Validate Migration

```bash
python scripts/migration/validate_migration.py
```

**Checks:**
1. Document count matches (within 5% tolerance)
2. Sample 100 tags and verify parsing:
   - Required fields present
   - SUFFIX is digits only
   - VARIANT is single letter
3. Test queries:
   - "5153" → finds 4 tags with different prefixes
   - "04 PAHH 5153" → exact match
   - "PAHH 5153" → filters by prefix
4. Response quality comparison

**Output:**
- `artifacts/migration/validation_report.json`

### Rollback Plan

If migration fails or has issues:

```bash
python scripts/migration/restore_backup.py
```

This will:
1. Delete the new index
2. Recreate the old index with backup mapping
3. Restore data from backup JSONL
4. Verify count

## Testing After Migration

### Manual Testing

```bash
# Test SUFFIX-only query
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "5153", "language": "vi"}'

# Expected: 4 tags with prefixes PAHH, PALL, PI, PXT
# Expected: Warning about multi-prefix ambiguity

# Test component query
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "04 5153", "language": "vi"}'

# Expected: Tags filtered by UNIT=04

# Test full tag
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "04 PAHH 5153", "language": "vi"}'

# Expected: Exact match (may include annotation A/B/C)
```

### Automated Tests

```bash
# Run unit tests
pytest tests/test_pid_enhancements.py -v

# Run integration tests (requires OpenSearch running)
pytest tests/integration/test_pid_search_e2e.py -v

# Run smoke tests
python tests/smoke_test_tags.py
```

## Files Modified

### Core Schema & Config
- `app/ingestion/tags/schemas.py` - Updated TagParts and TagEntity
- `config/tag_grammar.yaml` - Updated patterns and whitelist
- `config/tags_index_mapping.json` - Updated OpenSearch mapping

### Extraction Layer
- `app/ingestion/tags/tag_extractor.py` - Updated triplet assembly logic

### Query & Search Layer
- `app/rag/normalizers/tag_normalizer.py` - Added new patterns and parsing
- `app/rag/query_processing/pid_query_enhancer.py` - Added SUFFIX/component detection
- `app/rag/indexers/opensearch_tags_retriever.py` - Added component/suffix search

### New Files
- `app/rag/formatters/pid_response_formatter.py` - Response formatting
- `scripts/migration/backup_pid_data.py` - Backup script
- `scripts/migration/reextract_tags.py` - Re-extraction script
- `scripts/migration/reindex_tags.py` - Re-indexing script
- `scripts/migration/validate_migration.py` - Validation script
- `scripts/migration/restore_backup.py` - Rollback script

## Expected Improvements

### Coverage
- **UNIT variations**: 1-3 digits (was 2 only) → +X% coverage
- **PREFIX variations**: 2-6 letters (was 2-4) → Covers PDAHH, FFSAL, etc.
- **SUFFIX-only queries**: New capability → +60-80% for digit-only queries
- **Component queries**: New capability → Flexible partial matching

### Accuracy
- Multi-prefix detection: 43% of suffixes have ≥2 prefixes
- Co-location indicator: 84.3% multi-prefix cases on same page
- Ambiguity warnings: Helps users refine queries

### Query Examples

| Query Type | Example | Old Behavior | New Behavior |
|------------|---------|--------------|--------------|
| SUFFIX-only | "5153" | Not recognized | Finds 4 tags, shows prefixes, warns |
| UNIT+SUFFIX | "04 5153" | Not recognized | Filters to UNIT 04 |
| PREFIX+SUFFIX | "PAHH 5153" | Limited | Exact component match |
| Full tag | "04 PAHH 5153" | Limited | Matches with/without annotation |
| With annotation | "04 PAHH 5153A/B/C" | Not handled | Annotation separated |

## Troubleshooting

### Migration fails at re-extraction
- Check if PDFs are accessible at paths in doc_id_map.json
- Check OCR dependencies (PaddleOCR)
- Review logs in reextraction_stats.json

### Re-indexing fails
- Verify OpenSearch is running: `curl http://localhost:9200`
- Check disk space for index
- Review OpenSearch logs

### Validation fails
- Compare backup count vs new count
- Review validation_report.json for details
- Check sample issues for systematic problems

### Need to rollback
```bash
python scripts/migration/restore_backup.py
```

## Post-Migration Checklist

- [ ] Backup completed successfully
- [ ] Re-extraction completed (check stats)
- [ ] Re-indexing completed (verify count)
- [ ] Validation passed (>95% success)
- [ ] Manual tests pass (query "5153", "04 PAHH 5153")
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Performance acceptable (<500ms per query)
- [ ] No regression in existing queries
- [ ] Documentation updated

## Support

If you encounter issues:
1. Check logs in `artifacts/migration/`
2. Review validation_report.json
3. Try rollback if critical
4. Contact system maintainer

## Timeline

- **Backup**: ~2-5 minutes
- **Re-extraction**: ~10-30 minutes (depends on corpus size)
- **Re-indexing**: ~2-5 minutes
- **Validation**: ~5 minutes
- **Total**: ~20-45 minutes

**Recommendation:** Run during low-usage period to avoid disruption.
