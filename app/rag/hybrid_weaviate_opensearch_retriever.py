"""
Hybrid Weaviate + OpenSearch Retriever (Modern Architecture)

Combines:
- Weaviate (semantic/vector search)
- OpenSearch BM25 (keyword search)
- RRF (Reciprocal Rank Fusion)
- BGE CrossEncoder Reranking (optional)

This is the production retriever replacing legacy FAISS + BM25 offline.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.core.config import settings
from app.rag.indexers.opensearch_bm25_retriever import create_opensearch_retriever
from app.rag.query_transform import TransformedQuery
from app.rag.retriever import RetrievalResult, extract_text_with_parent_fallback
from app.rag.weaviate_retriever import WeaviateRetriever, WeaviateSearchConfig
from app.services.reranker import get_reranker_service


@dataclass
class HybridModernConfig:
    """Configuration for modern hybrid retrieval"""

    # Retrieval limits (increased to 100 for better recall on diagram-heavy documents)
    weaviate_limit: int = 100  # Candidates from Weaviate
    opensearch_limit: int = 100  # Candidates from OpenSearch

    # Fusion
    rrf_k: int = 60  # RRF constant
    top_rrf: int = 60  # Results after RRF

    # Reranking
    enable_bge_rerank: bool = (
        True  # Use BGE reranking (must stay True for technical docs)
    )
    bge_top_k: int = 20  # Final results after BGE (increased to match MAX_CONTEXT)
    bge_level: str = "chunk"  # chunk, doc, or page
    bge_aggregation: str = "max"  # max, mean, or top3_mean

    def __post_init__(self):
        """Post-initialization: load from settings and apply hard guards.

        1. Override limits from settings if available (allows ENV config)
        2. Hard guard: never allow BGE rerank to be disabled at runtime.
        """
        # Load retrieval limits from settings (ENV override)
        try:
            if hasattr(settings, "weaviate_retrieval_limit"):
                self.weaviate_limit = settings.weaviate_retrieval_limit
            if hasattr(settings, "opensearch_retrieval_limit"):
                self.opensearch_limit = settings.opensearch_retrieval_limit
            if hasattr(settings, "bge_rerank_candidate_limit"):
                # Update top_rrf to match candidate limit
                self.top_rrf = settings.bge_rerank_candidate_limit
            if hasattr(settings, "bge_rerank_top_k"):
                # Override final top_k from settings
                self.bge_top_k = settings.bge_rerank_top_k
        except Exception as e:
            logger.warning(f"Failed to load retrieval limits from settings: {e}")

        # Hard guard: BGE rerank must always be enabled
        if not self.enable_bge_rerank:
            from loguru import logger as _logger

            _logger.warning(
                "HybridModernConfig received enable_bge_rerank=False - overriding to True"
            )
            self.enable_bge_rerank = True


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
            top_k_final=self.config.weaviate_limit,  # ⚠️ ADDED: Return full limit to Fusion
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
        top_k: Optional[int] = None,
        config_override: Optional[HybridModernConfig] = None,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Hybrid search with Weaviate + OpenSearch

        Args:
            transformed_query: Transformed query with filters
            top_k: Optional top_k override (if provided, overrides config.bge_top_k)
            config_override: Optional config override
            **kwargs: Additional arguments (ignored, for compatibility)

        Returns:
            List of retrieval results (fused and optionally reranked)
        """
        config = config_override or self.config

        # Use top_k override if provided, otherwise use config value
        effective_top_k = top_k if top_k is not None else config.bge_top_k

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
                    top_k=effective_top_k,
                )
                logger.info(f"BGE reranking complete: {len(fused_results)} results")
            except Exception as e:
                logger.error(f"BGE reranking failed: {e}, using RRF results")
                # Graceful degradation: use RRF results
                fused_results = fused_results[:effective_top_k]
        else:
            # No BGE, just limit to top_k
            fused_results = fused_results[:effective_top_k]

        # Final sanitation: ensure page numbers are consistent (avoid 0/None when possible)
        fused_results = self._sanitize_pages(fused_results)

        logger.info(f"Final result count: {len(fused_results)}")
        return fused_results

    def retrieve_enhanced(
        self,
        query: str,
        top_k: int = 10,
        enable_pid_enhancement: bool = True,
        config_override: Optional[HybridModernConfig] = None,
    ) -> List[RetrievalResult]:
        """
        Enhanced retrieval with P&ID tag awareness

        Flow:
        1. PID Query Enhancement (detect tags, variants, query_type)
        2. Parallel search (OpenSearch + Weaviate) with boosting/filtering
        3. Adaptive RRF fusion (weights based on query_type)
        4. PID Tag Reranking (boost exact/fuzzy matches)
        5. BGE Reranking (final semantic ordering)

        Args:
            query: User query string
            top_k: Final number of results to return
            enable_pid_enhancement: Enable P&ID-specific enhancements
            config_override: Optional config override

        Returns:
            Enhanced retrieval results optimized for P&ID queries
        """
        config = config_override or self.config

        logger.info("=" * 80)
        logger.info(f"ENHANCED RETRIEVAL: '{query}'")
        logger.info(f"PID Enhancement: {enable_pid_enhancement}")
        logger.info("=" * 80)

        # Step 1: Query enhancement
        if enable_pid_enhancement:
            from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer

            enhancer = PIDQueryEnhancer()
            enhanced = enhancer.enhance(query)
        else:
            enhanced = {"strategy": "semantic", "original": query}

        strategy = enhanced["strategy"]
        query_type = enhanced.get("query_type", "semantic")

        logger.info(f"→ Strategy: {strategy}, Type: {query_type}")

        # Step 2: Retrieval with boosting/filtering
        if strategy == "tag_focused":
            tags = enhanced["tags"]
            logger.info(f"→ Tag-focused retrieval for tags: {tags}")

            # OpenSearch: tag-boosted search
            try:
                logger.debug("  Searching OpenSearch with tag boosting...")
                opensearch_results = self._search_opensearch_tag_boosted(
                    query=enhanced["original"],
                    detected_tags=tags,
                    top_k=config.opensearch_limit,
                )
                logger.info(f"  OpenSearch: {len(opensearch_results)} results")
            except Exception as e:
                logger.error(f"  OpenSearch tag-boosted search failed: {e}")
                opensearch_results = []

            # Weaviate: tag-filtered search
            try:
                logger.debug("  Searching Weaviate with tag filter...")
                weaviate_results = self.weaviate_retriever.search_with_tag_filter(
                    query=enhanced["original"],
                    tag_filter=tags,
                    limit=config.weaviate_limit,
                )
                logger.info(f"  Weaviate: {len(weaviate_results)} results")
            except Exception as e:
                logger.error(f"  Weaviate tag-filtered search failed: {e}")
                weaviate_results = []

        else:
            # Normal hybrid search
            logger.info(f"→ Normal hybrid search (strategy: {strategy})")

            # OpenSearch
            try:
                opensearch_results = self._search_opensearch(
                    query=enhanced["original"], top_k=config.opensearch_limit
                )
                logger.info(f"  OpenSearch: {len(opensearch_results)} results")
            except Exception as e:
                logger.error(f"  OpenSearch search failed: {e}")
                opensearch_results = []

            # Weaviate
            try:
                from app.rag.query_transform import QueryFilters, TransformedQuery

                transformed = TransformedQuery(
                    original=query,
                    normalized=query.lower(),
                    intent=None,
                    filters=QueryFilters(),
                    language="en",
                )
                weaviate_results = self.weaviate_retriever.search(transformed)
                logger.info(f"  Weaviate: {len(weaviate_results)} results")
            except Exception as e:
                logger.error(f"  Weaviate search failed: {e}")
                weaviate_results = []

        # Check if we have any results
        if not opensearch_results and not weaviate_results:
            logger.warning("No results from either backend!")
            return []

        # Step 3: Adaptive RRF fusion
        logger.info(f"→ Applying adaptive RRF fusion (type: {query_type})")
        fused_results = self._rrf_fusion_adaptive(
            opensearch_results=opensearch_results,
            weaviate_results=weaviate_results,
            query_type=query_type,
            k=config.rrf_k,
            top_n=config.top_rrf,
        )

        # Step 4: PID Tag Reranking (before BGE)
        if strategy == "tag_focused":
            from app.rag.rerankers.pid_tag_reranker import PIDTagReranker

            logger.info(f"→ Applying PID tag reranking")
            pid_reranker = PIDTagReranker()
            fused_results = pid_reranker.rerank(
                results=[r.__dict__ for r in fused_results],  # Convert to dict
                query_tags=enhanced["tags"],
                top_k=50,  # Keep more candidates for BGE
            )

            # Convert back to RetrievalResult
            fused_results = [
                RetrievalResult(
                    chunk_id=r.get("chunk_id") or r.get("metadata", {}).get("chunk_id"),
                    text=r["text"],
                    score=r["final_score"],
                    source=r.get("source", "unknown"),
                    metadata=r.get("metadata", {}),
                    doc_id=r.get("doc_id") or r.get("metadata", {}).get("doc_id"),
                    # Use 'is not None' to handle page=0 correctly
                    page=r.get("page")
                    if r.get("page") is not None
                    else r.get("metadata", {}).get("page"),
                    bbox=None,
                    parent_id=None,
                )
                for r in fused_results
            ]

        # Step 4.5: Apply exact match guardrails BEFORE BGE
        # This ensures exact matches are identified in the full candidate list
        # and protected from being filtered out by BGE's top_k truncation
        # Safety Quota: max 20 exact matches to reserve slots for semantic search
        logger.info(f"→ Checking for exact code matches in candidate list")
        exact_matches, remaining_candidates = self._extract_exact_matches(
            query=enhanced["original"],
            results=fused_results,
            limit=20,  # Safety quota: max 20 exact matches
        )

        # Step 5: BGE Reranking (final)
        if config.enable_bge_rerank and settings.enable_bge_rerank:
            logger.info(f"→ Applying BGE reranking to remaining candidates")
            try:
                # Rerank only the non-exact-match candidates
                if remaining_candidates:
                    bge_results = self._apply_bge_reranking(
                        query=enhanced["original"],
                        results=remaining_candidates,
                        top_k=top_k
                        - len(exact_matches),  # Reserve slots for exact matches
                    )
                else:
                    bge_results = []

                # Combine: exact matches first, then BGE-reranked results
                final_results = exact_matches + bge_results
                final_results = final_results[:top_k]  # Ensure we don't exceed top_k

            except Exception as e:
                logger.error(
                    f"  BGE reranking failed: {e}, using candidates with exact matches"
                )
                final_results = (exact_matches + remaining_candidates)[:top_k]
        else:
            # No BGE: just combine exact matches + remaining candidates
            final_results = (exact_matches + remaining_candidates)[:top_k]

        # Sanitize pages before returning
        final_results = self._sanitize_pages(final_results)

        logger.info("=" * 80)
        logger.info(f"ENHANCED RETRIEVAL COMPLETE: {len(final_results)} final results")
        logger.info("=" * 80)

        return final_results

    def _search_opensearch_tag_boosted(
        self, query: str, detected_tags: List[str], top_k: int
    ) -> List[RetrievalResult]:
        """
        Search OpenSearch with tag boosting and convert to RetrievalResult

        Args:
            query: Query string
            detected_tags: Detected equipment tags
            top_k: Number of results

        Returns:
            List of RetrievalResult objects
        """
        # Call tag-boosted search
        opensearch_hits = self.opensearch_retriever.search_with_tag_boosting(
            query=query, detected_tags=detected_tags, top_k=top_k
        )

        # Convert to RetrievalResult format
        results = []
        for hit in opensearch_hits:
            metadata = hit.get("metadata", {})

            result = RetrievalResult(
                chunk_id=metadata.get("chunk_id", hit.get("chunk_id", "unknown")),
                text=extract_text_with_parent_fallback(
                    hit, metadata
                ),  # Phase 3: Use parent_text
                score=hit["score"],
                source="opensearch_tag_boosted",
                metadata=metadata,
                doc_id=metadata.get("doc_id"),
                page=metadata.get("page"),
                bbox=None,
                parent_id=None,
            )
            results.append(result)

        return results

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
                text=extract_text_with_parent_fallback(
                    hit, metadata
                ),  # Phase 3: Use parent_text
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

    def _detect_special_codes(self, query: str) -> List[str]:
        """
        Detect special codes in query (equipment codes, drawing codes, part numbers).

        Pattern matches:
        - Equipment codes: HCD025, E-04217, KT06101
        - Drawing codes: LS006343, ABC-1234
        - Part numbers: 2+ uppercase letters followed by optional hyphen and 4+ digits

        Args:
            query: Search query string

        Returns:
            List of detected codes (deduplicated, uppercase)
        """
        # Pattern for equipment/drawing codes:
        # - Format 1: 2+ uppercase letters + optional hyphen + 3+ digits (HCD025, LS006343, KT06101)
        # - Format 2: 1 uppercase letter + hyphen + 4+ digits (E-04217)
        # Using alternation to handle both formats
        pattern = r"[A-Z]{2,}[-]?\d{3,}|[A-Z]-\d{4,}"

        # Normalize to ASCII (remove accents from Vietnamese characters)
        # This allows [A-Z] to match all ASCII uppercase letters
        import unicodedata

        normalized = unicodedata.normalize("NFD", query.upper())
        ascii_query = normalized.encode("ascii", "ignore").decode("ascii")

        # Extract codes from ASCII-normalized query
        codes = re.findall(pattern, ascii_query)

        # Deduplicate while preserving order
        seen = set()
        unique_codes = []
        for code in codes:
            if code not in seen:
                seen.add(code)
                unique_codes.append(code)

        return unique_codes

    def _extract_exact_matches(
        self, query: str, results: List[RetrievalResult], limit: int = 20
    ) -> Tuple[List[RetrievalResult], List[RetrievalResult]]:
        """
        Extract exact code matches from candidate list with SAFETY QUOTA enforcement.

        Problem: BGE reranker may filter out exact matches if they have low semantic scores.
        Additionally, header/footer flooding can fill top_k with noise.

        Solution:
        1. Identify ALL exact matches in full candidate list
        2. SORT by original RRF/BM25 score (descending)
        3. TRUNCATE to top {limit} exact matches only
        4. Reserve remaining slots for BGE semantic search

        Safety Quota: Ensures at least (top_k - limit) slots for semantic results.

        Args:
            query: Original query string
            results: Full candidate list (fused results before BGE)
            limit: Maximum exact matches to keep (default: 20)

        Returns:
            Tuple of (exact_matches[:limit], all_remaining_candidates)
        """
        # Detect special codes in query
        query_codes = self._detect_special_codes(query)

        if not query_codes:
            # No codes detected, all results go to "remaining"
            logger.debug("No special codes detected in query")
            return [], results

        logger.info(f"🎯 Exact Match Guardrails: Detected codes {query_codes}")

        # Classify results: exact matches vs remaining
        exact_matches = []
        remaining_candidates = []

        for result in results:
            # Check if chunk text contains any query codes (case-insensitive)
            text_upper = result.text.upper()
            has_exact_match = any(code in text_upper for code in query_codes)

            if has_exact_match:
                # Keep original RRF/BM25 score for sorting (DON'T boost yet)
                exact_matches.append(result)
                logger.debug(
                    f"  ✓ Exact match found: {result.chunk_id[:40]}... (score: {result.score:.3f})"
                )
            else:
                remaining_candidates.append(result)

        # SAFETY QUOTA: Sort exact matches by original score and truncate
        if exact_matches:
            # Sort by original RRF/BM25 score (descending) - best matches first
            exact_matches.sort(key=lambda x: x.score, reverse=True)

            # Apply safety limit
            before_truncate = len(exact_matches)
            exact_matches_top = exact_matches[:limit]
            exact_matches_dropped = exact_matches[limit:]

            # Boost ONLY the top-limited exact matches to 1.0
            for result in exact_matches_top:
                original_score = result.score
                result.score = 1.0  # Force to maximum
                logger.debug(
                    f"  ⚡ Top exact match: {result.chunk_id[:40]}... "
                    f"(score: {original_score:.3f} → 1.0)"
                )

            # Return dropped exact matches to remaining pool (with original scores)
            remaining_candidates.extend(exact_matches_dropped)

            logger.info(
                f"  🛡️ Safety Quota: {len(exact_matches_top)}/{before_truncate} exact matches kept "
                f"(limit={limit}, dropped={len(exact_matches_dropped)} to semantic pool)"
            )

            return exact_matches_top, remaining_candidates

        # No exact matches found
        return [], remaining_candidates

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

    def _rrf_fusion_adaptive(
        self,
        opensearch_results: List[RetrievalResult],
        weaviate_results: List[RetrievalResult],
        query_type: str = "mixed",
        k: int = 60,
        top_n: int = 60,
    ) -> List[RetrievalResult]:
        """
        Adaptive RRF fusion with query-type based weights

        Weight profiles:
        - tag_only:  OpenSearch=1.0, Weaviate=0.3 (keyword-heavy)
        - mixed:     OpenSearch=0.7, Weaviate=0.7 (balanced)
        - semantic:  OpenSearch=0.5, Weaviate=1.0 (semantic-heavy)
        - visual:    OpenSearch=0.4, Weaviate=0.6 (semantic-leaning)

        Args:
            opensearch_results: Results from OpenSearch (keyword)
            weaviate_results: Results from Weaviate (semantic)
            query_type: Query type classification
            k: RRF constant
            top_n: Number of results to return

        Returns:
            Fused results with adaptive weighting
        """
        # Define adaptive weights
        WEIGHT_MAP = {
            "tag_only": {"opensearch": 1.0, "weaviate": 0.3},
            "mixed": {"opensearch": 0.7, "weaviate": 0.7},
            "semantic": {"opensearch": 0.5, "weaviate": 1.0},
            "visual": {"opensearch": 0.4, "weaviate": 0.6},
        }

        weights = WEIGHT_MAP.get(query_type, WEIGHT_MAP["mixed"])

        logger.info(
            f"Adaptive RRF fusion: type={query_type}, "
            f"weights=[OS:{weights['opensearch']}, WV:{weights['weaviate']}]"
        )

        rrf_scores = defaultdict(float)
        all_results_dict = {}

        # OpenSearch contribution (keyword-focused)
        for rank, result in enumerate(opensearch_results):
            key = result.chunk_id or result.text[:200]
            rrf_contribution = weights["opensearch"] / (k + rank + 1)
            rrf_scores[key] += rrf_contribution

            if key not in all_results_dict:
                all_results_dict[key] = result

        logger.debug(
            f"OpenSearch contributed {len(opensearch_results)} results "
            f"with weight {weights['opensearch']}"
        )

        # Weaviate contribution (semantic-focused)
        for rank, result in enumerate(weaviate_results):
            key = result.chunk_id or result.text[:200]
            rrf_contribution = weights["weaviate"] / (k + rank + 1)
            rrf_scores[key] += rrf_contribution

            if key not in all_results_dict:
                all_results_dict[key] = result

        logger.debug(
            f"Weaviate contributed {len(weaviate_results)} results "
            f"with weight {weights['weaviate']}"
        )

        # Sort by RRF score
        sorted_results = sorted(
            [(key, score) for key, score in rrf_scores.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:top_n]

        # Build final results
        fused = []
        for key, rrf_score in sorted_results:
            result = all_results_dict[key]
            result.score = rrf_score
            result.source = f"rrf_{query_type}"
            fused.append(result)

        logger.info(
            f"Adaptive RRF fusion ({query_type}): produced {len(fused)} results, "
            f"top_score={fused[0].score:.4f}"
        )

        return fused

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

            # Create a mapping from chunk_id to original result for preserving metadata
            chunk_id_to_result = {r.chunk_id: r for r in results}

            # Convert back to RetrievalResult
            reranked_results = []
            for chunk, score in reranked_chunks:
                # Find the original result to preserve page, bbox, etc.
                original = chunk_id_to_result.get(chunk["chunk_id"])

                reranked_results.append(
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
                        page=original.page if original else None,
                        bbox=original.bbox if original else None,
                        parent_id=original.parent_id if original else None,
                    )
                )

            return reranked_results
        else:
            # For doc/page level, use chunk-level as fallback for now
            logger.warning(
                f"BGE reranking level '{level}' not fully implemented, using chunk-level"
            )
            return self._apply_bge_reranking(
                query, results, level="chunk", aggregation=aggregation, top_k=top_k
            )

    def _sanitize_pages(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Ensure each result has a valid page if possible.

        Strategy:
        - If result.page in (None, 0):
            - Use metadata['page'] if valid
            - Else extract from content markers <!-- Page N -->
            - Else parse from chunk_id patterns like '_p13_' or 'p13'
        - Keep page unchanged if already valid (>0)
        - Mirror back to metadata['page'] for consistency
        """
        try:
            from app.utils.page_utils import extract_page_from_content
        except Exception:
            extract_page_from_content = None

        for r in results:
            page = r.page
            if page in (None, 0):
                # 1) metadata
                meta_page = None
                try:
                    meta_page = r.metadata.get("page") if r.metadata else None
                except Exception:
                    meta_page = None
                if isinstance(meta_page, int) and meta_page > 0:
                    page = meta_page
                # 2) content markers
                if (
                    (page in (None, 0))
                    and extract_page_from_content is not None
                    and r.text
                ):
                    try:
                        p = extract_page_from_content(r.text)
                        if isinstance(p, int) and p > 0:
                            page = p
                    except Exception:
                        pass
                # 3) chunk_id pattern
                if page in (None, 0) and r.chunk_id:
                    try:
                        m = re.search(
                            r"[_\-]p(\d+)[_\-]", r.chunk_id, flags=re.IGNORECASE
                        )
                        if not m:
                            m = re.search(r"p(\d+)$", r.chunk_id, flags=re.IGNORECASE)
                        if m:
                            p = int(m.group(1))
                            if p > 0:
                                page = p
                    except Exception:
                        pass
                # Final fallback: avoid returning 0/None pages
                if page in (None, 0):
                    page = 1
                # Apply back
                r.page = page
                if r.metadata is None:
                    r.metadata = {}
                r.metadata["page"] = page
        return results

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
