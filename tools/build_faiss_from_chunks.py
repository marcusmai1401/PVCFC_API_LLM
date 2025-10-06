#!/usr/bin/env python3
"""
Build FAISS index directly from chunks.jsonl
Simplified version that doesn't depend on BM25 format
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

# Add project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import numpy as np
from loguru import logger

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

from app.rag.indexers.faiss_indexer import VectorIndexer
from app.services.embedding_enhanced import UniversalEmbeddingService


def load_chunks_from_jsonl(jsonl_file: Path) -> tuple[List[str], List[Dict]]:
    """Load texts and metadata from chunks.jsonl"""
    logger.info(f"Loading chunks from: {jsonl_file}")

    texts = []
    metadatas = []

    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                chunk = json.loads(line)
                texts.append(chunk.get("text", ""))

                # Build metadata
                meta = {
                    "chunk_id": chunk.get("chunk_id"),
                    "doc_id": chunk.get("doc_id"),
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "char_count": chunk.get("char_count"),
                    "parent_chunk_id": chunk.get("parent_chunk_id"),
                    "heading": chunk.get("heading"),
                    "level": chunk.get("level"),
                }

                # Add metadata fields
                if "metadata" in chunk:
                    meta.update(chunk["metadata"])

                metadatas.append(meta)

            except Exception as e:
                logger.warning(f"Error at line {line_num}: {e}")
                continue

    logger.info(f"Loaded {len(texts)} chunks from JSONL")
    return texts, metadatas


def main():
    parser = argparse.ArgumentParser(description="Build FAISS index from chunks.jsonl")
    parser.add_argument("--chunks-file", required=True, help="Path to chunks.jsonl")
    parser.add_argument(
        "--output-dir", required=True, help="Output directory for FAISS index"
    )
    parser.add_argument(
        "--batch-size", type=int, default=256, help="Batch size for embeddings"
    )
    args = parser.parse_args()

    chunks_file = Path(args.chunks_file)
    output_dir = Path(args.output_dir)

    if not chunks_file.exists():
        logger.error(f"Chunks file not found: {chunks_file}")
        return 1

    logger.info("=" * 80)
    logger.info("FAISS INDEX BUILDER (Direct from chunks.jsonl)")
    logger.info("=" * 80)
    logger.info(f"Chunks file: {chunks_file}")
    logger.info(f"Output dir: {output_dir}")
    logger.info(f"Batch size: {args.batch_size}")

    # Load chunks
    texts, metadatas = load_chunks_from_jsonl(chunks_file)

    if not texts:
        logger.error("No chunks loaded!")
        return 1

    logger.info(f"Loaded {len(texts)} chunks")

    # Initialize embedding service
    logger.info("\nInitializing embedding service...")
    embedding_service = UniversalEmbeddingService(
        provider="gemini", model_name="gemini-embedding-001"
    )

    # Generate embeddings
    logger.info("\nGenerating embeddings...")
    start_time = time.time()

    embeddings = embedding_service.embed_texts(texts)

    elapsed = time.time() - start_time
    logger.info(
        f"✓ Embeddings generated: shape={embeddings.shape}, time={elapsed:.2f}s"
    )
    logger.info(f"  Throughput: {len(texts)/elapsed:.2f} texts/sec")

    # Build FAISS index
    logger.info("\nBuilding FAISS index...")
    indexer = VectorIndexer(dim=embeddings.shape[1])
    indexer.build(embeddings, texts, metadatas)

    logger.info(f"✓ FAISS index built with {len(texts)} vectors")

    # Save everything
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"\nSaving to: {output_dir}")

    # Save index using the built-in save method
    indexer.save(str(output_dir))
    logger.info("✓ Saved FAISS index, texts, and metadata")

    # Save embeddings (optional, for debugging)
    np.save(output_dir / "embeddings.npy", embeddings)
    logger.info("✓ Saved embeddings.npy")

    # Test search
    logger.info("\n" + "=" * 80)
    logger.info("Testing FAISS search...")
    test_query = "CO2 compressor performance"
    query_embedding = embedding_service.embed_texts([test_query])

    results = indexer.search(query_embedding, top_k=3)

    logger.info(f"Query: '{test_query}'")
    logger.info("Top 3 results:")
    for idx, (doc_idx, score) in enumerate(results[0], 1):
        text = (
            texts[doc_idx][:100] + "..."
            if len(texts[doc_idx]) > 100
            else texts[doc_idx]
        )
        logger.info(f"  {idx}. Score: {score:.4f}, Text: {text}")

    logger.info("\n" + "=" * 80)
    logger.info("✅ FAISS index build complete!")
    logger.info("=" * 80)
    logger.info(f"Total chunks: {len(texts)}")
    logger.info(f"Embedding dimension: {embeddings.shape[1]}")
    logger.info(f"Output location: {output_dir.absolute()}")

    # Print metrics
    if hasattr(embedding_service, "metrics"):
        logger.info("\nEmbedding metrics:")
        for key, value in embedding_service.metrics.items():
            logger.info(f"  {key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
