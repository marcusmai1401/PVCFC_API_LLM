"""
Reranker Module for RAG Pipeline
Implements cross-encoder reranking for better relevance scoring
Sprint 1.3: Advanced Reranking
"""
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

# For cross-encoder models
try:
    from sentence_transformers import CrossEncoder

    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    logger.warning(
        "CrossEncoder not available. Install sentence-transformers[cross-encoder]"
    )

from app.rag.retriever import RetrievalResult
from app.services.llm_client import get_llm_client


@dataclass
class RerankConfig:
    """Configuration for reranking"""

    method: str = "cross_encoder"  # Options: cross_encoder, llm, hybrid
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Fast and accurate
    top_k: int = 10  # Final number of results
    batch_size: int = 32  # For cross-encoder
    use_llm_rerank: bool = False  # Use LLM for final reranking
    llm_rerank_top_k: int = 5  # Number of docs for LLM reranking
    score_threshold: float = 0.0  # Minimum score threshold
    boost_recent: bool = True  # Boost recent documents
    boost_factor: float = 1.2  # Factor for boosting


class Reranker:
    """
    Reranker for improving retrieval results
    Supports multiple reranking strategies
    """

    def __init__(self, config: Optional[RerankConfig] = None):
        """
        Initialize reranker

        Args:
            config: Reranking configuration
        """
        self.config = config or RerankConfig()
        self.cross_encoder = None
        self.llm_client = None

        # Initialize based on method
        if self.config.method in ["cross_encoder", "hybrid"]:
            self._init_cross_encoder()

        if self.config.use_llm_rerank:
            self._init_llm_client()

        logger.info(f"Reranker initialized with method: {self.config.method}")

    def _init_cross_encoder(self):
        """Initialize cross-encoder model"""
        if not CROSS_ENCODER_AVAILABLE:
            logger.warning(
                "CrossEncoder not available, falling back to score-based reranking"
            )
            return

        try:
            self.cross_encoder = CrossEncoder(
                self.config.model_name,
                max_length=512,
                device="cpu",  # Use 'cuda' if GPU available
            )
            logger.info(f"Loaded cross-encoder: {self.config.model_name}")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}")

    def _init_llm_client(self):
        """Initialize LLM client for reranking"""
        try:
            self.llm_client = get_llm_client(tier="standard")
            logger.info("LLM client initialized for reranking")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM client: {e}")

    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """
        Rerank retrieval results

        Args:
            query: Original query
            results: Initial retrieval results
            metadata: Additional metadata for reranking

        Returns:
            Reranked results
        """
        if not results:
            return results

        start_time = time.time()

        # Apply reranking based on method
        if self.config.method == "cross_encoder":
            reranked = self._cross_encoder_rerank(query, results)
        elif self.config.method == "llm":
            reranked = self._llm_rerank(query, results)
        elif self.config.method == "hybrid":
            reranked = self._hybrid_rerank(query, results)
        else:
            # Default: simple score-based reranking
            reranked = self._score_based_rerank(query, results)

        # Apply score threshold (but ensure minimum results)
        MIN_RESULTS = 3  # Always keep at least 3 results for downstream processing
        filtered = [r for r in reranked if r.score >= self.config.score_threshold]

        # Safety: If threshold filtering removed too many results, keep top MIN_RESULTS
        if len(filtered) < MIN_RESULTS and len(reranked) >= MIN_RESULTS:
            logger.warning(
                f"Score threshold {self.config.score_threshold} filtered to {len(filtered)} results. "
                f"Keeping top {MIN_RESULTS} regardless of threshold."
            )
            filtered = reranked[:MIN_RESULTS]
        elif len(filtered) == 0 and len(reranked) > 0:
            # Extreme case: all filtered out, keep at least 1
            logger.warning(
                f"All results filtered by threshold. Keeping top result with score {reranked[0].score:.4f}"
            )
            filtered = reranked[:1]

        reranked = filtered

        # Apply top-k
        reranked = reranked[: self.config.top_k]

        elapsed = (time.time() - start_time) * 1000
        logger.info(
            f"Reranked {len(results)} -> {len(reranked)} results in {elapsed:.2f}ms"
        )

        return reranked

    def _cross_encoder_rerank(
        self, query: str, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Rerank using cross-encoder

        Args:
            query: Query text
            results: Results to rerank

        Returns:
            Reranked results
        """
        if not self.cross_encoder:
            logger.warning("Cross-encoder not available, using fallback")
            return self._score_based_rerank(query, results)

        try:
            # Prepare query-document pairs
            pairs = [[query, result.text] for result in results]

            # Get cross-encoder scores in batches
            scores = []
            for i in range(0, len(pairs), self.config.batch_size):
                batch = pairs[i : i + self.config.batch_size]
                batch_scores = self.cross_encoder.predict(batch)
                scores.extend(batch_scores)

            # Update scores and sort
            for result, score in zip(results, scores):
                # Combine with original score (weighted average)
                result.score = 0.7 * float(score) + 0.3 * result.score

            # Sort by new scores
            results.sort(key=lambda x: x.score, reverse=True)

            return results

        except Exception as e:
            logger.error(f"Cross-encoder reranking failed: {e}")
            return self._score_based_rerank(query, results)

    def _llm_rerank(
        self, query: str, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Rerank using LLM for relevance scoring

        Args:
            query: Query text
            results: Results to rerank

        Returns:
            Reranked results
        """
        if not self.llm_client:
            logger.warning("LLM client not available, using fallback")
            return self._score_based_rerank(query, results)

        try:
            # Take top candidates for LLM reranking (expensive)
            candidates = results[: self.config.llm_rerank_top_k]

            # Build prompt for batch relevance scoring
            prompt = self._build_llm_rerank_prompt(query, candidates)

            # Get LLM scores
            response = self.llm_client.generate(
                prompt=prompt, temperature=0.0, max_tokens=100  # Deterministic
            )

            # Parse scores from response
            llm_scores = self._parse_llm_scores(response.content, len(candidates))

            # Update scores for candidates
            for i, score in enumerate(llm_scores):
                if i < len(candidates):
                    candidates[i].score = score

            # Sort candidates by LLM scores
            candidates.sort(key=lambda x: x.score, reverse=True)

            # Combine with remaining results
            remaining = results[self.config.llm_rerank_top_k :]
            return candidates + remaining[: self.config.top_k - len(candidates)]

        except Exception as e:
            logger.error(f"LLM reranking failed: {e}")
            return self._score_based_rerank(query, results)

    def _hybrid_rerank(
        self, query: str, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Hybrid reranking: Cross-encoder + LLM for top results

        Args:
            query: Query text
            results: Results to rerank

        Returns:
            Reranked results
        """
        # First pass: Cross-encoder reranking
        results = self._cross_encoder_rerank(query, results)

        # Second pass: LLM reranking for top results
        if self.config.use_llm_rerank and len(results) > 0:
            top_k = min(self.config.llm_rerank_top_k, len(results))
            top_results = results[:top_k]
            top_reranked = self._llm_rerank(query, top_results)

            # Combine reranked top with remaining
            results = top_reranked + results[top_k:]

        return results

    def _score_based_rerank(
        self, query: str, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Simple score-based reranking with query term matching

        Args:
            query: Query text
            results: Results to rerank

        Returns:
            Reranked results
        """
        query_terms = set(query.lower().split())

        for result in results:
            # Count query term matches
            text_lower = result.text.lower()
            term_matches = sum(1 for term in query_terms if term in text_lower)

            # Boost score based on term matches
            match_boost = 1.0 + (term_matches * 0.1)

            # Apply metadata boosts
            if self.config.boost_recent and result.metadata:
                # Example: boost recent documents
                if "date" in result.metadata:
                    # Implementation depends on date format
                    pass

            # Update score
            result.score *= match_boost

        # Sort by updated scores
        results.sort(key=lambda x: x.score, reverse=True)

        return results

    def _build_llm_rerank_prompt(
        self, query: str, results: List[RetrievalResult]
    ) -> str:
        """Build prompt for LLM reranking"""
        prompt = f"""Score the relevance of each document to the query on a scale of 0-10.
Query: {query}

Documents:
"""
        for i, result in enumerate(results, 1):
            text_preview = (
                result.text[:200] + "..." if len(result.text) > 200 else result.text
            )
            prompt += f"\n{i}. {text_preview}\n"

        prompt += """
Provide scores in format: 1:score, 2:score, 3:score, ...
Scores:"""

        return prompt

    def _parse_llm_scores(self, response: str, num_results: int) -> List[float]:
        """Parse relevance scores from LLM response"""
        scores = []

        try:
            # Parse format: "1:8.5, 2:7.0, 3:9.0"
            parts = response.strip().split(",")
            for part in parts:
                if ":" in part:
                    _, score_str = part.split(":")
                    score = float(score_str.strip())
                    scores.append(score / 10.0)  # Normalize to 0-1
        except Exception as e:
            logger.warning(f"Failed to parse LLM scores: {e}")
            # Return default scores
            scores = [0.5] * num_results

        # Pad with zeros if needed
        while len(scores) < num_results:
            scores.append(0.0)

        return scores[:num_results]

    def explain_reranking(
        self, query: str, results: List[RetrievalResult]
    ) -> Dict[str, Any]:
        """
        Explain reranking decisions

        Args:
            query: Query text
            results: Reranked results

        Returns:
            Explanation dictionary
        """
        explanation = {
            "method": self.config.method,
            "model": self.config.model_name
            if self.config.method == "cross_encoder"
            else None,
            "top_k": self.config.top_k,
            "num_results": len(results),
            "score_distribution": {
                "min": min(r.score for r in results) if results else 0,
                "max": max(r.score for r in results) if results else 0,
                "mean": np.mean([r.score for r in results]) if results else 0,
                "std": np.std([r.score for r in results]) if results else 0,
            },
            "factors": [],
        }

        # Add applied factors
        if self.config.boost_recent:
            explanation["factors"].append("Recent document boost")
        if self.config.use_llm_rerank:
            explanation["factors"].append("LLM relevance scoring")
        if self.cross_encoder:
            explanation["factors"].append("Cross-encoder similarity")

        return explanation


def create_reranker(method: str = "cross_encoder", **kwargs) -> Reranker:
    """
    Factory function to create reranker

    Args:
        method: Reranking method
        **kwargs: Additional config parameters

    Returns:
        Configured Reranker instance
    """
    config = RerankConfig(method=method, **kwargs)
    return Reranker(config)


# Convenience functions
def rerank_results(
    query: str,
    results: List[RetrievalResult],
    method: str = "cross_encoder",
    top_k: int = 10,
) -> List[RetrievalResult]:
    """
    Quick reranking function

    Args:
        query: Query text
        results: Results to rerank
        method: Reranking method
        top_k: Number of results to return

    Returns:
        Reranked results
    """
    reranker = create_reranker(method=method, top_k=top_k)
    return reranker.rerank(query, results)
