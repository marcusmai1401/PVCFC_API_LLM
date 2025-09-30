#!/usr/bin/env python
"""
Test script để kiểm tra System Status implementation
- Gọi API /healthz và /index-stats
- Hiển thị số liệu doc/chunk/dimension
"""

import json
from pathlib import Path

import requests


def test_api_endpoints():
    """Test API endpoints are accessible"""
    base_url = "http://localhost:8000"
    results = {}

    print("=" * 60)
    print("TESTING API ENDPOINTS")
    print("=" * 60)

    # Test /healthz
    try:
        response = requests.get(f"{base_url}/healthz", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            results["healthz"] = True
            print("✅ /healthz endpoint is working")
            print(f"   Status: {health_data.get('status', 'unknown')}")
            print(f"   Version: {health_data.get('version', 'unknown')}")
            print(f"   Environment: {health_data.get('app_env', 'unknown')}")
            print(f"   LLM Provider: {health_data.get('llm_provider', 'unknown')}")
            print(f"   LLM Ready: {health_data.get('llm_provider_ready', False)}")
            print(f"   Uptime: {health_data.get('uptime_human', 'unknown')}")
        else:
            results["healthz"] = False
            print(f"❌ /healthz returned status {response.status_code}")
    except Exception as e:
        results["healthz"] = False
        print(f"❌ /healthz failed: {e}")

    print()

    # Test /index-stats
    try:
        response = requests.get(f"{base_url}/index-stats", timeout=5)
        if response.status_code == 200:
            stats_data = response.json()
            results["index-stats"] = True
            print("✅ /index-stats endpoint is working")

            # Check different formats
            if "bm25_documents" in stats_data:
                # Retriever format
                print(f"   BM25 Documents: {stats_data.get('bm25_documents', 0):,}")
                print(f"   FAISS Documents: {stats_data.get('faiss_documents', 0):,}")
                config = stats_data.get("config", {})
                print(
                    f"   Config: k_bm25={config.get('k_bm25')}, k_faiss={config.get('k_faiss')}"
                )
            elif "bm25" in stats_data:
                # Index manager format
                bm25 = stats_data.get("bm25", {})
                faiss = stats_data.get("faiss", {})
                print(f"   BM25 Loaded: {bm25.get('loaded', False)}")
                print(f"   BM25 Docs: {bm25.get('doc_count', 0):,}")
                print(f"   FAISS Loaded: {faiss.get('loaded', False)}")
                print(f"   FAISS Vectors: {faiss.get('vector_count', 0):,}")
                print(f"   Vector Dimension: {faiss.get('dimension', 0)}")
            else:
                print("   (Unexpected format, see raw data)")
                print(json.dumps(stats_data, indent=2)[:500])
        else:
            results["index-stats"] = False
            print(f"❌ /index-stats returned status {response.status_code}")
    except Exception as e:
        results["index-stats"] = False
        print(f"❌ /index-stats failed: {e}")

    return results


def test_ui_component():
    """Test System Status UI component exists"""
    print("\n" + "=" * 60)
    print("TESTING UI COMPONENTS")
    print("=" * 60)

    tests = {
        "system_status.py exists": Path(
            "streamlit_app/components/system_status.py"
        ).exists(),
        "Uses /healthz endpoint": False,
        "Uses /index-stats endpoint": False,
        "render_system_status function": False,
        "render_compact_status function": False,
        "app.py updated": False,
    }

    # Check component file content
    component_file = Path("streamlit_app/components/system_status.py")
    if component_file.exists():
        content = component_file.read_text(encoding="utf-8")
        tests["Uses /healthz endpoint"] = "/healthz" in content
        tests["Uses /index-stats endpoint"] = "/index-stats" in content
        tests["render_system_status function"] = "def render_system_status" in content
        tests["render_compact_status function"] = "def render_compact_status" in content

    # Check app.py is updated
    app_file = Path("streamlit_app/app.py")
    if app_file.exists():
        content = app_file.read_text(encoding="utf-8")
        tests["app.py updated"] = "render_compact_status" in content

    for test_name, passed in tests.items():
        status = "✅" if passed else "❌"
        print(f"{status} {test_name}")

    return all(tests.values())


def test_integration():
    """Test that UI can fetch and display data from API"""
    print("\n" + "=" * 60)
    print("INTEGRATION TEST")
    print("=" * 60)

    # This would require running Streamlit, so we'll do a simulated test
    try:
        # Import the component
        import sys

        sys.path.append(".")
        from streamlit_app.components.system_status import (
            fetch_health_status,
            fetch_index_stats,
        )

        # Test fetch functions
        health = fetch_health_status("http://localhost:8000", timeout=2)
        index = fetch_index_stats("http://localhost:8000", timeout=2)

        if health.get("success"):
            print("✅ fetch_health_status() works")
            print(f"   Response time: {health.get('response_time_ms', 0):.0f}ms")
        else:
            print(f"⚠️ fetch_health_status() failed: {health.get('error')}")

        if index.get("success"):
            print("✅ fetch_index_stats() works")
            print(f"   Response time: {index.get('response_time_ms', 0):.0f}ms")
        else:
            print(f"⚠️ fetch_index_stats() failed: {index.get('error')}")

        return health.get("success") or index.get("success")

    except Exception as e:
        print(f"⚠️ Integration test failed: {e}")
        print("  (This is expected if API is not running)")
        return False


if __name__ == "__main__":
    print("🔍 TESTING SYSTEM STATUS IMPLEMENTATION\n")

    # Run tests
    api_working = test_api_endpoints()
    ui_ready = test_ui_component()
    integration_ok = test_integration()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if ui_ready:
        print("✅ System Status UI components are ready")
    else:
        print("❌ System Status UI components incomplete")

    if api_working.get("healthz") and api_working.get("index-stats"):
        print("✅ API endpoints are working")
    else:
        print("⚠️ API endpoints not fully accessible")
        print("  Run: python -m uvicorn app.main:app --port 8000")

    if integration_ok:
        print("✅ Integration between UI and API works")
    else:
        print("⚠️ Integration test failed (API may be offline)")

    print("\nNext steps:")
    print("1. Start API: python -m uvicorn app.main:app --port 8000")
    print("2. Start UI: streamlit run streamlit_app/app.py --server.port 8502")
    print("3. Check System Status in sidebar")
    print("4. Navigate to pages/system_status_page for full dashboard")
