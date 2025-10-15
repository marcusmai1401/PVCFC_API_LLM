"""
Trace Page Flow for Failed Citations

Analyzes how pages flow through the pipeline:
retrieval → doc_mapping → LLM brackets → parse → validator

Usage:
    python scripts/test_scripts/online_audit/audit_page_flow.py <test_results.json>
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


def extract_llm_brackets(answer: str) -> List[Dict[str, Any]]:
    """Extract [Doc X, p.Y] brackets from LLM answer"""
    brackets = []

    # Pattern: [Doc X, p.Y] or [Doc X, page Y]
    pattern = r"\[Doc\s*(\d+)(?:,\s*(?:p\.?|page)\s*(\d+))?\]"

    for match in re.finditer(pattern, answer):
        doc_num = int(match.group(1))
        page_num = int(match.group(2)) if match.group(2) else None
        brackets.append(
            {
                "doc_num": doc_num,
                "page_num": page_num,
                "raw": match.group(0),
            }
        )

    return brackets


def trace_page_flow(result: Dict[str, Any]) -> Dict[str, Any]:
    """Trace how page numbers flow through pipeline"""

    question_id = result["question_id"]
    response = result["response"]
    comparison = result["comparison"]

    # Extract components
    answer = response.get("answer", "")
    citations = response.get("citations", [])
    metadata = response.get("metadata", {})
    retrieval_details = metadata.get("retrieval_details", {})

    trace = {
        "question_id": question_id,
        "ground_truth_page": comparison["ground_truth_page"],
        "final_pages": [c.get("page") for c in citations],
        "page_distance": comparison.get("page_distance"),
        "flow": [],
    }

    # Step 1: Retrieval
    retrieval_pages = []
    if "top_results" in retrieval_details:
        for r in retrieval_details["top_results"][:10]:
            if r.get("doc_id") in [c.get("doc_id") for c in citations]:
                retrieval_pages.append(
                    {
                        "doc_id": r.get("doc_id", "unknown")[:50],
                        "page": r.get("page"),
                        "source": r.get("source"),
                        "score": r.get("score"),
                    }
                )

    trace["flow"].append(
        {
            "step": "1_retrieval",
            "pages_from_chunks": [p["page"] for p in retrieval_pages if p["page"]],
            "unique_pages": list(set(p["page"] for p in retrieval_pages if p["page"])),
        }
    )

    # Step 2: LLM brackets
    brackets = extract_llm_brackets(answer)
    trace["flow"].append(
        {
            "step": "2_llm_brackets",
            "brackets_found": len(brackets),
            "pages_explicit": [b["page_num"] for b in brackets if b["page_num"]],
            "pages_implicit": [b for b in brackets if not b["page_num"]],
        }
    )

    # Step 3: Parsed citations
    parsed_pages = [c.get("page") for c in citations]
    trace["flow"].append(
        {
            "step": "3_parsed_citations",
            "pages": parsed_pages,
            "count": len(citations),
        }
    )

    # Step 4: Validator
    validation = metadata.get("citation_validation", {})
    trace["flow"].append(
        {
            "step": "4_validator",
            "corrected_count": validation.get("corrected_count", 0),
            "avg_confidence": validation.get("avg_confidence"),
            "details": validation.get("details", []),
        }
    )

    # Diagnosis
    trace["diagnosis"] = []

    # Check if correct page was in retrieval
    if trace["ground_truth_page"] in trace["flow"][0]["unique_pages"]:
        trace["diagnosis"].append("* Correct page WAS in retrieval chunks")
    else:
        trace["diagnosis"].append(
            "X Correct page NOT in retrieval chunks (retrieval miss)"
        )

    # Check if LLM included page number
    if brackets and any(b["page_num"] for b in brackets):
        trace["diagnosis"].append(
            f'* LLM included explicit page numbers: {[b["page_num"] for b in brackets if b["page_num"]]}'
        )
    else:
        trace["diagnosis"].append(
            "X LLM did NOT include explicit page numbers (relying on chunk metadata)"
        )

    # Check if validator tried to correct
    if validation.get("corrected_count", 0) > 0:
        trace["diagnosis"].append(
            f'* Validator corrected {validation["corrected_count"]} citation(s)'
        )
    else:
        trace["diagnosis"].append(
            "X Validator made NO corrections (fuzzy match failed or confidence too low)"
        )

    # Check for multiple pages
    if len(set(parsed_pages)) > 1:
        trace["diagnosis"].append(
            f"! Multiple pages cited: {parsed_pages} (LLM cited all chunks, not best page)"
        )

    return trace


def main():
    if len(sys.argv) < 2:
        # Use most recent
        results_dir = Path("reports/test_results")
        json_files = list(results_dir.glob("citation_accuracy_golden_*.json"))
        if not json_files:
            print("Error: No test results found")
            sys.exit(1)
        json_file = max(json_files, key=lambda p: p.stat().st_mtime)
        print(f"Using: {json_file.name}")
    else:
        json_file = Path(sys.argv[1])

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("\n" + "=" * 80)
    print("PAGE FLOW TRACE ANALYSIS")
    print("=" * 80)

    # Analyze failed/partial cases
    failed_results = [
        r for r in data["results"] if r["success"] and "PASS" not in r["verdict"]
    ]

    print(f"\nTracing {len(failed_results)} failed/partial cases:\n")

    traces = []
    for result in failed_results:
        trace = trace_page_flow(result)
        traces.append(trace)

        print(f"\n[{trace['question_id']}]")
        print(f"  Ground truth: page {trace['ground_truth_page']}")
        print(f"  Final result: pages {trace['final_pages']}")
        print(f"  Distance: {trace['page_distance']}")

        print(f"\n  Flow:")
        for step_data in trace["flow"]:
            step = step_data["step"]
            if step == "1_retrieval":
                print(f"    {step}: Chunks had pages {step_data['unique_pages']}")
            elif step == "2_llm_brackets":
                print(
                    f"    {step}: Found {step_data['brackets_found']} brackets, explicit pages={step_data['pages_explicit']}"
                )
            elif step == "3_parsed_citations":
                print(
                    f"    {step}: Parsed {step_data['count']} citations, pages={step_data['pages']}"
                )
            elif step == "4_validator":
                print(f"    {step}: Corrected {step_data['corrected_count']} citations")

        print(f"\n  Diagnosis:")
        for diag in trace["diagnosis"]:
            print(f"    {diag}")

    # Save traces
    output_file = json_file.parent / f"page_flow_trace_{json_file.stem}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(traces, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print(f"* Traces saved to: {output_file}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
