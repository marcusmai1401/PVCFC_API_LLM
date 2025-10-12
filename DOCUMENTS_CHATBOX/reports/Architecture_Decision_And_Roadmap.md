# Architecture Decision & Roadmap (90% Citation Accuracy)

## Shortlist
- A) Page‑First RAG — Recommended
- B) Late‑Interaction Passage RAG (ColBERT/SPLADE)
- C) Managed Grounded Generation (Vectara / Vespa / Elastic)

## Decision (provisional)
- Choose A) Page‑First RAG if infra control and offline capability are required
- Escalate to B) only if exact‑only ≥85% is mandated and compute budget allows
- Consider C) if time‑to‑value is critical and vendor lock‑in is acceptable

## Why Page‑First now
- Directly optimizes page selection (root cause of current errors)
- Lower complexity vs ColBERT; retains extensibility (NLI, bbox)
- Balanced latency/accuracy; simplest path to ≥90% (±1)

## Roadmap (no‑code design; for later implementation)

P0 — Design (1 week)
- Finalize indices (page BM25 + embeddings), schema, prompts
- Define evaluation set & rubric; logging spec

P1 — Prototype (1–2 weeks)
- Enable page index + cross‑encoder rerank
- Add structured citations (JSON), basic CiteFix (±2)
- Dry‑run evaluation; iterate weights (BM25/semantic)

P2 — Hardening (1–2 weeks)
- Add NLI per‑claim, calibration; expand neighbor to ±4
- Vision bbox for table/figure; latency optimizations; caching
- Dashboards & alerts; readiness review

## Risks & Mitigations
- OCR/markdown mismatch → unify extractor for `text_by_page` & LLM context
- Cost of rerank/NLI → fast tiers, batch, cache; limit K
- Evals drift → CI with small gold set; periodic refresh

## Next Research Tasks
- Validate references from Haystack/LlamaIndex docs
- Survey cross‑encoders and NLI models (latency/quality)
- Collect production case studies (Vectara/Vespa)
