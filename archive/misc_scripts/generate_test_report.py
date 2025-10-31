"""
Test Report Generator
Generates markdown report from test results JSON
"""
import json
import sys
from datetime import datetime
from pathlib import Path


def generate_report(results_file: str):
    """Generate markdown report from test results"""

    # Load results
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    results = data["results"]

    # Group by query_id
    query_groups = {}
    for r in results:
        qid = r["query_id"]
        if qid not in query_groups:
            query_groups[qid] = []
        query_groups[qid].append(r)

    # Generate report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# P&ID Query Accuracy Test Report

**Generated:** {timestamp}
**Test File:** {results_file}

---

## Summary

- **Total Queries:** {summary['total_queries']}
- **Passed:** {summary['passed']}/5 ({summary['percentage']}%)
- **Required Passed:** {summary['required_passed']}/4

**Status:** {'SUCCESS - Meets minimum requirements' if summary['required_passed'] >= 4 else 'FAILURE - Below minimum requirements'}

---

## Detailed Results

"""

    # Per-query details
    for qid in sorted(query_groups.keys()):
        variants = query_groups[qid]

        # Find best variant
        best = max(variants, key=lambda v: 1 if v["status"] == "PASS" else 0)

        query_status = "PASS" if best["status"] == "PASS" else "FAIL"
        symbol = "✅" if query_status == "PASS" else "❌"

        report += f"### Query {qid}: {best['query'].split('tag name ')[1].split(' trong')[0]} {symbol}\n\n"
        report += f"**Expected Page:** {best['expected_page']}  \n"
        report += f"**Status:** {query_status}  \n\n"

        # Variant results
        report += "**Variant Results:**\n\n"
        report += (
            "| Variant | Status | Found Page | All Pages | Confidence | Latency |\n"
        )
        report += (
            "|---------|--------|------------|-----------|------------|---------|\n"
        )

        for v in variants:
            status_short = v["status"].replace("FAIL_", "").replace("_", " ")
            pages_str = str(v.get("all_pages", [])[:5])[:30]
            report += f"| {v['variant']} | {status_short} | {v.get('found_page', 'N/A')} | {pages_str} | {v.get('confidence', 0):.2f} | {v.get('latency_ms', 0)}ms |\n"

        report += "\n"

        # Best result details
        if best["status"] == "PASS":
            report += f"**Best Result:** {best['variant']} variant  \n"
            report += f"- Citations: {best['citations_count']}  \n"
            report += f"- Has Bbox: {best['has_bbox']}  \n"
        else:
            report += (
                f"**Issue:** {best.get('error', 'No matching page in results')}  \n"
            )

            # Add debug recommendation for required queries
            from_test_pid = [
                (1, "04 PSV 3926", 41),
                (2, "04 TI 5058", 58),
                (3, "04 TXI 2077", 17),
                (4, "04 ZI 4502", 100),
                (5, "06 FIC 1134", 103),
            ]

            test_info = next((t for t in from_test_pid if t[0] == qid), None)
            if test_info and qid <= 4:  # Required query failed
                report += f"\n**Debug Command:**\n"
                report += f'```bash\npython debug_pid_pipeline.py "{test_info[1]}" {test_info[2]} "Tìm cho tôi tag name {test_info[1]} trong bản vẽ P&ID"\n```\n'

        report += "\n---\n\n"

    # Recommendations
    report += "## Recommendations\n\n"

    if summary["required_passed"] < 4:
        report += "### Critical Issues Detected\n\n"

        failed_queries = [
            qid
            for qid in range(1, 5)
            if not any(v["status"] == "PASS" for v in query_groups.get(qid, []))
        ]

        if failed_queries:
            report += f"Required queries {failed_queries} failed. Debug actions:\n\n"
            report += "1. Run debug_pid_pipeline.py for each failed query\n"
            report += "2. Check if tags exist in OpenSearch index\n"
            report += "3. Verify PIDQueryEnhancer detects components\n"
            report += "4. Check API routing to tags_retriever\n\n"
    else:
        report += "All required queries passed. System working as expected.\n\n"

        if summary["passed"] == 5:
            report += "Perfect score! Consider this configuration production-ready.\n"
        else:
            report += (
                "Query 5 failed (acceptable). Consider investigating for improvement.\n"
            )

    # Save report
    output_file = f"TEST_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport generated: {output_file}")

    return output_file


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find latest results file
        results_files = list(Path(".").glob("TEST_RESULTS_*.json"))
        if not results_files:
            print("No test results found. Run test_pid_accuracy_5queries.py first.")
            sys.exit(1)

        latest = max(results_files, key=lambda p: p.stat().st_mtime)
        print(f"Using latest results: {latest}")
        results_file = str(latest)
    else:
        results_file = sys.argv[1]

    generate_report(results_file)
