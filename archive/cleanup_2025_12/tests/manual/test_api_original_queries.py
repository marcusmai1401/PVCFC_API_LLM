"""API test with 4 original queries from earlier testing"""
import json
from datetime import datetime

import requests

API_URL = "http://localhost:8000/ask"

# Original 4 test queries
QUERIES = [
    {
        "name": "Query 1: Steam Consumption Curve",
        "query": "What is the steam consumption curve for the turbine?",
        "language": "en",
        "max_context": 10,
        "query_type": "technical_doc",
    },
    {
        "name": "Query 2: CO2 Compressor Maintenance",
        "query": "What are the maintenance requirements for the CO2 compressor?",
        "language": "en",
        "max_context": 10,
        "query_type": "technical_doc",
    },
    {
        "name": "Query 3: P&ID Lube Oil System",
        "query": "Show me the P&ID diagram for the lube oil system",
        "language": "en",
        "max_context": 10,
        "query_type": "technical_doc",
    },
    {
        "name": "Query 4: Operating Temperature K06101",
        "query": "What is the operating temperature range for K06101?",
        "language": "en",
        "max_context": 10,
        "query_type": "technical_doc",
    },
]


def test_query(test_case: dict, test_num: int):
    """Test a single query"""
    print(f"\n{'='*80}")
    print(f"TEST #{test_num}: {test_case['name']}")
    print(f"{'='*80}")
    print(f"Query: {test_case['query']}\n")

    payload = {
        "query": test_case["query"],
        "language": test_case["language"],
        "max_context": test_case["max_context"],
        "query_type": test_case["query_type"],
        "hyde": True,
        "execution_mode": "heavy_only",
        "confidence_mode": "calibrated",
    }

    try:
        start = datetime.now()
        response = requests.post(API_URL, json=payload, timeout=180)
        duration = (datetime.now() - start).total_seconds()

        response.raise_for_status()
        result = response.json()

        # Display answer
        print(f"{'─'*80}")
        print("ANSWER:")
        print(f"{'─'*80}")
        answer = result.get("answer", "No answer")
        # Show first 600 chars for readability
        if len(answer) > 600:
            print(answer[:600] + "...")
        else:
            print(answer)

        # Display citations
        print(f"\n{'─'*80}")
        print("CITATIONS:")
        print(f"{'─'*80}")
        citations = result.get("citations", [])
        if citations:
            for i, cit in enumerate(citations[:5], 1):  # Show top 5
                doc_id = cit.get("doc_id", "N/A")
                page = cit.get("page", "N/A")
                source = cit.get("source", "N/A")
                # Extract filename from source
                if source != "N/A":
                    filename = (
                        source.split("\\")[-1]
                        if "\\" in source
                        else source.split("/")[-1]
                    )
                else:
                    filename = "N/A"
                print(f"[{i}] {filename}")
                print(f"    doc_id: {doc_id[:70]}...")
                print(f"    page: {page}")
        else:
            print("❌ No citations")

        # Metadata
        metadata = result.get("metadata", {})
        confidence = result.get("confidence", 0.0)
        retrieval_stats = metadata.get("retrieval_stats", {})

        print(f"\n{'─'*80}")
        print("STATS:")
        print(f"{'─'*80}")
        print(f"✓ Duration: {duration:.2f}s")
        print(f"✓ Confidence: {confidence:.2f}")
        print(f"✓ Citations: {len(citations)}")
        if retrieval_stats:
            print(f"✓ Retrieved chunks: {retrieval_stats.get('total_retrieved', 0)}")
            print(f"✓ Used in context: {retrieval_stats.get('used_in_context', 0)}")

        return {
            "success": True,
            "duration": duration,
            "confidence": confidence,
            "citations": len(citations),
        }

    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to API")
        print("Make sure API is running at http://localhost:8000")
        return {"success": False}
    except requests.exceptions.Timeout:
        print("❌ ERROR: Request timed out")
        return {"success": False}
    except Exception as e:
        print(f"❌ ERROR: {e}")
        if hasattr(e, "response"):
            print(f"Response: {e.response.text[:200]}")
        return {"success": False}


def main():
    print("\n" + "=" * 80)
    print("API TEST - 4 ORIGINAL QUERIES")
    print("=" * 80)
    print(f"Target: {API_URL}")
    print(f"Tests: {len(QUERIES)}")
    print("=" * 80)

    results = []
    for i, test_case in enumerate(QUERIES, 1):
        result = test_query(test_case, i)
        result["test"] = test_case["name"]
        results.append(result)

    # Summary
    print(f"\n\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")

    passed = sum(1 for r in results if r["success"])
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed > 0:
        avg_duration = (
            sum(r.get("duration", 0) for r in results if r["success"]) / passed
        )
        avg_confidence = (
            sum(r.get("confidence", 0) for r in results if r["success"]) / passed
        )
        total_citations = sum(r.get("citations", 0) for r in results if r["success"])

        print(f"\nPerformance Metrics:")
        print(f"  - Avg Duration: {avg_duration:.2f}s")
        print(f"  - Avg Confidence: {avg_confidence:.2f}")
        print(f"  - Total Citations: {total_citations}")

    print(f"\n{'─'*80}")
    for r in results:
        status = "✅" if r["success"] else "❌"
        test_name = r["test"]
        if r["success"]:
            print(
                f"{status} {test_name} ({r['duration']:.1f}s, conf={r['confidence']:.2f})"
            )
        else:
            print(f"{status} {test_name}")

    print(f"{'='*80}\n")

    if passed == total:
        print("🎉 All tests passed! System working as expected.")
    else:
        print(f"⚠️  {total - passed} test(s) failed.")


if __name__ == "__main__":
    main()
