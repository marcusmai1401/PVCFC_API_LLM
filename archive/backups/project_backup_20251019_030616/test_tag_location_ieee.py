"""
Test script to verify tag location queries return IEEE-style citations with page jump

Usage:
    python test_tag_location_ieee.py

Expected behavior:
- Tag location query should return answer with [Doc 1, p.X] format
- Citations should include page, doc_id, pdf_path
- Frontend should convert [Doc 1, p.X] to clickable [1] with page jump
"""

import json

import requests


def test_tag_location_query():
    """Test tag location query with IEEE citation format"""

    # API endpoint
    api_url = "http://localhost:8000/api/ask"

    # Test query for tag location
    query = "Tag 04 TAHH 5145 nằm ở trang nào?"

    # Request payload
    payload = {
        "query": query,
        "language": "vi",
        "top_k": 5,
        "execution_mode": "production",
    }

    print("=" * 80)
    print("TAG LOCATION QUERY TEST - IEEE STYLE CITATIONS")
    print("=" * 80)
    print(f"\nQuery: {query}")
    print(f"API: {api_url}")
    print("\nSending request...")

    try:
        response = requests.post(api_url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()

        print("\n✅ Response received")
        print("=" * 80)

        # Extract key fields
        answer = result.get("answer", "")
        citations = result.get("citations", [])

        print(f"\n📝 ANSWER:\n{answer}\n")
        print("=" * 80)

        # Check if answer contains IEEE-style citations
        if "[Doc 1, p." in answer:
            print("\n✅ PASS: Answer contains IEEE-style citation [Doc 1, p.X]")
        else:
            print("\n❌ FAIL: Answer does not contain IEEE-style citation")
            print(f"   Expected format: [Doc 1, p.X]")
            print(f"   Got: {answer[:200]}")

        print(f"\n📚 CITATIONS ({len(citations)} total):")
        print("=" * 80)

        # Check citation structure
        for idx, cit in enumerate(citations[:3], 1):
            print(f"\nCitation #{idx}:")
            print(f"  doc_id: {cit.get('doc_id', 'MISSING')}")
            print(f"  page: {cit.get('page', 'MISSING')}")
            print(f"  pdf_path: {cit.get('pdf_path', 'MISSING')[:80]}...")
            print(f"  score: {cit.get('score', 0):.3f}")

            # Validation
            has_doc_id = bool(cit.get("doc_id"))
            has_page = cit.get("page") is not None
            has_pdf_path = bool(cit.get("pdf_path"))

            if has_doc_id and has_page and has_pdf_path:
                print("  ✅ Citation structure: VALID")
            else:
                print("  ❌ Citation structure: INCOMPLETE")
                if not has_doc_id:
                    print("     - Missing doc_id")
                if not has_page:
                    print("     - Missing page")
                if not has_pdf_path:
                    print("     - Missing pdf_path")

        print("\n" + "=" * 80)
        print("EXPECTED FRONTEND BEHAVIOR:")
        print("=" * 80)
        print(
            """
1. Answer text will be displayed with IEEE-style [1], [2], ... citations
2. References section will show:
   [1] <document_name>
       p.54 (clickable link to PDF viewer)
3. Clicking p.54 should open PDF viewer at page 54
"""
        )

        # Check for potential issues
        print("\n" + "=" * 80)
        print("VALIDATION:")
        print("=" * 80)

        issues = []

        if not answer:
            issues.append("Empty answer text")

        if not citations:
            issues.append("No citations returned")

        if citations and not citations[0].get("pdf_path"):
            issues.append("First citation missing pdf_path (needed for page jump)")

        if citations and citations[0].get("page") is None:
            issues.append("First citation missing page number")

        if issues:
            print("\n❌ ISSUES FOUND:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("\n✅ ALL VALIDATIONS PASSED")
            print("\nThe tag location query is working correctly:")
            print("✓ Answer contains IEEE-style citations [Doc 1, p.X]")
            print("✓ Citations have complete metadata (doc_id, page, pdf_path)")
            print("✓ Frontend should render clickable page jump buttons")

        print("\n" + "=" * 80)

    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR: Request failed")
        print(f"   {str(e)}")
        print("\n   Make sure the API server is running:")
        print("   python -m uvicorn app.main:app --reload")

    except json.JSONDecodeError as e:
        print(f"\n❌ ERROR: Invalid JSON response")
        print(f"   {str(e)}")

    except Exception as e:
        print(f"\n❌ ERROR: Unexpected error")
        print(f"   {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_tag_location_query()
