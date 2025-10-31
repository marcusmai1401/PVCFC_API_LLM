"""
Comprehensive Integration Test for Query Classification & RAG Accuracy
Tests 4 real-world questions with expected answers and citations.
Uses LLM-as-judge for semantic matching.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.llm_client import get_llm_client


class TestCase:
    """Represents a single test case"""

    def __init__(
        self,
        id: str,
        question: str,
        language: str,
        expected_answer: str,
        expected_source: str,
        expected_doc_name: str,
        expected_query_type: str = "auto",
    ):
        self.id = id
        self.question = question
        self.language = language
        self.expected_answer = expected_answer
        self.expected_source = expected_source
        self.expected_doc_name = expected_doc_name
        self.expected_query_type = expected_query_type


class TestResult:
    """Represents test execution result"""

    def __init__(self, test_case: TestCase):
        self.test_case = test_case
        self.actual_answer: Optional[str] = None
        self.actual_citations: List[Dict] = []
        self.actual_query_classification: Optional[Dict] = None
        self.response_time_ms: Optional[float] = None
        self.error: Optional[str] = None

        # Evaluation results
        self.answer_correct: Optional[bool] = None
        self.answer_score: Optional[float] = None
        self.answer_reasoning: Optional[str] = None
        self.citation_correct: Optional[bool] = None
        self.citation_score: Optional[float] = None
        self.classification_correct: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "test_id": self.test_case.id,
            "question": self.test_case.question,
            "language": self.test_case.language,
            "expected": {
                "answer": self.test_case.expected_answer,
                "source": self.test_case.expected_source,
                "doc_name": self.test_case.expected_doc_name,
                "query_type": self.test_case.expected_query_type,
            },
            "actual": {
                "answer": self.actual_answer,
                "citations": self.actual_citations,
                "query_classification": self.actual_query_classification,
            },
            "evaluation": {
                "answer_correct": self.answer_correct,
                "answer_score": self.answer_score,
                "answer_reasoning": self.answer_reasoning,
                "citation_correct": self.citation_correct,
                "citation_score": self.citation_score,
                "classification_correct": self.classification_correct,
            },
            "response_time_ms": self.response_time_ms,
            "error": self.error,
        }


class RAGTester:
    """Test runner for RAG API"""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.llm_judge = get_llm_client(tier="heavy")

    def create_test_cases(self) -> List[TestCase]:
        """Create test cases from requirements"""
        return [
            # Test 1: Vietnamese - P&ID query with equipment tag
            TestCase(
                id="Q1_VN_PID",
                question="Trong Urea Unit, đối với turbine hơi dẫn động máy nén CO₂ (mã KT06101), điều kiện hơi vào turbine ở chế độ normal là bao nhiêu (áp suất và nhiệt độ)?",
                language="vi",
                expected_answer="39 bar(a) and 370 °C",
                expected_source='Data sheet shows "Steam Inlet 39 Bar a; 370 °C" on PDF page 8/8 (Rev. 0E)',
                expected_doc_name="Data Sheet for CO2 Compressor Steam Turbine.rev0E",
                expected_query_type="pid",
            ),
            # Test 2: English - Technical doc query
            TestCase(
                id="Q2_EN_TECH",
                question="According to the operation and maintenance manual for the HCD025 gear unit, what are the specified setpoints for lubricating oil pressure for normal operation, alarm, and shutdown (trip)?",
                language="en",
                expected_answer="Normal operation: 2.0 barG, Alarm: 1.2 barG, Trip: 0.8 barG",
                expected_source='PDF page 18, table in section (a) "Lubricating oil pressure"',
                expected_doc_name="092_3N4-S4279947_Rev.1 Operation and maintenance manual of gear.pdf",
                expected_query_type="technical_doc",
            ),
            # Test 3: Vietnamese - Technical doc query
            TestCase(
                id="Q3_VN_TECH",
                question="Theo biểu đồ hiệu suất dự kiến của máy nén CO2, tốc độ vận hành 100% của máy nén là bao nhiêu vòng/phút (RPM)?",
                language="vi",
                expected_answer="7800 / 13277 RPM",
                expected_source="PDF page 2, upper right corner of the performance chart",
                expected_doc_name="003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf",
                expected_query_type="technical_doc",
            ),
            # Test 4: English - P&ID query with tag
            TestCase(
                id="Q4_EN_PID",
                question="I need to configure the alarm settings for the temperature monitoring system on the steam turbine. According to the instrument list, there is a sensor with Tag No. 06-TE-0256 A/B. Based on the provided documentation, what is the measurement point (i.e., the component being monitored) for this tag number, and what is its corresponding high-temperature alarm (A) setpoint?",
                language="en",
                expected_answer="Measurement Point: Rear Journal Bearing, High-Temperature Alarm Setpoint: 105 °C",
                expected_source="Measurement point on page 4 of 6, alarm setpoint on page 6 of 6",
                expected_doc_name="instrument list",  # User doesn't have specific doc name
                expected_query_type="pid",
            ),
        ]

    def run_query(self, test_case: TestCase) -> TestResult:
        """Execute a single test query"""
        result = TestResult(test_case)

        try:
            # Call API
            start_time = time.time()

            # Build request - do NOT pass query_type to test auto-classification
            request_body = {
                "query": test_case.question,
                "language": test_case.language,
                "hyde": True,
                "max_context": 8,
                "enable_vision_generation": True,
                # NOTE: query_type not passed - let API auto-classify!
            }

            response = requests.post(
                f"{self.api_base_url}/ask",
                json=request_body,
                timeout=120,
            )
            result.response_time_ms = (time.time() - start_time) * 1000

            if response.status_code != 200:
                result.error = f"API error: {response.status_code} - {response.text}"
                return result

            data = response.json()

            # Extract results
            result.actual_answer = data.get("answer", "")
            result.actual_citations = data.get("citations", [])

            # Extract query classification from meta
            meta = data.get("meta", {})
            if "query_classification" in meta:
                result.actual_query_classification = meta["query_classification"]

            logger.info(
                f"✓ Query executed: {test_case.id} ({result.response_time_ms:.0f}ms)"
            )

        except Exception as e:
            result.error = f"Exception: {str(e)}"
            logger.error(f"✗ Query failed: {test_case.id} - {e}")

        return result

    def evaluate_answer(self, result: TestResult) -> None:
        """Use LLM-as-judge to evaluate answer quality"""
        if result.error or not result.actual_answer:
            result.answer_correct = False
            result.answer_score = 0.0
            result.answer_reasoning = "No answer generated"
            return

        prompt = f"""You are an expert judge evaluating RAG system answers.

