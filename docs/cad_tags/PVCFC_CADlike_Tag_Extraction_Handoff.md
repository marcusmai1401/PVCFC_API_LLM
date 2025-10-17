
# PVCFC — CAD-like Gate + Tag Extractor — Handoff Spec (Agent-Ready)

> **Goal**: Auto-detect *CAD-like* PDFs (e.g., P&ID/PFD/ISO/Loop/Schematic) without user folder separation, then extract **instrument tags** (e.g., `04 PSAL 2207`) with **stable bbox** + **suffixes** (A/B/C, 2oo3, -201B…), and expose them via a **sidecar “tags” index** for boosted retrieval and **vision crop citations**.
> **Non-goal**: Do *not* change core BM25/Weaviate logic for normal text documents; do *not* introduce paid APIs or heavyweight LLMs/YOLO unless explicitly enabled later.

---

## 1) Inputs, Outputs, Dependencies

### Inputs
- PDF files (mostly **CAD-exported**; some may be raster scans).
- No manual folder split; the system must **auto-gate**.

### Outputs
- `artifacts/page_layout/`: per-page JSON with text spans, vector drawings (when available).
- `artifacts/entities/tags.jsonl`: one JSON object per extracted tag.
- `artifacts/entities/relations.jsonl`: optional leader/stream/equipment relations.
- `artifacts/crops/`: PNG crops for bbox evidence (for vision citation).
- Sidecar index: **OpenSearch** index `pvcfc_pid_tags` (and optionally Weaviate class `TagEntity`).

### Dependencies (local, open-source)
- **PyMuPDF** (or `pdfminer.six`) for **vector-first** text & drawing extraction.
- **PaddleOCR v5** (local) as **OCR fallback** (only when pages are raster/no text vector).
- **OpenCV** (contours, Hough lines) for light shape/leader cues (optional but helpful).
- **R-tree/KD-tree** (e.g., `rtree`/`scipy`) for neighbor queries.
- **OpenSearch** client for sidecar index upserts (Weaviate optional).

---

## 2) High-level Flow

1. **CADLikeGate (auto)**: sample a few pages, compute **CAD-like score S ∈ [0,1]** → if `S ≥ 0.60`, treat as CAD-like.
2. **Page selection (“taggy” pages)**: among CAD-like docs, choose pages likely containing tags.
3. **Layout Build (vector-first)**: extract text spans (w/ bbox, font size, rotation) and vector drawings if available. Fallback to OCR only if raster.
4. **Tag Extractor (geometry-first)**:
   - ROI proposals (text-centric + optional shape-aware).
   - Assemble **AREA + CODE + NUM** vertically (CODE-anchored), ignore divider lines, attach **suffixes**.
5. **Artifacts**: write `tags.jsonl`, `relations.jsonl`, `crops/` evidence.
6. **Indexing**: upsert to **OpenSearch `pvcfc_pid_tags`** (keyword fields for filter; n-gram for fuzzy `tag` text).
7. **Serve**: intent detection → **parallel queries** (tags + chunks) → **RRF fusion** → rerank → if tag hit has `bbox`, attach **crop** for vision citation.

No changes to the existing chunk index; this is a **sidecar** enhancement.

---

## 3) CADLikeGate — Scoring (S)

**Sampling**: pages `[1, 2, 3, mid, last]` (5 pages default; may extend to 7–9 for very long docs).

**Score**: `S = Σ wᵢ · fᵢ`, with the following features and default weights (sum to 1.0):

