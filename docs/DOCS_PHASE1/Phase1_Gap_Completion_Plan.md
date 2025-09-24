
## 1) Executive Summary

Phase 1 delivered robust vector-PDF processing, Markdown conversion, baseline hierarchical chunking, and BM25 offline search. However, several scoped items remain incomplete for a production-ready ingestion and retrieval corpus:

- Multithreaded ingestion pipeline for throughput on Windows.
- Scanned PDF handling at ingest (OCR on scans/mixed) and optional unstructured.io parser for complex layouts.
- Advanced segmentation with explicit parent-child hierarchy populated, and richer metadata on chunks (doc_type, revision, source_format, page, heading/level).
- JSONL manifests (corpus/checksums) and JSONL chunk outputs to support streaming, lineage, and tooling.
- Optional auto classification at ingest (LLM light + rules) consistent with MVP features [[Agreed MVP features: device tag search across 4 types, auto classification at ingest, etc.]] [[memory:9168686]].

This plan describes deliverables, tasks, feasibility, risks, and acceptance criteria to complete these gaps with minimal disruption to existing workflows.

---

## 2) Scope and Non-Goals

In Scope (Phase 1 Gap Completion):
- Multithread ingestion of PDFs with safe Windows defaults.
- Enable OCR-at-ingest toggle, use existing `PDFProcessor` OCR, configurable language; keep unstructured.io optional.
- Populate parent-child chunk relationships and enrich metadata at chunk level.
- Emit JSONL: `artifacts/chunks/chunks.jsonl`, `manifests/corpus.jsonl`, `manifests/checksums.jsonl`.
- CLI tooling for ingest and index build working end-to-end on a clean Windows setup.

Non-Goals (future phases unless trivial):
- Full HOCR/bbox alignment and visual highlights (Phase 2/3 item).
- Vision-assisted verification or LLM heavy flows.
- Production UI workflow; only CLI and dev UI integrations if trivial.

---

## 3) Current State (Evidence)

- Vector PDFs: Extract → Normalize → Markdown → Chunk → BM25 works.
  - `app/rag/extractors/vector_extractor.py` — vector extraction
  - `app/rag/converters/markdown_converter.py` — to Markdown
  - `app/rag/chunkers/hierarchical_chunker.py` — hierarchical chunker (no parent_id populated yet)
  - `app/ingestion/text_chunker.py` — sentence/semantic chunker with metadata basics
  - `tools/demo_pipeline.py` — end-to-end demo (skips scans)
  - `tools/build_bm25_index.py` — builds BM25 from chunks.json (JSON, not JSONL)
- Scans: OCR exists in code (`app/ingestion/pdf_processor.py`) and is enabled via `--enable-ocr` in Phase 3, not Phase 1 report.
- JSONL outputs: not used for chunks; logs and QA do use JSONL elsewhere.

---

## 4) Deliverables

1. Ingestion Pipeline (Multithread + OCR Optional)
   - CLI: `tools/ingest.py` with options (`--source-dir`, `--output-dir`, `--workers`, `--enable-ocr`, `--ocr-lang`, `--parser=auto|pymupdf|unstructured`, `--emit-jsonl`).
   - Throughput: ≥ 2× speedup over single-thread on 4 sample PDFs (Windows).
   - Output: normalized Markdown per document, processed JSON, OCR cache persistence.

2. Advanced Chunking & Metadata
   - Populate `parent_chunk_id` for child chunks; track heading/level.
   - Enrich chunk metadata: `doc_type`, `revision`, `source_format`, `page`, `heading`, `level`, `file_name`.
   - Strategy options: `small-to-big` and `sentence-window` (windowed by sentence length around boundaries).

3. JSONL Artifacts & Manifests
   - `artifacts/chunks/chunks.jsonl` — one chunk per line (parent-child via `parent_chunk_id`).
   - `manifests/corpus.jsonl` — per-document manifest (doc_id, doc_type, revision, path, hash, source_format, pages).
   - `manifests/checksums.jsonl` — file-level checksums for idempotent ingest.

4. Index Build Compatibility
   - `tools/build_bm25_index.py` can read from JSONL chunks and older JSON chunks; flag `--chunks-jsonl`.

5. Tests & Docs
   - Unit tests for parent-child correctness and metadata presence.
   - Ingest integration test on sample PDFs.
   - Updated docs in `docs/` and `Build_plan_README/`.

