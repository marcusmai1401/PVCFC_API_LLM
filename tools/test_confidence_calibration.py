#!/usr/bin/env python
"""
Unit tests for Confidence Calibration
Tests rescaling and calibrated confidence computation
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.generator import (
    Citation,
    GeneratorConfig,
    _compute_calibrated_confidence,
    _rescale_scores,
)
from app.rag.retriever import RetrievalResult


def test_rescale_scores():
    """Test score rescaling functionality"""
    print("\n=== Test: Score Rescaling ===")

    # Test 1: Normal range
    scores = [0.5, 0.8, 0.9, 0.7]
    rescaled = _rescale_scores(scores)
    print(f"Input: {scores}")
    print(f"Rescaled: {[round(s, 3) for s in rescaled]}")
    assert min(rescaled) == 0.0, "Min should be 0"
    assert max(rescaled) == 1.0, "Max should be 1"
    print("✓ Normal range test passed")

    # Test 2: Single score
    single = _rescale_scores([0.7])
    assert single == [0.5], "Single score should map to 0.5"
    print("✓ Single score test passed")

    # Test 3: Empty list
    empty = _rescale_scores([])
    assert empty == [], "Empty should return empty"
    print("✓ Empty list test passed")

    # Test 4: Identical scores (degenerate case)
    identical = _rescale_scores([0.5, 0.5, 0.5])
    assert all(s == 0.5 for s in identical), "Identical scores should all map to 0.5"
    print("✓ Identical scores test passed")

    print("✓ All rescaling tests passed!\n")


def test_high_confidence_scenario():
    """Test high confidence with full page and multiple citations"""
    print("\n=== Test: High Confidence Scenario ===")

    # Mock retrieval results with high scores
    def mock_result(score):
        return RetrievalResult(
            chunk_id=f"chunk_{score}",
            text="Sample text",
            score=score,
            source="bm25",
            metadata={"full_page": True},
            doc_id="doc_A",
            page=5,
        )

    retrieval = [mock_result(0.95), mock_result(0.90), mock_result(0.88)]

    # Citations from same document, close pages
    citations = [
        Citation(doc_id="doc_A", source="bm25", page=5, relevance_score=0.95),
        Citation(doc_id="doc_A", source="bm25", page=6, relevance_score=0.90),
    ]

    extra = (
        " Additional technical explanation with references to exact specifications and values from the source documents."
        * 3
    )
    answer = (
        "Max pressure is 10 bar [Doc 1, p.5]. Tolerance ±0.5 bar [Doc 1, p.6]." + extra
    )

    cfg = GeneratorConfig(confidence_mode="calibrated")

    conf, components = _compute_calibrated_confidence(
        retrieval_results=retrieval,
        citations=citations,
        answer_text=answer,
        context_items=retrieval,
        cfg=cfg,
    )

    print(f"Confidence: {conf:.3f}")
    print(f"Components: {components}")
    print(f"  Base: {components['base']}")
    print(f"  Boosts: {components['boosts']}")
    print(f"  Penalties: {components['penalties']}")

    # With current scoring: base ~0.43 + boosts (0.10 full_page + 0.05 consistency + 0.05 length) ≈ 0.63
    assert (
        conf >= 0.62
    ), f"High confidence scenario should have conf >= 0.62, got {conf}"
    assert conf <= 0.8, f"High confidence should be reasonable, got {conf}"
    assert "full_page" in components["boosts"], "Should have full_page boost"
    assert (
        "multi_citation_consistency" in components["boosts"]
    ), "Should have citation consistency boost"
    assert "length" in components["boosts"], "Should have length boost"

    print("✓ High confidence test passed!\n")


def test_low_confidence_scenario():
    """Test low confidence with poor scores and fallback"""
    print("\n=== Test: Low Confidence Scenario ===")

    # Mock retrieval with low scores
    def mock_result(score):
        return RetrievalResult(
            chunk_id=f"chunk_{score}",
            text="Sample text",
            score=score,
            source="bm25",
            metadata={"uncited_fallback": True},
            doc_id="doc_B",
            page=1,
        )

    retrieval = [mock_result(0.2), mock_result(0.1)]
    citations = []
    answer = "Not found in the provided context."

    cfg = GeneratorConfig(confidence_mode="calibrated")

    conf, components = _compute_calibrated_confidence(
        retrieval_results=retrieval,
        citations=citations,
        answer_text=answer,
        context_items=retrieval,
        cfg=cfg,
    )

    print(f"Confidence: {conf:.3f}")
    print(f"Components: {components}")
    print(f"  Base: {components['base']}")
    print(f"  Penalties: {components['penalties']}")

    assert conf <= 0.4, f"Low confidence scenario should have conf <= 0.4, got {conf}"
    assert (
        "uncited_fallback" in components["penalties"]
    ), "Should have uncited fallback penalty"
    assert "short_answer" in components["penalties"], "Should have short answer penalty"

    print("✓ Low confidence test passed!\n")


def test_uncertainty_penalty():
    """Test confidence penalty for uncertainty phrases"""
    print("\n=== Test: Uncertainty Penalty ===")

    def mock_result(score):
        return RetrievalResult(
            chunk_id=f"chunk_{score}",
            text="Sample text",
            score=score,
            source="bm25",
            metadata={},
            doc_id="doc_C",
            page=2,
        )

    retrieval = [mock_result(0.6)]
    citations = [Citation(doc_id="doc_C", source="bm25", page=2, relevance_score=0.6)]

    # Answer with uncertainty marker
    answer = "I think it is approximately 5 bar [Doc 1, p.2]."

    cfg = GeneratorConfig(confidence_mode="calibrated")

    conf, components = _compute_calibrated_confidence(
        retrieval_results=retrieval,
        citations=citations,
        answer_text=answer,
        context_items=retrieval,
        cfg=cfg,
    )

    print(f"Confidence: {conf:.3f}")
    print(f"Components: {components}")
    print(f"  Penalties: {components['penalties']}")

    assert (
        "uncertainty_phrases" in components["penalties"]
    ), "Should have uncertainty penalty"
    assert "short_answer" in components["penalties"], "Should have short answer penalty"
    print(
        f"✓ Uncertainty penalty applied: {components['penalties']['uncertainty_phrases']}\n"
    )


def test_vietnamese_uncertainty():
    """Test Vietnamese uncertainty pattern detection"""
    print("\n=== Test: Vietnamese Uncertainty ===")

    def mock_result(score):
        return RetrievalResult(
            chunk_id=f"chunk_{score}",
            text="Sample text",
            score=score,
            source="bm25",
            metadata={},
            doc_id="doc_D",
            page=3,
        )

    retrieval = [mock_result(0.6)]
    citations = [Citation(doc_id="doc_D", source="bm25", page=3, relevance_score=0.6)]

    # Vietnamese answer with uncertainty
    answer = "Có thể áp suất khoảng 10 bar [Doc 1, p.3]. Đây là câu trả lời đủ dài để không bị phạt độ dài ngắn."

    cfg = GeneratorConfig(confidence_mode="calibrated")

    conf, components = _compute_calibrated_confidence(
        retrieval_results=retrieval,
        citations=citations,
        answer_text=answer,
        context_items=retrieval,
        cfg=cfg,
    )

    print(f"Confidence: {conf:.3f}")
    print(f"Components: {components}")

    assert (
        "uncertainty_phrases" in components["penalties"]
    ), "Should detect Vietnamese uncertainty"
    print(f"✓ Vietnamese uncertainty detected and penalized\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Confidence Calibration Test Suite")
    print("=" * 60)

    try:
        test_rescale_scores()
        test_high_confidence_scenario()
        test_low_confidence_scenario()
        test_uncertainty_penalty()
        test_vietnamese_uncertainty()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
