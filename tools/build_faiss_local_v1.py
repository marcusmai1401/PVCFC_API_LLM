#!/usr/bin/env python3
"""
Build a local embedding vector index (FAISS or numpy fallback) from BM25 artifacts.
V1: With batch processing and memory guard for <12GB RAM usage

Usage:
    python tools/build_faiss_local.py \
        --bm25-dir artifacts/index/bm25 \
        --faiss-dir artifacts/index/faiss \
        --embedding_model intfloat/multilingual-e5-small

If FAISS is unavailable, falls back to numpy cosine search.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import numpy as np
from dotenv import load_dotenv
from loguru import logger

from app.rag.indexers.faiss_indexer import VectorIndexer
from app.services.embedding_enhanced import EmbeddingService, get_embedding_service

# Load environment variables
load_dotenv()


def get_memory_usage_gb():
    """Get current memory usage in GB"""
    process = psutil.Process()
    return process.memory_info().rss / (1024 * 1024 * 1024)


def load_bm25_corpus(bm25_dir: Path) -> tuple[List[str], List[Dict[str, Any]]]:
    """Load BM25 corpus from directory"""
    # Try both naming conventions
    texts_file = bm25_dir / "texts.json"
    if not texts_file.exists():
        texts_file = bm25_dir / "documents.json"

    with open(texts_file, "r", encoding="utf-8") as f:
        texts = json.load(f)
    with open(bm25_dir / "metadata.json", "r", encoding="utf-8") as f:
        metas = json.load(f)

    assert len(texts) == len(
        metas
    ), f"Text/metadata count mismatch: {len(texts)} vs {len(metas)}"
    return texts, metas


def batch_embed_texts(
    embedding_service: EmbeddingService,
    texts: List[str],
    batch_size: int = 100,
    max_memory_gb: float = 10.0,
) -> np.ndarray:
    """
    Embed texts in batches to control memory usage

    Args:
        embedding_service: The embedding service to use
        texts: List of texts to embed
        batch_size: Number of texts per batch
        max_memory_gb: Maximum memory usage before forcing garbage collection

    Returns:
        Array of embeddings
    """
    total = len(texts)
    logger.info(f"Embedding {total} texts in batches of {batch_size}")

    all_embeddings = []

    for i in range(0, total, batch_size):
        batch_end = min(i + batch_size, total)
        batch_texts = texts[i:batch_end]

        # Check memory usage
        mem_usage = get_memory_usage_gb()
        if mem_usage > max_memory_gb:
            logger.warning(
                f"Memory usage high ({mem_usage:.2f} GB), forcing garbage collection"
            )
            gc.collect()

        logger.info(
            f"Processing batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size} "
            f"[{i+1}-{batch_end}/{total}] (Memory: {mem_usage:.2f} GB)"
        )

        # Embed batch
        try:
            batch_embeddings = embedding_service.embed_texts(batch_texts)
            all_embeddings.append(batch_embeddings)
        except Exception as e:
            logger.error(f"Failed to embed batch {i//batch_size + 1}: {e}")
            # Try with smaller batch
            if batch_size > 10:
                logger.info("Retrying with smaller batch size")
                for j in range(i, batch_end, 10):
                    sub_batch_end = min(j + 10, batch_end)
                    sub_batch = texts[j:sub_batch_end]
                    sub_embeddings = embedding_service.embed_texts(sub_batch)
                    all_embeddings.append(sub_embeddings)
            else:
                raise

        # Force garbage collection every 10 batches
        if (i // batch_size + 1) % 10 == 0:
            gc.collect()

    # Concatenate all embeddings
    logger.info("Concatenating embeddings...")
    result = np.vstack(all_embeddings)

    # Final garbage collection
    gc.collect()

    return result


def determine_batch_size(num_texts: int, embedding_dim: int = 384) -> int:
    """
    Determine optimal batch size based on available memory

    Args:
        num_texts: Total number of texts
        embedding_dim: Dimension of embeddings (default 384 for e5-small)

    Returns:
        Recommended batch size
    """
    # Get available memory
    mem = psutil.virtual_memory()
    available_gb = mem.available / (1024 * 1024 * 1024)

    # Estimate memory per embedding (float32 = 4 bytes per value)
    bytes_per_embedding = embedding_dim * 4
    mb_per_embedding = bytes_per_embedding / (1024 * 1024)

    # Use at most 2GB for a batch (conservative)
    max_batch_memory_gb = min(2.0, available_gb * 0.3)  # Use 30% of available
    max_batch_size = int(max_batch_memory_gb * 1024 / mb_per_embedding)

    # Clamp to reasonable range
    batch_size = min(max_batch_size, 500)  # Max 500 per batch
    batch_size = max(batch_size, 10)  # Min 10 per batch

    logger.info(
        f"Determined batch size: {batch_size} (Available memory: {available_gb:.2f} GB)"
    )

    return batch_size


def main():
    parser = argparse.ArgumentParser(
        description="Build FAISS index with batch processing and memory guard"
    )
    parser.add_argument(
        "--bm25-dir", type=Path, required=True, help="Directory containing BM25 index"
    )
    parser.add_argument(
        "--faiss-dir", type=Path, required=True, help="Directory to save FAISS index"
    )
    parser.add_argument(
        "--embedding_model",
        type=str,
        default=None,
        help="Embedding model name (default: from .env or intfloat/multilingual-e5-small)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for embedding (default: auto-determined)",
    )
    parser.add_argument(
        "--max-memory-gb",
        type=float,
        default=10.0,
        help="Maximum memory usage in GB (default: 10.0)",
    )

    args = parser.parse_args()

    bm25_dir: Path = args.bm25_dir
    faiss_dir: Path = args.faiss_dir

    logger.info("=" * 80)
    logger.info("FAISS INDEX BUILDER V1")
    logger.info("=" * 80)
    logger.info(f"BM25 directory: {bm25_dir}")
    logger.info(f"Output directory: {faiss_dir}")
    logger.info(f"Max memory: {args.max_memory_gb} GB")

    # Check BM25 directory exists
    if not bm25_dir.exists():
        logger.error(f"BM25 directory not found: {bm25_dir}")
        sys.exit(1)

    logger.info(f"Loading BM25 artifacts from: {bm25_dir}")
    texts, metas = load_bm25_corpus(bm25_dir)
    logger.info(f"Loaded {len(texts)} documents for embedding")

    # Determine embedding model
    if args.embedding_model:
        # Use specified model
        model_name = args.embedding_model
        logger.info(f"Using specified embedding model: {model_name}")
        emb = EmbeddingService(model_name=model_name)
    else:
        # Check environment variable
        model_name = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
        logger.info(f"Using embedding model from config: {model_name}")

        if model_name.startswith("models/"):
            # This looks like a Gemini model
            emb = get_embedding_service()
            logger.info(f"Using {emb.provider} embedding provider")
        else:
            # Use sentence-transformers
            emb = EmbeddingService(model_name=model_name)

    # Determine batch size
    if args.batch_size:
        batch_size = args.batch_size
    else:
        # Auto-determine based on embedding dimension
        # For e5-small, dimension is 384
        embedding_dim = 384 if "e5-small" in model_name else 768
        batch_size = determine_batch_size(len(texts), embedding_dim)

    # Embed texts in batches
    logger.info("Starting batch embedding process...")
    vecs = batch_embed_texts(
        emb, texts, batch_size=batch_size, max_memory_gb=args.max_memory_gb
    )

    logger.info(f"Generated embeddings shape: {vecs.shape}")

    # Build index
    logger.info("Building vector index...")
    indexer = VectorIndexer(dim=vecs.shape[1])

    # Build index with memory monitoring
    mem_before = get_memory_usage_gb()
    indexer.build(vecs, texts, metas)
    mem_after = get_memory_usage_gb()
    logger.info(
        f"Index built (Memory usage: {mem_before:.2f} GB -> {mem_after:.2f} GB)"
    )

    # Save index
    logger.info(f"Saving vector index to: {faiss_dir}")
    faiss_dir.mkdir(parents=True, exist_ok=True)
    indexer.save(faiss_dir)

    # Log final stats
    final_memory = get_memory_usage_gb()
    logger.info("=" * 80)
    logger.info("FAISS index building complete!")
    logger.info(f"Total documents indexed: {len(texts)}")
    logger.info(f"Embedding dimension: {vecs.shape[1]}")
    logger.info(f"Final memory usage: {final_memory:.2f} GB")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
