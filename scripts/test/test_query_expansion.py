"""
Quick test script for query expansion
Tests if expansion improves retrieval for failed queries
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.rag.query_expansion import QueryExpander


def test_expansion():
    """Test query expansion on 4 failing queries"""

    expander = QueryExpander()

    test_queries = [
        "Trong Urea Unit, đối với turbine hơi dẫn động máy nén CO₂ (mã KT06101), điều kiện hơi vào turbine ở chế độ normal là bao nhiêu?",
        "According to the operation and maintenance manual for the HCD025 gear unit, what are the specified setpoints for lubricating oil pressure?",
        "Theo biểu đồ hiệu suất dự kiến của máy nén CO2, tốc độ vận hành 100% là bao nhiêu vòng/phút (RPM)?",
        "Tag No. 06-TE-0256 A/B from instrument list, what is the measurement point and alarm setpoint?",
    ]

    print("=" * 60)
    print("QUERY EXPANSION TEST")
    print("=" * 60)

    for i, query in enumerate(test_queries, 1):
        print(f"\n[Q{i}] Original:")
        print(f"  {query[:80]}...")

        expanded = expander.expand_query(query)

        print(f"\n[Q{i}] Expanded:")
        print(f"  {expanded}")
        print(f"  Terms added: {len(expanded.split()) - len(query.split())}")
        print("-" * 60)


if __name__ == "__main__":
    test_expansion()
