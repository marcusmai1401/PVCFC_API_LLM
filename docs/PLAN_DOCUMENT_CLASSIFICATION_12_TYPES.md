# Task 1 – Document Classification into 12 Types (Gemini 2.5 Flash)

## 1. Problem Statement

We need an offline document classification system that assigns **each PDF** in `D:\Data_Raw` (currently 77 files, all already ingested and indexed) to **exactly one** of the following 12 categories:

1. P&ID
2. Management of Change
3. Root Cause Analysis
4. Technical Data
5. Maintenance history
6. Material partlist
7. Datasheet
8. Operation Instruction
9. Maintenance Instruction
10. Other technical document
11. Inventory
12. Pictures

Constraints / goals:
- Use **Gemini 2.5 Flash** (LLM light tier) for classification, potentially combined with lightweight rules.
- **Do not change** the existing RAG `/ask` pipeline; this is a **separate module**, but it can reuse ingestion/index artefacts.
- Persist classification results as metadata so they can be used later for filtering/boosting and equipment metadata work.

---

## 2. Current State

### 2.1 Ingestion & Artefacts

Relevant components:
- `tools/ingest.py`
  - Processes PDFs from `source_dir` (e.g. `D:\Data_Raw`) into:
    - `artifacts/ingestion_production/chunks/*.json` & `chunks.jsonl` – chunk text + metadata.
    - `artifacts/ingestion_production/manifests/corpus.jsonl` – one line per document with `doc_id`, `file_path`, `doc_type`, `revision`, `source_format`, etc.
    - `artifacts/ingestion_production/doc_id_map.json` – mapping `doc_id -> pdf_path`.
  - `_classify_document(...)` now uses **`CADLikeGate`** for binary classification:
    - `doc_type ∈ {"CAD-like", "non-CAD-like"}`
    - `revision` extracted from filename (e.g. `Rev A`, `R01`).
  - `_create_chunks(...)` attaches document-level metadata (including `doc_type`, `revision`) to each chunk.

- `app/ingestion/text_chunker.py`
  - Further attaches/derives metadata per chunk, including **heuristic `doc_type`** based on filename and hints (e.g. `instrument_list`, `manual`, `pid`).

- `app/rag/indexers/opensearch_bm25_retriever.py`
  - When reading from OpenSearch, it expects fields like `doc_type`, `tags`, `tags_raw` in `_source` for scoring/metadata.

- `tools/extract_metadata.py`
  - Provides `extract_metadata_from_path(...)` which can infer:
    - `equipment_type`, `doc_type`, `equipment_id`, `vendor`, `lang` from file paths like `D:\Data_Raw\K06101_CO2 COMPRESSOR_HITACHI\...`.

### 2.2 Existing Classification Logic (Rule-based + LLM)

There is an earlier, more general classification layer that is currently **not in the main ingestion path**, but is relevant:

- `app/ingestion/document_classifier.py`
  - `DocumentClassifier` with rich **rule-based** taxonomy (`ClassificationRules.TYPE_PATTERNS`):
    - Types like `"P&ID"`, `"Technical Data"`, `"Manual"`, `"Drawing"`, `"Procedure"`, `"Report"`, `"MOC"`, `"RCA"`, `"Certificate"`, `"Calculation"`, `"Performance"`, `"Checklist"`, `"Schedule"`, `"Specification"`, `"List"`, `"Vendor"`.
  - `classify(...)` uses filename, path components, parent directories, metadata (`title`, `keywords`), and first-page text to score each doc_type.
  - `classify_with_llm(...)` (if wired) calls LLM to refine classification when the rule-based result is `"unknown"`.

- `app/services/document_classification_llm.py`
  - `DocumentClassificationLLM` uses **`LLMService`** to call the LLM with a structured prompt:
    - Expects JSON response with `{ doc_type, confidence, revision, reasoning }`.
    - `DOCUMENT_TYPES` list matches the older taxonomy (P&ID, Technical Data, Manual, etc.).
  - Currently configured to use LLM **tier = "light"**, which maps to **Gemini 2.5 Flash** under the default environment.

- `docs/IMPLEMENTATION_SUMMARY.md` – section *“Simplified Document Classification”*
  - Historical note: ingestion used to call `DocumentClassifier` (with LLM fallback) but was simplified to binary CAD-like vs non-CAD-like for performance reasons.

### 2.3 How `doc_type` is Used Today

