# Build Plan Docs Index

Date: 2025-10-03
Owner: Agent Mode
Purpose: Central index for all .md plans/reports with current status and next actions

---

## 1) Summary

- Total docs: 20
- Completed: 3
- In progress / Design: 6
- Blocked: 1
- Roadmaps/Phase plans: 6
- UI/Operational notes: 2

---

## 2) Current Focus (Active Tracks)

- 🔴 CiteFix-lite (citation validation) — Design reviewed & updated; pending implementation
- 🟡 Performance Benchmarks — pending
- 🟢 Page Rank Caching — pending
- ⚠️ Embeddings dependency fix — blocked (transformers ↔ sentence-transformers)

---

## 3) Completed

- ✅ HybridRetriever Integration
  - [INTEGRATION_COMPLETION_REPORT.md](completed/INTEGRATION_COMPLETION_REPORT.md) — Status: COMPLETE
  - [INTEGRATION_POINTS_ANALYSIS.md](completed/INTEGRATION_POINTS_ANALYSIS.md) — Status: Analysis Complete
  - [HYBRID_RETRIEVER_INTEGRATION_DESIGN.md](completed/HYBRID_RETRIEVER_INTEGRATION_DESIGN.md) — Status: Design Approved

- ✅ Semantic Ranking (Page Embeddings & Hybrid)
  - [SEMANTIC_RANKING_COMPLETION_REPORT.md](completed/SEMANTIC_RANKING_COMPLETION_REPORT.md) — Status: IMPLEMENTED & TESTED

---

## 4) In Progress / Design

- 📝 CiteFix-lite (Validation)
  - [CITEFIX_LITE_DESIGN_SUMMARY.md](designs/CITEFIX_LITE_DESIGN_SUMMARY.md) — Status: Design Reviewed & Updated
  - [CITEFIX_LITE_DESIGN.md](designs/CITEFIX_LITE_DESIGN.md) — Status: Design Phase

- 🧩 Page Index & Schema
  - [PAGE_INDEX_SCHEMA.md](designs/PAGE_INDEX_SCHEMA.md) — Status: Schema Design (reference)

- 📈 Phase 1 Gap Analysis (partially outdated; superseded by completion reports)
  - [PHASE1_GAP_ANALYSIS.md](roadmap/PHASE1_GAP_ANALYSIS.md) — Status: Partially Complete (70%)

- 📄 Plans for citation accuracy
  - [build_plan_citation_accuracy.md](designs/build_plan_citation_accuracy.md) — Status: Proposal/Plan
  - [citation_accuracy_compatibility_assessment.md](designs/citation_accuracy_compatibility_assessment.md) — Status: Compatibility Assessment

---

## 5) Blockers / Issues

- ⚠️ Embeddings Build Issue
  - [EMBEDDINGS_BUILD_ISSUE.md](issues/EMBEDDINGS_BUILD_ISSUE.md) — Status: Blocked by dependency
  - Action: Downgrade transformers to 4.40.0 or switch to Gemini provider; rebuild embeddings

---

## 6) Roadmaps / Phase Plans (Archive/Reference)

- Phase overviews (reference; keep for context)
  - [Build_plan_phase_0.md](roadmap/Build_plan_phase_0.md)
  - [Build_plan_phase_1.md](roadmap/Build_plan_phase_1.md)
  - [Build_plan_phase_2.md](roadmap/Build_plan_phase_2.md)
  - [Build_plan_phase_3.md](roadmap/Build_plan_phase_3.md)
  - [Build_plan_phase_4.md](roadmap/Build_plan_phase_4.md)
  - [PHASE0_IMPLEMENTATION_SUMMARY.md](roadmap/PHASE0_IMPLEMENTATION_SUMMARY.md)
  - [PHASE0_FINAL_REPORT.md](roadmap/PHASE0_FINAL_REPORT.md)

---

## 7) UI / Operational Notes

- 5AM UI Fix (adapter for API schemas)
  - [5AM-Fix.md](ops-ui/5AM-Fix.md)
  - [5AM-Fix-Implementation-Summary.md](ops-ui/5AM-Fix-Implementation-Summary.md)

- New features (backlog)
  - [New_feat_02-10.md](ops-ui/New_feat_02-10.md)

---

## 8) Outstanding Technical Debts (Tồn đọng kỹ thuật)

1) 🔴 CiteFix-lite Implementation
   - Implement citation_validator.py (no circular imports)
   - Integrate into CitationRetriever (metadata['validation'])
   - Add config flags: enable_validation, validation_level, min_confidence_threshold, filter_invalid_citations
   - Tests: unit + integration + real data samples

2) 🟡 Performance Benchmarks
   - Compare: BM25-only vs Hybrid vs Page-reranked vs Validated
   - Record p50/p95/p99 latencies; CPU/memory footprint
   - Document trade-offs; tune thresholds

3) 🟢 Page Rank Caching
   - LRU cache for (query, doc_id) → ranked_pages
   - Optional: cache query embeddings
   - Metrics: cache hit ratio, latency reduction

4) ⚠️ Embeddings Dependency Fix
   - ✅ RESOLVED: Using Gemini embeddings (`gemini-embedding-001`)
   - Status: Embeddings built successfully with 768D vectors
   - No further action required

5) Vision Enhancements (Phase 2)
   - find_bbox_by_quote(), smart_vision_strategy
   - API response includes bbox when available

6) Generator Legacy Path Cleanup
   - Reduce regex `[Doc N]` reliance when structured output is ON
   - Maintain backward compatibility

---

## 9) Suggested Organization (no file moves yet; proposal)

- Keep current files but use this INDEX.md as the single source of truth
- If approved, we can create subfolders and move files:
  - `./completed/` → completion reports & finalized designs
  - `./designs/` → active designs & proposals
  - `./issues/` → blocking issues & investigations
  - `./roadmap/` → phase plans & overviews
  - `./ops-ui/` → UI fixes & operational notes

I can perform the folder creation and move files upon your confirmation.

---

## 10) Next Actions (proposed)

- Approve the index as canonical
- Confirm if you want me to:
  1) Create subfolders and move files as per “Suggested Organization”
  2) Start implementing CiteFix-lite (Phase 1 of implementation plan)
  3) Kick off performance benchmarks after CiteFix-lite
