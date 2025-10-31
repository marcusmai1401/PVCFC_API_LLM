"""
Test retrieval accuracy with query expansion
Direct API calls to test if expansion improves results for 4 failing queries
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import json

import requests

from app.rag.query_expansion import QueryExpander


def test_with_expansion():
    """Test 4 queries with and without expansion"""

    api_url = "http://localhost:8000"
    expander = QueryExpander()

    test_cases = [
        {
            "id": "Q1_VN",
            "original": "Trong Urea Unit, đối với turbine hơi dẫn động máy nén CO₂ (mã KT06101), điều kiện hơi vào turbine ở chế độ normal là bao nhiêu (áp suất và nhiệt độ)?",
            "language": "vi",
            "expected_doc": "KT06101",
            "expected_answer": "39 bar(a) and 370 °C",
        },
        {
            "id": "Q2_EN",
            "original": "According to the operation and maintenance manual for the HCD025 gear unit, what are the specified setpoints for lubricating oil pressure for normal operation, alarm, and shutdown (trip)?",
            "language": "en",
            "expected_doc": "092_3N4-S4279947",
            "expected_answer": "Normal: 2.0 barG, Alarm: 1.2 barG, Trip: 0.8 barG",
        },
        {
            "id": "Q3_VN",
            "original": "Theo biểu đồ hiệu suất dự kiến của máy nén CO2, tốc độ vận hành 100% của máy nén là bao nhiêu vòng/phút (RPM)?",
            "language": "vi",
            "expected_doc": "003_3N4-S4274345",
            "expected_answer": "7800 / 13277 RPM",
        },
        {
            "id": "Q4_EN",
            "original": "I need to configure the alarm settings for the temperature monitoring system on the steam turbine. According to the instrument list, there is a sensor with Tag No. 06-TE-0256 A/B. Based on the provided documentation, what is the measurement point (i.e., the component being monitored) for this tag number, and what is its corresponding high-temperature alarm (A) setpoint?",
            "language": "en",
            "expected_doc": "Instrument List",
            "expected_answer": "Measurement Point: Rear Journal Bearing, Alarm: 105 °C",
        },
    ]

    print("=" * 80)
    print("RETRIEVAL TEST: WITH vs WITHOUT QUERY EXPANSION")
    print("=" * 80)

    results = []

    for tc in test_cases:
        print(f"\n{'='*80}")
        print(f"[{tc['id']}] {tc['original'][:60]}...")
        print(f"{'='*80}")

        # Test WITHOUT expansion (original query)
        print("\n[1] WITHOUT Expansion:")
        try:
            response_orig = requests.post(
                f"{api_url}/ask",
                json={
                    "query": tc["original"],
                    "language": tc["language"],
                    "hyde": False,  # Disable HyDE for cleaner test
                    "max_context": 3,
                    "enable_vision_generation": False,  # Faster test
                },
                timeout=60,
            )

            if response_orig.status_code == 200:
                data_orig = response_orig.json()
                citations_orig = data_orig.get("citations", [])
                answer_orig = data_orig.get("answer", "")

                # Check if expected doc is in citations
                doc_match_orig = any(
                    tc["expected_doc"].lower() in cit.get("doc_id", "").lower()
                    for cit in citations_orig
                )

                print(f"  Retrieved {len(citations_orig)} docs")
                print(f"  Expected doc match: {'✓ YES' if doc_match_orig else '✗ NO'}")
                if citations_orig:
                    top_doc = citations_orig[0].get("doc_id", "")[:60]
                    print(f"  Top doc: {top_doc}")
                print(f"  Answer preview: {answer_orig[:100]}...")
            else:
                print(f"  ✗ API Error: {response_orig.status_code}")
                doc_match_orig = False

        except Exception as e:
            print(f"  ✗ Exception: {e}")
            doc_match_orig = False

        # Test WITH expansion
        print("\n[2] WITH Expansion:")
        expanded_query = expander.expand_query(tc["original"])
        print(f"  Expanded: {expanded_query[:100]}...")

        try:
            response_exp = requests.post(
                f"{api_url}/ask",
                json={
                    "query": expanded_query,
                    "language": tc["language"],
                    "hyde": False,
                    "max_context": 3,
                    "enable_vision_generation": False,
                },
                timeout=60,
            )

            if response_exp.status_code == 200:
                data_exp = response_exp.json()
                citations_exp = data_exp.get("citations", [])
                answer_exp = data_exp.get("answer", "")

                # Check if expected doc is in citations
                doc_match_exp = any(
                    tc["expected_doc"].lower() in cit.get("doc_id", "").lower()
                    for cit in citations_exp
                )

                print(f"  Retrieved {len(citations_exp)} docs")
                print(f"  Expected doc match: {'✓ YES' if doc_match_exp else '✗ NO'}")
                if citations_exp:
                    top_doc = citations_exp[0].get("doc_id", "")[:60]
                    print(f"  Top doc: {top_doc}")
                print(f"  Answer preview: {answer_exp[:100]}...")
            else:
                print(f"  ✗ API Error: {response_exp.status_code}")
                doc_match_exp = False

        except Exception as e:
            print(f"  ✗ Exception: {e}")
            doc_match_exp = False

        # Compare
        print(f"\n[RESULT]")
        if doc_match_exp and not doc_match_orig:
            print(f"  🎉 IMPROVED: Expansion found correct doc!")
            improvement = "IMPROVED"
        elif doc_match_exp and doc_match_orig:
            print(f"  ✓ MAINTAINED: Both found correct doc")
            improvement = "MAINTAINED"
        elif not doc_match_exp and doc_match_orig:
            print(f"  ⚠️ REGRESSED: Expansion lost correct doc")
            improvement = "REGRESSED"
        else:
            print(f"  ✗ NO CHANGE: Both failed to find correct doc")
            improvement = "NO_CHANGE"

        results.append(
            {
                "id": tc["id"],
                "doc_match_orig": doc_match_orig,
                "doc_match_exp": doc_match_exp,
                "improvement": improvement,
            }
        )

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    improved = sum(1 for r in results if r["improvement"] == "IMPROVED")
    maintained = sum(1 for r in results if r["improvement"] == "MAINTAINED")
    regressed = sum(1 for r in results if r["improvement"] == "REGRESSED")
    no_change = sum(1 for r in results if r["improvement"] == "NO_CHANGE")

    print(f"Total queries: {len(results)}")
    print(f"  🎉 Improved:   {improved}")
    print(f"  ✓ Maintained: {maintained}")
    print(f"  ⚠️ Regressed:  {regressed}")
    print(f"  ✗ No change:  {no_change}")

    accuracy_orig = sum(1 for r in results if r["doc_match_orig"]) / len(results)
    accuracy_exp = sum(1 for r in results if r["doc_match_exp"]) / len(results)

    print(f"\nAccuracy:")
    print(
        f"  Without expansion: {accuracy_orig:.1%} ({sum(1 for r in results if r['doc_match_orig'])}/{len(results)})"
    )
    print(
        f"  With expansion:    {accuracy_exp:.1%} ({sum(1 for r in results if r['doc_match_exp'])}/{len(results)})"
    )
    print(f"  Delta:             {(accuracy_exp - accuracy_orig):+.1%}")

    return results


if __name__ == "__main__":
    # Check API
    try:
        response = requests.get("http://localhost:8000/healthz", timeout=5)
        if response.status_code != 200:
            print("❌ API not healthy!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        print("Make sure API server is running!")
        sys.exit(1)

    # Run test
    results = test_with_expansion()

    # Exit code based on improvement
    improved_count = sum(
        1 for r in results if r["improvement"] in ["IMPROVED", "MAINTAINED"]
    )
    if improved_count >= len(results) * 0.75:
        print("\n✓ Test PASSED: ≥75% improved or maintained")
        sys.exit(0)
    else:
        print(
            f"\n✗ Test FAILED: Only {improved_count}/{len(results)} improved/maintained"
        )
        sys.exit(1)
