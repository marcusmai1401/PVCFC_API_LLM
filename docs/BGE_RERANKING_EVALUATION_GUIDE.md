# BGE CrossEncoder Reranking - Evaluation Guide

## Executive Summary

This guide helps you decide whether to enable BGE CrossEncoder reranking in your RAG pipeline through data-driven evaluation.

**TL;DR**: Run the evaluation scripts, get automatic recommendation based on latency/quality tradeoffs.

## What is BGE CrossEncoder Reranking?

### Concept
- **Cross-Encoder**: A deep neural model that scores (query, document) pairs together, more accurate than bi-encoder dot products
- **BGE (BAAI General Embedding)**: State-of-the-art reranking model from Beijing Academy of AI
- **Use Case**: Re-score top-K retrieval candidates to improve precision

### How It Works
1. **Initial Retrieval**: BM25 + FAISS retrieve top-50 candidates (fast but noisy)
2. **BGE Rerank**: CrossEncoder scores each (query, chunk) pair (slow but accurate)
3. **Top-K Selection**: Return top-10 after reranking (high precision)

### Tradeoffs

| Aspect | Without Reranking | With BGE Reranking |
|--------|------------------|-------------------|
| **Latency** | Fast (~500ms) | Slower (~700-850ms) |
| **Precision** | Good | Better (typically +5-15%) |
| **Recall** | Same | Same (acts on retrieved set) |
| **Cost** | Low | Medium (GPU recommended) |
| **Complexity** | Simple | Requires model loading |

## When to Consider BGE Reranking

### ✅ Good Fit
- Queries where top-1 answer matters (e.g., compliance checks)
- Domain with dense technical terminology (semantic similarity helps)
- Acceptable latency budget ≥1 second
- GPU available for inference
- High QPS is NOT required (<10 QPS)

### ❌ Not Recommended
- Real-time chat applications (latency-sensitive)
- Very high QPS (>50 QPS) without GPU
- Simple keyword lookups (BM25 already good)
- Budget constraints (CPU reranking is slow)

## Evaluation Process

### 1. Prepare Queries
Use existing QA set: `artifacts/qa/filtered_qa_set.jsonl`

Contains Vietnamese queries with:
- Equipment lookup questions
- Technical specification queries
- Mixed difficulty levels

### 2. Run Baseline
```powershell
.\scripts\eval_bge_rerank\01_run_baseline.ps1
```

Runs 30 queries **without** BGE reranking, captures:
- End-to-end latency (total_ms)
- Citations returned
- Confidence scores

Output: `artifacts/eval/run_baseline.jsonl`

### 3. Run BGE Chunk-Level Reranking
```powershell
.\scripts\eval_bge_rerank\02_run_bge_chunk.ps1
```

Runs same 30 queries **with** chunk-level BGE reranking:
- ENABLE_BGE_RERANK=true
- BGE_RERANK_LEVEL=chunk
- BGE_RERANK_TOP_K=10
- BGE_RERANK_CANDIDATE_LIMIT=50

⚠️ First query will be ~2-5s slower (model loading), then normal.

Output: `artifacts/eval/run_bge_chunk.jsonl`

### 4. (Optional) Run Doc-Level Reranking
```powershell
.\scripts\eval_bge_rerank\03_run_bge_doc.ps1
```

For document-level aggregation (useful if answers span multiple chunks):
- BGE_RERANK_LEVEL=doc
- BGE_RERANK_AGGREGATION=top3_mean

Output: `artifacts/eval/run_bge_doc.jsonl`

### 5. Compare & Get Recommendation
```powershell
.\scripts\eval_bge_rerank\04_compare_results.ps1
```

Computes metrics and generates recommendation.

Output: `artifacts/eval/comparison_baseline_vs_chunk.json`

## Metrics Explained

### Latency Metrics
- **total_ms.p95**: 95th percentile end-to-end latency
  - **Target**: Δ ≤ 350ms between baseline and rerank
- **rerank_ms.mean**: Average time spent in reranking
  - **Typical**: 100-300ms on GPU, 500-2000ms on CPU

### Quality Metrics
- **confidence.mean**: Average confidence score (0-1)
  - **Goal**: Improvement ≥ 0.01
- **citations.mean**: Average citations per query
  - **Goal**: Improvement ≥ 0.1
- **queries_with_citations**: Coverage metric

### Comparison
The evaluation script compares:
- P95 latency delta (ms and %)
- Mean latency delta
- Confidence improvement
- Citation quality improvement

## Decision Criteria

### Automatic Recommendation Logic

**Enable by default** if:
```
(P95_latency_increase ≤ 350ms) AND (confidence_delta > 0.01 OR citation_delta > 0.1)
```

**Keep disabled** otherwise.

### Example Good Case
```json
{
  "latency_delta": {
    "p95_increase_ms": 287,
    "p95_increase_pct": 34.2
  },
  "confidence_delta": {
    "delta": 0.034
  },
  "citation_delta": {
    "delta": 0.45
  }
}
```
✅ **Recommendation**: Enable (latency acceptable, quality improves)

### Example Bad Case
```json
{
  "latency_delta": {
    "p95_increase_ms": 450,
    "p95_increase_pct": 58.7
  },
  "confidence_delta": {
    "delta": 0.005
  },
  "citation_delta": {
    "delta": -0.02
  }
}
```
❌ **Recommendation**: Disable (latency too high, no quality gain)

## Suggested Configurations

