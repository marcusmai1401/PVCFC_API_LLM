"""
P&ID Fallback Enhancer Module

Enhanced semantic fallback search specifically for P&ID queries when spatial search fails.

Architecture:
1. Query expansion with tag variants
2. Tag-boosted OpenSearch search
3. Semantic Weaviate support
4. Adaptive RRF fusion (OpenSearch-heavy)
5. PID tag reranking (pre-BGE)
6. BGE reranking (final)
7. Post-BGE safety check

Usage:
    enhancer = PIDFallbackEnhancer(config={...})
    results = enhancer.search_with_enhancements(
        transformed_query=query,
        analysis=analysis,
        opensearch_retriever=os_retriever,
        weaviate_retriever=wv_retriever,
        top_k=10
    )
"""

from collections import defaultdict
from typing import Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.rag.query_transform import TransformedQuery
from app.rag.retriever import RetrievalResult


class PIDFallbackEnhancer:
    """
    Enhanced semantic fallback for P&ID queries

    Features:
    - Tag variant generation from components
    - Tag-boosted OpenSearch retrieval
    - Adaptive RRF fusion (keyword-heavy)
    - PID tag reranking (pre-BGE)
    - Post-BGE safety check
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize P&ID fallback enhancer

        Args:
            config: Configuration dict with:
                - opensearch_weight: RRF weight for OpenSearch (default: 1.0)
                - weaviate_weight: RRF weight for Weaviate (default: 0.3)
                - enable_tag_rerank: Enable PID tag reranking (default: True)
                - enable_safety_check: Enable post-BGE safety check (default: True)
                - max_variants: Max tag variants to generate (default: 4)
        """
        config = config or {}

        self.opensearch_weight = config.get("opensearch_weight", 1.0)
        self.weaviate_weight = config.get("weaviate_weight", 0.3)
        self.enable_tag_rerank = config.get("enable_tag_rerank", True)
        self.enable_safety_check = config.get("enable_safety_check", True)
        self.max_variants = config.get("max_variants", 4)
        self.rrf_k = 60

        # Initialize PID tag reranker if enabled
        self.tag_reranker = None
        if self.enable_tag_rerank:
            try:
                from app.rag.rerankers.pid_tag_reranker import PIDTagReranker

                self.tag_reranker = PIDTagReranker(
                    boost_meta_exact=10.0,
                    boost_text_exact=5.0,
                    boost_proximity=3.0,
                    fuzzy_threshold=90,
                )
                logger.info("PID tag reranker initialized for fallback")
            except Exception as e:
                logger.warning(f"Failed to init PID tag reranker: {e}")
                self.enable_tag_rerank = False

        logger.info(
            f"PIDFallbackEnhancer initialized: OS_weight={self.opensearch_weight}, "
            f"WV_weight={self.weaviate_weight}, tag_rerank={self.enable_tag_rerank}, "
            f"safety_check={self.enable_safety_check}"
        )

    def generate_tag_variants(self, components: Dict) -> List[str]:
        """
        Generate tag variants from components for fuzzy matching

        Examples:
            Input: {unit: '29', prefix: 'TE', suffix: '2038', variant: 'A'}
            Output: ['29 TE 2038A', '29TE2038A', '29-TE-2038A', 'TE 2038A']

        Args:
            components: Dict with unit, prefix, suffix, variant keys

        Returns:
            List of tag variant strings (limited to max_variants)
        """
        variants = []
        unit = components.get("unit", "")
        prefix = components.get("prefix", "")
        suffix = components.get("suffix", "")
        variant = components.get("variant", "")

        # Full canonical tag (with unit)
        if unit and prefix and suffix:
            canonical = f"{unit} {prefix} {suffix}{variant}"
            variants.append(canonical)
            variants.append(canonical.replace(" ", ""))  # No spaces: 29TE2038A
            variants.append(canonical.replace(" ", "-"))  # Hyphens: 29-TE-2038A

        # Without unit (prefix + suffix)
        if prefix and suffix:
            no_unit = f"{prefix} {suffix}{variant}"
            variants.append(no_unit)  # TE 2038A

        # Deduplicate while preserving order
        seen = set()
        unique_variants = []
        for v in variants:
            if v and v not in seen:
                seen.add(v)
                unique_variants.append(v)

        # Limit to max_variants
        result = unique_variants[: self.max_variants]
        logger.debug(f"Generated {len(result)} tag variants: {result}")
        return result

    def search_with_enhancements(
        self,
        transformed_query: TransformedQuery,
        analysis: Dict,
        opensearch_retriever,
        weaviate_retriever,
        top_k: int = 10,
    ) -> List[RetrievalResult]:
        """
        Enhanced P&ID semantic fallback search

        Pipeline:
        1. Generate tag variants from components
        2. Tag-boosted OpenSearch search (reuse existing method)
        3. Standard Weaviate semantic search
        4. Adaptive RRF fusion (OpenSearch-heavy)
        5. PID tag reranking (pre-BGE)
        6. BGE reranking (if enabled)
        7. Post-BGE safety check

        Args:
            transformed_query: Transformed query object
            analysis: PID query analysis dict with components
            opensearch_retriever: OpenSearchBM25Retriever instance
            weaviate_retriever: WeaviateRetriever instance
            top_k: Final number of results to return

        Returns:
            List of enhanced retrieval results
        """
        logger.info("=" * 60)
        logger.info("P&ID Enhanced Fallback Search Started")
        logger.info("=" * 60)

        # Step 1: Extract components and generate variants
        components = analysis.get("components", {})
        variants = self.generate_tag_variants(components)

        if not variants:
            logger.warning("No tag variants generated, falling back to standard search")
            # Fallback to standard if no variants
            from app.rag.hybrid_weaviate_opensearch_retriever import (
                HybridWeaviateOpenSearchRetriever,
            )

            standard_retriever = HybridWeaviateOpenSearchRetriever()
            return standard_retriever.search(transformed_query, top_k)

        logger.info(f"Step 1: Generated {len(variants)} tag variants: {variants}")

        # Step 2: Tag-boosted OpenSearch search
        opensearch_results = []
        try:
            logger.info("Step 2: Tag-boosted OpenSearch search...")
            opensearch_results = opensearch_retriever.search_with_tag_boosting(
                query=transformed_query.normalized, detected_tags=variants, top_k=50
            )
            logger.info(
                f"   → OpenSearch (tag-boosted): {len(opensearch_results)} results"
            )
        except Exception as e:
            logger.error(f"OpenSearch tag-boosted search failed: {e}")

        # Step 3: Weaviate semantic search
        weaviate_results = []
        try:
            logger.info("Step 3: Weaviate semantic search...")
            # WeaviateRetriever.search() takes (transformed_query, config_override)
            # It uses config.retrieval_limit and config.top_k_final internally
            from app.rag.weaviate_retriever import WeaviateSearchConfig

            wv_config = WeaviateSearchConfig(
                retrieval_limit=50,
                top_k_final=50,
                enable_bge_rerank=False,  # We do BGE later
            )
            weaviate_results = weaviate_retriever.search(
                transformed_query, config_override=wv_config
            )
            logger.info(f"   → Weaviate (semantic): {len(weaviate_results)} results")
        except Exception as e:
            logger.error(f"Weaviate search failed: {e}")

        # Check if we have any results
        if not opensearch_results and not weaviate_results:
            logger.warning("No results from either OpenSearch or Weaviate!")
            return []

        # Step 4: Adaptive RRF fusion
        logger.info("Step 4: Adaptive RRF fusion (OpenSearch-heavy)...")
        fused = self._adaptive_rrf_fusion(
            opensearch_results=opensearch_results,
            weaviate_results=weaviate_results,
            opensearch_weight=self.opensearch_weight,
            weaviate_weight=self.weaviate_weight,
        )
        logger.info(f"   → RRF fusion: {len(fused)} combined results")

        # Step 5: PID tag reranking (pre-BGE)
        if self.enable_tag_rerank and self.tag_reranker and fused:
            try:
                logger.info("Step 5: PID tag reranking (pre-BGE)...")
                # Convert to dict format for PID reranker
                fused_dicts = []
                for r in fused:
                    if isinstance(r, dict):
                        fused_dicts.append(r)
                    else:
                        fused_dicts.append(
                            {
                                "chunk_id": r.chunk_id,
                                "text": r.text,
                                "score": r.score,
                                "source": r.source,
                                "metadata": r.metadata,
                            }
                        )

                # PID reranker returns list of dicts
                fused_dicts = self.tag_reranker.rerank(
                    results=fused_dicts, query_tags=variants, top_k=60
                )

                # Convert back to RetrievalResult
                fused = []
                for d in fused_dicts:
                    fused.append(
                        RetrievalResult(
                            chunk_id=d.get("chunk_id", "unknown"),
                            text=d.get("text", ""),
                            score=float(
                                d.get("final_score", d.get("score", 0.0))
                            ),  # Ensure Python float
                            source="pid_fallback_tag_rerank",
                            metadata=d.get("metadata", {}),
                        )
                    )

                if fused:
                    logger.info(f"   → PID reranking: top score={fused[0].score:.4f}")
            except Exception as e:
                logger.warning(f"PID tag reranking failed: {e}, continuing without it")

        # Step 6: BGE reranking (if enabled)
        if fused and settings.enable_bge_rerank:
            try:
                logger.info("Step 6: BGE reranking (final semantic)...")
                from app.services.reranker import get_reranker_service

                reranker = get_reranker_service()
                # Convert RetrievalResult to dict format for reranker
                chunks_for_rerank = []
                for r in fused:
                    chunk_dict = {
                        "text": r.text,
                        "chunk_id": r.chunk_id,
                        "score": r.score,
                        "metadata": r.metadata,
                    }
                    chunks_for_rerank.append(chunk_dict)

                # RerankerService.rerank_chunks(query, chunks, top_k)
                reranked = reranker.rerank_chunks(
                    query=transformed_query.normalized,
                    chunks=chunks_for_rerank,
                    top_k=top_k,
                )

                # Convert back to RetrievalResult
                fused = []
                for chunk_dict, score in reranked:
                    fused.append(
                        RetrievalResult(
                            chunk_id=chunk_dict.get("chunk_id", "unknown"),
                            text=chunk_dict.get("text", ""),
                            score=float(score),  # Convert numpy.float32 to Python float
                            source="pid_fallback_bge",
                            metadata=chunk_dict.get("metadata", {}),
                        )
                    )

                logger.info(f"   → BGE reranking: {len(fused)} final results")
            except Exception as e:
                logger.warning(f"BGE reranking failed: {e}, using RRF results")
                fused = fused[:top_k]

        # Step 7: Post-BGE safety check
        if self.enable_safety_check and fused:
            logger.info("Step 7: Post-BGE safety check...")
            fused = self._post_bge_safety_check(fused, variants)

        logger.info("=" * 60)
        logger.info(f"P&ID Enhanced Fallback Complete: {len(fused[:top_k])} results")
        logger.info("=" * 60)

        return fused[:top_k]

    def _adaptive_rrf_fusion(
        self,
        opensearch_results: List,
        weaviate_results: List,
        opensearch_weight: float = 1.0,
        weaviate_weight: float = 0.3,
    ) -> List[RetrievalResult]:
        """
        Adaptive RRF fusion with configurable weights

        Formula: score = os_weight * 1/(k+rank_os) + wv_weight * 1/(k+rank_wv)

        Args:
            opensearch_results: Results from OpenSearch
            weaviate_results: Results from Weaviate
            opensearch_weight: Weight for OpenSearch (default: 1.0 for tags)
            weaviate_weight: Weight for Weaviate (default: 0.3 for support)

        Returns:
            Fused and sorted results
        """
        rrf_scores = defaultdict(float)
        result_map = {}

        # Add OpenSearch results
        for rank, result in enumerate(opensearch_results):
            # Handle both dict and RetrievalResult
            if isinstance(result, dict):
                chunk_id = result.get("metadata", {}).get("chunk_id") or result.get(
                    "chunk_id"
                )
                if chunk_id:
                    rrf_scores[chunk_id] += opensearch_weight / (self.rrf_k + rank + 1)
                    result_map[chunk_id] = result
            else:
                chunk_id = result.chunk_id
                rrf_scores[chunk_id] += opensearch_weight / (self.rrf_k + rank + 1)
                result_map[chunk_id] = result

        # Add Weaviate results
        for rank, result in enumerate(weaviate_results):
            if isinstance(result, dict):
                chunk_id = result.get("metadata", {}).get("chunk_id") or result.get(
                    "chunk_id"
                )
                if chunk_id:
                    rrf_scores[chunk_id] += weaviate_weight / (self.rrf_k + rank + 1)
                    if chunk_id not in result_map:
                        result_map[chunk_id] = result
            else:
                chunk_id = result.chunk_id
                rrf_scores[chunk_id] += weaviate_weight / (self.rrf_k + rank + 1)
                if chunk_id not in result_map:
                    result_map[chunk_id] = result

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Build result list - always return RetrievalResult objects
        fused_results = []
        for chunk_id, rrf_score in sorted_ids:
            result = result_map[chunk_id]

            # Convert everything to RetrievalResult for consistency
            if isinstance(result, dict):
                fused_results.append(
                    RetrievalResult(
                        chunk_id=result.get("chunk_id", chunk_id),
                        text=result.get("text", ""),
                        score=float(rrf_score),  # Ensure Python float
                        source="pid_fallback_rrf",
                        metadata=result.get("metadata", {}),
                    )
                )
            else:
                # Already RetrievalResult, just update score
                result.score = float(rrf_score)  # Ensure Python float
                result.source = "pid_fallback_rrf"
                fused_results.append(result)

        return fused_results

    def _post_bge_safety_check(self, results: List, tag_variants: List[str]) -> List:
        """
        Force exact tag matches to top 3 if BGE pushed them down

        Prevents semantic drift where exact matches are ranked lower than
        semantically similar but incorrect results.

        Args:
            results: Results after BGE reranking
            tag_variants: List of tag variants to check

        Returns:
            Results with exact matches promoted to top 3
        """
        if len(results) <= 3:
            return results

        # Find exact matches
        exact_matches = []
        for i, result in enumerate(results):
            # Get text and tags from result
            if isinstance(result, dict):
                text = result.get("text", "").upper()
                metadata_tags = [
                    t.upper() for t in result.get("metadata", {}).get("tags", [])
                ]
            else:
                text = result.text.upper()
                metadata_tags = [t.upper() for t in result.metadata.get("tags", [])]

            # Check if any variant appears exactly
            for variant in tag_variants:
                variant_upper = variant.upper()
                if variant_upper in text or variant_upper in metadata_tags:
                    exact_matches.append((i, result))
                    logger.debug(f"Exact match found at rank {i+1}: {variant}")
                    break

        if not exact_matches:
            logger.debug("No exact matches found in results")
            return results

        # Check if top exact match is ranked >3
        top_exact = exact_matches[0]
        if top_exact[0] > 2:  # Ranked 4th or lower
            logger.warning(
                f"⚠️  Exact match found at rank {top_exact[0]+1}, forcing to rank 1"
            )
            results_copy = list(results)
            results_copy.pop(top_exact[0])
            results_copy.insert(0, top_exact[1])
            return results_copy
        else:
            logger.info(f"✓ Exact match already in top 3 (rank {top_exact[0]+1})")

        return results

    def _ensure_retrieval_results(self, results: List) -> List[RetrievalResult]:
        """
        Ensure all results are RetrievalResult objects

        Converts dict results to RetrievalResult if needed for BGE reranking

        Args:
            results: Mixed list of dicts and RetrievalResult objects

        Returns:
            List of RetrievalResult objects
        """
        converted = []
        for r in results:
            if isinstance(r, RetrievalResult):
                converted.append(r)
            elif isinstance(r, dict):
                # Convert dict to RetrievalResult
                metadata = r.get("metadata", {})
                converted.append(
                    RetrievalResult(
                        chunk_id=metadata.get("chunk_id", "unknown"),
                        text=r.get("text", ""),
                        score=r.get("score", 0.0),
                        source=r.get("source", "unknown"),
                        metadata=metadata,
                        doc_id=metadata.get("doc_id"),
                        page=metadata.get("page"),
                        bbox=None,
                        parent_id=None,
                    )
                )
        return converted
