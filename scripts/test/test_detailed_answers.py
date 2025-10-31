"""
Test detailed answers for each query
"""
import json

import requests


def test_question(query, language, question_id):
    """Test a single question and show full answer"""

    resp = requests.post(
        "http://localhost:8000/ask",
        json={
            "query": query,
            "language": language,
            "hyde": False,
            "max_context": 3,
            "enable_vision_generation": False,
            "query_type": "technical_doc",
        },
        timeout=60,
    )

    if resp.status_code != 200:
        print(f"❌ ERROR {resp.status_code}: {resp.text}")
        return

    data = resp.json()

    print(f"\n{'='*80}")
    print(f"[{question_id}]")
    print(f"{'='*80}")
    print(f"\n📝 QUERY: {query[:100]}...")
    print(f"\n✅ ANSWER:\n{data['answer']}")
    print(f"\n📚 CITATIONS ({len(data['citations'])}):")
    for i, cit in enumerate(data["citations"], 1):
        print(f"  [{i}] {cit['doc_id'][:80]}")
        print(f"      Page: {cit['page']}, Score: {cit.get('relevance_score', 'N/A')}")


if __name__ == "__main__":
    # Q1
    test_question(
        "Trong Urea Unit, đối với turbine hơi dẫn động máy nén CO₂ (mã KT06101), điều kiện hơi vào turbine ở chế độ normal là bao nhiêu (áp suất và nhiệt độ)?",
        "vi",
        "Q1_VN",
    )

    # Q2
    test_question(
        "According to the operation and maintenance manual for the HCD025 gear unit, what are the specified setpoints for lubricating oil pressure for normal operation, alarm, and shutdown (trip)?",
        "en",
        "Q2_EN",
    )

    # Q3
    test_question(
        "Theo biểu đồ hiệu suất dự kiến của máy nén CO2, tốc độ vận hành 100% của máy nén là bao nhiêu vòng/phút (RPM)?",
        "vi",
        "Q3_VN",
    )

    # Q4
    test_question(
        "I need to configure the alarm settings for the temperature monitoring system on the steam turbine. According to the instrument list, there is a sensor with Tag No. 06-TE-0256 A/B. Based on the provided documentation, what is the measurement point (i.e., the component being monitored) for this tag number, and what is its corresponding high-temperature alarm (A) setpoint?",
        "en",
        "Q4_EN",
    )
