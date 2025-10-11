"""
Reranker Service - BGE CrossEncoder for semantic reranking

Supports:
- Chunk-level reranking (basic)
- Document-level reranking (aggregate chunks by doc_id)
- Page-level reranking (aggregate chunks by doc_id + page)
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger
from sentence_transformers import CrossEncoder

from app.core.config import settings


class RerankerService:
    """
    Reranker service using BGE CrossEncoder models.

    Provides reranking at multiple levels:
    - Chunk level: rerank individual chunks
    - Document level: aggregate scores per document
    - Page level: aggregate scores per page within documents
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize reranker service.

        Args:
            model_name: CrossEncoder model name (default: BAAI/bge-reranker-base)
        """
        self.model_name = model_name or os.getenv(
            "RERANKER_MODEL", "BAAI/bge-reranker-base"
        )
        self._model: Optional[CrossEncoder] = None
        self.batch_size = int(os.getenv("RERANKER_BATCH_SIZE", "32"))

        logger.info(
            f"Initializing reranker service: model={self.model_name}, "
            f"batch_size={self.batch_size}"
        )

    def _ensure_model(self):
        """Lazy load the CrossEncoder model."""
        if self._model is None:
            logger.info(f"Loading CrossEncoder model: {self.model_name}")
            self._model = CrossEncoder(self.model_name, max_length=512)
            logger.info(f"CrossEncoder model loaded successfully")

    def rerank_chunks(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Rerank chunks using CrossEncoder.

        Args:
            query: User query
            chunks: List of chunk dicts with 'text' field
            top_k: Return only top K results (None = return all)

        Returns:
            List of (chunk, score) tuples sorted by relevance score (descending)
        """
        self._ensure_model()

        if not chunks:
            return []

        # Prepare query-text pairs
        pairs = [[query, chunk.get("text", "")] for chunk in chunks]

        # Get reranking scores
        logger.info(f"Reranking {len(chunks)} chunks for query: {query[:50]}...")
        scores = self._model.predict(pairs, batch_size=self.batch_size)

        # Combine chunks with scores
        chunk_scores = list(zip(chunks, scores))

        # Sort by score descending
        chunk_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top_k if specified
        if top_k is not None:
            chunk_scores = chunk_scores[:top_k]

        logger.info(
            f"Reranking complete. Top score: {chunk_scores[0][1]:.4f}, "
            f"Lowest score: {chunk_scores[-1][1]:.4f}"
        )

        return chunk_scores

    def rerank_documents(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        aggregation: str = "max",
    ) -> List[Tuple[str, float, List[Dict[str, Any]]]]:
        """
        Rerank at document level by aggregating chunk scores.

        Args:
            query: User query
            chunks: List of chunk dicts with 'doc_id' and 'text' fields
            top_k: Return only top K documents (None = return all)
            aggregation: Score aggregation method ('max', 'mean', 'top3_mean')

        Returns:
            List of (doc_id, aggregated_score, chunks) tuples sorted by score (descending)
        """
        self._ensure_model()

        if not chunks:
            return []

        # First, get reranking scores for all chunks
        chunk_scores = self.rerank_chunks(query, chunks, top_k=None)

        # Group by doc_id
        doc_chunks: Dict[str, List[Tuple[Dict[str, Any], float]]] = defaultdict(list)
        for chunk, score in chunk_scores:
            doc_id = chunk.get("doc_id", "unknown")
            doc_chunks[doc_id].append((chunk, score))

        # Aggregate scores per document
        doc_scores: List[Tuple[str, float, List[Dict[str, Any]]]] = []

        for doc_id, chunk_score_list in doc_chunks.items():
            scores = [score for _, score in chunk_score_list]
            chunks_list = [chunk for chunk, _ in chunk_score_list]

            if aggregation == "max":
                agg_score = max(scores)
            elif aggregation == "mean":
                agg_score = np.mean(scores)
            elif aggregation == "top3_mean":
                top_scores = sorted(scores, reverse=True)[:3]
                agg_score = np.mean(top_scores)
            else:
                raise ValueError(
                    f"Unknown aggregation method: {aggregation}. "
                    f"Use 'max', 'mean', or 'top3_mean'"
                )

            doc_scores.append((doc_id, float(agg_score), chunks_list))

        # Sort by aggregated score descending
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top_k if specified
        if top_k is not None:
            doc_scores = doc_scores[:top_k]

        logger.info(
            f"Document-level reranking complete ({aggregation}). "
            f"Top doc: {doc_scores[0][0]} (score={doc_scores[0][1]:.4f}), "
            f"Documents returned: {len(doc_scores)}"
        )

        return doc_scores

    def rerank_pages(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        aggregation: str = "max",
    ) -> List[Tuple[str, str, float, List[Dict[str, Any]]]]:
        """
        Rerank at page level by aggregating chunk scores per page.

        Args:
            query: User query
            chunks: List of chunk dicts with 'doc_id', 'page_num', and 'text' fields
            top_k: Return only top K pages (None = return all)
            aggregation: Score aggregation method ('max', 'mean', 'top3_mean')

        Returns:
            List of (doc_id, page_key, aggregated_score, chunks) tuples sorted by score (descending)
        """
        self._ensure_model()

        if not chunks:
            return []

        # First, get reranking scores for all chunks
        chunk_scores = self.rerank_chunks(query, chunks, top_k=None)

        # Group by (doc_id, page_num)
        page_chunks: Dict[
            Tuple[str, str], List[Tuple[Dict[str, Any], float]]
        ] = defaultdict(list)

        for chunk, score in chunk_scores:
            doc_id = chunk.get("doc_id", "unknown")
            page_num = chunk.get("page_num", "unknown")
            page_key = (doc_id, str(page_num))
            page_chunks[page_key].append((chunk, score))

        # Aggregate scores per page
        page_scores: List[Tuple[str, str, float, List[Dict[str, Any]]]] = []

        for (doc_id, page_num), chunk_score_list in page_chunks.items():
            scores = [score for _, score in chunk_score_list]
            chunks_list = [chunk for chunk, _ in chunk_score_list]

            if aggregation == "max":
                agg_score = max(scores)
            elif aggregation == "mean":
                agg_score = np.mean(scores)
            elif aggregation == "top3_mean":
                top_scores = sorted(scores, reverse=True)[:3]
                agg_score = np.mean(top_scores)
            else:
                raise ValueError(
                    f"Unknown aggregation method: {aggregation}. "
                    f"Use 'max', 'mean', or 'top3_mean'"
                )

            page_scores.append((doc_id, page_num, float(agg_score), chunks_list))

        # Sort by aggregated score descending
        page_scores.sort(key=lambda x: x[2], reverse=True)

        # Return top_k if specified
        if top_k is not None:
            page_scores = page_scores[:top_k]

        logger.info(
            f"Page-level reranking complete ({aggregation}). "
            f"Top page: {page_scores[0][0]} p.{page_scores[0][1]} "
            f"(score={page_scores[0][2]:.4f}), Pages returned: {len(page_scores)}"
        )

        return page_scores


# Singleton instance
_reranker_service: Optional[RerankerService] = None


def get_reranker_service(model_name: Optional[str] = None) -> RerankerService:
    """
    Get or create singleton reranker service instance.

    Args:
        model_name: Optional model name (only used on first call)

    Returns:
        RerankerService instance
    """
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService(model_name=model_name)
    return _reranker_service
