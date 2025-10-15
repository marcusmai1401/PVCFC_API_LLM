# Project Cleanup Recommendations

Generated: 2025-10-15

## Summary

After reorganizing the project structure, several folders contain legacy, duplicate, or obsolete files that can be cleaned up:

- **scripts/**: 122 files → Recommend removing ~63 files (52% reduction)
- **tools/**: 113 files → Recommend removing ~40 files (35% reduction)
- **tests/**: 49 files → **KEEP ALL** (production pytest suite)
- **data/**: 755 items → Needs inspection (likely test data or cache)

**Total potential cleanup: ~100+ files**

---

## 1. SCRIPTS/ Folder (122 files)

### 1.1 Root Level - DELETE (13 files)

These are legacy/obsolete files from early development:

```
scripts/audit_logging_system.py
scripts/audit_logging_system_fixed.py
scripts/create_test_pdf.py
scripts/docker_deploy.sh                    # Only 5 bytes, empty file
scripts/phase1_index_to_weaviate.py         # Old phase test
scripts/phase1_smoke_test.py                # Old phase test
scripts/phase2_semantic_smoke_test.py       # Old phase test
scripts/phase3_reranker_smoke_test.py       # Old phase test
scripts/phase4_rag_integration_test.py      # Old phase test
scripts/semantic_check.py                   # Old smoke test
scripts/vision_logging_smoke.py             # Old smoke test
scripts/peek_redaction.py                   # Old utility
scripts/try_redact.py                       # Old utility
```

### 1.2 Root Level - REVIEW for Duplication (5 files)

These may overlap with `launchers/` or `scripts/ingestion/`:

```
scripts/dev.ps1                  # Compare with launchers/
scripts/run.ps1                  # Compare with launchers/
scripts/smoke.ps1                # Compare with launchers/
scripts/test.ps1                 # Compare with launchers/
scripts/ingest_pdf.ps1           # Compare with scripts/ingestion/
scripts/run_ingest_v1.ps1        # Compare with scripts/ingestion/
```

**Action**: Compare content, delete if duplicate.

### 1.3 Root Level - KEEP (5 files)

```
scripts/list_corpus_files.py     # Utility for corpus management
scripts/verify_weaviate_data.py  # Weaviate verification
scripts/view_logs.ps1            # Log viewer utility
scripts/README.md                # Index file
```

### 1.4 scripts/test_scripts/ - ARCHIVE ENTIRE FOLDER (~40 files)

This folder contains old development test scripts that overlap with the proper `tests/` pytest suite:

```
scripts/test_scripts/
├── analyze_extraction_coverage.py
├── audit_offline_build_7steps.py
├── debug_*.py (3 files)
├── ocr_on_pdf_page.py
├── smoke_test_phase0.py
├── test_api_*.py (3 files)
├── test_deduplication_behavior.py
├── test_diagnostic_queries.py
├── test_embedding_fix.py
├── test_gemini_*.py (2 files)
├── test_genai_api.py
├── test_logging_system.py
├── test_markdown_conv.py
├── test_ocr*.py (2 files)
├── test_page_*.py (2 files)
├── test_phase1_fixes.py
├── test_production_*.py (2 files)
├── test_reingest_with_tables.py
├── test_system_status*.py (2 files)
├── test_table_*.py (3 files)
├── test_torque_query_after_fix.py
├── test_vietnamese_debug.py
├── test_vision_citation_fix.py
├── verify_ingestion_ocr.py
├── online_audit/ (8 files + 2 JSON datasets)
└── README.md
```

**Recommendation**: Move entire folder to `archive/test_scripts_legacy/` or delete if tests are covered in `tests/`.

### 1.5 Organized Subfolders - KEEP

```
scripts/debug/              # 3 files - Keep
scripts/diagnostics/        # 13 files - Keep
scripts/eval_bge_rerank/    # 6 files - Keep (evaluation suite)
scripts/examples/           # 2 files - Keep (usage examples)
scripts/ingestion/          # 3 files - Keep
scripts/opensearch/         # 5 files - Keep (OpenSearch utilities)
scripts/test/               # 11 files - Keep
scripts/utilities/          # 5 files - Keep
scripts/weaviate/           # 2 files - Keep (Weaviate utilities)
```

---

## 2. TOOLS/ Folder (113 files)

### 2.1 Root Level - DELETE (40+ files)

#### Old Versions / Backups (5 files)
```
tools/ingest_backup_20250929.py
tools/ingest_v1.py
tools/build_faiss_local_backup_20250929.py
tools/build_faiss_local_v1.py
```

#### Old Demo/Test Files (3 files)
```
tools/demo_phase1.py
tools/demo_pipeline.py
tools/smoke_test.py
```

#### Test Files That Should Be in tests/ (~30 files)

All `test_*.py` files in tools/ root should either:
- Move to `tests/` if still relevant
- Delete if redundant with existing pytest tests

```
tools/test_bm25_index.py
tools/test_chunker.py
tools/test_citation_extraction.py
tools/test_confidence_calibration.py
tools/test_document_classifier.py
tools/test_embedding_implementation.py
tools/test_faiss_index.py
tools/test_fixes.py
tools/test_gemini_25.py
tools/test_gemini_25_detailed.py
tools/test_gemini_2_5.py
tools/test_gemini_api.py
tools/test_gemini_embeddings.py
tools/test_generator.py
tools/test_hybrid_retriever.py
tools/test_hybrid_search.py
tools/test_implementation.py
tools/test_ingest_performance.py
tools/test_intent_detection.py
tools/test_page_range_expansion.py
tools/test_pdf_processor.py
tools/test_phase2_simple.py
tools/test_provider_flexibility.py
tools/test_query_transform.py
tools/test_reranker.py
tools/test_sdk_difference.py
```

### 2.2 Root Level - KEEP (28 files)

#### Active Ingestion Tools
```
tools/ingest.py                          # Main ingestion tool
tools/ingest_single_pdf.py
```

#### Active Index Builders
```
tools/build_bm25_index.py
tools/build_bm25_simple.py
tools/build_faiss_from_chunks.py
tools/build_faiss_local.py
tools/build_page_embeddings.py
tools/build_page_index.py
tools/fix_indexes_single_pass.py
```

#### Evaluation & QA Tools
```
tools/analyze_filtered_qa.py
tools/batch_query_runner.py
tools/create_golden_qa_v1.py
tools/evaluate_golden_qa_v1.py
tools/evaluate_rerank_results.py
tools/eval_e2e.py
tools/eval_retrieval.py
tools/filter_qa_candidates.py
tools/generate_synthetic_qa.py
tools/qa_extraction.py
tools/run_evaluation.py
```

#### Utilities
```
tools/analyze_logs.py
tools/create_sample_pdf.py
tools/extract_metadata.py
tools/extract_pilot.py
tools/list_gemini_models.py
tools/list_models_simple.py
tools/migrate_page_metadata.py
tools/monitor_api_usage.py
tools/pdf_renderer.py
tools/search_faiss_local.py
tools/verify_ignore_config.py
tools/verify_phase2_complete.py
tools/verify_phase2_final.py
tools/verify_tags_in_index.py
tools/verify_weaviate_infrastructure.py
tools/FIX_INDEXES_README.md
```

### 2.3 Organized Subfolders - KEEP

```
tools/analysis/         # 11 files - Keep
tools/benchmarks/       # 5 files - Keep
tools/diagnostics/      # 2 files - Keep (but check overlap with scripts/diagnostics/)
tools/ocr/              # 6 files - Keep
tools/ops/              # 8 files - Keep (production operations)
tools/patches/          # 3 files - Keep
tools/verify/           # 5 files - Keep
```

**Note**: `tools/diagnostics/` (2 files) may overlap with `scripts/diagnostics/` (13 files). Consider consolidating.

---

## 3. TESTS/ Folder (49 files)

### ✅ KEEP ALL

This is the production pytest suite. All files are relevant and actively used:

```
tests/conftest.py
tests/test_*.py (46 test files)
tests/OPTIMIZATION_REPORT.md
tests/p*_test_*.py (phase tests)
```

---

## 4. DATA/ Folder (755 items)

### Inspection Needed

```
data/staging/  (755 items)
```

**Questions to answer:**
1. What type of data is this? (Test PDFs? Cached data? Corpus samples?)
2. Is it still needed? (Actual corpus is in `D:\Data_Raw`)
3. Is it version-controlled? (Check `.gitignore`)

**Recommendations:**
- If test fixtures → Move to `tests/fixtures/`
- If cached/generated data → Delete (regenerate when needed)
- If sample corpus → Keep but document purpose
- If duplicate of `D:\Data_Raw` → Delete

---

## Recommended Action Plan

### Phase 1: Safe Deletions (No Risk)
1. Delete empty/obsolete files in `scripts/` root (13 files)
2. Delete old backups in `tools/` (5 files)
3. Delete old demo files in `tools/` (3 files)

**Total: 21 files, ~15 minutes**

### Phase 2: Test File Consolidation (Low Risk)
1. Review and delete redundant `test_*.py` in `tools/` (~30 files)
2. Move any useful tests to `tests/` first

**Total: ~30 files, ~30 minutes**

### Phase 3: Archive Legacy Tests (Medium Risk)
1. Move `scripts/test_scripts/` to `archive/` (~40 files)
2. Keep `scripts/test_scripts/online_audit/golden_*.json` datasets

**Total: ~40 files, ~10 minutes**

### Phase 4: Review Duplicates (Needs Manual Check)
1. Compare launcher scripts in `scripts/` vs `launchers/`
2. Consolidate `tools/diagnostics/` vs `scripts/diagnostics/`
3. Inspect and cleanup `data/staging/`

**Total: Variable, ~30-60 minutes**

---

## Git Safety

Before any deletions:
```powershell
# Create cleanup branch
git checkout -b chore/cleanup-legacy-files

# After cleanup
git add -A
git commit -m "chore: remove legacy and duplicate files"
```

---

## Summary Table

| Folder | Current | Keep | Delete | Archive | Reduction |
|--------|---------|------|--------|---------|-----------|
| scripts/ | 122 | 59 | 13 | 50 | 52% |
| tools/ | 113 | 70 | 40 | 3 | 35% |
| tests/ | 49 | 49 | 0 | 0 | 0% |
| data/ | 755 | TBD | TBD | TBD | TBD |
| **Total** | **1039** | **~178** | **~53** | **~53** | **~10%** |

---

## Next Steps

1. Review this document
2. Confirm deletion lists
3. Execute Phase 1 (safe deletions)
4. Execute Phase 2-4 as agreed
5. Update documentation references if needed
