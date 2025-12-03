#!/usr/bin/env python
"""
Smoke Tests for PID Tags Extraction
8-12 fixed queries for no-build validation

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 9 + Review_AI.md Section 9.1
Usage:
    python tests/smoke_test_tags.py
"""

import sys
from pathlib import Path
from typing import Dict, List

from loguru import logger
from rich.console import Console
from rich.table import Table

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


SMOKE_TEST_QUERIES = [
    # Direct tag queries
    {
        "query": "PSAL 2207",
        "type": "direct",
        "expect": "correct doc_id+page, bbox crop",
    },
    {
        "query": "PAL 2208",
        "type": "direct",
        "expect": "correct doc_id+page, bbox crop",
    },
    {
        "query": "PI 2046A",
        "type": "direct",
        "expect": "trailing letter A recognized",
    },
    {
        "query": "FIC 2910",
        "type": "direct",
        "expect": "correct doc_id+page",
    },
    {
        "query": "PT 2511B",
        "type": "direct",
        "expect": "suffix B recognized",
    },
    {
        "query": "04 PSAL 2207",
        "type": "direct",
        "expect": "full AREA+CODE+NUM recognized",
    },
    # Suffix variants
    {
        "query": "PAL 2208 A/B/C",
        "type": "suffix",
        "expect": "suffix A/B/C attached, crop stable",
    },
    {
        "query": "PSU 2oo3",
        "type": "suffix",
        "expect": "voting suffix 2oo3 recognized",
    },
    {
        "query": "PI -201B",
        "type": "suffix",
        "expect": "negative suffix -201B recognized",
    },
    # Semantic-lite (if vector search enabled)
    {
        "query": "cảm biến áp suất 2207",
        "type": "semantic",
        "expect": "PSAL/PT 2207 in top-3",
    },
    {
        "query": "báo động áp suất 2208",
        "type": "semantic",
        "expect": "PAL 2208 in top-3",
    },
    {
        "query": "flow indicator 2910",
        "type": "semantic",
        "expect": "FIC 2910 in top-3",
    },
]


def run_smoke_test(query_info: Dict) -> Dict:
    """
    Run single smoke test query

    Args:
        query_info: Query dict with query, type, expect

    Returns:
        Result dict with pass/fail
    """
    query = query_info["query"]

    try:
        # Import here to avoid import errors if modules not ready
        from app.rag.hybrid_with_tags_retriever import HybridWithTagsRetriever
        from app.rag.query_transform import QueryTransformer

        # Initialize
        retriever = HybridWithTagsRetriever()
        transformer = QueryTransformer()

        # Transform query
        transformed = transformer.transform(query)

        # Search
        results = retriever.search(transformed, top_k=10)

        # Check results
        has_bbox = False
        has_crop = False
        has_tag_source = False
        top_docs = []

        for i, result in enumerate(results[:3]):
            top_docs.append(
                {
                    "rank": i + 1,
                    "doc_id": result.doc_id,
                    "page": result.page,
                    "score": round(result.score, 3),
                    "source": result.metadata.get("source", "unknown")
                    if result.metadata
                    else "unknown",
                }
            )

            if result.metadata:
                if result.metadata.get("bbox"):
                    has_bbox = True
                if result.metadata.get("crop_path"):
                    has_crop = True
                if result.metadata.get("source") == "tags":
                    has_tag_source = True

        # Determine pass/fail (simplified heuristics)
        passed = len(results) > 0

        if query_info["type"] == "direct":
            # Direct tag queries should have tag source + bbox/crop
            passed = has_tag_source and (has_bbox or has_crop)
        elif query_info["type"] == "suffix":
            # Suffix queries should recognize suffix in results
            passed = has_tag_source
        elif query_info["type"] == "semantic":
            # Semantic queries should return some results
            passed = len(results) > 0

        return {
            "query": query,
            "type": query_info["type"],
            "passed": passed,
            "results_count": len(results),
            "has_tags_source": has_tag_source,
            "has_bbox": has_bbox,
            "has_crop": has_crop,
            "top_docs": top_docs,
        }

    except Exception as e:
        logger.error(f"Smoke test failed for query '{query}': {e}")
        return {
            "query": query,
            "type": query_info["type"],
            "passed": False,
            "error": str(e),
        }


def main():
    """Main entry point"""
    console = Console()

    console.print("\n" + "=" * 80, style="cyan")
    console.print("PID TAGS SMOKE TESTS (8-12 Fixed Queries)", style="cyan bold")
    console.print("=" * 80 + "\n", style="cyan")

    # Run all tests
    results = []
    for query_info in SMOKE_TEST_QUERIES:
        console.print(f"Testing: {query_info['query']}", style="yellow")
        result = run_smoke_test(query_info)
        results.append(result)

        status = "[green]PASS[/green]" if result.get("passed") else "[red]FAIL[/red]"
        console.print(f"  Status: {status}")
        console.print(f"  Results: {result.get('results_count', 0)}")
        console.print()

    # Summary table
    console.print("\n" + "=" * 80, style="cyan")
    console.print("SMOKE TEST SUMMARY", style="cyan bold")
    console.print("=" * 80 + "\n", style="cyan")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Query", style="white", width=30)
    table.add_column("Type", style="cyan", width=10)
    table.add_column("Status", style="white", width=8)
    table.add_column("Results", justify="right", width=8)
    table.add_column("Tags Src", justify="center", width=8)
    table.add_column("BBox", justify="center", width=6)
    table.add_column("Crop", justify="center", width=6)

    passed_count = 0
    for result in results:
        status_str = (
            "[green]PASS[/green]" if result.get("passed") else "[red]FAIL[/red]"
        )
        tags_src = (
            "[green]Y[/green]" if result.get("has_tags_source") else "[red]N[/red]"
        )
        bbox_str = "[green]Y[/green]" if result.get("has_bbox") else "-"
        crop_str = "[green]Y[/green]" if result.get("has_crop") else "-"

        table.add_row(
            result["query"][:28],
            result["type"],
            status_str,
            str(result.get("results_count", 0)),
            tags_src,
            bbox_str,
            crop_str,
        )

        if result.get("passed"):
            passed_count += 1

    console.print(table)

    # Overall stats
    total = len(results)
    pass_rate = (passed_count / total * 100) if total > 0 else 0

    console.print(
        f"\n[bold]Overall: {passed_count}/{total} passed ({pass_rate:.1f}%)[/bold]"
    )

    # Target: >= 90% pass rate
    if pass_rate >= 90:
        console.print("[green bold]✓ Smoke tests PASSED (>= 90%)[/green bold]\n")
        sys.exit(0)
    else:
        console.print(
            f"[red bold]✗ Smoke tests FAILED (< 90%, got {pass_rate:.1f}%)[/red bold]"
        )
        console.print("[yellow]Review telemetry logs and tune tolerances[/yellow]\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
