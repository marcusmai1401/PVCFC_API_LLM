
## 0. Executive Summary

This design proposes:
- A one-click ingestion pipeline triggered from the UI to parse new documents (vector or scanned), run OCR as needed, normalize to structured Markdown, chunk hierarchically, and rebuild BM25/FAISS indices with zero-downtime reload.
- A “High Accuracy Mode” that optionally performs Vision-Assisted Verification by asking a multimodal LLM to re-read the original PDF page (or cropped region) for critical facts/citations, then adjusts the answer accordingly. This increases accuracy at the cost of higher latency and cost.

These features preserve the current text-only RAG path as the default, adding on-demand accuracy and operational controls for ingestion.


## 1. Background & Current State

- Current pipeline (runtime): text-only RAG
  - Transform query (normalize + intent + optional HyDE) — `app/rag/query_transform.py`
  - Hybrid retrieval (BM25 + FAISS) with RRF fusion + parent expansion — `app/rag/retriever.py`
  - Rerank via Cross-Encoder or score-based fallback — `app/rag/reranker.py`
  - Generation with inline citations `[Doc X]` — `app/rag/generator.py`
  - Optional CoVe verification (text re-retrieval) — `app/rag/cove.py`
  - Indices loaded from disk on startup — `app/deps/indices.py` → `artifacts/index/{bm25,faiss}`
- Current ingestion/indexing: offline via scripts/tools (e.g., `tools/demo_pipeline.py`, `tools/build_bm25_simple.py`, `tools/build_faiss_local.py`). Runtime does not re-open PDFs nor use vision models.

Gaps relative to the target:
- No UI-triggered ingestion (push-button ingest/OCR).
- No runtime “re-read PDF” or vision verification to maximize accuracy for critical answers.


## 2. Goals & Non-Goals

### 2.1 Goals
- One-click ingest from UI to:
  - Accept new documents (PDF vector or scanned) and run parsing + OCR.
  - Normalize to Markdown, hierarchical chunking, indexing (BM25 + FAISS).
  - Atomic index update with zero/minimal downtime; app index reload.
  - Progress visibility (job status, logs, metrics) in UI.
- Vision-Assisted Verification (High Accuracy Mode):
  - After retrieval/rerank/generation, for low-confidence or critical claims, re-open source page(s) and send page image (or crop) to a multimodal LLM (e.g., Gemini 2.5 Pro) to confirm values.
  - Merge adjustments/caveats into final answer; expose verification metadata.

### 2.2 Non-Goals (Phase 1)
- Full-fledged distributed job system or multi-tenant ACLs.
- Perfect OCR for every layout; aim for robust defaults with PyMuPDF + pytesseract, optional hooks for unstructured.io.
- End-to-end PDF redaction or security watermarking.


## 3. Architecture Overview

### 3.1 Components
- API (FastAPI): new endpoints to manage ingestion jobs and trigger index reloads.
- Ingest Worker (background within API process, then externalizable): runs pipelines (parse → OCR → normalize → chunk → index → write artifacts → reload indices).
- Artifact Store: `artifacts/` with subfolders for docs, pages (images), and index snapshots.
- Streamlit UI: “Data Management” page gains a “Ingest new data” button, job list, logs.
- Vision Verification: invocation path in the `/ask` pipeline (post-generation) guarded by config flags and heuristics.

### 3.2 Data Flow (High Level)
1) UI upload or reference documents → POST /ingest/start → returns job_id
2) Worker processes docs → creates Markdown + chunks → rebuilds BM25/FAISS → write to temp snapshot → atomically swap to `artifacts/index/current` → call index reload → job completes
3) At query time (optional High Accuracy): if triggered, fetch page images for cited doc_id/page → send to vision LLM with grounded instruction → adjust answer → return with verification meta


## 4. Item (2) — One-Click Ingest/OCR

### 4.1 Functional Requirements
- Trigger ingestion from UI with a single action.
- Support inputs:
  - File upload (PDF, images) or server-side folder path.
  - Optional metadata (doc_category, doc_id hints, tags).
- Pipeline steps:
  1. Validate inputs
  2. Detect doc type (vector vs scanned)
  3. Parse content:
     - Vector: PyMuPDF (pymupdf) text extraction; consider tables.
     - Scanned: OCR via pytesseract (configurable langs).
  4. Normalize to structured Markdown (headers, lists, tables where feasible)
  5. Hierarchical chunking (by headings, windowing around sentences)
  6. Build/Update indices: BM25, FAISS (compute embeddings)
  7. Write artifacts snapshot
  8. Atomic swap current index symlink/folder
  9. Request app to reload indices (no restart)
