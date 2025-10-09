"""
Analyze Golden Citation Test Results

Parses JSON results and generates detailed analysis report.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def analyze_results(json_file: Path) -> Dict[str, Any]:
    """Analyze test results and extract key insights"""

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    results = data["results"]

    analysis = {
        "summary": summary,
        "patterns": {
            "by_language": defaultdict(lambda: {"pass": 0, "partial": 0, "fail": 0}),
            "by_file": defaultdict(lambda: {"pass": 0, "partial": 0, "fail": 0}),
            "page_errors": [],
        },
        "validator_stats": {
            "avg_confidence": [],
            "corrected_count": 0,
            "total_citations": 0,
        },
        "retrieval_stats": {
            "avg_scores": [],
            "source_distribution": defaultdict(int),
        },
    }

    # Analyze each result
    for result in results:
        if not result["success"]:
            continue

        lang = result["language"]
        ground_truth_file = result.get("question_id", "unknown")

        # Classify verdict
        verdict = result["verdict"]
        if "PASS" in verdict:
            category = "pass"
        elif "PARTIAL" in verdict:
            category = "partial"
        else:
            category = "fail"

        analysis["patterns"]["by_language"][lang][category] += 1

        # Page error analysis
        comp = result["comparison"]
        if comp["page_distance"] is not None and comp["page_distance"] > 0:
            analysis["patterns"]["page_errors"].append(
                {
                    "question_id": result["question_id"],
                    "expected_page": comp["ground_truth_page"],
                    "actual_pages": [c["page"] for c in comp["matched_citations"]],
                    "page_distance": comp["page_distance"],
                }
            )

        # Validator stats
        response_meta = result["response"].get("metadata", {})
        if "citation_validation" in response_meta:
            val = response_meta["citation_validation"]
            if "avg_confidence" in val:
                analysis["validator_stats"]["avg_confidence"].append(
                    val["avg_confidence"]
                )
            if "corrected_count" in val:
                analysis["validator_stats"]["corrected_count"] += val["corrected_count"]

        citations = result["response"].get("citations", [])
        analysis["validator_stats"]["total_citations"] += len(citations)

        # Retrieval stats
        retrieval_details = response_meta.get("retrieval_details", {})
        if "top_results" in retrieval_details:
            for r in retrieval_details["top_results"][:5]:
                if "source" in r:
                    analysis["retrieval_stats"]["source_distribution"][r["source"]] += 1
                if "score" in r:
                    analysis["retrieval_stats"]["avg_scores"].append(r["score"])

    # Calculate averages
    if analysis["validator_stats"]["avg_confidence"]:
        analysis["validator_stats"]["mean_confidence"] = sum(
            analysis["validator_stats"]["avg_confidence"]
        ) / len(analysis["validator_stats"]["avg_confidence"])

    if analysis["retrieval_stats"]["avg_scores"]:
        analysis["retrieval_stats"]["mean_score"] = sum(
            analysis["retrieval_stats"]["avg_scores"]
        ) / len(analysis["retrieval_stats"]["avg_scores"])

    return analysis


def print_analysis(analysis: Dict[str, Any]):
    """Print human-readable analysis"""

    print("\n" + "=" * 80)
    print("GOLDEN CITATION TEST ANALYSIS")
    print("=" * 80)

    summary = analysis["summary"]
    print(f"\n[Overall Results]")
    print(f"  Total tests: {summary['total_tests']}")
    print(f"  * Correct doc+page: {summary['correct_doc_and_page']}")
    print(f"  ~ Correct doc, wrong page: {summary['correct_doc_wrong_page']}")
    print(f"  X Wrong doc: {summary['wrong_doc']}")
    print(f"  Pass rate: {summary.get('pass_rate', 0):.1%}")
    print(f"  Doc match rate: {summary.get('doc_match_rate', 0):.1%}")

    print(f"\n[Pattern Analysis]")
    print(f"\n  By Language:")
    for lang, stats in analysis["patterns"]["by_language"].items():
        print(
            f"    {lang.upper()}: pass={stats['pass']}, partial={stats['partial']}, fail={stats['fail']}"
        )

    print(f"\n  Page Errors (Distance > 0):")
    for err in analysis["patterns"]["page_errors"]:
        print(
            f"    {err['question_id']}: expected p.{err['expected_page']}, got {err['actual_pages']}, distance={err['page_distance']}"
        )

    print(f"\n[Validator Stats]")
    val_stats = analysis["validator_stats"]
    print(f"  Total citations: {val_stats['total_citations']}")
    print(f"  Corrected count: {val_stats['corrected_count']}")
    if "mean_confidence" in val_stats:
        print(f"  Mean confidence: {val_stats['mean_confidence']:.2%}")

    print(f"\n[Retrieval Stats]")
    ret_stats = analysis["retrieval_stats"]
    if "mean_score" in ret_stats:
        print(f"  Mean retrieval score: {ret_stats['mean_score']:.4f}")
    print(f"  Source distribution:")
    for source, count in ret_stats["source_distribution"].items():
        print(f"    {source}: {count}")

    print(f"\n[Key Findings]")

    # Finding 1: Page accuracy issue
    page_error_rate = len(analysis["patterns"]["page_errors"]) / summary["total_tests"]
    print(
        f"  1. Page Accuracy Issue: {page_error_rate:.0%} of queries have page errors"
    )

    # Finding 2: Validator effectiveness
    if val_stats["total_citations"] > 0:
        correction_rate = val_stats["corrected_count"] / val_stats["total_citations"]
        print(
            f"  2. Validator Correction Rate: {correction_rate:.1%} (corrected {val_stats['corrected_count']}/{val_stats['total_citations']} citations)"
        )

    # Finding 3: Doc matching
    doc_match_rate = summary.get("doc_match_rate", 0)
    if doc_match_rate >= 0.8:
        print(f"  3. Document Retrieval: GOOD (80%+ doc match rate)")
    else:
        print(
            f"  3. Document Retrieval: NEEDS IMPROVEMENT ({doc_match_rate:.0%} doc match rate)"
        )

    print(f"\n[Recommended Next Steps]")

    if page_error_rate > 0.6:
        print(f"  ! HIGH PRIORITY: Investigate page metadata quality (Step 4)")
        print(f"  ! Check doc_id_map consistency (Step 2)")
        print(f"  ! Trace page flow for failed cases (Step 3)")

    if correction_rate < 0.1:
        print(f"  ! Validator is not correcting pages - check neighbor scan (Step 6)")

    if doc_match_rate < 0.8:
        print(f"  ! Document retrieval needs tuning - check BM25/FAISS balance")

    print("\n" + "=" * 80)


def main():
    if len(sys.argv) < 2:
        # Find most recent result file
        results_dir = Path("reports/test_results")
        json_files = list(results_dir.glob("citation_accuracy_golden_*.json"))
        if not json_files:
            print("Error: No test results found")
            sys.exit(1)
        json_file = max(json_files, key=lambda p: p.stat().st_mtime)
        print(f"Using most recent result: {json_file.name}")
    else:
        json_file = Path(sys.argv[1])

    if not json_file.exists():
        print(f"Error: File not found: {json_file}")
        sys.exit(1)

    analysis = analyze_results(json_file)
    print_analysis(analysis)

    # Save analysis
    analysis_file = json_file.parent / f"analysis_{json_file.stem}.json"
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"\n* Detailed analysis saved to: {analysis_file}")


if __name__ == "__main__":
    main()