---

## 5) Detailed Workstreams and Tasks

### A) Ingestion Pipeline (Multithread + OCR + Optional Unstructured)

Goals:
- Improve throughput; robust handling of scans via OCR; keep optional unstructured.io for complex layouts.

Tasks:
1. Create `tools/ingest.py` (Typer/Click) to orchestrate ingest:
   - Flags: `--source-dir`, `--output-dir`, `--workers`, `--enable-ocr`, `--ocr-lang`, `--parser`, `--emit-jsonl`.
   - Reads PDFs, calls `PDFProcessor.process_pdf`.
   - Writes: `data/processed/markdown/*.md`, `artifacts/chunks/documents/*_processed.json`.
   - Emits `manifests/{corpus,checksums}.jsonl`.
2. Multithreading:
   - Wrap directory processing with `ThreadPoolExecutor(max_workers=workers)` in `PDFProcessor.process_directory` or inside `tools/ingest.py` dispatcher.
   - Default workers = `min(4, os.cpu_count() or 4)` for Windows safety.
   - Ensure thread-safe logging; use atomic write (temp file + rename) for outputs.
3. OCR Enablement:
   - Surface `--enable-ocr` and `--ocr-lang` → pass to `PDFProcessor`.
   - Validate Tesseract presence; degrade gracefully with clear logs if missing.
4. Optional unstructured.io:
   - Parser switch: `auto` (PyMuPDF → OCR; later optionally unstructured if both fail or doc type hints), `pymupdf`, `unstructured`.
   - Keep `unstructured` optional dependency; skip if not installed; log hint.
5. Manifests & Checksums:
   - Compute SHA256 for each file; write/update `manifests/checksums.jsonl`.
   - Create/update `manifests/corpus.jsonl` with doc_id, doc_type (if available), source_format, revision (if detected), pages, hash.

Acceptance Criteria:
- `python tools/ingest.py --source-dir data/raw/phase1_pilot --workers 4 --enable-ocr --ocr-lang eng` completes successfully; artifacts and manifests created.
- Throughput improvement ≥ 2× vs single-thread (local test).
- If Tesseract absent, run completes with scans marked but not OCR’d; clear warning emitted.

Feasibility: High (OCR path already implemented; threading straightforward).
Risks: Tesseract install variance on Windows; mitigated by `app/ingestion/ocr_config.py` checks and docs.

---

### B) Advanced Segmentation & Metadata (Parent-Child + Strategies)

Status: Implemented
- Parent-child: Parent chunk per heading; child chunks carry `parent_chunk_id` (observed ~99%+ where applicable on pilot set).
- Strategies available:
  - `hierarchical` (default)
  - `sentence-window` (windowed by sentences with configurable overlap%)
  - `small-to-big` (aggregate sentences up to target size; preserves parent-child)
- Metadata on chunks: ensured presence of `doc_id`, `page_start`, `page_end`, `heading`, `level`; metadata includes `doc_type`, `revision`, `source_format`, `file_name`.

CLI flags for strategy:
- `--chunk-strategy [hierarchical|sentence-window|small-to-big]`
- `--sentence-window-size N` (for sentence-window)

Goals:
- Populate hierarchical relationships and richer metadata at chunk level.

Tasks:
1. Populate `parent_chunk_id` in `HierarchicalChunker`:
   - Treat each heading section as a parent; children are windowed chunks within the section; set `parent_chunk_id` accordingly.
   - Preserve `heading` and `level` on children.
2. Add `sentence-window` strategy in `HierarchicalChunker`:
   - Split by sentences; when exceeding target size, allow an overlap window of previous N characters/sentences (configurable, defaults from `TextChunker`).
3. Metadata enrichment at chunk level:
   - Propagate `source_format` from `PDFProcessor`.
   - Add `doc_type`, `revision` if available (see C below for classification & revision heuristics).
   - Ensure `page_start/page_end`, `heading`, `level`, `file_name` present.
4. JSONL chunk writer:
   - Writer to emit one line per chunk with key fields (see schema below).
   - Keep existing JSON writer (`chunks.json`) for backward compatibility.

Acceptance Criteria:
- For a test document with headings, child chunks have non-null `parent_chunk_id` (≥ 95% where applicable).
- Metadata keys present on all chunks: `doc_id`, `page_start`, `page_end`, `heading`, `level`, `source_format`.
- `chunks.jsonl` generated and consumed by BM25 builder.

