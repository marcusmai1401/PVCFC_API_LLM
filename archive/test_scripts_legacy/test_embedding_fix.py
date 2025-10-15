#!/usr/bin/env python3
"""
Quick test to verify embedding service fix for asyncio.run() issue
"""
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_embedding_service():
    """Test that embedding service works without asyncio errors."""
    print("=" * 60)
    print("Testing Embedding Service Fix")
    print("=" * 60)

    try:
        from app.services.embedding_enhanced import UniversalEmbeddingService

        print("\n[1/3] Creating embedding service...")
        service = UniversalEmbeddingService(provider="gemini")
        print("✓ Service created successfully")

        print("\n[2/3] Testing single text embedding...")
        test_text = "This is a test query for embedding"
        embedding = service.embed_text(test_text)
        print(
            f"✓ Embedding generated: shape={embedding.shape}, dtype={embedding.dtype}"
        )

        print("\n[3/3] Testing batch embedding...")
        test_texts = [
            "First test text",
            "Second test text",
            "Third test text",
        ]
        embeddings = service.embed_texts(test_texts)
        print(
            f"✓ Batch embeddings generated: shape={embeddings.shape}, dtype={embeddings.dtype}"
        )

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nEmbedding service is working correctly.")
        print("The asyncio.run() issue has been fixed.")
        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED!")
        print("=" * 60)
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_retriever_search():
    """Test that retriever search works with fixed embedding."""
    print("\n" + "=" * 60)
    print("Testing Retriever with Fixed Embedding")
    print("=" * 60)

    try:
        from app.rag.query_transform import QueryTransformer, TransformedQuery
        from app.rag.retriever import create_hybrid_retriever

        print("\n[1/2] Creating retriever...")
        retriever = create_hybrid_retriever()
        print("✓ Retriever created successfully")

        print("\n[2/2] Testing search...")
        # Create a simple transformed query
        query = TransformedQuery(
            original="test query",
            normalized="test query",
            intent="ask",
            filters=None,
            hyde_queries=None,
            language="en",
        )

        results = retriever.search(query)
        print(f"✓ Search completed: {len(results)} results returned")

        if results:
            print(f"\nFirst result preview:")
            print(f"  Score: {results[0].score:.4f}")
            print(f"  Source: {results[0].source}")
            print(f"  Text: {results[0].text[:100]}...")

        print("\n" + "=" * 60)
        print("✅ RETRIEVER TEST PASSED!")
        print("=" * 60)
        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ RETRIEVER TEST FAILED!")
        print("=" * 60)
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🔍 EMBEDDING FIX VERIFICATION\n")

    # Test 1: Embedding service
    test1_passed = test_embedding_service()

    # Test 2: Retriever (if test 1 passed)
    test2_passed = False
    if test1_passed:
        print("\n" + "─" * 60)
        test2_passed = test_retriever_search()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Embedding Service: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Retriever Search:  {'✅ PASS' if test2_passed else '❌ FAIL'}")

    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! The fix is working correctly.")
        print("\nYou can now:")
        print("  1. Restart the API server")
        print("  2. Test /ask endpoint")
        print("  3. FAISS should now work properly")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")

    sys.exit(0 if (test1_passed and test2_passed) else 1)