| Feature (fᵢ) | Weight (wᵢ) | Computation Notes |
|---|---:|---|
| Producer/Creator contains CAD vendor | **0.20** | `f=1` if PDF metadata contains one of: `AutoCAD, Autodesk, Bentley, AVEVA, Intergraph, EPLAN, Plant3D, CAD`; else `0` |
| Geometry density | **0.15** | Normalize `(vector_paths + lines)/page_area` into `[0,1]` with sane caps |
| Short CAPS tokens rate | **0.15** | Ratio of spans matching `[A-Z]{2,4}` (PAL/PSAL/PIC/FIC/PT/…) over all spans |
| “3-piece tag” regex hits | **0.20** | Count on sampled pages; regex: `\b\d{2}\s+[A-Z]{2,4}\s+\d{3,5}[A-Z]?\b` (cap per page) → normalize |
| Technical suffix presence | **0.10** | Presence/normalized hits for `A/B/C`, `1oo2/2oo3`, `-\d{3,5}[A-Z]?`, `\d{3,5}[A-Z]` near tags |
| Non-A4 large page | **0.05** | `f=1` if page size ~A1/A0 or unusually large; else `0` |
| Multiple rotations | **0.05** | `f∝` number of rotated text spans (|θ|≥5°) |
| Leader-like lines | **0.10** | `f=1` if many thin lines end near text regions (leader pattern); else `0` |

**Thresholds**
- **CAD-like** if `S ≥ 0.60`.
- **Gray zone** `0.45 ≤ S < 0.60`: if filename contains any of `P&ID, PFD, ISO, Loop, Schematic, Piping` → treat as CAD-like.
- **Override**: support manual flags to force enable/disable gate per doc.

**Performance**: gate eval << 300ms/file (sampling only).

---

## 4) Page Selection — “Taggy” Pages

A CAD-like doc may have non-tag pages (title/legend only). Choose **taggy pages** to save compute:
- A page is **taggy** if **either**:
  - `regex_3piece_hits ≥ 3`, **or**
  - `#CODE_whitelist_tokens ≥ 4` (tokens like PAL/PSAL/PIC/FIC/PT/PXI/PSU/IS…).
- Optional: prefer pages where vector circles/boxes exist (instrument bubbles), if vector shapes are retrievable.

---

## 5) Layout Build (Vector-first, OCR-fallback)

### Vector-first
- Use PyMuPDF (or pdfminer) to extract **text spans**: `text`, `bbox=[x0,y0,x1,y1]`, `font_size`, `rotation_deg`, `page_id`.
- Extract **drawings** if available: lines/paths/circles/rects (some CAD circles are cubic Beziers; classification may be heuristic).

### OCR fallback (only for raster pages)
- PaddleOCR v5; store `text`, `bbox`, `confidence`.
- Use only when vector text is missing or insufficient.

### Normalization
- Unify page coordinate system and rotation per page.
- **Fix engineering spacing** artifacts common to SHX/CAD:
  - `"3.9  MPag" → "3.9 MPag"`, `"° C" → "°C"`
  - Ensure `"2oo3"` isn’t read as `"2003"` (normalize `o` vs `0` for this token).

**Output**: `artifacts/page_layout/page_{id}.json` with page size, spans, and optional shapes.

---

## 6) Tag Extractor (Geometry-first)

### 6.1 ROI Proposals (no heavy detectors)
- **Text-centric ROI** (default): find small **vertical columns** of 2–4 tokens where:
  - x-centers are approximately aligned,
  - vertical gaps are “reasonable” (see assembler tolerances),
  - at least one token is a known **CODE** (CAPS 2–4 letters in whitelist).
- **Shape-aware ROI** (optional): if vector circles/boxes/triangles are available, use them to prioritize/expand ROIs (instrument bubble, alarm triangle).

### 6.2 Token Roles & Regex (grammar)
- **AREA**: `^\d{2}$`
- **CODE**: `^[A-Z]{2,4}$` with **whitelist** (initial default; adjust per plant):
  - `PAL, PSAH, PSAL, PALL, PT, PI, PIC, FIC, HIC, LIC, TIC, PXI, PSU, IS` (extendable)
- **NUM**:  `^\d{3,5}[A-Z]?$` (allow trailing letter: `2046A`)
- **SUFFIX** (candidates):
  - `^[A-Z]/[A-Z](?:/[A-Z])?$` (e.g., `A/B`, `A/B/C`)
  - `^[1-3]oo[2-4]$` (e.g., `2oo3`)
  - `^-?\d{3,5}[A-Z]?$` (e.g., `-201B`)
  - `^\d{3,5}[A-Z]$` (e.g., `2208A` as a separate token)

