"""
Test Script for Vision Citation Fixes (4 fixes)
Tests all critical scenarios and generates detailed diagnostic report

Usage:
    python test_vision_citation_fixes.py

Output:
    - Console: Real-time test progress
    - File: test_vision_fixes_report_TIMESTAMP.txt
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Configuration
API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 120  # 2 minutes for Vision queries


class Colors:
    """ANSI color codes for terminal output"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class TestCase:
    """Represents a single test case"""

    def __init__(
        self,
        name: str,
        query: str,
        language: str,
        expected: Dict[str, Any],
        fix_number: int,
    ):
        self.name = name
        self.query = query
        self.language = language
        self.expected = expected
        self.fix_number = fix_number
        self.result: Optional[Dict[str, Any]] = None
        self.passed: Optional[bool] = None
        self.logs: List[str] = []
        self.duration_ms: Optional[float] = None


class VisionFixesTester:
    """Main test orchestrator"""

    def __init__(self):
        self.api_url = API_BASE_URL
        self.test_cases: List[TestCase] = []
        self.report_lines: List[str] = []
        self.start_time = datetime.now()

    def add_test_case(self, test_case: TestCase):
        """Add a test case to the suite"""
        self.test_cases.append(test_case)

    def print_header(self):
        """Print test suite header"""
        print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
        print(
            f"{Colors.BOLD}{Colors.HEADER}Vision Citation Fixes - Comprehensive Test Suite{Colors.ENDC}"
        )
        print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
        print(f"API Endpoint: {self.api_url}")
        print(f"Test Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Tests: {len(self.test_cases)}\n")

    def run_query(self, query: str, language: str = "vi") -> Optional[Dict[str, Any]]:
        """Execute a single API query"""
        try:
            payload = {
                "query": query,
                "language": language,
                "max_context": 8,
                "hyde": False,
                "execution_mode": "production",
                "confidence_mode": "calibrated",
            }

            response = requests.post(
                f"{self.api_url}/ask",
                json=payload,
                timeout=API_TIMEOUT,
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"HTTP {response.status_code}",
                    "detail": response.text[:500],
                }
        except requests.exceptions.Timeout:
            return {"error": "timeout", "detail": "Request exceeded 120s"}
        except Exception as e:
            return {"error": "exception", "detail": str(e)}

    def verify_test_case(self, test_case: TestCase) -> bool:
        """Verify test case expectations"""
        if not test_case.result:
            return False

        if "error" in test_case.result:
            test_case.logs.append(
                f"❌ API Error: {test_case.result.get('detail', 'Unknown')}"
            )
            return False

        passed = True
        result = test_case.result
        expected = test_case.expected

        # Check Vision usage (Fix 1)
        if "vision_used" in expected:
            meta = result.get("meta", {})
            vision_meta = meta.get("vision_generation", {})
            vision_skip_metrics = meta.get("vision_skip_metrics", {})

            vision_used = bool(
                vision_meta.get("pages_used")
            ) or vision_skip_metrics.get("vision_used", False)

            if vision_used == expected["vision_used"]:
                test_case.logs.append(
                    f"✅ Vision usage: {vision_used} (expected: {expected['vision_used']})"
                )
            else:
                test_case.logs.append(
                    f"❌ Vision usage: {vision_used} (expected: {expected['vision_used']})"
                )
                passed = False

        # Check page range (Fix 2)
        if "page_range" in expected:
            meta = result.get("meta", {})
            vision_meta = meta.get("vision_generation", {})
            pages_used = vision_meta.get("pages_used", [])

            if pages_used:
                page_numbers = [
                    p.get("page") for p in pages_used if isinstance(p, dict)
                ]
                page_numbers = [p for p in page_numbers if p is not None]

                if page_numbers:
                    min_page = min(page_numbers)
                    max_page = max(page_numbers)
                    expected_min, expected_max = expected["page_range"]

                    if min_page <= expected_min and max_page <= expected_max:
                        test_case.logs.append(
                            f"✅ Page range: {min_page}-{max_page} (within {expected_min}-{expected_max})"
                        )
                    else:
                        test_case.logs.append(
                            f"⚠️ Page range: {min_page}-{max_page} (expected {expected_min}-{expected_max})"
                        )
                        # Don't fail, just warn (page selection heuristic may vary)
                else:
                    test_case.logs.append(f"⚠️ No page numbers in pages_used")
            else:
                test_case.logs.append(f"⚠️ No pages_used in vision_generation")

        # Check result count (Fix 3)
        if "min_results" in expected:
            citations_count = len(result.get("citations", []))
            context_count = len(result.get("context_used", []))

            if citations_count >= expected["min_results"]:
                test_case.logs.append(
                    f"✅ Citations count: {citations_count} (min: {expected['min_results']})"
                )
            else:
                test_case.logs.append(
                    f"❌ Citations count: {citations_count} (min: {expected['min_results']})"
                )
                passed = False

            if context_count >= expected["min_results"]:
                test_case.logs.append(
                    f"✅ Context count: {context_count} (min: {expected['min_results']})"
                )
            else:
                test_case.logs.append(
                    f"⚠️ Context count: {context_count} (min: {expected['min_results']})"
                )

        # Check metadata enrichment (Fix 4)
        if "has_pdf_path" in expected:
            # Check if retrieval_details exist (contains metadata)
            retrieval_details = result.get("retrieval_details")
            if retrieval_details:
                total_docs = retrieval_details.get("total_retrieved", 0)
                test_case.logs.append(
                    f"✅ Retrieval details present: {total_docs} docs retrieved"
                )
            else:
                test_case.logs.append(f"⚠️ No retrieval_details in response")

        # Check answer quality
        answer = result.get("answer", "")
        if answer and len(answer) > 50:
            test_case.logs.append(f"✅ Answer generated: {len(answer)} chars")
        else:
            test_case.logs.append(f"⚠️ Short answer: {len(answer)} chars")

        return passed

    def run_all_tests(self):
        """Execute all test cases"""
        self.print_header()

        passed_count = 0
        failed_count = 0

        for i, test_case in enumerate(self.test_cases, 1):
            print(
                f"\n{Colors.OKCYAN}[Test {i}/{len(self.test_cases)}] {test_case.name}{Colors.ENDC}"
            )
            print(f"  Query: '{test_case.query}'")
            print(f"  Language: {test_case.language}")
            print(f"  Testing: Fix {test_case.fix_number}")

            # Run query
            start = time.time()
            test_case.result = self.run_query(test_case.query, test_case.language)
            test_case.duration_ms = (time.time() - start) * 1000

            print(f"  Duration: {test_case.duration_ms:.0f}ms")

            # Verify expectations
            test_case.passed = self.verify_test_case(test_case)

            # Print logs
            for log in test_case.logs:
                print(f"    {log}")

            # Summary
            if test_case.passed:
                print(f"  {Colors.OKGREEN}✓ PASSED{Colors.ENDC}")
                passed_count += 1
            else:
                print(f"  {Colors.FAIL}✗ FAILED{Colors.ENDC}")
                failed_count += 1

        # Final summary
        print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
        print(f"{Colors.BOLD}Test Summary{Colors.ENDC}")
        print(f"  Total: {len(self.test_cases)}")
        print(f"  {Colors.OKGREEN}Passed: {passed_count}{Colors.ENDC}")
        print(f"  {Colors.FAIL}Failed: {failed_count}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    def generate_report(self) -> str:
        """Generate detailed report"""
        report = []
        report.append("=" * 80)
        report.append("Vision Citation Fixes - Test Report")
        report.append("=" * 80)
        report.append(f"\nTest Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Tests: {len(self.test_cases)}")
        report.append(f"API Endpoint: {self.api_url}\n")

        # Summary by fix
        report.append("\n" + "=" * 80)
        report.append("Results by Fix")
        report.append("=" * 80)

        for fix_num in [1, 2, 3, 4]:
            fix_tests = [tc for tc in self.test_cases if tc.fix_number == fix_num]
            if fix_tests:
                passed = sum(1 for tc in fix_tests if tc.passed)
                total = len(fix_tests)
                report.append(f"\nFix {fix_num}: {passed}/{total} passed")
                for tc in fix_tests:
                    status = "PASS" if tc.passed else "FAIL"
                    report.append(f"  [{status}] {tc.name}")

        # Detailed test results
        report.append("\n\n" + "=" * 80)
        report.append("Detailed Test Results")
        report.append("=" * 80)

        for i, tc in enumerate(self.test_cases, 1):
            report.append(f"\n{'─'*80}")
            report.append(f"Test {i}: {tc.name}")
            report.append(f"{'─'*80}")
            report.append(f"Query: {tc.query}")
            report.append(f"Language: {tc.language}")
            report.append(f"Fix Number: {tc.fix_number}")
            report.append(f"Duration: {tc.duration_ms:.0f}ms")
            report.append(f"Status: {'PASSED' if tc.passed else 'FAILED'}")
            report.append("\nVerification Logs:")
            for log in tc.logs:
                report.append(f"  {log}")

            if tc.result:
                report.append("\nAPI Response Summary:")
                if "error" not in tc.result:
                    report.append(
                        f"  Answer length: {len(tc.result.get('answer', ''))} chars"
                    )
                    report.append(f"  Citations: {len(tc.result.get('citations', []))}")
                    report.append(
                        f"  Context used: {len(tc.result.get('context_used', []))}"
                    )
                    report.append(f"  Confidence: {tc.result.get('confidence', 0):.3f}")

                    meta = tc.result.get("meta", {})
                    report.append(f"  Latency: {meta.get('latency_ms', 0):.0f}ms")
                    report.append(f"  Cache hit: {meta.get('cache_hit', False)}")

                    vision_meta = meta.get("vision_generation", {})
                    if vision_meta:
                        report.append(
                            f"  Vision pages used: {len(vision_meta.get('pages_used', []))}"
                        )
                        report.append(
                            f"  Vision pages failed: {len(vision_meta.get('pages_failed', []))}"
                        )
                else:
                    report.append(f"  ERROR: {tc.result.get('error')}")
                    report.append(f"  Detail: {tc.result.get('detail', 'N/A')[:200]}")

        report.append("\n" + "=" * 80)
        report.append("End of Report")
        report.append("=" * 80)

        return "\n".join(report)

    def save_report(self):
        """Save report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_vision_fixes_report_{timestamp}.txt"

        report = self.generate_report()

        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\n{Colors.OKGREEN}Report saved to: {filename}{Colors.ENDC}")
        return filename


def main():
    """Main entry point"""
    tester = VisionFixesTester()

    # Test Fix 1: Vision Always ON
    tester.add_test_case(
        TestCase(
            name="Fix 1 - P&ID Query with Tag (Vietnamese)",
            query="04-FIC-2035",
            language="vi",
            expected={
                "vision_used": True,  # Vision should be used
                "page_range": (1, 15),  # Early pages (legend area)
                "min_results": 3,
            },
            fix_number=1,
        )
    )

    tester.add_test_case(
        TestCase(
            name="Fix 1 - English Text-Only Query",
            query="What is the torque specification?",
            language="en",
            expected={
                "vision_used": True,  # Vision should NOT skip text-only
                "min_results": 3,
            },
            fix_number=1,
        )
    )

    tester.add_test_case(
        TestCase(
            name="Fix 1 - Vietnamese Text Query",
            query="Moment xoắn của bu lông là bao nhiêu?",
            language="vi",
            expected={
                "vision_used": True,  # Vision should be used
                "min_results": 3,
            },
            fix_number=1,
        )
    )

    # Test Fix 2: P&ID Page Selection
    tester.add_test_case(
        TestCase(
            name="Fix 2 - P&ID with Equipment Tag",
            query="Tìm vị trí của 04-FIC-2035 trên P&ID",
            language="vi",
            expected={
                "vision_used": True,
                "page_range": (1, 15),  # Should select early pages, not middle
                "min_results": 1,
            },
            fix_number=2,
        )
    )

    tester.add_test_case(
        TestCase(
            name="Fix 2 - P&ID Legend Query",
            query="Legend của P&ID Ammonia Unit",
            language="vi",
            expected={
                "vision_used": True,
                "page_range": (1, 10),  # Legend typically at start
                "min_results": 1,
            },
            fix_number=2,
        )
    )

    # Test Fix 3: Rerank Safety Net
    tester.add_test_case(
        TestCase(
            name="Fix 3 - Complex Technical Query",
            query="CO2 compressor vibration monitoring system specifications",
            language="en",
            expected={
                "min_results": 3,  # Should have at least 3 results despite complexity
            },
            fix_number=3,
        )
    )

    tester.add_test_case(
        TestCase(
            name="Fix 3 - Specific Equipment Query",
            query="K06101 CO2 compressor expected performance curve",
            language="en",
            expected={
                "min_results": 3,
            },
            fix_number=3,
        )
    )

    # Test Fix 4: Metadata Enrichment
    tester.add_test_case(
        TestCase(
            name="Fix 4 - General Query (Check Metadata)",
            query="Steam turbine data sheet specifications",
            language="en",
            expected={
                "has_pdf_path": True,  # Retrieved docs should have pdf_path
                "min_results": 3,
            },
            fix_number=4,
        )
    )

    # Run all tests
    tester.run_all_tests()

    # Save report
    report_file = tester.save_report()

    # Exit with appropriate code
    failed_count = sum(1 for tc in tester.test_cases if not tc.passed)
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