- Observability: job status, progress %, logs, metrics.
- Safety: process isolation from runtime (no downtime), idempotent jobs, retry on transient errors.

### 4.2 API Design

- POST /ingest/start
  - Body:
    ```json
    {
      "source": {
        "mode": "upload" | "folder",
        "paths": ["/absolute/or/relative/path1.pdf", "path2.pdf"],
        "collection": "optional-collection-name"
      },
      "options": {
        "ocr": "auto" | "force" | "off",
        "language": "vi|en|mul",
        "chunking": { "max_tokens": 500, "hierarchical": true },
        "embedding": { "provider": "openai|local|gemini", "model": "..." },
        "index": { "bm25": true, "faiss": true }
      },
      "metadata": {
        "doc_category": "datasheet|pid|om|...",
        "tags": ["KT06101", "04000"]
      }
    }
    ```
  - Response:
    ```json
    { "job_id": "ing-20250916-abc123", "status": "queued" }
    ```

- GET /ingest/status/{job_id}
  - Response:
    ```json
    {
      "job_id": "ing-20250916-abc123",
      "state": "queued|running|success|failed|canceled",
      "progress": { "percent": 65, "stage": "chunking" },
      "metrics": { "pages": 124, "chunks": 580, "time_sec": 92 },
      "logs_tail": ["... last 20 lines ..."],
      "error": null
    }
    ```

- POST /ingest/cancel/{job_id}
  - Soft-cancel if supported by worker.

- POST /indices/reload (internal/admin)
  - Forces `IndexManager.reload_indices()`.

Security (Phase 1): optional simple token header for ingest and reload endpoints.

### 4.3 Ingestion Worker Design

- Execution model: start as an in-process background task using `asyncio.to_thread` or `BackgroundTasks`. Later phases can move to RQ/Celery.
- Job store: JSONL in `artifacts/state/ingest_jobs.jsonl` with rolling log per job in `artifacts/logs/ingest/{job_id}.log`.
- Snapshot layout:
  - `artifacts/snapshots/{timestamp}/index/{bm25,faiss}` — output of builders.
  - `artifacts/snapshots/{timestamp}/docs/` — normalized Markdown & chunk JSONL.
  - `artifacts/index/current -> artifacts/snapshots/{timestamp}/index` (symlink or folder swap on Windows: copy+rename).
  - `artifacts/index/metadata.json` — aggregated statistics.
- Atomicity on Windows:
  - Build in temp folder, then replace `artifacts\index\bm25` and `artifacts\index\faiss` via move/rename semantics (ensure no readers while swapping by reloader barrier).
- Reload protocol:
  - After swap, call `IndexManager.reload_indices()`; on success, mark job success; on failure, roll back to prior snapshot.

### 4.4 Pipeline Details

1) Detection:
   - Use PyMuPDF to check if page has extractable text; fallback to OCR if text blocks < threshold.
2) Parsing & OCR:
   - PyMuPDF (vector) for text blocks; `pytesseract` for scanned pages (with language models vi/eng as configured).
   - Consider `pdfplumber` for table hints (optional).
3) Normalization:
   - To Markdown: preserve hierarchy (H1..H4), lists, simple tables.
   - Keep per-page metadata: doc_id, page number; optionally bounding boxes for headings/paragraphs when available.
4) Chunking:
   - Hierarchical by headings; include context window around matches; target ~300–500 tokens per chunk.
   - Store `chunk_id`, `parent_id`, `doc_id`, `page`, `text`, `heading`, `level`.
5) Embeddings:
   - Batch with `EmbeddingService` (OpenAI or local sentence-transformers). Persist to disk for FAISS.
6) Indices:
   - BM25: use `BM25Indexer.build_index()` from chunks; save pkls/jsons.
   - FAISS: `VectorIndexer.build()` then `save()`.
7) Metadata:
   - Aggregate: counts, avg chunk length, languages, categories; write `artifacts/index/metadata.json`.
8) Swap & Reload:
   - Write to snapshot, then atomic swap; call reload endpoint internally; emit metrics.

### 4.5 Progress & Metrics

- Stages: validate → detect → parse/ocr → normalize → chunk → embed → build_bm25 → build_faiss → snapshot → swap → reload → done
- Prometheus (extend existing):
  - `rag_ingest_jobs_total{status}`
  - `rag_ingest_duration_seconds` (histogram)
  - `rag_ingest_pages_total`, `rag_ingest_chunks_total`
  - Errors by stage: `rag_ingest_errors_total{stage}`
