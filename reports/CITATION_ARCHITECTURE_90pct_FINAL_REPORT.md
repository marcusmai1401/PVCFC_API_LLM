# RAG Architecture Options for ≥90% Citation Accuracy — Final Report

Author: AI Research Assistant
Date: 2025-10-07

## 1) Objective & Constraints
- Target: ≥90% citation page accuracy (exact OR ±1), groundedness ≥85%, p95 latency <3s (no-vision)
- Scope: Research only (no code changes now); deliver design options + evaluation rubric + roadmap

## 2) Current Pain Points (from your system)
- Page selection errors dominate (80% wrong pages in audit)
- Chunk `metadata.page` unreliable; validator failed to correct (0%)
- Page-level reranking not enabled

## 3) Architecture Options

### A. Page‑First RAG (Recommended)
Pipeline:
- Doc Retrieval: BM25 ∪ Dense (bge-small/MPNet) → RRF
- Page Index: BM25 over `text_by_page.jsonl` + page embeddings; consistent `doc_id↔pdf_path`
- Page Reranking: Cross‑encoder (monoT5 / MiniLM) on top‑K pages
- Generation: Structured citations (JSON schema: doc_id, page, quote, bbox?)
- Verification: CiteFix (±2..4) + NLI (MiniLM-L6) per-claim; calibrated confidence
- Vision (when needed): render exact page → bbox by quote → attach

Pros:
- Directly optimizes page selection (root cause)
- Strong controllability, on-prem friendly
Cons: extra compute for cross‑encoder/NLI; need page index build

Expected: 70–85% exact; 85–92% (±1); groundedness ≥85%

### B. Late‑Interaction Passage RAG
Pipeline:
- Retriever: ColBERTv2 (late interaction) or SPLADE sparse expander on passages
- Group passages → page vote/selection
- Then same generation + verification as A

Pros: SOTA passage precision; better exactness potential
Cons: infra complexity (GPU/ANN), cost/latency higher

Expected: 75–88% exact; 88–94% (±1)

### C. Managed Grounded Generation (Vectara / Vespa Cloud / Elastic+ELSER)
- Use managed retrieval+rerank+grounded generation w/ built‑in citations/quotes
- Add light NLI verification client-side

Pros: quick to production, decent defaults
Cons: vendor lock‑in, recurring cost, less control over verification

Expected: 80–90% depending on domain and content quality

## 4) Evaluation Rubric & Test Plan
Dataset
- 20–50 gold Q&A labeled (doc_id + exact page + quote); include VI/EN; 30% tables

Metrics
- Citation Accuracy: exact; tolerant(±1)
- Coverage: ≥98% questions with ≥1 valid citation
- Groundedness (RAGAS/TruLens): ≥85%
- Latency: p50/p95; Stability: stdev across 3 runs

Protocol
- Warm‑up; each query run 3×; average; log retrieval→rerank→LLM→validator
- Export JSON (per‑query) + MD summary; inspect top failures manually

Gates
- Accept if exact ≥75% AND (±1) ≥90% with p95 <3s (no‑vision)

## 5) Decision Criteria & Trade‑offs
- If you require controllability/offline: choose A (Page‑First)
- If exact‑only ≥85% is mandatory and compute is available: consider B (Late‑Interaction)
- If time‑to‑value priority and vendor acceptable: consider C (Managed)

Cost & Risks
- A: moderate dev + compute; robust path to 90% (±1)
- B: higher cost/latency; best exactness; operational complexity
- C: subscription cost; lock‑in; limited custom verification

## 6) Phased Roadmap (for later implementation)
P0 — Design (1 week)
- Finalize page index design (BM25+emb), structured citations, prompts
- Define gold dataset & rubric; logging schema

P1 — Prototype (1–2 weeks)
- Enable page index and cross‑encoder rerank (K=5..10)
- Structured citations JSON; implement basic CiteFix (±2)
- Run evaluation; tune weights/thresholds

P2 — Hardening (1–2 weeks)
- Add NLI per‑claim; confidence calibration; neighbor ±4
- Vision bbox for table/figure; caching; latency optimization
- Dashboards; alerting; readiness review

## 7) Implementation Notes (when building)
- Unify extractor for `text_by_page` and LLM context (reduce text mismatch)
- Use robust doc_id↔pdf_path mapping (one source of truth)
- Cache cross‑encoder and NLI results (per query) to control latency
- Start with MiniLM cross‑encoder; upgrade to monoT5 if needed
- Prefer structured JSON outputs to avoid regex parsing errors

## 8) References (for research & benchmarking)
- Haystack (deepset): page retrievers, cross‑encoder rerank, eval
- LlamaIndex: citation‑aware synthesis, structured outputs
- ColBERTv2 / SPLADE: BEIR late‑interaction retrieval
- Vectara: grounded generation with citations/quotes (API)
- RAGAS / TruLens: groundedness & citation evaluation

## 9) Recommendation
Choose **Option A — Page‑First RAG** as primary path to reach ≥90% (±1) with balanced cost/latency and strong control. If exact‑only ≥85% becomes a hard requirement and compute allows, pilot **Option B**. Keep **Option C** as a contingency when quick managed deployment is desired.
