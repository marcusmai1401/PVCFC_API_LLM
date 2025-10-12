# Evaluation Rubric & Test Plan (Citation Accuracy ≥90%)

## Dataset
- 20–50 gold Q&A built from current corpus
- Label per question: answer text, doc_id(s), exact page(s), quote(s)
- Include 30% table/figure questions; 30% VI; 40% long‑form

## Metrics
- Citation Accuracy:
  - Exact page: % citations with page == gold
  - Tolerant (±1): % citations with |page−gold| ≤ 1
- Coverage: % answers having ≥1 valid citation
- Groundedness: RAGAS/TruLens ≥85%
- Latency: p50/p95 (vision off/on)
- Stability: stdev across 3 runs/query

## Logging (per query)
- Retrieval top‑K (doc_id, page, score, source)
- Rerank scores (cross‑encoder)
- LLM output (answer, raw brackets)
- Parsed citations (doc_id, page, pdf_path, quote)
- Validator result (confidence, corrected, neighbor)

## Procedure
1) Warm‑up: run 5 queries twice (ignore)
2) Run full set; each query 3 times; average
3) Compute metrics; export JSON & Markdown
4) Manually inspect 10 worst cases; categorize errors

## Acceptance Gates
- Exact ≥75% AND (±1) ≥90%
- Coverage ≥98%; Groundedness ≥85%
- p95 latency: <3s (no vision), <4.5s (vision)

## Scenarios (toggle matrix)
- Baseline vs Page‑First vs Late‑Interaction vs Managed
- Cross‑encoder: off / fast / full
- Validator neighbor: ±2 / ±4
- Structured citations: off / on
- Vision: off / on (table/figure only)

## Deliverables
- JSON: per‑query logs + summary metrics
- MD/PDF: report with charts & top errors
- Decision note: Go/No‑Go, and next changes