**Question:** {result.test_case.question}

**Expected Answer:** {result.test_case.expected_answer}

**Actual Answer:** {result.actual_answer}

**Task:** Evaluate if the actual answer contains the key information from the expected answer.
The actual answer may be longer and in different wording, but must include the core facts.

**Output JSON:**
{{
    "correct": true/false,
    "score": 0.0-1.0,
    "reasoning": "brief explanation"
}}
"""

        try:
            response = self.llm_judge.generate(
                prompt=prompt,
                system_prompt="You are a precise evaluator. Output only valid JSON.",
                temperature=0.0,
                max_tokens=300,
            )

            # Parse JSON response
            content = response.content.strip()
            # Try to extract JSON if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            evaluation = json.loads(content)

            result.answer_correct = evaluation.get("correct", False)
            result.answer_score = evaluation.get("score", 0.0)
            result.answer_reasoning = evaluation.get("reasoning", "")

        except Exception as e:
            logger.warning(f"LLM judge failed for {result.test_case.id}: {e}")
            # Fallback: smarter matching with number extraction
            expected_lower = result.test_case.expected_answer.lower()
            actual_lower = result.actual_answer.lower()

            # Extract numbers from both answers
            import re

            expected_numbers = set(re.findall(r"\d+\.?\d*", expected_lower))
            actual_numbers = set(re.findall(r"\d+\.?\d*", actual_lower))

            # Check number overlap
            number_matches = len(expected_numbers & actual_numbers)
            number_total = len(expected_numbers)

            # Check keyword overlap (non-numbers)
            expected_keywords = [
                w
                for w in expected_lower.split()
                if not any(c.isdigit() for c in w) and len(w) > 2
            ]
            keyword_matches = sum(1 for kw in expected_keywords if kw in actual_lower)

            # Combined score: 70% numbers, 30% keywords
            number_score = number_matches / number_total if number_total > 0 else 0.0
            keyword_score = (
                keyword_matches / len(expected_keywords) if expected_keywords else 0.0
            )
            result.answer_score = 0.7 * number_score + 0.3 * keyword_score
            result.answer_correct = result.answer_score > 0.6
            result.answer_reasoning = f"Fallback: {number_matches}/{number_total} numbers, {keyword_matches}/{len(expected_keywords)} keywords"

    def evaluate_citations(self, result: TestResult) -> None:
        """Evaluate if citations reference expected documents"""
        if result.error or not result.actual_citations:
            result.citation_correct = False
            result.citation_score = 0.0
            return

        # Check if any citation matches expected doc name (fuzzy)
        expected_doc_lower = result.test_case.expected_doc_name.lower()
        matching_citations = []

        for citation in result.actual_citations:
            doc_id = citation.get("doc_id", "").lower()
            source = citation.get("source", "").lower()

            # Fuzzy match: check if key parts of expected doc name appear
            if any(
                part in doc_id or part in source
                for part in expected_doc_lower.split()
                if len(part) > 3
            ):
                matching_citations.append(citation)

        result.citation_correct = len(matching_citations) > 0
        result.citation_score = min(
            1.0, len(matching_citations) / 2.0
        )  # Up to 2 citations = 1.0

    def evaluate_classification(self, result: TestResult) -> None:
        """Evaluate if query classification is correct"""
        if not result.actual_query_classification:
            result.classification_correct = None
            return

        actual_type = result.actual_query_classification.get("type", "auto")
        expected_type = result.test_case.expected_query_type

        # Accept "auto" or matching specific type
        result.classification_correct = (
            actual_type == expected_type or expected_type == "auto"
        )

    def run_all_tests(self) -> List[TestResult]:
        """Run all test cases"""
        test_cases = self.create_test_cases()
        results = []

        logger.info(f"\n{'='*60}")
        logger.info(f"Starting RAG Accuracy Test Suite ({len(test_cases)} tests)")
        logger.info(f"{'='*60}\n")

        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"[{i}/{len(test_cases)}] Running: {test_case.id}")
            logger.info(f"  Language: {test_case.language}")
            logger.info(f"  Question: {test_case.question[:80]}...")

            # Run query
            result = self.run_query(test_case)

            # Evaluate
            if not result.error:
                self.evaluate_answer(result)
                self.evaluate_citations(result)
                self.evaluate_classification(result)

            results.append(result)

            # Print immediate result
            if result.error:
                logger.error(f"  ✗ FAILED: {result.error}\n")
            else:
                logger.info(
                    f"  Answer Score: {result.answer_score:.2f} - {'✓ PASS' if result.answer_correct else '✗ FAIL'}"
                )
                logger.info(
                    f"  Citation Score: {result.citation_score:.2f} - {'✓ MATCH' if result.citation_correct else '✗ NO MATCH'}"
                )
                logger.info(
                    f"  Classification: {result.actual_query_classification.get('type') if result.actual_query_classification else 'N/A'}\n"
                )

            time.sleep(1)  # Be nice to API

        return results

    def generate_report(self, results: List[TestResult]) -> Dict[str, Any]:
        """Generate summary report"""
        total = len(results)
        successful = sum(1 for r in results if not r.error)
        answer_correct = sum(1 for r in results if r.answer_correct)
        citation_correct = sum(1 for r in results if r.citation_correct)
        classification_correct = sum(1 for r in results if r.classification_correct)

        avg_answer_score = (
            sum(r.answer_score or 0.0 for r in results) / total if total > 0 else 0.0
        )
        avg_citation_score = (
            sum(r.citation_score or 0.0 for r in results) / total if total > 0 else 0.0
        )
        avg_response_time = (
            sum(r.response_time_ms or 0.0 for r in results) / total
            if total > 0
            else 0.0
        )

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total,
                "successful_queries": successful,
                "answer_accuracy": answer_correct / total if total > 0 else 0.0,
                "citation_accuracy": citation_correct / total if total > 0 else 0.0,
                "classification_accuracy": classification_correct / total
                if total > 0
                else 0.0,
                "avg_answer_score": avg_answer_score,
                "avg_citation_score": avg_citation_score,
                "avg_response_time_ms": avg_response_time,
            },
            "results": [r.to_dict() for r in results],
        }

        return report

    def print_summary(self, report: Dict[str, Any]) -> None:
        """Print human-readable summary"""
        summary = report["summary"]

        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests:              {summary['total_tests']}")
        print(f"Successful Queries:       {summary['successful_queries']}")
        print(
            f"Answer Accuracy:          {summary['answer_accuracy']:.1%} ({int(summary['answer_accuracy'] * summary['total_tests'])}/{summary['total_tests']})"
        )
        print(
            f"Citation Accuracy:        {summary['citation_accuracy']:.1%} ({int(summary['citation_accuracy'] * summary['total_tests'])}/{summary['total_tests']})"
        )
        print(
            f"Classification Accuracy:  {summary['classification_accuracy']:.1%} ({int(summary['classification_accuracy'] * summary['total_tests'])}/{summary['total_tests']})"
        )
        print(f"Avg Answer Score:         {summary['avg_answer_score']:.2f}/1.00")
        print(f"Avg Citation Score:       {summary['avg_citation_score']:.2f}/1.00")
        print(f"Avg Response Time:        {summary['avg_response_time_ms']:.0f}ms")
        print(f"{'='*60}\n")

        # Detailed results
        print("DETAILED RESULTS:")
        print(f"{'='*60}")
        for result_dict in report["results"]:
            test_id = result_dict["test_id"]
            lang = result_dict["language"]
            eval_data = result_dict["evaluation"]

            status = "✓ PASS" if eval_data["answer_correct"] else "✗ FAIL"
            print(f"\n[{test_id}] ({lang.upper()}) - {status}")
            answer_score_str = (
                f"{eval_data['answer_score']:.2f}"
                if eval_data["answer_score"] is not None
                else "N/A"
            )
            print(f"  Answer Score: {answer_score_str}")
            print(f"  Reasoning: {eval_data['answer_reasoning'] or 'Error occurred'}")
            print(f"  Citation Match: {'✓' if eval_data['citation_correct'] else '✗'}")
            print(
                f"  Classification: {'✓' if eval_data['classification_correct'] else '✗' if eval_data['classification_correct'] is not None else 'N/A'}"
            )

        print(f"\n{'='*60}\n")


def main():
    """Main test execution"""
    # Configure logger
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="<level>{message}</level>")

    # Check API availability
    api_url = "http://localhost:8000"
    try:
        response = requests.get(f"{api_url}/healthz", timeout=5)
        if response.status_code != 200:
            logger.error(f"API not healthy at {api_url}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Cannot connect to API at {api_url}: {e}")
        logger.error("Make sure the API server is running!")
        sys.exit(1)

    # Run tests
    tester = RAGTester(api_base_url=api_url)
    results = tester.run_all_tests()

    # Generate report
    report = tester.generate_report(results)

    # Save to file
    output_dir = Path("artifacts/test_reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = (
        output_dir
        / f"rag_accuracy_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"Report saved to: {output_file}")

    # Print summary
    tester.print_summary(report)

    # Exit with appropriate code
    success_rate = report["summary"]["answer_accuracy"]
    if success_rate >= 0.75:
        logger.info("✓ Test suite PASSED (≥75% accuracy)")
        sys.exit(0)
    else:
        logger.error(f"✗ Test suite FAILED ({success_rate:.1%} < 75% threshold)")
        sys.exit(1)


if __name__ == "__main__":
    main()
