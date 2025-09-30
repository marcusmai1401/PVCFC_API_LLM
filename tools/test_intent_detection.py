#!/usr/bin/env python
"""
Test Intent Detection for Task 2.2
Tests that equipment tags without location keywords return ASK intent
"""
import argparse
import os
import sys
from typing import Dict, List, Tuple

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger
from rich.console import Console
from rich.table import Table

from app.rag.query_transform import QueryIntent, QueryTransformer

console = Console()


def create_test_cases() -> Dict[str, List[Tuple[str, QueryIntent]]]:
    """Create comprehensive test cases for intent detection"""
    return {
        "Equipment Tags Alone (Should be ASK)": [
            ("KT06101", QueryIntent.ASK),
            ("V-202", QueryIntent.ASK),
            ("P-301A", QueryIntent.ASK),
            ("pump P-301A", QueryIntent.ASK),
            ("valve V-202", QueryIntent.ASK),
            ("compressor KT06101", QueryIntent.ASK),
            ("KT06101 KT06102", QueryIntent.ASK),  # Multiple tags
        ],
        "Equipment Tags with Location Keywords (Should be LOCATE)": [
            ("where is KT06101", QueryIntent.LOCATE),
            ("locate V-202", QueryIntent.LOCATE),
            ("find pump P-301A", QueryIntent.LOCATE),
            ("KT06101 location", QueryIntent.LOCATE),
            ("position of V-202", QueryIntent.LOCATE),
            ("page containing P-301A", QueryIntent.LOCATE),
            ("where can I find KT06101", QueryIntent.LOCATE),
            ("show me where V-202 is located", QueryIntent.LOCATE),
        ],
        "Equipment Tags with Property Questions (Should be ASK)": [
            ("what is the pressure of KT06101", QueryIntent.ASK),
            ("KT06101 specifications", QueryIntent.ASK),
            ("V-202 operating temperature", QueryIntent.ASK),
            ("P-301A flow rate", QueryIntent.ASK),
            ("maximum pressure KT06101", QueryIntent.ASK),
            ("what are the specs for V-202", QueryIntent.ASK),
            ("operating conditions of P-301A", QueryIntent.ASK),
            ("KT06101 pressure temperature flow", QueryIntent.ASK),
        ],
        "General Questions (Should be ASK)": [
            ("what is the operating pressure", QueryIntent.ASK),
            ("maximum temperature", QueryIntent.ASK),
            ("specifications for the system", QueryIntent.ASK),
            ("what are the normal operating conditions", QueryIntent.ASK),
            ("pressure drop calculation", QueryIntent.ASK),
        ],
        "Explain Queries (Should be EXPLAIN)": [
            ("explain how the compressor works", QueryIntent.EXPLAIN),
            ("how does the cooling system operate", QueryIntent.EXPLAIN),
            ("why does pressure increase", QueryIntent.EXPLAIN),
            ("explain the process flow", QueryIntent.EXPLAIN),
        ],
        "Report Queries (Should be REPORT)": [
            ("generate a report on system parameters", QueryIntent.REPORT),
            ("create comprehensive summary", QueryIntent.REPORT),
            ("compile all information about KT06101", QueryIntent.REPORT),
            ("summarize everything about the system", QueryIntent.REPORT),
        ],
        "Edge Cases": [
            ("", QueryIntent.ASK),  # Empty query
            ("123", QueryIntent.ASK),  # Just numbers
            ("where", QueryIntent.LOCATE),  # Just "where"
            ("what", QueryIntent.ASK),  # Just "what"
            ("how much pressure", QueryIntent.ASK),  # "how much" should be ASK
            ("how many valves", QueryIntent.ASK),  # "how many" should be ASK
            ("how long does it take", QueryIntent.ASK),  # "how long" should be ASK
            ("how does it work", QueryIntent.EXPLAIN),  # "how does" should be EXPLAIN
        ],
    }


def test_intent_detection(transformer: QueryTransformer, verbose: bool = False):
    """Run intent detection tests"""
    test_cases = create_test_cases()

    total_tests = 0
    passed_tests = 0
    failed_cases = []

    for category, cases in test_cases.items():
        console.print(f"\n[bold blue]{category}[/bold blue]")

        category_passed = 0
        category_total = len(cases)

        for query, expected_intent in cases:
            total_tests += 1

            # Normalize and detect intent
            normalized = transformer.normalize_query(query)
            detected_intent = transformer.detect_intent(normalized)

            # Check if it matches expected
            if detected_intent == expected_intent:
                passed_tests += 1
                category_passed += 1
                if verbose:
                    console.print(f"  ✅ '{query}' → {detected_intent.value}")
            else:
                failed_cases.append((category, query, expected_intent, detected_intent))
                console.print(
                    f"  ❌ '{query}' → [red]{detected_intent.value}[/red] (expected: [green]{expected_intent.value}[/green])"
                )

        # Category summary
        if category_passed == category_total:
            console.print(f"  [green]✓ All {category_total} tests passed[/green]")
        else:
            console.print(
                f"  [yellow]⚠ {category_passed}/{category_total} tests passed[/yellow]"
            )

    return total_tests, passed_tests, failed_cases


