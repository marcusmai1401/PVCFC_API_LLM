## Build Plan — Phase 6: UI, Evaluation & Performance

### Goals
- Finalize Streamlit demo flows; formalize evaluation; set performance baselines and quick wins.

### Source of Truth
- `../../streamlit_app/*`
- `../../reports/Evaluation_Rubric_and_Test_Plan.md`
- `../../tests/integration/*`, `../../tests/OPTIMIZATION_REPORT.md`
- `../../artifacts/perf_*` (if present)

### Prerequisites
- Phase 5 completed

### Steps
1) Streamlit UI flows
- Verify ask, locate, open PDF, IEEE citation toggle
- Ensure vision screenshot rendering works as expected

2) Evaluation
```powershell
pytest tests/unit -v
pytest tests/integration -v
python tests/integration/test_week1_pipeline.py
```

3) Performance Baseline
- Measure p50/p95 latency on `/api/ask` (text vs vision)
- Record QPS with autocannon/hey equivalent (Windows: `wrk` via WSL)

4) Quick Wins
- Warm BGE cache by one dummy query
- Enable caches (TTL 10m) in config
- Batch OpenSearch queries where applicable

### Validation
- All tests pass (see Optimization Report)
- UI demo paths complete without errors

### KPIs (Phase Exit)
- p95 E2E latency ≤ 2s (text), ≤ 3.5s (vision ≤ 10 pages)
- 0 critical errors in logs during demo

### Troubleshooting
- Slow first response → warm caches
- UI unable to render images → verify PDF paths and rendering DPI

### References
- `../../tests/OPTIMIZATION_REPORT.md`
- `../../reports/Evaluation_Rubric_and_Test_Plan.md`
