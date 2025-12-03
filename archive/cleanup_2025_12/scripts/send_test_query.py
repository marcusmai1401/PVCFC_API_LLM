"""
Send test query to running API server to debug citation accuracy
"""
import json

import requests

# API endpoint
API_URL = "http://localhost:8000/ask"

# The test query
query = """I need to configure the alarm settings for the temperature monitoring system on the steam turbine. According to the instrument list, there is a sensor with Tag No. 06-TE-0256 A/B.
Based on the provided documentation, what is the measurement point (i.e., the component being monitored) for this tag number, and what is its corresponding high-temperature alarm (A) setpoint?"""

# Expected answer for reference
print("=" * 80)
print("SENDING TEST QUERY TO API")
print("=" * 80)
print(f"\nQuery: {query}\n")
print("Expected Answer:")
print("  - Measurement Point: Rear Journal Bearing (后径向轴承)")
print("  - High-Temperature Alarm Setpoint: 105 °C")
print("  - Correct Sources: page 4 (measurement point) and page 6 (alarm setpoint)")
print("\n" + "=" * 80)
print("SENDING REQUEST...")
print("=" * 80 + "\n")

# Request payload
payload = {
    "query": query,
    "language": "en",
    "max_context": 10,
    "hyde": True,
    "execution_mode": "heavy_only",
    "confidence_mode": "calibrated",
    "enable_vision_generation": True,
}

try:
    # Send request
    response = requests.post(API_URL, json=payload, timeout=120)
    response.raise_for_status()

    result = response.json()

    # Display results
    print("\n" + "=" * 80)
    print("API RESPONSE RECEIVED")
    print("=" * 80 + "\n")

    print("GENERATED ANSWER:")
    print("-" * 80)
    print(result.get("answer", "No answer"))
    print("-" * 80 + "\n")

    print("CITATIONS:")
    print("-" * 80)
    citations = result.get("citations", [])
    if citations:
        for i, cit in enumerate(citations, 1):
            print(f"[{i}] doc_id: {cit.get('doc_id')}")
            print(f"    page: {cit.get('page')}")
            print(f"    source: {cit.get('source')}")
            print(f"    pdf_path: {cit.get('pdf_path', 'N/A')}")
            print(f"    snippet: {cit.get('snippet', '')[:100]}...")
            print()
    else:
        print("No citations found!")
    print("-" * 80 + "\n")

    # Check confidence
    confidence = result.get("confidence", 0.0)
    print(f"Confidence Score: {confidence}\n")

    # Check doc_number_map
    metadata = result.get("metadata", {})
    if "doc_number_map" in metadata:
        print("DOC_NUMBER_MAP (for UI page buttons):")
        print("-" * 80)
        doc_map = metadata["doc_number_map"]
        for doc_num in sorted(doc_map.keys()):
            info = doc_map[doc_num]
            print(f"Doc {doc_num}:")
            print(f"  doc_id: {info.get('doc_id')}")
            print(f"  file_name: {info.get('file_name')}")
            print(f"  pdf_path: {'present' if info.get('pdf_path') else 'MISSING'}")
        print("-" * 80 + "\n")

    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("Now check the API terminal logs for:")
    print("  1. 'Prepared LLM context' - which documents were sent to LLM")
    print("  2. 'Doc mapping summary' - how [Doc 1], [Doc 2], etc. map to doc_ids")
    print("  3. 'Prompt preview' - what prompt was sent to LLM")
    print("  4. 'Answer preview' - raw LLM output before citation parsing")
    print("  5. 'Parsed citations' - final citations with doc_id + page")
    print("\nLook for mismatches between:")
    print("  - What the LLM cited (e.g., [Doc 1, p.6])")
    print("  - What doc_number_map says Doc 1 actually is")
    print("=" * 80 + "\n")

except requests.exceptions.ConnectionError:
    print("\n❌ ERROR: Could not connect to API at", API_URL)
    print("Please make sure the API is running with:")
    print("    .\\start_api_debug.ps1")
    print()
except requests.exceptions.Timeout:
    print("\n❌ ERROR: Request timed out")
    print("The query might be taking too long. Check API logs.")
    print()
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print()
