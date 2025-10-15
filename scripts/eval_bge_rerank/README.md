# BGE CrossEncoder Reranking Evaluation

This directory contains scripts to evaluate whether BGE CrossEncoder reranking should be enabled in your RAG pipeline.

## Overview

The evaluation compares:
- **Baseline**: No BGE reranking (current default)
- **BGE Chunk**: Chunk-level reranking with top-K selection
- **BGE Doc** (optional): Document-level reranking with score aggregation

## Prerequisites

1. **API Running**: Start the API server first
   ```powershell
   .\start_api_debug.ps1
   ```

2. **Dependencies**: Ensure `sentence-transformers` is installed
   ```powershell
   pip install sentence-transformers
   ```

3. **QA Dataset**: Verify queries exist in `artifacts/qa/filtered_qa_set.jsonl`

## Quick Start

Run the full evaluation in sequence:

```powershell
# 1. Run baseline (no reranking)
.\scripts\eval_bge_rerank\01_run_baseline.ps1

# 2. Run BGE chunk-level reranking
.\scripts\eval_bge_rerank\02_run_bge_chunk.ps1

# 3. (Optional) Run BGE doc-level reranking
.\scripts\eval_bge_rerank\03_run_bge_doc.ps1

# 4. Compare and get recommendation
.\scripts\eval_bge_rerank\04_compare_results.ps1
```

Each script will:
- Set appropriate environment variables
- Check API availability
- Run 30 test queries (configurable)
- Save results incrementally
- Display summary statistics

## Output Files

Results are saved to `artifacts/eval/`:

- `run_baseline.jsonl` - Baseline results (no reranking)
- `run_bge_chunk.jsonl` - Chunk-level BGE reranking results
- `run_bge_doc.jsonl` - Doc-level BGE reranking results (optional)
- `comparison_baseline_vs_chunk.json` - Detailed comparison report with recommendation
- `comparison_baseline_vs_doc.json` - Doc-level comparison (if run)

## Metrics Evaluated

### Latency
- Total end-to-end time (P50, P95, mean)
- Rerank overhead (if enabled)
- By query difficulty

### Quality
- Mean citations per query
- Confidence scores
- Queries with/without citations

### Comparison
- P95 latency delta (should be ≤350ms)
- Confidence improvement
- Citation quality improvement

## Decision Criteria

The evaluation script will recommend **enabling** BGE rerank if:
- P95 latency increase ≤ 350ms, AND
- (Confidence improves by >0.01 OR Citations improve by >0.1)

Otherwise, it recommends **keeping it disabled** by default.

## Example Output

```
RECOMMENDATION
================================================================================
✅ ENABLE BGE reranking by default

Reasoning:
  - P95 latency increase acceptable: 287ms
  - Confidence improves by 0.034
  - Citations per query improve by 0.45

Suggested Config:
  ENABLE_BGE_RERANK: true
  BGE_RERANK_LEVEL: chunk
  BGE_RERANK_TOP_K: 10
  BGE_RERANK_CANDIDATE_LIMIT: 50
  RERANKER_BATCH_SIZE: 32
  gating:
    apply_when: candidate_count >= 20 AND top2_score_margin < 0.10
    skip_when: degrade_mode OR high_load
```

## Configuration Options

### Chunk-Level (Recommended)
```powershell
$env:ENABLE_BGE_RERANK = "true"
$env:BGE_RERANK_LEVEL = "chunk"
$env:BGE_RERANK_TOP_K = "10"
$env:BGE_RERANK_CANDIDATE_LIMIT = "50"
```

### Doc-Level (For Long Documents)
```powershell
$env:BGE_RERANK_LEVEL = "doc"
$env:BGE_RERANK_AGGREGATION = "top3_mean"  # or "max", "mean"
```

### Page-Level (For Page-Specific Queries)
```powershell
$env:BGE_RERANK_LEVEL = "page"
$env:BGE_RERANK_AGGREGATION = "max"
```

## Troubleshooting

### API Not Running
```
✗ API is not running!
Please start the API first with: .\start_api_debug.ps1
```
**Solution**: Start the API in another terminal

### Model Loading Slow
First query with BGE will be slower (~2-5s extra) for model loading.
Subsequent queries will use cached model.

### Out of Memory
Reduce batch size:
```powershell
$env:RERANKER_BATCH_SIZE = "16"  # default is 32
```

## Advanced Usage

### Run with Different Query Limits
Edit the scripts and change:
```powershell
$limit = 30  # Change to 50, 100, etc.
```

### Test on Specific Query Types
Filter the input JSONL by difficulty or category before running.

### Custom Comparison
Run the evaluation script directly:
```powershell
python tools/evaluate_rerank_results.py \
  --baseline artifacts/eval/run_baseline.jsonl \
  --rerank artifacts/eval/run_bge_chunk.jsonl \
  --output my_custom_report.json
```

## Next Steps

After evaluation:
1. Review the comparison report
2. If recommended, update `.env` with suggested config
3. Monitor production metrics after rollout
4. Consider implementing gating logic for selective reranking
