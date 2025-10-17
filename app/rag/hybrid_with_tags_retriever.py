"""
Hybrid Retriever with PID Tags Support
Extends existing hybrid retrieval with parallel tags sidecar search

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 8
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from app.config import get_config
from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridModernConfig,
    HybridWeaviateOpenSearchRetriever,
)
from app.rag.query_transform import TransformedQuery
from app.rag.retriever import RetrievalResult


class HybridWithTagsRetriever:
    """
    Extended hybrid retriever with PID tags sidecar

    Architecture:
    1. Check if PID tags enabled + tag intent detected
    2. Branch A: Tags retriever (if applicable)
    3. Branch B: Standard hybrid (Weaviate + OpenSearch chunks)
    4. RRF fusion of all branches
    5. Rerank
    6. Attach crop to tag results
    """

    def __init__(self, config: Optional[HybridModernConfig] = None):
        """Initialize hybrid retriever with tags support"""
        self.config = get_config()
        self.hybrid_config = config or HybridModernConfig()

        # Standard hybrid retriever (chunks)
        self.hybrid_retriever = HybridWeaviateOpenSearchRetriever(self.hybrid_config)

        # PID tags components (lazy init)
        self.tags_enabled = self.config.ENABLE_PID_TAGS
        self.tags_retriever = None
        self.pid_enhancer = None

        if self.tags_enabled:
            try:
                # Lazy import to avoid circular dependencies
                from app.rag.indexers.opensearch_tags_retriever import (
                    OpenSearchTagsRetriever,
                )
                from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer

                self.tags_retriever = OpenSearchTagsRetriever()
                self.pid_enhancer = PIDQueryEnhancer()
                logger.info("✓ PID tags retrieval enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize tags components: {e}")
                logger.warning("Falling back to standard hybrid retrieval")
                self.tags_enabled = False

    def search(
        self,
        transformed_query: TransformedQuery,
        top_k: int = 10,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Search with tags sidecar support

        Args:
            transformed_query: Transformed query
            top_k: Number of final results
            **kwargs: Additional args for hybrid retriever

        Returns:
            List of RetrievalResult objects (may include tag results with crop_path)
        """
        # Check if tags retrieval should be used
        use_tags = self.tags_enabled and self._should_use_tags(transformed_query)

        if use_tags:
            logger.info("Using tags-enhanced retrieval")
            return self._search_with_tags(transformed_query, top_k, **kwargs)
        else:
            # Standard hybrid retrieval
            logger.debug("Using standard hybrid retrieval (no tags)")
            return self.hybrid_retriever.search(transformed_query, top_k, **kwargs)

    def _should_use_tags(self, transformed_query: TransformedQuery) -> bool:
        """
        Determine if tags retrieval should be used

        Args:
            transformed_query: Transformed query

        Returns:
            True if tags retrieval applicable
        """
        if not self.pid_enhancer:
            return False

        # Analyze query for tag patterns
        try:
            analysis = self.pid_enhancer.enhance(transformed_query.original)

            # Use tags if strategy is tag-focused or mixed
            if analysis.get("strategy") in ["tag_focused", "mixed"]:
                detected_tags = analysis.get("tags", [])
                if detected_tags:
                    logger.debug(f"Detected tags in query: {detected_tags}")
                    return True

        except Exception as e:
            logger.debug(f"Tag detection failed: {e}")

        return False

    def _search_with_tags(
        self,
        transformed_query: TransformedQuery,
        top_k: int,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Search with parallel tags + chunks retrieval

        Pipeline:
        1. Detect tags in query
        2. Search tags index (Branch A)
        3. Search chunks (Branch B - standard hybrid)
        4. RRF fusion of both branches
        5. Rerank
        6. Attach crop_path to tag results

        Args:
            transformed_query: Transformed query
            top_k: Final results count
            **kwargs: Additional args

        Returns:
            Fused and reranked results
        """
        # Analyze query for tags
        analysis = self.pid_enhancer.enhance(transformed_query.original)
        detected_tags = analysis.get("tags", [])

        # Branch A: Tags retrieval
        tags_results = []
        if detected_tags and self.tags_retriever:
            try:
                # Parse detected tags into structured format
                # PIDQueryEnhancer returns tag strings; parse into parts
                parsed_tags = self._parse_detected_tags(detected_tags)

                tags_results = self.tags_retriever.search(
                    query=transformed_query.original,
                    detected_tags=parsed_tags,
                    top_k=50,  # Get more candidates for fusion
                )
                logger.info(f"Tags branch returned {len(tags_results)} results")
            except Exception as e:
                logger.warning(f"Tags retrieval failed: {e}")

        # Branch B: Standard chunks retrieval
        chunks_results = self.hybrid_retriever.search(
            transformed_query, top_k=50, **kwargs
        )
        logger.info(f"Chunks branch returned {len(chunks_results)} results")

        # RRF Fusion
        if tags_results:
            fused_results = self._rrf_fusion(
                tags_results=tags_results,
                chunks_results=chunks_results,
                k=self.hybrid_config.rrf_k,
            )
            logger.info(f"RRF fusion: {len(fused_results)} combined results")
        else:
            # No tags results, use chunks only
            fused_results = chunks_results

        # Return top-k
        return fused_results[:top_k]

    def _parse_detected_tags(self, tag_strings: List[str]) -> List[Dict]:
        """
        Parse detected tag strings into structured format

        Args:
            tag_strings: List of tag strings (e.g., ["04 PSAL 2207", "PAL 2208"])

        Returns:
            List of dicts with tag and parts
        """
        import re

        parsed = []

        # Pattern: optional AREA + CODE + NUM (+ optional suffix)
        pattern = re.compile(r"(?:(\d{2})\s+)?([A-Z]{2,4})\s+(\d{3,5}[A-Z]?)")

        for tag_str in tag_strings:
            match = pattern.search(tag_str)
            if match:
                area, code, num = match.groups()
                parsed.append(
                    {
                        "tag": tag_str,
                        "parts": {
                            "area": area,
                            "code": code,
                            "num": num,
                        },
                    }
                )
            else:
                # Fallback: treat as full tag text
                parsed.append({"tag": tag_str, "parts": {}})

        return parsed

    def _rrf_fusion(
        self,
        tags_results: List[Dict],
        chunks_results: List[RetrievalResult],
        k: int = 60,
    ) -> List[RetrievalResult]:
        """
        RRF fusion of tags and chunks results

        Args:
            tags_results: Results from tags retriever
            chunks_results: Results from chunks retriever
            k: RRF constant

        Returns:
            Fused results sorted by RRF score
        """
        rrf_scores = {}
        result_map = {}

        # Add tags results
        for rank, tag_result in enumerate(tags_results):
            chunk_id = tag_result["chunk_id"]
            rrf_scores[chunk_id] = 1.0 / (k + rank + 1)

            # Convert to RetrievalResult
            result_map[chunk_id] = RetrievalResult(
                chunk_id=chunk_id,
                text=tag_result["text"],
                doc_id=tag_result["doc_id"],
                page=tag_result["page"],
                score=tag_result["score"],
                metadata={
                    "source": "tags",
                    "bbox": tag_result.get("bbox"),
                    "crop_path": tag_result.get("crop_path"),
                    "tag_parts": tag_result.get("tag_parts"),
                    "tag_confidence": tag_result.get("confidence"),
                },
            )

        # Add chunks results
        for rank, chunk_result in enumerate(chunks_results):
            chunk_id = chunk_result.chunk_id

            if chunk_id in rrf_scores:
                # Already in tags results, add to score
                rrf_scores[chunk_id] += 1.0 / (k + rank + 1)
            else:
                rrf_scores[chunk_id] = 1.0 / (k + rank + 1)
                result_map[chunk_id] = chunk_result

        # Sort by RRF score
        sorted_ids = sorted(
            rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True
        )

        fused_results = []
        for chunk_id in sorted_ids:
            result = result_map[chunk_id]
            # Attach RRF score
            result.fused_score = rrf_scores[chunk_id]
            fused_results.append(result)

        return fused_results

    def health_check(self) -> Dict[str, Any]:
        """Health check for all components"""
        health = {
            "retriever_type": "hybrid_with_tags",
            "components": {},
        }

        # Check hybrid retriever
        health["components"]["hybrid"] = self.hybrid_retriever.health_check()

        # Check tags retriever
        if self.tags_enabled and self.tags_retriever:
            health["components"]["tags"] = self.tags_retriever.health_check()
        else:
            health["components"]["tags"] = {"status": "disabled"}

        # Determine overall status
        hybrid_ok = health["components"]["hybrid"]["overall_status"] == "healthy"
        tags_status = health["components"]["tags"]["status"]

        if hybrid_ok:
            if tags_status in ["healthy", "disabled"]:
                health["overall_status"] = "healthy"
            else:
                health["overall_status"] = "degraded"  # Tags down but chunks OK
        else:
            health["overall_status"] = "critical"

        return health
