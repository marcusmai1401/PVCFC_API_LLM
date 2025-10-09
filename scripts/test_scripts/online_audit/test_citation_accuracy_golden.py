"""
Golden Citation Accuracy Test

Tests citation accuracy using 5 verified Q&A pairs with known ground truth.
Calls /api/ask endpoint with vision on/off variants and compares results.

Usage:
    python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py

    Optional arguments:
    --api-url http://localhost:8000  (default)
    --output-dir reports/test_results  (default)
    --vision-only  (test only with vision enabled)
    --no-vision  (test only with vision disabled)
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from loguru import logger

# Add project root to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))


class CitationAccuracyTester:
    """Test citation accuracy against golden dataset"""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        output_dir: str = "reports/test_results",
    ):
        self.api_url = api_url.rstrip("/")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load golden dataset
        dataset_path = Path(__file__).parent / "golden_citation_dataset.json"
        with open(dataset_path, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)

        self.results = []
        self.summary = {
            "total_tests": 0,
            "correct_doc_and_page": 0,
            "correct_doc_wrong_page": 0,
            "wrong_doc": 0,
            "no_answer": 0,
            "page_off_by_1": 0,
            "page_off_by_2_plus": 0,
            "vision_enabled_tests": 0,
            "vision_disabled_tests": 0,
        }

    def check_api_health(self) -> bool:
        """Verify API server is running"""
        try:
            # Try /index-stats endpoint
            response = requests.get(f"{self.api_url}/index-stats", timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ API server is healthy at {self.api_url}")
                logger.info(
                    f"  BM25: {data['bm25']['chunk_count']} chunks, FAISS: {data['faiss']['vector_count']} vectors"
                )
                return True
            else:
                logger.error(f"✗ API health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ Cannot connect to API at {self.api_url}: {e}")
            return False

    def call_ask_api(
        self, query: str, language: str, enable_vision: bool, timeout: int = 120
    ) -> Optional[Dict[str, Any]]:
        """Call /api/ask endpoint"""
        payload = {
            "query": query,
            "language": language,
            "enable_vision_generation": enable_vision,
        }

        try:
            logger.info(f"Calling /ask/ (vision={enable_vision}, lang={language})")
            response = requests.post(
                f"{self.api_url}/ask/", json=payload, timeout=timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API error {response.status_code}: {response.text[:500]}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"API timeout after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return None

    def extract_doc_id_from_citation(self, citation: Dict[str, Any]) -> Optional[str]:
        """Extract doc_id from citation"""
        return citation.get("doc_id")

    def extract_page_from_citation(self, citation: Dict[str, Any]) -> Optional[int]:
        """Extract page number from citation"""
        return citation.get("page")

    def match_doc_id_pattern(self, doc_id: str, pattern: str) -> bool:
        """Check if doc_id matches pattern (regex)"""
        if not doc_id or not pattern:
            return False
        try:
            return bool(re.search(pattern, doc_id, re.IGNORECASE))
        except:
            return False

    def match_file_name(self, doc_id: str, file_name: str) -> bool:
        """Check if doc_id contains file name components"""
        if not doc_id or not file_name:
            return False

        # Extract meaningful parts from file name
        # e.g., "003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf"
        # -> ["3N4", "S4274345", "Compressor"]
        file_parts = re.findall(r"[A-Z0-9]{3,}", file_name.upper())

        doc_id_upper = doc_id.upper()
        matches = sum(1 for part in file_parts if part in doc_id_upper)

        # Require at least 2 significant matches
        return matches >= 2

    def compare_with_ground_truth(
        self, question_id: str, ground_truth: Dict[str, Any], response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare API response with ground truth"""
        comparison = {
            "question_id": question_id,
            "ground_truth_page": ground_truth["page"],
            "ground_truth_file": ground_truth["file_name"],
            "doc_match": False,
            "page_match": "no_citation",
            "page_distance": None,
            "citations_found": 0,
            "matched_citations": [],
            "mismatched_citations": [],
            "answer_length": 0,
            "has_keywords": False,
        }

        # Check answer
        answer = response.get("answer", "")
        comparison["answer_length"] = len(answer)

        # Check if answer is empty or generic
        if len(answer) < 50:
            comparison["page_match"] = "no_answer"
            return comparison

        # Check citations
        citations = response.get("citations", [])
        comparison["citations_found"] = len(citations)

        if not citations:
            comparison["page_match"] = "no_citation"
            return comparison

        # Analyze each citation
        for cit in citations:
            doc_id = self.extract_doc_id_from_citation(cit)
            page = self.extract_page_from_citation(cit)

            # Check doc match
            doc_matches = False
            if doc_id:
                # Try pattern match first
                if "doc_id_pattern" in ground_truth:
                    doc_matches = self.match_doc_id_pattern(
                        doc_id, ground_truth["doc_id_pattern"]
                    )

                # Fallback to file name match
                if not doc_matches:
                    doc_matches = self.match_file_name(
                        doc_id, ground_truth["file_name"]
                    )

            if doc_matches:
                comparison["doc_match"] = True

                # Check page match
                if page is not None:
                    gt_page = ground_truth["page"]
                    page_diff = abs(page - gt_page)

                    if page == gt_page:
                        comparison["page_match"] = "exact"
                        comparison["page_distance"] = 0
                    elif page_diff == 1:
                        comparison["page_match"] = "off_by_1"
                        comparison["page_distance"] = 1
                    elif page_diff <= 3:
                        comparison["page_match"] = "off_by_2_to_3"
                        comparison["page_distance"] = page_diff
                    else:
                        comparison["page_match"] = "off_by_many"
                        comparison["page_distance"] = page_diff

                    comparison["matched_citations"].append(
                        {
                            "doc_id": doc_id,
                            "page": page,
                            "page_diff": page_diff,
                            "pdf_path": cit.get("pdf_path"),
                        }
                    )
                else:
                    comparison["page_match"] = "doc_match_no_page"
            else:
                comparison["mismatched_citations"].append(
                    {
                        "doc_id": doc_id,
                        "page": page,
                    }
                )

        return comparison

    def test_single_question(
        self, question: Dict[str, Any], enable_vision: bool
    ) -> Dict[str, Any]:
        """Test a single question with specified vision setting"""
        question_id = question["id"]
        query = question["query"]
        language = question["language"]
        ground_truth = question["ground_truth"]

        logger.info(f"\n{'='*80}")
        logger.info(f"Testing: {question_id} (vision={enable_vision})")
        logger.info(f"Query: {query[:100]}...")
        logger.info(
            f"Expected: {ground_truth['file_name']}, page {ground_truth['page']}"
        )

        # Call API
        start_time = time.time()
        response = self.call_ask_api(query, language, enable_vision)
        elapsed_ms = (time.time() - start_time) * 1000

        if not response:
            logger.error("✗ API call failed")
            result = {
                "question_id": question_id,
                "query": query,
                "language": language,
                "vision_enabled": enable_vision,
                "success": False,
                "error": "API call failed",
                "elapsed_ms": elapsed_ms,
            }
            self.summary["no_answer"] += 1
            return result

        # Compare with ground truth
        comparison = self.compare_with_ground_truth(question_id, ground_truth, response)

        # Determine verdict
        if comparison["page_match"] == "exact":
            verdict = "✓ PASS (exact page)"
            self.summary["correct_doc_and_page"] += 1
        elif comparison["page_match"] == "off_by_1":
            verdict = "~ PARTIAL (page off by 1)"
            self.summary["correct_doc_wrong_page"] += 1
            self.summary["page_off_by_1"] += 1
        elif comparison["doc_match"]:
            verdict = f"✗ FAIL (doc OK, page wrong: {comparison['page_match']})"
            self.summary["correct_doc_wrong_page"] += 1
            if comparison["page_distance"] and comparison["page_distance"] >= 2:
                self.summary["page_off_by_2_plus"] += 1
        else:
            verdict = "✗✗ FAIL (wrong doc)"
            self.summary["wrong_doc"] += 1

        logger.info(f"Result: {verdict}")
        logger.info(f"Citations found: {comparison['citations_found']}")
        if comparison["matched_citations"]:
            for mc in comparison["matched_citations"]:
                logger.info(
                    f"  - Matched: {mc['doc_id']}, page {mc['page']} (diff: {mc['page_diff']})"
                )

        # Build result
        result = {
            "question_id": question_id,
            "query": query,
            "language": language,
            "vision_enabled": enable_vision,
            "success": True,
            "elapsed_ms": elapsed_ms,
            "verdict": verdict,
            "comparison": comparison,
            "response": response,  # Full response for deep analysis
        }

        return result

    def run_tests(self, vision_only: bool = False, no_vision: bool = False):
        """Run all tests"""
        logger.info(f"Starting Golden Citation Accuracy Test")
        logger.info(f"Dataset: {len(self.dataset['questions'])} questions")

        # Check API health
        if not self.check_api_health():
            logger.error("Aborting: API server not available")
            return

        # Determine test variants
        variants = []
        if not no_vision:
            variants.append(True)  # vision on
        if not vision_only:
            variants.append(False)  # vision off

        # Run tests
        for question in self.dataset["questions"]:
            for enable_vision in variants:
                result = self.test_single_question(question, enable_vision)
                self.results.append(result)
                self.summary["total_tests"] += 1

                if enable_vision:
                    self.summary["vision_enabled_tests"] += 1
                else:
                    self.summary["vision_disabled_tests"] += 1

                # Small delay between requests
                time.sleep(0.5)

        # Calculate summary statistics
        if self.summary["total_tests"] > 0:
            self.summary["pass_rate"] = (
                self.summary["correct_doc_and_page"] / self.summary["total_tests"]
            )
            self.summary["doc_match_rate"] = (
                self.summary["correct_doc_and_page"]
                + self.summary["correct_doc_wrong_page"]
            ) / self.summary["total_tests"]

        logger.info(f"\n{'='*80}")
        logger.info("Test Summary:")
        logger.info(f"  Total tests: {self.summary['total_tests']}")
        logger.info(f"  ✓ Correct doc+page: {self.summary['correct_doc_and_page']}")
        logger.info(
            f"  ~ Correct doc, wrong page: {self.summary['correct_doc_wrong_page']}"
        )
        logger.info(f"  ✗ Wrong doc: {self.summary['wrong_doc']}")
        logger.info(f"  ✗ No answer/citation: {self.summary['no_answer']}")
        logger.info(f"  Pass rate: {self.summary.get('pass_rate', 0):.1%}")
        logger.info(f"  Doc match rate: {self.summary.get('doc_match_rate', 0):.1%}")

    def save_results(self):
        """Save results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"citation_accuracy_golden_{timestamp}.json"

        output = {
            "test_name": "golden_citation_accuracy",
            "timestamp": timestamp,
            "api_url": self.api_url,
            "dataset": self.dataset["dataset_name"],
            "summary": self.summary,
            "results": self.results,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"\n✓ Results saved to: {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(description="Golden Citation Accuracy Test")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/test_results",
        help="Output directory for results (default: reports/test_results)",
    )
    parser.add_argument(
        "--vision-only", action="store_true", help="Test only with vision enabled"
    )
    parser.add_argument(
        "--no-vision", action="store_true", help="Test only with vision disabled"
    )

    args = parser.parse_args()

    # Configure logger
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )

    # Run tests
    tester = CitationAccuracyTester(api_url=args.api_url, output_dir=args.output_dir)
    tester.run_tests(vision_only=args.vision_only, no_vision=args.no_vision)
    output_file = tester.save_results()

    # Exit code based on pass rate
    pass_rate = tester.summary.get("pass_rate", 0)
    if pass_rate >= 0.6:
        logger.info(f"\n✓ Test PASSED (pass rate: {pass_rate:.1%} >= 60%)")
        sys.exit(0)
    else:
        logger.warning(f"\n✗ Test FAILED (pass rate: {pass_rate:.1%} < 60%)")
        sys.exit(1)


if __name__ == "__main__":
    main()
