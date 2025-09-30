#!/usr/bin/env python
"""
Test Citation Extraction with Page Numbers (Task 2.3)
Tests citation extraction from various formats including page numbers
"""
import argparse
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger
from rich.console import Console
from rich.table import Table

from app.rag.generator import (
    Citation,
    GeneratedAnswer,
    GeneratorConfig,
    ResponseGenerator,
)
from app.rag.query_transform import QueryIntent, TransformedQuery
from app.rag.retriever import RetrievalResult

console = Console()


def create_mock_retrieval_results() -> List[RetrievalResult]:
    """Create mock retrieval results with page numbers"""
    return [
        RetrievalResult(
            chunk_id="chunk_001",
            text="The CO2 compressor operates at a maximum pressure of 25 bar.",
            score=0.95,
            source="bm25",
            metadata={"doc_id": "PVCFC-DS-001", "page": 15},
            doc_id="PVCFC-DS-001",
            page=15,
        ),
        RetrievalResult(
            chunk_id="chunk_002",
            text="Operating temperature range is between -40°C and 85°C.",
            score=0.90,
            source="faiss",
            metadata={"doc_id": "PVCFC-DS-001", "page": 20},
            doc_id="PVCFC-DS-001",
            page=20,
        ),
        RetrievalResult(
            chunk_id="chunk_003",
            text="The valve V-202 has a flow coefficient (Cv) of 150.",
            score=0.85,
            source="bm25",
            metadata={"doc_id": "PVCFC-PID-04000", "page": 8},
            doc_id="PVCFC-PID-04000",
            page=8,
        ),
        RetrievalResult(
            chunk_id="chunk_004",
            text="Maintenance schedule: Monthly inspection, annual overhaul.",
            score=0.80,
            source="faiss",
            metadata={"doc_id": "PVCFC-OM-002", "page": 45},
            doc_id="PVCFC-OM-002",
            page=45,
        ),
        RetrievalResult(
            chunk_id="chunk_005",
            text="Safety shut-off pressure is set at 30 bar.",
            score=0.75,
            source="bm25",
            metadata={"doc_id": "PVCFC-DS-001", "page": 18},
            doc_id="PVCFC-DS-001",
            page=18,
        ),
    ]


def test_citation_formats():
    """Test different citation formats"""
    console.print("\n[bold blue]Testing Citation Format Patterns[/bold blue]\n")

    test_cases = [
        # (answer_text, expected_citations_count, description)
        ("The maximum pressure is 25 bar [Doc 1].", 1, "Basic format [Doc X]"),
        (
            "Operating temperature is -40°C to 85°C [Doc 2, p.20].",
            1,
            "With page number [Doc X, p.Y]",
        ),
        (
            "The valve has Cv=150 [Doc 3, page 8] according to specs.",
            1,
            "With 'page' word [Doc X, page Y]",
        ),
        (
            "See maintenance schedule [Doc 4, pp. 45-47] for details.",
            1,
            "Page range [Doc X, pp. Y-Z]",
        ),
        (
            "Multiple citations: pressure [Doc 1] and temperature [Doc 2, p.20].",
            2,
            "Multiple citations mixed formats",
        ),
        (
            "The pressure [1] and temperature [2] are critical parameters.",
            2,
            "Footnote style [X]",
        ),
        (
            "Combined info from [Doc 1, p.15], [Doc 2], and [Doc 3, page 8].",
            3,
            "Multiple citations with mixed page formats",
        ),
    ]

    # Create mock generator
    generator = ResponseGenerator(GeneratorConfig())

    # Create mock doc mapping
    mock_results = create_mock_retrieval_results()
    doc_mapping = {i + 1: result for i, result in enumerate(mock_results)}

    results_table = Table(title="Citation Format Tests")
    results_table.add_column("Test Case", style="cyan")
    results_table.add_column("Answer", style="yellow", width=40)
    results_table.add_column("Expected", style="green", justify="center")
    results_table.add_column("Found", style="blue", justify="center")
    results_table.add_column("Status", style="magenta")

    passed = 0
    total = len(test_cases)

    for answer_text, expected_count, description in test_cases:
        # Extract citations
        citations = generator._extract_citations(answer_text, doc_mapping)
        found_count = len(citations)

        # Check if passed
        status = "✅ PASS" if found_count == expected_count else "❌ FAIL"
        if found_count == expected_count:
            passed += 1

        # Truncate answer for display
        display_answer = (
            answer_text[:40] + "..." if len(answer_text) > 40 else answer_text
        )

        results_table.add_row(
            description, display_answer, str(expected_count), str(found_count), status
        )

    console.print(results_table)
    console.print(
        f"\n[bold]Summary: {passed}/{total} tests passed ({passed/total*100:.1f}%)[/bold]"
    )

    return passed == total


