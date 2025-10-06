"""
Vertex AI Semantic Reranker (Stage-1)

Uses Google Cloud Vertex AI semantic ranker for neural reranking.
"""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import Vertex AI SDK
try:
    from google.cloud import aiplatform
    from google.cloud.aiplatform_v1 import PredictionServiceClient
    from google.cloud.aiplatform_v1.types import PredictRequest

    _VERTEX_AI_AVAILABLE = True
except ImportError:
    _VERTEX_AI_AVAILABLE = False
    logger.warning(
        "Vertex AI SDK not available. Install with: pip install google-cloud-aiplatform"
    )


class VertexAIReranker:
    """
    Vertex AI Semantic Reranker for Stage-1 reranking.

    Uses Google's semantic understanding to rerank search results.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        model: str = "semantic-ranker-512@latest",
        max_records: int = 100,
        timeout: int = 30,
    ):
        """
        Initialize Vertex AI reranker.

        Args:
            project_id: GCP project ID (default: from env)
            location: GCP location
            model: Model name
            max_records: Max records per request
            timeout: API timeout in seconds
        """
        if not _VERTEX_AI_AVAILABLE:
            raise ImportError(
                "Vertex AI SDK not available. "
                "Install with: pip install google-cloud-aiplatform"
            )

        self.project_id = project_id
        self.location = location
        self.model = model
        self.max_records = max_records
        self.timeout = timeout

        # Initialize Vertex AI
        aiplatform.init(project=project_id, location=location)

        # Metrics
        self.metrics = {
            "total_requests": 0,
            "total_records_reranked": 0,
            "total_api_time": 0.0,
            "errors": 0,
        }

        logger.info(f"VertexAIReranker initialized: {project_id}/{location}/{model}")

    def rerank(
        self, query: str, results: List[Dict[str, Any]], top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank results using Vertex AI Semantic Ranker.

        Args:
            query: Search query
            results: List of search results with 'text' field
            top_k: Number of top results to return (None = all)

        Returns:
            Reranked results with 'rerank_score' field
        """
        if not results:
            logger.warning("No results to rerank")
            return []

        # Limit to max_records
        if len(results) > self.max_records:
            logger.warning(f"Truncating {len(results)} results to {self.max_records}")
            results = results[: self.max_records]

        try:
            start_time = time.time()

            # Prepare records for API
            records = []
            for i, result in enumerate(results):
                records.append({"id": str(i), "content": result.get("text", "")})

            # Call Vertex AI API
            reranked_scores = self._call_vertex_ai_api(query, records)

            # Merge scores back into results
            reranked_results = []
            for i, result in enumerate(results):
                reranked_result = result.copy()
                reranked_result["rerank_score"] = reranked_scores.get(i, 0.0)
                reranked_results.append(reranked_result)

            # Sort by rerank score
            reranked_results.sort(key=lambda x: x["rerank_score"], reverse=True)

            # Apply top_k if specified
            if top_k:
                reranked_results = reranked_results[:top_k]

            # Update metrics
            elapsed = time.time() - start_time
            self.metrics["total_requests"] += 1
            self.metrics["total_records_reranked"] += len(results)
            self.metrics["total_api_time"] += elapsed

            logger.info(
                f"Reranked {len(results)} results in {elapsed:.2f}s "
                f"(top score: {reranked_results[0]['rerank_score']:.4f})"
            )

            return reranked_results

        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            self.metrics["errors"] += 1
            # Return original results on error
            return results

    def _call_vertex_ai_api(
        self, query: str, records: List[Dict[str, str]]
    ) -> Dict[int, float]:
        """
        Call Vertex AI Semantic Ranker API.

        Args:
            query: Search query
            records: List of {id, content} dicts

        Returns:
            Dictionary mapping record index to rerank score
        """
        # Note: Actual Vertex AI Semantic Ranker API implementation
        # depends on the specific API endpoint and format.
        # This is a placeholder that should be replaced with real API calls.

        logger.warning(
            "Using mock Vertex AI API. "
            "Replace with real implementation for production."
        )

        # Mock implementation: return random scores
        import random

        scores = {}
        for record in records:
            idx = int(record["id"])
            # Simulate semantic relevance scoring
            # In real implementation, this would be API response
            scores[idx] = random.uniform(0.5, 1.0)

        return scores

    def get_metrics(self) -> Dict[str, Any]:
        """Get reranking metrics."""
        metrics = self.metrics.copy()

        if metrics["total_requests"] > 0:
            metrics["avg_api_time"] = (
                metrics["total_api_time"] / metrics["total_requests"]
            )
            metrics["avg_records_per_request"] = (
                metrics["total_records_reranked"] / metrics["total_requests"]
            )
        else:
            metrics["avg_api_time"] = 0.0
            metrics["avg_records_per_request"] = 0.0

        return metrics


