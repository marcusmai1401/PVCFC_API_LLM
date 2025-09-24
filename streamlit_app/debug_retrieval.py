"""
Debug script to check what's being retrieved from PDFs
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_retrieval():
    """Test what's actually being retrieved"""

    from app.deps.indices import get_index_manager
    from app.rag.query_transform import QueryTransformer

    print("=" * 60)
    print("TESTING RETRIEVAL FROM REAL PDFs")
    print("=" * 60)

    # Get index manager
    manager = get_index_manager()

    # Load indices
    print("\n1. Loading indices...")
    await manager.load_indices()

    # Get retriever
    retriever = manager.get_retriever()

    if retriever is None:
        print("❌ ERROR: Retriever is None!")
        return

    print("✅ Retriever loaded successfully")

    # Test queries
    test_queries = [
        "CO2 compressor",
        "steam turbine",
        "SPECIAL PURPOSE STEAM TURBINE DATA SHEET",
        "operating pressure",
        "ammonia",
        "gear maintenance",
    ]

    transformer = QueryTransformer(enable_hyde=False)

    for query in test_queries:
        print(f"\n" + "=" * 60)
        print(f"QUERY: {query}")
        print("=" * 60)

        # Transform query
        transformed = transformer.transform(query)

        # Search
        results = retriever.search(transformed, k=3)

        if not results:
            print(f"❌ No results found for '{query}'")
            continue

        print(f"✅ Found {len(results)} results")

        for i, result in enumerate(results, 1):
            print(f"\n--- Result {i} ---")
            print(f"Score: {result.score:.3f}")
            print(f"Document: {result.metadata.get('doc_id', 'Unknown')}")
            print(f"Page: {result.metadata.get('page', 'Unknown')}")
            print(f"Chunk ID: {result.chunk_id}")
            print(f"Content preview (first 500 chars):")
            print("-" * 40)
            print(result.text[:500])
            print("-" * 40)

    # Check what documents are indexed
    print("\n" + "=" * 60)
    print("INDEXED DOCUMENTS CHECK")
    print("=" * 60)

    # Check BM25 index
    if hasattr(retriever, "bm25_retriever") and retriever.bm25_retriever:
        bm25 = retriever.bm25_retriever
        if hasattr(bm25, "chunks"):
            unique_docs = set()
            for chunk in bm25.chunks:
                if "doc_id" in chunk.metadata:
                    unique_docs.add(chunk.metadata["doc_id"])
            print(f"\nBM25 Index contains {len(unique_docs)} unique documents:")
            for doc in sorted(unique_docs):
                print(f"  - {doc}")

    # Check FAISS index
    if hasattr(retriever, "faiss_retriever") and retriever.faiss_retriever:
        faiss = retriever.faiss_retriever
        if hasattr(faiss, "chunks"):
            unique_docs = set()
            for chunk in faiss.chunks:
                if "doc_id" in chunk.metadata:
                    unique_docs.add(chunk.metadata["doc_id"])
            print(f"\nFAISS Index contains {len(unique_docs)} unique documents:")
            for doc in sorted(unique_docs):
                print(f"  - {doc}")


if __name__ == "__main__":
    asyncio.run(test_retrieval())