def test_citation_page_extraction():
    """Test page number extraction from citations"""
    console.print("\n[bold blue]Testing Page Number Extraction[/bold blue]\n")

    generator = ResponseGenerator(GeneratorConfig())
    mock_results = create_mock_retrieval_results()
    doc_mapping = {i + 1: result for i, result in enumerate(mock_results)}

    test_cases = [
        ("Reference [Doc 1, p.15] shows the data.", 1, 15),
        ("See document [Doc 2, page 20] for details.", 2, 20),
        ("As per [Doc 3] the valve specs...", 3, 8),  # Should use doc's page
        ("Multiple pages [Doc 4, pp. 45-47].", 4, 45),  # First page of range
        ("Simple footnote [1] reference.", 1, 15),  # Should map to Doc 1
    ]

    results = []
    for answer, expected_doc, expected_page in test_cases:
        citations = generator._extract_citations(answer, doc_mapping)

        if citations:
            citation = citations[0]
            doc_num = (
                int(citation.doc_id.split("-")[-1]) if "-" in citation.doc_id else 0
            )
            actual_page = citation.page

            status = "✅" if actual_page == expected_page else "❌"
            results.append((answer[:40], expected_page, actual_page, status))
        else:
            results.append((answer[:40], expected_page, "None", "❌"))

    # Display results
    table = Table(title="Page Number Extraction Tests")
    table.add_column("Answer Snippet", style="cyan", width=40)
    table.add_column("Expected Page", style="green", justify="center")
    table.add_column("Extracted Page", style="blue", justify="center")
    table.add_column("Status", style="magenta", justify="center")

    for answer, exp_page, act_page, status in results:
        table.add_row(answer, str(exp_page), str(act_page), status)

    console.print(table)

    passed = sum(1 for _, _, _, status in results if status == "✅")
    total = len(results)
    console.print(
        f"\n[bold]Summary: {passed}/{total} tests passed ({passed/total*100:.1f}%)[/bold]"
    )

    return passed == total


def test_end_to_end_generation():
    """Test end-to-end generation with citations"""
    console.print(
        "\n[bold blue]Testing End-to-End Generation with Citations[/bold blue]\n"
    )

    # Create generator
    config = GeneratorConfig(
        include_citations=True, citation_style="inline", temperature=0.3
    )
    generator = ResponseGenerator(config)

    # Create mock query and results
    query = TransformedQuery(
        original="What is the maximum pressure of the CO2 compressor?",
        normalized="what maximum pressure co2 compressor",
        intent=QueryIntent.ASK,
        filters=None,
        hyde_queries=None,
        language="en",
        metadata={},
    )

    retrieved_docs = create_mock_retrieval_results()

    # Test generation (mock the LLM call)
    import unittest.mock as mock

    mock_response = mock.Mock()
    mock_response.content = (
        "The maximum pressure of the CO2 compressor is 25 bar [Doc 1, p.15], "
        "with a safety shut-off at 30 bar [Doc 5, p.18]. "
        "The operating temperature range is -40°C to 85°C [Doc 2, page 20]."
    )

    with mock.patch.object(
        generator.llm_client, "generate", return_value=mock_response
    ):
        answer = generator.generate(query, retrieved_docs)

    console.print("[bold]Generated Answer:[/bold]")
    console.print(f"Query: {answer.query}")
    console.print(f"Answer: {answer.answer}")
    console.print(f"Confidence: {answer.confidence:.2f}")
    console.print(f"Citations: {len(answer.citations)}")

    # Display citations table
    if answer.citations:
        citations_table = Table(title="Extracted Citations")
        citations_table.add_column("Doc ID", style="cyan")
        citations_table.add_column("Page", style="green", justify="center")
        citations_table.add_column("Score", style="blue", justify="center")
        citations_table.add_column("Source", style="magenta")

        for citation in answer.citations:
            citations_table.add_row(
                citation.doc_id,
                str(citation.page) if citation.page else "N/A",
                f"{citation.relevance_score:.3f}",
                citation.source,
            )

        console.print("\n")
        console.print(citations_table)

    # Check results
    success = len(answer.citations) >= 3 and all(c.page for c in answer.citations)
    status = "[green]✅ SUCCESS[/green]" if success else "[red]❌ FAILED[/red]"
    console.print(f"\nTest Status: {status}")

    return success


