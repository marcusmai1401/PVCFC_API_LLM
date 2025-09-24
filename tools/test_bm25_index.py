#!/usr/bin/env python
"""Test BM25 indexer"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger

from app.rag.indexers.bm25_indexer import BM25Indexer


def test_bm25():
    logger.info("Testing BM25 Indexer")

    # Create test documents
    texts = [
        "The CO2 compressor operates at high pressure",
        "Steam turbine specifications include temperature limits",
        "Safety requirements must be followed",
    ]
    metadatas = [{"doc_id": f"doc_{i}"} for i in range(len(texts))]

    # Build index
    indexer = BM25Indexer()
    indexer.build_index(texts, metadatas)
    logger.info(f"✅ Built index with {len(texts)} documents")

    # Test search
    results = indexer.search("compressor pressure", top_k=2)
    logger.info(f"✅ Search returned {len(results)} results")

    return True


if __name__ == "__main__":
    test_bm25()