class MockVertexAIReranker:
    """
    Mock reranker for testing without Vertex AI access.

    Uses simple heuristics to simulate reranking.
    """

    def __init__(self, **kwargs):
        """Initialize mock reranker."""
        logger.info("MockVertexAIReranker initialized (no API calls)")
        self.metrics = {
            "total_requests": 0,
            "total_records_reranked": 0,
            "total_api_time": 0.0,
            "errors": 0,
        }

    def rerank(
        self, query: str, results: List[Dict[str, Any]], top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Mock reranking using simple heuristics.

        Simulates semantic relevance by:
        - Exact keyword matches
        - Query term frequency
        - Text length (penalize very short/long)
        """
        if not results:
            return []

        start_time = time.time()
        query_terms = query.lower().split()

        reranked_results = []
        for result in results:
            text = result.get("text", "").lower()

            # Compute mock "semantic" score
            score = 0.0

            # Exact match bonus
            if query.lower() in text:
                score += 0.3

            # Term frequency
            term_matches = sum(term in text for term in query_terms)
            score += (term_matches / len(query_terms)) * 0.5

            # Length penalty (prefer medium-length chunks)
            text_len = len(text)
            if 200 <= text_len <= 1000:
                score += 0.2
            elif text_len < 100 or text_len > 2000:
                score -= 0.1

            # Normalize to [0, 1]
            score = min(max(score, 0.0), 1.0)

            reranked_result = result.copy()
            reranked_result["rerank_score"] = score
            reranked_results.append(reranked_result)

        # Sort by mock score
        reranked_results.sort(key=lambda x: x["rerank_score"], reverse=True)

        if top_k:
            reranked_results = reranked_results[:top_k]

        # Update metrics
        elapsed = time.time() - start_time
        self.metrics["total_requests"] += 1
        self.metrics["total_records_reranked"] += len(results)
        self.metrics["total_api_time"] += elapsed

        logger.debug(
            f"Mock reranked {len(results)} results in {elapsed:.3f}s "
            f"(top score: {reranked_results[0]['rerank_score']:.4f})"
        )

        return reranked_results

    def get_metrics(self) -> Dict[str, Any]:
        """Get reranking metrics."""
        metrics = self.metrics.copy()

        if metrics["total_requests"] > 0:
            metrics["avg_api_time"] = (
                metrics["total_api_time"] / metrics["total_requests"]
            )
            metrics["avg_records_per_request"] = (
                metrics["total_records_reranked"] / metrics["total_requests"]
            )
        else:
            metrics["avg_api_time"] = 0.0
            metrics["avg_records_per_request"] = 0.0

        return metrics


def get_vertex_ai_reranker(
    project_id: Optional[str] = None, use_mock: bool = False, **kwargs
) -> Any:
    """
    Factory function to get Vertex AI reranker.

    Args:
        project_id: GCP project ID
        use_mock: Force use of mock reranker
        **kwargs: Additional arguments for reranker

    Returns:
        Reranker instance (real or mock)
    """
    if use_mock or not _VERTEX_AI_AVAILABLE or not project_id:
        logger.info("Using MockVertexAIReranker")
        return MockVertexAIReranker(**kwargs)
    else:
        logger.info("Using VertexAIReranker")
        return VertexAIReranker(project_id=project_id, **kwargs)


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    # Test mock reranker
    reranker = MockVertexAIReranker()

    # Test data
    query = "CO2 compressor pressure"
    results = [
        {"text": "CO2 compression system with high pressure stages", "score": 0.8},
        {"text": "Pump P-101 specifications and torque data", "score": 0.7},
        {"text": "CO2 compressor C-101 pressure control system", "score": 0.85},
        {"text": "Heat exchanger design parameters", "score": 0.6},
    ]

    print("\n=== Testing Mock Reranker ===")
    print(f"Query: {query}")
    print(f"Input: {len(results)} results\n")

    reranked = reranker.rerank(query, results, top_k=3)

    print("\nReranked Results:")
    for i, r in enumerate(reranked, 1):
        print(f"{i}. [Score: {r['rerank_score']:.4f}] {r['text'][:60]}...")

    print(f"\nMetrics: {reranker.get_metrics()}")