def test_fallback_citations():
    """Test fallback citation behavior when no citations in text"""
    console.print("\n[bold blue]Testing Fallback Citation Behavior[/bold blue]\n")

    generator = ResponseGenerator(GeneratorConfig(include_citations=True))
    mock_results = create_mock_retrieval_results()
    doc_mapping = {i + 1: result for i, result in enumerate(mock_results[:3])}

    # Test with answer that has no explicit citations
    answer_no_citations = (
        "The maximum pressure is 25 bar according to the specifications."
    )

    citations = generator._extract_citations(answer_no_citations, doc_mapping)

    console.print(f"Answer: '{answer_no_citations}'")
    console.print(f"Doc mapping size: {len(doc_mapping)}")
    console.print(f"Citations found: {len(citations)}")

    if citations:
        console.print("\n[green]✅ Fallback citations generated:[/green]")
        for c in citations:
            console.print(f"  - {c.doc_id}, page {c.page}")
    else:
        console.print(
            "\n[yellow]⚠ No fallback citations (check if include_citations=True)[/yellow]"
        )

    # Should have fallback citations from top docs
    success = len(citations) > 0
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Test citation extraction with page numbers"
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument(
        "--test",
        choices=["formats", "pages", "generation", "fallback", "all"],
        default="all",
        help="Which test to run",
    )

    args = parser.parse_args()

    console.print("[bold]Task 2.3: Citation Extraction with Page Numbers Test[/bold]")
    console.print("=" * 60)

    tests = {
        "formats": ("Citation Format Patterns", test_citation_formats),
        "pages": ("Page Number Extraction", test_citation_page_extraction),
        "generation": ("End-to-End Generation", test_end_to_end_generation),
        "fallback": ("Fallback Citations", test_fallback_citations),
    }

    if args.test == "all":
        tests_to_run = tests.values()
    else:
        tests_to_run = [(tests[args.test][0], tests[args.test][1])]

    results = []
    for test_name, test_func in tests_to_run:
        try:
            console.print(f"\n[bold yellow]Running: {test_name}[/bold yellow]")
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            console.print(f"[red]Error in {test_name}: {e}[/red]")
            results.append((test_name, False))

    # Final summary
    console.print("\n" + "=" * 60)
    console.print("[bold]Final Test Summary[/bold]\n")

    summary_table = Table(show_header=True)
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Result", style="green")

    for test_name, success in results:
        result = "✅ PASS" if success else "❌ FAIL"
        summary_table.add_row(test_name, result)

    console.print(summary_table)

    total_passed = sum(1 for _, success in results if success)
    total_tests = len(results)
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    console.print(
        f"\n[bold]Overall: {total_passed}/{total_tests} passed ({success_rate:.1f}%)[/bold]"
    )

    if success_rate == 100:
        console.print(
            "\n[green]✅ All tests passed! Task 2.3 implementation is working correctly.[/green]"
        )
    else:
        console.print(
            "\n[yellow]⚠ Some tests failed. Review the implementation.[/yellow]"
        )


if __name__ == "__main__":
    main()
