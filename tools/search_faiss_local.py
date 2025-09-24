#!/usr/bin/env python3
"""
Search the local vector index (FAISS or numpy fallback).

Usage:
    python tools/search_faiss_local.py \
        --faiss-dir artifacts/index/faiss \
        --model BAAI/bge-small-en-v1.5 \
        --query "your question" --k 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import numpy as np
from loguru import logger

from app.rag.indexers.faiss_indexer import VectorIndexer
from app.services.embedding import EmbeddingService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--faiss-dir", type=Path, required=True)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--query", type=str, required=True)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    faiss_dir: Path = args.faiss_dir

    # Load index
    indexer = VectorIndexer()
    indexer.load(faiss_dir)

    emb = EmbeddingService(model_name=args.model)
    qvec = emb.embed_text(args.query)
    hits = indexer.search(qvec[None, :], top_k=args.k)[0]

    # load texts for display if stored
    texts_path = faiss_dir / "texts.json"
    texts = None
    if texts_path.exists():
        with open(texts_path, "r", encoding="utf-8") as f:
            texts = json.load(f)

    for rank, (doc_idx, score) in enumerate(hits, start=1):
        text = indexer.documents[doc_idx].text if texts is None else texts[doc_idx]
        snippet = (text[:200] + "...") if len(text) > 200 else text
        logger.info(f"#{rank} score={score:.4f} idx={doc_idx} | {snippet}")


if __name__ == "__main__":
    main()
