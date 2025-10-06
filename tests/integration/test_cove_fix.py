"""
Test script for CoVe warnings fix.
Tests the same question that previously showed false warnings.
"""
import json
import time
from typing import Any, Dict

import requests

API_URL = "http://127.0.0.1:8000"


def check_api_health() -> bool:
    """Check if API is running."""
    try:
        response = requests.get(f"{API_URL}/healthz", timeout=5)
        return response.status_code == 200
    except:
        return False


def wait_for_api(max_wait: int = 30) -> bool:
    """Wait for API to be ready."""
    print("⏳ Waiting for API to be ready...")
    for i in range(max_wait):
        if check_api_health():
            print("✅ API is ready!")
            return True
        print(f"   Attempt {i+1}/{max_wait}...", end="\r")
        time.sleep(1)
    print(f"\n❌ API not ready after {max_wait} seconds")
    return False


def test_cove_fix():
    """Test the CoVe warnings fix."""
    print("\n" + "=" * 80)
    print("🧪 TESTING COVE WARNINGS FIX")
    print("=" * 80)

    # Check API health
    if not check_api_health():
        print("❌ API is not running!")
        print("\nPlease start the API first:")
        print("  .\\start_api.ps1")
        return

    print("✅ API is running\n")

    # Test question (same as before)
    test_request = {
        "query": "To achieve the rated power of 11040 kW under normal work conditions, what are the specified operating conditions?",
        "max_context": 8,
        "execution_mode": "production",
        "language": "en",
        "hyde": False,
    }

    print("📝 Test Question:")
    print(f"   {test_request['query'][:80]}...")
    print(f"\n🚀 Sending request to /ask endpoint...")

    start_time = time.time()

    try:
        response = requests.post(f"{API_URL}/ask", json=test_request, timeout=60)

        elapsed_time = time.time() - start_time

        if response.status_code != 200:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return

        result = response.json()

        print(f"✅ Request completed in {elapsed_time:.1f}s\n")

        # Print results
        print("=" * 80)
        print("📊 RESULTS")
        print("=" * 80)

        # 1. Answer preview
        answer = result.get("answer", "")
        print(f"\n📄 Answer (first 200 chars):")
        print(f"   {answer[:200]}...")

        # 2. Confidence
        confidence = result.get("confidence", 0)
        print(f"\n💯 Overall Confidence: {confidence*100:.0f}%")

        # 3. Citations
        citations = result.get("citations", [])
        print(f"\n📚 Citations: {len(citations)} found")
        if citations:
            for i, cit in enumerate(citations[:3], 1):
                print(f"   {i}. Doc: {cit.get('doc_id', 'N/A')[:50]}...")
                print(f"      Page: {cit.get('page', 'N/A')}")
                if cit.get("pdf_path"):
                    print(f"      PDF: {cit['pdf_path'][-60:]}...")

        # 4. Warnings - THIS IS THE KEY CHECK
        warnings = result.get("warnings", [])
        print(f"\n⚠️  CoVe Warnings: {len(warnings) if warnings else 0}")

        if warnings:
            print("   WARNINGS FOUND:")
            for i, warning in enumerate(warnings, 1):
                print(f"   {i}. {warning}")
        else:
            print("   ✅ NO WARNINGS (Expected for high-confidence vision answers)")

        # 5. Meta information
        meta = result.get("meta", {})
        print(f"\n📈 Metadata:")
        print(f"   Latency: {meta.get('latency_ms', 0)}ms")
        print(f"   Model: {meta.get('model_generation', 'N/A')}")
        print(f"   Cache Hit: {meta.get('cache_hit', False)}")

        # Vision generation info
        vision_gen = meta.get("vision_generation")
        if vision_gen:
            print(f"   Vision Pages Used: {len(vision_gen.get('pages_used', []))}")
            print(f"   Vision Pages Failed: {len(vision_gen.get('pages_failed', []))}")

        # Timing breakdown
        breakdown = meta.get("breakdown", {})
        if breakdown:
            print(f"\n⏱️  Timing Breakdown:")
            for key, value in breakdown.items():
                print(f"   {key}: {value}ms")

        # 6. Generation details
        gen_details = result.get("generation_details", {})
        if gen_details:
            print(f"\n🤖 Generation Details:")
            print(f"   Vision Enabled: {gen_details.get('vision_enabled', False)}")
            print(f"   CoVe Enabled: {gen_details.get('cove_enabled', False)}")

        # 7. VERDICT
        print("\n" + "=" * 80)
        print("🎯 TEST VERDICT")
        print("=" * 80)

        # Check if fix is working
        if confidence >= 0.9 and not warnings:
            print("✅ PASS: High confidence (≥90%) with NO warnings")
            print("   → CoVe smart warning logic is working correctly!")
        elif confidence >= 0.9 and warnings:
            print("⚠️  UNEXPECTED: High confidence but warnings still present")
            print("   → CoVe logic may need adjustment")
        elif confidence < 0.7 and warnings:
            print("✅ PASS: Low confidence with warnings")
            print("   → This is expected behavior")
        else:
            print("ℹ️  INFO: Medium confidence scenario")
            print(
                f"   Confidence: {confidence*100:.0f}%, Warnings: {len(warnings) if warnings else 0}"
            )

        print("\n" + "=" * 80)

    except requests.exceptions.Timeout:
        print("❌ Request timed out after 60 seconds")
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_cove_fix()

    print("\n💡 Tips:")
    print("   - If warnings still appear with high confidence, check API logs")
    print("   - Look for: 'global_conf=X.XX, verification_rate=X%' in logs")
    print("   - Try clearing cache and testing again if needed")
