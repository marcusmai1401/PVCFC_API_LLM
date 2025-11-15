"""
Test C-3: Confidence Score High-Score Bypass
"""
from statistics import mean

from app.rag.generator import Citation, _compute_calibrated_confidence
from app.rag.retriever import RetrievalResult


def test_confidence_high_scores():
    """Test that high scores (≥0.80) skip rescaling"""

    # Mock high-quality retrieval results
    results = [
        RetrievalResult(
            chunk_id=f"chunk{i}",
            doc_id=f"doc{i}",
            text=f"text {i}",
            score=score,
            source="test",
            page=1,
            metadata={},
        )
        for i, score in enumerate([0.91, 0.90, 0.89, 0.87, 0.85], 1)
    ]

    # Mock citations
    citations = [
        Citation(doc_id="doc1", source="test.pdf", page=1),
        Citation(doc_id="doc2", source="test.pdf", page=2),
    ]

    # Mock answer
    answer_text = "The pressure is 150 psi according to the specifications. This meets the design requirements."

    # Mock config
    class MockConfig:
        pass

    cfg = MockConfig()

    # Compute confidence
    conf, components = _compute_calibrated_confidence(
        retrieval_results=results,
        citations=citations,
        answer_text=answer_text,
        context_items=results,
        cfg=cfg,
        top_m=5,
        length_threshold_chars=200,
    )

    print("\n=== Test C-3: High Score Bypass ===")
    print(f"Raw scores: {[r.score for r in results]}")
    print(f"Min score: {min(r.score for r in results):.3f}")
    print(f"Components: {components}")
    print(f"Base confidence: {components['base']:.4f}")
    print(f"Final confidence: {conf:.4f}")

    # Assertions
    raw_scores = [r.score for r in results]
    expected_base = mean(raw_scores)  # Should use raw average

    assert min(raw_scores) >= 0.80, "Test setup error: scores should be ≥0.80"
    assert "note" in components, "Should have 'note' indicating bypass"
    assert "High-quality" in components["note"], "Note should mention high-quality"
    assert (
        abs(components["base"] - expected_base) < 0.01
    ), f"Base should be raw average {expected_base:.3f}, got {components['base']:.3f}"
    assert "rescaled_top_scores" not in components, "Should NOT have rescaled scores"
    assert (
        conf >= 0.85
    ), f"Final confidence should be ≥0.85 for high scores, got {conf:.3f}"

    print("✅ HIGH SCORE BYPASS TEST PASSED")
    print(f"   - Base confidence: {components['base']:.3f} (raw average)")
    print(f"   - Final confidence: {conf:.3f} (≥0.85 ✓)")


def test_confidence_mixed_scores():
    """Test that mixed scores still use rescaling"""

    # Mock mixed-quality retrieval results
    results = [
        RetrievalResult(
            chunk_id=f"chunk{i}",
            doc_id=f"doc{i}",
            text=f"text {i}",
            score=score,
            source="test",
            page=1,
            metadata={},
        )
        for i, score in enumerate([0.75, 0.65, 0.55, 0.45, 0.35], 1)
    ]

    # Mock config
    class MockConfig:
        pass

    cfg = MockConfig()

    # Compute confidence
    conf, components = _compute_calibrated_confidence(
        retrieval_results=results,
        citations=[],
        answer_text="Short answer",
        context_items=results,
        cfg=cfg,
        top_m=5,
    )

    print("\n=== Test C-3: Mixed Score Rescaling ===")
    print(f"Raw scores: {[r.score for r in results]}")
    print(f"Min score: {min(r.score for r in results):.3f}")
    print(f"Components: {components}")
    print(f"Base confidence: {components['base']:.4f}")
    print(f"Final confidence: {conf:.4f}")

    # Assertions
    raw_scores = [r.score for r in results]

    assert min(raw_scores) < 0.80, "Test setup: scores should be <0.80"
    assert (
        "rescaled_top_scores" in components
    ), "Should HAVE rescaled scores for mixed quality"
    assert "note" not in components, "Should NOT have bypass note"

    print("✅ MIXED SCORE RESCALING TEST PASSED")
    print(f"   - Rescaling applied ✓")
    print(f"   - Base confidence: {components['base']:.3f}")


if __name__ == "__main__":
    test_confidence_high_scores()
    test_confidence_mixed_scores()
    print("\n" + "=" * 50)
    print("ALL C-3 TESTS PASSED ✅")
    print("=" * 50)
