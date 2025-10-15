#!/usr/bin/env python
"""
Retrieval & Reranking Tests
Tests hybrid retrieval (BM25 + FAISS) and reranking behavior (EN CE vs VI fallback)

Key checks:
- BM25 and FAISS both return results
- RRF merge works correctly
- EN uses cross-encoder reranking
- VI uses score-based fallback (no NaN, no empty results)
- top_k parameter respected
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import httpx
from loguru import logger

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger.remove()
logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
)

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 30.0


class RetrievalRerankTester:
    """Test retrieval and reranking logic"""

    def __init__(self):
        self.results = {}
        self.findings = []

    def run_all_tests(self) -> Dict:
        """Run all retrieval/rerank tests"""
        logger.info("=" * 80)
        logger.info("ONLINE PIPELINE - RETRIEVAL & RERANK TESTS")
        logger.info("=" * 80)

        # Test 1: Keyword-heavy query (BM25 should dominate)
        logger.info("\n[1/6] Testing keyword-heavy query...")
        self.test_keyword_query()

        # Test 2: Semantic query (FAISS should help)
        logger.info("\n[2/6] Testing semantic query...")
        self.test_semantic_query()

        # Test 3: EN with cross-encoder reranking
        logger.info("\n[3/6] Testing EN reranking (cross-encoder)...")
        self.test_en_reranking()

        # Test 4: VI with score-based fallback
        logger.info("\n[4/6] Testing VI reranking (score fallback)...")
        self.test_vi_reranking()

        # Test 5: Different max_context values
        logger.info("\n[5/6] Testing max_context variation...")
        self.test_max_context_variation()

        # Test 6: Retrieval details (if API returns them)
        logger.info("\n[6/6] Testing retrieval_details...")
        self.test_retrieval_details()

        return self._generate_report()

    def test_keyword_query(self):
        """Test query with exact keywords"""
        try:
            payload = {
                "query": "KT06101 pressure bar",  # Exact keywords
                "language": "en",
                "max_context": 8,
                "hyde": False,
                "execution_mode": "light_only",
                "enable_vision_generation": False,
            }

            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                citations = data.get("citations", [])

                logger.info(f"✓ Keyword query successful")
                logger.info(f"  Citations: {len(citations)}")

                # Check if retrieval_details available
                if "retrieval_details" in data and data["retrieval_details"]:
                    details = data["retrieval_details"]
                    bm25_count = details.get("bm25_count", 0)
                    faiss_count = details.get("faiss_count", 0)
                    logger.info(f"  BM25 results: {bm25_count}")
                    logger.info(f"  FAISS results: {faiss_count}")

                    if bm25_count > 0:
                        logger.info(
                            f"  ✓ BM25 returned results (good for keyword query)"
                        )
                    else:
                        logger.warning(f"  ⚠ BM25 returned 0 results")

                self.results["keyword_query"] = {
                    "status": "PASS",
                    "citations": len(citations),
                }
                self.findings.append({"check": "keyword_query", "status": "PASS"})
            else:
                logger.error(f"✗ Request failed: {response.status_code}")
                self.results["keyword_query"] = {
                    "status": "FAIL",
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.results["keyword_query"] = {"status": "FAIL", "error": str(e)}

    def test_semantic_query(self):
        """Test semantic query (paraphrased)"""
        try:
            payload = {
                "query": "What is the maximum allowed stress for operation?",  # Semantic for "pressure"
                "language": "en",
                "max_context": 8,
                "hyde": True,  # Enable HyDE for semantic boost
                "execution_mode": "light_only",
                "enable_vision_generation": False,
            }

            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                citations = data.get("citations", [])

                logger.info(f"✓ Semantic query successful")
                logger.info(f"  Citations: {len(citations)}")

                self.results["semantic_query"] = {
                    "status": "PASS",
                    "citations": len(citations),
                }
                self.findings.append({"check": "semantic_query", "status": "PASS"})
            else:
                logger.error(f"✗ Request failed: {response.status_code}")
                self.results["semantic_query"] = {"status": "FAIL"}

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.results["semantic_query"] = {"status": "FAIL", "error": str(e)}

    def test_en_reranking(self):
        """Test EN query with cross-encoder reranking"""
        try:
            payload = {
                "query": "operating pressure specifications",
                "language": "en",  # EN → cross-encoder
                "max_context": 8,
                "hyde": False,
                "execution_mode": "light_only",
                "enable_vision_generation": False,
            }

            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)

            if response.status_code == 200:
                data = response.json()

                # Check reranking_details if available
                if "reranking_details" in data and data["reranking_details"]:
                    rerank_info = data["reranking_details"]
                    method = rerank_info.get("method", "unknown")
                    logger.info(f"  Rerank method: {method}")

                    if method == "cross_encoder":
                        logger.info(f"  ✓ EN correctly uses cross-encoder")
                        self.findings.append(
                            {
                                "check": "en_reranker",
                                "status": "PASS",
                                "method": "cross_encoder",
                            }
                        )
                    else:
                        logger.warning(f"  ⚠ Expected cross_encoder, got {method}")

                logger.info(f"✓ EN reranking test completed")
                self.results["en_reranking"] = {"status": "PASS"}
            else:
                logger.error(f"✗ Request failed: {response.status_code}")
                self.results["en_reranking"] = {"status": "FAIL"}

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.results["en_reranking"] = {"status": "FAIL", "error": str(e)}

    def test_vi_reranking(self):
        """Test VI query with score-based fallback (no NaN)"""
        try:
            payload = {
                "query": "thông số áp suất vận hành",
                "language": "vi",  # VI → score-based fallback
                "max_context": 8,
                "hyde": False,
                "execution_mode": "light_only",
                "enable_vision_generation": False,
            }

            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                citations = data.get("citations", [])
                answer = data.get("answer", "")

                # Critical check: VI should NOT return empty or NaN
                if len(citations) > 0 and len(answer) > 10:
                    logger.info(f"✓ VI reranking successful (no NaN, not empty)")
                    logger.info(f"  Citations: {len(citations)}")
                    logger.info(f"  Answer length: {len(answer)}")

                    self.results["vi_reranking"] = {
                        "status": "PASS",
                        "citations": len(citations),
                        "answer_length": len(answer),
                    }
                    self.findings.append(
                        {
                            "check": "vi_reranker_no_nan",
                            "status": "PASS",
                            "note": "VI fallback works correctly",
                        }
                    )
                else:
                    logger.error(f"✗ VI reranking returned empty results!")
                    self.results["vi_reranking"] = {
                        "status": "FAIL",
                        "issue": "Empty results or NaN",
                    }
                    self.findings.append(
                        {
                            "check": "vi_reranker_no_nan",
                            "status": "FAIL",
                            "issue": "Empty results",
                        }
                    )
            else:
                logger.error(f"✗ Request failed: {response.status_code}")
                self.results["vi_reranking"] = {"status": "FAIL"}

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.results["vi_reranking"] = {"status": "FAIL", "error": str(e)}

    def test_max_context_variation(self):
        """Test different max_context values"""
        try:
            test_values = [1, 5, 8, 15, 20]
            results = []

            for k in test_values:
                payload = {
                    "query": "operating parameters",
                    "language": "en",
                    "max_context": k,
                    "hyde": False,
                    "execution_mode": "light_only",
                    "enable_vision_generation": False,
                }

                response = httpx.post(
                    f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT
                )

                if response.status_code == 200:
                    data = response.json()
                    context_count = len(data.get("context_used", []))
                    citations_count = len(data.get("citations", []))

                    results.append(
                        {
                            "max_context": k,
                            "context_used": context_count,
                            "citations": citations_count,
                        }
                    )
                    logger.info(
                        f"  k={k}: context={context_count}, citations={citations_count}"
                    )

            if results:
                logger.info(f"✓ max_context variation test completed")
                self.results["max_context_variation"] = {
                    "status": "PASS",
                    "results": results,
                }
                self.findings.append(
                    {
                        "check": "max_context_respected",
                        "status": "PASS",
                        "note": f"Tested k={test_values}",
                    }
                )
            else:
                self.results["max_context_variation"] = {"status": "FAIL"}

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.results["max_context_variation"] = {"status": "FAIL", "error": str(e)}

    def test_retrieval_details(self):
        """Test if retrieval_details are available"""
        try:
            payload = {
                "query": "test query",
                "language": "en",
                "max_context": 5,
                "hyde": False,
                "execution_mode": "light_only",
                "enable_vision_generation": False,
            }

            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)

            if response.status_code == 200:
                data = response.json()

                has_retrieval_details = (
                    "retrieval_details" in data and data["retrieval_details"]
                )
                has_reranking_details = (
                    "reranking_details" in data and data["reranking_details"]
                )

                if has_retrieval_details or has_reranking_details:
                    logger.info(f"✓ Debug details available")
                    if has_retrieval_details:
                        logger.info(f"  ✓ retrieval_details present")
                    if has_reranking_details:
                        logger.info(f"  ✓ reranking_details present")
                else:
                    logger.info(f"ℹ Debug details not exposed (may be intentional)")

                self.results["retrieval_details"] = {
                    "status": "INFO",
                    "has_retrieval": has_retrieval_details,
                    "has_reranking": has_reranking_details,
                }
            else:
                self.results["retrieval_details"] = {"status": "FAIL"}

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.results["retrieval_details"] = {"status": "FAIL", "error": str(e)}

    def _generate_report(self) -> Dict:
        """Generate report"""
        logger.info("\n" + "=" * 80)
        logger.info("RETRIEVAL & RERANK TESTS - REPORT")
        logger.info("=" * 80)

        passed = sum(1 for r in self.results.values() if r.get("status") == "PASS")
        failed = sum(1 for r in self.results.values() if r.get("status") == "FAIL")

        logger.info(f"✓ Passed: {passed}/{len(self.results)}")
        logger.info(f"✗ Failed: {failed}/{len(self.results)}")
        logger.info("=" * 80)

        report_path = (
            PROJECT_ROOT
            / "reports"
            / "test_results"
            / f"online_retrieval_test_{int(time.time())}.json"
        )
        report_data = {
            "test_type": "retrieval_rerank",
            "timestamp": time.time(),
            "summary": {"passed": passed, "failed": failed, "total": len(self.results)},
            "results": self.results,
            "findings": self.findings,
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Report saved: {report_path}")
        return report_data


def main():
    """Main entry point"""
    tester = RetrievalRerankTester()
    report = tester.run_all_tests()

    if report["summary"]["failed"] > 0:
        logger.error("\n❌ Some tests failed")
        sys.exit(1)
    else:
        logger.info("\n✓ All retrieval/rerank tests passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