def display_results_table(
    failed_cases: List[Tuple[str, str, QueryIntent, QueryIntent]]
):
    """Display failed test cases in a table"""
    if not failed_cases:
        return

    table = Table(title="Failed Test Cases", show_header=True)
    table.add_column("Category", style="cyan")
    table.add_column("Query", style="yellow")
    table.add_column("Expected", style="green")
    table.add_column("Got", style="red")

    for category, query, expected, detected in failed_cases:
        table.add_row(category[:30], query[:40], expected.value, detected.value)

    console.print("\n")
    console.print(table)


def test_specific_query(transformer: QueryTransformer, query: str):
    """Test a specific query and show detailed analysis"""
    console.print(f"\n[bold]Testing Query: '{query}'[/bold]")

    # Normalize
    normalized = transformer.normalize_query(query)
    console.print(f"Normalized: '{normalized}'")

    # Detect intent
    intent = transformer.detect_intent(normalized)
    console.print(f"Detected Intent: [bold cyan]{intent.value}[/bold cyan]")

    # Check for equipment tags
    import re

    equipment_pattern = r"\b[A-Z]{1,}[-]?\d{2,}[A-Z]?\b"
    equipment_tags = re.findall(equipment_pattern, query.upper())
    if equipment_tags:
        console.print(f"Equipment Tags Found: {equipment_tags}")

    # Check for location keywords
    location_keywords = [
        "where",
        "locate",
        "find",
        "position",
        "location",
        "page containing",
    ]
    found_location_keywords = [
        kw for kw in location_keywords if kw in normalized.lower()
    ]
    if found_location_keywords:
        console.print(f"Location Keywords Found: {found_location_keywords}")

    # Explanation
    console.print("\n[bold]Intent Detection Logic:[/bold]")
    if intent == QueryIntent.LOCATE:
        console.print("→ Detected LOCATE because query contains location keywords")
    elif intent == QueryIntent.ASK:
        if equipment_tags and not found_location_keywords:
            console.print(
                "→ Detected ASK because equipment tag found without location keywords (Task 2.2)"
            )
        else:
            console.print("→ Detected ASK based on question patterns or default")
    elif intent == QueryIntent.EXPLAIN:
        console.print("→ Detected EXPLAIN because query contains how/why patterns")
    elif intent == QueryIntent.REPORT:
        console.print(
            "→ Detected REPORT because query contains report/summary keywords"
        )


def main():
    parser = argparse.ArgumentParser(description="Test intent detection for Task 2.2")
    parser.add_argument("--query", type=str, help="Test a specific query")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all test results (not just failures)",
    )
    parser.add_argument("--test-all", action="store_true", help="Run all test cases")

    args = parser.parse_args()

    # Initialize transformer
    transformer = QueryTransformer(remove_stopwords=True)

    console.print("[bold]Task 2.2: Intent Detection Test[/bold]")
    console.print(
        "Testing that equipment tags without location keywords return ASK intent\n"
    )

    if args.query:
        # Test specific query
        test_specific_query(transformer, args.query)
    else:
        # Run all tests
        total, passed, failed = test_intent_detection(transformer, verbose=args.verbose)

        # Display summary
        console.print(f"\n[bold]Test Summary[/bold]")
        console.print(f"Total Tests: {total}")
        console.print(f"Passed: [green]{passed}[/green]")
        console.print(f"Failed: [red]{total - passed}[/red]")
        console.print(f"Success Rate: {passed/total*100:.1f}%")

        # Show failed cases table
        if failed:
            display_results_table(failed)
            console.print(
                "\n[yellow]⚠ Some tests failed. Review the logic for these cases.[/yellow]"
            )
        else:
            console.print(
                "\n[green]✅ All tests passed! Task 2.2 implementation is correct.[/green]"
            )

        # Key insights
        console.print("\n[bold]Key Behavior Changes (Task 2.2):[/bold]")
        console.print("1. Equipment tags alone (e.g., 'KT06101') → ASK intent")
        console.print(
            "2. Equipment tags + location words (e.g., 'where is KT06101') → LOCATE intent"
        )
        console.print(
            "3. Equipment tags + property questions (e.g., 'KT06101 pressure') → ASK intent"
        )
        console.print(
            "4. This prevents incorrect routing to /locate endpoint for property questions"
        )


if __name__ == "__main__":
    main()