- Logs: per-job structured logs in JSONL; UI tails last N lines.

### 4.6 Streamlit UI Additions (Phase 1)

- New tab: Data Management → Ingest
  - File uploader (multi) or path input
  - Options (OCR mode, language, chunk size)
  - Button “Start Ingest” → calls POST /ingest/start
  - Job list with status polling; view logs; retry/rollback controls (basic)

### 4.7 Error Handling & Recovery

- On stage failure: mark job failed with error; do not swap indices; preserve logs & partial outputs under snapshot for inspection.
- Retry policy: allow user-triggered retry; cache intermediate artifacts where possible.
- Rollback: keep N snapshots; allow switching `current` back to last-known-good.

### 4.8 Security & Access Control (Phase 1)

- Simple API token header for ingest operations.
- Rate-limit /ingest endpoints separately (lower RPS).
- Validate allowed folders to prevent path traversal.

### 4.9 Testing Strategy

- Unit: parsers, OCR adapter (mock), chunker, builders.
- Integration: end-to-end ingest on sample PDFs (vector + scanned), assert index stats.
- API tests: start/status lifecycle, reload behavior (mock IndexManager).


## 5. Item (3) — Vision-Assisted Verification (High Accuracy Mode)

### 5.1 Current Operation (Text-Only)

- Retrieval and generation rely solely on pre-extracted text (JSON/Pickle/FAISS). At runtime, PDFs are not reopened; no images are sent to LLM. Citations map back to doc_id/page via metadata.

### 5.2 High Accuracy Mode: Target Behavior

- When enabled, after the normal RAG generation (and optional CoVe), the system applies a “vision verification” step for selected claims/citations:
  - For each critical claim (numbers/specs) or low-confidence answer, fetch the cited page image (or crop by bbox) and ask a multimodal LLM (e.g., Gemini 2.5 Pro) to confirm the value/statement.
  - If discrepancies are found, adjust the answer (replace numbers, add caveats) and record verification metadata.

### 5.3 Trigger Conditions

- Configurable modes per request:
  - `verification_mode`: `"never" | "auto" | "always"`
  - `high_accuracy`: boolean shortcut (maps to `auto`)
- Auto triggers when any of the following:
  - `confidence < threshold` (e.g., 0.75)
  - Claims contain numbers/units (detected by CoVe extractors) and sources include scanned P&IDs/tables
  - User explicitly requests high-accuracy mode

### 5.4 Required Artifacts & Preprocessing

- Page Images Store (created during ingest):
  - `artifacts/pages/{doc_id}/{page}.png` at sufficient DPI (e.g., 200–300 DPI)
  - Optionally precompute `thumb_{page}.jpg` for UI
- Citation-to-Region map (optional, Phase 2):
  - If chunking preserves approximate bbox, store `[x0, y0, x1, y1]` for finer crops
  - If not available, fallback to whole-page verification or heuristic text localization via PyMuPDF search

### 5.5 API Changes

- Extend /ask request schema (backward-compatible):
  ```json
  {
    "high_accuracy": true,
    "verification_mode": "auto",
    "verification": {
      "max_pages": 2,
      "max_claims": 3,
      "provider": "gemini",
      "model": "gemini-2.5-pro",
      "image_crop": "auto|full|bbox",
      "dpi": 300
    }
  }
  ```
- Response metadata additions:
  ```json
  {
    "meta": {
      "vision_verification": {
        "enabled": true,
        "claims_checked": 3,
        "claims_verified": 2,
        "verification_rate": 0.67,
        "adjusted": true,
        "latency_ms": 1800,
        "provider": "gemini",
        "model": "gemini-2.5-pro"
      }
    },
    "warnings": ["Một số thông tin đã được hiệu chỉnh sau khi xác minh từ ảnh trang PDF."]
  }
  ```

### 5.6 Vision Verification Flow

1) Candidate selection:
   - Use CoVe to extract claims, rank by importance (numbers/specs prioritized)
   - Map claims → citations (doc_id, page), pick up to `verification.max_pages` unique pages
2) Page retrieval:
   - Load `artifacts/pages/{doc_id}/{page}.png` (render in ingest; if missing, render on-the-fly via PyMuPDF)
   - Crop region if bbox available; else full page
3) LLM multimodal prompt:
   - Provide: user query, generated answer segment, text snippet context, and page image as input parts
   - Instruction: “Extract/verify exact values and wording from the image; if discrepancy vs text context, output corrected value and snippet coordinates if possible.”