- Ingestion manifests (`corpus.jsonl`) store `doc_type` as `"CAD-like"` / `"non-CAD-like"`.
- Chunks metadata may contain additional `doc_type` hints (e.g. `"manual"`, `"pid"`) via heuristics.
- OpenSearch index (`rag_chunks`) stores `doc_type` and uses it for:
  - Diagnostics and possible boosting (e.g. PID vs technical doc retrieval).
- Request schema `AskRequest.filters` allows filtering by `doc_category` / `doc_id`, but there is **no dedicated 12-class taxonomy** integrated yet.

Summary: We already have **artefacts, indexes, and a partially built classification layer**, but:
- The **active ingestion classification** is **binary (CAD-like vs non-CAD-like)**.
- The **rich taxonomy and LLM classifier** exist but are **not wired** to current ingestion or a dedicated batch.
- There is **no single, coherent 12-class taxonomy** matching your new requirement.

---

## 3. Target Scope & Requirements (Task 1)

**Goal:** Build a **standalone classification module** that:

- Classifies each **document-level PDF** into **one** of the 12 target categories.
- Uses **Gemini 2.5 Flash (light tier)** as the primary semantic classifier, optionally combined with:
  - Path-based and rule-based hints (to reduce cost and increase stability).
- Runs as a **batch process** over ~77 existing PDFs in `D:\Data_Raw` using artefacts in `artifacts/ingestion_production`.
- Persists results to:
  1. A dedicated **classification manifest** (e.g. `artifacts/classification/document_types_12.jsonl`).
  2. Optionally, enrich **OpenSearch/Weaviate indices** with the new 12-class `doc_type_12` field for downstream retrieval.

**Out of scope (for this task):**
- Changing `/ask` behavior or query-time routing.
- Rewriting ingestion/classification logic for P&ID CAD-like gate.
- Full UI integration (can be added later).

---

## 4. Design Overview

### 4.1 Taxonomy & Mapping

Define a **canonical 12-class taxonomy**:

```text
P_ID
MANAGEMENT_OF_CHANGE
ROOT_CAUSE_ANALYSIS
TECHNICAL_DATA
MAINTENANCE_HISTORY
MATERIAL_PARTLIST
DATASHEET
OPERATION_INSTRUCTION
MAINTENANCE_INSTRUCTION
OTHER_TECHNICAL_DOCUMENT
INVENTORY
PICTURES
```

- Use these as **internal codes** (`doc_type_12`), mapped to user-friendly labels.
- Add optional **mapping from existing types** (old taxonomy or heuristics) to the new ones, for rule-based pre-hints:
  - e.g. `"P&ID"` → `P_ID`; `"Manual"` → `OPERATION_INSTRUCTION` or `MAINTENANCE_INSTRUCTION` depending on path; `"List"` → `INVENTORY` or `MATERIAL_PARTLIST`.

### 4.2 Architecture Components

1. **Classifier Core (`app/classification/document_type_12.py` – new module)**
   - Responsible for:
     - Defining the 12-class taxonomy and mapping helpers.
     - Generating prompts for Gemini 2.5 Flash.
     - Combining rule-based hints + LLM output.
   - Input: `filename`, `relative_path`, optional `first_page_text`, optional `old_doc_type`, optional path metadata (equipment/vendor info from `extract_metadata_from_path`).
   - Output: `DocumentType12Result`:
     - `doc_id: str`
     - `doc_type_12: str` (one of 12 codes)
     - `confidence: float`
     - `method: str` (`"rule_only" | "llm_only" | "rule_llm"`)
     - `raw_llm_doc_type: str` (verbatim from model, before mapping)
     - `reasoning: Optional[str]` (for logs only)

2. **LLM Adapter (reuse `DocumentClassificationLLM` or create a thin wrapper)**
   - Either:
     - Option A: Reuse `app/services/document_classification_llm.py` but adjust `DOCUMENT_TYPES` and prompt for 12 classes.
     - Option B: Create a dedicated `DocumentType12LLM` wrapper under `app/services/` so we don’t break old behavior.
   - Must always call **`LLMService.complete(..., tier="light")`** so that Gemini 2.5 Flash is used according to env.