### Chunk-Level (Recommended Default)
Best for most use cases:
```env
ENABLE_BGE_RERANK=true
BGE_RERANK_LEVEL=chunk
BGE_RERANK_TOP_K=10
BGE_RERANK_CANDIDATE_LIMIT=50
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_BATCH_SIZE=32
```

**When to use**: General-purpose improvement, answers in single chunks.

### Doc-Level with Aggregation
For multi-chunk answers:
```env
BGE_RERANK_LEVEL=doc
BGE_RERANK_AGGREGATION=top3_mean
```

**When to use**: Answers span multiple chunks from same document, want document-level ranking.

### Page-Level
For page-specific queries:
```env
BGE_RERANK_LEVEL=page
BGE_RERANK_AGGREGATION=max
```

**When to use**: Users cite page numbers, page is atomic unit.

## Advanced: Gating Logic

If you enable BGE rerank, consider **selective gating** to minimize latency impact:

### When to Apply Reranking
```python
apply_rerank = (
    candidate_count >= 20 AND
    (top1_score - top2_score) < 0.10
)
```

**Rationale**: Only rerank when there's ambiguity (low score margin) and enough candidates.

### When to Skip Reranking
```python
skip_rerank = (
    degrade_mode OR
    high_load OR
    query_length < 5
)
```

**Rationale**: Preserve baseline latency under stress or for simple queries.

### Implementation Hint
Modify `app/rag/retriever.py`:
```python
def _should_apply_bge_rerank(self, results: List[RetrievalResult]) -> bool:
    if not settings.enable_bge_rerank:
        return False

    # Gating logic
    if len(results) < 20:
        return False

    if len(results) >= 2:
        score_margin = results[0].score - results[1].score
        if score_margin > 0.10:
            return False  # Top result is confident

    return True
```

## Rollout Strategy

### Phase 1: Evaluation (Current)
1. Run scripts on 30-50 queries
2. Review metrics and recommendation
3. Decide on configuration

### Phase 2: Shadow Mode (Optional)
1. Enable rerank but log results without using them
2. Compare online metrics with baseline
3. Validate latency/quality in production

### Phase 3: Gradual Rollout
1. Enable for 10% of traffic
2. Monitor P95 latency, confidence, user feedback
3. Increase to 50%, then 100% if metrics hold

### Phase 4: Optimization
1. Implement gating logic
2. Fine-tune thresholds (top_k, candidate_limit)
3. Consider model distillation or quantization

## Monitoring

After enabling, track:

### Latency Metrics
- `rerank_ms` (mean, p50, p95)
- `total_ms` delta vs baseline
- Gating trigger rate

### Quality Metrics
- User satisfaction (thumbs up/down)
- Citation click-through rate
- Confidence distribution

### Infrastructure
- GPU utilization (if used)
- Memory usage (model cache)
- QPS limits

## Troubleshooting

### Slow First Query
**Symptom**: First query takes 5+ seconds
**Cause**: Model loading from disk
**Solution**: Acceptable, subsequent queries fast. Consider warm-up on startup.

### High Memory Usage
**Symptom**: OOM errors
**Cause**: Large batch size or model size
**Solution**: Reduce `RERANKER_BATCH_SIZE` to 16 or use smaller model.

### No Quality Improvement
**Symptom**: Metrics same or worse
**Cause**: Queries don't benefit from semantic reranking (e.g., exact keyword matches)
**Solution**: Keep disabled or use gating to apply selectively.

### Latency Too High
**Symptom**: P95 > 1.5 seconds
**Cause**: CPU inference or large candidate set
**Solution**: Use GPU, reduce `BGE_RERANK_CANDIDATE_LIMIT` to 30, or disable.

## Cost Analysis

### GPU Inference (Recommended)
- **Hardware**: RTX 4060 or better
- **Rerank time**: 100-300ms for 50 candidates
- **Throughput**: ~10-20 QPS sustained
- **Cost**: One-time GPU purchase

### CPU Inference (Not Recommended)
- **Rerank time**: 500-2000ms for 50 candidates
- **Throughput**: ~2-5 QPS
- **Cost**: Free but slow

### Model Options
| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| bge-reranker-base | 279M | Medium | Good |
| bge-reranker-large | 560M | Slow | Better |
| bge-reranker-v2-m3 | 568M | Slow | Best (multilingual) |

**Recommendation**: Start with `bge-reranker-base`, upgrade to v2-m3 if Vietnamese quality matters.

## Summary Checklist

- [ ] Run `01_run_baseline.ps1`
- [ ] Run `02_run_bge_chunk.ps1`
- [ ] Run `04_compare_results.ps1`
- [ ] Review `comparison_baseline_vs_chunk.json`
- [ ] Check recommendation: enable or disable?
- [ ] If enable: update `.env` with suggested config
- [ ] If enable: implement gating logic (optional)
- [ ] Monitor production metrics for 1 week
- [ ] Adjust thresholds based on real-world performance

## References

- **BGE Reranker**: https://huggingface.co/BAAI/bge-reranker-base
- **CrossEncoder Guide**: https://www.sbert.net/examples/applications/cross-encoder/README.html
- **Code**: `app/services/reranker.py`, `app/rag/retriever.py`

## Support

Questions? Check:
1. `scripts/eval_bge_rerank/README.md` - Quick start
2. `SYSTEM_ARCHITECTURE.md` - System overview
3. This guide - Decision framework
