"""
Evaluation Script for P&ID Retrieval Enhancement

Measures Precision@5, Recall@10, and Latency on ground truth queries
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from loguru import logger

from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridWeaviateOpenSearchRetriever,
)


def calculate_precision_at_k(
    results: List[Any], ground_truth: Dict, k: int = 5
) -> float:
    """
    Calculate Precision@K

    Checks if expected tags or answer keywords appear in top-k results

    Args:
        results: Retrieval results
        ground_truth: Ground truth dict with expected_tags, expected_answer_contains
        k: Top-k to evaluate

    Returns:
        Precision score (0-1)
    """
    if not results:
        return 0.0

    top_k = results[:k]

    # Collect all text from top-k
    combined_text = " ".join([r.text for r in top_k if hasattr(r, "text")]).upper()

    relevant_count = 0

    # Check for expected tags
    expected_tags = ground_truth.get("expected_tags", [])
    for tag in expected_tags:
        if tag.upper() in combined_text:
            relevant_count += 1

    # Check for expected answer keywords
    expected_keywords = ground_truth.get("expected_answer_contains", [])
    for keyword in expected_keywords:
        if keyword.lower() in combined_text.lower():
            relevant_count += 0.5  # Partial credit

    # Normalize by number of expectations
    total_expected = len(expected_tags) + len(expected_keywords)
    if total_expected == 0:
        # No specific expectations, just check if we got results
        return 1.0 if len(top_k) > 0 else 0.0

    precision = min(1.0, relevant_count / total_expected)
    return precision


def calculate_recall_at_k(results: List[Any], ground_truth: Dict, k: int = 10) -> float:
    """
    Calculate Recall@K

    Similar to precision but checks if all expected items are found

    Args:
        results: Retrieval results
        ground_truth: Ground truth dict
        k: Top-k to evaluate

    Returns:
        Recall score (0-1)
    """
    if not results:
        return 0.0

    top_k = results[:k]
    combined_text = " ".join([r.text for r in top_k if hasattr(r, "text")]).upper()

    found_count = 0
    total_expected = 0

    # Check tags
    expected_tags = ground_truth.get("expected_tags", [])
    total_expected += len(expected_tags)
    for tag in expected_tags:
        if tag.upper() in combined_text:
            found_count += 1

    # Check keywords
    expected_keywords = ground_truth.get("expected_answer_contains", [])
    total_expected += len(expected_keywords)
    for keyword in expected_keywords:
        if keyword.lower() in combined_text.lower():
            found_count += 1

    if total_expected == 0:
        return 1.0 if len(top_k) > 0 else 0.0

    recall = found_count / total_expected
    return recall


def evaluate_pid_retrieval(
    ground_truth_file: Path = None,
    enable_pid_enhancement: bool = True,
    verbose: bool = True,
):
    """
    Evaluate P&ID retrieval performance on ground truth queries

    Args:
        ground_truth_file: Path to ground truth JSON file
        enable_pid_enhancement: Enable P&ID enhancements
        verbose: Print detailed results

    Returns:
        Dict with evaluation metrics
    """
    # Default ground truth file
    if ground_truth_file is None:
        ground_truth_file = PROJECT_ROOT / "tests/ground_truth/pid_queries.json"

    if not ground_truth_file.exists():
        logger.error(f"Ground truth file not found: {ground_truth_file}")
        return None

    # Load ground truth
    with open(ground_truth_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    logger.info("=" * 80)
    logger.info(f"P&ID RETRIEVAL EVALUATION")
    logger.info(f"Ground truth: {ground_truth_file}")
    logger.info(f"Test cases: {len(test_cases)}")
    logger.info(f"PID Enhancement: {enable_pid_enhancement}")
    logger.info("=" * 80)
    logger.info("")

    # Initialize retriever
    retriever = HybridWeaviateOpenSearchRetriever()

    # Metrics storage
    metrics = {
        "precision_at_5": [],
        "recall_at_10": [],
        "latency_ms": [],
    }

    results_detail = []

    # Evaluate each test case
    for idx, case in enumerate(test_cases, 1):
        query = case["query"]
        query_type = case.get("query_type", "unknown")

        if verbose:
            print(f"\n[{idx}/{len(test_cases)}] Query: {query}")
            print(f"  Type: {query_type}")

        # Execute retrieval
        start_time = time.time()

        try:
            results = retriever.retrieve_enhanced(
                query=query, top_k=10, enable_pid_enhancement=enable_pid_enhancement
            )
        except Exception as e:
            logger.error(f"  Retrieval failed: {e}")
            results = []

        latency = (time.time() - start_time) * 1000  # ms

        # Calculate metrics
        p5 = calculate_precision_at_k(results, case, k=5)
        r10 = calculate_recall_at_k(results, case, k=10)

        metrics["precision_at_5"].append(p5)
        metrics["recall_at_10"].append(r10)
        metrics["latency_ms"].append(latency)

        if verbose:
            print(f"  P@5: {p5:.2%}, R@10: {r10:.2%}, Latency: {latency:.0f}ms")

            if results:
                print(f"  Top result: {results[0].text[:100]}...")
                print(f"  Source: {results[0].source}, Score: {results[0].score:.4f}")

        # Store detailed results
        results_detail.append(
            {
                "query": query,
                "query_type": query_type,
                "precision_at_5": p5,
                "recall_at_10": r10,
                "latency_ms": latency,
                "num_results": len(results),
                "top_result": (
                    {
                        "text": results[0].text[:200],
                        "score": results[0].score,
                        "source": results[0].source,
                    }
                    if results
                    else None
                ),
            }
        )

    # Calculate summary statistics
    summary = {
        "total_queries": len(test_cases),
        "avg_precision_at_5": np.mean(metrics["precision_at_5"]),
        "avg_recall_at_10": np.mean(metrics["recall_at_10"]),
        "median_latency_ms": np.median(metrics["latency_ms"]),
        "p50_latency_ms": np.percentile(metrics["latency_ms"], 50),
        "p90_latency_ms": np.percentile(metrics["latency_ms"], 90),
        "p95_latency_ms": np.percentile(metrics["latency_ms"], 95),
        "min_latency_ms": np.min(metrics["latency_ms"]),
        "max_latency_ms": np.max(metrics["latency_ms"]),
    }

    # Print summary
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total queries: {summary['total_queries']}")
    print(f"Avg Precision@5: {summary['avg_precision_at_5']:.2%}")
    print(f"Avg Recall@10: {summary['avg_recall_at_10']:.2%}")
    print(f"P50 Latency: {summary['p50_latency_ms']:.0f}ms")
    print(f"P90 Latency: {summary['p90_latency_ms']:.0f}ms")
    print(f"P95 Latency: {summary['p95_latency_ms']:.0f}ms")
    print(f"Min Latency: {summary['min_latency_ms']:.0f}ms")
    print(f"Max Latency: {summary['max_latency_ms']:.0f}ms")
    print("=" * 80)

    # Success/Failure assessment
    print("\nTARGET METRICS:")
    print(
        f"  Precision@5 ≥ 90%: {'✅ PASS' if summary['avg_precision_at_5'] >= 0.9 else '❌ FAIL'}"
    )
    print(
        f"  Recall@10 ≥ 95%: {'✅ PASS' if summary['avg_recall_at_10'] >= 0.95 else '❌ FAIL'}"
    )
    print(
        f"  P50 Latency ≤ 2.5s: {'✅ PASS' if summary['p50_latency_ms'] <= 2500 else '❌ FAIL'}"
    )

    # Save detailed results
    output_file = PROJECT_ROOT / "tests/ground_truth/evaluation_results.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {"summary": summary, "details": results_detail},
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.info(f"\nDetailed results saved to: {output_file}")

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate P&ID retrieval performance")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help="Path to ground truth JSON file",
    )
    parser.add_argument(
        "--no-enhancement",
        action="store_true",
        help="Disable PID enhancement (baseline comparison)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")

    args = parser.parse_args()

    summary = evaluate_pid_retrieval(
        ground_truth_file=args.ground_truth,
        enable_pid_enhancement=not args.no_enhancement,
        verbose=not args.quiet,
    )

    if summary:
        # Exit with success if targets met
        meets_targets = (
            summary["avg_precision_at_5"] >= 0.9
            and summary["avg_recall_at_10"] >= 0.95
            and summary["p50_latency_ms"] <= 2500
        )
        sys.exit(0 if meets_targets else 1)
    else:
        sys.exit(1)
