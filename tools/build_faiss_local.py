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
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil  # type: ignore

    _PSUTIL_AVAILABLE = True
except Exception:
    psutil = None  # type: ignore
    _PSUTIL_AVAILABLE = False

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import numpy as np
from loguru import logger

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:

    def load_dotenv():
        return None


from app.rag.indexers.faiss_indexer import VectorIndexer
from app.services.embedding_enhanced import EmbeddingService, get_embedding_service

# Load environment variables
load_dotenv()


def get_memory_usage_gb():
    """Get current memory usage in GB"""
    if _PSUTIL_AVAILABLE:
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024 * 1024)
    # Fallback when psutil not available
    return 0.0


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
) -> Tuple[np.ndarray, Dict[str, int]]:
    """
    Embed texts in batches to control memory usage

    Args:
        embedding_service: The embedding service to use
        texts: List of texts to embed
        batch_size: Number of texts per batch
        max_memory_gb: Maximum memory usage before forcing garbage collection

    Returns:
        Tuple of (Array of embeddings, metrics dict)
    """
    total = len(texts)
    logger.info(f"Embedding {total} texts")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Concurrency: {getattr(embedding_service, 'concurrency', 'N/A')}")
    logger.info(
        f"Max tokens per request: {getattr(embedding_service, 'max_tokens_per_req', 'N/A')}"
    )

    # Get initial metrics
    initial_metrics = getattr(embedding_service, "metrics", {}).copy()

    all_embeddings = []
    start_time = time.time()

    # Process all texts at once (micro-batching handled internally)
    try:
        logger.info("Starting embedding process (handled internally by service)...")
        embeddings = embedding_service.embed_texts(texts)
        all_embeddings.append(embeddings)
    except Exception as e:
        logger.error(f"Failed to embed texts: {e}")
        raise

    # Concatenate all embeddings
    if len(all_embeddings) > 1:
        logger.info("Concatenating embeddings...")
        result = np.vstack(all_embeddings)
    else:
        result = all_embeddings[0] if all_embeddings else np.array([])

    # Calculate metrics
    elapsed = time.time() - start_time
    final_metrics = getattr(embedding_service, "metrics", {}).copy()

    # Calculate deltas
    metrics = {
        "n_total": total,
        "n_embedded": len(result),
        "cache_hits": final_metrics.get("cache_hits", 0)
        - initial_metrics.get("cache_hits", 0),
        "api_calls": final_metrics.get("api_calls", 0)
        - initial_metrics.get("api_calls", 0),
        "retries": final_metrics.get("retries", 0) - initial_metrics.get("retries", 0),
        "rate_limit_events": final_metrics.get("rate_limit_events", 0)
        - initial_metrics.get("rate_limit_events", 0),
        "quarantine_count": final_metrics.get("quarantine_count", 0)
        - initial_metrics.get("quarantine_count", 0),
        "elapsed_seconds": elapsed,
        "throughput": total / elapsed if elapsed > 0 else 0,
    }

    # Log comprehensive metrics
    logger.info("=" * 60)
    logger.info("EMBEDDING METRICS:")
    logger.info(f"  Total texts: {metrics['n_total']}")
    logger.info(f"  Successfully embedded: {metrics['n_embedded']}")
    logger.info(f"  Cache hits: {metrics['cache_hits']}")
    logger.info(f"  API calls: {metrics['api_calls']}")
    logger.info(f"  Retries: {metrics['retries']}")
    logger.info(f"  Rate limit events: {metrics['rate_limit_events']}")
    logger.info(f"  Quarantined: {metrics['quarantine_count']}")
    logger.info(f"  Elapsed time: {metrics['elapsed_seconds']:.2f}s")
    logger.info(f"  Throughput: {metrics['throughput']:.2f} texts/s")
    logger.info("=" * 60)

    # Final garbage collection
    gc.collect()

    return result, metrics


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
    if _PSUTIL_AVAILABLE:
        mem = psutil.virtual_memory()
        available_gb = mem.available / (1024 * 1024 * 1024)
    else:
        available_gb = 8.0  # Assume 8 GB available as conservative default

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
        help="Batch size for embedding (default: from .env or auto-determined)",
    )
    parser.add_argument(
        "--max-memory-gb",
        type=float,
        default=10.0,
        help="Maximum memory usage in GB (default: 10.0)",
    )

    args = parser.parse_args()

    # Read additional config from environment
    embed_output_dim = int(os.getenv("EMBED_OUTPUT_DIM", "768"))
    embed_batch_size = int(os.getenv("EMBED_BATCH_SIZE", "256"))
    embed_concurrency = int(os.getenv("EMBED_CONCURRENCY", "8"))
    embed_task = os.getenv("EMBED_TASK", "RETRIEVAL_DOCUMENT")

    bm25_dir: Path = args.bm25_dir
    faiss_dir: Path = args.faiss_dir

    logger.info("=" * 80)
    logger.info("FAISS INDEX BUILDER V1")
    logger.info("=" * 80)
    logger.info(f"BM25 directory: {bm25_dir}")
    logger.info(f"Output directory: {faiss_dir}")
    logger.info(f"Max memory: {args.max_memory_gb} GB")
    logger.info(f"Embedding dimension: {embed_output_dim}")
    logger.info(f"Batch size (env): {embed_batch_size}")
    logger.info(f"Concurrency: {embed_concurrency}")
    logger.info(f"Task type: {embed_task}")

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
        # Use from env or auto-determine
        batch_size = embed_batch_size or determine_batch_size(
            len(texts), embed_output_dim
        )

    # Embed texts in batches
    logger.info("Starting batch embedding process...")
    logger.info(f"Model resolved: {getattr(emb, '_gemini_model', model_name)}")
    logger.info(f"Output dimension: {embed_output_dim}")

    vecs, metrics = batch_embed_texts(
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
    logger.info("FAISS INDEX BUILD COMPLETE!")
    logger.info(f"Total documents: {len(texts)}")
    logger.info(f"Successfully embedded: {metrics['n_embedded']}")
    logger.info(f"Embedding dimension: {vecs.shape[1]}")
    logger.info(f"Cache hits: {metrics['cache_hits']}")
    logger.info(f"API calls: {metrics['api_calls']}")
    logger.info(f"Retries: {metrics['retries']}")
    logger.info(f"Rate limit events: {metrics['rate_limit_events']}")
    logger.info(f"Quarantined: {metrics['quarantine_count']}")
    logger.info(f"Total time: {metrics['elapsed_seconds']:.2f}s")
    logger.info(f"Throughput: {metrics['throughput']:.2f} texts/s")
    logger.info(f"Final memory usage: {final_memory:.2f} GB")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
