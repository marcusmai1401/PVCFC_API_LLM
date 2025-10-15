# BGE CrossEncoder Reranking - Evaluation Implementation Complete

## ✅ Implementation Status

All evaluation infrastructure has been implemented and is ready to use.

## What Was Built

### 1. Batch Query Runner (`tools/batch_query_runner.py`)
- Sends multiple queries to API with timing capture
- Incremental result saving (JSONL format)
- Supports all query parameters (hyde, execution_mode, etc.)
- Captures retrieval info, citations, confidence, timing breakdown

### 2. Evaluation Script (`tools/evaluate_rerank_results.py`)
- Compares baseline vs reranked results
- Computes latency metrics (P50, P95, mean)
- Computes quality metrics (confidence, citations)
- Generates automatic recommendation based on decision criteria
- Outputs detailed JSON report

### 3. PowerShell Execution Scripts (`scripts/eval_bge_rerank/`)
- `01_run_baseline.ps1` - Run without BGE reranking
- `02_run_bge_chunk.ps1` - Run with chunk-level BGE reranking
- `03_run_bge_doc.ps1` - Run with doc-level aggregation (optional)
- `04_compare_results.ps1` - Compare and generate recommendation
- `run_full_evaluation.ps1` - Master script to run all steps
- `README.md` - Quick start guide

### 4. Documentation
- `docs/BGE_RERANKING_EVALUATION_GUIDE.md` - Comprehensive decision guide
- `scripts/eval_bge_rerank/README.md` - Script usage guide
- This summary document

## How to Use

### Quick Start (3 Commands)

```powershell
# Start API first (in separate terminal)
.\start_api_debug.ps1

# Run full evaluation (one command)
.\scripts\eval_bge_rerank\run_full_evaluation.ps1
```

This will:
1. Run 30 queries baseline (no reranking)
2. Run same 30 queries with BGE chunk-level reranking
3. Compare and output recommendation

**Estimated time**: 10-15 minutes

### Individual Steps

If you prefer step-by-step:

```powershell
# 1. Baseline
.\scripts\eval_bge_rerank\01_run_baseline.ps1

# 2. BGE Reranking
.\scripts\eval_bge_rerank\02_run_bge_chunk.ps1

# 3. Compare
.\scripts\eval_bge_rerank\04_compare_results.ps1
```

## Output Files

All results saved to `artifacts/eval/`:

- `run_baseline.jsonl` - Baseline results
- `run_bge_chunk.jsonl` - BGE reranking results
- `comparison_baseline_vs_chunk.json` - Full comparison report with recommendation

## Decision Criteria (Automated)

The evaluation will recommend **enabling** BGE rerank if:

```
P95 latency increase ≤ 350ms
AND
(Confidence improves >0.01 OR Citations improve >0.1)
```

Otherwise, keep disabled.

## Example Recommendation Output

```json
{
  "enable_by_default": true,
  "reasoning": [
    "P95 latency increase acceptable: 287ms",
    "Confidence improves by 0.034",
    "Citations per query improve by 0.45"
  ],
  "suggested_config": {
    "ENABLE_BGE_RERANK": "true",
    "BGE_RERANK_LEVEL": "chunk",
    "BGE_RERANK_TOP_K": "10",
    "BGE_RERANK_CANDIDATE_LIMIT": "50",
    "RERANKER_BATCH_SIZE": "32"
  }
}
```

## Next Steps (User Actions)

### To Run Evaluation:
1. ✅ Infrastructure is ready
2. ⚠️ **Start API**: `.\start_api_debug.ps1`
3. ⚠️ **Run evaluation**: `.\scripts\eval_bge_rerank\run_full_evaluation.ps1`
4. ⚠️ **Review recommendation** in output
5. ⚠️ **Update .env** if recommended to enable

### To Implement Recommendation:
If evaluation recommends enabling:

```env
# Add to .env
ENABLE_BGE_RERANK=true
BGE_RERANK_LEVEL=chunk
BGE_RERANK_TOP_K=10
BGE_RERANK_CANDIDATE_LIMIT=50
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_BATCH_SIZE=32
```

Then restart API and monitor production metrics.

## Technical Details

### Query Dataset
Uses existing: `artifacts/qa/filtered_qa_set.jsonl` (57 queries)
- Default limit: 30 queries (configurable)
- Vietnamese equipment/datasheet queries
- Mixed difficulty levels

### BGE Model
- Model: `BAAI/bge-reranker-base` (279M params)
- First query: ~2-5s (model loading)
- Subsequent: ~100-300ms on GPU, ~500-2000ms on CPU

### Metrics Computed
**Latency:**
- Total end-to-end time (mean, P50, P95)
- Rerank overhead (if enabled)

**Quality:**
- Mean confidence score
- Mean citations per query
- Queries with/without citations

**Breakdown:**
- By difficulty (easy/medium/hard)
- Deltas between baseline and rerank

## Advanced Usage

### Run with Different Limits
Edit scripts and change:
```powershell
$limit = 50  # Default is 30
```

### Test Doc-Level Reranking
```powershell
.\scripts\eval_bge_rerank\03_run_bge_doc.ps1
```

Then compare:
```powershell
python tools/evaluate_rerank_results.py \
  --baseline artifacts/eval/run_baseline.jsonl \
  --rerank artifacts/eval/run_bge_doc.jsonl \
  --output artifacts/eval/comparison_baseline_vs_doc.json
```

### Custom Evaluation
```powershell
python tools/batch_query_runner.py \
  --input your_queries.jsonl \
  --output your_results.jsonl \
  --limit 20
```

## Troubleshooting

### API Not Running
```
✗ API is not running!
```
**Solution**: Start API in another terminal: `.\start_api_debug.ps1`

### First Query Very Slow
First query with BGE will load model (~2-5s). Subsequent queries fast.

### Out of Memory
Reduce batch size:
```powershell
$env:RERANKER_BATCH_SIZE = "16"  # default is 32
```

## Files Created

```
tools/
  batch_query_runner.py         # Batch query execution
  evaluate_rerank_results.py    # Metrics computation and comparison

scripts/eval_bge_rerank/
  01_run_baseline.ps1           # Run baseline
  02_run_bge_chunk.ps1          # Run BGE chunk rerank
  03_run_bge_doc.ps1            # Run BGE doc rerank (optional)
  04_compare_results.ps1        # Compare and recommend
  run_full_evaluation.ps1       # Master script
  README.md                     # Quick start guide

docs/
  BGE_RERANKING_EVALUATION_GUIDE.md  # Comprehensive guide

BGE_RERANK_EVALUATION_SUMMARY.md     # This file
```

## Summary

✅ **All evaluation infrastructure is complete and ready to use.**

To proceed with evaluation, user needs to:
1. Start API server
2. Run `.\scripts\eval_bge_rerank\run_full_evaluation.ps1`
3. Review recommendation
4. Update configuration if recommended

The scripts will handle everything automatically and output a clear recommendation.

---

**Implementation Date**: 2025-10-15
**Status**: Ready for User Execution
**Estimated Evaluation Time**: 10-15 minutes
