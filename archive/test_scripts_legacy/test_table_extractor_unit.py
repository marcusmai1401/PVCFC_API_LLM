"""
Unit test for TableExtractor module with synthetic data
Tests core functionality without relying on specific PDF files
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from app.ingestion.table_extractor import TableData, TableExtractor

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")


def test_markdown_conversion():
    """Test table to Markdown conversion"""
    print("\n" + "=" * 80)
    print("TEST 1: Markdown Conversion")
    print("=" * 80 + "\n")

    extractor = TableExtractor()

    # Test case: Simple 3x3 table
    test_cells = [
        ["Header 1", "Header 2", "Header 3"],
        ["Row1 Col1", "Row1 Col2", "Row1 Col3"],
        ["Row2 Col1", "Row2 Col2", "Row2 Col3"],
    ]

    print("Input cells:")
    for row in test_cells:
        print(f"  {row}")

    markdown = extractor._convert_to_markdown(test_cells)

    print("\nGenerated Markdown:")
    print("─" * 80)
    print(markdown)
    print("─" * 80)

    # Verify
    lines = markdown.split("\n")
    checks = {
        "Has header row": len(lines) >= 1,
        "Has separator": len(lines) >= 2 and "---" in lines[1],
        "Has data rows": len(lines) >= 4,
        "Correct format": all("|" in line for line in lines),
    }

    print("\nVerification:")
    all_passed = True
    for check_name, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
        if not result:
            all_passed = False

    return all_passed


def test_cell_cleaning():
    """Test cell text cleaning"""
    print("\n" + "=" * 80)
    print("TEST 2: Cell Text Cleaning")
    print("=" * 80 + "\n")

    extractor = TableExtractor()

    test_cases = [
        ("  Normal text  ", "Normal text"),
        ("Multiple   spaces", "Multiple spaces"),
        ("Tab\ttext", "Tab text"),
        ("", ""),
        (None, ""),
        (123, "123"),
    ]

    all_passed = True
    for input_text, expected in test_cases:
        result = extractor._clean_cell_text(input_text)
        passed = result == expected
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: '{input_text}' -> '{result}' (expected: '{expected}')")
        if not passed:
            all_passed = False

    return all_passed


def test_confidence_calculation():
    """Test confidence score calculation"""
    print("\n" + "=" * 80)
    print("TEST 3: Confidence Calculation")
    print("=" * 80 + "\n")

    extractor = TableExtractor()

    test_cases = [
        {
            "name": "Full table",
            "cells": [["A", "B"], ["C", "D"]],
            "expected_range": (0.8, 1.0),
        },
        {
            "name": "Half empty",
            "cells": [["A", ""], ["", "D"]],
            "expected_range": (0.4, 0.6),
        },
        {
            "name": "All empty",
            "cells": [["", ""], ["", ""]],
            "expected_range": (0.0, 0.1),
        },
        {
            "name": "Large filled table",
            "cells": [
                ["H1", "H2", "H3"],
                ["A", "B", "C"],
                ["D", "E", "F"],
                ["G", "H", "I"],
            ],
            "expected_range": (0.9, 1.2),
        },
    ]

    all_passed = True
    for case in test_cases:
        confidence = extractor._calculate_confidence(case["cells"])
        min_conf, max_conf = case["expected_range"]
        passed = min_conf <= confidence <= max_conf
        status = "✓ PASS" if passed else "✗ FAIL"
        print(
            f"{status}: {case['name']}: confidence={confidence:.2f} (expected: {min_conf}-{max_conf})"
        )
        if not passed:
            all_passed = False

    return all_passed


def test_table_validation():
    """Test table validation logic"""
    print("\n" + "=" * 80)
    print("TEST 4: Table Validation")
    print("=" * 80 + "\n")

    extractor = TableExtractor(min_rows=2, min_cols=2)

    test_cases = [
        {
            "name": "Valid 3x3 table",
            "table": TableData(
                page_num=1,
                table_index=0,
                bbox=(0, 0, 100, 100),
                row_count=3,
                col_count=3,
                cells=[["A", "B", "C"], ["D", "E", "F"], ["G", "H", "I"]],
                markdown="test",
                confidence=0.9,
            ),
            "expected": True,
        },
        {
            "name": "Too few rows (1)",
            "table": TableData(
                page_num=1,
                table_index=0,
                bbox=(0, 0, 100, 100),
                row_count=1,
                col_count=3,
                cells=[["A", "B", "C"]],
                markdown="test",
                confidence=0.9,
            ),
            "expected": False,
        },
        {
            "name": "Too few cols (1)",
            "table": TableData(
                page_num=1,
                table_index=0,
                bbox=(0, 0, 100, 100),
                row_count=3,
                col_count=1,
                cells=[["A"], ["B"], ["C"]],
                markdown="test",
                confidence=0.9,
            ),
            "expected": False,
        },
        {
            "name": "Empty table",
            "table": TableData(
                page_num=1,
                table_index=0,
                bbox=(0, 0, 100, 100),
                row_count=2,
                col_count=2,
                cells=[["", ""], ["", ""]],
                markdown="test",
                confidence=0.0,
            ),
            "expected": False,
        },
    ]

    all_passed = True
    for case in test_cases:
        is_valid = extractor._is_valid_table(case["table"])
        passed = is_valid == case["expected"]
        status = "✓ PASS" if passed else "✗ FAIL"
        print(
            f"{status}: {case['name']}: valid={is_valid} (expected: {case['expected']})"
        )
        if not passed:
            all_passed = False

    return all_passed


def test_format_for_chunk():
    """Test table formatting for chunks"""
    print("\n" + "=" * 80)
    print("TEST 5: Format Table for Chunk")
    print("=" * 80 + "\n")

    extractor = TableExtractor()

    table = TableData(
        page_num=15,
        table_index=0,
        bbox=(100, 200, 400, 500),
        row_count=3,
        col_count=3,
        cells=[
            ["Size", "Torque", "Type"],
            ["M36", "1200", "Bolt"],
            ["M48", "2150", "Bolt"],
        ],
        markdown="| Size | Torque | Type |\n| --- | --- | --- |\n| M36 | 1200 | Bolt |\n| M48 | 2150 | Bolt |",
        confidence=0.95,
    )

    formatted = extractor.format_table_for_chunk(table)

    print("Formatted output:")
    print("─" * 80)
    print(formatted)
    print("─" * 80)

    # Verify
    checks = {
        "Has TABLE marker": "<!-- TABLE" in formatted,
        "Has END TABLE marker": "<!-- END TABLE" in formatted,
        "Has table metadata": "rows ×" in formatted and "cols" in formatted,
        "Has markdown table": "M48" in formatted and "2150" in formatted,
        "Has pipe symbols": "|" in formatted,
    }

    print("\nVerification:")
    all_passed = True
    for check_name, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
        if not result:
            all_passed = False

    return all_passed


if __name__ == "__main__":
    print("\n" + "█" * 80)
    print("TABLE EXTRACTOR UNIT TESTS")
    print("█" * 80)

    results = {}

    # Run all tests
    results["Test 1: Markdown Conversion"] = test_markdown_conversion()
    results["Test 2: Cell Cleaning"] = test_cell_cleaning()
    results["Test 3: Confidence Calculation"] = test_confidence_calculation()
    results["Test 4: Table Validation"] = test_table_validation()
    results["Test 5: Format for Chunk"] = test_format_for_chunk()

    # Final summary
    print("\n" + "█" * 80)
    print("FINAL SUMMARY")
    print("█" * 80)

    all_passed = True
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
        if not result:
            all_passed = False

    print("█" * 80)

    if all_passed:
        print("\n✓ ALL UNIT TESTS PASSED\n")
        sys.exit(0)
    else:
        print("\n✗ SOME TESTS FAILED\n")
        sys.exit(1)