3. **Batch Runner (`tools/classify_documents_12types.py` – new script)**
   - Reads existing artefacts:
     - `artifacts/ingestion_production/doc_id_map.json` → mapping doc_id to pdf_path.
     - Optionally `artifacts/ingestion_production/manifests/corpus.jsonl` to get `doc_type` (CAD-like vs non-CAD-like), `revision`, `source_format`.
     - Optionally markdown/processed JSON for first-page content.
   - For each document:
     - Builds classification input (path, name, optional text snippet).
     - Applies rule-based pre-class (from path + `extract_metadata_from_path`).
     - Calls Gemini 2.5 Flash classification if needed.
     - Emits a `DocumentType12Result` record.
   - Writes output to:
     - `artifacts/classification/document_types_12.jsonl` (1 JSON per line).
     - Optional per-doc summary file for debugging.

4. **Index & Metadata Integration (optional but recommended)**
   - A small utility script `tools/apply_doc_type_12_to_index.py` can:
     - Read `document_types_12.jsonl`.
     - For each `doc_id`, update:
       - OpenSearch `rag_chunks` documents with a new field `doc_type_12` (keyword).
       - Optionally add `doc_type_12` to Weaviate `Chunk` objects as a new property.
   - This keeps classification **decoupled** from ingestion; can be rerun or rolled back independently.

5. **Config & Feature Flags**

Add minimal config options via env + `Settings` (in `app/core/config.py`):
- `DOC_CLASSIFICATION_12_ENABLED=true|false` – global enable/disable.
- `DOC_CLASSIFICATION_12_MODE=off|fallback|always` – when integrating into ingestion later.
- `DOC_CLASSIFICATION_12_CONFIDENCE_THRESHOLD=0.6` – below this we either:
  - Assign `OTHER_TECHNICAL_DOCUMENT` or
  - Mark as `unknown` and handle separately.

For **Task 1 (current 77 PDFs)** the batch script can bypass env flags and run explicitly when invoked.

---

## 5. Detailed Implementation Steps

> **Note:** This section is an execution plan. **Do not implement until explicitly approved.**

### 5.1 Define Taxonomy & Data Structures

1. **Add new module:** `app/classification/document_type_12.py` (name can be adjusted later) with:
   - Enum or constant list of the 12 codes.
   - Mapping helper: `map_llm_label_to_code(raw_label: str) -> str`.
   - `DocumentType12Result` dataclass/Pydantic model.

2. **Design mapping rules:** from existing hints (`old_doc_type`, path metadata) to the new 12 classes.
   - Use `tools/extract_metadata.py.extract_doc_type` & `extract_equipment_type` as hints.
   - Cover obvious cases (P&ID, MoC, RCA, etc.) with rules.

3. **Document the taxonomy** in the plan and optionally in a short README under `docs/` or `DOCUMENTS_CHATBOX/docs`.

### 5.2 LLM Prompt & Adapter

1. Decide whether to **reuse** `DocumentClassificationLLM`:
   - Option A (less intrusive): create a **new LLM adapter** `DocumentType12LLM` in `app/services/document_type_12_llm.py` that:
     - Uses `LLMService` with `tier="light"`.
     - Has its own prompt and `DOCUMENT_TYPES_12` list.
   - This avoids touching existing classification logic that might still be referenced by legacy scripts.

2. Design the prompt (English, but robust to Vietnamese text in metadata):
   - Enumerate the 12 categories clearly with short definitions.
   - Provide `Filename`, `Path`, `First page content (truncated)`, optional doc/path metadata.
   - Ask for **JSON-only** response:

     ```json
     {
       "doc_type": "one_of_12_labels_or_unknown",
       "confidence": 0.0-1.0,
       "reasoning": "brief explanation"
     }
     ```

3. Implement `parse_llm_response` similar to `DocumentClassificationLLM.parse_llm_response`, but mapping to 12 codes.

4. Implement `classify(...)` API:
   - Inputs: `filename`, `path`, optional `text_snippet`, optional rule-based_hint.
   - Outputs: `DocumentType12Result`.
   - Behavior:
     - If rule-based hint is **high-confidence** (e.g. strong path pattern), skip LLM.
     - Else, call LLM and apply `confidence_threshold`.

### 5.3 Batch Runner for Existing 77 PDFs

Create `tools/classify_documents_12types.py` with roughly these steps:

1. **Load doc list**:
   - Read `artifacts/ingestion_production/doc_id_map.json` (or `artifacts/ingestion/doc_id_map.json` in legacy setups).
   - Each entry gives `doc_id` and `pdf_path`.

2. **For each document**:
   - Read **path-based metadata**:
     - Use `extract_metadata_from_path(pdf_path)` to get `equipment_type`, `doc_type` (old), `equipment_id`, `vendor`, `lang`.
   - Optionally read **processed content**:
     - Prefer `artifacts/ingestion_production/markdown/{doc_id}.md`.
     - If missing, use the first page from `documents/{doc_id}_processed.json` or a page-specific artefact.
   - Build a `ClassificationInput` object.