### 6.3 Assembler (CODE-anchored, divider-tolerant)
- **Anchor**: choose a `CODE` token as the center of a vertical triplet.
- **Find** the nearest `AREA` **above** and `NUM` **below** within tolerances.
- **Tolerances** (defaults):
  - X-center alignment: `|Δx_center| ≤ 0.60 × min(width_AREA, width_NUM)`
  - Vertical spacing: each gap ∈ `[0.7, 2.0] × median(font_height_in_ROI)`
  - Font-size similarity: `|Δfont_size| ≤ 1.5 pt`
  - Rotation tolerance: `≤ 15°` misalignment relative to ROI axis
- **Scoring** (sum):
  - `+4` regex triplet match (AREA+CODE+NUM in order)
  - `+2` x-center alignment quality
  - `+2` vertical spacing uniformity
  - `+2` font-size similarity
  - `+1` alarm triangle present near ROI and CODE ∈ `{PAL,PSAL,PSAH}`
- **Pass threshold**: **`score ≥ 6`** → accept triplet; tag text = `"AREA CODE NUM"`.
- **Suffix attachment**: expand the accepted triplet’s union bbox by **`radius = 1.0em`** (1× median font height). If any SUFFIX candidates fall within, attach to `parts.suffix` and expand bbox accordingly.
- **Divider lines** inside bubbles are **ignored** for line-breaking; rely on alignment and spacing.

### 6.4 Relations & Noise Exclusion
- **Leader linking**: if thin line/arrow tip touches a symbol or pipe and starts near text, record `leader_to` relation (preferred over pure proximity).
- **Stream/Line codes**: permissive grammar for tokens like `10FG 04101 BB1 N` (phase/seq/class/service). Accept ragged spacing/line breaks.
- **Exclude zones**: don’t extract tags from **LEGEND/NOTES/FIGURE** boxes or page headers/footers (detect via titles or table-like frames).

### 6.5 Tag Output Schema (one JSON per tag)
```json
{
  "doc_id": "04000-CP25-05",
  "page": 5,
  "tag": "04 PSAL 2207",
  "parts": { "area": "04", "code": "PSAL", "num": "2207", "suffix": null },
  "bbox": [x0, y0, x1, y1],
  "rotation": 0.0,
  "confidence": 0.96,
  "evidence_span_ids": [123,124,125]
}
```
- `bbox` coordinates are in page space; `confidence` may be normalized from the scoring.

---

## 7) Indexing — OpenSearch Sidecar (`pvcfc_pid_tags`)

### Mapping
Use keyword fields for exact filter and an n-gram analyzer for fuzzy `tag` text.
```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "tag_ngram_analyzer": {
          "tokenizer": "ngram_tokenizer",
          "filter": ["lowercase"]
        }
      },
      "tokenizer": {
        "ngram_tokenizer": {
          "type": "ngram",
          "min_gram": 2,
          "max_gram": 6,
          "token_chars": ["letter", "digit", "symbol", "punctuation"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "tag":       { "type": "text", "analyzer": "tag_ngram_analyzer", "fields": { "kw": { "type": "keyword" } } },
      "area":      { "type": "keyword" },
      "code":      { "type": "keyword" },
      "num":       { "type": "keyword" },
      "suffix":    { "type": "keyword" },
      "doc_id":    { "type": "keyword" },
      "page":      { "type": "integer" },
      "bbox":      { "type": "float" },
      "rotation":  { "type": "float" },
      "confidence":{ "type": "float" },
      "ts_ingest": { "type": "date" }
    }
  }
}
```
**Doc ID**: use a deterministic `_id`, e.g., `"{doc_id}#{page}#{tag}"` (hash safely if needed).

---

## 8) Serve — Intent, Parallel Query, Fusion, Vision Citation

