#!/usr/bin/env python3
"""
Test script to verify Priority 1 fixes:
1. UI defaults (vision + embedding enabled)
2. Index configuration (new index location)
3. API response debug fields
"""
import json
import sys
import time
from pathlib import Path

import requests


def print_header(text: str):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     {details}")


def test_config_settings():
    """Test 1: Verify config settings"""
    print_header("TEST 1: Config Settings")

    try:
        from app.core.config import Settings

        settings = Settings()

        # Check index_dir
        has_index_dir = hasattr(settings, "index_dir")
        correct_value = settings.index_dir == "data/indexes" if has_index_dir else False

        print_result(
            "Settings has index_dir field",
            has_index_dir,
            f"index_dir = {settings.index_dir if has_index_dir else 'NOT FOUND'}",
        )
        print_result(
            "index_dir points to data/indexes",
            correct_value,
            f"Expected: 'data/indexes', Got: '{settings.index_dir if has_index_dir else 'N/A'}'",
        )

        return has_index_dir and correct_value

    except Exception as e:
        print_result("Config settings test", False, f"Error: {e}")
        return False


def test_index_paths():
    """Test 2: Verify index paths exist"""
    print_header("TEST 2: Index Paths")

    try:
        import app
        from app.core.config import Settings

        settings = Settings()
        project_root = Path(app.__file__).parent.parent
        index_base = project_root / settings.index_dir

        bm25_path = index_base / "bm25"
        faiss_path = index_base / "faiss_index"

        bm25_exists = bm25_path.exists()
        faiss_exists = faiss_path.exists()

        print_result(f"BM25 index exists at {bm25_path}", bm25_exists)
        print_result(f"FAISS index exists at {faiss_path}", faiss_exists)

        # Check for key files
        if bm25_exists:
            documents_json = bm25_path / "documents.json"
            print_result(
                "BM25 documents.json exists",
                documents_json.exists(),
                f"Path: {documents_json}",
            )

        if faiss_exists:
            faiss_index_file = faiss_path / "faiss.index"
            texts_json = faiss_path / "texts.json"
            metadata_json = faiss_path / "metadatas.json"

            print_result("FAISS index file exists", faiss_index_file.exists())
            print_result("FAISS texts.json exists", texts_json.exists())
            print_result("FAISS metadatas.json exists", metadata_json.exists())

        return bm25_exists and faiss_exists

    except Exception as e:
        print_result("Index paths test", False, f"Error: {e}")
        return False


def test_api_health(api_url: str = "http://localhost:8000"):
    """Test 3: Verify API is running"""
    print_header("TEST 3: API Health Check")

    try:
        response = requests.get(f"{api_url}/healthz", timeout=5)

        if response.status_code == 200:
            health_data = response.json()
            print_result(
                "API is running",
                True,
                f"Status: {health_data.get('status', 'unknown')}",
            )
            print_result(
                "LLM provider ready",
                health_data.get("llm_provider_ready", False),
                f"Provider: {health_data.get('llm_provider', 'unknown')}",
            )
            return True
        else:
            print_result(
                "API health check", False, f"Status code: {response.status_code}"
            )
            return False

    except requests.exceptions.ConnectionError:
        print_result(
            "API health check",
            False,
            "Cannot connect to API. Please start the API server first.",
        )
        return False
    except Exception as e:
        print_result("API health check", False, f"Error: {e}")
        return False


def test_index_stats(api_url: str = "http://localhost:8000"):
    """Test 4: Verify index statistics from API"""
    print_header("TEST 4: Index Statistics")

    try:
        response = requests.get(f"{api_url}/index-stats", timeout=5)

        if response.status_code == 200:
            stats = response.json()

            # Check BM25 stats
            bm25_stats = stats.get("bm25", {})
            bm25_loaded = bm25_stats.get("loaded", False)
            bm25_docs = bm25_stats.get("doc_count", 0)

            print_result("BM25 index loaded", bm25_loaded, f"Documents: {bm25_docs}")

            # Check FAISS stats
            faiss_stats = stats.get("faiss", {})
            faiss_loaded = faiss_stats.get("loaded", False)
            faiss_vectors = faiss_stats.get("vector_count", 0)

            print_result(
                "FAISS index loaded", faiss_loaded, f"Vectors: {faiss_vectors}"
            )

            # Check if using new index (should have ~9420 vectors)
            using_new_index = faiss_vectors > 9000
            print_result(
                "Using new index with 9420+ vectors",
                using_new_index,
                f"Expected: >9000, Got: {faiss_vectors}",
            )

            return bm25_loaded and faiss_loaded and using_new_index
        else:
            print_result("Index stats", False, f"Status code: {response.status_code}")
            return False

    except Exception as e:
        print_result("Index stats", False, f"Error: {e}")
        return False


