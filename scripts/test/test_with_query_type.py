"""
Test retrieval with REQUIRED query_type parameter
Tests technical_doc mode (auto mode removed - user must select)
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import json

import requests


def test_explicit_mode():
    """Test 4 queries with explicit query_type='technical_doc'"""

    api_url = "http://localhost:8000"

    test_cases = [
        {
            "id": "Q1_VN",
            "query": "Trong Urea Unit, đối với turbine hơi dẫn động máy nén CO₂ (mã KT06101), điều kiện hơi vào turbine ở chế độ normal là bao nhiêu (áp suất và nhiệt độ)?",
            "language": "vi",
            "expected_doc": "KT06101",
        },
        {
            "id": "Q2_EN",
            "query": "According to the operation and maintenance manual for the HCD025 gear unit, what are the specified setpoints for lubricating oil pressure for normal operation, alarm, and shutdown (trip)?",
            "language": "en",
            "expected_doc": "092_3N4-S4279947",
        },
        {
            "id": "Q3_VN",
            "query": "Theo biểu đồ hiệu suất dự kiến của máy nén CO2, tốc độ vận hành 100% của máy nén là bao nhiêu vòng/phút (RPM)?",
            "language": "vi",
            "expected_doc": "003_3N4-S4274345",
        },
        {
            "id": "Q4_EN",
            "query": "I need to configure the alarm settings for the temperature monitoring system on the steam turbine. According to the instrument list, there is a sensor with Tag No. 06-TE-0256 A/B. Based on the provided documentation, what is the measurement point (i.e., the component being monitored) for this tag number, and what is its corresponding high-temperature alarm (A) setpoint?",
            "language": "en",
            "expected_doc": "Instrument List",
        },
    ]

    print("=" * 80)
    print("TEST: Technical doc retrieval (query_type='technical_doc')")
    print("=" * 80)

    results_tech = []

    for tc in test_cases:
        print(f"\n{'='*80}")
        print(f"[{tc['id']}] {tc['query'][:60]}...")
        print(f"{'='*80}")
        try:
            resp = requests.post(
                f"{api_url}/ask",
                json={
                    "query": tc["query"],
                    "language": tc["language"],
                    "hyde": False,
                    "max_context": 3,
                    "enable_vision_generation": False,
                    "query_type": "technical_doc",  # Explicit mode
                },
                timeout=60,
            )

            if resp.status_code == 200:
                data = resp.json()
                citations = data.get("citations", [])
                match = any(
                    tc["expected_doc"].lower() in c.get("doc_id", "").lower()
                    for c in citations
                )
                results_tech.append(match)
                print(f"  Retrieved: {len(citations)} docs")
                print(f"  Expected doc match: {'✓ YES' if match else '✗ NO'}")
                if citations:
                    print(f"  Top doc: {citations[0].get('doc_id', '')[:60]}")
            else:
                print(f"  ✗ Error: {resp.status_code}")
                results_tech.append(False)
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            results_tech.append(False)

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    tech_accuracy = sum(results_tech) / len(results_tech)

    print(
        f"TECHNICAL_DOC mode: {tech_accuracy:.1%} ({sum(results_tech)}/{len(results_tech)})"
    )
    print(f"Expected: ≥75% accuracy")

    if tech_accuracy >= 0.75:
        print("\n✓ TEST PASSED: Technical doc mode ≥75% accuracy")
        return 0
    else:
        print(f"\n✗ TEST FAILED: Only {tech_accuracy:.1%} accuracy")
        return 1


if __name__ == "__main__":
    # Check API
    try:
        response = requests.get("http://localhost:8000/healthz", timeout=5)
        if response.status_code != 200:
            print("❌ API not healthy!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        sys.exit(1)

    exit_code = test_explicit_mode()
    sys.exit(exit_code)
