"""
Test script to verify production system is ready
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio

from app.deps.indices import IndexManager
from app.rag.retriever import create_hybrid_retriever


async def test_system():
    print("=" * 80)
    print("PRODUCTION SYSTEM READINESS CHECK")
    print("=" * 80)
    print()

    # Test 1: Check index files
    print("📂 1. Checking index files...")
    project_root = Path(__file__).parent
    bm25_path = project_root / "artifacts" / "index_production" / "bm25"
    faiss_path = project_root / "artifacts" / "index_production" / "faiss"

    bm25_exists = (bm25_path / "bm25_index.pkl").exists()
    faiss_exists = (faiss_path / "faiss.index").exists()

    print(f"   BM25 index: {'✅ Found' if bm25_exists else '❌ Missing'}")
    print(f"   FAISS index: {'✅ Found' if faiss_exists else '❌ Missing'}")

    if not (bm25_exists and faiss_exists):
        print("\n❌ Index files missing! Run build_production_indices.py first.")
        return False

    print()

    # Test 2: Load indices
    print("🔄 2. Loading indices...")
    try:
        manager = IndexManager()
        result = await manager.load_indices()

        if result["status"] == "loaded":
            print("   ✅ Indices loaded successfully")
            print(f"   - BM25 ready: {result['bm25_ready']}")
            print(f"   - FAISS ready: {result['faiss_ready']}")
            print(f"   - Retriever ready: {result['retriever_ready']}")

            if result.get("statistics"):
                stats = result["statistics"]
                print(f"   - Documents: {stats.get('bm25', {}).get('chunk_count', 0)}")
                print(f"   - Vectors: {stats.get('faiss', {}).get('vector_count', 0)}")
        else:
            print(f"   ❌ Failed to load indices: {result.get('error')}")
            return False
    except Exception as e:
        print(f"   ❌ Error loading indices: {e}")
        import traceback

        traceback.print_exc()
        return False

    print()

    # Test 3: Test retrieval
    print("🔍 3. Testing retrieval...")
    try:
        retriever = manager.get_retriever()
        if retriever is None:
            print("   ❌ Retriever not initialized")
            return False

        # Test query - need to create TransformedQuery
        from app.rag.query_transform import TransformedQuery

        test_query = "What is the compressor performance?"
        print(f"   Query: '{test_query}'")

        # Create a simple TransformedQuery
        transformed = TransformedQuery(
            original=test_query,
            normalized=test_query,
            intent="factual",
            hyde_queries=[],
            filters=None,
        )

        results = retriever.search(transformed_query=transformed)

        if results:
            print(f"   ✅ Retrieved {len(results)} results")
            print(f"   - Top result score: {results[0].score:.4f}")
            print(f"   - Doc ID: {results[0].doc_id or 'N/A'}")
            print(f"   - Source: {results[0].source}")
        else:
            print("   ⚠️  No results returned (may be normal if query doesn't match)")
    except Exception as e:
        print(f"   ❌ Error during retrieval: {e}")
        import traceback

        traceback.print_exc()
        return False

    print()
    print("=" * 80)
    print("✅ SYSTEM IS READY FOR PRODUCTION!")
    print("=" * 80)
    print()
    print("🚀 Next steps:")
    print("   1. Start API: uvicorn app.main:app --reload")
    print("   2. Start UI: streamlit run streamlit_app/app.py")
    print()

    return True


if __name__ == "__main__":
    result = asyncio.run(test_system())
    sys.exit(0 if result else 1)
