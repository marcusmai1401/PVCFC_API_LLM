"""
Hybrid Weaviate + OpenSearch Retriever (Modern Architecture)

Combines:
- Weaviate (semantic/vector search)
- OpenSearch BM25 (keyword search)
- RRF (Reciprocal Rank Fusion)
- BGE CrossEncoder Reranking (optional)

This is the production retriever replacing legacy FAISS + BM25 offline.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.rag.indexers.opensearch_bm25_retriever import create_opensearch_retriever
from app.rag.query_transform import TransformedQuery
from app.rag.retriever import RetrievalResult
from app.rag.weaviate_retriever import WeaviateRetriever, WeaviateSearchConfig
from app.services.reranker import get_reranker_service


@dataclass
class HybridModernConfig:
    """Configuration for modern hybrid retrieval"""

    # Retrieval limits
    weaviate_limit: int = 50  # Candidates from Weaviate
    opensearch_limit: int = 50  # Candidates from OpenSearch

    # Fusion
    rrf_k: int = 60  # RRF constant
    top_rrf: int = 60  # Results after RRF

    # Reranking
    enable_bge_rerank: bool = True  # Use BGE reranking
    bge_top_k: int = 10  # Final results after BGE
    bge_level: str = "chunk"  # chunk, doc, or page
    bge_aggregation: str = "max"  # max, mean, or top3_mean


class HybridWeaviateOpenSearchRetriever:
    """
    Modern hybrid retriever combining Weaviate + OpenSearch BM25

    Production architecture:
    1. Query → Weaviate (semantic) + OpenSearch (keyword) in parallel
    2. RRF fusion to combine results
    3. (Optional) BGE reranking for final ordering
    4. Return top-k results

    Replaces: HybridRetriever (FAISS + BM25 offline)
    """

    def __init__(self, config: Optional[HybridModernConfig] = None):
        """
        Initialize hybrid modern retriever

        Args:
            config: Hybrid configuration (uses defaults if None)
        """
        self.config = config or HybridModernConfig()

        # Initialize retrievers
        logger.info("Initializing Hybrid Modern Retriever (Weaviate + OpenSearch)")

        # Weaviate retriever
        weaviate_config = WeaviateSearchConfig(
            retrieval_limit=self.config.weaviate_limit,
            enable_bge_rerank=False,  # We'll do BGE at hybrid level
        )
        self.weaviate_retriever = WeaviateRetriever(config=weaviate_config)

        # OpenSearch BM25 retriever
        self.opensearch_retriever = create_opensearch_retriever(
            host=settings.opensearch_host,
            port=settings.opensearch_port,
            index_name=settings.opensearch_index,
            k1=settings.opensearch_bm25_k1,
            b=settings.opensearch_bm25_b,
            timeout=settings.opensearch_timeout,
        )

        logger.info(
            f"Hybrid Modern Retriever initialized: "
            f"Weaviate({self.config.weaviate_limit}) + "
            f"OpenSearch({self.config.opensearch_limit}) → "
            f"RRF(k={self.config.rrf_k}) → "
            f"BGE({self.config.enable_bge_rerank})"
        )

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of both Weaviate and OpenSearch

        Returns:
            Combined health status
        """
        health = {
            "retriever_type": "hybrid_modern",
            "components": {},
            "overall_status": "healthy",
        }

        # Check Weaviate
        try:
            weaviate_health = self.weaviate_retriever.health_check()
            health["components"]["weaviate"] = weaviate_health

            if weaviate_health.get("status") != "healthy":
                health["overall_status"] = "degraded"
                logger.warning(f"Weaviate unhealthy: {weaviate_health}")
        except Exception as e:
            health["components"]["weaviate"] = {"status": "error", "error": str(e)}
            health["overall_status"] = "degraded"
            logger.error(f"Weaviate health check failed: {e}")

        # Check OpenSearch
        try:
            opensearch_healthy = self.opensearch_retriever.health_check()
            health["components"]["opensearch"] = {
                "status": "healthy" if opensearch_healthy else "unhealthy"
            }

            if not opensearch_healthy:
                health["overall_status"] = "degraded"
                logger.warning("OpenSearch unhealthy")
        except Exception as e:
            health["components"]["opensearch"] = {"status": "error", "error": str(e)}
            health["overall_status"] = "degraded"
            logger.error(f"OpenSearch health check failed: {e}")

        # Both failed = critical
        weaviate_ok = (
            health["components"].get("weaviate", {}).get("status") == "healthy"
        )
        opensearch_ok = (
            health["components"].get("opensearch", {}).get("status") == "healthy"
        )

        if not weaviate_ok and not opensearch_ok:
            health["overall_status"] = "critical"
            logger.error("Both Weaviate and OpenSearch are unhealthy!")

        return health

    def search(
        self,
        transformed_query: TransformedQuery,
        config_override: Optional[HybridModernConfig] = None,
    ) -> List[RetrievalResult]:
        """
        Hybrid search with Weaviate + OpenSearch

        Args:
            transformed_query: Transformed query with filters
            config_override: Optional config override

        Returns:
            List of retrieval results (fused and optionally reranked)
        """
        config = config_override or self.config

        logger.info(f"Hybrid Modern search: '{transformed_query.normalized[:100]}...'")

        all_results = []

        # 1. Weaviate search (semantic)
        try:
            logger.debug("Searching Weaviate...")
            weaviate_results = self.weaviate_retriever.search(transformed_query)
            logger.info(f"Weaviate returned {len(weaviate_results)} results")
            all_results.extend(weaviate_results)
        except Exception as e:
            logger.error(f"Weaviate search failed: {e}")
            # Continue with OpenSearch only

        # 2. OpenSearch BM25 search (keyword)
        try:
            logger.debug("Searching OpenSearch BM25...")
            # Convert transformed query to plain string for BM25
            opensearch_results = self._search_opensearch(
                query=transformed_query.normalized,
                top_k=config.opensearch_limit,
            )
            logger.info(f"OpenSearch returned {len(opensearch_results)} results")
            all_results.extend(opensearch_results)
        except Exception as e:
            logger.error(f"OpenSearch search failed: {e}")
            # Continue with Weaviate only

        # Check if we have any results
        if not all_results:
            logger.warning("No results from either Weaviate or OpenSearch!")
            return []

        # 3. RRF Fusion
        logger.debug("Applying RRF fusion...")
        fused_results = self._reciprocal_rank_fusion(
            all_results, k=config.rrf_k, top_n=config.top_rrf
        )
        logger.info(f"RRF fusion produced {len(fused_results)} results")

        # 4. BGE Reranking (optional)
        if config.enable_bge_rerank and settings.enable_bge_rerank:
            try:
                logger.debug("Applying BGE reranking...")
                fused_results = self._apply_bge_reranking(
                    query=transformed_query.normalized,
                    results=fused_results,
                    level=config.bge_level,
                    aggregation=config.bge_aggregation,
                    top_k=config.bge_top_k,
                )
                logger.info(f"BGE reranking complete: {len(fused_results)} results")
            except Exception as e:
                logger.error(f"BGE reranking failed: {e}, using RRF results")
                # Graceful degradation: use RRF results
                fused_results = fused_results[: config.bge_top_k]
        else:
            # No BGE, just limit to top_k
            fused_results = fused_results[: config.bge_top_k]

        logger.info(f"Final result count: {len(fused_results)}")
        return fused_results

    def _search_opensearch(self, query: str, top_k: int) -> List[RetrievalResult]:
        """
        Search OpenSearch and convert to RetrievalResult format

        Args:
            query: Query string
            top_k: Number of results

        Returns:
            List of RetrievalResult objects
        """
        # OpenSearch returns compatible format already
        opensearch_hits = self.opensearch_retriever.search(query, top_k=top_k)

        # Convert to RetrievalResult format
        results = []
        for hit in opensearch_hits:
            # OpenSearch returns dict with text, score, metadata, rank
            metadata = hit.get("metadata", {})

            result = RetrievalResult(
                chunk_id=metadata.get("chunk_id", hit.get("chunk_id", "unknown")),
                text=hit["text"],
                score=hit["score"],
                source="opensearch_bm25",
                metadata=metadata,
                doc_id=metadata.get("doc_id"),
                page=metadata.get("page"),
                bbox=None,
                parent_id=None,
            )
            results.append(result)

        return results

    def _reciprocal_rank_fusion(
        self, results: List[RetrievalResult], k: int = 60, top_n: int = 60
    ) -> List[RetrievalResult]:
        """
        Apply Reciprocal Rank Fusion to merge results from different sources

        RRF formula: RRF(d) = Σ 1/(k + rank(d))

        Args:
            results: All results from different sources
            k: RRF constant (typically 60)
            top_n: Number of results to return

        Returns:
            Fused and reranked results
        """
        # Group results by source
        source_rankings = defaultdict(list)
        for result in results:
            source_rankings[result.source].append(result)

        # Calculate RRF scores
        rrf_scores = defaultdict(float)
        result_map = {}

        for source, source_results in source_rankings.items():
            # Sort by original score
            source_results.sort(key=lambda x: x.score, reverse=True)

            # Calculate RRF contribution
            for rank, result in enumerate(source_results, 1):
                # Use chunk_id as key for deduplication
                key = result.chunk_id or result.text[:200]
                rrf_scores[key] += 1 / (k + rank)

                # Keep the result with higher original score
                if key not in result_map or result.score > result_map[key].score:
                    result_map[key] = result

        # Sort by RRF score
        sorted_keys = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Return top N results with updated scores
        fused_results = []
        for key, rrf_score in sorted_keys[:top_n]:
            result = result_map[key]
            # Update score to RRF score
            result.score = rrf_score
            # Mark as RRF fused
            result.source = f"{result.source}_rrf"
            fused_results.append(result)

        return fused_results

    def _apply_bge_reranking(
        self,
        query: str,
        results: List[RetrievalResult],
        level: str = "chunk",
        aggregation: str = "max",
        top_k: int = 10,
    ) -> List[RetrievalResult]:
        """
        Apply BGE reranking to results

        Args:
            query: Query string
            results: Results to rerank
            level: Reranking level (chunk, doc, page)
            aggregation: Aggregation method (max, mean, top3_mean)
            top_k: Final number of results

        Returns:
            Reranked results
        """
        if not results:
            return []

        # Get reranker service
        reranker = get_reranker_service()

        # Convert results to format expected by reranker
        chunks = [
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "metadata": r.metadata or {},
                "doc_id": r.doc_id,
                "source": r.source,
                "original_score": r.score,
            }
            for r in results
        ]

        if level == "chunk":
            # Chunk-level reranking
            reranked_chunks = reranker.rerank_chunks(query, chunks, top_k=top_k)

            # Convert back to RetrievalResult
            return [
                RetrievalResult(
                    chunk_id=chunk["chunk_id"],
                    text=chunk["text"],
                    score=float(score),
                    source=f"hybrid_modern_bge_{chunk['source']}",
                    metadata={
                        **chunk["metadata"],
                        "bge_rerank_score": float(score),
                        "original_rrf_score": chunk["original_score"],
                    },
                    doc_id=chunk["doc_id"],
                    page=results[i].page if i < len(results) else None,
                    bbox=results[i].bbox if i < len(results) else None,
                    parent_id=results[i].parent_id if i < len(results) else None,
                )
                for i, (chunk, score) in enumerate(reranked_chunks)
            ]
        else:
            # For doc/page level, use chunk-level as fallback for now
            logger.warning(
                f"BGE reranking level '{level}' not fully implemented, using chunk-level"
            )
            return self._apply_bge_reranking(
                query, results, level="chunk", aggregation=aggregation, top_k=top_k
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics from both Weaviate and OpenSearch

        Returns:
            Combined statistics
        """
        stats = {
            "retriever_type": "hybrid_modern",
            "weaviate": {},
            "opensearch": {},
            "config": {
                "weaviate_limit": self.config.weaviate_limit,
                "opensearch_limit": self.config.opensearch_limit,
                "rrf_k": self.config.rrf_k,
                "top_rrf": self.config.top_rrf,
                "enable_bge_rerank": self.config.enable_bge_rerank,
                "bge_top_k": self.config.bge_top_k,
            },
        }

        # Weaviate stats
        try:
            weaviate_health = self.weaviate_retriever.health_check()
            stats["weaviate"] = {
                "status": weaviate_health.get("status"),
                "collection": weaviate_health.get("collection"),
                "ready": weaviate_health.get("ready", False),
            }
        except Exception as e:
            stats["weaviate"] = {"error": str(e)}

        # OpenSearch stats
        try:
            opensearch_stats = self.opensearch_retriever.get_statistics()
            stats["opensearch"] = opensearch_stats
        except Exception as e:
            stats["opensearch"] = {"error": str(e)}

        return stats

    def close(self):
        """Close connections to Weaviate and OpenSearch"""
        try:
            if hasattr(self.weaviate_retriever, "close"):
                self.weaviate_retriever.close()
        except Exception as e:
            logger.error(f"Error closing Weaviate: {e}")

        # OpenSearch client doesn't need explicit close

        logger.info("Hybrid Modern Retriever connections closed")

    def __del__(self):
        """Cleanup on deletion"""
        self.close()


def create_hybrid_modern_retriever(
    config: Optional[HybridModernConfig] = None,
) -> HybridWeaviateOpenSearchRetriever:
    """
    Factory function to create hybrid modern retriever

    Args:
        config: Optional configuration

    Returns:
        Initialized HybridWeaviateOpenSearchRetriever
    """
    return HybridWeaviateOpenSearchRetriever(config=config)
