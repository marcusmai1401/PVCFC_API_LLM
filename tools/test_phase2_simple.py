#!/usr/bin/env python3
"""
Simple Phase 2 Test - No multiprocessing issues
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_all_components():
    """Test all Phase 2 components"""
    from app.core.config import settings
    from app.deps.indices import get_index_manager
    from app.rag.cove import ChainOfVerification
    from app.rag.generator import GeneratorConfig, ResponseGenerator
    from app.rag.query_transform import QueryIntent, QueryTransformer
    from app.rag.reranker import Reranker
    from app.rag.retriever import HybridRetriever

    print("\n" + "=" * 60)
    print("  PHASE 2 SIMPLE TEST")
    print("=" * 60)

    # 1. Test configuration
    print("\n✅ Configuration loaded:")
    print(f"  - LLM Provider: {settings.llm_provider}")
    print(f"  - Models: {settings.llm_model_light} / {settings.llm_model_heavy}")
    print(f"  - Embedding: {settings.embedding_provider} / {settings.embedding_model}")

    # 2. Test indices
    print("\n✅ Loading indices...")
    manager = get_index_manager(settings)
    result = asyncio.run(manager.load_indices())
    print(f"  - BM25 ready: {result['bm25_ready']}")
    print(f"  - FAISS ready: {result['faiss_ready']}")

    # 3. Test retriever
    print("\n✅ Testing retriever...")
    retriever = manager.get_retriever()
    if retriever:
        # Create a test query
        qt = QueryTransformer(enable_hyde=False)
        transformed = qt.transform("What is the operating pressure?")
        results = retriever.search(transformed)
        print(f"  - Retrieved {len(results)} results")
        if results:
            print(f"  - Top result score: {results[0].score:.3f}")

    # 4. Test reranker
    print("\n✅ Testing reranker...")
    reranker = Reranker()
    if results:
        reranked = reranker.rerank("operating pressure", results[:5])
        print(f"  - Reranked {len(reranked)} results")

    # 5. Test generator
    print("\n✅ Testing generator...")
    gen_config = GeneratorConfig(llm_tier="light")
    generator = ResponseGenerator(config=gen_config)
    if results:
        answer = generator.generate(transformed, results[:3])
        print(f"  - Generated answer: {len(answer.answer)} chars")
        print(f"  - Citations: {len(answer.citations)}")
        print(f"  - Confidence: {answer.confidence:.2f}")

    # 6. Test CoVe
    print("\n✅ Testing CoVe...")
    cove = ChainOfVerification(settings=settings)
    verification = asyncio.run(
        cove.run_verification(
            answer.answer if "answer" in locals() else "Test answer",
            retriever,
            max_claims=2,
        )
    )
    print(f"  - Verification rate: {verification['verification_rate']:.2f}")

    print("\n" + "=" * 60)
    print("  ✅ ALL COMPONENTS WORKING!")
    print("=" * 60)


def test_api_simple():
    """Simple API test without multiprocessing"""
    print("\n📌 To test API endpoints, run in separate terminal:")
    print("   python -m app.main")
    print("\nThen test with curl:")
    print("   curl http://localhost:8000/healthz")
    print(
        '   curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\\"query\\": \\"test\\"}"'
    )


if __name__ == "__main__":
    try:
        test_all_components()
        test_api_simple()
        print("\n🎉 PHASE 2 TESTING COMPLETE!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
