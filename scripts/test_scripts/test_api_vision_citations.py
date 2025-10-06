"""
Test API request to verify vision citations point to correct pages
"""

import json

import requests

API_URL = "http://127.0.0.1:8000/ask"


def test_vision_citations():
    """Send test query and check citations"""

    # Test query about torque table
    payload = {
        "query": "During the installation procedure for the condensing turbine, after the back grouting has been finished for at least 72 hours, according to Table: Tightened torque for anchor bolt, what is the specified final tightening torque for an M42 anchor bolt?",
        "max_context": 20,
        "language": "en",
        "hyde": True,
        "execution_mode": "production",
        "confidence_mode": "calibrated",
        "enable_vision_generation": True,
    }

    print("Sending request to API...")
    print(f"Query: {payload['query'][:100]}...")

    response = requests.post(API_URL, json=payload)

    if response.status_code != 200:
        print(f"❌ API request failed: {response.status_code}")
        print(response.text)
        return

    data = response.json()

    print("\n" + "=" * 80)
    print("ANSWER:")
    print("=" * 80)
    print(data.get("answer", "No answer"))

    print("\n" + "=" * 80)
    print("CITATIONS:")
    print("=" * 80)

    citations = data.get("citations", [])
    if not citations:
        print("No citations found!")
        return

    import os

    for i, citation in enumerate(citations, 1):
        print(f"\n[{i}] Doc ID: {citation.get('doc_id', 'unknown')}")
        print(f"    Page: {citation.get('page', 'unknown')}")
        if "pdf_path" in citation and citation["pdf_path"]:
            filename = os.path.basename(citation["pdf_path"])
            print(f"    PDF: {filename}")
        else:
            print(f"    PDF: (not provided)")

    # Check if vision was used
    meta = data.get("meta", {})
    vision_meta = meta.get("vision_generation")

    if vision_meta:
        print("\n" + "=" * 80)
        print("VISION METADATA:")
        print("=" * 80)
        pages_used = vision_meta.get("pages_used", [])
        print(f"Vision pages used: {len(pages_used)}")
        for page_info in pages_used[:5]:
            filename = os.path.basename(page_info.get("pdf_path", ""))
            page_num = page_info.get("page", "?")
            print(f"  - {filename}, page {page_num}")

        # Validation
        print("\n" + "=" * 80)
        print("VALIDATION:")
        print("=" * 80)

        # Check if any citation points to KT06101_Installation instruction.pdf
        found_installation_doc = False
        for citation in citations:
            if "pdf_path" in citation and citation["pdf_path"]:
                if "Installation instruction" in citation["pdf_path"]:
                    found_installation_doc = True
                    print(
                        f"✓ Found citation to Installation instruction.pdf, page {citation.get('page')}"
                    )
                    break

        if not found_installation_doc:
            print("⚠ No citation to Installation instruction.pdf found")
            print("Citations point to:")
            for citation in citations[:3]:
                if "pdf_path" in citation and citation["pdf_path"]:
                    filename = os.path.basename(citation["pdf_path"])
                    print(f"  - {filename}, page {citation.get('page')}")
    else:
        print("\n⚠ Vision was NOT used (check if vision is enabled)")

    print("\n" + "=" * 80)
    print(f"Confidence: {data.get('confidence', 'unknown')}")
    print(f"Execution mode: {meta.get('execution_mode', 'unknown')}")


if __name__ == "__main__":
    try:
        test_vision_citations()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