3. **Apply rule-based pre-classification** (cheap):
   - Use patterns on path + old `doc_type`/`equipment_type` to assign a preliminary label.
   - If clear (e.g. path contains `MOC`, `Root Cause`, `P&ID`, `Inventory`), mark as **rule_confident**.

4. **Call Gemini Flash where needed**:
   - For documents without a high-confidence rule-based label, call the `DocumentType12LLM` classifier.
   - Apply `DOC_CLASSIFICATION_12_CONFIDENCE_THRESHOLD`; if LLM is low-confidence (e.g. < 0.6), set `doc_type_12 = "UNKNOWN"` and rely on **manual fix in the UI** later (do **not** auto-map to `OTHER_TECHNICAL_DOCUMENT`).

5. **Write results**:
   - Output one JSON per line to `artifacts/classification/document_types_12.jsonl`, e.g.:

     ```json
     {
       "doc_id": "DOCID_...",
       "pdf_path": "D:\\Data_Raw\\...pdf",
       "doc_type_12": "DATASHEET",
       "confidence": 0.82,
       "method": "rule_llm",
       "raw_llm_doc_type": "Datasheet",
       "timestamp": "2025-11-xxT..",
       "reasoning": "..."
     }
     ```

6. **(Optional) Write a summary report**:
   - Count of documents per `doc_type_12`.
   - List of low-confidence classifications for manual review.

### 5.4 Index Integration (Future / Optional)

> **Current requirement:** For Task 1, **do not update OpenSearch/Weaviate indices** – only write the `document_types_12.jsonl` manifest and use it for analysis/metadata equipment work. The steps below are kept as a future extension and are **out of scope** for the initial implementation.

Potential future script `tools/apply_doc_type_12_to_index.py` could:

1. Load `document_types_12.jsonl` into a mapping `doc_id -> doc_type_12`.
2. For **OpenSearch `rag_chunks`**:
   - For each `doc_id`, send an update-by-query to set `doc_type_12` field on all chunks with that `doc_id`.
   - Ensure mapping is updated to add `doc_type_12` as `keyword`.
3. For **Weaviate `Chunk` collection** (if needed):
   - Alter schema to add a `doc_type_12` property (`TEXT` or `TEXT_ARRAY`).
   - Batch update objects by `doc_id`.
4. This script should be idempotent and safe to rerun.

### 5.5 Configuration & Safety

1. Add basic env flags (if/when we wire into ingestion or other pipelines):
   - `DOC_CLASSIFICATION_12_ENABLED`
   - `DOC_CLASSIFICATION_12_CONFIDENCE_THRESHOLD`
   - `DOC_CLASSIFICATION_12_MODE`
2. For Task 1 (77 PDFs), the batch script can be run manually without changing ingestion.
3. Add logging and metrics:
   - How many docs classified per label.
   - Average LLM confidence.
   - Number of calls to Gemini (for cost awareness).

### 5.6 Testing Plan

1. **Unit tests**:
   - Taxonomy mapping functions: ensure all LLM labels/map variants are mapped to one of 12 codes or `unknown`.
   - LLM response parser: robust to extra text, malformed JSON.
   - Rule-based hints: path-derived doc_type mapping to 12 labels.

2. **Integration tests** (small set of curated PDFs):
   - Create a test dataset with one sample per target class (using synthetic or already-known PDFs).
   - Run `classify_documents_12types.py` in a controlled environment (possibly mocking Gemini responses for determinism).

3. **Manual validation**:
   - For the 77 PDFs, inspect `document_types_12.jsonl` and generate a small table (doc_id, filename, classification, confidence) for SME review.

4. **No-op guarantee**:
   - Ensure that, until explicitly invoked, this module does **not** modify existing indices or ingestion behavior.

---

## 4.3 UI Design – Device-centric Classification Tab

### Goals

Provide a **Streamlit UI tab** where a user can:
- Select one of the current devices (initially only 2: `KT06101_TURBINE_HTC`, `K06101_CO2 COMPRESSOR_HITACHI`).
- See the device's **metadata** rendered on screen.
- See a **"folder tree" view** of classification results for that device:
  - Up to 12 folders, corresponding to the 12 document types.
  - Any folder with **no documents** is **hidden** (only non-empty folders are shown).
