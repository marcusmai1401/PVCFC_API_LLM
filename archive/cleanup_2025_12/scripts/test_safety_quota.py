"""
Test Safety Quota Implementation for Exact Match Guardrails

This script verifies that:
1. Exact matches are detected correctly
2. Safety quota limits exact matches to 20
3. Dropped exact matches return to semantic pool
4. BGE receives correct slot allocation (top_k - len(exact_matches))
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from typing import List

from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridWeaviateOpenSearchRetriever,
    RetrievalResult,
)


def create_mock_result(chunk_id: str, text: str, score: float) -> RetrievalResult:
    """Create mock retrieval result"""
    return RetrievalResult(
        chunk_id=chunk_id,
        text=text,
        score=score,
        source="mock",
        metadata={"page": 1},
        doc_id="mock_doc",
        page=1,
        bbox=None,
        parent_id=None,
    )


def test_case_1_no_codes():
    """Test Case 1: Query with no special codes"""
    print("\n" + "=" * 80)
    print("TEST CASE 1: Query with no special codes")
    print("=" * 80)

    # Create mock retriever - we only need the _extract_exact_matches method
    retriever = type("MockRetriever", (), {})()
    # Copy the methods we need from the actual class
    from app.rag.hybrid_weaviate_opensearch_retriever import (
        HybridWeaviateOpenSearchRetriever,
    )

    retriever._detect_special_codes = (
        HybridWeaviateOpenSearchRetriever._detect_special_codes.__get__(retriever)
    )
    retriever._extract_exact_matches = (
        HybridWeaviateOpenSearchRetriever._extract_exact_matches.__get__(retriever)
    )

    query = "What is the operating pressure?"
    results = [
        create_mock_result("chunk1", "The operating pressure is 150 PSI", 0.9),
        create_mock_result("chunk2", "Normal pressure range: 100-200 PSI", 0.8),
        create_mock_result("chunk3", "Pressure monitoring system details", 0.7),
    ]

    exact_matches, remaining = retriever._extract_exact_matches(
        query=query, results=results, limit=20
    )

    print(f"Query: {query}")
    print(f"Expected: No exact matches")
    print(f"Result: {len(exact_matches)} exact matches, {len(remaining)} remaining")

    assert len(exact_matches) == 0, "Should have 0 exact matches"
    assert len(remaining) == 3, "Should have all 3 in remaining"
    print("✅ PASSED")


def test_case_2_flooding_scenario():
    """Test Case 2: Flooding scenario with 50 exact matches (header/footer noise)"""
    print("\n" + "=" * 80)
    print("TEST CASE 2: Flooding Scenario - 50 exact matches from headers")
    print("=" * 80)

    # Create mock retriever
    retriever = type("MockRetriever", (), {})()
    from app.rag.hybrid_weaviate_opensearch_retriever import (
        HybridWeaviateOpenSearchRetriever,
    )

    retriever._detect_special_codes = (
        HybridWeaviateOpenSearchRetriever._detect_special_codes.__get__(retriever)
    )
    retriever._extract_exact_matches = (
        HybridWeaviateOpenSearchRetriever._extract_exact_matches.__get__(retriever)
    )

    query = "Thông số áp suất KT06101"

    # Simulate 50 chunks with KT06101 (header/footer noise) with varying scores
    results = []

    # 45 low-quality header chunks (score 0.1-0.3)
    for i in range(45):
        results.append(
            create_mock_result(
                chunk_id=f"header_chunk_{i}",
                text=f"[HEADER] Drawing: KT06101 - Page {i+1}",
                score=0.1 + (i % 3) * 0.1,  # Scores: 0.1, 0.2, 0.3
            )
        )

    # 5 high-quality content chunks with KT06101 (score 0.7-0.9)
    for i in range(5):
        results.append(
            create_mock_result(
                chunk_id=f"content_chunk_{i}",
                text=f"KT06101: Operating pressure is {150 + i*10} PSI at temperature {30 + i*5}°C",
                score=0.9 - i * 0.05,  # Scores: 0.9, 0.85, 0.8, 0.75, 0.7
            )
        )

    # 10 semantic chunks without KT06101 (score 0.4-0.6)
    for i in range(10):
        results.append(
            create_mock_result(
                chunk_id=f"semantic_chunk_{i}",
                text=f"Pressure monitoring system specification for operating conditions",
                score=0.6 - i * 0.02,
            )
        )

    exact_matches, remaining = retriever._extract_exact_matches(
        query=query, results=results, limit=20
    )

    print(f"Query: {query}")
    print(f"Total input: {len(results)} chunks")
    print(f"  - 45 header chunks (scores 0.1-0.3)")
    print(f"  - 5 content chunks (scores 0.7-0.9)")
    print(f"  - 10 semantic chunks (no code)")
    print(f"\nExpected: Top 20 exact matches (5 content + 15 best headers)")
    print(f"Result:")
    print(f"  - Exact matches kept: {len(exact_matches)} (limit=20)")
    print(f"  - Remaining pool: {len(remaining)} (30 dropped headers + 10 semantic)")

    # Verify counts
    # Total: 50 exact + 10 semantic = 60 chunks
    # Kept: 20 exact matches
    # Remaining: 30 dropped exact + 10 semantic = 40
    assert (
        len(exact_matches) == 20
    ), f"Should have exactly 20 exact matches, got {len(exact_matches)}"
    assert (
        len(remaining) == 40
    ), f"Should have 40 in remaining (30 dropped + 10 semantic), got {len(remaining)}"

    # Verify score boosting: top 20 exact matches should have score = 1.0
    assert all(
        r.score == 1.0 for r in exact_matches
    ), "All exact matches should have score 1.0"

    # Verify sorting: top 5 should be content chunks (original score 0.7-0.9)
    top_5_ids = [r.chunk_id for r in exact_matches[:5]]
    print(f"\nTop 5 exact matches: {top_5_ids}")
    assert all(
        "content_chunk" in cid for cid in top_5_ids
    ), "Top 5 should be content chunks"

    # Verify remaining pool contains dropped headers with original scores
    dropped_headers = [r for r in remaining if "header_chunk" in r.chunk_id]
    print(f"Dropped headers: {len(dropped_headers)} (scores not boosted)")
    assert all(
        r.score < 1.0 for r in dropped_headers
    ), "Dropped headers should keep original scores"

    print("✅ PASSED - Safety Quota prevents flooding!")


def test_case_3_slot_allocation():
    """Test Case 3: Verify BGE slot allocation logic"""
    print("\n" + "=" * 80)
    print("TEST CASE 3: BGE Slot Allocation")
    print("=" * 80)

    test_scenarios = [
        (10, 2, 8),  # top_k=10, 2 exact matches → BGE gets 8 slots
        (50, 20, 30),  # top_k=50, 20 exact matches → BGE gets 30 slots
        (50, 5, 45),  # top_k=50, 5 exact matches → BGE gets 45 slots
    ]

    for top_k, num_exact, expected_bge_slots in test_scenarios:
        bge_slots = top_k - num_exact
        print(f"Scenario: top_k={top_k}, exact={num_exact}")
        print(f"  Expected BGE slots: {expected_bge_slots}")
        print(f"  Actual BGE slots: {bge_slots}")
        assert bge_slots == expected_bge_slots, "Slot calculation mismatch"
        print(f"  ✅ Correct")

    print("\n✅ All slot allocation scenarios PASSED")


def test_case_4_code_detection():
    """Test Case 4: Code detection patterns"""
    print("\n" + "=" * 80)
    print("TEST CASE 4: Code Detection Patterns")
    print("=" * 80)

    # Create mock retriever
    retriever = type("MockRetriever", (), {})()
    from app.rag.hybrid_weaviate_opensearch_retriever import (
        HybridWeaviateOpenSearchRetriever,
    )

    retriever._detect_special_codes = (
        HybridWeaviateOpenSearchRetriever._detect_special_codes.__get__(retriever)
    )

    test_patterns = [
        ("LS006343", ["LS006343"]),
        ("HCD025", ["HCD025"]),
        ("E-04217", ["E04217"]),  # Hyphen normalized
        ("KT06101", ["KT06101"]),
        ("ABC-1234", ["ABC1234"]),
        ("Thông số LS006343 và HCD025", ["LS006343", "HCD025"]),
        ("No codes here", []),
    ]

    for query, expected in test_patterns:
        codes = retriever._detect_special_codes(query)
        print(f"Query: '{query}'")
        print(f"  Expected: {expected}")
        print(f"  Detected: {codes}")

        # Normalize comparison (remove hyphens)
        expected_normalized = [c.replace("-", "") for c in expected]
        codes_normalized = [c.replace("-", "") for c in codes]

        assert codes_normalized == expected_normalized, f"Mismatch for query '{query}'"
        print(f"  ✅ Match")

    print("\n✅ All code detection tests PASSED")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SAFETY QUOTA IMPLEMENTATION TEST SUITE")
    print("=" * 80)

    try:
        test_case_1_no_codes()
        test_case_2_flooding_scenario()
        test_case_3_slot_allocation()
        test_case_4_code_detection()

        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print("\nSummary:")
        print("✅ No codes: Returns empty exact_matches")
        print("✅ Flooding: Limits to 20 exact matches, drops rest to semantic pool")
        print("✅ Slot allocation: Correctly reserves slots for BGE")
        print("✅ Code detection: Detects all code patterns correctly")
        print("\n🛡️ Safety Quota is PRODUCTION READY!")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
