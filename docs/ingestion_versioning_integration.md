# Ingestion-Versioning Integration Guide

## Overview

The ingestion pipeline is now fully integrated with the versioning system (P2.6), enabling automatic snapshot creation after successful ingestion. This provides complete lineage tracking, reproducibility, and rollback capabilities for your RAG system.

## Table of Contents

1. [Architecture](#architecture)
2. [Usage Patterns](#usage-patterns)
3. [Workflow Examples](#workflow-examples)
4. [Version Management](#version-management)
5. [Best Practices](#best-practices)

---

## Architecture

### Integration Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Ingestion Pipeline                        │
│  (tools/ingest.py)                                          │
│                                                              │
│  1. PDF Processing                                          │
│  2. Chunk Generation                                        │
│  3. Manifest Creation  ◄───────────────────┐               │
│  4. Version Snapshot (optional)             │               │
└──────────────────────┬──────────────────────┴───────────────┘
                       │
                       │ Creates
                       ▼
         ┌─────────────────────────────┐
         │   Ingestion Manifest        │
         │  (manifest.json)            │
         │                             │
         │  - Configuration            │
         │  - Source statistics        │
         │  - Chunk statistics         │
         │  - Artifact paths           │
         └──────────────┬──────────────┘
                        │
                        │ Used by
                        ▼
         ┌─────────────────────────────┐
         │   Version Manager           │
         │  (app/storage)              │
         │                             │
         │  - Create snapshots         │
         │  - Track history            │
         │  - Enable rollback          │
         │  - Compare versions         │
         └─────────────────────────────┘
```

### Key Features

1. **Automatic Versioning**: Optional `--create-version` flag triggers snapshot creation after ingestion
2. **Manifest Generation**: Comprehensive ingestion manifest tracks all configuration and metrics
3. **Artifact Management**: Version snapshots include chunks, manifests, and indices
4. **Lineage Tracking**: Full lineage from source PDFs → chunks → embeddings → versions
5. **Rollback Support**: Restore any previous version with full fidelity

---

## Usage Patterns

### Pattern 1: Ingestion with Auto-Versioning

Run ingestion and automatically create a version snapshot:

```bash
python tools/ingest.py \
    --source-dir D:\Data_Raw \
    --output-dir artifacts/ingestion_v1 \
    --workers 4 \
    --chunk-size 1000 \
    --chunk-overlap 200 \
    --extract-tables \
    --create-version \
    --version-id v1.0 \
    --version-description "Initial production baseline" \
    --version-tags production baseline
```

**What happens:**
1. PDFs are processed from `D:\Data_Raw`
2. Chunks and manifests are written to `artifacts/ingestion_v1/`
3. An ingestion manifest is created: `artifacts/ingestion_v1/manifest.json`
4. A version snapshot is created in `artifacts/versions/v1.0/`
5. Version history is updated in `artifacts/versions/version_history.json`

### Pattern 2: Ingestion without Versioning

Run ingestion normally, create version later:

```bash
# Step 1: Run ingestion
python tools/ingest.py \
    --source-dir D:\Data_Raw \
    --output-dir artifacts/ingestion_test \
    --workers 4

# Step 2: Create version manually (if needed)
python tools/ops/create_version.py \
    --ingestion-dir artifacts/ingestion_test \
    --version-id test_v1 \
    --description "Test ingestion snapshot" \
    --tags test experimental
```

**When to use:**
- Testing new configurations
- Exploratory data processing
- When you're not sure if you want to keep the results

### Pattern 3: Production Ingestion

Use the production script with built-in versioning:

```bash
python tools/ops/run_production_ingest.py
```

This automatically:
- Ingests from `D:\Data_Raw`
- Enables table extraction
- Creates version `production_baseline`
- Tags with `production` and `baseline`

---

## Workflow Examples

### Example 1: Initial Production Deployment

```bash
# 1. Run initial ingestion with versioning
python tools/ingest.py \
    --source-dir D:\Data_Raw \
    --output-dir artifacts/ingestion_production \
    --workers 4 \
    --extract-tables \
    --create-version \
    --version-id v1.0_production \
    --version-description "Initial production deployment - 150 PDFs" \
    --version-tags production baseline stable

# 2. Build indices (if needed)
# ... (index building step)

# 3. List versions to verify
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    for v in vm.list_versions(): print(f'{v[\"version_id\"]}: {v[\"description\"]}')"
```

**Output:**
```
v1.0_production: Initial production deployment - 150 PDFs
```

### Example 2: Incremental Update

```bash
# 1. Ingest new documents to separate directory
python tools/ingest.py \
    --source-dir D:\Data_Raw_New \
    --output-dir artifacts/ingestion_incremental \
    --workers 4 \
    --extract-tables \
    --create-version \
    --version-id v1.1_incremental \
    --version-description "Added 20 new technical specifications" \
    --version-tags production incremental

# 2. Version is now available for comparison
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    diff = vm.compare_versions('v1.0_production', 'v1.1_incremental'); \
    print(diff)"
```

### Example 3: Rollback Scenario

```bash
# Scenario: v1.2 had issues, need to rollback to v1.1

# 1. List available versions
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    print('Available versions:'); \
    for v in vm.list_versions(): print(f'  {v[\"version_id\"]}')"

# 2. Rollback to v1.1
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    success = vm.rollback('v1.1_production', \
                          'artifacts/ingestion_active', \
                          'artifacts/indices_active'); \
    print(f'Rollback successful: {success}')"

# 3. Verify current version
python -c "from app.storage.version_manager import VersionManager; \
    vm = VersionManager('artifacts'); \
    print(f'Current version: {vm.get_current_version()}')"
```

### Example 4: Version from Existing Ingestion

```bash
# Create a version from an ingestion that was run without --create-version

python tools/ops/create_version.py \
    --ingestion-dir artifacts/ingestion_test \
    --version-id v1.0_test \
    --description "Test run from 2025-01-02" \
    --tags test historical

# The script will:
# - Auto-detect chunks and documents
# - Generate a manifest if missing
# - Create version snapshot
```

---

## Version Management

### Version Naming Conventions

**Recommended patterns:**

1. **Semantic Versioning**: `v1.0`, `v1.1`, `v2.0`
   - Use for production deployments
   - Increment major for breaking changes
   - Increment minor for additions

2. **Timestamp-based**: `v20250102_150000`
   - Use for frequent updates
   - Automatic if no `--version-id` provided

3. **Environment-based**: `production_baseline`, `staging_v1`, `dev_experiment`
   - Use for multi-environment setups
   - Clear indication of deployment target

4. **Feature-based**: `v1.0_tables`, `v2.0_multilang`
   - Use for feature-specific versions
   - Tracks what was added

### Version Metadata

Each version stores:

```json
{
  "version_id": "v1.0_production",
  "created_at": "2025-01-02T15:00:00Z",
  "description": "Initial production deployment",
  "tags": ["production", "baseline", "stable"],
  "ingestion_id": "2025-01-02T15:00:00",
  "artifacts": {
    "chunks_jsonl": "versions/v1.0_production/chunks.jsonl",
    "manifest": "versions/v1.0_production/manifest.json",
    "bm25_dir": "versions/v1.0_production/bm25",
    "faiss_dir": "versions/v1.0_production/faiss"
  },
  "stats": {
    "total_chunks": 12500,
    "unique_chunks": 12500,
    "total_embedded": 12500
  }
}
```

### Version Operations

**List versions:**
```python
from app.storage.version_manager import VersionManager

vm = VersionManager("artifacts")

# List all versions
versions = vm.list_versions()

# Filter by tags
prod_versions = vm.list_versions(tags=["production"])

# Limit results
recent = vm.list_versions(limit=5)
```

**Compare versions:**
```python
comparison = vm.compare_versions("v1.0", "v1.1")
print(f"Chunk delta: {comparison['diff']['chunks_delta']}")
```

**Get version details:**
```python
version = vm.get_version("v1.0_production")
print(f"Created: {version['created_at']}")
print(f"Chunks: {version['stats']['total_chunks']}")
```

**Rollback:**
```python
success = vm.rollback(
    version_id="v1.0_production",
    target_ingestion_dir="artifacts/ingestion_active",
    target_index_dir="artifacts/indices_active"
)
```

---

## Best Practices

### 1. Version Naming

✅ **DO:**
- Use consistent naming conventions
- Include environment/stage info
- Use semantic versioning for production
- Add descriptive tags

❌ **DON'T:**
- Use special characters or spaces
- Make names too long (>50 chars)
- Reuse version IDs

### 2. Version Frequency

**Create versions when:**
- Deploying to production
- After significant data additions
- Before experimental changes
- At regular intervals (e.g., weekly for active development)

**Don't version:**
- Every single test run
- Failed ingestions
- Debugging sessions
- Identical re-runs

### 3. Version Tags

**Recommended tags:**
- `production`, `staging`, `dev` - Environment
- `baseline`, `incremental`, `refresh` - Type
- `stable`, `experimental`, `test` - Status
- `tables`, `multilang`, `ocr` - Features

### 4. Version Cleanup

Regularly review and delete old versions:

```python
from app.storage.version_manager import VersionManager

vm = VersionManager("artifacts")

# List old test versions
test_versions = vm.list_versions(tags=["test"])

# Delete if no longer needed
for v in test_versions:
    if should_delete(v):  # Your logic
        vm.delete_version(v["version_id"])
```

### 5. Documentation

Always document:
- What changed in this version
- Why the version was created
- Known issues or limitations
- Dependencies or requirements

Use `--version-description` to capture this inline:

```bash
--version-description "Added 50 new specs (TCVN 5574-2012 series). Fixed table extraction for complex layouts. Known issue: Some Vietnamese diacritics may be missing."
```

### 6. Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: Ingestion Pipeline

on:
  push:
    paths:
      - 'data/**'

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run ingestion with versioning
        run: |
          python tools/ingest.py \
            --source-dir data/raw \
            --output-dir artifacts/ingestion \
            --create-version \
            --version-id "v$(date +%Y%m%d_%H%M%S)" \
            --version-description "Automated ingestion from commit ${{ github.sha }}" \
            --version-tags production automated

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: version-snapshot
          path: artifacts/versions/
```

---

## Troubleshooting

### Issue: Version creation fails with "chunks not found"

**Solution:**
Ensure chunks were written. Check that `--emit-jsonl` is enabled (default: True).

```bash
ls artifacts/ingestion_XXX/chunks/chunks.jsonl
```

### Issue: Manifest format mismatch

**Solution:**
Use the new manifest format from `ManifestWriter`. For old ingestions, use `create_version.py` which auto-detects formats.

### Issue: Version already exists

**Solution:**
Either:
1. Choose a different version ID
2. Delete the old version: `vm.delete_version("v1.0", force=True)`
3. Use `--version-id` with timestamp suffix

---

## Summary

**Integration Benefits:**

✅ **Reproducibility**: Every ingestion can be exactly reproduced
✅ **Rollback**: Instant restoration to any previous version
✅ **Comparison**: Track changes between versions
✅ **Lineage**: Complete audit trail from source to index
✅ **Safety**: Test changes without affecting production

**Quick Reference:**

```bash
# Ingest with versioning
python tools/ingest.py --source-dir <dir> --create-version --version-id <id>

# Create version from existing
python tools/ops/create_version.py --ingestion-dir <dir> --version-id <id>

# Production ingestion (auto-versioned)
python tools/ops/run_production_ingest.py

# List versions
python -c "from app.storage.version_manager import VersionManager; ..."
```

---

## Next Steps

With ingestion-versioning integration complete, consider:

1. **P3: 2-Tier Reranking** - Implement advanced retrieval with reranking
2. **Index Versioning** - Extend versioning to BM25/FAISS indices
3. **Incremental Updates** - Add support for incremental ingestion with delta tracking
4. **Performance Monitoring** - Track ingestion metrics across versions
5. **Automated Testing** - Version-aware integration tests

For questions or issues, refer to:
- `app/storage/version_manager.py` - Version management implementation
- `tools/ingest.py` - Main ingestion pipeline
- `tools/ops/create_version.py` - Post-ingestion versioning tool
