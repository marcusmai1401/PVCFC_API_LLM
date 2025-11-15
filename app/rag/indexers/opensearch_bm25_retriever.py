"""
OpenSearch BM25 Retriever
Production-ready BM25 search using OpenSearch instead of offline rank-bm25

This retriever is compatible with the BM25Indexer interface and can be used
as a drop-in replacement in HybridRetriever.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from opensearchpy import OpenSearch
from pybreaker import CircuitBreakerError

from app.core.circuit_breaker import get_opensearch_breaker
from app.core.config import settings


class OpenSearchBM25Retriever:
    """
    BM25 retriever using OpenSearch backend

    Compatible with BM25Indexer interface for seamless integration.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        index_name: str = "rag_chunks",
        k1: float = 1.2,
        b: float = 0.75,
        timeout: int = 30,
    ):
        """
        Initialize OpenSearch BM25 retriever

        Args:
            host: OpenSearch server host
            port: OpenSearch server port
            index_name: Index name to search
            k1: BM25 k1 parameter (term frequency saturation)
            b: BM25 b parameter (length normalization)
            timeout: Query timeout in seconds
        """
        self.host = host
        self.port = port
        self.index_name = index_name
        self.k1 = k1
        self.b = b
        self.timeout = timeout

        # OpenSearch client (lazy initialization)
        self._client: Optional[OpenSearch] = None

        # Cache for statistics (lazy loaded)
        self._num_documents: Optional[int] = None

        logger.info(
            f"Initialized OpenSearchBM25Retriever: "
            f"host={host}, port={port}, index={index_name}, "
            f"k1={k1}, b={b}"
        )

    @property
    def client(self) -> OpenSearch:
        """Get or create OpenSearch client (lazy initialization)"""
        if self._client is None:
            try:
                self._client = OpenSearch(
                    hosts=[{"host": self.host, "port": self.port}],
                    http_compress=True,
                    use_ssl=False,
                    verify_certs=False,
                    timeout=self.timeout,
                )
                # Test connection
                info = self._client.info()
                logger.info(f"Connected to OpenSearch: {info['version']['number']}")
            except Exception as e:
                logger.error(
                    f"Failed to connect to OpenSearch at {self.host}:{self.port}"
                )
                logger.error(f"Error: {e}")
                raise ConnectionError(
                    f"Cannot connect to OpenSearch at {self.host}:{self.port}. "
                    f"Make sure OpenSearch is running."
                ) from e
        return self._client

    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search documents using BM25 with circuit breaker protection.

        Circuit breaker prevents cascading failures when OpenSearch is slow/down.
        If breaker is OPEN, returns empty list for graceful degradation.

        Args:
            query: Search query
            top_k: Number of results to return
            min_score: Minimum score threshold

        Returns:
            List of search results with scores (empty if circuit breaker is open)
        """
        circuit_breaker_enabled = getattr(settings, "circuit_breaker_enabled", True)

        if not circuit_breaker_enabled:
            return self._execute_search(query, top_k, min_score)

        try:
            breaker = get_opensearch_breaker()
            return breaker.call(
                self._execute_search, query=query, top_k=top_k, min_score=min_score
            )
        except CircuitBreakerError:
            logger.warning(
                "OpenSearch circuit breaker OPEN - returning empty results. "
                "System will use fallback retrieval if available."
            )
            return []  # Graceful degradation
        except Exception as e:
            logger.error(f"OpenSearch search failed: {e}")
            raise

    def _execute_search(
        self, query: str, top_k: int = 5, min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Execute OpenSearch query (internal method called by circuit breaker)"""
        try:
            # Build OpenSearch query with tag entity boosting
            # Strategy: Boost is_tag_entity=True docs by 10x
            body = {
                "size": top_k,
                "query": {
                    "bool": {
                        "should": [
                            # Normal multi_match query (boost 1.0)
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": [
                                        "text^3",  # Main content, highest boost
                                        "heading^2",  # Section headings, medium boost
                                        "title",  # Document title, default boost
                                    ],
                                    "type": "best_fields",
                                    "operator": "or",
                                    "boost": 1.0,
                                }
                            },
                            # Tag entities: multi_match + is_tag_entity=True (boost 10x)
                            {
                                "bool": {
                                    "must": [
                                        {
                                            "multi_match": {
                                                "query": query,
                                                "fields": [
                                                    "text^3",
                                                    "heading^2",
                                                    "title",
                                                ],
                                                "type": "best_fields",
                                                "operator": "or",
                                            }
                                        },
                                        {"term": {"is_tag_entity": True}},
                                    ],
                                    "boost": 10.0,  # 10x boost for tag entities!
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "_source": [
                    "chunk_id",
                    "doc_id",
                    "text",
                    "page",
                    "page_start",
                    "page_end",
                    "heading",
                    "title",
                    "level",
                    "doc_type",
                    "tags",  # Include tags field
                    "is_tag_entity",  # Include is_tag_entity flag
                ],
            }

            # Execute search
            response = self.client.search(index=self.index_name, body=body)
            hits = response["hits"]["hits"]

            # Convert to compatible format
            results = []
            for idx, hit in enumerate(hits):
                score = hit.get("_score", 0.0)

                # Apply min_score filter
                if score < min_score:
                    continue

                src = hit.get("_source", {})

                # Extract metadata in compatible format
                metadata = {
                    "chunk_id": src.get("chunk_id"),
                    "doc_id": src.get("doc_id"),
                    "page": src.get("page"),
                    "page_start": src.get("page_start"),
                    "page_end": src.get("page_end"),
                    "heading": src.get("heading"),
                    "title": src.get("title"),
                    "level": src.get("level"),
                    "doc_type": src.get("doc_type"),
                    "tags": src.get("tags", []),  # Include tags
                    "is_tag_entity": src.get("is_tag_entity", False),  # Tag flag
                }

                result = {
                    "text": src.get("text", ""),
                    "score": float(score),
                    "metadata": metadata,
                    "rank": len(results) + 1,
                }
                results.append(result)

            logger.debug(
                f"OpenSearch BM25 search returned {len(results)} results for query: {query[:50]}..."
            )
            return results

        except Exception as e:
            logger.error(f"OpenSearch search failed: {e}")
            # Return empty results on error (graceful degradation)
            logger.warning("Returning empty results due to OpenSearch error")
            return []

    def search_with_tag_boosting(
        self, query: str, detected_tags: List[str] = None, top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Enhanced search with tag boosting for P&ID documents

        Strategy:
        - Exact match in tags.keyword field → boost 10x
        - Phrase match in text → boost 5x
        - Multi-match with fuzziness → boost 2x

        Args:
            query: Search query
            detected_tags: List of detected equipment tags
            top_k: Number of results to return

        Returns:
            List of search results with boosted scores
        """
        if not detected_tags:
            # Fallback to normal search
            logger.debug("No tags detected, using normal search")
            return self.search(query, top_k)

        logger.info(f"Tag-boosted search for tags: {detected_tags}")

        try:
            # Tag-focused query strategy with bool query
            body = {
                "size": top_k,
                "query": {
                    "bool": {
                        "should": [
                            # Exact match trong tags.keyword → boost 10x
                            {
                                "terms": {
                                    "tags.keyword": detected_tags,
                                    "boost": 10.0,
                                }
                            },
                            # Phrase match trong text → boost 5x
                            {
                                "match_phrase": {
                                    "text": {
                                        "query": " ".join(detected_tags),
                                        "boost": 5.0,
                                    }
                                }
                            },
                            # Multi-match với fuzzy → boost 2x
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["text^2", "heading^1.5", "title"],
                                    "fuzziness": "AUTO",
                                    "prefix_length": 1,
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "_source": [
                    "chunk_id",
                    "doc_id",
                    "text",
                    "page",
                    "page_start",
                    "page_end",
                    "heading",
                    "title",
                    "level",
                    "doc_type",
                    "tags",
                    "tags_raw",
                ],
            }

            # Execute search
            response = self.client.search(index=self.index_name, body=body)
            hits = response["hits"]["hits"]

            # Convert to compatible format
            results = []
            for idx, hit in enumerate(hits):
                score = hit.get("_score", 0.0)
                src = hit.get("_source", {})

                # Extract metadata
                metadata = {
                    "chunk_id": src.get("chunk_id"),
                    "doc_id": src.get("doc_id"),
                    "page": src.get("page"),
                    "page_start": src.get("page_start"),
                    "page_end": src.get("page_end"),
                    "heading": src.get("heading"),
                    "title": src.get("title"),
                    "level": src.get("level"),
                    "doc_type": src.get("doc_type"),
                    "tags": src.get("tags", []),
                    "tags_raw": src.get("tags_raw", []),
                }

                result = {
                    "text": src.get("text", ""),
                    "score": float(score),
                    "metadata": metadata,
                    "rank": len(results) + 1,
                    "source": "opensearch_tag_boosted",
                }
                results.append(result)

            logger.info(
                f"Tag-boosted search returned {len(results)} results "
                f"(tags: {detected_tags})"
            )
            return results

        except Exception as e:
            logger.error(f"Tag-boosted search failed: {e}")
            # Graceful degradation: fallback to normal search
            logger.warning("Falling back to normal search")
            return self.search(query, top_k)

    def batch_search(
        self, queries: List[str], top_k: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search multiple queries (compatible with BM25Indexer.batch_search interface)

        Args:
            queries: List of search queries
            top_k: Number of results per query

        Returns:
            Dictionary mapping queries to results
        """
        results = {}
        for query in queries:
            results[query] = self.search(query, top_k)
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get index statistics (compatible with BM25Indexer.get_statistics interface)

        Returns:
            Statistics dictionary
        """
        try:
            # Get document count
            count_result = self.client.count(index=self.index_name)
            num_docs = count_result["count"]

            # Get index stats
            stats_result = self.client.indices.stats(index=self.index_name)
            index_stats = stats_result["indices"][self.index_name]["total"]

            return {
                "num_documents": num_docs,
                "index_name": self.index_name,
                "store_size": index_stats["store"]["size_in_bytes"],
                "store_size_human": index_stats["store"].get("size", "N/A"),
                "backend": "opensearch",
                "bm25_params": {"k1": self.k1, "b": self.b},
            }
        except Exception as e:
            logger.error(f"Failed to get OpenSearch statistics: {e}")
            return {
                "num_documents": 0,
                "backend": "opensearch",
                "error": str(e),
            }

    @property
    def documents(self) -> List[str]:
        """
        Get document list (compatibility property)

        Note: OpenSearch doesn't store documents in memory like BM25Indexer.
        This returns an empty list but provides the count via get_statistics().
        """
        logger.warning(
            "OpenSearchBM25Retriever.documents is not populated (documents stored in OpenSearch). "
            "Use get_statistics() to get document count."
        )
        return []

    @property
    def metadata(self) -> List[Dict[str, Any]]:
        """
        Get metadata list (compatibility property)

        Note: OpenSearch doesn't store metadata in memory like BM25Indexer.
        This returns an empty list. Metadata is retrieved per query.
        """
        logger.warning(
            "OpenSearchBM25Retriever.metadata is not populated (metadata stored in OpenSearch). "
            "Metadata is returned with each search result."
        )
        return []

    def load_index(self, index_dir: str) -> None:
        """
        Load index from directory (compatibility method - no-op for OpenSearch)

        OpenSearch retriever connects to a running OpenSearch instance,
        so loading from disk is not applicable. This method logs a warning
        and is a no-op.

        Args:
            index_dir: Directory path (ignored)
        """
        logger.warning(
            f"OpenSearchBM25Retriever.load_index() called with {index_dir}. "
            f"This is a no-op as OpenSearch retriever connects to a running server. "
            f"Index name: {self.index_name}"
        )

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text (compatibility method - not used by OpenSearch)

        OpenSearch handles tokenization internally using its analyzers.
        This method is provided for interface compatibility only.

        Args:
            text: Input text

        Returns:
            Empty list (tokenization handled by OpenSearch)
        """
        logger.warning(
            "OpenSearchBM25Retriever._tokenize() called. "
            "OpenSearch handles tokenization internally."
        )
        return []

    def health_check(self) -> Dict[str, Any]:
        """
        Check if OpenSearch connection is healthy

        Returns:
            Dict with status and details
        """
        try:
            # Test connection
            info = self.client.info()

            # Check if index exists
            exists = self.client.indices.exists(index=self.index_name)
            if not exists:
                logger.error(f"Index '{self.index_name}' does not exist")
                return {
                    "status": "unhealthy",
                    "error": f"Index '{self.index_name}' does not exist",
                }

            # Check index health
            health = self.client.cluster.health(index=self.index_name)
            cluster_status = health["status"]

            if cluster_status == "red":
                logger.error(f"Index '{self.index_name}' health is RED")
                return {
                    "status": "unhealthy",
                    "error": f"Index '{self.index_name}' health is RED",
                    "cluster_health": cluster_status,
                }

            logger.info(
                f"OpenSearch health check OK: version={info['version']['number']}, "
                f"index={self.index_name}, status={cluster_status}"
            )
            return {
                "status": "healthy",
                "index": self.index_name,
                "cluster_health": cluster_status,
                "version": info["version"]["number"],
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}


# Factory function for easy instantiation from config
def create_opensearch_retriever(
    host: Optional[str] = None,
    port: Optional[int] = None,
    index_name: Optional[str] = None,
    **kwargs,
) -> OpenSearchBM25Retriever:
    """
    Factory function to create OpenSearchBM25Retriever from config

    Args:
        host: OpenSearch host (default from env: OPENSEARCH_HOST)
        port: OpenSearch port (default from env: OPENSEARCH_PORT)
        index_name: Index name (default from env: OPENSEARCH_INDEX)
        **kwargs: Additional arguments for OpenSearchBM25Retriever

    Returns:
        Configured OpenSearchBM25Retriever instance
    """
    # Try to load from app config
    try:
        from app.core.config import settings

        host = host or settings.opensearch_host
        port = port or settings.opensearch_port
        index_name = index_name or settings.opensearch_index
    except Exception as e:
        logger.warning(f"Could not load OpenSearch config from settings: {e}")
        # Use defaults
        host = host or "localhost"
        port = port or 9200
        index_name = index_name or "rag_chunks"

    return OpenSearchBM25Retriever(
        host=host, port=port, index_name=index_name, **kwargs
    )
