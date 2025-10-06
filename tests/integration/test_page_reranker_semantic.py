import os
import pickle
from pathlib import Path

import numpy as np

from app.config import get_config
from app.rag.page_reranker import PageReranker


def test_semantic_reranking_hybrid_runs():
    cfg = get_config()
    # Load BM25 index to get ordering
    with open(cfg.page_bm25_index_path, "rb") as f:
        data = pickle.load(f)
    doc_ids = data["doc_ids"]
    pages = data["pages"]

    assert len(doc_ids) == len(pages) and len(doc_ids) > 0

    # Create deterministic random embeddings aligned to BM25 order
    rng = np.random.default_rng(42)
    dim = 16
    embs = rng.standard_normal((len(doc_ids), dim)).astype(np.float32)
    # Normalize to unit vectors
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
    embs = embs / norms

    # Save NPZ to configured path
    out_path = cfg.page_embeddings_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(out_path),
        embeddings=embs,
        doc_ids=np.array(doc_ids, dtype=object),
        pages=np.array(pages, dtype=np.int32),
        dim=np.int32(dim),
        provider=np.array(["local"], dtype=object),
        model=np.array(["unit-test"], dtype=object),
    )

    # Pick a sample doc_id present in index
    target_doc = doc_ids[0]

    reranker = PageReranker()
    results = reranker.rank_pages_for_doc(
        query="pressure rating",
        doc_id=target_doc,
        top_k=3,
    )

    # Basic assertions: results exist and have expected structure
    assert isinstance(results, list)
    assert len(results) <= 3
    if results:
        page, score = results[0]
        assert isinstance(page, int)
        assert isinstance(score, float)