Feasibility: High.
Risks: Edge cases in heading detection; mitigated by fallback grouping and tests.

---

### C) Ingest Classification & Revision Heuristics (Lightweight) ✅

**Status: COMPLETED**

Goals:
- Attach `doc_type` and `revision` where possible without heavy LLM dependencies.

Tasks Completed:
1. Created dedicated `DocumentClassifier` module:
   - Enhanced rule-based classification with 16+ document type categories
   - Comprehensive revision extraction patterns (15+ patterns)
   - Weighted scoring system for classification accuracy
   - Support for metadata-based classification (title, subject, keywords)

2. Document type classification:
   - Achieved **100% classification** on pilot set (exceeded 80% target)
   - Categories include: P&ID, Technical Data, Manual, Drawing, Procedure, Report, MOC, RCA, Certificate, Calculation, Performance, Checklist, Schedule, Specification, List, Vendor

3. Revision extraction:
   - Successfully extracts revisions from filenames and content
   - Handles multiple formats: Rev.01, REV A, v1.0, _R1, .rev0E., etc.
   - Cleans and normalizes revision strings

4. Optional LLM integration:
   - Added `--use-llm-classifier` flag for future LLM enhancement
   - Placeholder for local model integration (llama2, mistral, etc.)
   - Falls back to rules when LLM unavailable

Test Results on Pilot Set:
- 003_3N4-S4274345... => Type: Performance, Rev: 01
- 092_3N4-S4279947... => Type: Manual, Rev: 1
- Data Sheet for CO2... => Type: Vendor, Rev: 0E
- 01. P&ID Ammonia... => Type: P&ID, Rev: 12

Feasibility: Proven - Rules achieved 100% coverage on pilot set.

---

### D) JSONL Manifests & Compatibility ✅

**Status: COMPLETED**

Goals:
- Introduce JSONL without breaking existing consumers.

Tasks Completed:
1. **JSONL Writers Implemented**:
   - ✅ `artifacts/chunks/chunks.jsonl` - Consolidated chunk output
   - ✅ `manifests/corpus.jsonl` - Document manifest with metadata
   - ✅ `manifests/checksums.jsonl` - File checksums for idempotency
   - Thread-safe append operations with locking
   - Atomic writes using temp file + rename pattern

2. **BM25 Builder Full Compatibility**:
   - ✅ `--chunks-jsonl` flag for JSONL input
   - ✅ Enhanced `load_chunks_from_jsonl()` with full schema support
   - ✅ Handles parent-child relationships
   - ✅ Converts page_start/page_end to page_nums
   - ✅ Preserves all metadata (doc_type, revision, etc.)

3. **Migration Strategy Implemented**:
   - ✅ Dual output: Both JSON and JSONL generated by default
   - ✅ `--emit-jsonl` flag (default: True)
   - ✅ Backward compatibility maintained
   - ✅ Created JSONL Migration Guide

4. **Schema Validation**:
   - All JSONL files pass schema validation
   - Chunks: 100% compliance (3707 chunks tested)
   - Corpus: 100% compliance (4 entries)
   - Checksums: 100% compliance (4 entries)

5. **Testing Results**:
   - ✅ BM25 builds successfully from JSONL: 3707 chunks indexed
   - ✅ BM25 builds successfully from JSON: 3707 chunks indexed
   - ✅ Search functionality verified: "CO2 compressor" returns correct results
   - ✅ Identical search results from both formats

Deliverables:
- `docs/JSONL_Migration_Guide.md` - Complete migration documentation
- Enhanced `tools/build_bm25_index.py` with full JSONL support
- Thread-safe JSONL writers in `tools/ingest.py`

Feasibility: Proven - All acceptance criteria met.
Risks: None - Full backward compatibility maintained.

---

## 6) JSONL Schemas (Proposed)

Chunk (one line per record):
```json
{
  "chunk_id": "DOC123_chunk_0001",
  "doc_id": "Technical Data/CO2_Compressor_rev0E",
  "parent_chunk_id": "DOC123_parent_0000",
  "text": "...",
  "page_start": 0,
  "page_end": 0,
  "heading": "1. INTRODUCTION",
  "level": 1,
  "metadata": {
    "doc_type": "Technical Data",
    "revision": "rev0E",
    "source_format": "vector",
    "file_name": "Data Sheet for CO2 Compressor Steam Turbine.rev0E.pdf"
  }
}
```

