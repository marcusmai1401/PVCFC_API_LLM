#!/usr/bin/env python
"""
Test hybrid search (BM25 + FAISS) functionality
"""
import sys
from pathlib import Path

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.indexers.bm25_indexer import BM25Indexer
from app.rag.indexers.faiss_indexer import VectorIndexer
from app.services.embedding import EmbeddingService


def main():
    """Test hybrid search with both BM25 and FAISS"""

    # Test queries
    queries = [
        "CO2 compressor operating pressure",
        "equipment tag KT06101",
        "steam turbine specifications",
    ]

    logger.info("=== Testing Hybrid Search (BM25 + FAISS) ===")

    # Load BM25 index
    logger.info("Loading BM25 index...")
    bm25 = BM25Indexer()
    bm25_dir = Path("artifacts/index/bm25")
    bm25.load_index(str(bm25_dir))
    logger.info(f"BM25 index loaded: {len(bm25.documents)} documents")

    # Load FAISS index
    logger.info("Loading FAISS index...")
    faiss = VectorIndexer()
    faiss_dir = Path("artifacts/index/faiss")
    faiss.load(str(faiss_dir))
    logger.info(f"FAISS index loaded: {len(faiss.documents)} documents")

    # Initialize embedding service for FAISS search
    embedding_service = EmbeddingService()

    # Test each query
    for query in queries:
        logger.info(f"\n=== Query: '{query}' ===")

        # BM25 search
        logger.info("BM25 Results:")
        bm25_results = bm25.search(query, top_k=3)
        for i, result in enumerate(bm25_results, 1):
            text_preview = result["text"][:100].replace("\n", " ")
            logger.info(f"  #{i} (score={result['score']:.2f}): {text_preview}...")

        # FAISS search
        logger.info("FAISS Results:")
        query_embedding = embedding_service.embed_text(query)
        # VectorIndexer expects batch input, so add batch dimension
        query_batch = query_embedding.reshape(1, -1)
        faiss_results_batch = faiss.search(query_batch, top_k=3)
        faiss_results = faiss_results_batch[0] if faiss_results_batch else []
        for i, (idx, score) in enumerate(faiss_results, 1):
            text_preview = faiss.documents[idx].text[:100].replace("\n", " ")
            logger.info(f"  #{i} (score={score:.3f}): {text_preview}...")

        # Simple fusion (could be improved with RRF or weighted fusion)
        logger.info("Hybrid Results (simple fusion):")
        # Collect all unique results
        seen_texts = set()
        hybrid_results = []

        # Add BM25 results
        for result in bm25_results[:2]:
            text = result["text"][:100]
            if text not in seen_texts:
                seen_texts.add(text)
                hybrid_results.append(("BM25", result["score"], text))

        # Add FAISS results
        for idx, score in faiss_results[:2]:
            text = faiss.documents[idx].text[:100]
            if text not in seen_texts:
                seen_texts.add(text)
                hybrid_results.append(("FAISS", score, text))

        # Display hybrid results
        for i, (source, score, text) in enumerate(hybrid_results[:3], 1):
            text_preview = text.replace("\n", " ")
            logger.info(f"  #{i} [{source}] (score={score:.3f}): {text_preview}...")

    logger.info("\n=== Phase 1 Complete! ===")
    logger.info("✅ BM25 index: Working")
    logger.info("✅ FAISS index: Working")
    logger.info("✅ Hybrid search: Ready for Phase 2 RAG API")
    logger.info("\nNext steps for Phase 2:")
    logger.info("1. Create /api/v1/ask endpoint")
    logger.info("2. Implement retrieval with hybrid search")
    logger.info("3. Add LLM generation with Gemini 2.5")
    logger.info("4. Implement citations from retrieved chunks")


if __name__ == "__main__":
    main()
