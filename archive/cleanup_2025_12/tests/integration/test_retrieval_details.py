"""
Test script for retrieval/reranking details fix.
Tests that details are populated even on cache hit.
"""
import json
import time

import requests

API_URL = "http://127.0.0.1:8000"


def check_api_health():
    """Check if API is running."""
    try:
        response = requests.get(f"{API_URL}/healthz", timeout=5)
        return response.status_code == 200
    except:
        return False


def clear_cache():
    """Clear retrieval cache."""
    try:
        response = requests.delete(f"{API_URL}/cache/clear", timeout=5)
        return response.status_code == 200
    except:
        return False


def test_retrieval_details():
    """Test retrieval/reranking details population."""
    print("\n" + "=" * 80)
    print("🧪 TESTING RETRIEVAL & RERANKING DETAILS FIX")
    print("=" * 80)

    # Check API
    if not check_api_health():
        print("❌ API is not running!")
        print("\nPlease start the API first: .\\start_api.ps1")
        return

    print("✅ API is running\n")

    # Clear cache to start fresh
    print("🗑️  Clearing cache...")
    if clear_cache():
        print("✅ Cache cleared\n")
    else:
        print("⚠️  Could not clear cache (endpoint may not exist)\n")

    test_query = {
        "query": "What is the maximum operating pressure?",
        "max_context": 8,
        "execution_mode": "production",
        "language": "en",
        "hyde": False,
    }

    # Test 1: Cache MISS (first request)
    print("=" * 80)
    print("TEST 1: Cache MISS (First Request)")
    print("=" * 80)
    print(f"📝 Query: {test_query['query']}\n")

    start = time.time()
    response1 = requests.post(f"{API_URL}/ask", json=test_query, timeout=60)
    elapsed1 = time.time() - start

    if response1.status_code != 200:
        print(f"❌ Request failed: {response1.status_code}")
        print(response1.text)
        return

    result1 = response1.json()
    print(f"✅ Request completed in {elapsed1:.1f}s\n")

    # Check meta
    meta1 = result1.get("meta", {})
    print(f"📊 Metadata:")
    print(f"   Cache Hit: {meta1.get('cache_hit', False)}")
    print(f"   Retrieve Time: {meta1.get('breakdown', {}).get('retrieve_ms', 0)}ms")
    print(f"   Rerank Time: {meta1.get('breakdown', {}).get('rerank_ms', 0)}ms")

    # Check retrieval_details
    retrieval_details1 = result1.get("retrieval_details")
    print(f"\n🔍 Retrieval Details:")
    if retrieval_details1:
        print(f"   ✅ EXISTS")
        print(f"   Total Retrieved: {retrieval_details1.get('total_retrieved', 0)}")
        print(f"   BM25 docs: {len(retrieval_details1.get('bm25', []))}")
        print(f"   FAISS docs: {len(retrieval_details1.get('faiss', []))}")
        print(f"   From Cache: {retrieval_details1.get('from_cache', False)}")
    else:
        print(f"   ❌ MISSING")

    # Check reranking_details
    reranking_details1 = result1.get("reranking_details")
    print(f"\n📊 Reranking Details:")
    if reranking_details1:
        print(f"   ✅ EXISTS")
        print(f"   Method: {reranking_details1.get('method', 'N/A')}")
        print(f"   Input Count: {reranking_details1.get('input_count', 0)}")
        print(f"   Output Count: {reranking_details1.get('output_count', 0)}")
        print(f"   Results: {len(reranking_details1.get('results', []))}")
        print(f"   From Cache: {reranking_details1.get('from_cache', False)}")
    else:
        print(f"   ❌ MISSING")

    # Verdict for Test 1
    print(f"\n🎯 TEST 1 VERDICT:")
    if retrieval_details1 and reranking_details1:
        if not retrieval_details1.get("from_cache") and not reranking_details1.get(
            "from_cache"
        ):
            print("✅ PASS: Both details present with from_cache=False")
        else:
            print("⚠️  UNEXPECTED: from_cache should be False on first request")
    else:
        print("❌ FAIL: Details missing on cache miss")

    # Wait a bit
    time.sleep(2)

    # Test 2: Cache HIT (second request)
    print("\n" + "=" * 80)
    print("TEST 2: Cache HIT (Second Request)")
    print("=" * 80)
    print(f"📝 Query: {test_query['query']} (same as before)\n")

    start = time.time()
    response2 = requests.post(f"{API_URL}/ask", json=test_query, timeout=60)
    elapsed2 = time.time() - start

    if response2.status_code != 200:
        print(f"❌ Request failed: {response2.status_code}")
        print(response2.text)
        return

    result2 = response2.json()
    print(f"✅ Request completed in {elapsed2:.1f}s\n")

    # Check meta
    meta2 = result2.get("meta", {})
    print(f"📊 Metadata:")
    print(f"   Cache Hit: {meta2.get('cache_hit', False)}")
    print(f"   Retrieve Time: {meta2.get('breakdown', {}).get('retrieve_ms', 0)}ms")
    print(f"   Rerank Time: {meta2.get('breakdown', {}).get('rerank_ms', 0)}ms")

    # Check retrieval_details
    retrieval_details2 = result2.get("retrieval_details")
    print(f"\n🔍 Retrieval Details:")
    if retrieval_details2:
        print(f"   ✅ EXISTS")
        print(f"   Total Retrieved: {retrieval_details2.get('total_retrieved', 0)}")
        print(f"   BM25 docs: {len(retrieval_details2.get('bm25', []))}")
        print(f"   FAISS docs: {len(retrieval_details2.get('faiss', []))}")
        print(f"   From Cache: {retrieval_details2.get('from_cache', False)}")
    else:
        print(f"   ❌ MISSING (THIS IS THE BUG!)")

    # Check reranking_details
    reranking_details2 = result2.get("reranking_details")
    print(f"\n📊 Reranking Details:")
    if reranking_details2:
        print(f"   ✅ EXISTS")
        print(f"   Method: {reranking_details2.get('method', 'N/A')}")
        print(f"   Input Count: {reranking_details2.get('input_count', 0)}")
        print(f"   Output Count: {reranking_details2.get('output_count', 0)}")
        print(f"   Results: {len(reranking_details2.get('results', []))}")
        print(f"   From Cache: {reranking_details2.get('from_cache', False)}")
    else:
        print(f"   ❌ MISSING (THIS IS THE BUG!)")

    # Verdict for Test 2
    print(f"\n🎯 TEST 2 VERDICT:")
    if retrieval_details2 and reranking_details2:
        if retrieval_details2.get("from_cache") and reranking_details2.get(
            "from_cache"
        ):
            print("✅ PASS: Both details present with from_cache=True")
            print("   → Fix is working! Details populated even on cache hit")
        else:
            print("⚠️  PARTIAL: Details present but from_cache flag incorrect")
    else:
        print("❌ FAIL: Details missing on cache hit")
        print("   → Fix NOT applied yet, or API needs restart")

    # Overall summary
    print("\n" + "=" * 80)
    print("📊 OVERALL TEST SUMMARY")
    print("=" * 80)

    test1_pass = retrieval_details1 is not None and reranking_details1 is not None
    test2_pass = retrieval_details2 is not None and reranking_details2 is not None

    if test1_pass and test2_pass:
        print("✅ ALL TESTS PASSED!")
        print("   → Retrieval & reranking details always populated")
        print("   → from_cache flag correctly indicates source")
        print("\n🎉 Fix is working correctly!")
    elif test1_pass and not test2_pass:
        print("⚠️  PARTIAL SUCCESS")
        print("   → Test 1 (cache miss): PASS")
        print("   → Test 2 (cache hit): FAIL")
        print("\n❌ Fix NOT working - details still missing on cache hit")
        print("   Please ensure API has been restarted with new code")
    else:
        print("❌ TESTS FAILED")
        print("   Unexpected behavior - please check API logs")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_retrieval_details()

    print("\n💡 Next Steps:")
    print("   - If tests passed, verify UI displays correctly")
    print("   - If tests failed, restart API and try again")
    print("   - Check API logs for any errors")
