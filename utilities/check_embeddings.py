#!/usr/bin/env python
"""Quick check for page embeddings"""
import numpy as np

from app.config import get_config

cfg = get_config()
path = cfg.page_embeddings_path

print(f"Embeddings path: {path}")
print(f"Exists: {path.exists()}")

if path.exists():
    data = np.load(str(path), allow_pickle=True)
    embs = data["embeddings"]
    print(f"Shape: {embs.shape}")
    print(f"Model: {data['model'][0] if 'model' in data else 'N/A'}")
    print(f"Provider: {data['provider'][0] if 'provider' in data else 'N/A'}")
    print(f"Dimension: {data['dim'] if 'dim' in data else embs.shape[1]}")

    # Verify alignment with BM25
    doc_ids_emb = list(data["doc_ids"].tolist())
    pages_emb = list(data["pages"].tolist())

    import pickle

    with open(cfg.page_bm25_index_path, "rb") as f:
        bm25_data = pickle.load(f)
    doc_ids_bm25 = bm25_data["doc_ids"]
    pages_bm25 = bm25_data["pages"]

    aligned = doc_ids_emb == doc_ids_bm25 and pages_emb == pages_bm25
    print(f"Aligned with BM25: {aligned}")

    if not aligned:
        print(f"  BM25 count: {len(doc_ids_bm25)}")
        print(f"  Embeddings count: {len(doc_ids_emb)}")
        if len(doc_ids_bm25) == len(doc_ids_emb):
            mismatches = sum(
                1
                for i in range(len(doc_ids_bm25))
                if doc_ids_bm25[i] != doc_ids_emb[i] or pages_bm25[i] != pages_emb[i]
            )
            print(f"  Mismatches: {mismatches}")
else:
    print("Embeddings file not found.")