- Click a folder to see the list of documents assigned to that category.
- (Future) Provide a way for users to submit **feedback / corrections** when LLM classification is wrong, without implementing the persistence logic yet.

### Proposed UX Flow

1. **New Tab in Streamlit UI**
   - Add a new tab in the existing Streamlit app (e.g. "Device Library" or "Document Classification").
   - This tab will focus on **device-centric browsing** of classified documents.

2. **Device Selector**
   - At the top of the tab, show a `selectbox` for `equipment_key`:
     - `KT06101_TURBINE_HTC`
     - `K06101_CO2 COMPRESSOR_HITACHI`
   - Behind the scenes, this maps to `equipment_id` (e.g. `KT06101`, `K06101`).

3. **Device Metadata Panel**
   - After selecting a device, UI loads device metadata from a future metadata source (planned in equipment-metadata work):
     - Likely a JSON file such as `artifacts/equipment/{equipment_id}.json` or an index `equipment_metadata`.
   - Display key fields in a panel/card:
     - Name, equipment_type, vendor, main_doc_ids, priority_doc_types, etc.
   - This is **read-only** in Task 1; editing metadata is out of scope.

4. **Classification Tree / Folder View**
   - Use classification results from `artifacts/classification/document_types_12.jsonl` and any future equipment-document mapping to build a structure:

     ```text
     <Device>
       ├── P&ID (N docs)
       ├── Management of Change (M docs)
       ├── Root Cause Analysis (K docs)
       ├── ...
     ```

   - Only show folders where `count > 0` for the selected device.
   - Implementation in Streamlit can be:
     - A set of **expanders**, one per category (12 max).
     - Each expander title shows `Category Name (count)`.

5. **Document List per Folder**
   - Inside each folder/expander, show a table of documents of that type that are relevant to the selected device:
     - Columns: `filename`, `doc_id`, `confidence`, maybe `source_path`.
     - Possibly an action button/link: "Open" (e.g. view in PDF viewer or call existing PDF render endpoint).
   - This view uses:
     - `doc_type_12` from classification manifest.
     - future mapping `equipment_id → [doc_id]` from equipment-metadata stage.

6. **Feedback / Manual Correction (Design Only, Not Implemented Yet)**
   - UI elements (planned, not implemented in Task 1):
     - For each row/document, optionally show:
       - A button `"Mark as wrong"`.
       - A dropdown `"Correct category"` with 12 options.
     - This would allow the user to propose a corrected `doc_type_12`.
   - Persistence / logic (not implemented now, just planned):
     - Store corrections in a separate structure (e.g. `artifacts/classification/overrides.jsonl`), which can later be applied on top of auto classification.
     - Optionally track `user_id`, timestamp, and original vs corrected label.
   - For this plan, we **only document** the UI and data shape for feedback; actual write-back logic is deferred.

7. **Component Placement in Codebase (High-level)**
   - Likely add a new component under `streamlit_app/components/` (e.g. `classification_browser.py` or extend `data_management.py`).
   - The new tab is wired from the main `streamlit_app/app.py` or the central tab/router component.
   - The component will read JSONL manifests from `artifacts/classification/` and equipment metadata from `artifacts/equipment/` (once available).

---

## 6. Owner Decisions (Resolved)

Based on your answers, the plan is updated with these decisions:

1. **Fallback policy for low-confidence LLM results**
   - If `confidence < threshold` (e.g. 0.6), classify as `UNKNOWN` (or equivalent internal code) and **do not** automatically map to `OTHER_TECHNICAL_DOCUMENT`.
   - These `UNKNOWN` cases will be surfaced in the UI for **manual fix** (planned feedback/correction flow), not auto-resolved.

2. **Index update**
   - For Task 1, we **only** produce the manifest `artifacts/classification/document_types_12.jsonl`.
   - We **do not update** OpenSearch/Weaviate indices with `doc_type_12` yet. Index integration remains a **future optional step**.

3. **Tolerance for manual correction**
   - Target: roughly **≤ 5%** of documents may require manual label correction; the classifier should aim for ≥95% acceptable auto-labels.
   - This justifies keeping explicit `UNKNOWN` and designing the UI flow for SME review/fix.

4. **Internal code naming**
   - You are **OK** with the uppercase underscore codes such as `P_ID`, `DATASHEET`, `OTHER_TECHNICAL_DOCUMENT` for internal representation.
   - These codes will be used consistently in manifests and internal APIs; UI can map them to human-readable labels.

With these decisions, the plan is concrete and ready for implementation once you give the go-ahead.
