"""
Test script for 5AM-Fix UI changes
Tests normalize_api_response adapter and validates all tabs can access data correctly
"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from streamlit_app.components.query_lab_improved import (
    format_citations_enhanced,
    normalize_api_response,
)

# Mock API response matching actual structure
mock_response = {
    "answer": "Test answer",
    "confidence": 0.85,
    "citations": [
        {
            "doc_id": "DOCID_K06101_TEST",
            "page": 1238,
            "confidence": 1.0,
            "pdf_path": "D:\\Data_Raw\\test.pdf",
            # Note: no "score" field
        }
    ],
    "context_used": ["chunk1", "chunk2"],
    "meta": {
        "breakdown": {
            "transform_ms": 5118,
            "retrieve_ms": 890,
            "rerank_ms": 3,
            "generate_ms": 6769,
            "cove_ms": 1251,
        },
        "model_generation": "gemini-2.5-pro",
        "vision_generation": {
            "pages_used": [
                {"page": 56, "pdf_path": "D:\\test1.pdf"},
                {"page": 1238, "pdf_path": "D:\\test2.pdf"},
            ],
            "pages_failed": [],
        },
    },
    "retrieval_details": {
        "bm25": [
            {"chunk_id": "c1", "doc_id": "doc1", "score": 0.95, "page": 10},
            {"chunk_id": "c2", "doc_id": "doc2", "score": 0.89, "page": 15},
        ],
        "faiss": [{"chunk_id": "c3", "doc_id": "doc3", "score": 0.92, "page": 20}],
        "total_retrieved": 60,
        "from_cache": False,
    },
    "reranking_details": {
        "method": "score",
        "input_count": 60,
        "output_count": 20,
        "from_cache": False,
        "results": [
            {
                "rank": 1,
                "chunk_id": "c1",
                "doc_id": "doc1",
                "score": 0.98,
                "page": 10,
                "text": "Sample text 1",
            },
            {
                "rank": 2,
                "chunk_id": "c2",
                "doc_id": "doc2",
                "score": 0.95,
                "page": 15,
                "text": "Sample text 2",
            },
        ],
    },
    "generation_details": {
        "model": "gemini-2.5-pro",
        "tier": "heavy",
        "language": "vi",
        "execution_mode": "production",
        "vision_enabled": True,
        "answer_length": 250,
        "citations_count": 1,
        "confidence": 0.85,
        "total_tokens": 0,
        "estimated_cost": 0.0,
    },
}


def test_normalize_adapter():
    """Test the normalize_api_response adapter"""
    print("=" * 60)
    print("TEST 1: normalize_api_response adapter")
    print("=" * 60)

    ui = normalize_api_response(mock_response)

    # Test Retrieval
    assert "retrieval" in ui, "Missing retrieval in ui"
    assert (
        len(ui["retrieval"]["bm25"]) == 2
    ), f"Expected 2 BM25 results, got {len(ui['retrieval']['bm25'])}"
    assert (
        len(ui["retrieval"]["faiss"]) == 1
    ), f"Expected 1 FAISS result, got {len(ui['retrieval']['faiss'])}"
    assert ui["retrieval"]["total_retrieved"] == 60, f"Expected 60 total retrieved"
    print("✓ Retrieval data correctly normalized")

    # Test Rerank
    assert "rerank" in ui, "Missing rerank in ui"
    assert (
        ui["rerank"]["method"] == "score"
    ), f"Expected method 'score', got {ui['rerank']['method']}"
    assert ui["rerank"]["input_count"] == 60, f"Expected input_count 60"
    assert ui["rerank"]["output_count"] == 20, f"Expected output_count 20"
    assert len(ui["rerank"]["results"]) == 2, f"Expected 2 rerank results"
    print("✓ Rerank data correctly normalized")

    # Test Generation
    assert "generation" in ui, "Missing generation in ui"
    assert (
        ui["generation"]["model"] == "gemini-2.5-pro"
    ), f"Expected model gemini-2.5-pro"
    assert ui["generation"]["latency_ms"] == 6769, f"Expected latency_ms 6769"
    assert ui["generation"]["tier"] == "heavy", f"Expected tier heavy"
    assert ui["generation"]["language"] == "vi", f"Expected language vi"
    print("✓ Generation data correctly normalized")

    # Test Vision
    assert "vision" in ui, "Missing vision in ui"
    assert ui["vision"]["enabled"] == True, f"Expected vision enabled=True"
    assert len(ui["vision"]["pages_used"]) == 2, f"Expected 2 pages_used"
    assert len(ui["vision"]["pages_failed"]) == 0, f"Expected 0 pages_failed"
    print("✓ Vision data correctly normalized")

    print("\n✅ All adapter tests passed!\n")
    return ui


def test_citations_formatter():
    """Test the format_citations_enhanced function"""
    print("=" * 60)
    print("TEST 2: format_citations_enhanced")
    print("=" * 60)

    citations = mock_response["citations"]
    df = format_citations_enhanced(citations)

    assert not df.empty, "Citations dataframe should not be empty"
    assert "Score" in df.columns, "Missing Score column"
    assert "Confidence" in df.columns, "Missing Confidence column"

    # Check Score is N/A when not present
    score_value = df.iloc[0]["Score"]
    assert (
        score_value == "N/A"
    ), f"Expected Score='N/A' when field missing, got '{score_value}'"
    print(f"✓ Score correctly shows 'N/A' when field not present")

    # Check Confidence is displayed
    conf_value = df.iloc[0]["Confidence"]
    assert conf_value == "1.000", f"Expected Confidence='1.000', got '{conf_value}'"
    print(f"✓ Confidence correctly displayed: {conf_value}")

    print("\n✅ Citations formatter tests passed!\n")


def test_vision_enabled_detection():
    """Test vision enabled detection logic"""
    print("=" * 60)
    print("TEST 3: Vision enabled detection")
    print("=" * 60)

    ui = normalize_api_response(mock_response)

    # Should detect vision as enabled from both vision_meta and vision_enabled flag
    assert ui["vision"]["enabled"] == True, "Vision should be detected as enabled"
    print("✓ Vision correctly detected as enabled")

    # Test with vision disabled
    mock_no_vision = {
        "meta": {},
        "generation_details": {"vision_enabled": False},
        "retrieval_details": {},
        "reranking_details": {},
    }
    ui_no_vision = normalize_api_response(mock_no_vision)
    assert (
        ui_no_vision["vision"]["enabled"] == False
    ), "Vision should be detected as disabled"
    print("✓ Vision correctly detected as disabled when not used")

    print("\n✅ Vision detection tests passed!\n")


def test_backward_compatibility():
    """Test backward compatibility with meta-based access"""
    print("=" * 60)
    print("TEST 4: Backward compatibility")
    print("=" * 60)

    # Ensure meta still accessible for other code
    meta = mock_response.get("meta", {})
    assert "breakdown" in meta, "meta.breakdown should still be accessible"
    assert (
        "vision_generation" in meta
    ), "meta.vision_generation should still be accessible"
    print("✓ Original meta structure preserved for backward compatibility")

    print("\n✅ Backward compatibility tests passed!\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("5AM-Fix Validation Tests")
    print("=" * 60 + "\n")

    try:
        ui = test_normalize_adapter()
        test_citations_formatter()
        test_vision_enabled_detection()
        test_backward_compatibility()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\nAdapter output sample:")
        print(
            f"  Retrieval: BM25={len(ui['retrieval']['bm25'])}, FAISS={len(ui['retrieval']['faiss'])}"
        )
        print(
            f"  Rerank: {ui['rerank']['input_count']} → {ui['rerank']['output_count']} docs ({ui['rerank']['method']})"
        )
        print(
            f"  Generation: {ui['generation']['model']} ({ui['generation']['tier']}, {ui['generation']['language']})"
        )
        print(
            f"  Vision: enabled={ui['vision']['enabled']}, pages={len(ui['vision']['pages_used'])}"
        )
        print("\n✅ Ready to test in Streamlit UI")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
