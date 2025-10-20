# Changelog

All notable changes to the PVCFC RAG System.

## [Unreleased]

### Added - P&ID Search Enhancement v2 (2025-10-18)

**Major enhancement to P&ID tag extraction and search based on data analysis**

**New Capabilities:**
- SUFFIX-only search (e.g., "5153" finds all tags with that number)
- Component-based search (e.g., "04 5153", "PAHH 5153", "04 PAHH")
- Multi-prefix grouping and ambiguity warnings (43% of suffixes have multiple prefixes)
- Annotation separation (A/B/C, 1oo2 patterns)
- Variant extraction (A/B/C single letters)

**Schema Changes (BREAKING):**
- `area` → `unit` (1-3 digits now, was 2 only)
- `code` → `prefix` (2-6 letters now, was 2-4)
- `num` → `suffix` (digits only, no letters)
- Added `variant` field (single letter)
- Added `annotation` field (A/B/C, 1oo2)

**Files:**
- See `docs/CHANGELOG_PID_ENHANCEMENT.md` for complete details
- Migration guide: `scripts/migration/README_MIGRATION.md`
- User guide: `docs/PID_SEARCH_ENHANCEMENT_GUIDE.md`

**Migration Required:** Hard migration with full re-indexing
- Run: `python scripts/migration/run_migration.py`
- Rollback: `python scripts/migration/restore_backup.py`

---

### Added - P&ID Retrieval Enhancement v1 (2025-10-16)

**New Features:**
- Tag-aware query processing for P&ID and technical drawings
- Adaptive RRF fusion with query-type based weighting
- Specialized PID tag reranking with fuzzy matching
- Equipment tag boosting in OpenSearch (10x metadata, 5x text)
- Tag filtering in Weaviate (ContainsAny)
- Tag-parameter proximity detection (100 char window)

**New Components:**
- `app/rag/query_processing/pid_query_enhancer.py` - Tag detection & enhancement
- `app/rag/query_processing/query_type_detector.py` - Query classification
- `app/rag/rerankers/pid_tag_reranker.py` - Tag-aware reranking
- `scripts/opensearch/update_tags_mapping.py` - Schema update script
- `scripts/weaviate/add_tags_property.py` - Schema update script
- `scripts/utilities/backfill_tags.py` - Data migration script
- `tests/eval_pid_retrieval.py` - Evaluation framework
- `tests/ground_truth/pid_queries.json` - Test cases
- `docs/guides/PID_RETRIEVAL_ENHANCEMENT.md` - User guide

**Enhanced Components:**
- `app/rag/indexers/opensearch_bm25_retriever.py` - Added `search_with_tag_boosting()`
- `app/rag/weaviate_retriever.py` - Added `search_with_tag_filter()`
- `app/rag/hybrid_weaviate_opensearch_retriever.py` - Added `retrieve_enhanced()` and `_rrf_fusion_adaptive()`

**Configuration:**
- Added P&ID settings to `env.example`
  - `ENABLE_PID_ENHANCEMENT`
  - `PID_TAG_BOOST_EXACT`, `PID_TAG_BOOST_FUZZY`, `PID_TAG_BOOST_PROXIMITY`
  - `PID_FUZZY_THRESHOLD`
  - `RRF_ADAPTIVE_WEIGHTS`

**Expected Improvements:**
- Precision@5: ~60-70% → ≥90% (+20-30%)
- Recall@10: ~80% → ≥95% (+15%)
- Latency P50: ~1.5s → ≤2.5s (acceptable tradeoff)

**Schema Changes:**
- OpenSearch: Added `tags` and `tags_raw` fields (text + keyword)
- Weaviate: Added `tags` property (TEXT_ARRAY)

**Migration Required:**
- Run `scripts/opensearch/update_tags_mapping.py` (one-time)
- Run `scripts/weaviate/add_tags_property.py` (one-time)
- Run `scripts/utilities/backfill_tags.py` (one-time, ~5-10 min)

---

## [0.7.0] - 2025-10-15

### Changed
- Enhanced BGE reranking configuration
- Improved confidence scoring with defensive clamping
- Updated Weaviate infrastructure

### Fixed
- Page metadata extraction bugs
- Citation validation edge cases
- Confidence calculation defensive programming

---

## [0.6.0] - 2025-10-10

### Added
- Hybrid Modern retrieval (Weaviate + OpenSearch)
- BGE CrossEncoder reranking
- Production index building tools

### Changed
- Migrated from FAISS to Weaviate for vector search
- Replaced offline BM25 with OpenSearch

---

## [0.5.0] - 2025-10-01

### Added
- PaddleOCR PP-OCRv5 integration
- Table extraction from PDFs
- Hierarchical chunking strategies

---

*For detailed version history, see git log and DOCUMENTS_CHATBOX/CHANGLOG_README/*