### Intent detection (tag-style queries)
Match any of:
- `(?P<area>\d{2})\s+(?P<code>[A-Z]{2,4})\s+(?P<num>\d{3,5}[A-Z]?)`
- `(?P<code>[A-Z]{2,4})\s*(?P<num>\d{3,5}[A-Z]?)`
Also scan for suffixes: `A/B(/C)?`, `[1-3]oo[2-4]`, `-\d{3,5}[A-Z]?`, `\d{3,5}[A-Z]`.

### Plan
- **Branch A — Tags index (OpenSearch)**: filter on `code`, `num` (and `area` if present); fallback full-text on `tag` to tolerate typos.
- **Branch B — Content index (existing chunks)**: BM25 + vector + rerank (no change).

### Fusion
- **RRF** (e.g., `k=60`) to merge results from A & B, then **final rerank** (top-50 → top-10).
- If a top result from A has `bbox`, attach **crop** (from `artifacts/crops/`) for **vision citation** in the answer UI.

---

## 9) Telemetry — “No build” Ops (lightweight)

Write **one JSONL line per file** after ingestion:
- `doc_id`, `cadlike_score`, `pages_sampled`, `is_cadlike`, `pages_taggy`,
- `tags_found_total`, `tags_found_per_page_p50`, `tags_found_per_page_p90`,
- `ocr_fallback_ratio`, `legend_excluded_hits`, `avg_triplet_score`, `elapsed_sec`.

**Warn thresholds** (heuristics):
- `is_cadlike=true` **and** `tags_found_total=0` → **warn**.
- `ocr_fallback_ratio > 0.20` for mostly-vector corpora → **warn**.
- `avg_triplet_score < 6.0` → **warn** (assembler tolerances might be too strict).
- Very low `tags_found_per_page_p50` (<2) with `cadlike_score ≥ 0.70` → **warn**.

**Smoke tests** (manual, 5–10 min; fixed set):
- Direct tags: `PSAL 2207`, `PAL 2208`, `PI 2046A`, `FIC 2910`, `PT 2511B`… → expect correct `doc_id+page` and bbox crop.
- Suffixes: `PAL 2208 A/B/C`, `2oo3`, `-201B`… → expect suffix recognized and crop stable.
- Semantic-lite (if vector search enabled): “cảm biến áp suất 2207”, “báo động áp suất 2208” → expect a correct tag in top-3.

---

## 10) Configuration Defaults (embed)

### 10.1 Ingestion Orchestrator
```yaml
enable_pid_tags: true
gate_mode: auto
cadlike_gate_config: cadlike_gate.yaml
tag_grammar_config: tag_grammar.yaml
page_filters_config: page_filters.yaml

sample_pages: [1, 2, 3, mid, last]
gate_threshold: 0.60
gray_zone_boost_keywords: [P&ID, PFD, ISO, Loop, Schematic, Piping]

taggy_page_rules:
  min_regex_hits_3piece: 3
  min_code_tokens: 4
  max_pages: -1

layout:
  prefer_vector_text: true
  ocr_fallback:
    enabled: true
    engine: paddleocr_v5
    min_confidence: 0.50

artifacts:
  base_dir: artifacts
  layout_dir: artifacts/page_layout
  entities_dir: artifacts/entities
  crops_dir: artifacts/crops
  logs_dir: artifacts/logs

index:
  tags_index_name: pvcfc_pid_tags
  opensearch_mapping: tags_index_mapping.json

telemetry:
  enable_runtime_log: true
  warn_thresholds:
    tags_zero_when_cadlike: true
    ocr_fallback_ratio: 0.20
    min_avg_triplet_score: 6.0
    low_tag_density_p50: 2
```

### 10.2 CAD-like Gate
```yaml
weights:
  producer_keyword: 0.20
  geometry_density: 0.15
  short_caps_rate: 0.15
  regex_3piece_hits: 0.20
  technical_suffix: 0.10
  non_a4_page: 0.05
  multi_rotation: 0.05
  leader_pattern: 0.10

producer_keywords: [AutoCAD, Autodesk, Bentley, AVEVA, Intergraph, EPLAN, Plant3D, CAD]

regex_3piece:
  pattern: "\\b\\d{2}\\s+[A-Z]{2,4}\\s+\\d{3,5}[A-Z]?\\b"
  per_page_cap: 20

thresholds:
  cadlike: 0.60
  gray_zone_low: 0.45
  gray_zone_boost_keywords: true
```