Corpus Manifest (one line per document):
```json
{
  "doc_id": "Technical Data/CO2_Compressor_rev0E",
  "file_path": "data/raw/phase1_pilot/Data Sheet for CO2 Compressor Steam Turbine.rev0E.pdf",
  "hash_sha256": "...",
  "pages": 8,
  "doc_type": "Technical Data",
  "revision": "rev0E",
  "source_format": "vector",
  "ingested_at": "2025-09-24T10:30:00Z"
}
```

Checksums (one line per file):
```json
{
  "file_path": "data/raw/phase1_pilot/...pdf",
  "hash_sha256": "...",
  "last_modified": 1695543000
}
```

---

## 7) Acceptance Criteria (Summary)

- CLI ingest runs multithreaded, produces Markdown, processed JSON, JSONL outputs, and manifests.
- OCR optional path works; if OCR not available, graceful degradation with logs.
- Hierarchical chunks have correct `parent_chunk_id` and enriched metadata.
- BM25 builds from JSONL and JSON.
- Tests cover parent-child relationships and metadata presence.

---

## 8) Validation & Tests

- Unit Tests:
  - `tests/test_chunk_hierarchy.py`: parent-child population correctness.
  - `tests/test_chunk_metadata.py`: required keys present.
  - `tests/test_jsonl_writer.py`: valid JSONL and round-trip.
- Integration:
  - Ingest 4 pilot PDFs; verify manifests, JSONL chunk count, OCR paths.
  - Build BM25 from JSONL; run sample queries.
- Performance:
  - Record wall-clock single-thread vs `--workers 4` on pilot set; ≥ 2× improvement.

---

## 9) Feasibility & Risks

- Feasibility: High overall; most building blocks exist.
- Risks & Mitigations:
  - Tesseract install: surface clear guidance, use `ocr_config.py` auto-detection; allow run without OCR.
  - Unstructured.io deps heavy: keep optional; detect and skip if not installed.
  - Windows file locking/rename: use atomic writes (temp file + rename); avoid cross-process conflicts.
  - Heading detection variance: fallback grouping; configurable thresholds; tests on pilot docs.

---

## 10) Timeline & Effort (Rough)

- A) Ingestion CLI + Threading + OCR flags: 1.0–1.5 days
- B) Parent-child population + sentence-window strategy: 1.0 day
- C) Metadata enrichment + doc_type/revision heuristics: 0.5–1.0 day
- D) JSONL writers + BM25 compatibility: 0.5 day
- E) Tests + Docs + Validation: 0.5–1.0 day

Total: 3.5–5.0 days (1–1.5 weeks elapsed with review/QA).

---

## 11) Rollout & Backward Compatibility

- Default scripts emit JSONL and JSON in parallel for one release.
- BM25 builder supports both; deprecate JSON after stabilization.
- No breaking changes to existing Phase 1 demos.

---

## 12) Implementation Pointers (File Map)

- `tools/ingest.py` — new CLI orchestrator.
- `app/ingestion/pdf_processor.py` — thread-safe directory processing (or keep in CLI), OCR flags.
- `app/rag/chunkers/hierarchical_chunker.py` — parent-child + sentence-window.
- `app/ingestion/text_chunker.py` — ensure metadata propagation; optional reuse for windowing.
- `tools/build_bm25_index.py` — read JSONL via `--chunks-jsonl`.
- `manifests/*.jsonl` — new outputs.

---

## 13) Appendices

### A. Configuration
- Default workers: `min(4, cpu_count())` (Windows safe).
- OCR confidence threshold: keep current default (e.g., 30.0) unless configured.
- Parser: default `auto` (PyMuPDF → OCR; unstructured only if explicitly chosen and installed).

### B. Logging & Observability
- Structured logs include per-document timing, OCR usage flag, and warnings for skipped scans.
- Optional per-ingest job JSONL log for progress (future alignment with UI ingest panel).

### C. Documentation Updates
- `docs/TECH_DESIGN_INGEST_AND_VISION.md` — note optional unstructured and Phase 1 OCR path.
- `docs/Developer_Handbook.md` — add JSONL usage and chunk metadata reference.
