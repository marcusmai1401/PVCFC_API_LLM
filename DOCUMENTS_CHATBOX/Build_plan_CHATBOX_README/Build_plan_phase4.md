## Build Plan — Phase 4: Vision Generation & CiteFix‑lite

### Goals
- Add Gemini 2.5 Vision for page images; validate citations with CiteFix‑lite (L1–L2).

### Source of Truth
- `../../docs/CITEFIX_QUICKSTART.md`
- `../../reports/CITATION_*`
- `../../docs/PROJECT_REPORTS/*`

### Prerequisites
- Phase 3 completed
- PDFs accessible at paths in `doc_id_map.json`

### Steps
1) Enable vision strategy
```ini
VISION_MAX_PAGES_TOTAL=10
PDF_RENDER_DPI=200
PDF_IMAGE_FORMAT=jpeg
```

2) Page selection & rendering
- Select up to 10 pages per response (±2 window around cited pages)
- Render to JPEG @ 200 DPI; skip failures gracefully

3) CiteFix‑lite validation
- Level 1: doc exists + page in range
- Level 2: fuzzy text match + neighbor scan ±2 pages

### Validation
- Quick vision tests from `../../docs/QUICK_TEST_GUIDE.md`
- Citation reports show ≥90% correctness on sample set

### KPIs (Phase Exit)
- Vision p95 latency < 2.5s for ≤10 pages
- Citation correctness ≥ 90%

### Troubleshooting
- "Vision usage: False" → enable vision flags; ensure PDFs readable
- Timeouts → reduce pages; verify API quota

### References
- `../../docs/CITEFIX_QUICKSTART.md`
- `../../reports/CITATION_INVESTIGATION_FINAL_REPORT.md`
