"""
Test script to verify PDF citations are working correctly
"""

import json

import requests


def test_pdf_citations(api_url="http://localhost:8000"):
    """Test that PDF citations include pdf_path"""

    print("=" * 80)
    print("  PRIORITY 2: PDF CITATIONS TEST")
    print("=" * 80)
    print()

    # Test 1: Check doc_id_map exists and has entries
    print("TEST 1: Checking doc_id_map file")
    print("-" * 80)
    try:
        import json
        from pathlib import Path

        doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
        if doc_id_map_path.exists():
            with open(doc_id_map_path, "r", encoding="utf-8") as f:
                doc_id_map = json.load(f)

            print(f"✅ doc_id_map.json exists")
            print(f"   Entries: {len(doc_id_map)}")

            # Show sample entry
            if doc_id_map:
                sample_key = list(doc_id_map.keys())[0]
                sample = doc_id_map[sample_key]
                print(f"\n   Sample entry:")
                print(f"   doc_id: {sample_key[:60]}...")
                if isinstance(sample, dict):
                    print(f"   file_name: {sample.get('file_name', 'N/A')}")
                    print(f"   pdf_path: {sample.get('pdf_path', 'N/A')}")
                    print(f"   doc_type: {sample.get('doc_type', 'N/A')}")
                else:
                    print(f"   pdf_path: {sample}")
        else:
            print("❌ doc_id_map.json not found")
            return False
    except Exception as e:
        print(f"❌ Error reading doc_id_map: {e}")
        return False

    print()

    # Test 2: Query API and check citations
    print("TEST 2: Checking API citations")
    print("-" * 80)

    test_query = {
        "query": "What is the maximum operating pressure of KT06101?",
        "execution_mode": "production",
        "max_context": 8,
        "language": "en",
    }

    try:
        print("Sending test query...")
        response = requests.post(f"{api_url}/ask", json=test_query, timeout=60)

        if response.status_code != 200:
            print(f"❌ API returned status {response.status_code}")
            return False

        data = response.json()
        citations = data.get("citations", [])

        print(f"✅ API responded successfully")
        print(f"   Citations count: {len(citations)}")

        if not citations:
            print("⚠️  No citations returned")
            return False

        # Check citation structure
        print(f"\n   Analyzing citations...")
        citations_with_pdf_path = 0
        citations_without_pdf_path = 0

        for i, citation in enumerate(citations[:3]):  # Check first 3
            doc_id = citation.get("doc_id", "unknown")
            pdf_path = citation.get("pdf_path")
            page = citation.get("page", "unknown")

            print(f"\n   Citation {i+1}:")
            print(
                f"      doc_id: {doc_id[:60]}..."
                if len(doc_id) > 60
                else f"      doc_id: {doc_id}"
            )
            print(f"      page: {page}")

            if pdf_path:
                print(f"      pdf_path: ✅ {pdf_path}")
                citations_with_pdf_path += 1
            else:
                print(f"      pdf_path: ❌ None")
                citations_without_pdf_path += 1

        print(f"\n   Summary:")
        print(
            f"      Citations with pdf_path: {citations_with_pdf_path}/{len(citations)}"
        )
        print(
            f"      Citations without pdf_path: {citations_without_pdf_path}/{len(citations)}"
        )

        if citations_with_pdf_path > 0:
            print(f"\n✅ PASS: Citations now include pdf_path!")
            return True
        else:
            print(f"\n❌ FAIL: No citations have pdf_path")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()
    result = test_pdf_citations()

    print()
    print("=" * 80)
    if result:
        print("✅ PRIORITY 2 TEST PASSED!")
        print("   PDF citations are working correctly")
    else:
        print("❌ PRIORITY 2 TEST FAILED!")
        print("   PDF citations still not working")
    print("=" * 80)
    print()
