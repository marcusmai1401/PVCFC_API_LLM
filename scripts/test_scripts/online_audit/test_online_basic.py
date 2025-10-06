#!/usr/bin/env python
"""
Basic Online Pipeline Tests
Tests /ask endpoint with simple queries, schema validation, and error handling

Prerequisites:
- API server running on localhost:8000
- Index loaded (BM25 + FAISS)
- doc_id_map.json available
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import httpx
from loguru import logger

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>")

# API base URL
API_BASE_URL = "http://localhost:8000"
TIMEOUT = 30.0  # seconds


class OnlineBasicTester:
    """Basic online pipeline tester"""
    
    def __init__(self):
        self.results = {
            "server_health": {"status": "pending"},
            "schema_validation": {"status": "pending"},
            "basic_vi_query": {"status": "pending"},
            "basic_en_query": {"status": "pending"},
            "error_empty_query": {"status": "pending"},
            "error_invalid_params": {"status": "pending"},
        }
        self.findings = []
    
    def run_all_tests(self) -> Dict:
        """Run all basic tests"""
        logger.info("=" * 80)
        logger.info("ONLINE PIPELINE - BASIC TESTS")
        logger.info("=" * 80)
        
        # Test 1: Server health
        logger.info("\n[1/6] Testing server health...")
        self.test_server_health()
        
        # Test 2: Schema validation
        logger.info("\n[2/6] Testing response schema...")
        self.test_schema_validation()
        
        # Test 3: Basic Vietnamese query
        logger.info("\n[3/6] Testing Vietnamese query...")
        self.test_basic_vi_query()
        
        # Test 4: Basic English query
        logger.info("\n[4/6] Testing English query...")
        self.test_basic_en_query()
        
        # Test 5: Error - empty query
        logger.info("\n[5/6] Testing error handling - empty query...")
        self.test_error_empty_query()
        
        # Test 6: Error - invalid params
        logger.info("\n[6/6] Testing error handling - invalid params...")
        self.test_error_invalid_params()
        
        return self._generate_report()
    
    def test_server_health(self):
        """Test if server is running and healthy"""
        try:
            response = httpx.get(f"{API_BASE_URL}/health", timeout=TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ Server healthy: {data.get('status', 'unknown')}")
                self.results["server_health"] = {
                    "status": "PASS",
                    "response_time_ms": response.elapsed.total_seconds() * 1000,
                    "data": data
                }
                self.findings.append({
                    "check": "server_health",
                    "status": "PASS",
                    "response_time": f"{response.elapsed.total_seconds()*1000:.0f}ms"
                })
            else:
                logger.error(f"✗ Server health check failed: {response.status_code}")
                self.results["server_health"] = {
                    "status": "FAIL",
                    "status_code": response.status_code
                }
                self.findings.append({
                    "check": "server_health",
                    "status": "FAIL",
                    "status_code": response.status_code
                })
                
        except httpx.ConnectError:
            logger.error("✗ Cannot connect to server. Is it running?")
            self.results["server_health"] = {
                "status": "FAIL",
                "error": "Connection refused - server not running"
            }
            self.findings.append({
                "check": "server_health",
                "status": "FAIL",
                "error": "Server not running on localhost:8000"
            })
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}")
            self.results["server_health"] = {
                "status": "FAIL",
                "error": str(e)
            }
    
    def test_schema_validation(self):
        """Test response schema compliance"""
        try:
            # Simple query to get response
            payload = {
                "query": "test",
                "language": "vi",
                "max_context": 5,
                "hyde": False,
                "execution_mode": "light_only",  # Use light for speed
                "enable_vision_generation": False  # Disable vision for basic test
            }
            
            response = httpx.post(
                f"{API_BASE_URL}/ask",
                json=payload,
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                required_fields = ["answer", "citations", "context_used", "confidence", "meta"]
                missing_fields = [f for f in required_fields if f not in data]
                
                if not missing_fields:
                    logger.info(f"✓ Schema valid: all required fields present")
                    
                    # Validate citations structure
                    citations = data.get("citations", [])
                    if citations:
                        first_citation = citations[0]
                        citation_fields = ["doc_id", "page"]
                        missing_citation_fields = [f for f in citation_fields if f not in first_citation]
                        
                        if not missing_citation_fields:
                            logger.info(f"  ✓ Citation schema valid")
                        else:
                            logger.warning(f"  ⚠ Missing citation fields: {missing_citation_fields}")
                    
                    # Validate meta structure
                    meta = data.get("meta", {})
                    expected_meta_fields = ["model", "latency_ms"]
                    present_meta = [f for f in expected_meta_fields if f in meta]
                    logger.info(f"  ✓ Meta fields present: {present_meta}")
                    
                    self.results["schema_validation"] = {
                        "status": "PASS",
                        "required_fields": required_fields,
                        "citations_count": len(citations),
                        "meta_fields": list(meta.keys())
                    }
                    self.findings.append({
                        "check": "response_schema",
                        "status": "PASS",
                        "note": "All required fields present"
                    })
                else:
                    logger.error(f"✗ Missing required fields: {missing_fields}")
                    self.results["schema_validation"] = {
                        "status": "FAIL",
                        "missing_fields": missing_fields
                    }
                    self.findings.append({
                        "check": "response_schema",
                        "status": "FAIL",
                        "missing_fields": missing_fields
                    })
            else:
                logger.error(f"✗ Request failed: {response.status_code}")
                self.results["schema_validation"] = {
                    "status": "FAIL",
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"✗ Schema test failed: {e}")
            self.results["schema_validation"] = {
                "status": "FAIL",
                "error": str(e)
            }
    
    def test_basic_vi_query(self):
        """Test basic Vietnamese query"""
        try:
            payload = {
                "query": "Áp suất vận hành là bao nhiêu?",
                "language": "vi",
                "max_context": 8,
                "hyde": False,
                "execution_mode": "light_only",
                "enable_vision_generation": False
            }
            
            start = time.time()
            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                citations = data.get("citations", [])
                
                logger.info(f"✓ Vietnamese query successful")
                logger.info(f"  Latency: {latency:.0f}ms")
                logger.info(f"  Answer length: {len(answer)} chars")
                logger.info(f"  Citations: {len(citations)}")
                
                self.results["basic_vi_query"] = {
                    "status": "PASS",
                    "latency_ms": latency,
                    "answer_length": len(answer),
                    "citations_count": len(citations)
                }
                self.findings.append({
                    "check": "vi_query",
                    "status": "PASS",
                    "latency_ms": latency
                })
            else:
                logger.error(f"✗ Request failed: {response.status_code}")
                self.results["basic_vi_query"] = {
                    "status": "FAIL",
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"✗ Vietnamese query test failed: {e}")
            self.results["basic_vi_query"] = {
                "status": "FAIL",
                "error": str(e)
            }
    
    def test_basic_en_query(self):
        """Test basic English query"""
        try:
            payload = {
                "query": "What is the operating pressure?",
                "language": "en",
                "max_context": 8,
                "hyde": False,
                "execution_mode": "light_only",
                "enable_vision_generation": False
            }
            
            start = time.time()
            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                citations = data.get("citations", [])
                
                logger.info(f"✓ English query successful")
                logger.info(f"  Latency: {latency:.0f}ms")
                logger.info(f"  Answer length: {len(answer)} chars")
                logger.info(f"  Citations: {len(citations)}")
                
                self.results["basic_en_query"] = {
                    "status": "PASS",
                    "latency_ms": latency,
                    "answer_length": len(answer),
                    "citations_count": len(citations)
                }
                self.findings.append({
                    "check": "en_query",
                    "status": "PASS",
                    "latency_ms": latency
                })
            else:
                logger.error(f"✗ Request failed: {response.status_code}")
                self.results["basic_en_query"] = {
                    "status": "FAIL",
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"✗ English query test failed: {e}")
            self.results["basic_en_query"] = {
                "status": "FAIL",
                "error": str(e)
            }
    
    def test_error_empty_query(self):
        """Test error handling for empty query"""
        try:
            payload = {
                "query": "",  # Empty query
                "language": "vi",
                "max_context": 8
            }
            
            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)
            
            # Should return 422 (Validation Error)
            if response.status_code in [400, 422]:
                logger.info(f"✓ Empty query correctly rejected: {response.status_code}")
                self.results["error_empty_query"] = {
                    "status": "PASS",
                    "status_code": response.status_code,
                    "error_message": response.json().get("detail", "")
                }
                self.findings.append({
                    "check": "error_empty_query",
                    "status": "PASS",
                    "note": f"Correctly returns {response.status_code}"
                })
            else:
                logger.error(f"✗ Expected 422, got {response.status_code}")
                self.results["error_empty_query"] = {
                    "status": "FAIL",
                    "expected": 422,
                    "actual": response.status_code
                }
                self.findings.append({
                    "check": "error_empty_query",
                    "status": "FAIL",
                    "issue": f"Wrong status code: {response.status_code}"
                })
                
        except Exception as e:
            logger.error(f"✗ Error test failed: {e}")
            self.results["error_empty_query"] = {
                "status": "FAIL",
                "error": str(e)
            }
    
    def test_error_invalid_params(self):
        """Test error handling for invalid parameters"""
        try:
            payload = {
                "query": "test",
                "language": "vi",
                "max_context": 100  # Exceeds limit (max 20)
            }
            
            response = httpx.post(f"{API_BASE_URL}/ask", json=payload, timeout=TIMEOUT)
            
            # Should return 422 (Validation Error)
            if response.status_code == 422:
                logger.info(f"✓ Invalid params correctly rejected")
                self.results["error_invalid_params"] = {
                    "status": "PASS",
                    "status_code": response.status_code
                }
                self.findings.append({
                    "check": "error_invalid_params",
                    "status": "PASS"
                })
            else:
                logger.warning(f"⚠ Expected 422, got {response.status_code}")
                self.results["error_invalid_params"] = {
                    "status": "WARNING",
                    "expected": 422,
                    "actual": response.status_code,
                    "note": "May accept out-of-range values"
                }
                
        except Exception as e:
            logger.error(f"✗ Invalid params test failed: {e}")
            self.results["error_invalid_params"] = {
                "status": "FAIL",
                "error": str(e)
            }
    
    def _generate_report(self) -> Dict:
        """Generate test report"""
        logger.info("\n" + "=" * 80)
        logger.info("BASIC TESTS - REPORT")
        logger.info("=" * 80)
        
        passed = sum(1 for r in self.results.values() if r.get("status") == "PASS")
        failed = sum(1 for r in self.results.values() if r.get("status") == "FAIL")
        warnings = sum(1 for r in self.results.values() if r.get("status") == "WARNING")
        
        logger.info(f"✓ Passed: {passed}/{len(self.results)}")
        logger.info(f"✗ Failed: {failed}/{len(self.results)}")
        logger.info(f"⚠ Warnings: {warnings}/{len(self.results)}")
        logger.info("")
        
        # Details
        for test_name, result in self.results.items():
            status = result.get("status", "unknown")
            icon = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
            logger.info(f"{icon} {test_name}: {status}")
        
        logger.info("=" * 80)
        
        # Save report
        report_path = PROJECT_ROOT / "reports" / "test_results" / f"online_basic_test_{int(time.time())}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report_data = {
            "test_type": "online_basic",
            "timestamp": time.time(),
            "summary": {
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
                "total": len(self.results)
            },
            "results": self.results,
            "findings": self.findings
        }
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Report saved: {report_path}")
        
        return report_data


def main():
    """Main entry point"""
    tester = OnlineBasicTester()
    report = tester.run_all_tests()
    
    if report["summary"]["failed"] > 0:
        logger.error("\n❌ Some tests failed")
        sys.exit(1)
    else:
        logger.info("\n✓ All basic tests passed")
        sys.exit(0)


if __name__ == "__main__":
    main()

