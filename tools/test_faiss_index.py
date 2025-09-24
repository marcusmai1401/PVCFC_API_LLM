#!/usr/bin/env python
"""Test FAISS indexer"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
from loguru import logger

from app.rag.indexers.faiss_indexer import VectorIndexer


def test_faiss():
    logger.info("Testing FAISS Indexer")

    # Create test embeddings
    dim = 384
    num_docs = 3
    embeddings = np.random.randn(num_docs, dim).astype(np.float32)
    texts = [
        "The CO2 compressor operates at high pressure",
        "Steam turbine specifications include temperature limits",
        "Safety requirements must be followed",
    ]
    metadatas = [{"doc_id": f"doc_{i}"} for i in range(len(texts))]

    # Build index
    indexer = VectorIndexer(dim=dim)
    indexer.build(embeddings, texts, metadatas)
    logger.info(f"✅ Built index with {num_docs} vectors (dim={dim})")

    # Test search
    query_vec = np.random.randn(1, dim).astype(np.float32)
    results = indexer.search(query_vec, top_k=2)
    logger.info(f"✅ Search returned {len(results[0])} results")

    return True


if __name__ == "__main__":
    test_faiss()
