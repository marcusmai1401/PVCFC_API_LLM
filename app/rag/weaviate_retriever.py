"""
Weaviate Retriever Module for RAG Pipeline (Phase 4)
Uses Weaviate vector database for semantic search with BGE reranking
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import weaviate
from loguru import logger
from weaviate.classes.query import Filter, MetadataQuery

from app.core.config import settings
from app.rag.query_transform import TransformedQuery
from app.rag.retriever import RetrievalResult
from app.services.embedding_enhanced import EmbeddingService
from app.services.reranker import get_reranker_service


@dataclass
class WeaviateSearchConfig:
    """Configuration for Weaviate search"""

    retrieval_limit: int = 50  # Number of results from Weaviate before reranking
    top_k_final: int = 10  # Final number of results after BGE reranking
    enable_bge_rerank: bool = True  # Enable BGE reranking
    bge_rerank_level: str = "chunk"  # chunk, doc, or page
    bge_aggregation: str = "max"  # max, mean, or top3_mean
    alpha: float = 0.7  # Hybrid search alpha (0=keyword, 1=semantic)


class WeaviateRetriever:
    """
    Weaviate-based retriever for semantic search with BGE reranking

    Features:
    - Semantic search using Weaviate's near_vector
    - Metadata filtering support
    - BGE CrossEncoder reranking at multiple levels (chunk, doc, page)
    - Graceful degradation on errors
    """

    def __init__(
        self,
        collection_name: Optional[str] = None,
        config: Optional[WeaviateSearchConfig] = None,
    ):
        """
        Initialize WeaviateRetriever

        Args:
            collection_name: Weaviate collection name (default from settings)
            config: Search configuration
        """
        self.config = config or WeaviateSearchConfig()
        self.collection_name = collection_name or settings.weaviate_collection

        # Weaviate client (lazy initialized)
        self._client: Optional[weaviate.WeaviateClient] = None
        self._collection = None

        # Embedding service for query vectorization
        self.embedding_service = EmbeddingService()

        logger.info(
            f"WeaviateRetriever initialized with collection: {self.collection_name}"
        )

    def _ensure_client(self):
        """Lazy initialize Weaviate client"""
        if self._client is None:
            try:
                logger.info(
                    f"Connecting to Weaviate at {settings.weaviate_host}:{settings.weaviate_port}"
                )

                # Build connection config
                if settings.weaviate_use_grpc and settings.weaviate_grpc_port:
                    # Use gRPC for better performance
                    self._client = weaviate.connect_to_custom(
                        http_host=settings.weaviate_host,
                        http_port=settings.weaviate_port,
                        http_secure=False,
                        grpc_host=settings.weaviate_host,
                        grpc_port=settings.weaviate_grpc_port,
                        grpc_secure=False,
                    )
                else:
                    # HTTP only
                    self._client = weaviate.connect_to_local(
                        host=settings.weaviate_host,
                        port=settings.weaviate_port,
                    )

                # Get collection reference
                self._collection = self._client.collections.get(self.collection_name)

                logger.info("Weaviate client connected successfully")

            except Exception as e:
                logger.error(f"Failed to connect to Weaviate: {e}")
                raise

    def health_check(self) -> Dict[str, Any]:
        """
        Check Weaviate connection health

        Returns:
            Health status dict with connection info
        """
        try:
            self._ensure_client()

            # Check if ready
            ready = self._client.is_ready()

            # Get collection info
            collection_config = self._collection.config.get()

            return {
                "status": "healthy" if ready else "unhealthy",
                "ready": ready,
                "collection": self.collection_name,
                "collection_exists": True,
                "vector_config": str(collection_config.vector_config),
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "collection": self.collection_name,
            }

    def search(
        self,
        transformed_query: TransformedQuery,
        config_override: Optional[WeaviateSearchConfig] = None,
    ) -> List[RetrievalResult]:
        """
        Perform semantic search with Weaviate and BGE reranking

        Args:
            transformed_query: Query after transformation (with intent, filters)
            config_override: Optional config to override defaults

        Returns:
            List of retrieval results ranked by relevance
        """
        config = config_override or self.config

        logger.info(
            f"Starting Weaviate search for: {transformed_query.normalized[:100]}..."
        )

        try:
            self._ensure_client()

            # Get query embedding
            query_vector = self._get_query_vector(transformed_query.normalized)

            # Build metadata filters if any
            where_filter = self._build_filters(transformed_query.filters)

            # Perform Weaviate search
            results = self._search_weaviate(
                query_vector=query_vector,
                where_filter=where_filter,
                limit=config.retrieval_limit,
            )

            logger.info(f"Weaviate returned {len(results)} results")

            # Convert to RetrievalResult format
            retrieval_results = self._convert_to_retrieval_results(results)

            # Apply BGE reranking if enabled
            if config.enable_bge_rerank and settings.enable_bge_rerank:
                try:
                    retrieval_results = self._apply_bge_reranking(
                        query=transformed_query.normalized,
                        results=retrieval_results,
                        level=config.bge_rerank_level,
                        aggregation=config.bge_aggregation,
                        top_k=config.top_k_final,
                    )
                    logger.info(
                        f"BGE reranking complete: {len(retrieval_results)} results"
                    )
                except Exception as e:
                    logger.error(
                        f"BGE reranking failed: {e}, continuing without reranking"
                    )
                    # Graceful degradation: limit to top_k without reranking
                    retrieval_results = retrieval_results[: config.top_k_final]
            else:
                # No reranking, just limit to top_k
                retrieval_results = retrieval_results[: config.top_k_final]

            logger.info(
                f"Weaviate search complete: {len(retrieval_results)} final results"
            )
            return retrieval_results

        except Exception as e:
            logger.error(f"Weaviate search failed: {e}")
            # Return empty results on error (graceful degradation)
            return []

    def _get_query_vector(self, query: str) -> List[float]:
        """
        Get embedding vector for query

        Args:
            query: Query text

        Returns:
            Query embedding vector
        """
        try:
            embeddings = self.embedding_service.embed_texts([query])
            # embed_texts returns numpy array, convert to list
            return (
                embeddings[0].tolist()
                if hasattr(embeddings[0], "tolist")
                else list(embeddings[0])
            )
        except Exception as e:
            logger.error(f"Failed to get query embedding: {e}")
            raise

    def _build_filters(self, filters) -> Optional[Filter]:
        """
        Build Weaviate filters from QueryFilters

        Args:
            filters: QueryFilters object with doc_categories, doc_ids, etc.

        Returns:
            Weaviate Filter object or None
        """
        if filters is None:
            return None

        filter_conditions = []

        # Filter by doc_categories
        if filters.doc_categories:
            filter_conditions.append(
                Filter.by_property("doc_category").contains_any(filters.doc_categories)
            )

        # Filter by doc_ids
        if filters.doc_ids:
            filter_conditions.append(
                Filter.by_property("doc_id").contains_any(filters.doc_ids)
            )

        # Additional metadata filters
        if filters.metadata:
            for key, value in filters.metadata.items():
                filter_conditions.append(Filter.by_property(key).equal(value))

        # Combine filters with AND
        if len(filter_conditions) == 0:
            return None
        elif len(filter_conditions) == 1:
            return filter_conditions[0]
        else:
            combined_filter = filter_conditions[0]
            for condition in filter_conditions[1:]:
                combined_filter = combined_filter & condition
            return combined_filter

    def _search_weaviate(
        self,
        query_vector: List[float],
        where_filter: Optional[Filter],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Perform Weaviate near_vector search

        KNOWN LIMITATION: Some Weaviate SDK versions may not support passing
        'where' filter to near_vector() method, causing:
        "_NearVectorQueryExecutor.near_vector() got an unexpected keyword argument 'where'"

        If this occurs in production, the hybrid retriever will degrade gracefully
        to OpenSearch-only results. To fix: upgrade weaviate-client SDK or adjust
        filter application strategy.

        Args:
            query_vector: Query embedding vector
            where_filter: Metadata filters
            limit: Number of results to retrieve

        Returns:
            List of raw Weaviate results
        """
        try:
            # Query Weaviate with near_vector
            # Build query with all parameters upfront to avoid API issues
            query_params = {
                "near_vector": query_vector,
                "limit": limit,
                "return_metadata": MetadataQuery(distance=True, certainty=True),
            }

            # Apply filters if any
            if where_filter is not None:
                query_params["where"] = where_filter

            # Execute query using the collection's query.near_vector method
            response = self._collection.query.near_vector(**query_params)

            # Convert to list of dicts
            results = []
            for obj in response.objects:
                result = {
                    "uuid": str(obj.uuid),
                    "properties": obj.properties,
                    "metadata": obj.metadata,
                }
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Weaviate query failed: {e}")
            raise

    def _convert_to_retrieval_results(
        self, weaviate_results: List[Dict[str, Any]]
    ) -> List[RetrievalResult]:
        """
        Convert Weaviate results to RetrievalResult objects

        Args:
            weaviate_results: Raw results from Weaviate

        Returns:
            List of RetrievalResult objects
        """
        retrieval_results = []

        for result in weaviate_results:
            props = result["properties"]
            metadata_obj = result.get("metadata", {})

            # Extract properties (adjust field names to match your Weaviate schema)
            chunk_id = props.get("chunk_id", result["uuid"])
            text = props.get("text", "")
            doc_id = props.get("doc_id")
            page = props.get("page")
            bbox = props.get("bbox")  # Assuming bbox is stored as list

            # Calculate score from distance (lower distance = higher score)
            # Handle both dict and MetadataReturn object
            if isinstance(metadata_obj, dict):
                distance = metadata_obj.get("distance", 0.0)
                certainty = metadata_obj.get("certainty")
            else:
                # Weaviate v4 returns a MetadataReturn object with attributes
                distance = getattr(metadata_obj, "distance", 0.0)
                certainty = getattr(metadata_obj, "certainty", None)

            score = 1.0 - distance  # Simple conversion, adjust as needed

            # Build metadata dict
            metadata = {
                "doc_id": doc_id,
                "page": page,
                "doc_category": props.get("doc_category"),
                "doc_name": props.get("doc_name"),
                "weaviate_distance": distance,
                "weaviate_certainty": certainty,
            }

            retrieval_results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    text=text,
                    score=score,
                    source="weaviate",
                    metadata=metadata,
                    doc_id=doc_id,
                    page=page,
                    bbox=bbox,
                    parent_id=None,  # Weaviate doesn't have parent concept
                )
            )

        return retrieval_results

    def _apply_bge_reranking(
        self,
        query: str,
        results: List[RetrievalResult],
        level: str,
        aggregation: str,
        top_k: int,
    ) -> List[RetrievalResult]:
        """
        Apply BGE reranking to Weaviate results

        Args:
            query: User query
            results: Weaviate retrieval results
            level: Reranking level (chunk, doc, page)
            aggregation: Score aggregation method
            top_k: Final number of results

        Returns:
            Reranked results
        """
        if not results:
            return []

        # Get reranker service
        reranker = get_reranker_service()

        # Convert RetrievalResult to dict format expected by reranker
        chunks = [
            {
                "doc_id": r.doc_id or r.chunk_id,
                "text": r.text,
                "page_num": str(r.page) if r.page is not None else "unknown",
                "metadata": r.metadata or {},
                "chunk_id": r.chunk_id,
                "source": r.source,
                "original_score": r.score,
            }
            for r in results
        ]

        logger.info(
            f"Applying BGE reranking: level={level}, top_k={top_k}, "
            f"aggregation={aggregation}, candidates={len(chunks)}"
        )

        if level == "chunk":
            # Chunk-level reranking (default)
            reranked_chunks = reranker.rerank_chunks(query, chunks, top_k=top_k)

            # Convert back to RetrievalResult
            return [
                RetrievalResult(
                    chunk_id=chunk["chunk_id"],
                    text=chunk["text"],
                    score=float(score),  # BGE rerank score
                    source="weaviate_bge_reranked",
                    metadata={
                        **chunk["metadata"],
                        "bge_rerank_score": float(score),
                        "original_weaviate_score": chunk["original_score"],
                    },
                    doc_id=chunk["doc_id"],
                    page=results[i].page if i < len(results) else None,
                    bbox=results[i].bbox if i < len(results) else None,
                    parent_id=None,
                )
                for i, (chunk, score) in enumerate(reranked_chunks)
            ]

        elif level == "doc":
            # Document-level reranking
            doc_results = reranker.rerank_documents(
                query, chunks, top_k=top_k, aggregation=aggregation
            )

            # Convert back to RetrievalResult (flatten doc chunks)
            reranked_results = []
            for doc_id, doc_score, doc_chunks in doc_results:
                for chunk in doc_chunks:
                    # Find original result for metadata
                    orig_result = next(
                        (r for r in results if r.chunk_id == chunk["chunk_id"]), None
                    )
                    reranked_results.append(
                        RetrievalResult(
                            chunk_id=chunk["chunk_id"],
                            text=chunk["text"],
                            score=float(doc_score),  # Use doc-level aggregated score
                            source="weaviate_bge_doc_reranked",
                            metadata={
                                **chunk["metadata"],
                                "bge_doc_score": float(doc_score),
                                "original_weaviate_score": chunk["original_score"],
                            },
                            doc_id=doc_id,
                            page=orig_result.page if orig_result else None,
                            bbox=orig_result.bbox if orig_result else None,
                            parent_id=None,
                        )
                    )
            return reranked_results[:top_k]  # Limit to top_k total chunks

        elif level == "page":
            # Page-level reranking
            page_results = reranker.rerank_pages(
                query, chunks, top_k=top_k, aggregation=aggregation
            )

            # Convert back to RetrievalResult (flatten page chunks)
            reranked_results = []
            for doc_id, page_num, page_score, page_chunks in page_results:
                for chunk in page_chunks:
                    # Find original result for metadata
                    orig_result = next(
                        (r for r in results if r.chunk_id == chunk["chunk_id"]), None
                    )
                    reranked_results.append(
                        RetrievalResult(
                            chunk_id=chunk["chunk_id"],
                            text=chunk["text"],
                            score=float(page_score),  # Use page-level aggregated score
                            source="weaviate_bge_page_reranked",
                            metadata={
                                **chunk["metadata"],
                                "bge_page_score": float(page_score),
                                "original_weaviate_score": chunk["original_score"],
                            },
                            doc_id=doc_id,
                            page=int(page_num) if page_num.isdigit() else None,
                            bbox=orig_result.bbox if orig_result else None,
                            parent_id=None,
                        )
                    )
            return reranked_results[:top_k]  # Limit to top_k total chunks

        else:
            logger.warning(f"Unknown rerank level: {level}, skipping reranking")
            return results[:top_k]

    def close(self):
        """Close Weaviate client connection"""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("Weaviate client closed")
            except Exception as e:
                logger.error(f"Error closing Weaviate client: {e}")

    def __del__(self):
        """Cleanup on deletion"""
        self.close()


def create_weaviate_retriever(
    collection_name: Optional[str] = None,
    config: Optional[WeaviateSearchConfig] = None,
) -> WeaviateRetriever:
    """
    Create a Weaviate retriever with default settings

    Args:
        collection_name: Weaviate collection name
        config: Optional configuration

    Returns:
        Initialized WeaviateRetriever
    """
    return WeaviateRetriever(collection_name=collection_name, config=config)
