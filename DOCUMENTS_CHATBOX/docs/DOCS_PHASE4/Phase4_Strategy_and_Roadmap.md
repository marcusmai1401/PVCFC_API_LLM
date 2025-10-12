# Phase4_Strategy_and_Roadmap

## 1) Executive Summary
- Objective: Evolve from validated Phase 3 (UI + OCR + retrieval evaluation) to production-grade reliability, security, and iterative optimization.
- Outcomes: A/B experimentation, end-to-end evaluation (faithfulness/citations), security controls, performance SLAs (p95 latency), and operational readiness.

---

## 2) Goals & Non-Goals
### Goals
- Grounded answers with measurable quality (faithfulness, citation correctness).
- A/B experimentation across retrieval/generation knobs (HyDE, rerank, RRF weights, k, max-tokens).
- Production controls: authN/Z, quotas, rate limiting, audit logs.
- Performance: p95 latency targets per route; caching and circuit breakers.
- Observability: structured logs, metrics, traces with dashboards.

### Non-Goals (Phase 5+)
- Multilingual pipeline, advanced doc ingestion automation at scale.
- Full data governance (PII redaction pipelines) beyond basic logging hygiene.

---

## 3) Scope & Deliverables
### In Scope
1. A/B & Evaluation
   - UI controls for toggles and variants; persist runs; compare metrics.
   - Retrieval + E2E evaluation: recall@k, precision@k, MRR, citation accuracy, factuality.
2. Security & Controls
   - API keys, roles (admin/viewer), per-key quotas, per-route rate limit.
   - Audit logging for prompts, outputs, costs (redaction for sensitive fields).
3. Performance & Resilience
   - Response caching (in-memory + optional Redis), request dedupe.
   - Timeouts, retries with backoff, circuit breakers for LLM and embeddings.
4. Observability
   - Metrics: latency, error rates, cache hit ratio, cost per request, token usage.
   - Tracing spans for retrieval, generation, rerank; sampling configuration.
5. Documentation & Playbooks
   - Operator guide, on-call runbook, A/B experimentation guide, security checklist.

### Out of Scope
- Horizontal scaling with k8s; multi-region HA.

---

## 4) Architecture Changes
- API Layer: introduce auth middleware, API key store, rate limiter, quota enforcer.
- Experiment Layer: configuration object (variant id) passed through pipeline (retrieval → generator → verifier), persisted to logs.
- Caching Layer: per-(query, variant) cache with TTL; guard invalidation on index rebuild.
- Evaluation Layer: unify runners to emit common schema (JSONL) for dashboarding.

---

## 5) Roadmap & Milestones
### M1: A/B Foundations (Week 1)
- Variant config schema in `app/core/config.py`.
- UI toggles mapping → variant id; persist to logs.
- Retrieval-only A/B: HyDE on/off, RRF weights; compute recall@k, MRR.

### M2: Security & Controls (Week 2)
- API key management, simple RBAC (admin/viewer).
- Rate limits (per key) and quotas; audit logs (redacted).

### M3: E2E Evaluation (Week 3)
- Add citation correctness check (can the answer’s citations cover referenced claims?).
- Faithfulness scoring (LLM-as-judge with constrained prompt + self-consistency).

### M4: Performance & Reliability (Week 4)
- Redis cache for retrieval + generation.
- Timeout + retry policy; circuit breaker wrapper for LLM and embeddings.
- p95 latency SLOs; dashboards.

### M5: Docs & Handover (Week 5)
- Guides: A/B, security, operations, dashboards.
- Final report and acceptance criteria sign-off.

---

## 6) Acceptance Criteria
- A/B: Can run two variants and compare metrics in UI; results stored to artifacts/logs.
- E2E eval: Produce CSV/JSON with recall@k, precision@k, MRR, citation accuracy, faithfulness.
- Security: API key required for protected routes; rate/quotas enforced; audit logs present.
- Performance: p95 latency targets met (e.g., /ask <= 2.5s with cache warm).
- Observability: Dashboards show latency, errors, cache hit, cost; traces visible for key spans.

---

## 7) Metrics & Telemetry
- Retrieval: recall@k, precision@k, MRR, coverage@k, unique sources.
- Generation: answer length, token usage, latency, citation count, citation coverage.
- Cost: per-provider, per-variant, per-request.
- Reliability: timeout rate, retry count, circuit open rate.
- Security: requests per API key, throttled/blocked counts.

---

## 8) Risks & Mitigations
- Provider rate limits → backoff + request collapsing + cache.
- Judge model drift → anchor prompts, sampling control, calibration set.
- False pass on citations → strict span overlap check; page-level heuristics.
- Cache staleness after index rebuild → versioned cache key with index hash.

---

## 9) Implementation Plan (Concrete Tasks)
- Add variant config structs and plumbing.
- Implement API key table (file or sqlite), middleware, and decorators.
- Add rate limiter + quota counters with sliding window.
- Introduce Redis optional client; wire caches in retriever and generator.
- Extend evaluation runner for citation/faithfulness; add prompts.
- Update UI for A/B compare view with charts.
- Add metrics (Prometheus): latency histograms, cache hit, errors, costs.
- Create Grafana dashboards json templates.

---

## 10) Checklists
### Security
- [ ] API key required on POST /ask, /report
- [ ] Roles enforced
- [ ] Quotas configured per key
- [ ] Audit logs redact secrets

### Reliability
- [ ] Timeouts and retries configured
- [ ] Circuit breakers in place
- [ ] Cache hit ratio > 60% on repeated queries

### Evaluation
- [ ] Retrieval A/B report generated
- [ ] E2E evaluation with citation & faithfulness

### Observability
- [ ] Latency dashboards up
- [ ] Error budget tracked
- [ ] Cost per request visible

---

## 11) References
- `docs/Phase3_Integration_Guide.md`
- `CHANGLOG_README/Phase3_Final_Report.md`
- `app/deps/indices.py`, `app/rag/retriever.py`, `tools/run_evaluation.py`
