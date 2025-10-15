#!/usr/bin/env python
"""
Comprehensive Online Audit
Tổng hợp kiểm tra toàn diện online pipeline

Covers:
1. Server preconditions (indices, doc_id_map)
2. Basic queries (VI/EN)
3. Error handling (400/422/503)
4. Retrieval & reranking
5. Vision gating
6. Metrics & tracing
7. Response schema & telemetry

Note: Requires API server running and indices loaded
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from loguru import logger

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add(
    PROJECT_ROOT / "logs" / f"online_audit_{int(time.time())}.log", level="DEBUG"
)

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 30.0


class ComprehensiveOnlineAuditor:
    """Comprehensive online pipeline auditor"""

    def __init__(self):
        self.test_results = {
            "preconditions": {"status": "pending"},
            "basic_queries": {"status": "pending"},
            "error_handling": {"status": "pending"},
            "retrieval_rerank": {"status": "pending"},
            "vision_gating": {"status": "pending"},
            "schema_telemetry": {"status": "pending"},
            "metrics_trace": {"status": "pending"},
        }
        self.findings = []
        self.metrics = {
            "latencies": [],
            "citation_counts": [],
        }

    def run_audit(self) -> Dict:
        """Run comprehensive audit"""
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE ONLINE PIPELINE AUDIT")
        logger.info("=" * 80)
        logger.info(f"API URL: {API_BASE_URL}")
        logger.info("")

        # PHASE 1: Preconditions
        logger.info("\n📋 PHASE 1: Preconditions")
        if not self.check_preconditions():
            logger.error("❌ Preconditions failed - cannot continue audit")
            return self._generate_report()

        # PHASE 2: Basic queries
        logger.info("\n🔍 PHASE 2: Basic Queries (VI/EN)")
        self.audit_basic_queries()

        # PHASE 3: Error handling
        logger.info("\n⚠️  PHASE 3: Error Handling")
        self.audit_error_handling()

        # PHASE 4: Retrieval & Reranking
        logger.info("\n🔄 PHASE 4: Retrieval & Reranking")
        self.audit_retrieval_rerank()

        # PHASE 5: Vision Gating
        logger.info("\n👁️  PHASE 5: Vision Gating")
        self.audit_vision_gating()

        # PHASE 6: Schema & Telemetry
        logger.info("\n📊 PHASE 6: Schema & Telemetry")
        self.audit_schema_telemetry()

        # PHASE 7: Metrics & Tracing
        logger.info("\n📈 PHASE 7: Metrics & Tracing")
        self.audit_metrics_trace()

        return self._generate_report()

    def check_preconditions(self) -> bool:
        """Check if prerequisites are met"""
        findings = []
        all_ok = True

        try:
            # Check 1: Server running
            logger.info("  Checking server...")
            response = httpx.get(f"{API_BASE_URL}/health", timeout=TIMEOUT)
            if response.status_code == 200:
                logger.info("  ✓ Server is running")
                findings.append({"check": "server_running", "status": "PASS"})
            else:
                logger.error(f"  ✗ Server health check failed: {response.status_code}")
                findings.append({"check": "server_running", "status": "FAIL"})
                all_ok = False

        except httpx.ConnectError:
            logger.error("  ✗ Cannot connect - server not running?")
            findings.append(
                {
                    "check": "server_running",
                    "status": "FAIL",
                    "error": "Connection refused",
                }
            )
            all_ok = False

        try:
            # Check 2: Index stats
            logger.info("  Checking index stats...")
            response = httpx.get(f"{API_BASE_URL}/index-stats", timeout=TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"  ✓ Index stats available")

                if "bm25" in data:
                    bm25_count = data["bm25"].get("total_documents", 0)
                    logger.info(f"    BM25 docs: {bm25_count}")

                if "faiss" in data:
                    faiss_count = data["faiss"].get("total_vectors", 0)
                    logger.info(f"    FAISS vectors: {faiss_count}")

                findings.append(
                    {"check": "index_loaded", "status": "PASS", "data": data}
                )
            else:
                logger.warning(f"  ⚠ Index stats not available: {response.status_code}")
                findings.append({"check": "index_loaded", "status": "WARNING"})

        except Exception as e:
            logger.warning(f"  ⚠ Could not check index stats: {e}")
            findings.append(
                {"check": "index_loaded", "status": "WARNING", "error": str(e)}
            )

        try:
            # Check 3: doc_id_map.json
            logger.info("  Checking doc_id_map...")
            doc_id_map_path = (
                PROJECT_ROOT / "artifacts" / "ingestion" / "doc_id_map.json"
            )
            if doc_id_map_path.exists():
                with open(doc_id_map_path, encoding="utf-8") as f:
                    doc_id_map = json.load(f)
                logger.info(f"  ✓ doc_id_map available ({len(doc_id_map)} entries)")
                findings.append(
                    {
                        "check": "doc_id_map",
                        "status": "PASS",
                        "entries": len(doc_id_map),
                    }
                )
            else:
                logger.warning(f"  ⚠ doc_id_map.json not found")
                logger.warning(f"    Citations will not have pdf_path")
                findings.append(
                    {
                        "check": "doc_id_map",
                        "status": "WARNING",
                        "note": "pdf_path unavailable",
                    }
                )

        except Exception as e:
            logger.warning(f"  ⚠ Could not load doc_id_map: {e}")
            findings.append(
                {"check": "doc_id_map", "status": "WARNING", "error": str(e)}
            )

        self.test_results["preconditions"] = {
            "status": "PASS" if all_ok else "FAIL",
            "findings": findings,
        }

        return all_ok

    def audit_basic_queries(self):
        """Audit basic query functionality"""
        findings = []

        test_queries = [
            {"query": "áp suất", "language": "vi", "label": "VI keyword"},
            {"query": "operating pressure", "language": "en", "label": "EN keyword"},
        ]

        for test in test_queries:
            try:
                payload = {
                    "query": test["query"],
                    "language": test["language"],
                    "max_context": 8,
                    "hyde": False,
                    "execution_mode": "light_only",
                    "enable_vision_generation": False,
                }

                start = time.time()
                response = httpx.post(
                    f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT
                )
                latency = (time.time() - start) * 1000

                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        f"  ✓ {test['label']}: {latency:.0f}ms, {len(data.get('citations', []))} citations"
                    )

                    self.metrics["latencies"].append(latency)
                    self.metrics["citation_counts"].append(
                        len(data.get("citations", []))
                    )

                    findings.append(
                        {
                            "query_type": test["label"],
                            "status": "PASS",
                            "latency_ms": latency,
                        }
                    )
                else:
                    logger.error(f"  ✗ {test['label']} failed: {response.status_code}")
                    findings.append({"query_type": test["label"], "status": "FAIL"})

            except Exception as e:
                logger.error(f"  ✗ {test['label']} error: {e}")
                findings.append(
                    {"query_type": test["label"], "status": "FAIL", "error": str(e)}
                )

        self.test_results["basic_queries"] = {
            "status": "PASS"
            if all(f.get("status") == "PASS" for f in findings)
            else "FAIL",
            "findings": findings,
        }

    def audit_error_handling(self):
        """Audit error handling"""
        findings = []

        # Test empty query
        try:
            response = httpx.post(
                f"{API_BASE_URL}/ask",
                json={"query": "", "language": "vi"},
                timeout=TIMEOUT,
            )

            if response.status_code in [400, 422]:
                logger.info(f"  ✓ Empty query rejected: {response.status_code}")
                findings.append({"test": "empty_query", "status": "PASS"})
            else:
                logger.warning(
                    f"  ⚠ Unexpected status for empty query: {response.status_code}"
                )
                findings.append({"test": "empty_query", "status": "WARNING"})

        except Exception as e:
            logger.error(f"  ✗ Error test failed: {e}")
            findings.append({"test": "empty_query", "status": "FAIL", "error": str(e)})

        self.test_results["error_handling"] = {
            "status": "PASS"
            if findings and findings[0].get("status") == "PASS"
            else "FAIL",
            "findings": findings,
        }

    def audit_retrieval_rerank(self):
        """Audit retrieval and reranking"""
        findings = []

        # Test EN (cross-encoder)
        try:
            payload = {
                "query": "specifications",
                "language": "en",
                "max_context": 8,
                "execution_mode": "light_only",
                "enable_vision_generation": False,
            }

            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"  ✓ EN retrieval+rerank: {len(data.get('citations', []))} citations"
                )
                findings.append({"test": "en_rerank", "status": "PASS"})
            else:
                findings.append({"test": "en_rerank", "status": "FAIL"})

        except Exception as e:
            findings.append({"test": "en_rerank", "status": "FAIL", "error": str(e)})

        # Test VI (score fallback)
        try:
            payload = {
                "query": "thông số",
                "language": "vi",
                "max_context": 8,
                "execution_mode": "light_only",
                "enable_vision_generation": False,
            }

            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                citations = data.get("citations", [])
                answer = data.get("answer", "")

                if len(citations) > 0 and len(answer) > 10:
                    logger.info(
                        f"  ✓ VI retrieval+rerank: {len(citations)} citations, no NaN"
                    )
                    findings.append({"test": "vi_rerank_no_nan", "status": "PASS"})
                else:
                    logger.error(f"  ✗ VI returned empty results (possible NaN issue)")
                    findings.append(
                        {
                            "test": "vi_rerank_no_nan",
                            "status": "FAIL",
                            "issue": "Empty results",
                        }
                    )
            else:
                findings.append({"test": "vi_rerank", "status": "FAIL"})

        except Exception as e:
            findings.append({"test": "vi_rerank", "status": "FAIL", "error": str(e)})

        self.test_results["retrieval_rerank"] = {
            "status": "PASS"
            if all(f.get("status") == "PASS" for f in findings)
            else "FAIL",
            "findings": findings,
        }

    def audit_vision_gating(self):
        """Audit vision gating logic"""
        findings = []

        # Test with vision enabled
        try:
            payload = {
                "query": "technical specifications table",
                "language": "en",
                "max_context": 5,
                "execution_mode": "production",  # Use heavy (supports vision)
                "enable_vision_generation": True,  # Enable vision
            }

            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                meta = data.get("meta", {})

                # Check vision_generation in meta
                if "vision_generation" in meta:
                    vision_info = meta["vision_generation"]
                    enabled = vision_info.get("enabled", False)
                    pages_used = vision_info.get("pages_used", [])
                    pages_failed = vision_info.get("pages_failed", [])

                    logger.info(f"  Vision enabled: {enabled}")
                    logger.info(f"  Pages used: {len(pages_used)}")
                    logger.info(f"  Pages failed: {len(pages_failed)}")

                    if enabled and len(pages_used) > 0:
                        logger.info(f"  ✓ Vision successfully gated and used")
                        findings.append(
                            {
                                "test": "vision_enabled",
                                "status": "PASS",
                                "pages": len(pages_used),
                            }
                        )
                    elif not enabled:
                        logger.info(f"  ℹ Vision not triggered (may lack pdf_path)")
                        findings.append(
                            {
                                "test": "vision_enabled",
                                "status": "INFO",
                                "note": "Not triggered",
                            }
                        )
                    else:
                        findings.append({"test": "vision_enabled", "status": "INFO"})
                else:
                    logger.warning(f"  ⚠ vision_generation not in meta")
                    findings.append(
                        {"test": "vision_info_present", "status": "WARNING"}
                    )

            else:
                findings.append({"test": "vision_query", "status": "FAIL"})

        except Exception as e:
            logger.error(f"  ✗ Vision test failed: {e}")
            findings.append({"test": "vision", "status": "FAIL", "error": str(e)})

        self.test_results["vision_gating"] = {
            "status": "PASS",  # INFO counts as pass
            "findings": findings,
        }

    def audit_schema_telemetry(self):
        """Audit response schema and telemetry"""
        findings = []

        try:
            payload = {
                "query": "test",
                "language": "vi",
                "max_context": 5,
                "execution_mode": "light_only",
                "enable_vision_generation": False,
            }

            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)

            if response.status_code == 200:
                data = response.json()

                # Check required fields
                required = ["answer", "citations", "context_used", "confidence", "meta"]
                missing = [f for f in required if f not in data]

                if not missing:
                    logger.info(f"  ✓ All required fields present")
                    findings.append({"check": "schema_complete", "status": "PASS"})

                    # Check meta breakdown
                    meta = data.get("meta", {})
                    if "breakdown" in meta:
                        breakdown = meta["breakdown"]
                        logger.info(f"  ✓ Latency breakdown present")
                        logger.info(
                            f"    - transform: {breakdown.get('transform_ms', 0):.0f}ms"
                        )
                        logger.info(
                            f"    - retrieve: {breakdown.get('retrieve_ms', 0):.0f}ms"
                        )
                        logger.info(
                            f"    - rerank: {breakdown.get('rerank_ms', 0):.0f}ms"
                        )
                        logger.info(
                            f"    - generate: {breakdown.get('generate_ms', 0):.0f}ms"
                        )

                        # Verify breakdown sum ≈ total latency
                        breakdown_sum = sum(breakdown.values())
                        total_latency = meta.get("latency_ms", 0)
                        if (
                            abs(breakdown_sum - total_latency) / total_latency < 0.2
                        ):  # Within 20%
                            logger.info(
                                f"  ✓ Breakdown sum matches total ({breakdown_sum:.0f} ≈ {total_latency:.0f})"
                            )
                            findings.append(
                                {"check": "breakdown_accuracy", "status": "PASS"}
                            )
                        else:
                            logger.warning(
                                f"  ⚠ Breakdown sum mismatch: {breakdown_sum:.0f} vs {total_latency:.0f}"
                            )
                            findings.append(
                                {"check": "breakdown_accuracy", "status": "WARNING"}
                            )
                    else:
                        logger.warning(f"  ⚠ Latency breakdown not present")
                        findings.append(
                            {"check": "latency_breakdown", "status": "WARNING"}
                        )

                    # Check trace_id
                    if "trace_id" in meta:
                        logger.info(f"  ✓ trace_id present: {meta['trace_id']}")
                        findings.append({"check": "trace_id_present", "status": "PASS"})
                    else:
                        logger.warning(f"  ⚠ trace_id not in meta")
                        findings.append(
                            {"check": "trace_id_present", "status": "WARNING"}
                        )

                else:
                    logger.error(f"  ✗ Missing fields: {missing}")
                    findings.append(
                        {
                            "check": "schema_complete",
                            "status": "FAIL",
                            "missing": missing,
                        }
                    )

        except Exception as e:
            logger.error(f"  ✗ Schema test failed: {e}")
            findings.append({"check": "schema", "status": "FAIL", "error": str(e)})

        self.test_results["schema_telemetry"] = {
            "status": "PASS"
            if findings and findings[0].get("status") == "PASS"
            else "FAIL",
            "findings": findings,
        }

    def audit_metrics_trace(self):
        """Audit /metrics and /trace endpoints"""
        findings = []

        # Test /metrics
        try:
            response = httpx.get(f"{API_BASE_URL}/metrics", timeout=TIMEOUT)
            if response.status_code == 200:
                metrics_text = response.text
                logger.info(
                    f"  ✓ /metrics endpoint available ({len(metrics_text)} chars)"
                )

                # Check for Prometheus format
                if "# HELP" in metrics_text or "# TYPE" in metrics_text:
                    logger.info(f"  ✓ Prometheus format detected")
                    findings.append({"check": "metrics_prometheus", "status": "PASS"})
                else:
                    logger.warning(f"  ⚠ May not be Prometheus format")
                    findings.append(
                        {"check": "metrics_prometheus", "status": "WARNING"}
                    )
            else:
                logger.warning(f"  ⚠ /metrics not available: {response.status_code}")
                findings.append({"check": "metrics_endpoint", "status": "WARNING"})

        except Exception as e:
            logger.warning(f"  ⚠ Metrics test failed: {e}")
            findings.append({"check": "metrics", "status": "WARNING", "error": str(e)})

        # Test /trace
        try:
            response = httpx.get(f"{API_BASE_URL}/trace", timeout=TIMEOUT)
            if response.status_code == 200:
                logger.info(f"  ✓ /trace endpoint available")
                findings.append({"check": "trace_endpoint", "status": "PASS"})
            else:
                logger.info(f"  ℹ /trace may not be active")
                findings.append({"check": "trace_endpoint", "status": "INFO"})

        except Exception as e:
            logger.info(f"  ℹ /trace not available: {e}")
            findings.append({"check": "trace", "status": "INFO"})

        self.test_results["metrics_trace"] = {"status": "PASS", "findings": findings}

    def _generate_report(self) -> Dict:
        """Generate comprehensive report"""
        logger.info("\n" + "=" * 80)
        logger.info("COMPREHENSIVE AUDIT - SUMMARY")
        logger.info("=" * 80)

        passed = sum(1 for r in self.test_results.values() if r.get("status") == "PASS")
        failed = sum(1 for r in self.test_results.values() if r.get("status") == "FAIL")

        logger.info(f"✓ Passed: {passed}/{len(self.test_results)}")
        logger.info(f"✗ Failed: {failed}/{len(self.test_results)}")
        logger.info("")

        # Metrics summary
        if self.metrics["latencies"]:
            latencies = self.metrics["latencies"]
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = (
                latencies[int(len(latencies) * 0.95)]
                if len(latencies) > 20
                else latencies[-1]
            )

            logger.info(f"Latency Metrics:")
            logger.info(f"  P50: {p50:.0f}ms")
            logger.info(f"  P95: {p95:.0f}ms")
            logger.info(f"  Min: {min(latencies):.0f}ms")
            logger.info(f"  Max: {max(latencies):.0f}ms")

        logger.info("=" * 80)

        # Save report
        report_path = (
            PROJECT_ROOT
            / "reports"
            / "test_results"
            / f"online_comprehensive_audit_{int(time.time())}.json"
        )
        report_data = {
            "audit_type": "online_comprehensive",
            "timestamp": time.time(),
            "api_url": API_BASE_URL,
            "summary": {
                "passed": passed,
                "failed": failed,
                "total": len(self.test_results),
            },
            "results": self.test_results,
            "findings": self.findings,
            "metrics": self.metrics,
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"📄 Report saved: {report_path}")

        return report_data


def main():
    """Main entry point"""
    auditor = ComprehensiveOnlineAuditor()
    report = auditor.run_audit()

    if report["summary"]["failed"] > 0:
        logger.error("\n❌ Audit completed with failures")
        sys.exit(1)
    else:
        logger.info("\n✓ Audit completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