4) Consolidation:
   - Merge corrections into answer; annotate with citations (page/region)
   - Update `vision_verification` meta; add warnings when low verification rate
5) Caching:
   - Cache page images and prior verification outputs by `(doc_id,page,claim_hash)` to control cost/latency

### 5.7 LLM Client Extension (Multimodal)

- Extend `LLMService` / `llm_client` to accept image parts:
  - Gemini (google-genai): use `types.Part.from_bytes` with `mime_type="image/png"` for page image parts in `GenerateContent`.
  - Keep current text generate path; add `generate_multimodal(prompt_text, images=[...])` helper.
- Safety & limits:
  - Page images can be large; resize to reasonable dimensions; consider JPEG for speed if quality acceptable.

### 5.8 Performance & Cost Considerations

- Latency: +1.0–3.0s per page verification typical (network + model)
- Cost: proportional to image size and steps; mitigate via:
  - Auto trigger only for low confidence & numerical claims
  - Cap pages/claims; enable caching; user toggle
  - Batch verification when multiple claims map to same page

### 5.9 Observability

- Metrics (Prometheus):
  - `rag_vision_verification_requests_total{status}`
  - `rag_vision_verification_latency_seconds`
  - `rag_vision_verification_rate` (gauge)
- Logs: include `verification_decisions`, pages checked, corrections applied, deltas
- Tracing: spans `vision_page_fetch`, `vision_llm_call`, `vision_merge`

### 5.10 Failure Modes & Fallbacks

- Vision model errors/timeouts: skip with warning; return text-only result
- Missing page images: on-the-fly render; if rendering fails, skip
- Bbox invalid: use full page

### 5.11 Testing Strategy

- Unit: page rendering, cropper, prompt builder, merger logic
- Integration: sample PDFs with known numbers; assert corrections
- A/B evaluation: compare accuracy/latency with/without high accuracy mode on a golden set


## 6. Rollout Plan

- Phase A (Ingest minimal):
  - Add ingest endpoints; implement vector parsing + OCR fallback; BM25/FAISS snapshot + reload
  - Streamlit button + job status; basic metrics
- Phase B (Vision MVP):
  - Pre-render pages during ingest; add multimodal call for `verification_mode=always` (behind feature flag)
  - Logging/metrics; caching
- Phase C (Auto-mode & Heuristics):
  - Confidence-based triggers; claim selection optimization; page dedup, batching
- Phase D (Hardening):
  - External worker (RQ/Celery), retries, rollbacks, access control; bbox mapping improvements; UI polish


## 7. Risks & Mitigations

- OCR accuracy on poor scans → allow per-document language hints; QA sampling; consider unstructured.io for complex layouts
- Atomic swap on Windows file locks → perform swap with short app pause window via reloader barrier; retry
- Vision model quota/cost → strict caps, caching, `auto` default conservative
- Security for ingest endpoints → token auth; restrict allowed paths; rate-limit


## 8. Open Questions

- Do we standardize on Gemini for multimodal or support OpenAI GPT-4o too? (client abstraction needed)
- How much bbox fidelity is needed for tables/P&ID? (Phase B can start full-page)
- Storage budget for page images per collection? (DPI tradeoff)


## 9. References (Code Pointers)

- Startup & indices: `app/main.py`, `app/deps/indices.py`
- RAG modules: `app/rag/query_transform.py`, `app/rag/retriever.py`, `app/rag/reranker.py`, `app/rag/generator.py`, `app/rag/cove.py`
- Indexers: `app/rag/indexers/bm25_indexer.py`, `app/rag/indexers/faiss_indexer.py`
- LLM services: `app/services/llm.py`, `app/services/llm_client.py`
- Metrics & tracing: `app/core/metrics.py`, `app/core/tracing.py`, `app/core/logging.py`, `app/core/rate_limit.py`
- Tools (ingest prototypes): `tools/build_bm25_simple.py`, `tools/build_faiss_local.py`, `tools/demo_pipeline.py`


## 10. Acceptance Criteria (Phase A & B)

- Phase A (Ingest):
  - [ ] POST /ingest/start returns job_id; status lifecycle observable
  - [ ] New docs processed end-to-end; indices swapped atomically; /index-stats reflects changes
  - [ ] Streamlit “Ingest” button operates the flow; logs/metrics visible
- Phase B (Vision):
  - [ ] High Accuracy Mode (`verification_mode=always`) verifies at least 1 cited page and adjusts answer if discrepancy
  - [ ] Response includes `vision_verification` meta and warnings when applicable
  - [ ] Vision errors fall back gracefully to text-only with warning
