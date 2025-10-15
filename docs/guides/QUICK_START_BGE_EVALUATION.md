# BGE Reranking Evaluation - Quick Start

## ❓ Question: Should I Enable BGE CrossEncoder Reranking?

**Let's find out with data!** ⏱️ Takes ~10-15 minutes.

---

## 🚀 One-Command Evaluation

### Step 1: Start API (Terminal 1)
```powershell
.\start_api_debug.ps1
```
Wait for: `✅ Application startup complete`

### Step 2: Run Evaluation (Terminal 2)
```powershell
.\scripts\eval_bge_rerank\run_full_evaluation.ps1
```

That's it! The script will:
- ✅ Run 30 queries **without** reranking (baseline)
- ✅ Run same 30 queries **with** BGE reranking
- ✅ Compare results
- ✅ Give you a **clear recommendation**: Enable or Disable

---

## 📊 What You'll Get

At the end, you'll see:

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
```

OR

```
RECOMMENDATION
================================================================================
❌ KEEP BGE reranking DISABLED by default

Reasoning:
  - P95 latency increases by 450ms (>350ms threshold)
  - No significant quality improvement observed
```

---

## ⚡ What Happens Next?

### If Recommendation = ✅ ENABLE

Add to your `.env` file:
```env
ENABLE_BGE_RERANK=true
BGE_RERANK_LEVEL=chunk
BGE_RERANK_TOP_K=10
BGE_RERANK_CANDIDATE_LIMIT=50
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_BATCH_SIZE=32
```

Restart API and you're done!

### If Recommendation = ❌ DISABLE

Keep current config (no changes needed). BGE reranking is already disabled by default.

---

## 🤔 Want to Understand the Details?

Read the comprehensive guide:
```
docs/BGE_RERANKING_EVALUATION_GUIDE.md
```

Or script-level docs:
```
scripts/eval_bge_rerank/README.md
```

---

## 🔧 Troubleshooting

### "API is not running"
Start API first: `.\start_api_debug.ps1`

### "First query very slow (5+ seconds)"
Normal! BGE model loading. Subsequent queries fast.

### "Out of memory"
Reduce batch size before running:
```powershell
$env:RERANKER_BATCH_SIZE = "16"
```

---

## 📁 Where Are Results Saved?

All output in `artifacts/eval/`:
- `run_baseline.jsonl` - Baseline results
- `run_bge_chunk.jsonl` - Reranking results
- `comparison_baseline_vs_chunk.json` - **Full report + recommendation**

---

## ⏭️ Optional: Doc-Level Reranking

If you want to test document-level aggregation:

```powershell
.\scripts\eval_bge_rerank\03_run_bge_doc.ps1
```

Then compare:
```powershell
python tools/evaluate_rerank_results.py `
  --baseline artifacts/eval/run_baseline.jsonl `
  --rerank artifacts/eval/run_bge_doc.jsonl `
  --output artifacts/eval/comparison_baseline_vs_doc.json
```

---

## ✅ Summary

1. Start API: `.\start_api_debug.ps1`
2. Run evaluation: `.\scripts\eval_bge_rerank\run_full_evaluation.ps1`
3. Follow the recommendation
4. Update `.env` if enabling
5. Monitor production metrics

**Total time**: ~10-15 minutes for data-driven decision!

---

**Ready? Start API and run the evaluation! 🚀**
