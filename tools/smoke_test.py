#!/usr/bin/env python3
"""
Smoke test cho PVCFC RAG API
Kiểm tra kết nối LLM và các service cơ bản

Usage:
    python tools/smoke_test.py
    python -m tools.smoke_test
"""

import asyncio
import os
import sys
from typing import Any, Dict

import httpx
from loguru import logger

# Add app to path để import được
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


class SmokeTest:
    """Smoke test runner"""

    def __init__(self):
        self.results = {}
        self.passed = 0
        self.failed = 0

    async def run_all_tests(self) -> Dict[str, Any]:
        """Chạy tất cả smoke tests"""
        logger.info("Starting smoke tests...")

        # Test 1: Basic health check
        await self.test_health_endpoint()

        # Test 2: LLM connection (nếu có config)
        await self.test_llm_connection()

        # Test 3: Configuration validation
        await self.test_configuration()

        # Summary
        self._print_summary()

        return {
            "total_tests": self.passed + self.failed,
            "passed": self.passed,
            "failed": self.failed,
            "success_rate": self.passed / (self.passed + self.failed)
            if (self.passed + self.failed) > 0
            else 0,
            "results": self.results,
        }

    async def test_health_endpoint(self):
        """Test health endpoint accessibility"""
        test_name = "health_endpoint"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:{settings.api_port}/healthz", timeout=5.0
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "healthy":
                        self._record_pass(
                            test_name, "Health endpoint responding correctly"
                        )
                    else:
                        self._record_fail(
                            test_name, f"Unexpected health status: {data.get('status')}"
                        )
                else:
                    self._record_fail(test_name, f"HTTP {response.status_code}")

        except Exception as e:
            self._record_fail(test_name, f"Connection failed: {str(e)}")

    async def test_llm_connection(self):
        """Test LLM provider connection (nếu có API key)"""
        test_name = "llm_connection"

        if settings.llm_provider == "none":
            self._record_skip(test_name, "LLM_PROVIDER=none, skipping connection test")
            return

        if not settings.llm_provider_ready:
            self._record_skip(
                test_name, f"No API key for provider: {settings.llm_provider}"
            )
            return

        # TODO Phase 2+: Implement actual LLM connection test
        try:
            if settings.llm_provider == "openai":
                await self._test_openai_connection()
            elif settings.llm_provider == "gemini":
                await self._test_gemini_connection()
            else:
                self._record_fail(
                    test_name, f"Unknown provider: {settings.llm_provider}"
                )

        except Exception as e:
            self._record_fail(test_name, f"LLM connection failed: {str(e)}")

    async def test_configuration(self):
        """Test configuration validation"""
        test_name = "configuration"

        try:
            # Kiểm tra các cấu hình cơ bản
            checks = []

            # Port valid
            if 1 <= settings.api_port <= 65535:
                checks.append("OK API port valid")
            else:
                checks.append("ERR API port invalid")

            # Environment valid
            if settings.app_env in ["local", "dev", "prod"]:
                checks.append("OK APP_ENV valid")
            else:
                checks.append("ERR APP_ENV invalid")

            # Log level valid
            if settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                checks.append("OK LOG_LEVEL valid")
            else:
                checks.append("ERR LOG_LEVEL invalid")

            failed_checks = [c for c in checks if c.startswith("ERR")]
            if failed_checks:
                self._record_fail(
                    test_name, f"Config validation failed: {'; '.join(failed_checks)}"
                )
            else:
                self._record_pass(
                    test_name, f"All config checks passed: {len(checks)} items"
                )

        except Exception as e:
            self._record_fail(test_name, f"Config validation error: {str(e)}")

    async def _test_openai_connection(self):
        """Test OpenAI API connection"""
        # TODO Phase 2+: Implement OpenAI connection test
        # async with httpx.AsyncClient() as client:
        #     headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        #     response = await client.get("https://api.openai.com/v1/models", headers=headers)
        #     if response.status_code == 200:
        #         self._record_pass("llm_connection", "OpenAI API accessible")
        #     else:
        #         self._record_fail("llm_connection", f"OpenAI API error: {response.status_code}")

        self._record_skip(
            "llm_connection", "OpenAI connection test will be implemented in Phase 2+"
        )

    async def _test_gemini_connection(self):
        """Test Gemini API connection"""
        # TODO Phase 2+: Implement Gemini connection test
        self._record_skip(
            "llm_connection", "Gemini connection test will be implemented in Phase 2+"
        )

    def _record_pass(self, test_name: str, message: str):
        """Ghi nhận test pass"""
        self.results[test_name] = {"status": "PASS", "message": message}
        self.passed += 1
        logger.info(f"PASS {test_name}: {message}")

    def _record_fail(self, test_name: str, message: str):
        """Ghi nhận test fail"""
        self.results[test_name] = {"status": "FAIL", "message": message}
        self.failed += 1
        logger.error(f"FAIL {test_name}: {message}")

    def _record_skip(self, test_name: str, message: str):
        """Ghi nhận test skip"""
        self.results[test_name] = {"status": "SKIP", "message": message}
        logger.info(f"SKIP {test_name}: {message}")

    def _print_summary(self):
        """In summary kết quả"""
        total = self.passed + self.failed
        logger.info("=" * 50)
        logger.info("SMOKE TEST SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {self.passed}")
        logger.info(f"Failed: {self.failed}")

        if self.failed == 0:
            logger.info("ALL TESTS PASSED!")
        else:
            logger.warning(f"{self.failed} test(s) failed")

        logger.info("=" * 50)


async def main():
    """Main smoke test entry point"""
    # Setup logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

    logger.info(f"PVCFC RAG API Smoke Test")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"API Port: {settings.api_port}")
    logger.info("")

    # Run tests
    smoke_test = SmokeTest()
    results = await smoke_test.run_all_tests()

    # Exit code
    exit_code = 0 if results["failed"] == 0 else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
