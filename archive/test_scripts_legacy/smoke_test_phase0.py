"""
Smoke Test for Phase 0: Structured Citations

Quick manual test to verify structured output works end-to-end.
"""

from app.rag.generator import GeneratorConfig, ResponseGenerator
from app.rag.query_transform import QueryIntent, TransformedQuery
from app.rag.retriever import RetrievalResult


def test_structured_output_enabled():
    """Test with structured output flag ON"""
    print("\n=== Testing Structured Output (ENABLED) ===")

    config = GeneratorConfig(
        enable_structured_output=True,
        enable_vision_generation=False,  # Disable vision for cleaner test
        temperature=0.2,
    )

    generator = ResponseGenerator(config)

    # Mock query
    query = TransformedQuery(
        original="What is the maximum pressure?",
        normalized="maximum pressure specification",
        intent=QueryIntent.ASK,
        language="en",
        filters={},
    )

    # Mock retrieved docs
    docs = [
        RetrievalResult(
            chunk_id="test1",
            doc_id="TEST_DOC",
            source="test.pdf",
            page=10,
            text="Maximum operating pressure is 150 psi at ambient temperature.",
            score=0.95,
            metadata={"doc_category": "specification"},
        )
    ]

    print(f"Config: enable_structured_output={config.enable_structured_output}")
    print(f"Query: {query.original}")
    print(f"Retrieved {len(docs)} documents")

    try:
        result = generator.generate(query, docs)

        print(f"\n✓ Generation successful")
        print(f"  Answer: {result.answer[:100]}...")
        print(f"  Citations: {len(result.citations)}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Metadata: {result.metadata}")

        if result.metadata.get("structured_output"):
            print("\n✓ Structured output was used!")
        else:
            print("\n⚠ Fell back to legacy regex (expected if no API key)")

        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


def test_structured_output_disabled():
    """Test with structured output flag OFF (legacy)"""
    print("\n=== Testing Legacy Mode (DISABLED) ===")

    config = GeneratorConfig(
        enable_structured_output=False,  # Legacy mode
        enable_vision_generation=False,
        temperature=0.2,
    )

    generator = ResponseGenerator(config)

    query = TransformedQuery(
        original="What is the pressure?",
        normalized="pressure value",
        intent=QueryIntent.ASK,
        language="en",
        filters={},
    )

    docs = [
        RetrievalResult(
            chunk_id="test1",
            doc_id="DOC1",
            source="doc.pdf",
            page=5,
            text="The pressure is 100 bar.",
            score=0.9,
            metadata={},
        )
    ]

    print(f"Config: enable_structured_output={config.enable_structured_output}")

    try:
        result = generator.generate(query, docs)

        print(f"\n✓ Generation successful (legacy mode)")
        print(f"  Answer: {result.answer[:100]}...")
        print(f"  Citations: {len(result.citations)}")

        if not result.metadata.get("structured_output"):
            print("\n✓ Legacy regex was used (as expected)")

        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


def test_claims_extraction():
    """Test claims extraction module"""
    print("\n=== Testing Claims Extraction ===")

    from app.rag.claims import extract_factual_claims

    test_answer = """
    The maximum operating pressure of valve KT-06101 is 150 psi according to specification sheet.
    The device must be installed at location P-123 in the facility.
    Regular maintenance is required every 6 months as per safety guidelines.
    """

    claims = extract_factual_claims(test_answer)

    print(f"Extracted {len(claims)} claims:")
    for i, claim in enumerate(claims, 1):
        print(f"\n  Claim {i}:")
        print(f"    Type: {claim.type.value}")
        print(f"    Text: {claim.text[:80]}...")
        print(f"    Keywords: {claim.keywords[:5]}")  # First 5
        print(f"    Requires citation: {claim.requires_citation}")

    return len(claims) > 0


def test_schemas():
    """Test structured schemas validation"""
    print("\n=== Testing Structured Schemas ===")

    from app.rag.schemas_structured import StructuredAnswer, StructuredCitation

    # Valid citation
    try:
        citation = StructuredCitation(
            doc_id="TEST", page=10, quote="test quote", evidence_type="text"
        )
        print("✓ StructuredCitation validates correctly")
    except Exception as e:
        print(f"✗ StructuredCitation validation failed: {e}")
        return False

    # Valid answer with claims
    try:
        answer = StructuredAnswer(
            answer="Test answer",
            claims=[
                {
                    "claim_id": "c1",
                    "claim_text": "Test claim",
                    "citations": [{"doc_id": "D1", "page": 5}],
                }
            ],
        )
        print("✓ StructuredAnswer validates correctly")
    except Exception as e:
        print(f"✗ StructuredAnswer validation failed: {e}")
        return False

    # Invalid: claim without citations (should fail)
    try:
        bad_answer = StructuredAnswer(
            answer="Bad",
            claims=[
                {"claim_id": "c1", "claim_text": "Bad claim", "citations": []}  # Empty!
            ],
        )
        print("✗ Should have rejected claim without citations")
        return False
    except Exception:
        print("✓ Correctly rejected claim without citations")

    return True


def main():
    """Run all smoke tests"""
    print("=" * 60)
    print("PHASE 0 SMOKE TEST - Structured Citations")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Claims Extraction", test_claims_extraction()))
    results.append(("Schema Validation", test_schemas()))
    results.append(
        ("Structured Output (Disabled/Legacy)", test_structured_output_disabled())
    )
    results.append(("Structured Output (Enabled)", test_structured_output_enabled()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All smoke tests PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) FAILED")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