def test_api_response_structure(api_url: str = "http://localhost:8000"):
    """Test 5: Verify API response has debug fields"""
    print_header("TEST 5: API Response Structure")

    try:
        # Send test query
        test_query = {
            "query": "What is the maximum operating pressure of KT06101?",
            "execution_mode": "production",
            "max_context": 8,
            "language": "en",
        }

        print("Sending test query to API...")
        response = requests.post(f"{api_url}/ask", json=test_query, timeout=60)

        if response.status_code == 200:
            data = response.json()

            # Check main fields
            has_answer = "answer" in data and len(data["answer"]) > 0
            has_citations = "citations" in data
            has_meta = "meta" in data

            print_result("Response has answer", has_answer)
            print_result("Response has citations", has_citations)
            print_result("Response has meta", has_meta)

            # Check NEW debug fields
            has_retrieval_details = "retrieval_details" in data
            has_reranking_details = "reranking_details" in data
            has_generation_details = "generation_details" in data

            print_result(
                "Response has retrieval_details",
                has_retrieval_details,
                f"Value: {'Present' if has_retrieval_details else 'Missing'}",
            )
            print_result(
                "Response has reranking_details",
                has_reranking_details,
                f"Value: {'Present' if has_reranking_details else 'Missing'}",
            )
            print_result(
                "Response has generation_details",
                has_generation_details,
                f"Value: {'Present' if has_generation_details else 'Missing'}",
            )

            # Check retrieval_details structure
            if has_retrieval_details and data["retrieval_details"]:
                retrieval = data["retrieval_details"]
                has_bm25 = "bm25" in retrieval
                has_faiss = "faiss" in retrieval

                print_result(
                    "retrieval_details has BM25 results",
                    has_bm25,
                    f"Count: {len(retrieval.get('bm25', []))}",
                )
                print_result(
                    "retrieval_details has FAISS results",
                    has_faiss,
                    f"Count: {len(retrieval.get('faiss', []))}",
                )

            # Check reranking_details structure
            if has_reranking_details and data["reranking_details"]:
                rerank = data["reranking_details"]
                has_method = "method" in rerank
                has_results = "results" in rerank

                print_result(
                    "reranking_details has method",
                    has_method,
                    f"Method: {rerank.get('method', 'N/A')}",
                )
                print_result(
                    "reranking_details has results",
                    has_results,
                    f"Count: {len(rerank.get('results', []))}",
                )

            # Check generation_details structure
            if has_generation_details and data["generation_details"]:
                gen = data["generation_details"]
                has_model = "model" in gen
                has_vision = "vision_enabled" in gen

                print_result(
                    "generation_details has model",
                    has_model,
                    f"Model: {gen.get('model', 'N/A')}",
                )
                print_result(
                    "generation_details has vision_enabled",
                    has_vision,
                    f"Vision: {gen.get('vision_enabled', False)}",
                )

            # Overall success
            all_debug_fields = (
                has_retrieval_details
                and has_reranking_details
                and has_generation_details
            )

            if all_debug_fields:
                print("\n📊 Sample response structure:")
                print(f"  Answer length: {len(data['answer'])} chars")
                print(f"  Citations: {len(data.get('citations', []))}")
                print(f"  Latency: {data.get('meta', {}).get('latency_ms', 0)}ms")
                if data.get("retrieval_details"):
                    print(
                        f"  BM25 results: {len(data['retrieval_details'].get('bm25', []))}"
                    )
                    print(
                        f"  FAISS results: {len(data['retrieval_details'].get('faiss', []))}"
                    )
                if data.get("reranking_details"):
                    print(
                        f"  Reranked results: {len(data['reranking_details'].get('results', []))}"
                    )

            return all_debug_fields

        else:
            print_result(
                "API query test",
                False,
                f"Status code: {response.status_code}, Error: {response.text[:200]}",
            )
            return False

    except Exception as e:
        print_result("API response structure test", False, f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_ui_defaults():
    """Test 6: Verify UI default settings"""
    print_header("TEST 6: UI Default Settings")

    try:
        # Read the UI app.py file to check defaults
        ui_app_path = Path(__file__).parent / "streamlit_app" / "app.py"

        if not ui_app_path.exists():
            print_result("UI app.py exists", False, f"Not found at {ui_app_path}")
            return False

        with open(ui_app_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for correct defaults
        vision_default_true = "st.session_state.enable_vision = True" in content
        embedding_default_true = "st.session_state.enable_embedding = True" in content

        print_result(
            "UI enables vision by default",
            vision_default_true,
            "Found: enable_vision = True",
        )
        print_result(
            "UI enables embedding by default",
            embedding_default_true,
            "Found: enable_embedding = True",
        )

        return vision_default_true and embedding_default_true

    except Exception as e:
        print_result("UI defaults test", False, f"Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "🔬" * 40)
    print("  PRIORITY 1 VERIFICATION TEST SUITE")
    print("🔬" * 40)

    results = {}

    # Test 1: Config settings
    results["config"] = test_config_settings()
    time.sleep(0.5)

    # Test 2: Index paths
    results["paths"] = test_index_paths()
    time.sleep(0.5)

    # Test 3: API health
    results["health"] = test_api_health()
    time.sleep(0.5)

    # Test 4: Index stats (only if API is running)
    if results["health"]:
        results["stats"] = test_index_stats()
        time.sleep(0.5)
    else:
        results["stats"] = False
        print_header("TEST 4: Index Statistics")
        print_result("Index stats", False, "Skipped - API not running")

    # Test 5: API response structure (only if API is running)
    if results["health"]:
        results["response"] = test_api_response_structure()
        time.sleep(0.5)
    else:
        results["response"] = False
        print_header("TEST 5: API Response Structure")
        print_result("API response test", False, "Skipped - API not running")

    # Test 6: UI defaults
    results["ui"] = test_ui_defaults()

    # Summary
    print_header("TEST SUMMARY")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print(f"\nTests passed: {passed}/{total}")
    print("\nDetailed results:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} | {test_name}")

    if passed == total:
        print("\n" + "🎉" * 40)
        print("  ALL TESTS PASSED!")
        print("  Priority 1 fixes verified successfully!")
        print("🎉" * 40)
        return 0
    else:
        print("\n" + "⚠️" * 40)
        print("  SOME TESTS FAILED")
        print(f"  Please review the failed tests above.")
        if not results["health"]:
            print("\n  💡 TIP: Start the API server with: .\\start_api.ps1")
        print("⚠️" * 40)
        return 1


if __name__ == "__main__":
    sys.exit(main())