### 10.3 Tag Grammar & Assembler
```yaml
code_whitelist: [PAL, PSAH, PSAL, PALL, PT, PI, PIC, FIC, HIC, LIC, TIC, PXI, PSU, IS]
area_regex: "^[0-9]{2}$"
code_regex: "^[A-Z]{2,4}$"
num_regex:  "^[0-9]{3,5}[A-Z]?$"
suffix_candidates: ["^[A-Z]/[A-Z](?:/[A-Z])?$", "^[1-3]oo[2-4]$", "^-?[0-9]{3,5}[A-Z]?$", "^[0-9]{3,5}[A-Z]$"]

anchor: CODE
x_center_tolerance_ratio: 0.60
y_gap_ratio_range: [0.7, 2.0]
font_size_delta_pt: 1.5
rotation_tolerance_deg: 15
score_weights: {triplet_regex: 4, x_align: 2, y_uniform: 2, font_sim: 2, alarm_hint: 1}
pass_threshold: 6
suffix_radius_em: 1.0
```

### 10.4 Exclusion & Taggy Pages
```yaml
exclude_titles: ["^LEGEND\\b", "^NOTES\\b", "^FIGURE\\b", "^SYMBOLS\\b"]
exclude_layout: {table_like: true, header_footer: true}
taggy_min_regex_hits_3piece: 3
taggy_min_code_tokens: 4
prefer_bubbles_if_available: true
```

---

## 11) Edge Cases & Heuristics

- **Divider lines** inside bubbles: ignore for line-breaking; rely on alignment & spacing.
- **A/B/C suffix**: token can be right/left/below; use suffix radius (1.0em) from union bbox.
- **2oo3** voting near logic/PSU: accept as suffix; normalize `o` vs `0` correctly.
- **Trailing letters** (e.g., `2046A`): allowed in NUM; if separated (`2208` + `A`), attach via suffix rules.
- **Rotated text**: allow ±15°; base grouping on ROI axis, not global horizontal.
- **Legend/Notes**: hard exclude to avoid false positives with “nice regex but wrong context”.
- **Leader line**: if arrow tip hits a symbol/pipe, use to override naive proximity.
- **Raster anomaly**: if OCR used and conf is low, retry small ROI crops to improve local OCR (optional).

---

## 12) Environment (suggested)

```bash
ENABLE_PID_TAGS=true
PID_TAGS_GATE=auto      # auto|always|never
PID_TAGS_GATE_THRESH=0.60
PID_TAGS_MIN_REGEX_HITS=3
TAGS_INDEX_NAME=pvcfc_pid_tags
```

---

## 13) Extensibility

- Plant-specific **CODE whitelist** can be expanded without code changes.
- Gate weights/thresholds are config-only; adjust after initial logs.
- Sidecar index is isolated; rollback by disabling `ENABLE_PID_TAGS`.
- Optional Weaviate `TagEntity` can be added later for semantic filters.

---

## 14) Acceptance (lightweight, no-build)

- Rely on **runtime logs** + **fixed smoke tests** (8–12 queries).
- Expected behavior: for tag-like queries, top results contain **correct doc/page** and **bbox crop**; suffixes recognized.
- If warnings trigger, adjust config (`pass_threshold`, `x_center_tolerance_ratio`, whitelist, gate weights).

---

## 15) Assumptions (to avoid back-and-forth)

- Most PDFs are CAD-exported; **vector-first** is valid and fast.
- PaddleOCR v5 is installed locally (only used for raster pages).
- OpenSearch is available for a sidecar index (`pvcfc_pid_tags`).
- Chosen defaults fit typical PVCFC P&ID-like drawings; tune after first logs if needed.
