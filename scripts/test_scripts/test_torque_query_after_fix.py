"""
Test torque query với index đã được fix (Phase 1)
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("TESTING TORQUE QUERY AFTER PHASE 1 FIXES")
print("=" * 70)

# Test query
query = "What is the final tightened torque for M48 anchor bolt after back grouting finished for 72 hours?"

print(f"\nQuery: {query}\n")

# Call API
url = "http://localhost:8000/ask"
payload = {
    "question": query,
    "max_context": 20,
}

try:
    print("Sending request to API...")
    response = requests.post(url, json=payload, timeout=60)

    if response.status_code == 200:
        result = response.json()

        print("\n" + "=" * 70)
        print("RESPONSE")
        print("=" * 70)

        # Answer
        answer = result.get("answer", "")
        print(f"\nAnswer:\n{answer}\n")

        # Citations
        citations = result.get("citations", [])
        print(f"Citations ({len(citations)}):")
        for i, cite in enumerate(citations, 1):
            page = cite.get("page", "?")
            doc_id = cite.get("doc_id", "?")[:60]
            snippet = cite.get("text_snippet", "")[:100]
            print(f"\n  [{i}] Page {page}")
            print(f"      Doc: {doc_id}...")
            print(f"      Snippet: {snippet}...")

        # Verify
        print("\n" + "=" * 70)
        print("VERIFICATION")
        print("=" * 70)

        # Check if answer contains M48 value
        has_2150 = "2150" in answer
        has_m48 = "m48" in answer.lower()

        # Check if any citation points to page 15
        page_15_cited = any(c.get("page") == 15 for c in citations)

        print(f"\n✓ Answer contains '2150' (correct value): {has_2150}")
        print(f"✓ Answer mentions 'M48': {has_m48}")
        print(f"✓ Citations include page 15: {page_15_cited}")

        if has_2150 and page_15_cited:
            print("\n🎉 SUCCESS! Phase 1 fixes are working correctly!")
            print("   - Correct torque value found")
            print("   - Citations point to correct page")
        elif page_15_cited:
            print("\n⚠ PARTIAL SUCCESS!")
            print("   - Citations point to correct page ✓")
            print(
                "   - But answer might not have exact value (table extraction issue - Phase 2)"
            )
        else:
            print("\n✗ STILL ISSUES - Need investigation")

    else:
        print(f"\n✗ API Error: {response.status_code}")
        print(response.text)

except requests.exceptions.ConnectionError:
    print("\n✗ ERROR: Cannot connect to API server")
    print("   Please start the server first: .\\start_api.ps1")
except Exception as e:
    print(f"\n✗ ERROR: {e}")

print("\n" + "=" * 70)
