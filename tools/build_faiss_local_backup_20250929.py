#!/usr/bin/env python3
"""
Build a local embedding vector index (FAISS or numpy fallback) from BM25 artifacts.

Usage:
    python tools/build_faiss_local.py \
        --bm25-dir artifacts/index/bm25 \
        --faiss-dir artifacts/index/faiss \
        --model BAAI/bge-small-en-v1.5

If FAISS is unavailable, falls back to numpy cosine search.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import numpy as np
from loguru import logger

from app.rag.indexers.faiss_indexer import VectorIndexer
from app.services.embedding_enhanced import get_embedding_service


def load_bm25_corpus(bm25_dir: Path) -> tuple[List[str], List[Dict[str, Any]]]:
    # Try both naming conventions
    texts_file = bm25_dir / "texts.json"
    if not texts_file.exists():
        texts_file = bm25_dir / "documents.json"

    with open(texts_file, "r", encoding="utf-8") as f:
        texts = json.load(f)
    with open(bm25_dir / "metadata.json", "r", encoding="utf-8") as f:
        metas = json.load(f)
    assert len(texts) == len(metas)
    return texts, metas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bm25-dir", type=Path, required=True)
    parser.add_argument("--faiss-dir", type=Path, required=True)
    parser.add_argument(
        "--model", type=str, default=None, help="sentence-transformers model name"
    )
    args = parser.parse_args()

    bm25_dir: Path = args.bm25_dir
    faiss_dir: Path = args.faiss_dir

    logger.info(f"Loading BM25 artifacts from: {bm25_dir}")
    texts, metas = load_bm25_corpus(bm25_dir)
    logger.info(f"Loaded {len(texts)} documents for embedding")

    # Use embedding service from .env configuration (supports Gemini)
    if args.model:
        # If model specified, override the config
        from app.services.embedding_enhanced import EmbeddingService

        emb = EmbeddingService(model_name=args.model)
    else:
        # Use configuration from .env (Gemini if configured)
        emb = get_embedding_service()
        logger.info(
            f"Using {emb.provider} embedding provider with model {emb.model_name}"
        )

    vecs = emb.embed_texts(texts)

    indexer = VectorIndexer(dim=vecs.shape[1])
    indexer.build(vecs, texts, metas)

    logger.info(f"Saving vector index to: {faiss_dir}")
    indexer.save(faiss_dir)
    logger.info("Done.")


if __name__ == "__main__":
    main()
