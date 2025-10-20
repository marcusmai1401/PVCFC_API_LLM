# P&ID Enhancement Migration - Quick Start

## TL;DR - 3 Commands

```bash
# 1. Backup (REQUIRED!)
python scripts/migration/backup_pid_data.py

# 2. Run complete migration (backup → re-extract → re-index → validate)
python scripts/migration/run_migration.py

# 3. If something goes wrong - rollback
python scripts/migration/restore_backup.py
```

That's it! The master script handles everything.

## What Happens

### Before Migration
```
Query: "5153"
Result: Not recognized (semantic search)
```

### After Migration
```
Query: "5153"
Result:
  ✓ Found 4 tags: 04 PAHH 5153A/B/C, 04 PALL 5153A/B/C,
                  04 PI 5153A/B/C, 04 PXT 5153A/B/C
  ⚠ Warning: "4 different prefixes found for suffix 5153"
  💡 Suggestion: "Try 'PAHH 5153' or '04 5153' for specificity"
```

## New Query Examples

```bash
# SUFFIX-only (NEW!)
"5153"       → All tags with number 5153
"501"        → All tags with number 501

# Component queries (NEW!)
"04 5153"    → Tags in UNIT 04 with SUFFIX 5153
"PAHH 5153"  → Only PAHH instruments with 5153
"04 PAHH"    → All PAHH in UNIT 04

# Full tags (IMPROVED!)
"04 PAHH 5153"       → Exact match
"04 PAHH 5153A/B/C"  → Also exact (annotation separated)
```

## Pre-flight Check

Before running migration:

```bash
# 1. Check OpenSearch is running
curl http://localhost:9200/_cluster/health

# 2. Check ENABLE_PID_TAGS is true
grep ENABLE_PID_TAGS .env

# 3. Check disk space (need ~500MB free)
df -h

# 4. Check PDFs are accessible
ls "D:\Data_Raw"  # Or your PDF directory
```

## Migration Steps (Manual)

If you prefer step-by-step:

```bash
# Step 1: Backup
python scripts/migration/backup_pid_data.py
# → artifacts/migration_backup/

# Step 2: Re-extract
python scripts/migration/reextract_tags.py
# → artifacts/migration/tags_new_schema.jsonl

# Step 3: Re-index
python scripts/migration/reindex_tags.py
# → Rebuilds pvcfc_pid_tags index

# Step 4: Validate
python scripts/migration/validate_migration.py
# → artifacts/migration/validation_report.json
```

## Rollback

If migration fails or has issues:

```bash
python scripts/migration/restore_backup.py
```

This restores everything to pre-migration state.

## Post-Migration Testing

Quick smoke test:

```bash
# Test 1: SUFFIX-only
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "5153", "language": "vi"}' | jq .

# Expected: 4 tags with multi-prefix warning

# Test 2: Component query
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "04 PAHH 5153", "language": "vi"}' | jq .

# Expected: Exact match with annotation
```

Automated tests:
```bash
pytest tests/test_pid_enhancements.py -v
```

## Timeline

| Phase | Duration |
|-------|----------|
| Backup | 2-5 min |
| Re-extraction | 10-30 min |
| Re-indexing | 2-5 min |
| Validation | 5 min |
| **Total** | **20-45 min** |

## What Can Go Wrong

**Common issues:**

1. **"PDFs not found"** during re-extraction
   - Fix: Update paths in doc_id_map.json
   - Or: Move PDFs to expected locations

2. **"OpenSearch connection failed"**
   - Fix: Start OpenSearch: `docker-compose up -d opensearch`
   - Check .env: OPENSEARCH_HOST, OPENSEARCH_PORT

3. **"Count mismatch"** in validation
   - Check: Did all PDFs extract successfully?
   - Review: artifacts/migration/reextraction_stats.json

4. **Performance degradation**
   - Usually not an issue (same data, better queries)
   - Check: OpenSearch heap size sufficient?

## Support Files

- **Full guide**: `scripts/migration/README_MIGRATION.md`
- **User guide**: `docs/PID_SEARCH_ENHANCEMENT_GUIDE.md`
- **Changelog**: `docs/CHANGELOG_PID_ENHANCEMENT.md`

## Need Help?

1. Check validation report: `artifacts/migration/validation_report.json`
2. Review logs in `artifacts/migration/`
3. Consult README_MIGRATION.md
4. If critical: `python scripts/migration/restore_backup.py`

---

**Status**: Ready to run
**Risk**: Medium (hard migration, but rollback available)
**Recommendation**: Run during low-usage period
