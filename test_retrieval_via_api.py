"""
Test retrieval via API to see if Instrument List can be retrieved
"""
import json

import requests

API_URL = "http://localhost:8000/ask"

# Test different queries to see which one retrieves Instrument List
test_queries = [
    "06-TE-0256 A/B Tag No",
    "Tag number 06-TE-0256 instrument list",
    "116_3N4-S4275354 Instrument List",
    "temperature sensor 06-TE-0256 rear journal bearing",
]

print("=" * 80)
print("TESTING RETRIEVAL WITH DIFFERENT QUERIES")
print("=" * 80)
print("\nGoal: Find a query that retrieves Instrument List document")
print("Target doc_id contains: 'Instrument_116_3N4-S4275354_Instrument_L'")
print("\n" + "=" * 80)

for i, query in enumerate(test_queries, 1):
    print(f"\n[Test {i}] Query: {query}")
    print("-" * 80)

    payload = {
        "query": query,
        "language": "en",
        "max_context": 10,
        "hyde": False,
        "execution_mode": "heavy_only",
        "confidence_mode": "calibrated",
        "enable_vision_generation": False,  # Disable vision for faster testing
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()

        # Check citations for Instrument List
        citations = result.get("citations", [])
        found_instrument = False

        print(f"Found {len(citations)} citations:")
        for j, cit in enumerate(citations[:5], 1):
            doc_id = cit.get("doc_id", "")
            page = cit.get("page", "?")

            # Check if this is Instrument List
            is_instrument = "Instrument" in doc_id and "116_3N4" in doc_id
            marker = "✅ INSTRUMENT LIST!" if is_instrument else ""

            print(f"  [{j}] Page {page}: {doc_id[:80]}... {marker}")

            if is_instrument:
                found_instrument = True

        if found_instrument:
            print("\n✅ SUCCESS! This query retrieved Instrument List!")
            print(f"Answer preview: {result.get('answer', '')[:200]}...")
            break
        else:
            print("❌ Instrument List NOT in results")

    except Exception as e:
        print(f"❌ Error: {e}")

print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)
print("\nIf NONE of the queries retrieved Instrument List, possible reasons:")
print("  1. Tag number '06-TE-0256' is not in the indexed text (OCR issue?)")
print("  2. Document chunks don't contain enough matching keywords")
print("  3. BM25/semantic scores are too low compared to Operating Manual")
print("  4. Document might not be properly indexed in Weaviate/OpenSearch")
print("\nRecommended fixes:")
print("  1. Check if Tag number appears in the Instrument List PDF")
print("  2. Re-index with better chunking strategy")
print("  3. Add domain-specific boosting for Instrument List documents")
print("  4. Use filters to restrict search to Instrument List only")
print("=" * 80)
