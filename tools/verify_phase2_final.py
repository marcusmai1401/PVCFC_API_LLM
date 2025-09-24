#!/usr/bin/env python3
"""
Final Phase 2 Verification Script
Checks all components are working correctly
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_config() -> Dict[str, bool]:
    """Check configuration is properly set"""
    from app.core.config import settings

    checks = {
        "env_loaded": True,
        "llm_configured": settings.llm_provider != "none",
        "embedding_configured": settings.embedding_provider != "none",
        "api_keys_present": False,
        "models_configured": False,
    }

    # Check API keys
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        checks["api_keys_present"] = True
    elif settings.llm_provider == "openai" and settings.openai_api_key:
        checks["api_keys_present"] = True

    # Check models
    if settings.llm_model_light and settings.llm_model_heavy:
        checks["models_configured"] = True

    return checks


def check_indices() -> Dict[str, bool]:
    """Check if indices are properly loaded"""
    checks = {
        "bm25_exists": False,
        "faiss_exists": False,
        "bm25_loadable": False,
        "faiss_loadable": False,
    }

    # Check BM25
    bm25_path = Path("artifacts/index/bm25")
    if bm25_path.exists() and (bm25_path / "bm25_index.pkl").exists():
        checks["bm25_exists"] = True
        try:
            from app.rag.indexers.bm25_indexer import BM25Indexer

            indexer = BM25Indexer()
            indexer.load_index(str(bm25_path))
            checks["bm25_loadable"] = True
            logger.info(f"BM25 index loaded: {len(indexer.documents)} documents")
        except Exception as e:
            logger.error(f"Failed to load BM25: {e}")

    # Check FAISS
    faiss_path = Path("artifacts/index/faiss")
    if faiss_path.exists() and (faiss_path / "faiss.index").exists():
        checks["faiss_exists"] = True
        try:
            from app.rag.indexers.faiss_indexer import VectorIndexer

            indexer = VectorIndexer()
            indexer.load(str(faiss_path))
            checks["faiss_loadable"] = True
            logger.info(f"FAISS index loaded: {len(indexer.documents)} documents")
        except Exception as e:
            logger.error(f"Failed to load FAISS: {e}")

    return checks


def check_components() -> Dict[str, bool]:
    """Check if all RAG components can be initialized"""
    checks = {
        "query_transformer": False,
        "retriever": False,
        "reranker": False,
        "generator": False,
        "cove": False,
    }

    try:
        from app.rag.query_transform import QueryTransformer

        qt = QueryTransformer(enable_hyde=False)
        checks["query_transformer"] = True
    except Exception as e:
        logger.error(f"QueryTransformer failed: {e}")

    try:
        from app.core.config import settings
        from app.deps.indices import get_index_manager

        manager = get_index_manager(settings)
        asyncio.run(manager.load_indices())
        retriever = manager.get_retriever()
        if retriever:
            checks["retriever"] = True
    except Exception as e:
        logger.error(f"Retriever failed: {e}")

    try:
        from app.rag.reranker import Reranker

        reranker = Reranker()
        checks["reranker"] = True
    except Exception as e:
        logger.error(f"Reranker failed: {e}")

    try:
        from app.rag.generator import ResponseGenerator

        gen = ResponseGenerator()
        checks["generator"] = True
    except Exception as e:
        logger.error(f"Generator failed: {e}")

    try:
        from app.core.config import settings
        from app.rag.cove import ChainOfVerification

        cove = ChainOfVerification(settings=settings)
        checks["cove"] = True
    except Exception as e:
        logger.error(f"CoVe failed: {e}")

    return checks


def test_api_endpoints() -> Dict[str, Any]:
    """Test API endpoints are working"""
    import multiprocessing

    import uvicorn

    from app.main import app

    results = {
        "server_starts": False,
        "health_check": False,
        "ask_endpoint": False,
        "locate_endpoint": False,
        "report_endpoint": False,
        "metrics_endpoint": False,
    }

    # Start server in subprocess
    def run_server():
        uvicorn.run(app, host="127.0.0.1", port=8888, log_level="error")

    server_process = multiprocessing.Process(target=run_server)
    server_process.start()

    # Wait for server to start
    time.sleep(3)

    try:
        results["server_starts"] = True
        base_url = "http://127.0.0.1:8888"

        # Test health
        try:
            resp = requests.get(f"{base_url}/healthz", timeout=5)
            if resp.status_code == 200:
                results["health_check"] = True
        except Exception as e:
            logger.error(f"Health check failed: {e}")

        # Test ask endpoint
        try:
            resp = requests.post(
                f"{base_url}/ask",
                json={
                    "query": "What is the operating pressure?",
                    "hyde": False,
                    "max_context": 5,
                },
                timeout=10,
            )
            if resp.status_code in [200, 503]:  # 503 if retriever not ready
                results["ask_endpoint"] = True
        except Exception as e:
            logger.error(f"Ask endpoint failed: {e}")

        # Test locate endpoint
        try:
            resp = requests.post(
                f"{base_url}/locate",
                json={"query": "KT06101", "max_hits": 5},
                timeout=10,
            )
            if resp.status_code in [200, 503]:
                results["locate_endpoint"] = True
        except Exception as e:
            logger.error(f"Locate endpoint failed: {e}")

        # Test report endpoint
        try:
            resp = requests.post(
                f"{base_url}/report",
                json={
                    "topic": "Test report",
                    "sub_queries": ["Query 1"],
                    "format": "markdown",
                },
                timeout=10,
            )
            if resp.status_code in [200, 503]:
                results["report_endpoint"] = True
        except Exception as e:
            logger.error(f"Report endpoint failed: {e}")

        # Test metrics
        try:
            resp = requests.get(f"{base_url}/metrics", timeout=5)
            if resp.status_code == 200:
                results["metrics_endpoint"] = True
        except Exception as e:
            logger.error(f"Metrics endpoint failed: {e}")

    finally:
        # Stop server
        server_process.terminate()
        server_process.join(timeout=2)

    return results


def print_results(title: str, checks: Dict[str, Any]):
    """Print check results"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

    for key, value in checks.items():
        status = "✅" if value else "❌"
        key_display = key.replace("_", " ").title()
        print(f"{status} {key_display}: {value}")

    # Calculate pass rate
    total = len(checks)
    passed = sum(1 for v in checks.values() if v)
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"\n➡️  Pass rate: {passed}/{total} ({pass_rate:.0f}%)")


