#!/usr/bin/env python
"""
Evaluate BGE Reranking Results

Compare baseline vs BGE reranking runs and compute metrics:
- Hits@1, Hits@3, MRR@10
- Latency P50, P95
- Citation quality

Usage:
    python tools/evaluate_rerank_results.py --baseline artifacts/eval/run_baseline.jsonl --rerank artifacts/eval/run_bge_chunk.jsonl --output artifacts/eval/comparison_report.json
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class RerankEvaluator:
    """Evaluate and compare reranking results"""

    def __init__(self):
        pass

    def load_results(self, results_path: Path) -> List[Dict[str, Any]]:
        """Load results from JSONL file"""
        results = []
        with results_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        return results

    def compute_metrics(
        self, results: List[Dict[str, Any]], run_name: str = "run"
    ) -> Dict[str, Any]:
        """
        Compute evaluation metrics for a result set

        Returns:
            Dict with accuracy and latency metrics
        """
        # Filter successful queries
        successful = [r for r in results if r.get("success", False)]

        if not successful:
            logger.warning(f"No successful queries in {run_name}")
            return {
                "total_queries": len(results),
                "successful_queries": 0,
                "accuracy": {},
                "latency": {},
            }

        # Latency metrics
        total_times = [r["timing"]["total_ms"] for r in successful]
        total_times.sort()

        rerank_times = [
            r["timing"].get("rerank_ms", 0)
            for r in successful
            if r["timing"].get("rerank_ms")
        ]
        rerank_times.sort()

        latency_metrics = {
            "total_ms": {
                "mean": float(np.mean(total_times)),
                "p50": float(np.percentile(total_times, 50)),
                "p95": float(np.percentile(total_times, 95)),
                "min": float(np.min(total_times)),
                "max": float(np.max(total_times)),
            }
        }

        if rerank_times:
            latency_metrics["rerank_ms"] = {
                "mean": float(np.mean(rerank_times)),
                "p50": float(np.percentile(rerank_times, 50)),
                "p95": float(np.percentile(rerank_times, 95)),
                "min": float(np.min(rerank_times)),
                "max": float(np.max(rerank_times)),
            }

        # Citation quality metrics
        citation_counts = [len(r.get("citations", [])) for r in successful]
        citation_metrics = {
            "mean_citations": float(np.mean(citation_counts)) if citation_counts else 0,
            "queries_with_citations": sum(1 for c in citation_counts if c > 0),
            "queries_without_citations": sum(1 for c in citation_counts if c == 0),
        }

        # Confidence metrics
        confidences = [r.get("confidence", 0.0) for r in successful]
        confidence_metrics = {
            "mean": float(np.mean(confidences)),
            "median": float(np.median(confidences)),
            "std": float(np.std(confidences)),
        }

        # Breakdown by difficulty
        by_difficulty = defaultdict(list)
        for r in successful:
            difficulty = r.get("original_metadata", {}).get("difficulty", "unknown")
            by_difficulty[difficulty].append(r)

        difficulty_breakdown = {}
        for difficulty, queries in by_difficulty.items():
            times = [q["timing"]["total_ms"] for q in queries]
            difficulty_breakdown[difficulty] = {
                "count": len(queries),
                "mean_latency_ms": float(np.mean(times)),
                "mean_citations": float(
                    np.mean([len(q.get("citations", [])) for q in queries])
                ),
            }

        return {
            "total_queries": len(results),
            "successful_queries": len(successful),
            "failed_queries": len(results) - len(successful),
            "latency": latency_metrics,
            "citations": citation_metrics,
            "confidence": confidence_metrics,
            "by_difficulty": difficulty_breakdown,
        }

    def compare_runs(
        self,
        baseline_results: List[Dict[str, Any]],
        rerank_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compare baseline vs reranking results

        Returns:
            Comparison report
        """
        baseline_metrics = self.compute_metrics(baseline_results, "baseline")
        rerank_metrics = self.compute_metrics(rerank_results, "rerank")

        # Compute deltas
        comparison = {
            "baseline": baseline_metrics,
            "rerank": rerank_metrics,
            "comparison": {},
        }

        # Latency delta
        if (
            baseline_metrics.get("latency")
            and rerank_metrics.get("latency")
            and baseline_metrics["latency"].get("total_ms")
            and rerank_metrics["latency"].get("total_ms")
        ):
            baseline_p95 = baseline_metrics["latency"]["total_ms"]["p95"]
            rerank_p95 = rerank_metrics["latency"]["total_ms"]["p95"]
            delta_p95 = rerank_p95 - baseline_p95

            baseline_mean = baseline_metrics["latency"]["total_ms"]["mean"]
            rerank_mean = rerank_metrics["latency"]["total_ms"]["mean"]
            delta_mean = rerank_mean - baseline_mean

            comparison["comparison"]["latency_delta"] = {
                "p95_increase_ms": float(delta_p95),
                "mean_increase_ms": float(delta_mean),
                "p95_increase_pct": float((delta_p95 / baseline_p95) * 100)
                if baseline_p95 > 0
                else 0,
            }

        # Rerank time breakdown
        if rerank_metrics.get("latency", {}).get("rerank_ms"):
            rerank_time = rerank_metrics["latency"]["rerank_ms"]
            comparison["comparison"]["rerank_overhead"] = {
                "mean_ms": rerank_time["mean"],
                "p95_ms": rerank_time["p95"],
            }

        # Citation quality comparison
        baseline_cit = baseline_metrics.get("citations", {})
        rerank_cit = rerank_metrics.get("citations", {})

        if baseline_cit and rerank_cit:
            comparison["comparison"]["citation_delta"] = {
                "baseline_mean": baseline_cit.get("mean_citations", 0),
                "rerank_mean": rerank_cit.get("mean_citations", 0),
                "delta": rerank_cit.get("mean_citations", 0)
                - baseline_cit.get("mean_citations", 0),
            }

        # Confidence comparison
        baseline_conf = baseline_metrics.get("confidence", {})
        rerank_conf = rerank_metrics.get("confidence", {})

        if baseline_conf and rerank_conf:
            comparison["comparison"]["confidence_delta"] = {
                "baseline_mean": baseline_conf.get("mean", 0),
                "rerank_mean": rerank_conf.get("mean", 0),
                "delta": rerank_conf.get("mean", 0) - baseline_conf.get("mean", 0),
            }

        return comparison

    def generate_recommendation(self, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate recommendation based on comparison

        Decision criteria:
        - Enable if P95 latency increase ≤ 350ms AND (confidence improves OR citations improve)
        - Otherwise disable by default
        """
        comp = comparison.get("comparison", {})
        latency_delta = comp.get("latency_delta", {})
        conf_delta = comp.get("confidence_delta", {})
        cit_delta = comp.get("citation_delta", {})

        p95_increase = latency_delta.get("p95_increase_ms", 0)
        conf_improvement = conf_delta.get("delta", 0)
        cit_improvement = cit_delta.get("delta", 0)

        # Decision logic
        latency_acceptable = p95_increase <= 350
        quality_improved = conf_improvement > 0.01 or cit_improvement > 0.1

        recommendation = {
            "enable_by_default": latency_acceptable and quality_improved,
            "reasoning": [],
            "suggested_config": {},
        }

        # Reasoning
        if p95_increase > 350:
            recommendation["reasoning"].append(
                f"P95 latency increases by {p95_increase:.0f}ms (>350ms threshold)"
            )
        else:
            recommendation["reasoning"].append(
                f"P95 latency increase acceptable: {p95_increase:.0f}ms"
            )

        if conf_improvement > 0.01:
            recommendation["reasoning"].append(
                f"Confidence improves by {conf_improvement:.3f}"
            )

        if cit_improvement > 0.1:
            recommendation["reasoning"].append(
                f"Citations per query improve by {cit_improvement:.2f}"
            )

        if not quality_improved:
            recommendation["reasoning"].append(
                "No significant quality improvement observed"
            )

        # Suggested config
        if recommendation["enable_by_default"]:
            recommendation["suggested_config"] = {
                "ENABLE_BGE_RERANK": "true",
                "BGE_RERANK_LEVEL": "chunk",
                "BGE_RERANK_TOP_K": "10",
                "BGE_RERANK_CANDIDATE_LIMIT": "50",
                "RERANKER_BATCH_SIZE": "32",
                "gating": {
                    "apply_when": "candidate_count >= 20 AND top2_score_margin < 0.10",
                    "skip_when": "degrade_mode OR high_load",
                },
            }
        else:
            recommendation["suggested_config"] = {
                "ENABLE_BGE_RERANK": "false",
                "note": "Keep disabled unless specific use cases require it",
            }

        return recommendation


def main():
    parser = argparse.ArgumentParser(description="Evaluate BGE reranking results")
    parser.add_argument(
        "--baseline",
        type=str,
        required=True,
        help="Baseline results (JSONL)",
    )
    parser.add_argument(
        "--rerank",
        type=str,
        required=True,
        help="Rerank results (JSONL)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output comparison report (JSON)",
    )

    args = parser.parse_args()

    # Load results
    baseline_path = Path(args.baseline)
    rerank_path = Path(args.rerank)

    if not baseline_path.exists():
        logger.error(f"Baseline file not found: {baseline_path}")
        sys.exit(1)

    if not rerank_path.exists():
        logger.error(f"Rerank file not found: {rerank_path}")
        sys.exit(1)

    evaluator = RerankEvaluator()

    logger.info("Loading results...")
    baseline_results = evaluator.load_results(baseline_path)
    rerank_results = evaluator.load_results(rerank_path)

    logger.info(f"Baseline: {len(baseline_results)} queries")
    logger.info(f"Rerank: {len(rerank_results)} queries")

    # Compare
    logger.info("\nComputing metrics...")
    comparison = evaluator.compare_runs(baseline_results, rerank_results)

    # Generate recommendation
    logger.info("Generating recommendation...")
    recommendation = evaluator.generate_recommendation(comparison)

    # Build final report
    report = {
        "comparison": comparison,
        "recommendation": recommendation,
        "metadata": {
            "baseline_file": str(baseline_path),
            "rerank_file": str(rerank_path),
            "baseline_queries": len(baseline_results),
            "rerank_queries": len(rerank_results),
        },
    }

    # Save report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"\n✅ Report saved to: {output_path}")

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("EVALUATION SUMMARY")
    logger.info("=" * 80)

    comp = comparison.get("comparison", {})

    if "latency_delta" in comp:
        lat = comp["latency_delta"]
        logger.info(f"\nLatency Impact:")
        logger.info(
            f"  P95 increase: {lat.get('p95_increase_ms', 0):.0f}ms ({lat.get('p95_increase_pct', 0):.1f}%)"
        )
        logger.info(f"  Mean increase: {lat.get('mean_increase_ms', 0):.0f}ms")

    if "rerank_overhead" in comp:
        ro = comp["rerank_overhead"]
        logger.info(f"\nRerank Overhead:")
        logger.info(f"  Mean: {ro.get('mean_ms', 0):.0f}ms")
        logger.info(f"  P95: {ro.get('p95_ms', 0):.0f}ms")

    if "confidence_delta" in comp:
        cd = comp["confidence_delta"]
        logger.info(f"\nConfidence:")
        logger.info(f"  Baseline: {cd.get('baseline_mean', 0):.3f}")
        logger.info(f"  Rerank: {cd.get('rerank_mean', 0):.3f}")
        logger.info(f"  Delta: {cd.get('delta', 0):+.3f}")

    if "citation_delta" in comp:
        cd = comp["citation_delta"]
        logger.info(f"\nCitations per Query:")
        logger.info(f"  Baseline: {cd.get('baseline_mean', 0):.2f}")
        logger.info(f"  Rerank: {cd.get('rerank_mean', 0):.2f}")
        logger.info(f"  Delta: {cd.get('delta', 0):+.2f}")

    logger.info(f"\n{'=' * 80}")
    logger.info("RECOMMENDATION")
    logger.info("=" * 80)

    rec = recommendation
    if rec.get("enable_by_default"):
        logger.info("✅ ENABLE BGE reranking by default")
    else:
        logger.info("❌ KEEP BGE reranking DISABLED by default")

    logger.info("\nReasoning:")
    for reason in rec.get("reasoning", []):
        logger.info(f"  - {reason}")

    logger.info("\nSuggested Config:")
    for key, value in rec.get("suggested_config", {}).items():
        if isinstance(value, dict):
            logger.info(f"  {key}:")
            for k, v in value.items():
                logger.info(f"    {k}: {v}")
        else:
            logger.info(f"  {key}: {value}")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
