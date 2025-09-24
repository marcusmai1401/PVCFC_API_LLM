#!/usr/bin/env python3
"""
Test live API endpoints
Run this AFTER starting the server with: python -m app.main
"""

import json
import sys

import requests

BASE_URL = "http://localhost:8000"


def test_endpoints():
    """Test all endpoints"""
    print("\n" + "=" * 60)
    print("  TESTING LIVE API ENDPOINTS")
    print("=" * 60)

    # 1. Health check
    print("\n1. Testing /healthz...")
    try:
        resp = requests.get(f"{BASE_URL}/healthz", timeout=5)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Environment: {data.get('app_env')}")
            print(f"   LLM Ready: {data.get('llm_provider_ready')}")
            print("   ✅ Health check passed")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        print("\n⚠️  Is the server running? Start with: python -m app.main")
        return False

    # 2. Metrics
    print("\n2. Testing /metrics...")
    try:
        resp = requests.get(f"{BASE_URL}/metrics", timeout=5)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"   Response size: {len(resp.text)} bytes")
            print("   ✅ Metrics endpoint working")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # 3. Index stats
    print("\n3. Testing /index-stats...")
    try:
        resp = requests.get(f"{BASE_URL}/index-stats", timeout=5)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   BM25 docs: {data.get('bm25', {}).get('doc_count', 0)}")
            print(f"   FAISS vectors: {data.get('faiss', {}).get('vector_count', 0)}")
            print("   ✅ Index stats working")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # 4. Ask endpoint
    print("\n4. Testing /ask...")
    try:
        resp = requests.post(
            f"{BASE_URL}/ask",
            json={
                "query": "What is the operating pressure of KT06101?",
                "hyde": False,
                "max_context": 5,
                "execution_mode": "light_only",
            },
            timeout=30,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Answer length: {len(data.get('answer', ''))} chars")
            print(f"   Citations: {len(data.get('citations', []))}")
            print(f"   Confidence: {data.get('confidence', 0):.2f}")
            print(f"   Latency: {data.get('meta', {}).get('latency_ms', 0)} ms")
            print("   ✅ Ask endpoint working")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # 5. Locate endpoint
    print("\n5. Testing /locate...")
    try:
        resp = requests.post(
            f"{BASE_URL}/locate", json={"query": "KT06101", "max_hits": 5}, timeout=15
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Hits found: {data.get('total_found', 0)}")
            print(f"   Latency: {data.get('meta', {}).get('latency_ms', 0)} ms")
            print("   ✅ Locate endpoint working")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # 6. Report endpoint
    print("\n6. Testing /report...")
    try:
        resp = requests.post(
            f"{BASE_URL}/report",
            json={
                "topic": "Operating parameters",
                "sub_queries": ["pressure", "temperature"],
                "format": "markdown",
            },
            timeout=45,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Sections: {len(data.get('sections', []))}")
            print(
                f"   Total citations: {data.get('meta', {}).get('total_citations', 0)}"
            )
            print(f"   Latency: {data.get('meta', {}).get('total_latency_ms', 0)} ms")
            print("   ✅ Report endpoint working")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    print("\n" + "=" * 60)
    print("  ✅ API TESTING COMPLETE!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_endpoints()
    sys.exit(0 if success else 1)
