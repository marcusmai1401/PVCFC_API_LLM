from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

try:
    import faiss  # type: ignore

    _FAISS_AVAILABLE = True
except Exception:
    _FAISS_AVAILABLE = False


@dataclass
class VectorDoc:
    text: str
    embedding: np.ndarray
    metadata: Dict[str, Any]


class VectorIndexer:
    """Vector indexer using FAISS if available; falls back to numpy search."""

    def __init__(self, dim: Optional[int] = None, use_gpu: bool = False):
        self.dim = dim
        self.use_gpu = use_gpu and _FAISS_AVAILABLE
        self.index = None
        self.documents: List[VectorDoc] = []

    def build(
        self, embeddings: np.ndarray, texts: List[str], metadatas: List[Dict[str, Any]]
    ):
        assert len(embeddings) == len(texts) == len(metadatas)
        self.dim = embeddings.shape[1]

        # Store docs
        self.documents = [
            VectorDoc(text=texts[i], embedding=embeddings[i], metadata=metadatas[i])
            for i in range(len(texts))
        ]

        if _FAISS_AVAILABLE:
            index = faiss.IndexFlatIP(self.dim)
            if self.use_gpu:
                res = faiss.StandardGpuResources()
                index = faiss.index_cpu_to_gpu(res, 0, index)
            index.add(embeddings)
            self.index = index
            logger.info(f"Built FAISS index with {len(texts)} vectors (dim={self.dim})")
        else:
            # Numpy fallback: store normalized embeddings for cosine similarity
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12
            self.index = (embeddings / norms).astype(np.float32, copy=False)
            logger.info(
                f"FAISS not available. Using numpy fallback for {len(texts)} vectors (dim={self.dim})"
            )

    def search(
        self, query_embeddings: np.ndarray, top_k: int = 5
    ) -> List[List[Tuple[int, float]]]:
        if self.index is None:
            return []

        if _FAISS_AVAILABLE:
            scores, indices = self.index.search(query_embeddings, top_k)
            results: List[List[Tuple[int, float]]] = []
            for row_idx in range(indices.shape[0]):
                hits = []
                for j in range(top_k):
                    idx = int(indices[row_idx, j])
                    if idx == -1:
                        continue
                    hits.append((idx, float(scores[row_idx, j])))
                results.append(hits)
            return results

        # numpy fallback: cosine similarity via dot product (embeddings already normalized)
        q_norms = np.linalg.norm(query_embeddings, axis=1, keepdims=True) + 1e-12
        q = (query_embeddings / q_norms).astype(np.float32, copy=False)
        scores = q @ self.index.T  # (n_queries, n_docs)
        top_indices = np.argpartition(
            -scores, kth=min(top_k, scores.shape[1] - 1), axis=1
        )[:, :top_k]
        results: List[List[Tuple[int, float]]] = []
        for i in range(scores.shape[0]):
            pairs = [(int(idx), float(scores[i, idx])) for idx in top_indices[i]]
            pairs.sort(key=lambda x: x[1], reverse=True)
            results.append(pairs[:top_k])
        return results

    def save(self, index_dir: str | Path):
        index_dir = Path(index_dir)
        index_dir.mkdir(parents=True, exist_ok=True)

        # Save texts and metadata
        import json
        import pickle

        texts = [d.text for d in self.documents]
        metas = [d.metadata for d in self.documents]
        with open(index_dir / "texts.json", "w", encoding="utf-8") as f:
            json.dump(texts, f, ensure_ascii=False, indent=2)
        # Save metadata as JSON to avoid pickle security concerns
        with open(index_dir / "metadatas.json", "w", encoding="utf-8") as f:
            json.dump(metas, f, ensure_ascii=False, indent=2)

        if _FAISS_AVAILABLE:
            faiss.write_index(
                faiss.index_gpu_to_cpu(self.index) if self.use_gpu else self.index,
                str(index_dir / "faiss.index"),
            )
        else:
            np.save(index_dir / "embeddings.npy", self.index)

    def load(self, index_dir: str | Path):
        import json
        import pickle

        index_dir = Path(index_dir)
        with open(index_dir / "texts.json", "r", encoding="utf-8") as f:
            texts = json.load(f)
        metas = None
        json_path = index_dir / "metadatas.json"
        pkl_path = index_dir / "metadatas.pkl"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                metas = json.load(f)
        elif pkl_path.exists():
            # Backward compatibility: load legacy pickle metadata
            with open(pkl_path, "rb") as f:
                metas = pickle.load(f)
        else:
            raise FileNotFoundError(
                f"Neither metadatas.json nor metadatas.pkl found in {index_dir}"
            )

        if _FAISS_AVAILABLE:
            self.index = faiss.read_index(str(index_dir / "faiss.index"))
            self.dim = self.index.d
            # embeddings not loaded for memory saving; keep texts/metas only
            self.documents = [
                VectorDoc(
                    text=texts[i],
                    embedding=np.empty((0,), dtype=np.float32),
                    metadata=metas[i],
                )
                for i in range(len(texts))
            ]
        else:
            self.index = np.load(index_dir / "embeddings.npy")
            self.dim = self.index.shape[1]
            self.documents = [
                VectorDoc(text=texts[i], embedding=self.index[i], metadata=metas[i])
                for i in range(len(texts))
            ]

        logger.info(
            f"Loaded vector index from {index_dir} with {len(texts)} docs (dim={self.dim})"
        )
