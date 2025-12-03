"""
Comprehensive Test Suite for Phase 1 RAG Pipeline

Runs all tests in sequence to validate the entire system:
1. Configuration tests
2. OCR tests
3. Tokenization tests
4. Page reranker tests
5. Snippet extractor tests
6. Citation retriever tests (end-to-end)

Usage:
    python run_all_tests.py
    python run_all_tests.py --verbose
    python run_all_tests.py --quick  # Skip slow tests
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Test scripts to run (in order)
TEST_SCRIPTS = [
    {
        "name": "Configuration",
        "script": "test_config.py",
        "description": "Validate centralized configuration",
        "critical": True,
        "quick": True,
    },
    {
        "name": "OCR (Cached Model)",
        "script": "test_ocr_cached.py",
        "description": "Verify OCR with cached recognition model",
        "critical": True,
        "quick": True,
    },
    {
        "name": "Tokenization Consistency",
        "script": "test_tokenization.py",
        "description": "Ensure BM25 tokenization consistency",
        "critical": True,
        "quick": True,
    },
    {
        "name": "Page Reranker",
        "script": "test_page_reranker.py",
        "description": "Test page-level BM25 ranking",
        "critical": True,
        "quick": False,  # Loads 4k page index
    },
    {
        "name": "Snippet Extractor",
        "script": "test_snippet_extractor.py",
        "description": "Test snippet extraction and highlighting",
        "critical": True,
        "quick": True,
    },
    {
        "name": "Citation Retriever (E2E)",
        "script": "test_citation_retriever.py",
        "description": "End-to-end RAG pipeline integration",
        "critical": True,
        "quick": False,  # Full pipeline test
    },
]


class TestResult:
    """Represents result of a test run"""

    def __init__(self, name: str, passed: bool, duration: float, output: str = ""):
        self.name = name
        self.passed = passed
        self.duration = duration
        self.output = output

    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        return f"{status} {self.name} ({self.duration:.2f}s)"


def run_test(test_script: dict, verbose: bool = False) -> TestResult:
    """
    Run a single test script

    Args:
        test_script: Test configuration dict
        verbose: Whether to show full output

    Returns:
        TestResult object
    """
    script_path = Path(__file__).parent / test_script["script"]

    if not script_path.exists():
        print(f"⚠ Test script not found: {test_script['script']}")
        return TestResult(test_script["name"], False, 0.0, "Script not found")

    print(f"\n{'='*80}")
    print(f"Running: {test_script['name']}")
    print(f"Description: {test_script['description']}")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        duration = time.time() - start_time
        passed = result.returncode == 0

        # Show output if verbose or if test failed
        if verbose or not passed:
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
        else:
            # Show summary only
            lines = result.stdout.strip().split("\n")
            # Show last few lines (usually summary)
            summary_lines = [
                l for l in lines if "PASS" in l or "FAIL" in l or "passed" in l
            ]
            if summary_lines:
                print("\n".join(summary_lines[-5:]))

        return TestResult(
            name=test_script["name"],
            passed=passed,
            duration=duration,
            output=result.stdout,
        )

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"✗ Test timed out after {duration:.1f}s")
        return TestResult(test_script["name"], False, duration, "Timeout")

    except Exception as e:
        duration = time.time() - start_time
        print(f"✗ Test raised exception: {e}")
        return TestResult(test_script["name"], False, duration, str(e))


def run_all_tests(verbose: bool = False, quick: bool = False) -> List[TestResult]:
    """
    Run all test scripts

    Args:
        verbose: Show full output for all tests
        quick: Skip slow tests

    Returns:
        List of TestResult objects
    """
    print("\n" + "=" * 80)
    print("PHASE 1 RAG PIPELINE - COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    # Filter tests if quick mode
    tests_to_run = TEST_SCRIPTS
    if quick:
        tests_to_run = [t for t in TEST_SCRIPTS if t.get("quick", True)]
        print(f"\n⚡ Quick mode: Running {len(tests_to_run)}/{len(TEST_SCRIPTS)} tests")

    print(f"\nTotal tests to run: {len(tests_to_run)}")

    results = []

    for i, test_script in enumerate(tests_to_run, 1):
        print(f"\n[{i}/{len(tests_to_run)}]", end=" ")
        result = run_test(test_script, verbose)
        results.append(result)

        # Stop on critical test failure
        if not result.passed and test_script.get("critical", False):
            print(f"\n{'='*80}")
            print(f"⚠ CRITICAL TEST FAILED: {result.name}")
            print(f"Stopping test suite execution.")
            print(f"{'='*80}")
            break

    return results


def print_summary(results: List[TestResult]):
    """Print test summary"""
    print("\n" + "=" * 80)
    print("TEST SUITE SUMMARY")
    print("=" * 80)

    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    total_duration = sum(r.duration for r in results)

    print(f"\nResults:")
    for result in results:
        print(f"  {result}")

    print(f"\n{'-'*80}")
    print(f"Total: {passed_count}/{len(results)} tests passed")
    print(f"Failed: {failed_count}")
    print(f"Duration: {total_duration:.2f}s")

    if passed_count == len(results):
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"Phase 1 RAG Pipeline is fully validated and production-ready.")
    else:
        print(f"\n⚠ {failed_count} test(s) failed")
        print(f"Please review failures above.")

    print("=" * 80)

    return passed_count == len(results)


def generate_test_report(results: List[TestResult], output_path: Path):
    """Generate detailed test report"""
    report = []
    report.append("# Phase 1 RAG Pipeline - Test Report")
    report.append(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\n## Summary")
    report.append(f"\n- Total Tests: {len(results)}")
    report.append(f"- Passed: {sum(1 for r in results if r.passed)}")
    report.append(f"- Failed: {sum(1 for r in results if not r.passed)}")
    report.append(f"- Total Duration: {sum(r.duration for r in results):.2f}s")

    report.append(f"\n## Test Results")
    for result in results:
        status = "✓ PASS" if result.passed else "✗ FAIL"
        report.append(f"\n### {status} {result.name}")
        report.append(f"- Duration: {result.duration:.2f}s")
        if not result.passed and result.output:
            report.append(f"\n```\n{result.output[:500]}\n```")

    # Write report
    output_path.write_text("\n".join(report), encoding="utf-8")
    print(f"\n📄 Test report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Run comprehensive test suite for Phase 1 RAG Pipeline"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show full output for all tests"
    )
    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Run only quick tests (skip slow ones)",
    )
    parser.add_argument(
        "--report",
        "-r",
        type=str,
        default="test_report.md",
        help="Path to save test report (default: test_report.md)",
    )

    args = parser.parse_args()

    # Run all tests
    start_time = time.time()
    results = run_all_tests(verbose=args.verbose, quick=args.quick)
    total_time = time.time() - start_time

    # Print summary
    all_passed = print_summary(results)

    # Generate report
    if args.report:
        report_path = Path(args.report)
        generate_test_report(results, report_path)

    print(f"\nTotal execution time: {total_time:.2f}s")

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