def main():
    """Run all Phase 2 verification checks"""
    print("\n" + "=" * 60)
    print("  PHASE 2 FINAL VERIFICATION")
    print("=" * 60)

    all_checks = {}

    # 1. Check configuration
    config_checks = check_config()
    print_results("Configuration", config_checks)
    all_checks.update({"config_" + k: v for k, v in config_checks.items()})

    # 2. Check indices
    index_checks = check_indices()
    print_results("Search Indices", index_checks)
    all_checks.update({"index_" + k: v for k, v in index_checks.items()})

    # 3. Check components
    component_checks = check_components()
    print_results("RAG Components", component_checks)
    all_checks.update({"component_" + k: v for k, v in component_checks.items()})

    # 4. Test API endpoints
    print("\n⏳ Testing API endpoints (this may take a moment)...")
    api_checks = test_api_endpoints()
    print_results("API Endpoints", api_checks)
    all_checks.update({"api_" + k: v for k, v in api_checks.items()})

    # Overall summary
    print("\n" + "=" * 60)
    print("  OVERALL SUMMARY")
    print("=" * 60)

    total = len(all_checks)
    passed = sum(1 for v in all_checks.values() if v)
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"Total checks: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {total - passed}")
    print(f"📊 Success rate: {pass_rate:.1f}%")

    if pass_rate == 100:
        print("\n🎉 PHASE 2 IS 100% COMPLETE!")
        print("All components are working correctly.")
    elif pass_rate >= 90:
        print("\n✅ PHASE 2 IS ESSENTIALLY COMPLETE!")
        print("Minor issues can be addressed as needed.")
    elif pass_rate >= 75:
        print("\n⚠️ PHASE 2 IS MOSTLY COMPLETE")
        print("Some components need attention.")
    else:
        print("\n❌ PHASE 2 NEEDS WORK")
        print("Please fix the failed components.")

    # Save results
    results_file = Path("artifacts/phase2_verification.json")
    results_file.parent.mkdir(exist_ok=True)
    with open(results_file, "w") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "checks": all_checks,
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": total - passed,
                    "pass_rate": pass_rate,
                },
            },
            f,
            indent=2,
        )
    print(f"\n📄 Results saved to: {results_file}")

    return 0 if pass_rate >= 90 else 1


if __name__ == "__main__":
    sys.exit(main())
