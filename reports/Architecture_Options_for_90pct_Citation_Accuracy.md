# Architecture Options for ≥90% Citation Accuracy (Research)

## Goal
- Achieve ≥90% citation page accuracy (exact or ±1) with groundedness ≥85%
- No code changes now; provide actionable design options and evaluation plan

## Option A — Page‑First RAG (Recommended)
- Retrieval (doc-level): BM25 ∪ Dense (bge-small/MPNet) + RRF
- Page index: Build BM25 over `text_by_page.jsonl` + page embeddings; 1:1 `doc_id↔pdf_path`
- Reranking: Cross‑encoder (monoT5 / MiniLM) on top‑K pages
- Generation: Structured citations (JSON schema: doc_id, page, quote, bbox?)
- Verification: CiteFix (±2..4 pages) + light NLI (MiniLM-L6) per-claim; compute confidence
- Vision (when needed): render exact page, find bbox by quote, attach to citation

Pros:
- High precision on page selection; robust to chunk page noise
- Strong control and extensibility; works offline/air‑gapped
Cons:
- Needs page index build and extra compute for rerank/NLI

Expected: 70–85% exact; 85–92% (±1); groundedness ≥85%

## Option B — Late‑Interaction Passage RAG
- Retriever: ColBERTv2 or SPLADE for high‑precision passage retrieval
- Group passages by page → select best page per doc
- Rerank & Verification as in Option A

Pros:
- State‑of‑the‑art passage precision; better for fine‑grained facts
Cons:
- More complex infra (GPU/ANN); higher latency/cost

Expected: 75–88% exact; 88–94% (±1)

## Option C — Managed Grounded Generation (Vectara / Vespa Cloud / Elastic + ELSER)
- Use managed retrieval + reranking + grounded generation with built‑in citations/quotes
- Add lightweight verification layer (NLI) client‑side

Pros:
- Quickest time‑to‑value; built‑in best practices
Cons:
- Vendor lock‑in, recurring cost; limited custom verification

Expected: 80–90% depending on domain

## Evaluation Rubric & Test Plan
- Dataset: 20–50 gold Q&A with labels (doc_id + page); include tables/figures
- Metrics:
  - Citation accuracy: exact page; tolerant (±1)
  - Coverage: % answers with ≥1 valid citation
  - Groundedness (RAGAS/TruLens): ≥85%
  - Latency: p50/p95 (vision off/on)
- Protocol:
  1) Warm‑up; run each query 3x, average
  2) Report doc and page confusion separately
  3) Log retrieval→rerank→LLM→validator signals per query

## Decision Criteria
- If exact ≥75% and (±1) ≥90% with p95 <3s → Accept
- If not, add NLI or increase cross‑encoder depth before switching to Option B/C

## Phased Roadmap (No‑code now; for implementation later)
- P0 (Design): finalize schema, indices, metrics, and prompts
- P1 (Prototype): enable page index and cross‑encoder; structured citations; basic CiteFix
- P2 (Hardening): add NLI, calibration, vision bbox; optimize latency; dashboards

## References (for research)
- Haystack: page‑level retrievers, cross‑encoder reranking, eval tools
- LlamaIndex: citation‑aware synthesis, structured outputs
- ColBERTv2 / SPLADE: BEIR late‑interaction passage retrieval
- Vectara: grounded generation with citations/quotes
- RAGAS / TruLens: groundedness & citation evaluation
